"""Vigila la salud de las cámaras y emite eventos cuando se caen o vuelven."""
from __future__ import annotations

import logging
import socket
import threading
import time

log = logging.getLogger("panel.camaras")

MOTIVO = {
    "sin_red": "No responde en la red: revisa Wi-Fi, señal o corriente de la cámara.",
    "sin_video": "Responde en la red pero no envía video: el flujo RTSP se cortó (go2rtc reintenta solo).",
}


def duracion(seg: float) -> str:
    seg = int(seg)
    if seg < 60:
        return f"{seg} s"
    if seg < 3600:
        return f"{seg // 60} min"
    return f"{seg // 3600} h {seg % 3600 // 60} min"


def bytes_recibidos(info: dict) -> int:
    total = 0
    for p in info.get("producers") or []:
        total += p.get("bytes_recv") or sum(r.get("bytes", 0) for r in p.get("receivers") or [])
    return total


def red(ip: str, puerto: int, timeout: float = 3) -> int | None:
    """Latencia en ms de una conexión TCP, o None si no responde."""
    t0 = time.monotonic()
    try:
        socket.create_connection((ip, puerto), timeout=timeout).close()
    except OSError:
        return None
    return int((time.monotonic() - t0) * 1000)


class Vigilante:
    def __init__(self, obtener_camaras, go2rtc, caida_tras: float = 45, cada: float = 10,
                 al_evento=None, probar_red=red, reloj=time.time):
        self._obtener_camaras = obtener_camaras
        self._go2rtc = go2rtc
        self._caida_tras = caida_tras
        self._cada = cada
        self._al_evento = al_evento
        self._probar_red = probar_red
        self._reloj = reloj
        self._candado = threading.Lock()
        self._salud: dict = {}
        self._bytes: dict = {}
        self._go = {"ok": True, "inicio_fallo": None, "avisado": False}
        self._ultima = reloj()

    # --- eventos ---
    def _emitir(self, tipo, nivel, titulo, detalle, sujeto) -> None:
        ts = int(self._reloj())
        ev = {"ts": ts, "fuente": "camaras", "tipo": tipo, "nivel": nivel, "titulo": titulo,
              "detalle": detalle, "clave": f"vig:{tipo}:{sujeto}:{ts}"}
        if not self._al_evento:
            return
        try:
            self._al_evento(ev)
        except Exception:
            log.exception("vigilante: fallo al entregar el evento %s", tipo)

    # --- revisión ---
    def _revisar_go2rtc(self, streams):
        if streams is not None:
            return streams
        ahora = self._reloj()
        if self._go["ok"]:
            self._go.update(ok=False, inicio_fallo=ahora)
        if not self._go["avisado"] and ahora - self._go["inicio_fallo"] >= self._caida_tras:
            self._go["avisado"] = True
            self._emitir("go2rtc_sin_respuesta", "alto", "go2rtc sin respuesta",
                         "El servidor de video no responde.", "go2rtc")
        return None

    def revisar(self) -> None:
        # Lo lento (go2rtc y la prueba TCP de cada cámara) va fuera del candado para no frenar salud()
        try:
            streams = self._go2rtc.streams()
        except Exception:
            streams = None
        camaras = self._obtener_camaras() if streams is not None else []
        latencias = {c["id"]: self._probar_red(c["ip"], c["puerto_rtsp"]) for c in camaras}
        with self._candado:
            self._revisar(streams, camaras, latencias)

    def _revisar(self, streams, camaras, latencias) -> None:
        streams = self._revisar_go2rtc(streams)
        if streams is None:
            return
        if not self._go["ok"]:
            if self._go["avisado"]:
                self._emitir("go2rtc_volvio", "info", "go2rtc volvió",
                             "El servidor de video responde de nuevo.", "go2rtc")
            self._go.update(ok=True, inicio_fallo=None, avisado=False)

        for cid in set(self._salud) - {c["id"] for c in camaras}:
            del self._salud[cid]
            self._bytes.pop(cid, None)

        for c in camaras:
            cid = c["id"]
            lat = latencias.get(cid)
            b = bytes_recibidos(streams.get(cid) or {})
            hay_video = b > self._bytes.get(cid, -1)
            self._bytes[cid] = b
            nuevo = "ok" if hay_video else ("sin_red" if lat is None else "sin_video")
            ahora = self._reloj()

            s = self._salud.setdefault(cid, {"estado": "ok", "desde": ahora, "avisado": False,
                                             "cortes": [], "inicio_fallo": None})
            s.update(nombre=c["nombre"], ip=c["ip"], latencia_ms=lat)
            if nuevo != s["estado"]:
                s.update(estado=nuevo, desde=ahora)
            if nuevo == "ok":
                if s["avisado"]:
                    self._emitir("camara_volvio", "info", f'{c["nombre"]} volvió',
                                 "tras " + duracion(ahora - s["inicio_fallo"]), cid)
                s.update(avisado=False, inicio_fallo=None)
            else:
                if s["inicio_fallo"] is None:
                    s["inicio_fallo"] = ahora
                if not s["avisado"] and ahora - s["inicio_fallo"] >= self._caida_tras:
                    s["avisado"] = True
                    s["cortes"].append(ahora)
                    self._emitir("camara_caida", "alto", f'{c["nombre"]} sin video',
                                 f'IP {c["ip"]}. ' + MOTIVO[nuevo], cid)

    def vuelta(self) -> None:
        ahora = self._reloj()
        salto = ahora - self._ultima
        self._ultima = ahora
        if salto > self._cada * 3 + 30:
            self._emitir("servidor_suspendido", "medio", "Servidor suspendido",
                         f"Unos {duracion(salto)} sin vigilar las cámaras (¿el equipo se durmió?)",
                         "servidor")
        self.revisar()

    # --- salud ---
    def _cortes_24h(self, s) -> int:
        limite = self._reloj() - 86400
        s["cortes"] = [t for t in s["cortes"] if t > limite]
        return len(s["cortes"])

    def salud(self) -> dict:
        with self._candado:
            return {"go2rtc": self._go["ok"], "camaras": {
                cid: {"nombre": s["nombre"], "ip": s["ip"], "estado": s["estado"], "desde": s["desde"],
                      "latencia_ms": s["latencia_ms"], "cortes_24h": self._cortes_24h(s)}
                for cid, s in self._salud.items()}}
