"""Pruebas del escáner de equipo: sin red real (servidor TCP local y dobles de prueba)."""
from __future__ import annotations

import socket
import threading
import unittest

from panel.red.escaner import (Escaner, escanear_puerto, nombre_servicio, parse_puertos, pista_so)


class _Red:
    """Doble de la red: equipos() devuelve la base de equipos."""

    def __init__(self, equipos):
        self._equipos = equipos

    def equipos(self):
        return list(self._equipos)


def _servidor_banner(texto: bytes):
    """Servidor TCP local en 127.0.0.1 (puerto libre) que envía `texto` al conectar."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    puerto = srv.getsockname()[1]

    def atender():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            try:
                conn.sendall(texto)
            except OSError:
                pass
            conn.close()

    threading.Thread(target=atender, daemon=True).start()
    return srv, puerto


def _puerto_cerrado() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    puerto = s.getsockname()[1]
    s.close()
    return puerto


class PuertosTest(unittest.TestCase):
    def test_parse_rangos_y_listas(self):
        self.assertEqual(parse_puertos("22, 80,8000-8002"), [22, 80, 8000, 8001, 8002])
        self.assertEqual(parse_puertos("5,3-4,4"), [3, 4, 5])

    def test_comunes_por_defecto(self):
        self.assertIn(22, parse_puertos(None))
        self.assertEqual(parse_puertos("common"), parse_puertos(""))

    def test_limite_de_puertos(self):
        self.assertEqual(len(parse_puertos("1-5000")), 5000)
        with self.assertRaises(ValueError):
            parse_puertos("1-5001")

    def test_rechaza_invalidos(self):
        for spec in ("abc", "0", "1-70000", "100-50", ",", "1-6000"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                parse_puertos(spec)

    def test_pista_so(self):
        self.assertIsNone(pista_so(None))
        self.assertIn("Linux", pista_so(63))
        self.assertEqual(pista_so(120), "Windows")
        self.assertIn("Equipo de red", pista_so(200))

    def test_nombre_servicio(self):
        self.assertEqual(nombre_servicio(22), "ssh")
        self.assertEqual(nombre_servicio(443), "https")


class EscanearPuertoTest(unittest.TestCase):
    def test_puerto_abierto_con_banner(self):
        srv, puerto = _servidor_banner(b"SSH-2.0-prueba\r\nmas\r\n")
        try:
            r = escanear_puerto("127.0.0.1", puerto, timeout=1.0)
        finally:
            srv.close()
        self.assertEqual(r["port"], puerto)
        self.assertEqual(r["banner"], "SSH-2.0-prueba")
        self.assertEqual(set(r), {"port", "service", "banner"})

    def test_puerto_cerrado(self):
        self.assertIsNone(escanear_puerto("127.0.0.1", _puerto_cerrado(), timeout=0.5))


class EscanerTest(unittest.TestCase):
    def setUp(self):
        self.srv, self.abierto = _servidor_banner(b"hola\r\n")
        self.cerrado = _puerto_cerrado()
        self.equipo = {"mac": "00:11:22:33:44:55", "ip": "127.0.0.1", "hostname": "caja",
                       "alias": "Mi PC", "network": "5 GHz", "first_seen": 1, "online": 1}

    def tearDown(self):
        self.srv.close()

    def _escaner(self, equipos=None, **extra):
        opciones = dict(
            fabricante=lambda mac: "ACME",
            ping_series=lambda ip, count: ([1.0, 3.0], 64),
            dns_query=lambda server, name=None, timeout=None: (False, None),
            resolver_nombre=lambda host: "127.0.0.1",
        )
        opciones.update(extra)
        red = _Red([self.equipo] if equipos is None else equipos)
        return Escaner(red, **opciones)

    def test_forma_de_la_respuesta(self):
        r = self._escaner().escanear("servidor.local", f"{self.cerrado},{self.abierto}")
        self.assertEqual(set(r), {"host", "ip", "hostname", "mac", "vendor", "random_mac", "known",
                                  "ping", "ttl", "os_hint", "dns", "ports_scanned", "open",
                                  "steps", "elapsed"})
        self.assertEqual(r["host"], "servidor.local")
        self.assertEqual(r["ip"], "127.0.0.1")
        self.assertEqual(r["ports_scanned"], 2)
        self.assertEqual([p["port"] for p in r["open"]], [self.abierto])
        self.assertEqual(r["ping"]["loss"], 50.0)
        self.assertEqual(r["ttl"], 64)
        self.assertEqual(r["os_hint"], "Linux, macOS, iOS o Android")
        self.assertEqual(r["dns"], {"ok": False, "ms": None})
        self.assertEqual(len(r["steps"]), 6)
        self.assertIsInstance(r["elapsed"], float)

    def test_identifica_equipo_por_la_base(self):
        r = self._escaner().escanear("servidor.local", [self.abierto])
        self.assertEqual(r["mac"], "00:11:22:33:44:55")
        self.assertEqual(r["vendor"], "ACME")
        self.assertFalse(r["random_mac"])
        self.assertEqual(r["known"], {"alias": "Mi PC", "hostname": "caja",
                                      "network": "5 GHz", "first_seen": 1})

    def test_equipo_desconocido(self):
        r = self._escaner(equipos=[]).escanear("servidor.local", [self.abierto])
        self.assertIsNone(r["mac"])
        self.assertIsNone(r["vendor"])
        self.assertIsNone(r["known"])
        self.assertFalse(r["random_mac"])

    def test_mac_aleatoria(self):
        equipo = dict(self.equipo, mac="02:11:22:33:44:55")
        r = self._escaner(equipos=[equipo]).escanear("servidor.local", [self.abierto])
        self.assertTrue(r["random_mac"])

    def test_dns_responde(self):
        r = self._escaner(dns_query=lambda server, name=None, timeout=None: (True, 12.34)) \
            .escanear("servidor.local", [self.abierto])
        self.assertEqual(r["dns"], {"ok": True, "ms": 12.3})
        self.assertIn("responde en 12.3 ms", r["steps"][4])

    def test_ping_sin_respuesta_ttl_nulo(self):
        r = self._escaner(ping_series=lambda ip, count: ([], None)) \
            .escanear("servidor.local", [self.abierto])
        self.assertIsNone(r["ttl"])
        self.assertIsNone(r["os_hint"])
        self.assertEqual(r["ping"]["loss"], 100.0)

    def test_host_invalido(self):
        for host in ("", "   ", "a b; rm", "x" * 254):
            with self.subTest(host=host), self.assertRaisesRegex(ValueError, "host inválido"):
                self._escaner().escanear(host, [self.abierto])

    def test_no_resuelve(self):
        def falla(host):
            raise socket.gaierror("sin nombre")

        with self.assertRaisesRegex(ValueError, "no se pudo resolver nohay.local"):
            self._escaner(resolver_nombre=falla).escanear("nohay.local", [self.abierto])

    def test_puertos_invalidos(self):
        with self.assertRaisesRegex(ValueError, "no se indicaron puertos"):
            self._escaner().escanear("servidor.local", [])
        with self.assertRaisesRegex(ValueError, "fuera de rango"):
            self._escaner().escanear("servidor.local", [70000])
        with self.assertRaisesRegex(ValueError, "rango de puertos inválido"):
            self._escaner().escanear("servidor.local", "abc")


if __name__ == "__main__":
    unittest.main()
