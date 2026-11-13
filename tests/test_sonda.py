"""Pruebas de la sonda: sin red real ni esperas."""
from __future__ import annotations

import json
import unittest

from sonda import medir
from sonda.sonda import Sonda

ARP_MAC = """? (192.168.1.1) at aa:bb:cc:dd:ee:ff on en0 ifscope [ethernet]
? (192.168.1.5) at 0:1a:2b:3c:4d:5e on en0 ifscope [ethernet]
? (192.168.1.9) at (incomplete) on en0 ifscope [ethernet]
? (192.168.1.255) at ff:ff:ff:ff:ff:ff on en0 ifscope [ethernet]
? (224.0.0.251) at 1:0:5e:0:0:fb on en0 ifscope permanent [ethernet]
"""
NEIGH = """192.168.1.1 dev eth0 lladdr AA:BB:CC:DD:EE:FF REACHABLE
192.168.1.7 dev eth0 lladdr 11:22:33:44:55:66 STALE
192.168.1.8 dev eth0  FAILED
192.168.1.9 dev eth0  INCOMPLETE
"""
ARP_WIN = """
Interfaz: 192.168.1.50 --- 0x5
  Dirección de Internet          Dirección física      Tipo
  192.168.1.1           aa-bb-cc-dd-ee-ff     dinámico
  192.168.1.20          11-22-33-44-55-66     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     estático
  224.0.0.22            01-00-5e-00-00-16     estático
"""
PING_ES = "Respuesta desde 192.168.1.1: bytes=32 tiempo=3ms TTL=64\nRespuesta desde 192.168.1.1: bytes=32 tiempo<1ms TTL=64"
PING_EN = "Reply from 192.168.1.1: bytes=32 time=12ms TTL=118"


class MedidorFalso:
    def __init__(self):
        self.gw = "192.168.1.1"
        self.ip = "192.168.1.50"
        self.arp = {}
        self.vivos = set()
        self.rdns_llamadas = []
        self.externos_ok = True

    def gateway(self):
        return self.gw

    def local_ip(self):
        return self.ip

    def ping(self, host, timeout=1.0):
        if host in ("1.1.1.1", "8.8.8.8") and not self.externos_ok:
            return False, None
        return True, 2.0

    def dns_query(self, server, name="example.com", timeout=2.0):
        return True, 5.0

    def read_arp(self):
        return dict(self.arp)

    def reverse_dns(self, ip):
        self.rdns_llamadas.append(ip)
        return "host-" + ip.split(".")[-1]

    def fetch(self, url, timeout=10, data=None):
        return b"x" * 1000


class TestMedir(unittest.TestCase):
    def test_arp_macos(self):
        self.assertEqual(medir.parse_arp([ARP_MAC]),
                         {"aa:bb:cc:dd:ee:ff": "192.168.1.1", "00:1a:2b:3c:4d:5e": "192.168.1.5"})

    def test_arp_linux(self):
        self.assertEqual(medir.parse_arp([NEIGH]),
                         {"aa:bb:cc:dd:ee:ff": "192.168.1.1", "11:22:33:44:55:66": "192.168.1.7"})

    def test_arp_windows(self):
        self.assertEqual(medir.parse_arp([ARP_WIN]),
                         {"aa:bb:cc:dd:ee:ff": "192.168.1.1", "11:22:33:44:55:66": "192.168.1.20"})

    def test_ping_windows_espanol(self):
        self.assertEqual(medir.parse_ping(PING_ES), ([3.0, 1.0], 64))

    def test_ping_windows_ingles(self):
        self.assertEqual(medir.parse_ping(PING_EN), ([12.0], 118))

    def test_ping_unix(self):
        self.assertEqual(medir.parse_ping("64 bytes from x: icmp_seq=0 ttl=57 time=11.2 ms"), ([11.2], 57))


class TestSonda(unittest.TestCase):
    def crear(self, **kw):
        self.m = MedidorFalso()
        self.envios = []
        self.estado = 200

        def http(url, cuerpo, cabeceras):
            self.envios.append((url, json.loads(cuerpo), cabeceras))
            return self.estado

        return Sonda("http://panel:8770/", "tok", "lenovo", medidor=self.m, reloj=lambda: 1000.0,
                     enviar_http=http, **kw)

    def test_sondeo_con_gateway(self):
        s = self.crear()
        r = s.sondeo()
        self.assertEqual(r["t"], "sondeo")
        self.assertEqual(r["ts"], 1000)
        self.assertEqual(r["gateway"], "192.168.1.1")
        self.assertEqual({(x["kind"], x["target"]) for x in r["resultados"]},
                         {(k, t) for k in ("ping", "dns") for t in ("gateway", "1.1.1.1", "8.8.8.8")})

    def test_sondeo_sin_gateway(self):
        s = self.crear()
        self.m.gw = None
        r = s.sondeo()
        self.assertIsNone(r["gateway"])
        self.assertEqual({x["target"] for x in r["resultados"]}, {"1.1.1.1", "8.8.8.8"})

    def test_escaneo_filtra_24_y_rdns_una_vez(self):
        s = self.crear()
        self.m.arp = {"aa:bb:cc:dd:ee:01": "192.168.1.10", "aa:bb:cc:dd:ee:02": "10.0.0.5"}
        r1 = s.escaneo()
        r2 = s.escaneo()
        self.assertEqual(r1["base"], "192.168.1")
        self.assertEqual(r1["propia"], "192.168.1.50")
        self.assertEqual(r1["equipos"], {"aa:bb:cc:dd:ee:01": {"ip": "192.168.1.10", "hostname": "host-10"}})
        self.assertEqual(r2["equipos"], r1["equipos"])
        self.assertEqual(self.m.rdns_llamadas, ["192.168.1.10"])

    def test_escaneo_sin_ip(self):
        s = self.crear()
        self.m.ip = None
        self.assertIsNone(s.escaneo())

    def test_calidad(self):
        s = self.crear()
        self.assertIsNone(s.calidad())
        self.m.arp = {"aa:bb:cc:dd:ee:01": "192.168.1.10"}
        s.escaneo()
        r = s.calidad()
        self.assertEqual(r["resultados"], [{"mac": "aa:bb:cc:dd:ee:01", "ip": "192.168.1.10", "ok": True, "ms": 2.0}])

    def test_velocidad_requiere_internet(self):
        s = self.crear()
        self.assertIsNone(s.velocidad())          # aún sin sondeo
        self.m.externos_ok = False
        s.sondeo()
        self.assertIsNone(s.velocidad())
        self.m.externos_ok = True
        s.sondeo()
        r = s.velocidad()
        self.assertEqual(r["t"], "velocidad")
        self.assertGreater(r["down"], 0)

    def test_ip_publica(self):
        s = self.crear()
        self.m.fetch = lambda url, timeout=10, data=None: b"1.2.3.4\n"
        self.assertEqual(s.ip_publica()["ip"], "1.2.3.4")

    def test_enviar_200_vacia_la_cola(self):
        s = self.crear()
        s.encolar({"t": "sondeo", "ts": 1})
        self.assertTrue(s.enviar())
        self.assertEqual(s.pendientes(), 0)
        url, cuerpo, cab = self.envios[0]
        self.assertEqual(url, "http://panel:8770/api/interno/red")
        self.assertEqual(cuerpo["sonda"], "lenovo")
        self.assertEqual(cuerpo["version"], 1)
        self.assertEqual(cuerpo["lecturas"], [{"t": "sondeo", "ts": 1}])
        self.assertEqual(cab["Authorization"], "Bearer tok")
        self.assertEqual(cab["Content-Type"], "application/json")

    def test_enviar_conserva_con_500_y_401(self):
        s = self.crear()
        s.encolar({"t": "sondeo", "ts": 1})
        for estado in (500, 401):
            self.estado = estado
            self.assertFalse(s.enviar())
            self.assertEqual(s.pendientes(), 1)

    def test_enviar_con_excepcion_conserva(self):
        s = Sonda("http://p", "t", "n", medidor=MedidorFalso(),
                  enviar_http=lambda *a: (_ for _ in ()).throw(OSError("sin red")))
        s.encolar({"t": "x", "ts": 1})
        self.assertFalse(s.enviar())
        self.assertEqual(s.pendientes(), 1)

    def test_lote_maximo(self):
        s = self.crear(lote=3)
        for i in range(5):
            s.encolar({"t": "sondeo", "ts": i})
        self.assertTrue(s.enviar())
        self.assertEqual(len(self.envios[0][1]["lecturas"]), 3)
        self.assertEqual(s.pendientes(), 2)

    def test_cola_tope_descarta_las_mas_viejas(self):
        s = self.crear(max_cola=3)
        for i in range(5):
            s.encolar({"t": "sondeo", "ts": i})
        s.enviar()
        self.assertEqual([x["ts"] for x in self.envios[0][1]["lecturas"]], [2, 3, 4])

    def test_tareas(self):
        s = self.crear()
        self.assertEqual([(n, c, r) for n, c, r, _ in s.tareas()],
                         [("sondeo", 5, 0), ("escaneo", 120, 0), ("calidad", 30, 10), ("ip_publica", 300, 0),
                          ("velocidad", 3600, 30), ("envio", 15, 3)])
        dict_t = {n: f for n, _, _, f in s.tareas()}
        dict_t["sondeo"]()
        self.assertEqual(s.pendientes(), 1)


if __name__ == "__main__":
    unittest.main()
