"""Pruebas del puente de video en modo de transición (sin cámaras internas)."""
from __future__ import annotations

import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from panel.config import Config
from panel.db import Db
from panel.eventos import Recolector
from panel.web import crear_servidor


class SesionAbierta:
    def sesion(self, token):
        return {"usuario": "admin", "debe_cambiar": False}


class SinSesion:
    def sesion(self, token):
        return None


class Go2rtcHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/api/streams":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"camara1": {}}')
        elif self.path in ("/video-stream.js", "/video-rtc.js"):
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript")
            self.end_headers()
            self.wfile.write(b"// js go2rtc")
        else:
            self.send_response(404)
            self.end_headers()


class BasePuente(unittest.TestCase):
    auth = SesionAbierta
    go2rtc_activo = True
    camaras_internas = False

    def setUp(self):
        if self.go2rtc_activo:
            self.go2rtc_srv = ThreadingHTTPServer(("127.0.0.1", 0), Go2rtcHandler)
            self.go2rtc_puerto = self.go2rtc_srv.server_address[1]
            self.go2rtc_hilo = threading.Thread(target=self.go2rtc_srv.serve_forever, daemon=True)
            self.go2rtc_hilo.start()
            self.addCleanup(self._parar_go2rtc)
            go2rtc_url = f"http://127.0.0.1:{self.go2rtc_puerto}"
        else:
            go2rtc_url = ""

        self.cfg = Config(
            host="127.0.0.1",
            port=0,
            camaras_internas=self.camaras_internas,
            go2rtc_url=go2rtc_url,
        )
        db = Db(":memory:")
        self.srv = crear_servidor(self.cfg, db, Recolector(self.cfg, db), self.auth(), camaras=None)
        self.puerto = self.srv.server_address[1]
        self.hilo = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.hilo.start()
        self.addCleanup(self._parar_srv)

    def _parar_go2rtc(self):
        self.go2rtc_srv.shutdown()
        self.go2rtc_srv.server_close()
        self.go2rtc_hilo.join()

    def _parar_srv(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.hilo.join()

    def pedir(self, metodo, ruta, cuerpo=None, cab=None, crudo=False):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        cab = dict(cab or {})
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            cab["Content-Type"] = "application/json"
        con.request(metodo, ruta, datos, cab)
        r = con.getresponse()
        raw = r.read()
        con.close()
        if crudo:
            return r.status, raw, r
        try:
            return r.status, json.loads(raw), r
        except ValueError:
            return r.status, raw, r


class TestPuenteVideo(BasePuente):
    def test_camaras_puente_flag_en_panel(self):
        st, d, _ = self.pedir("GET", "/api/panel")
        self.assertEqual(st, 200)
        self.assertTrue(d["camaras_puente"])

    def test_scripts_go2rtc(self):
        st, cuerpo, r = self.pedir("GET", "/api/camaras/go2rtc/video-stream.js", crudo=True)
        self.assertEqual(st, 200)
        self.assertEqual(cuerpo, b"// js go2rtc")
        self.assertIn("text/javascript", r.getheader("Content-Type"))

        st, cuerpo, _ = self.pedir("GET", "/api/camaras/go2rtc/video-rtc.js", crudo=True)
        self.assertEqual(st, 200)
        self.assertEqual(cuerpo, b"// js go2rtc")

        st, _, _ = self.pedir("GET", "/api/camaras/go2rtc/otro.js")
        self.assertEqual(st, 404)

    def test_go2rtc_caido(self):
        # Apagar go2rtc para simular fallo 502
        self._parar_go2rtc()
        st, d, _ = self.pedir("GET", "/api/camaras/go2rtc/video-stream.js")
        self.assertEqual(st, 502)

    def test_video_websocket_validaciones(self):
        cab_ws = {"Upgrade": "websocket", "Connection": "Upgrade"}

        # src desconocida -> 404
        st, d, _ = self.pedir("GET", "/api/camaras/video?src=desconocida", cab=cab_ws)
        self.assertEqual(st, 404)
        self.assertEqual(d["error"], "cámara desconocida")

        # Origin de otro host -> 403
        cab_malo = dict(cab_ws)
        cab_malo["Origin"] = "http://malo.com"
        st, d, _ = self.pedir("GET", "/api/camaras/video?src=camara1", cab=cab_malo)
        self.assertEqual(st, 403)
        self.assertEqual(d["error"], "origen no permitido")

        # Sin cabecera Upgrade -> 400
        st, d, _ = self.pedir("GET", "/api/camaras/video?src=camara1")
        self.assertEqual(st, 400)
        self.assertEqual(d["error"], "se espera WebSocket")


class TestPuenteSinGo2rtcUrl(BasePuente):
    go2rtc_activo = False

    def test_camaras_puente_false_sin_go2rtc_url(self):
        st, d, _ = self.pedir("GET", "/api/panel")
        self.assertEqual(st, 200)
        self.assertFalse(d["camaras_puente"])

    def test_409_sin_go2rtc_url(self):
        st, _, _ = self.pedir("GET", "/api/camaras/go2rtc/video-stream.js")
        self.assertEqual(st, 409)

        cab_ws = {"Upgrade": "websocket", "Connection": "Upgrade"}
        st, _, _ = self.pedir("GET", "/api/camaras/video?src=camara1", cab=cab_ws)
        self.assertEqual(st, 409)


class TestPuenteCamarasInternas(BasePuente):
    camaras_internas = True

    def test_camaras_puente_false_con_camaras_internas(self):
        st, d, _ = self.pedir("GET", "/api/panel")
        self.assertEqual(st, 200)
        self.assertFalse(d["camaras_puente"])


class TestPuenteSinSesion(BasePuente):
    auth = SinSesion

    def test_requiere_sesion(self):
        self.assertEqual(self.pedir("GET", "/api/panel")[0], 401)
        self.assertEqual(self.pedir("GET", "/api/camaras/go2rtc/video-stream.js")[0], 401)
        cab_ws = {"Upgrade": "websocket", "Connection": "Upgrade"}
        self.assertEqual(self.pedir("GET", "/api/camaras/video?src=camara1", cab=cab_ws)[0], 401)


if __name__ == "__main__":
    unittest.main()
