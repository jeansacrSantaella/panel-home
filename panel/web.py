"""Servidor HTTP del panel: página única, API JSON y fotos de movimiento."""
from __future__ import annotations

import json
import logging
import mimetypes
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from panel import fuentes
from panel.config import ROOT

STATIC = ROOT / "static"
CLAVES_RED = ("uptime", "ribbon_start", "ribbon", "series", "hours", "public_ip", "checks", "speed", "contracted")
log = logging.getLogger("panel.web")


def _entero(valor, defecto=None):
    try:
        return int(valor) if valor not in (None, "") else defecto
    except ValueError:
        raise ValueError("parámetro numérico inválido")


def estado_panel(cfg, db, recolector, ahora=None) -> dict:
    """Une lo último que leyó el recolector con el consumo y los conteos guardados."""
    ahora = int(time.time()) if ahora is None else int(ahora)
    u = recolector.ultimo
    nw = u.get("netwatch")
    consumo = db.consumo(24, ahora)
    equipos = []
    for d in (nw or {}).get("devices", []):
        mac, ip = (d.get("mac") or "").lower(), d.get("ip") or ""
        equipos.append({
            "mac": mac, "ip": ip, "vendor": d.get("vendor") or "",
            "nombre": d.get("alias") or d.get("hostname") or d.get("vendor") or ip,
            "online": bool(d.get("online")), "q": d.get("q"), "drops": d.get("drops", 0),
            "consumo": consumo.get(mac) or consumo.get(ip),
        })
    salud = u.get("salud") or {}
    estados = salud.get("camaras") or {}
    camaras = []
    for c in u.get("camaras") or []:
        s = estados.get(c.get("id"), {})
        camaras.append({"id": c.get("id"), "nombre": c.get("nombre") or c.get("id"), "ip": c.get("ip"),
                        "estado": s.get("estado"), "latencia_ms": s.get("latencia_ms"),
                        "cortes_24h": s.get("cortes_24h"), "desde": s.get("desde")})
    movs = {}
    for ev in db.eventos(desde=ahora - 86400, tipos=["movimiento"], limite=200):
        cid = ev["ref"].split("/")[-1].split("_")[0] if ev["ref"] else ""
        movs.setdefault(cid, ev)  # vienen del más nuevo al más viejo
    return {
        "ahora": ahora, "actualizado": u.get("ts", 0), "go2rtc_url": cfg.go2rtc_url,
        "camaras_url": cfg.camaras_url, "netwatch_url": cfg.netwatch_url,
        "red": {k: nw.get(k) for k in CLAVES_RED} if nw else None,
        "equipos": equipos, "consumo_activo": bool(cfg.consumo_cmd),
        "camaras": camaras, "go2rtc_ok": salud.get("go2rtc") if salud else None,
        "ultimo_movimiento": movs, "espacio": u.get("espacio"), "conteo_24h": db.conteo_por_tipo(ahora - 86400),
    }


def capturas(cfg, recolector, fecha: str) -> dict:
    """Galería de un día: capturas del detector con el nombre de su cámara."""
    nombres = {c.get("id"): c.get("nombre") for c in (recolector.ultimo.get("camaras") or [])}
    lista = fuentes.capturas_del_dia(cfg, fecha)  # ValueError si la fecha es inválida
    for c in lista or []:
        c["nombre_camara"] = nombres.get(c["camara"]) or c["camara"]
    return {"fecha": fecha, "dias": fuentes.dias_con_capturas(cfg), "capturas": lista or [],
            "error": None if lista is not None else
            "No pude leer las capturas de gestorCamaras: ¿ya está desplegada la versión con /api/fotos?"}


def crear_servidor(cfg, db, recolector) -> ThreadingHTTPServer:
    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.debug(fmt, *args)

        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str, cache: str = "no-store"):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, datos, codigo: int = 200):
            self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _archivo(self, ruta: Path, cache: str = "no-cache"):
            tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo.endswith("javascript"):
                tipo += "; charset=utf-8"
            self._enviar(200, ruta.read_bytes(), tipo, cache)

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    return self._archivo(STATIC / "index.html")
                if url.path.startswith("/static/"):
                    ruta = (STATIC / url.path[len("/static/"):]).resolve()
                    if STATIC.resolve() in ruta.parents and ruta.is_file():
                        return self._archivo(ruta)
                    return self._json({"error": "no existe"}, 404)
                if url.path == "/api/panel":
                    return self._json(estado_panel(cfg, db, recolector))
                if url.path == "/api/eventos":
                    tipos = [t for t in q.get("tipos", "").split(",") if t]
                    return self._json({"eventos": db.eventos(_entero(q.get("desde")), _entero(q.get("hasta")),
                                                             tipos, _entero(q.get("limite"), 200))})
                if url.path == "/api/capturas":
                    return self._json(capturas(cfg, recolector, q.get("fecha") or time.strftime("%Y-%m-%d")))
                if url.path == "/api/foto":
                    # local o pedida a gestorCamaras según FOTOS_REMOTAS
                    foto = fuentes.leer_foto(cfg, q.get("ref", ""))
                    if foto:
                        return self._enviar(200, foto, "image/jpeg", "max-age=86400")
                    return self._json({"error": "foto no encontrada"}, 404)
                return self._json({"error": "no existe"}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)

    return ThreadingHTTPServer((cfg.host, cfg.port), Manejador)
