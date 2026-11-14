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

import hmac
import platform
import re
import sqlite3

from panel import VERSION, fuentes
from panel.camaras.go2rtc import Go2rtc, Go2rtcError
from panel.camaras.grabaciones import Grabaciones, GrabacionError
from panel.camaras.registro import CamaraError
from panel.camaras.servicio import exigir_admin
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
        "camaras_internas": cfg.camaras_internas,
        # Modo de transición con GO2RTC_URL: el video pasa por el puente del panel (mismo origen, audio controlable)
        "camaras_puente": bool(not cfg.camaras_internas and cfg.go2rtc_url),
        "camaras_url": cfg.camaras_url, "netwatch_url": cfg.netwatch_url, "red_interna": cfg.red_interna,
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
            (servicio("Sonda de red", "POST /api/interno/red", u.get("netwatch") is not None, "red, caídas y equipos")
             if cfg.red_interna else
             servicio("NetWatch", cfg.netwatch_url, u.get("netwatch") is not None, "red, caídas y equipos")),
            (servicio("Cámaras (internas)", "panel.db", u.get("salud") is not None, "cámaras, capturas y clips")
             if cfg.camaras_internas else
             servicio("gestorCamaras", cfg.camaras_url, u.get("salud") is not None, "cámaras, capturas y clips")),
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
MAX_LECTURAS = 2 * 1024 * 1024  # lote de la sonda de red
MAX_CUERPO_GRAB = 256 * 1024    # selección de grabaciones para borrar o exportar
TROZO = 64 * 1024
PUBLICAS = ("/login", "/login.html")  # además de /static/: todo lo demás pide sesión


def _rango(cabecera: str, total: int):
    """Interpreta "bytes=a-b" -> (inicio, fin) incluyente; None si no es válido o no cabe."""
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", (cabecera or "").strip())
    if not m or (not m.group(1) and not m.group(2)):
        return None
    if not m.group(1):  # últimos n bytes
        n = int(m.group(2))
        if n == 0:
            return None
        return max(0, total - n), total - 1
    ini = int(m.group(1))
    fin = min(int(m.group(2)), total - 1) if m.group(2) else total - 1
    if ini >= total or fin < ini:
        return None
    return ini, fin


def crear_servidor(cfg, db, recolector, auth, luces=None, rutinas=None, red=None, clima=None,
                   habitaciones=None, camaras=None) -> ThreadingHTTPServer:
    from panel.auth import COOKIE, DURACION_SESION, Bloqueado

    grabaciones = camaras.grabaciones if camaras is not None else Grabaciones(cfg.camaras_data)
    # Sin cámaras internas pero con GO2RTC_URL: puente de video y scripts de go2rtc por el panel (ver docs/CAMARAS.md)
    go2rtc_externo = Go2rtc(cfg.go2rtc_url) if camaras is None and cfg.go2rtc_url else None
    fuentes_externas = {"ts": 0.0, "ids": set()}

    def fuente_externa_valida(src: str) -> bool:
        # Solo fuentes que go2rtc ya conoce (nada arbitrario); la lista se refresca cada 60 s
        ahora = time.time()
        if ahora - fuentes_externas["ts"] > 60 or src not in fuentes_externas["ids"]:
            try:
                fuentes_externas["ids"] = set(go2rtc_externo.streams() or {})
                fuentes_externas["ts"] = ahora
            except Go2rtcError:
                return False
        return src in fuentes_externas["ids"]

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
                if url.path == "/salud":  # healthcheck de Docker: sin sesión y sin datos de la casa
                    return self._json({"ok": True})
                if url.path in PUBLICAS:
                    return self._archivo(STATIC / "login.html", "no-store")
                if url.path == "/api/interno/camaras":
                    return self._camaras_interno()
                sesion = auth.sesion(self._token())
                if sesion is None:
                    if url.path.startswith("/api/"):
                        return self._json({"error": "sin sesión"}, 401)
                    return self._redirigir("/login")
                if url.path == "/api/camaras/video":  # WebSocket: se atiende antes de cualquier otra respuesta
                    return self._camaras_video(q)
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
                    lista = luces.lista()
                    if habitaciones is not None:
                        lista = habitaciones.con_habitacion(lista)
                    return self._json({"configurado": True, "motivo": None, "luces": lista})
                if url.path == "/api/luces/habitaciones":
                    if habitaciones is None or luces is None or not luces.configurado:
                        return self._json({"habitaciones": [], "nombres": []})
                    return self._json({"habitaciones": habitaciones.resumen(luces.lista()),
                                       "nombres": habitaciones.nombres()})
                if url.path == "/api/clima":
                    if clima is None:
                        return self._json({"configurado": False})
                    if q.get("lat") and q.get("lon"):  # ubicación del dispositivo (la manda el navegador)
                        try:
                            lat, lon = float(q["lat"]), float(q["lon"])
                        except ValueError:
                            raise ValueError("coordenadas inválidas")
                        return self._json(clima.datos_para(lat, lon))
                    return self._json(clima.datos())
                if url.path == "/api/rutinas":
                    return self._json({"rutinas": rutinas.lista() if rutinas is not None else []})
                if url.path == "/api/eventos":
                    tipos = [t for t in q.get("tipos", "").split(",") if t]
                    return self._json({"eventos": db.eventos(_entero(q.get("desde")), _entero(q.get("hasta")),
                                                             tipos, _entero(q.get("limite"), 200))})
                if url.path.startswith("/api/red/"):
                    return self._red_get(url.path[len("/api/red/"):], q)
                if url.path == "/api/camaras" or url.path.startswith("/api/camaras/"):
                    return self._camaras_get(url.path[len("/api/camaras"):])
                if url.path == "/api/grabaciones" or url.path.startswith("/api/grabaciones/"):
                    return self._grabaciones_get(url.path[len("/api/grabaciones"):], q)
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
            if cual == "habitacion" and habitaciones is not None:  # una habitación completa
                nombre = datos.get("habitacion")
                cambios = {k: datos[k] for k in ("encendida", "brillo", "temperatura", "color") if k in datos}
                if not isinstance(nombre, str) or not cambios:
                    return self._json({"error": "falta 'habitacion' o qué cambiar"}, 400)
                try:
                    return self._json(habitaciones.aplicar(luces, nombre, cambios))
                except KeyError:
                    return self._json({"error": "Esa habitación no tiene focos"}, 404)
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
            m = re.fullmatch(r"([A-Za-z0-9_-]{1,64})/habitacion", cual)
            if m and habitaciones is not None:  # asignar la habitación de un foco
                if m.group(1) not in {x["id"] for x in luces.lista()}:
                    return self._json({"error": "No conozco ese foco"}, 404)
                valor = datos.get("habitacion")
                if valor is not None and not isinstance(valor, str):
                    return self._json({"error": "'habitacion' debe ser texto"}, 400)
                try:
                    return self._json({"id": m.group(1), "habitacion": habitaciones.asignar(m.group(1), valor)})
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
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

        # --- red interna (docs/RED.md) ---
        def _sin_red(self):
            return self._json({"error": "La red interna no está activa (RED_INTERNA=1)"}, 409)

        def _red_get(self, que: str, q: dict):
            if red is None:
                return self._sin_red()
            if que == "eventos":
                return self._json(red.eventos(q))  # ValueError -> 400 en do_GET
            if que == "export.csv":
                nombre = time.strftime("red-%Y%m%d-%H%M.csv")
                return self._enviar(200, red.csv().encode("utf-8"), "text/csv; charset=utf-8",
                                    extra=[("Content-Disposition", f'attachment; filename="{nombre}"')])
            if que == "sonda":
                return self._json({"sonda": red.sonda()})
            if que == "resumen":  # todo lo de la pestaña Red en una sola petición
                return self._json({"resumen": red.resumen(), "sonda": red.sonda(),
                                   "vivo": red.resumen_vivo() is not None})
            return self._json({"error": "no existe"}, 404)

        def _red_post(self, que: str, datos: dict):
            if red is None:
                return self._sin_red()
            try:
                if que == "escanear":
                    return self._json(red.escanear(datos.get("host"), datos.get("ports")))
                if que == "alias":
                    red.alias(datos)
                    return self._json({"ok": True})
                if que == "network":
                    red.network(datos)
                    return self._json({"ok": True})
            except (ValueError, KeyError, TypeError) as e:
                return self._json({"error": str(e) or "petición inválida"}, 400)
            return self._json({"error": "no existe"}, 404)

        def _red_ingesta(self):
            """Lecturas de la sonda: token propio (no sesión) y lotes de hasta 2 MB."""
            if red is None or not cfg.red_token:
                return self._json({"error": "no existe"}, 404)
            dado = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(dado.encode(), cfg.red_token.encode()):
                log.warning("sonda de red con token incorrecto desde %s", self._ip())
                return self._json({"error": "token incorrecto"}, 401)
            try:
                largo = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                largo = -1
            if largo <= 0 or largo > MAX_LECTURAS:
                return self._json({"error": "cuerpo inválido"}, 413)
            try:
                n = red.recibir(json.loads(self.rfile.read(largo)))
            except ValueError as e:
                return self._json({"error": str(e) or "JSON inválido"}, 400)
            return self._json({"ok": True, "recibidas": n})

        # --- cámaras internas (docs/CAMARAS.md) ---
        def _sin_camaras(self):
            return self._json({"error": "Cámaras internas no activas (CAMARAS_INTERNAS=1)"}, 409)

        def _error_cam(self, e):
            return self._json({"error": str(e)}, getattr(e, "codigo", 422))

        def _admin(self):
            exigir_admin(cfg.admin_pin, self.headers.get("X-Admin", ""))

        def _camaras_interno(self):
            """Lista completa (sin claves) para el detector: token propio, no sesión."""
            if camaras is None or not cfg.interno_token:
                return self._json({"error": "no existe"}, 404)
            dado = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(dado.encode(), cfg.interno_token.encode()):
                log.warning("detector con token incorrecto desde %s", self._ip())
                return self._json({"error": "token incorrecto"}, 401)
            return self._json([{k: v for k, v in c.items() if k != "clave"} for c in camaras.registro.lista()])

        def _camaras_video(self, q: dict):
            if camaras is None and go2rtc_externo is None:
                return self._sin_camaras()
            origen = self.headers.get("Origin")
            if origen and urlparse(origen).netloc != self.headers.get("Host", ""):
                return self._json({"error": "origen no permitido"}, 403)
            if "websocket" not in (self.headers.get("Upgrade") or "").lower():
                return self._json({"error": "se espera WebSocket"}, 400)
            src = q.get("src", "")
            from panel.camaras.video import puente_websocket
            if camaras is None:  # modo de transición: go2rtc externo, sin sesiones de video
                if not fuente_externa_valida(src):
                    return self._json({"error": "cámara desconocida"}, 404)
                self.close_connection = True
                return puente_websocket(self, cfg.go2rtc_url, src)
            if not camaras.sesiones.valida(q.get("sesion", "")):
                return self._json({"error": "sesión de video no válida"}, 403)
            try:
                camaras.registro.una(src)  # solo cámaras registradas (nada de fuentes arbitrarias)
            except CamaraError as e:
                return self._error_cam(e)
            self.close_connection = True
            puente_websocket(self, cfg.go2rtc_interno_url, src)

        def _camaras_get(self, resto: str):
            if camaras is None:
                m = re.fullmatch(r"/go2rtc/([\w.-]+)", resto)
                if go2rtc_externo is None or not m:
                    return self._sin_camaras()
                try:
                    cuerpo = go2rtc_externo.script(m.group(1))
                except ValueError:
                    return self._json({"error": "no existe"}, 404)
                except Go2rtcError as e:
                    return self._json({"error": str(e)}, 502)
                return self._enviar(200, cuerpo, "text/javascript; charset=utf-8", "private, max-age=3600")
            if resto in ("", "/"):
                return self._json(camaras.lista())
            if resto == "/salud":
                return self._json(camaras.salud())
            if resto == "/config":
                return self._json({"protegido": bool(cfg.admin_pin), "maximo_sesiones": cfg.max_sesiones})
            m = re.fullmatch(r"/go2rtc/([\w.-]+)", resto)
            if m:
                try:
                    cuerpo = camaras.go2rtc.script(m.group(1))
                except ValueError:
                    return self._json({"error": "no existe"}, 404)
                except Go2rtcError as e:
                    return self._json({"error": str(e)}, 502)
                return self._enviar(200, cuerpo, "text/javascript; charset=utf-8", "private, max-age=3600")
            m = re.fullmatch(r"/([\w-]{1,64})/foto", resto)
            if m:
                try:
                    camaras.registro.una(m.group(1))
                except CamaraError as e:
                    return self._error_cam(e)
                foto = camaras.go2rtc.foto(m.group(1))
                if not foto:
                    return self._json({"error": "go2rtc no entregó la imagen"}, 502)
                return self._enviar(200, foto, "image/jpeg")
            return self._json({"error": "no existe"}, 404)

        def _camaras_post(self, resto: str, datos: dict):
            if camaras is None:
                return self._sin_camaras()
            try:
                if resto in ("", "/"):
                    self._admin()
                    return self._json(camaras.agregar(datos))
                if resto == "/sesion":
                    from panel.camaras.video import SinLugar
                    try:
                        return self._json(camaras.sesiones.abrir())
                    except SinLugar as e:
                        return self._json({"error": "No hay lugar para otra sesión de video",
                                           "sesiones": getattr(e, "info", [])}, 409)
                m = re.fullmatch(r"/sesion/([\w-]{1,64})/(latido|salir)", resto)
                if m:
                    if m.group(2) == "latido":
                        return self._json({"estado": camaras.sesiones.latido(m.group(1))})
                    camaras.sesiones.salir(m.group(1))
                    return self._json({"ok": True})
                m = re.fullmatch(r"/([\w-]{1,64})/(mover|parar|borrar)", resto)
                if m:
                    cid, accion = m.groups()
                    if accion == "borrar":
                        self._admin()
                        camaras.quitar(cid)
                        return self._json({"ok": True})
                    camaras.registro.una(cid)
                    if accion == "parar":
                        camaras.ptz.parar(cid)
                        return self._json({"ok": True})
                    if not camaras.sesiones.valida(self.headers.get("X-Sesion", "")):
                        return self._json({"error": "sesión de video no válida"}, 403)
                    x, y = datos.get("x"), datos.get("y")
                    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (x, y)):
                        return self._json({"error": "x e y deben ser números entre -1 y 1"}, 400)
                    camaras.ptz.mover(cid, max(-1.0, min(1.0, float(x))), max(-1.0, min(1.0, float(y))))
                    return self._json({"ok": True})
            except (CamaraError, GrabacionError) as e:
                return self._error_cam(e)
            except Exception as e:
                if type(e).__name__ == "OnvifError":
                    return self._json({"error": str(e)}, 502)
                raise
            return self._json({"error": "no existe"}, 404)

        def _camaras_delete(self, resto: str):
            if camaras is None:
                return self._sin_camaras()
            m = re.fullmatch(r"/([\w-]{1,64})", resto)
            if not m:
                return self._json({"error": "no existe"}, 404)
            try:
                self._admin()
                camaras.quitar(m.group(1))
            except CamaraError as e:
                return self._error_cam(e)
            return self._json({"ok": True})

        # --- grabaciones (fotos y clips del detector en cfg.camaras_data) ---
        def _sin_grabaciones(self):
            return self._json({"error": "Las grabaciones están en gestorCamaras (FOTOS_REMOTAS=1): "
                                        "no se pueden gestionar desde aquí"}, 409)

        def _servir_grabacion(self, ruta: Path, tipo: str):
            """Envía un archivo en trozos; con Range (206) para que el <video> pueda adelantar."""
            if not ruta.is_file():
                return self._json({"error": "no existe"}, 404)
            total = ruta.stat().st_size
            ini, fin, codigo, extra = 0, total - 1, 200, []
            cab = self.headers.get("Range")
            if cab:
                r = _rango(cab, total)
                if r is None:
                    return self._json({"error": "rango no satisfacible"}, 416,
                                      extra=[("Content-Range", f"bytes */{total}")])
                ini, fin = r
                codigo = 206
                extra = [("Content-Range", f"bytes {ini}-{fin}/{total}")]
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(max(0, fin - ini + 1)))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "private, max-age=3600")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            try:
                with open(ruta, "rb") as f:
                    f.seek(ini)
                    resta = fin - ini + 1
                    while resta > 0:
                        trozo = f.read(min(TROZO, resta))
                        if not trozo:
                            break
                        self.wfile.write(trozo)
                        resta -= len(trozo)
            except OSError:
                self.close_connection = True  # el navegador cortó la descarga

        def _enviar_zip(self, pares):
            if not pares:
                raise GrabacionError("Nada que exportar", 404)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{grabaciones.nombre_zip()}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()  # sin Content-Length: termina al cerrar la conexión
            self.close_connection = True
            try:
                grabaciones.escribir_zip(pares, self.wfile)
            except OSError:
                pass

        def _grabaciones_get(self, resto: str, q: dict):
            if cfg.fotos_remotas:
                return self._sin_grabaciones()
            try:
                if resto == "/dias":
                    return self._json({"dias": grabaciones.dias()})
                if resto in ("", "/"):
                    fecha = q.get("fecha") or time.strftime("%Y-%m-%d")
                    return self._json({"fecha": fecha, "fotos": grabaciones.fotos(fecha),
                                       "clips": grabaciones.clips(fecha)})
                m = re.fullmatch(r"/exportar/([\d-]{10})", resto)
                if m:
                    return self._enviar_zip(grabaciones.pares_dia(m.group(1)))
                m = re.fullmatch(r"/(fotos|clips)/([\d-]{10})/([^/]+)", resto)
                if m:
                    ruta = grabaciones.ruta(*m.groups())
                    return self._servir_grabacion(ruta, grabaciones.tipo_mime(m.group(1)))
            except GrabacionError as e:
                return self._error_cam(e)
            return self._json({"error": "no existe"}, 404)

        def _grabaciones_post(self, resto: str, datos: dict):
            if cfg.fotos_remotas:
                return self._sin_grabaciones()
            lista = lambda k: datos.get(k) if isinstance(datos.get(k), list) and all(  # noqa: E731
                isinstance(x, str) for x in datos.get(k)) else None
            try:
                if resto in ("/borrar", "/exportar"):
                    fotos, clips = lista("fotos") or [], lista("clips") or []
                    if (datos.get("fotos") is not None and lista("fotos") is None) or \
                       (datos.get("clips") is not None and lista("clips") is None):
                        return self._json({"error": "fotos y clips deben ser listas de texto"}, 400)
                    if resto == "/exportar":
                        return self._enviar_zip(grabaciones.resolver(fotos, clips))
                    self._admin()
                    return self._json({"borrados": grabaciones.borrar(fotos, clips)})
                if resto == "/borrar-dia":
                    self._admin()
                    fecha = datos.get("fecha")
                    if not isinstance(fecha, str):
                        return self._json({"error": "falta 'fecha'"}, 400)
                    grabaciones.fotos(fecha)  # valida el formato (GrabacionError 422)
                    return self._json({"borrados": grabaciones.borrar_dia(fecha)})
            except (CamaraError, GrabacionError) as e:
                return self._error_cam(e)
            return self._json({"error": "no existe"}, 404)

        def do_DELETE(self):
            url = urlparse(self.path)
            origen = self.headers.get("Origin")
            if origen and urlparse(origen).netloc != self.headers.get("Host", ""):
                return self._json({"error": "origen no permitido"}, 403)
            if auth.sesion(self._token()) is None:
                return self._json({"error": "sin sesión"}, 401)
            if url.path.startswith("/api/camaras/"):
                return self._camaras_delete(url.path[len("/api/camaras"):])
            return self._json({"error": "no existe"}, 404)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path == "/api/interno/red":
                return self._red_ingesta()
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
            if largo < 0 or largo > (MAX_CUERPO_GRAB if url.path.startswith("/api/grabaciones/") else MAX_CUERPO):
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
            if url.path.startswith("/api/red/"):
                return self._red_post(url.path[len("/api/red/"):], datos)
            if url.path == "/api/camaras" or url.path.startswith("/api/camaras/"):
                return self._camaras_post(url.path[len("/api/camaras"):], datos)
            if url.path.startswith("/api/grabaciones/"):
                return self._grabaciones_post(url.path[len("/api/grabaciones"):], datos)
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
