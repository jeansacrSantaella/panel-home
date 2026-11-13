"""Pruebas de panel.camaras.onvif sin red."""
from __future__ import annotations

import base64
import hashlib
import io
import time
import unittest
import urllib.error
import xml.etree.ElementTree as ET

from panel.camaras.onvif import ControlPTZ, Onvif, OnvifError, _digest

CAPS = b"""<?xml version="1.0"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"
 xmlns:tds="http://www.onvif.org/ver10/device/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
<SOAP-ENV:Body><tds:GetCapabilitiesResponse><tds:Capabilities>
<tt:Media><tt:XAddr>http://10.0.0.5:8899/onvif/media_x</tt:XAddr></tt:Media>
<tt:PTZ><tt:XAddr>http://10.0.0.5:8899/onvif/ptz_x</tt:XAddr></tt:PTZ>
</tds:Capabilities></tds:GetCapabilitiesResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"""

PROFILES = b"""<?xml version="1.0"?><s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
 xmlns:trt="http://www.onvif.org/ver10/media/wsdl" xmlns:tt="http://www.onvif.org/ver10/schema">
<s:Body><trt:GetProfilesResponse>
<trt:Profiles token="PROFILE_A" fixed="true"><tt:Name>uno</tt:Name></trt:Profiles>
<trt:Profiles token="PROFILE_B"><tt:Name>dos</tt:Name></trt:Profiles>
</trt:GetProfilesResponse></s:Body></s:Envelope>"""

OK = b"""<?xml version="1.0"?><s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body/></s:Envelope>"""

FAULT = b"""<?xml version="1.0"?><s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body>
<s:Fault><s:Code><s:Value>s:Sender</s:Value></s:Code><s:Reason><s:Text xml:lang="en">Sender not Authorized</s:Text></s:Reason>
</s:Fault></s:Body></s:Envelope>"""


class Resp:
    def __init__(self, datos, status=200):
        self._d, self.status = datos, status

    def read(self):
        return self._d

    def getcode(self):
        return self.status


class Falso:
    """abrir falso: guarda lo enviado y responde segun la accion."""

    def __init__(self, fallo_en=None, http=None):
        self.enviados = []
        self.fallo_en = fallo_en
        self.http = http

    def __call__(self, req, timeout=None):
        cuerpo = req.data.decode()
        raiz = ET.fromstring(cuerpo)
        body = [e for e in raiz if e.tag.endswith("}Body")][0]
        accion = body[0].tag.split("}")[1]
        self.enviados.append((req.full_url, accion, raiz))
        if self.http:
            raise urllib.error.HTTPError(req.full_url, self.http, "x", {}, io.BytesIO(FAULT))
        if accion == self.fallo_en:
            raise urllib.error.HTTPError(req.full_url, 500, "x", {}, io.BytesIO(FAULT))
        return Resp({"GetCapabilities": CAPS, "GetProfiles": PROFILES}.get(accion, OK))


def _q(raiz, nombre):
    return [e for e in raiz.iter() if e.tag.endswith("}" + nombre)]


class TestOnvif(unittest.TestCase):
    def test_digest(self):
        nonce, creado, clave = b"0123456789abcdef", "2024-01-02T03:04:05Z", "secreto"
        esperado = base64.b64encode(hashlib.sha1(nonce + creado.encode() + b"secreto").digest()).decode()
        self.assertEqual(_digest(nonce, creado, clave), esperado)

    def test_perfil_y_endpoints(self):
        f = Falso()
        o = Onvif("10.0.0.5", 8899, abrir=f)
        self.assertEqual(o.perfil(), "PROFILE_A")
        self.assertEqual(o.perfil(), "PROFILE_A")  # caché
        urls = [(u, a) for u, a, _ in f.enviados]
        self.assertEqual(urls[0], ("http://10.0.0.5:8899/onvif/device_service", "GetCapabilities"))
        self.assertEqual(urls[1], ("http://10.0.0.5:8899/onvif/media_x", "GetProfiles"))
        self.assertEqual(len(urls), 2)
        self.assertEqual(_q(f.enviados[0][2], "Security"), [])

    def test_capabilities_falla_usa_defecto(self):
        f = Falso(fallo_en="GetCapabilities")
        o = Onvif("10.0.0.5", 8899, abrir=f)
        self.assertEqual(o.perfil(), "PROFILE_A")
        self.assertEqual(f.enviados[1][0], "http://10.0.0.5:8899/onvif/media_service")

    def test_mover_recorta_y_parar(self):
        f = Falso()
        o = Onvif("10.0.0.5", abrir=f)
        o.mover(3, -2, 0.5)
        url, accion, raiz = f.enviados[-1]
        self.assertEqual((url, accion), ("http://10.0.0.5:8899/onvif/ptz_x", "ContinuousMove"))
        self.assertEqual(_q(raiz, "ProfileToken")[0].text, "PROFILE_A")
        pt = _q(raiz, "PanTilt")[0]
        self.assertEqual((float(pt.get("x")), float(pt.get("y"))), (1.0, -1.0))
        self.assertEqual(float(_q(raiz, "Zoom")[0].get("x")), 0.5)
        o.parar()
        _, accion, raiz = f.enviados[-1]
        self.assertEqual(accion, "Stop")
        self.assertEqual(_q(raiz, "PanTilt")[0].text, "true")
        self.assertEqual(_q(raiz, "Zoom")[0].text, "true")

    def test_seguridad(self):
        f = Falso()
        Onvif("10.0.0.5", usuario="admin", clave="pw", abrir=f).perfil()
        raiz = f.enviados[0][2]
        self.assertEqual(_q(raiz, "Username")[0].text, "admin")
        nonce = base64.b64decode(_q(raiz, "Nonce")[0].text)
        self.assertEqual(len(nonce), 16)
        creado = _q(raiz, "Created")[0].text
        self.assertEqual(_q(raiz, "Password")[0].text, _digest(nonce, creado, "pw"))

    def test_fault_y_http(self):
        with self.assertRaises(OnvifError) as c:
            Onvif("10.0.0.5", abrir=Falso(fallo_en="GetProfiles")).perfil()
        self.assertIn("Sender not Authorized", str(c.exception))
        with self.assertRaises(OnvifError):
            Onvif("10.0.0.5", abrir=Falso(http=401)).perfil()

    def test_timeout(self):
        def abrir(req, timeout=None):
            raise TimeoutError("timed out")
        with self.assertRaises(OnvifError):
            Onvif("10.0.0.5", abrir=abrir).perfil()


class Conex:
    def __init__(self, ip, puerto, usuario, clave, timeout=5.0, fallar=0):
        self.ip, self.llamadas, self.fallar = ip, [], fallar
        Conex.vivas.append(self)

    vivas: list = []

    def mover(self, x, y, zoom=0.0):
        if self.fallar:
            self.fallar -= 1
            raise OnvifError("caída")
        self.llamadas.append(("mover", x, y))

    def parar(self):
        self.llamadas.append(("parar",))


class TestControl(unittest.TestCase):
    def setUp(self):
        Conex.vivas = []
        self.cam = {"ip": "1.2.3.4", "puerto_onvif": 8899, "usuario": "", "clave": ""}

    def ctl(self, **kw):
        return ControlPTZ(lambda cid: self.cam if cid == "c1" else None, fabrica=Conex, **kw)

    def test_cache_y_reintento(self):
        c = self.ctl(autoparada=60)
        c.mover("c1", 1, 0)
        c.mover("c1", 0, 1)
        self.assertEqual(len(Conex.vivas), 1)
        Conex.vivas[0].fallar = 1
        c.mover("c1", 1, 1)
        self.assertEqual(len(Conex.vivas), 2)
        self.assertEqual(Conex.vivas[1].llamadas, [("mover", 1, 1)])
        c.olvidar("c1")

    def test_falla_dos_veces(self):
        c = self.ctl(autoparada=60)
        c.mover("c1", 0, 0)
        orig = Conex.mover

        def siempre(self, *a, **k):
            raise OnvifError("x")
        Conex.mover = siempre
        try:
            with self.assertRaises(OnvifError):
                c.mover("c1", 1, 0)
        finally:
            Conex.mover = orig
            c.olvidar("c1")

    def test_camara_desconocida(self):
        with self.assertRaises(OnvifError):
            self.ctl().mover("zz", 1, 0)

    def test_autoparada(self):
        c = self.ctl(autoparada=0.05)
        c.mover("c1", 1, 0)
        time.sleep(0.3)
        self.assertEqual(Conex.vivas[0].llamadas, [("mover", 1, 0), ("parar",)])

    def test_autoparada_se_reinicia(self):
        c = self.ctl(autoparada=0.15)
        c.mover("c1", 1, 0)
        time.sleep(0.08)
        c.mover("c1", 1, 0)
        time.sleep(0.1)
        self.assertNotIn(("parar",), Conex.vivas[0].llamadas)
        time.sleep(0.2)
        self.assertEqual(Conex.vivas[0].llamadas.count(("parar",)), 1)

    def test_olvidar(self):
        c = self.ctl(autoparada=0.05)
        c.mover("c1", 1, 0)
        c.olvidar("c1")
        time.sleep(0.2)
        self.assertEqual(Conex.vivas[0].llamadas, [("mover", 1, 0)])
        c.mover("c1", 0, 1)
        self.assertEqual(len(Conex.vivas), 2)
        c.olvidar("c1")


if __name__ == "__main__":
    unittest.main()
