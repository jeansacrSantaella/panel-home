from __future__ import annotations

import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from panel.camaras.video import Sesiones, SinLugar, puente_websocket


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class PruebaSesiones(unittest.TestCase):
    def setUp(self):
        self.r = Reloj()
        self.s = Sesiones(maximo=2, caduca=60, reloj=self.r)

    def test_maximo_y_info(self):
        a = self.s.abrir()
        self.s.abrir()
        with self.assertRaises(SinLugar) as c:
            self.s.abrir()
        self.assertEqual(len(c.exception.info), 2)
        self.assertEqual(a["maximo"], 2)

    def test_caducidad(self):
        a = self.s.abrir()["id"]
        self.r.t += 61
        self.assertFalse(self.s.valida(a))
        self.assertEqual(self.s.latido(a), "expulsada")
        self.s.abrir()
        self.s.abrir()

    def test_latido_renueva(self):
        a = self.s.abrir()["id"]
        self.r.t += 50
        self.assertEqual(self.s.latido(a), "ok")
        self.r.t += 50
        self.assertTrue(self.s.valida(a))

    def test_salir_libera(self):
        a = self.s.abrir()["id"]
        self.s.abrir()
        self.s.salir(a)
        self.assertEqual(self.s.latido(a), "expulsada")
        self.s.abrir()


def falso_go2rtc(codigo101=True):
    """Servidor TCP: responde 101 (o 404) y hace eco."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    vistos = []

    def atender(c):
        datos = b""
        while b"\r\n\r\n" not in datos:
            t = c.recv(4096)
            if not t:
                return
            datos += t
        vistos.append(datos)
        if not codigo101:
            c.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            c.close()
            return
        c.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
        while True:
            t = c.recv(65536)
            if not t:
                break
            c.sendall(t)
        c.close()

    def bucle():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=atender, args=(c,), daemon=True).start()

    threading.Thread(target=bucle, daemon=True).start()
    return srv, vistos


def servidor_puente(url):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            puente_websocket(self, url, "camara 1", timeout=3)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


PETICION = (b"GET /api/camaras/video?src=x HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\n"
            b"Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            b"Sec-WebSocket-Version: 13\r\n\r\n")


def leer_hasta(sock, fin):
    datos = b""
    while fin not in datos:
        t = sock.recv(4096)
        if not t:
            break
        datos += t
    return datos


class PruebaPuente(unittest.TestCase):
    def test_eco_en_ambos_sentidos(self):
        falso, vistos = falso_go2rtc()
        web = servidor_puente("http://127.0.0.1:%d" % falso.getsockname()[1])
        try:
            c = socket.create_connection(("127.0.0.1", web.server_address[1]), timeout=3)
            c.sendall(PETICION)
            cab = leer_hasta(c, b"\r\n\r\n")
            self.assertTrue(cab.startswith(b"HTTP/1.1 101"))
            c.sendall(b"hola")
            self.assertEqual(c.recv(100), b"hola")
            grande = b"x" * 200000
            c.sendall(grande)
            recibido = b""
            while len(recibido) < len(grande):
                recibido += c.recv(65536)
            self.assertEqual(recibido, grande)
            c.close()
            peticion = vistos[0]
            self.assertIn(b"GET /api/ws?src=camara%201 HTTP/1.1", peticion)
            self.assertIn(b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==", peticion)
        finally:
            web.shutdown()
            web.server_close()
            falso.close()

    def test_go2rtc_404_da_502(self):
        falso, _ = falso_go2rtc(codigo101=False)
        web = servidor_puente("http://127.0.0.1:%d" % falso.getsockname()[1])
        try:
            c = socket.create_connection(("127.0.0.1", web.server_address[1]), timeout=3)
            c.sendall(PETICION)
            self.assertTrue(c.recv(4096).startswith(b"HTTP/1.0 502"))
            c.close()
        finally:
            web.shutdown()
            web.server_close()
            falso.close()

    def test_sin_conexion_da_502_y_sin_upgrade_400(self):
        libre = socket.socket()
        libre.bind(("127.0.0.1", 0))
        puerto = libre.getsockname()[1]
        libre.close()
        web = servidor_puente("http://127.0.0.1:%d" % puerto)
        try:
            c = socket.create_connection(("127.0.0.1", web.server_address[1]), timeout=3)
            c.sendall(PETICION)
            self.assertIn(b" 502 ", c.recv(4096).split(b"\r\n")[0])
            c.close()
            c = socket.create_connection(("127.0.0.1", web.server_address[1]), timeout=3)
            c.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
            self.assertIn(b" 400 ", c.recv(4096).split(b"\r\n")[0])
            c.close()
        finally:
            web.shutdown()
            web.server_close()


if __name__ == "__main__":
    unittest.main()
