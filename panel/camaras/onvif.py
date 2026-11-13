"""PTZ por ONVIF sin dependencias: SOAP 1.2 a mano + WS-Security (UsernameToken digest)."""
from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

NS_DEVICE = "http://www.onvif.org/ver10/device/wsdl"
NS_MEDIA = "http://www.onvif.org/ver10/media/wsdl"
NS_PTZ = "http://www.onvif.org/ver20/ptz/wsdl"
NS_SCHEMA = "http://www.onvif.org/ver10/schema"
NS_SOAP = "http://www.w3.org/2003/05/soap-envelope"
NS_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
NS_WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
PW_DIGEST = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest"
ENC_BASE64 = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary"


class OnvifError(Exception):
    pass


def _digest(nonce: bytes, created: str, clave: str) -> str:
    """base64(sha1(nonce + created + clave))."""
    crudo = nonce + created.encode("utf-8") + clave.encode("utf-8")
    return base64.b64encode(hashlib.sha1(crudo).digest()).decode("ascii")


def _esc(txt: str) -> str:
    return (txt.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _limitar(v: float) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise OnvifError("valor de movimiento no numérico")
    return max(-1.0, min(1.0, v))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


class Onvif:
    def __init__(self, ip, puerto=8899, usuario="", clave="", timeout=5.0, abrir=None):
        self.ip = ip
        self.puerto = int(puerto)
        self.usuario = usuario or ""
        self.clave = clave or ""
        self.timeout = timeout
        self._abrir = abrir or urllib.request.urlopen
        self._base = "http://%s:%d" % (ip, self.puerto)
        self._media = None
        self._ptz = None
        self._token = None
        self._lock = threading.Lock()

    # ---- SOAP ----
    def _cabecera(self) -> str:
        if not self.usuario:
            return ""
        nonce = secrets.token_bytes(16)
        creado = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            '<s:Header><wsse:Security xmlns:wsse="%s" xmlns:wsu="%s"><wsse:UsernameToken>'
            "<wsse:Username>%s</wsse:Username>"
            '<wsse:Password Type="%s">%s</wsse:Password>'
            '<wsse:Nonce EncodingType="%s">%s</wsse:Nonce>'
            "<wsu:Created>%s</wsu:Created></wsse:UsernameToken></wsse:Security></s:Header>"
            % (NS_WSSE, NS_WSU, _esc(self.usuario), PW_DIGEST, _digest(nonce, creado, self.clave),
               ENC_BASE64, base64.b64encode(nonce).decode("ascii"), creado)
        )

    def _llamar(self, url: str, ns: str, accion: str, cuerpo: str = "") -> ET.Element:
        sobre = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="%s">%s<s:Body>'
            '<%s xmlns="%s" xmlns:tt="%s">%s</%s></s:Body></s:Envelope>'
            % (NS_SOAP, self._cabecera(), accion, ns, NS_SCHEMA, cuerpo, accion)
        ).encode("utf-8")
        req = urllib.request.Request(url, data=sobre, method="POST", headers={
            "Content-Type": 'application/soap+xml; charset=utf-8; action="%s/%s"' % (ns, accion),
        })
        try:
            resp = self._abrir(req, timeout=self.timeout)
            estado = getattr(resp, "status", None) or resp.getcode()
            datos = resp.read()
        except urllib.error.HTTPError as e:
            estado = e.code
            try:
                datos = e.read()
            except Exception:
                datos = b""
        except (urllib.error.URLError, OSError) as e:
            raise OnvifError("sin conexión con %s: %s" % (url, getattr(e, "reason", e)))
        try:
            raiz = ET.fromstring(datos)
        except ET.ParseError:
            raiz = None
        fallo = self._fallo(raiz)
        if fallo is not None:
            raise OnvifError(fallo)
        if estado != 200:
            raise OnvifError("HTTP %s en %s" % (estado, url))
        if raiz is None:
            raise OnvifError("respuesta no es XML")
        return raiz

    @staticmethod
    def _fallo(raiz):
        if raiz is None:
            return None
        for el in raiz.iter():
            if _local(el.tag) == "Fault":
                textos = [(t.text or "").strip() for t in el.iter() if _local(t.tag) == "Text"]
                textos = [t for t in textos if t]
                if not textos:
                    textos = [(t.text or "").strip() for t in el.iter()
                              if _local(t.tag) in ("faultstring", "Value") and (t.text or "").strip()]
                return "; ".join(textos) or "fallo SOAP"
        return None

    # ---- servicios ----
    def _descubrir(self) -> None:
        if self._media and self._ptz:
            return
        media = ptz = None
        try:
            raiz = self._llamar(self._base + "/onvif/device_service", NS_DEVICE, "GetCapabilities",
                                "<Category>All</Category>")
            for el in raiz.iter():
                if _local(el.tag) in ("Media", "PTZ"):
                    for x in el:
                        if _local(x.tag) == "XAddr" and (x.text or "").strip():
                            if _local(el.tag) == "Media":
                                media = x.text.strip()
                            else:
                                ptz = x.text.strip()
        except OnvifError:
            pass
        self._media = media or self._base + "/onvif/media_service"
        self._ptz = ptz or self._base + "/onvif/ptz_service"

    def perfil(self) -> str:
        with self._lock:
            if self._token:
                return self._token
            self._descubrir()
            raiz = self._llamar(self._media, NS_MEDIA, "GetProfiles")
            for el in raiz.iter():
                if _local(el.tag) == "Profiles" and el.get("token"):
                    self._token = el.get("token")
                    return self._token
            raise OnvifError("la cámara no devolvió perfiles")

    def mover(self, x: float, y: float, zoom: float = 0.0) -> None:
        x, y, z = _limitar(x), _limitar(y), _limitar(zoom)
        token = self.perfil()
        cuerpo = (
            "<ProfileToken>%s</ProfileToken><Velocity>"
            '<tt:PanTilt x="%s" y="%s"/><tt:Zoom x="%s"/></Velocity>'
            % (_esc(token), x, y, z)
        )
        self._llamar(self._ptz, NS_PTZ, "ContinuousMove", cuerpo)

    def parar(self) -> None:
        token = self.perfil()
        cuerpo = ("<ProfileToken>%s</ProfileToken><PanTilt>true</PanTilt><Zoom>true</Zoom>"
                  % _esc(token))
        self._llamar(self._ptz, NS_PTZ, "Stop", cuerpo)


class ControlPTZ:
    def __init__(self, obtener_camara, timeout=5.0, autoparada=2.0, fabrica=Onvif):
        self._obtener = obtener_camara
        self._timeout = timeout
        self._autoparada = autoparada
        self._fabrica = fabrica
        self._lock = threading.Lock()
        self._conex = {}
        self._temps = {}

    def _conexion(self, cid, nueva=False):
        with self._lock:
            if not nueva and cid in self._conex:
                return self._conex[cid]
        c = self._obtener(cid)
        if not c:
            raise OnvifError("cámara desconocida: %s" % cid)
        con = self._fabrica(c["ip"], c.get("puerto_onvif", 8899), c.get("usuario", ""),
                            c.get("clave", ""), timeout=self._timeout)
        with self._lock:
            self._conex[cid] = con
        return con

    def _con_reintento(self, cid, accion):
        try:
            accion(self._conexion(cid))
        except OnvifError:
            with self._lock:
                self._conex.pop(cid, None)
            accion(self._conexion(cid, nueva=True))

    def mover(self, cid, x, y) -> None:
        self._con_reintento(cid, lambda con: con.mover(x, y))
        self._programar(cid)

    def _programar(self, cid) -> None:
        with self._lock:
            previo = self._temps.pop(cid, None)
            if previo:
                previo.cancel()
            t = threading.Timer(self._autoparada, self._parada_auto, args=(cid,))
            t.daemon = True
            self._temps[cid] = t
            t.start()

    def _parada_auto(self, cid) -> None:
        with self._lock:
            self._temps.pop(cid, None)
        try:
            self._con_reintento(cid, lambda con: con.parar())
        except Exception:
            pass

    def parar(self, cid) -> None:
        with self._lock:
            t = self._temps.pop(cid, None)
            if t:
                t.cancel()
        self._con_reintento(cid, lambda con: con.parar())

    def olvidar(self, cid) -> None:
        with self._lock:
            self._conex.pop(cid, None)
            t = self._temps.pop(cid, None)
        if t:
            t.cancel()
