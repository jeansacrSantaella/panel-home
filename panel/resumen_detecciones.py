"""Resumen periódico de detecciones por Telegram (el mismo que mandaba el detector de gestorCamaras)."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Tuple

from panel import fuentes
from panel.telegram import TelegramError

log = logging.getLogger("panel.resumen")
CLAVE_ULTIMO = "resumen_detecciones_ultimo"
MAX_FOTOS = 10


def capturas_entre(grabaciones, desde: float, hasta: float) -> list:
    """Fotos de movimiento con desde <= hora < hasta: [{ts, camara, clases, dia, nombre}], por hora."""
    res = []
    dia = datetime.fromtimestamp(desde).date()
    ultimo = datetime.fromtimestamp(max(desde, hasta - 1)).date()
    while dia <= ultimo:
        fecha = dia.strftime("%Y-%m-%d")
        for nombre in grabaciones.fotos(fecha):
            cap = fuentes._captura(fecha, nombre)
            if cap and desde <= cap["ts"] < hasta:
                res.append({**cap, "dia": fecha, "nombre": nombre})
        dia += timedelta(days=1)
    return sorted(res, key=lambda c: c["ts"])


def conteo_texto(capturas: list, nombres: Callable[[], dict]) -> List[str]:
    """Una línea por cámara: '• Patio: 3 person, 1 cat'."""
    conteo: dict = {}
    for c in capturas:
        por_clase = conteo.setdefault(c["camara"], {})
        for cls in c["clases"]:
            por_clase[cls] = por_clase.get(cls, 0) + 1
    nombres = nombres() or {}
    return [f"• {nombres.get(cid, cid)}: " + ", ".join(f"{n} {cls}" for cls, n in clases.items())
            for cid, clases in conteo.items()]


def elegir_fotos(capturas: list, maximo: int = MAX_FOTOS) -> list:
    """Una por cámara y clase; si sobra espacio, completa con las más recientes."""
    elegidas, vistos = [], set()
    for c in capturas:
        for cls in c["clases"]:
            if (c["camara"], cls) not in vistos:
                vistos.add((c["camara"], cls))
                if c not in elegidas:
                    elegidas.append(c)
    elegidas = elegidas[:maximo]
    for c in reversed(capturas):
        if len(elegidas) >= maximo:
            break
        if c not in elegidas:
            elegidas.append(c)
    return sorted(elegidas, key=lambda c: c["ts"])


def leer_fotos(grabaciones, capturas: list) -> List[Tuple[bytes, str]]:
    """[(bytes, pie)] de las capturas que se puedan leer."""
    fotos = []
    for c in capturas:
        try:
            datos = grabaciones.ruta("fotos", c["dia"], c["nombre"]).read_bytes()
        except (OSError, Exception):
            continue
        fotos.append((datos, f"{c['hora']} · {c['camara']} · {', '.join(c['clases'])}"))
    return fotos


class ResumenDetecciones:
    def __init__(self, cfg, grabaciones, nombres_camaras: Callable[[], dict], cliente,
                 reloj: Callable[[], float] = time.time, db=None):
        self.cfg = cfg
        self.grabaciones = grabaciones
        self.nombres = nombres_camaras      # () -> {id: nombre}
        self.cliente = cliente
        self.reloj = reloj
        self.db = db
        self._ultimo: Optional[int] = None  # inicio del último bloque ya resumido

    def _cada(self) -> int:
        return max(1, int(self.cfg.resumen_cada_h))

    def _inicio_bloque(self, ahora: float) -> int:
        """Inicio (epoch) del bloque en curso: horas múltiplo de RESUMEN_CADA_H (pares si son 2)."""
        dt = datetime.fromtimestamp(ahora)
        h = dt.hour // self._cada() * self._cada()
        return int(dt.replace(hour=h, minute=0, second=0, microsecond=0).timestamp())

    def _leer_ultimo(self) -> Optional[int]:
        if self._ultimo is None and self.db is not None:
            self._ultimo = self.db.get(CLAVE_ULTIMO)
        return self._ultimo

    def _guardar_ultimo(self, valor: int) -> None:
        self._ultimo = valor
        if self.db is not None:
            self.db.set(CLAVE_ULTIMO, valor)

    def en_silencio(self, t: float) -> bool:
        h = time.localtime(t).tm_hour
        d, a = self.cfg.silencio_desde, self.cfg.silencio_hasta
        return (h >= d or h < a) if d > a else d <= h < a

    def toca(self, ahora: Optional[float] = None) -> bool:
        """True si empezó un bloque nuevo desde el último resumen. La primera vez solo marca el bloque en curso."""
        ahora = self.reloj() if ahora is None else ahora
        bloque = self._inicio_bloque(ahora)
        ultimo = self._leer_ultimo()
        if ultimo is None:
            self._guardar_ultimo(bloque)
            return False
        return bloque > ultimo

    def texto(self, desde: float, hasta: float, capturas: Optional[list] = None) -> str:
        capturas = capturas_entre(self.grabaciones, desde, hasta) if capturas is None else capturas
        t0, t1 = (time.strftime("%H:%M", time.localtime(t)) for t in (desde, hasta))
        if not capturas:
            return f"📷 Sin detecciones de {t0} a {t1}"
        return "\n".join([f"📷 Detecciones de {t0} a {t1}"] + conteo_texto(capturas, self.nombres))

    def enviar(self, ahora: Optional[float] = None) -> bool:
        """Manda el resumen del bloque anterior (con fotos fuera del silencio). True si se envió."""
        ahora = self.reloj() if ahora is None else ahora
        bloque = self._inicio_bloque(ahora)
        desde = bloque - self._cada() * 3600
        capturas = capturas_entre(self.grabaciones, desde, bloque)
        silencio = bool(capturas) and self.en_silencio(ahora)
        texto = self.texto(desde, bloque, capturas)
        if silencio:
            texto += f"\n(sin fotos de {self.cfg.silencio_desde}:00 a {self.cfg.silencio_hasta}:00; pídelas con /hoy)"
        try:
            self.cliente.enviar_texto(texto)
            if capturas and not silencio:
                fotos = leer_fotos(self.grabaciones, elegir_fotos(capturas))
                if fotos:
                    self.cliente.enviar_album(fotos)
        except TelegramError as e:
            log.warning("No se pudo enviar el resumen de detecciones: %s", e)
            return False   # no se marca: se reintenta en la siguiente vuelta
        self._guardar_ultimo(bloque)
        return True

    def vuelta(self) -> None:
        """Tarea del planificador: cada minuto revisa si toca."""
        if self.toca():
            self.enviar()
