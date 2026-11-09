"""Servidor HTTP del panel: página única, API JSON y fotos de movimiento."""
from __future__ import annotations

import json
import logging
import mimetypes
import time
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import platform
import re
import sqlite3

from panel import VERSION, fuentes
from panel.config import ROOT

STATIC = ROOT / "static"
CLAVES_RED = ("uptime", "ribbon_start", "ribbon", "series", "hours", "public_ip", "checks", "speed", "contracted")
log = logging.getLogger("panel.web")


def _entero(valor, defecto=None):
    try:
        return int(valor) if valor not in (None, "") else defecto
    except ValueError:
        raise ValueError("parámetro numérico inválido")


def estado_panel(cfg, db, recolector, ahora=None, luces=None) -> dict:
    """Une lo último que leyó el recolector con el consumo y los conteos guardados."""
    ahora = int(time.time()) if ahora is None else int(ahora)
    u = recolector.ultimo
    nw = u.get("netwatch")
    consumo = db.consumo(24, ahora)
    equipos = []
    focos = luces.nombre_por_ip() if luces is not None and luces.configurado else {}
    for d in (nw or {}).get("devices", []):
        mac, ip = (d.get("mac") or "").lower(), d.get("ip") or ""
        equipos.append({
            "mac": mac, "ip": ip, "vendor": d.get("vendor") or "",
            "nombre": d.get("alias") or focos.get(ip) or d.get("hostname") or d.get("vendor") or ip,
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
        "ultimo_movimiento": movs, "espacio": u.get("espacio"),
        "sistema": u.get("sistema"), "calor": db.calor_movimiento(28, ahora), "conteo_24h": db.conteo_por_tipo(ahora - 86400),
    }


INICIO = int(time.time())


def acerca(cfg, db, recolector, ahora=None) -> dict:
    """Datos de la ventana "Acerca de": versión, entorno y estado de cada servicio conectado."""
    ahora = int(time.time()) if ahora is None else int(ahora)
    u = recolector.ultimo
    salud = u.get("salud") or {}
    sistema = u.get("sistema") or {}
    try:
        db_bytes = sum(f.stat().st_size for f in cfg.db_path.parent.glob(cfg.db_path.name + "*"))
    except OSError:
        db_bytes = None
    total = db._q("SELECT COUNT(*) AS n, MIN(ts) AS desde FROM eventos")[0]
    servicio = lambda nombre, url, ok, detalle="": {"nombre": nombre, "url": url, "ok": ok, "detalle": detalle}  # noqa: E731
    return {
        "version": VERSION, "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "sistema": f"{platform.system()} {platform.machine()}", "inicio": INICIO, "ahora": ahora,
        "db_bytes": db_bytes, "eventos": total["n"], "eventos_desde": total["desde"],
        "servicios": [
            servicio("NetWatch", cfg.netwatch_url, u.get("netwatch") is not None, "red, caídas y equipos"),
            servicio("gestorCamaras", cfg.camaras_url, u.get("salud") is not None, "cámaras, capturas y clips"),
            servicio("go2rtc", cfg.go2rtc_url or "(host):1984", salud.get("go2rtc") if salud else None, "video en vivo"),
            servicio("Docker", cfg.docker_sock or "—", sistema.get("contenedores") is not None, "estado de contenedores"),
            servicio("Telegram", "api.telegram.org", True if cfg.telegram_activo else None, "avisos"),
            servicio("ntfy", cfg.ntfy_url or "—", True if cfg.ntfy_url else None, "avisos push"),
        ],
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


MAX_CUERPO = 4096
PUBLICAS = ("/login", "/login.html")  # además de /static/: todo lo demás pide sesión


def crear_servidor(cfg, db, recolector, auth, luces=None, rutinas=None) -> ThreadingHTTPServer:
    from panel.auth import COOKIE, DURACION_SESION, Bloqueado

    class Manejador(BaseHTTPRequestHandler):
        server_version = "PleyadesHome"  # no anunciar versión de Python
        sys_version = ""

        def log_message(self, fmt, *args):
            log.debug(fmt, *args)

        def _enviar(self, codigo: int, cuerpo: bytes, tipo: str, cache: str = "no-store", extra=()):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", cache)
            # cabeceras de seguridad: nadie puede incrustar el panel ni adivinar tipos
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "same-origin")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(cuerpo)

        def _json(self, datos, codigo: int = 200, extra=()):
            self._enviar(codigo, json.dumps(datos, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                         extra=extra)

        def _archivo(self, ruta: Path, cache: str = "no-cache"):
            tipo = mimetypes.guess_type(ruta.name)[0] or "application/octet-stream"
            if tipo.startswith("text/") or tipo.endswith("javascript"):
                tipo += "; charset=utf-8"
            self._enviar(200, ruta.read_bytes(), tipo, cache)

        def _redirigir(self, destino: str):
            self.send_response(302)
            self.send_header("Location", destino)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        # --- sesión ---
        def _token(self) -> str:
            galleta = SimpleCookie()
            try:
                galleta.load(self.headers.get("Cookie", ""))
            except CookieError:
                return ""
            m = galleta.get(COOKIE)
            return m.value if m else ""

        def _cookie(self, token: str, edad: int) -> tuple:
            return ("Set-Cookie", f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={edad}")

        def _ip(self) -> str:
            return self.client_address[0]

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path.startswith("/static/"):
                    ruta = (STATIC / url.path[len("/static/"):]).resolve()
                    if STATIC.resolve() in ruta.parents and ruta.is_file():
                        return self._archivo(ruta)
                    return self._json({"error": "no existe"}, 404)
                if url.path in PUBLICAS:
                    return self._archivo(STATIC / "login.html", "no-store")
                sesion = auth.sesion(self._token())
                if sesion is None:
                    if url.path.startswith("/api/"):
                        return self._json({"error": "sin sesión"}, 401)
                    return self._redirigir("/login")
                if url.path in ("/", "/index.html"):
                    return self._archivo(STATIC / "index.html", "no-store")
                if url.path == "/api/sesion":
                    return self._json(sesion)
                if url.path == "/api/acerca":
                    return self._json(acerca(cfg, db, recolector))
                if url.path == "/api/panel":
                    return self._json(estado_panel(cfg, db, recolector, luces=luces))
                if url.path == "/api/luces":
                    if luces is None or not luces.configurado:
                        motivo = luces.motivo if luces is not None else "Control de luces desactivado"
                        return self._json({"configurado": False, "motivo": motivo, "luces": []})
                    return self._json({"configurado": True, "motivo": None, "luces": luces.lista()})
                if url.path == "/api/rutinas":
                    return self._json({"rutinas": rutinas.lista() if rutinas is not None else []})
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
                        return self._enviar(200, foto, "image/jpeg", "private, max-age=86400")
                    return self._json({"error": "foto no encontrada"}, 404)
                return self._json({"error": "no existe"}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)

        def _rutinas_post(self, resto: str, datos: dict):
            """Crear o editar (/api/rutinas), y /<id>/ejecutar, /<id>/activa, /<id>/borrar."""
            if rutinas is None or luces is None or not luces.configurado:
                return self._json({"error": "Las luces no están configuradas"}, 409)
            try:
                if resto in ("", "/"):
                    return self._json(rutinas.guardar(datos))
                m = re.fullmatch(r"/(\d{1,9})/(ejecutar|activa|borrar)", resto)
                if not m:
                    return self._json({"error": "no existe"}, 404)
                ident, accion = int(m.group(1)), m.group(2)
                if accion == "ejecutar":
                    return self._json(rutinas.ejecutar(ident))
                if accion == "activa":
                    if not isinstance(datos.get("activa"), bool):
                        return self._json({"error": "falta 'activa'"}, 400)
                    return self._json(rutinas.activar(ident, datos["activa"]))
                rutinas.borrar(ident)
                return self._json({"ok": True})
            except KeyError:
                return self._json({"error": "No existe esa rutina"}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)

        def _luces_post(self, cual: str, datos: dict):
            """Enciende, apaga o ajusta un foco (o todos) por la red local."""
            if luces is None or not luces.configurado:
                return self._json({"error": "Las luces no están configuradas"}, 409)
            if cual == "todas":
                if not isinstance(datos.get("encendida"), bool):
                    return self._json({"error": "falta 'encendida'"}, 400)
                return self._json({"respondieron": luces.aplicar_todas(datos["encendida"])})
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cual):
                return self._json({"error": "foco inválido"}, 400)
            cambios = {k: datos[k] for k in ("encendida", "brillo", "temperatura", "color") if k in datos}
            if not cambios:
                return self._json({"error": "nada que cambiar"}, 400)
            try:
                return self._json(luces.aplicar(cual, cambios))
            except KeyError:
                return self._json({"error": "No conozco ese foco"}, 404)
            except ValueError as e:
                return self._json({"error": str(e)}, 400)
            except RuntimeError as e:
                return self._json({"error": str(e)}, 504)

        def do_POST(self):
            url = urlparse(self.path)
            # Solo JSON del mismo origen: junto con SameSite=Strict evita peticiones forjadas desde otras páginas
            origen = self.headers.get("Origin")
            if origen and urlparse(origen).netloc != self.headers.get("Host", ""):
                return self._json({"error": "origen no permitido"}, 403)
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._json({"error": "se espera JSON"}, 415)
            try:
                largo = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                largo = -1
            if largo < 0 or largo > MAX_CUERPO:
                return self._json({"error": "cuerpo inválido"}, 413)
            try:
                datos = json.loads(self.rfile.read(largo) or b"{}")
                if not isinstance(datos, dict):
                    raise ValueError
            except ValueError:
                return self._json({"error": "JSON inválido"}, 400)
            texto = lambda k: datos.get(k) if isinstance(datos.get(k), str) else ""  # noqa: E731

            if url.path == "/api/login":
                try:
                    r = auth.entrar(texto("usuario"), texto("contrasena"), self._ip())
                except Bloqueado as b:
                    return self._json({"error": "Demasiados intentos", "segundos": b.segundos}, 429,
                                      extra=[("Retry-After", str(b.segundos))])
                if r is None:
                    return self._json({"error": "Usuario o contraseña incorrectos"}, 401)
                return self._json({"usuario": r["usuario"], "debe_cambiar": r["debe_cambiar"]},
                                  extra=[self._cookie(r["token"], DURACION_SESION)])
            if url.path == "/api/logout":
                auth.salir(self._token())
                return self._json({"ok": True}, extra=[self._cookie("", 0)])
            sesion = auth.sesion(self._token())
            if sesion is None:
                return self._json({"error": "sin sesión"}, 401)
            if url.path == "/api/rutinas" or url.path.startswith("/api/rutinas/"):
                return self._rutinas_post(url.path[len("/api/rutinas"):], datos)
            if url.path.startswith("/api/luces/"):
                return self._luces_post(url.path[len("/api/luces/"):], datos)
            if url.path == "/api/contrasena":
                try:
                    auth.cambiar(sesion["usuario"], texto("actual"), texto("nueva"), self._token())
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
                return self._json({"ok": True})
            return self._json({"error": "no existe"}, 404)

    return ThreadingHTTPServer((cfg.host, cfg.port), Manejador)
