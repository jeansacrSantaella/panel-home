"""Fachada de las cámaras internas: arma registro, go2rtc, vigilancia, grabaciones, PTZ y sesiones de video."""
from __future__ import annotations

import dataclasses
import hmac

from panel import fuentes
from panel.camaras.go2rtc import Go2rtc, Sincronizador
from panel.camaras.grabaciones import Grabaciones
from panel.camaras.registro import CamaraError, Registro, fuente_rtsp, publica
from panel.camaras.vigilante import Vigilante
from panel.tareas import cada


def exigir_admin(admin_pin: str, pin: str) -> None:
    """CamaraError 401 si hay PIN configurado y no coincide."""
    if admin_pin and not hmac.compare_digest((pin or "").encode(), admin_pin.encode()):
        raise CamaraError("PIN de administrador incorrecto", 401)


def _entero(datos: dict, clave: str, defecto: int) -> int:
    v = datos.get(clave)
    if v in (None, ""):
        return defecto
    if isinstance(v, bool):
        raise CamaraError(f"{clave} debe ser un número")
    try:
        return int(v)
    except (TypeError, ValueError):
        raise CamaraError(f"{clave} debe ser un número")


def _texto(datos: dict, clave: str, defecto: str = "") -> str:
    v = datos.get(clave)
    if v is None:
        return defecto
    if not isinstance(v, str):
        raise CamaraError(f"{clave} debe ser texto")
    return v


class Camaras:
    def __init__(self, cfg, db, al_evento=None, ptz=None, sesiones=None, go2rtc=None):
        self.cfg = cfg
        self.registro = Registro(db, cfg.max_camaras, cfg.camaras_iniciales)
        self.go2rtc = go2rtc or Go2rtc(cfg.go2rtc_interno_url)
        self.sincronizador = Sincronizador(self.go2rtc, self.registro.lista, fuente_rtsp)
        self.vigilante = Vigilante(self.registro.lista, self.go2rtc, cfg.caida_tras, cfg.vigilar_cada, al_evento)
        self.grabaciones = Grabaciones(cfg.camaras_data)
        if ptz is None:
            from panel.camaras.onvif import ControlPTZ
            ptz = ControlPTZ(self.registro.una, timeout=cfg.onvif_timeout)
        if sesiones is None:
            from panel.camaras.video import Sesiones
            sesiones = Sesiones(cfg.max_sesiones, cfg.sesion_caduca)
        self.ptz = ptz
        self.sesiones = sesiones

    def tareas(self) -> list:
        return [cada("camaras-sincronizar", 10, self.sincronizador.vuelta, retraso=1),
                cada("camaras-vigilar", self.cfg.vigilar_cada, self.vigilante.vuelta, retraso=3)]

    def lista(self) -> list:
        return self.registro.publicas()

    def salud(self) -> dict:
        return self.vigilante.salud()

    def espacio(self):
        # siempre se mide la carpeta local: aquí las grabaciones las escribe el detector en cfg.camaras_data
        return fuentes.camaras_espacio(dataclasses.replace(self.cfg, fotos_remotas=False))

    def agregar(self, datos: dict) -> dict:
        res = self.registro.agregar(
            _texto(datos, "ips"), _texto(datos, "nombre"),
            _entero(datos, "puerto_rtsp", 554), _texto(datos, "ruta_rtsp", "/live/ch00_0") or "/live/ch00_0",
            _entero(datos, "puerto_onvif", 8899), _texto(datos, "usuario"), _texto(datos, "clave"))
        for c in res["agregadas"]:
            self.sincronizador.registrar_ya(c)
        return {"agregadas": [publica(c) for c in res["agregadas"]], "omitidas": res["omitidas"]}

    def quitar(self, cid: str) -> None:
        self.registro.quitar(cid)
        self.sincronizador.olvidar(cid)
        self.ptz.olvidar(cid)

    def exigir_admin(self, pin: str) -> None:
        exigir_admin(self.cfg.admin_pin, pin)
