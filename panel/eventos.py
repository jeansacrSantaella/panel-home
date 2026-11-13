"""Convierte lo que reportan NetWatch y las cámaras en eventos de la línea de tiempo."""
from __future__ import annotations

import logging
import time

from panel import fuentes, sistema

log = logging.getLogger("panel.eventos")

# kind de NetWatch -> (tipo, nivel, titulo)
MAPA_RED = {
    "wan_down": ("internet_caido", "alto", "Internet caído"),
    "wan_up": ("internet_ok", "info", "Internet restablecido"),
    "lan_down": ("red_local_caida", "alto", "Red local caída"),
    "lan_up": ("red_local_ok", "info", "Red local restablecida"),
    "dns_down": ("dns_caido", "medio", "DNS sin respuesta"),
    "dns_up": ("dns_ok", "info", "DNS restablecido"),
    "new_device": ("equipo_nuevo", "medio", "Equipo nuevo en la red"),
    "ip_change": ("cambio_ip", "medio", "Cambió la IP pública"),
    "ip_first": ("ip_publica", "info", "IP pública detectada"),
    "device_online": ("equipo_conectado", "bajo", "Equipo conectado"),
    "device_offline": ("equipo_desconectado", "bajo", "Equipo desconectado"),
    "monitor_gap": ("pausa_monitor", "bajo", "El monitor de red estuvo detenido"),
}
# estado nuevo de una cámara -> (tipo, nivel, plantilla de título)
MAPA_CAMARA = {
    "sin_red": ("camara_sin_red", "alto", "{nombre}: sin red"),
    "sin_video": ("camara_sin_video", "medio", "{nombre}: sin video"),
    "ok": ("camara_ok", "info", "{nombre}: video de vuelta"),
}


class Recolector:
    def __init__(self, cfg, db, red=None):
        self.cfg = cfg
        self.db = db
        self.red = red  # panel.red.servicio.Red: la red la mide la sonda (RED_INTERNA=1); None = leer NetWatch
        self.ultimo = {"ts": 0, "netwatch": None, "camaras": None, "salud": None, "espacio": None, "sistema": None}
        self._espacio_ts = 0
        self._malos = {}  # lecturas seguidas con el contenedor caído

    def ciclo(self, ahora=None) -> int:
        ahora = int(time.time()) if ahora is None else int(ahora)
        # primer arranque: el historial entra ya marcado como avisado para no inundar de avisos
        silencio = self.db.get("iniciado") is None
        total = 0
        for paso in (self._red, self._camaras, self._movimiento, self._consumo, self._sistema, self._podar):
            try:
                total += paso(ahora, silencio)
            except Exception:
                log.exception("falló %s", paso.__name__)
        if silencio:
            self.db.set("iniciado", ahora)
        if ahora - self._espacio_ts >= 300:  # el disco cambia despacio: cada 5 min basta
            self._espacio_ts = ahora
            try:
                self.ultimo["espacio"] = fuentes.camaras_espacio(self.cfg)
            except Exception:
                log.exception("falló espacio")
        self.ultimo["ts"] = ahora
        return total

    def _guardar(self, ev: dict, silencio: bool) -> bool:
        ev.setdefault("ref", "")
        ev.setdefault("detalle", "")
        ev["avisado"] = 1 if silencio else 0
        return self.db.agregar_evento(ev)

    def _fuente(self, nombre: str, ok: bool, ahora: int, silencio: bool) -> int:
        estados = self.db.get("fuentes", {})
        previo = estados.get(nombre)
        estados[nombre] = ok
        self.db.set("fuentes", estados)
        if previo is None or previo == ok:
            return 0
        tipo, nivel, titulo = (("fuente_ok", "info", f"{nombre} responde de nuevo") if ok
                               else ("fuente_caida", "medio", f"{nombre} no responde"))
        return int(self._guardar({"ts": ahora, "fuente": "panel", "tipo": tipo, "nivel": nivel, "titulo": titulo,
                                  "clave": f"fuente:{nombre}:{ahora}"}, silencio))

    def _sistema(self, ahora: int, silencio: bool) -> int:
        """CPU, RAM y contenedores del servidor; avisa si un contenedor se detiene o vuelve."""
        s = sistema.leer_sistema(self.cfg.docker_sock)
        self.ultimo["sistema"] = s
        if s.get("contenedores") is None:
            return 0
        previos = self.db.get("contenedores", {})
        actuales = {}
        for c in s["contenedores"]:
            nombre = c["nombre"]
            ok = c["estado"] == "running" and c.get("salud") != "unhealthy"
            # una caída cuenta tras 2 lecturas seguidas (~30 s): un `docker compose up --build` no avisa
            self._malos[nombre] = 0 if ok else self._malos.get(nombre, 0) + 1
            if nombre not in previos:  # primera vez que lo vemos: es la línea base (un contenedor viejo ya detenido no avisa)
                actuales[nombre] = ok
            else:
                actuales[nombre] = ok or (previos[nombre] is not False and self._malos[nombre] < 2)
        n = 0
        for nombre, ok in actuales.items():
            if previos.get(nombre) is None or previos[nombre] == ok:
                continue
            det = next(c["detalle"] for c in s["contenedores"] if c["nombre"] == nombre)
            tipo, nivel, titulo = (("contenedor_ok", "info", f"Contenedor {nombre} funciona de nuevo") if ok
                                   else ("contenedor_caido", "alto", f"Contenedor {nombre} detenido o con fallas"))
            n += self._guardar({"ts": ahora, "fuente": "sistema", "tipo": tipo, "nivel": nivel, "titulo": titulo,
                                "detalle": det, "clave": f"ctr:{nombre}:{ahora}"}, silencio)
        self.db.set("contenedores", {**previos, **actuales})
        return n

    def _red(self, ahora: int, silencio: bool) -> int:
        if self.red is not None:
            r = self.red.resumen_vivo(ahora)  # None si la sonda dejó de mandar lecturas
            n = self._fuente("Sonda de red", r is not None, ahora, silencio)
        else:
            r = fuentes.netwatch_resumen(self.cfg)
            n = self._fuente("NetWatch", r is not None, ahora, silencio)
        self.ultimo["netwatch"] = r
        for e in (r or {}).get("events", []):
            kind, detalle = e.get("kind", ""), e.get("detail", "")
            tipo, nivel, titulo = MAPA_RED.get(kind, (f"red_{kind}", "bajo", kind))
            n += self._guardar({"ts": int(e["ts"]), "fuente": "red", "tipo": tipo, "nivel": nivel, "titulo": titulo,
                                "detalle": detalle, "clave": f"nw:{e['ts']}:{kind}:{detalle}"}, silencio)
        return n

    def _camaras(self, ahora: int, silencio: bool) -> int:
        self.ultimo["camaras"] = fuentes.camaras_lista(self.cfg)
        salud = fuentes.camaras_salud(self.cfg)
        self.ultimo["salud"] = salud
        n = self._fuente("Cámaras", salud is not None, ahora, silencio)
        if not salud:
            return n
        previos = self.db.get("camaras", {})
        nuevos = {"_go2rtc": bool(salud.get("go2rtc"))}
        for cid, s in (salud.get("camaras") or {}).items():
            estado = s.get("estado")
            nuevos[cid] = estado
            if cid in previos and previos[cid] != estado and estado in MAPA_CAMARA:
                tipo, nivel, plantilla = MAPA_CAMARA[estado]
                ts = int(s.get("desde") or ahora)
                n += self._guardar({"ts": ts, "fuente": "camaras", "tipo": tipo, "nivel": nivel,
                                    "titulo": plantilla.format(nombre=s.get("nombre") or cid),
                                    "detalle": f"IP {s.get('ip', '')}", "clave": f"cam:{cid}:{ts}:{estado}"}, silencio)
        if "_go2rtc" in previos and previos["_go2rtc"] != nuevos["_go2rtc"]:
            ok = nuevos["_go2rtc"]
            n += self._guardar({"ts": ahora, "fuente": "camaras", "tipo": "go2rtc_ok" if ok else "go2rtc_caido",
                                "nivel": "info" if ok else "alto",
                                "titulo": "go2rtc responde de nuevo" if ok else "go2rtc no responde",
                                "clave": f"go2rtc:{ahora}"}, silencio)
        self.db.set("camaras", nuevos)
        return n

    def _movimiento(self, ahora: int, silencio: bool) -> int:
        desde = self.db.get("ultima_foto", ahora - 86400)
        nombres = {c.get("id"): c.get("nombre") for c in (self.ultimo["camaras"] or [])}
        fotos = fuentes.fotos_movimiento(self.cfg, desde, ahora)
        n = 0
        for f in fotos:
            n += self._guardar({"ts": f["ts"], "fuente": "camaras", "tipo": "movimiento", "nivel": "medio",
                                "titulo": f"Movimiento en {nombres.get(f['camara']) or f['camara']}",
                                "detalle": ", ".join(f["clases"]), "ref": f["ref"],
                                "clave": f"mov:{f['ref']}"}, silencio)
        if fotos:
            self.db.set("ultima_foto", max(f["ts"] for f in fotos))
        return n

    def _consumo(self, ahora: int, silencio: bool) -> int:
        m = fuentes.leer_consumo(self.cfg)
        if m:
            self.db.guardar_consumo(ahora, m)
        return 0

    def _podar(self, ahora: int, silencio: bool) -> int:
        if ahora - self.db.get("poda", 0) >= 86400:
            self.db.podar(ahora=ahora)
            self.db.set("poda", ahora)
        return 0
