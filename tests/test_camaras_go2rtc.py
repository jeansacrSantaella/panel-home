from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs, urlsplit
from io import BytesIO
from panel.camaras.go2rtc import Go2rtc, Go2rtcError, Sincronizador, SCRIPTS


class RespuestaFalsa:
    def __init__(self, contenido: bytes, status: int = 200):
        self._contenido = contenido
        self.status = status

    def read(self) -> bytes:
        return self._contenido

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestGo2rtc(unittest.TestCase):
    def setUp(self):
        self.peticiones = []
        self.presentes = {"camara1": {"producers": []}}  # flujos que go2rtc conoce

        def abrir_falso(req, timeout=5):
            self.peticiones.append((req.method, req.full_url))
            url = req.full_url
            
            if "/api/streams" in url and req.method == "GET":
                if "error" in url:
                    raise Exception("Fallo de red")
                return RespuestaFalsa(json.dumps(self.presentes).encode())
            
            if "/api/streams" in url and req.method == "PUT":
                if "fallo_stream" in url:
                    return RespuestaFalsa(b"Error", 400)
                self.presentes[parse_qs(urlsplit(url).query)["name"][0]] = {"producers": []}
                return RespuestaFalsa(b"OK")

            if "/api/preload" in url and req.method == "PUT":
                if "fallo_preload" in url:
                    return RespuestaFalsa(b"Error", 400)
                return RespuestaFalsa(b"OK")

            if "/api/streams" in url and req.method == "DELETE":
                return RespuestaFalsa(b"OK")

            if "/video-stream.js" in url:
                if "fallo_script" in url:
                    raise Exception("Error script")
                return RespuestaFalsa(b"console.log('stream');")

            return RespuestaFalsa(b"Not Found", 404)

        self.go2rtc = Go2rtc("http://localhost:1984", abrir=abrir_falso)

    def test_streams_ok_y_error(self):
        res = self.go2rtc.streams()
        self.assertEqual(res, {"camara1": {"producers": []}})

        # Forzar error cambiando temporalmente el comportamiento o usando URL con error
        go2rtc_err = Go2rtc("http://localhost:1984", abrir=lambda r, timeout=5: (_ for _ in ()).throw(Exception("err")))
        self.assertIsNone(go2rtc_err.streams())

    def test_registrar(self):
        # Registro normal
        ok = self.go2rtc.registrar("camara1", "rtsp://test")
        self.assertTrue(ok)
        self.assertIn(("PUT", "http://localhost:1984/api/streams?name=camara1&src=rtsp%3A%2F%2Ftest"), self.peticiones)
        self.assertIn(("PUT", "http://localhost:1984/api/preload?src=camara1&query=video%26audio"), self.peticiones)

        # Fallo en preload no debe romper el True
        self.peticiones.clear()
        go2rtc_preload_fail = Go2rtc("http://localhost:1984", abrir=lambda r, timeout=5: RespuestaFalsa(b"Error", 400) if "preload" in r.full_url else RespuestaFalsa(b"OK"))
        ok_preload = go2rtc_preload_fail.registrar("camara1", "rtsp://test")
        self.assertTrue(ok_preload)

        # Fallo en streams debe retornar False
        go2rtc_stream_fail = Go2rtc("http://localhost:1984", abrir=lambda r, timeout=5: RespuestaFalsa(b"Error", 400) if "streams" in r.full_url else RespuestaFalsa(b"OK"))
        ok_stream = go2rtc_stream_fail.registrar("camara1", "rtsp://test")
        self.assertFalse(ok_stream)

        # Sin conexión -> None (se reintentará), no False
        sin_red = Go2rtc("http://localhost:1984", abrir=lambda r, timeout=5: (_ for _ in ()).throw(OSError("timeout")))
        self.assertIsNone(sin_red.registrar("camara1", "rtsp://test"))

    def test_sincronizador_fallidas(self):
        """Rechazada por go2rtc no se reintenta; sin conexión sí; registrar_ya la vuelve a intentar."""
        camaras = [{"id": "cam1", "ip": "1.1.1.1"}]
        estado = {"rechaza": True, "sin_red": False}
        pedidas = []

        def abrir(req, timeout=5):
            pedidas.append(req.method)
            if req.method == "GET":
                return RespuestaFalsa(b"{}")
            if estado["sin_red"]:
                raise OSError("timeout")
            return RespuestaFalsa(b"Error", 400) if estado["rechaza"] and "streams" in req.full_url else RespuestaFalsa(b"OK")

        sync = Sincronizador(Go2rtc("http://x", abrir=abrir), lambda: camaras, lambda c: f"rtsp://{c['ip']}")
        self.assertEqual(sync.vuelta(), 0)
        pedidas.clear()
        self.assertEqual(sync.vuelta(), 0)
        self.assertEqual(pedidas, ["GET"])  # la rechazada no se reintenta
        estado["rechaza"] = False
        self.assertTrue(sync.registrar_ya(camaras[0]))

        sync2 = Sincronizador(Go2rtc("http://x", abrir=abrir), lambda: camaras, lambda c: f"rtsp://{c['ip']}")
        estado["sin_red"] = True
        self.assertEqual(sync2.vuelta(), 0)
        estado["sin_red"] = False
        self.assertEqual(sync2.vuelta(), 1)  # sin conexión sí se reintenta

    def test_script_cache_y_val(self):
        # Nombre raro -> ValueError
        with self.assertRaises(ValueError):
            self.go2rtc.script("script_malo.js")

        # Segunda llamada usa caché (una sola petición)
        contenido1 = self.go2rtc.script("video-stream.js")
        self.assertEqual(contenido1, b"console.log('stream');")
        
        peticiones_antes = len(self.peticiones)
        contenido2 = self.go2rtc.script("video-stream.js")
        self.assertEqual(contenido2, b"console.log('stream');")
        self.assertEqual(len(self.peticiones), peticiones_antes)

    def test_sincronizador(self):
        camaras = [{"id": "cam1", "ip": "1.1.1.1"}, {"id": "cam2", "ip": "2.2.2.2"}]
        fuente_fn = lambda c: f"rtsp://{c['ip']}"

        sync = Sincronizador(self.go2rtc, lambda: camaras, fuente_fn)

        # Primera vuelta: registra las cámaras que faltan
        registradas = sync.vuelta()
        self.assertEqual(registradas, 2)
        self.assertFalse(sync.caido)

        # Segunda vuelta: ya están registradas, no hace nada nuevo
        self.peticiones.clear()
        registradas = sync.vuelta()
        self.assertEqual(registradas, 0)

        # Cambia la fuente de cam1: debe re-registrarla
        camaras[0]["ip"] = "1.1.1.9"
        registradas = sync.vuelta()
        self.assertEqual(registradas, 1)

        # Olvidar cámara
        sync.olvidar("cam2")
        self.assertIn(("DELETE", "http://localhost:1984/api/streams?src=cam2"), self.peticiones)

        # Go2rtc caído -> 0 y caido True
        go2rtc_caido = Go2rtc("http://localhost:1984", abrir=lambda r, timeout=5: (_ for _ in ()).throw(Exception("down")))
        sync_caido = Sincronizador(go2rtc_caido, lambda: camaras, fuente_fn)
        self.assertEqual(sync_caido.vuelta(), 0)
        self.assertTrue(sync_caido.caido)


if __name__ == "__main__":
    unittest.main()
