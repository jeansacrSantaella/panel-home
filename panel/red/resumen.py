"""Resumen de la red (= /api/summary de NetWatch) para el panel."""
from __future__ import annotations

import re
import time
from typing import Callable, Dict, Optional

HORA = 3600
DIA = 86400
TRAMO_CINTA = 600                  # tramos de 10 minutos
TRAMOS = DIA // TRAMO_CINTA        # 144 tramos = 24 h
SERVICIOS = ("lan", "wan", "dns")
MAC_EN_DETALLE = re.compile(r"\(([0-9a-f:]{17})\)")


def calidad(filas) -> Optional[dict]:
    """filas: [(ms, ok)] en orden -> latencia media, jitter y % de pérdida."""
    if not filas:
        return None
    ms = [f[0] for f in filas if f[1] and f[0] is not None]
    difs = [abs(a - b) for a, b in zip(ms, ms[1:])]
    return {"avg": round(sum(ms) / len(ms), 1) if ms else None,
            "jitter": round(sum(difs) / len(difs), 1) if difs else None,
            "loss": round(100 * (1 - sum(f[1] for f in filas) / len(filas)), 1)}


def clave_ip(ip) -> tuple:
    try:
        return tuple(int(x) for x in (ip or "0.0.0.0").split("."))
    except ValueError:
        return (0, 0, 0, 0)


class ResumenRed:
    def __init__(self, red, fabricante: Callable, servicios: Callable, contratado: Optional[dict] = None,
                 reloj: Callable = time.time):
        self._red = red
        self._fabricante = fabricante
        self._servicios = servicios
        self._contratado = contratado if contratado is not None else {"down": 0, "up": 0}
        self._reloj = reloj

    def construir(self) -> dict:
        ahora = int(self._reloj())
        muestras = self._red.muestras_desde(ahora - HORA)
        inicio, cinta, uptime = self._disponibilidad(ahora)
        return {
            "now": ahora,
            "checks": self._servicios(),
            "ribbon_start": inicio, "ribbon": cinta, "uptime": uptime,
            "series": self._red.latencia_por_minuto(ahora - HORA),
            "hours": self._red.caidas_por_hora(),
            "devices": self._equipos(ahora, muestras),
            "events": self._red.eventos_recientes(60),
            "quality": {t: calidad(v) for (k, t), v in muestras.items() if k == "ping"},
            "speed": self._red.velocidad_reciente(48)[::-1],
            "contracted": self._contratado,
            "public_ip": self._red.get("ip_publica"),
        }

    def _equipos(self, ahora: int, muestras: dict) -> list:
        caidas: Dict[str, int] = {}
        for detalle in self._red.detalles_desde("device_offline", ahora - DIA):
            m = MAC_EN_DETALLE.search(detalle or "")
            if m:
                caidas[m.group(1)] = caidas.get(m.group(1), 0) + 1
        equipos = self._red.equipos()
        equipos.sort(key=lambda d: (-(d["online"] or 0), clave_ip(d["ip"])))
        for d in equipos:
            d["vendor"] = self._fabricante(d["mac"])
            d["q"] = calidad(muestras.get(("dev", d["mac"]), []))
            d["drops"] = caidas.get(d["mac"], 0)
        return equipos

    def _disponibilidad(self, ahora: int):
        """Aciertos por tramo; de cada servicio cuenta el mejor destino."""
        tramos = [ahora // TRAMO_CINTA - (TRAMOS - 1) + i for i in range(TRAMOS)]
        agg: Dict[str, Dict[int, float]] = {k: {} for k in SERVICIOS}
        for r in self._red.exito_por_tramo(tramos[0] * TRAMO_CINTA, TRAMO_CINTA):
            clave = "dns" if r["kind"] == "dns" else "lan" if r["target"] == "gateway" else "wan"
            agg[clave][r["b"]] = max(agg[clave].get(r["b"], 0), r["a"])
        cinta, uptime = {}, {}
        for k in SERVICIOS:
            vals = [agg[k].get(s) for s in tramos]
            cinta[k] = [None if v is None else round(v, 3) for v in vals]
            vistos = [v for v in vals if v is not None]
            uptime[k] = round(100 * sum(vistos) / len(vistos), 2) if vistos else None
        return tramos[0] * TRAMO_CINTA, cinta, uptime
