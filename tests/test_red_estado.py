"""Pruebas de las reglas de la red (con una base falsa en memoria)."""
from __future__ import annotations

import unittest

from panel.red.estado import EstadoRed, formato_duracion, mac_privada


class RedFalsa:
    def __init__(self):
        self.eq, self.sondeos, self.eventos, self.vel, self.meta = {}, [], [], [], {}

    def equipo(self, mac):
        d = self.eq.get(mac)
        return dict(d) if d else None

    def equipos(self):
        return [dict(d) for d in self.eq.values()]

    def hay_equipos(self):
        return bool(self.eq)

    def agregar_equipo(self, mac, ip, hostname, random_mac, ts):
        self.eq[mac] = {"mac": mac, "ip": ip, "hostname": hostname, "alias": None, "random_mac": random_mac,
                        "first_seen": ts, "last_seen": ts, "online": 1, "misses": 0, "network": None}

    def marcar_visto(self, mac, ip, ts):
        self.eq[mac].update(ip=ip, last_seen=ts, online=1, misses=0)

    def fijar_fallos(self, mac, misses, online):
        self.eq[mac].update(misses=misses, online=int(online))

    def agregar_sondeos(self, filas):
        self.sondeos.extend(filas)

    def podar_sondeos(self, antes):
        self.sondeos = [f for f in self.sondeos if f[0] >= antes]

    def agregar_evento(self, ts, kind, detail):
        self.eventos.append((ts, kind, detail))

    def agregar_velocidad(self, ts, down, up):
        self.vel.append((ts, down, up))

    def get(self, clave, defecto=None):
        return self.meta.get(clave, defecto)

    def set(self, clave, valor):
        self.meta[clave] = valor


def sondeo(ts, wan=True, gw=True, dns=True, con_gw=True):
    r = []
    if con_gw:
        r += [{"kind": "ping", "target": "gateway", "ok": gw, "ms": 1.0 if gw else None}]
    for h in ("1.1.1.1", "8.8.8.8"):
        r += [{"kind": "ping", "target": h, "ok": wan, "ms": 9.0 if wan else None},
              {"kind": "dns", "target": h, "ok": dns, "ms": 20.0 if dns else None}]
    return {"t": "sondeo", "ts": ts, "gateway": "192.168.1.1" if con_gw else None, "resultados": r}


def escaneo(ts, equipos):
    return {"t": "escaneo", "ts": ts, "base": "192.168.1", "propia": "192.168.1.2",
            "equipos": {m: {"ip": ip, "hostname": h} for m, (ip, h) in equipos.items()}}


def tipos(red):
    return [e[1] for e in red.eventos]


class PruebasConectividad(unittest.TestCase):
    def setUp(self):
        self.red = RedFalsa()
        self.e = EstadoRed(self.red)

    def test_dos_fallos_no_caen_tres_si(self):
        self.e.procesar([sondeo(100, wan=False), sondeo(105, wan=False)])
        self.assertNotIn("wan_down", tipos(self.red))
        self.e.procesar([sondeo(110, wan=False)])
        self.assertIn("wan_down", tipos(self.red))
        self.assertEqual(self.e.servicios()["wan"]["down_since"], 100)
        self.assertFalse(self.e.internet_ok())

    def test_recuperacion_con_duracion(self):
        self.e.procesar([sondeo(100, wan=False, dns=False), sondeo(105, wan=False, dns=False),
                         sondeo(110, wan=False, dns=False), sondeo(165)])
        up = [e for e in self.red.eventos if e[1] == "wan_up"]
        self.assertEqual(len(up), 1)
        self.assertEqual(up[0][2], "Internet restablecida tras 1m 5s")
        self.assertTrue(self.e.internet_ok())

    def test_gateway_caido_no_culpa_a_internet_ni_dns(self):
        self.e.procesar([sondeo(100 + 5 * i, wan=False, gw=False, dns=False) for i in range(5)])
        self.assertEqual(tipos(self.red), ["lan_down"])
        s = self.e.servicios()
        self.assertIsNone(s["wan"]["down_since"])
        self.assertIsNone(s["dns"]["down_since"])

    def test_sin_gateway_lan_ok(self):
        self.e.procesar([sondeo(100 + 5 * i, con_gw=False) for i in range(4)])
        self.assertEqual(self.red.eventos, [])
        self.assertIsNone(self.e.servicios()["lan"]["down_since"])

    def test_dns_cae_con_internet(self):
        self.e.procesar([sondeo(100 + 5 * i, dns=False) for i in range(3)])
        self.assertEqual(tipos(self.red), ["dns_down"])

    def test_monitor_gap(self):
        self.e.procesar([sondeo(100), sondeo(120)])
        self.assertNotIn("monitor_gap", tipos(self.red))
        self.e.procesar([sondeo(141)])
        gap = [e for e in self.red.eventos if e[1] == "monitor_gap"]
        self.assertEqual(len(gap), 1)
        self.assertIn("21s", gap[0][2])

    def test_estado_sobrevive_a_nueva_instancia(self):
        self.e.procesar([sondeo(100, wan=False), sondeo(105, wan=False)])
        e2 = EstadoRed(self.red)
        e2.procesar([sondeo(110, wan=False)])
        self.assertEqual(e2.servicios()["wan"]["down_since"], 100)
        e3 = EstadoRed(self.red)
        self.assertEqual(e3.servicios()["wan"]["down_since"], 100)

    def test_guarda_sondeos_y_ultimo(self):
        self.e.procesar([sondeo(100)])
        self.assertEqual(len(self.red.sondeos), 5)
        self.assertEqual(self.red.get("ultimo_sondeo"), 100)
        self.assertEqual(self.e.ultima_lectura(), 100)

    def test_podar(self):
        self.e.procesar([sondeo(100)])
        self.e.podar(dias=1, ahora=100 + 86400 + 1)
        self.assertEqual(self.red.sondeos, [])


class PruebasEquipos(unittest.TestCase):
    def setUp(self):
        self.red = RedFalsa()
        self.e = EstadoRed(self.red, fabricante=lambda m: "Acme" if m.startswith("a0") else None)

    def test_flujo_completo(self):
        a, b = "a0:00:00:00:00:01", "a2:00:00:00:00:02"
        self.e.procesar([escaneo(100, {a: ("192.168.1.10", "pc")})])
        self.assertEqual(self.red.eventos, [])
        self.assertTrue(self.red.equipo(a))
        self.e.procesar([escaneo(220, {a: ("192.168.1.10", "pc"), b: ("192.168.1.11", None)})])
        nuevo = [e for e in self.red.eventos if e[1] == "new_device"]
        self.assertEqual(len(nuevo), 1)
        self.assertIn("Equipo nuevo: " + b + " en 192.168.1.11", nuevo[0][2])
        self.assertIn("MAC privada", nuevo[0][2])
        # b ausente 3 escaneos
        for i in range(3):
            self.e.procesar([escaneo(340 + 120 * i, {a: ("192.168.1.10", "pc")})])
        off = [e for e in self.red.eventos if e[1] == "device_offline"]
        self.assertEqual(len(off), 1)
        self.assertEqual(off[0][2], f"192.168.1.11 ({b}) se desconectó")
        # vuelve
        self.e.procesar([escaneo(800, {a: ("192.168.1.10", "pc"), b: ("192.168.1.11", None)})])
        self.assertIn("device_online", tipos(self.red))
        self.assertEqual(self.red.equipo(b)["online"], 1)

    def test_nuevo_con_fabricante(self):
        a, b = "a0:00:00:00:00:01", "a0:00:00:00:00:04"
        self.e.procesar([escaneo(100, {a: ("192.168.1.10", None)}),
                         escaneo(220, {a: ("192.168.1.10", None), b: ("192.168.1.12", "tv")})])
        d = [e for e in self.red.eventos if e[1] == "new_device"][0][2]
        self.assertEqual(d, f"Equipo nuevo: {b} en 192.168.1.12 (tv) · Acme")

    def test_base_con_equipos_avisa_en_primer_escaneo(self):
        self.red.agregar_equipo("a0:00:00:00:00:01", "192.168.1.10", None, False, 1)
        self.e.procesar([escaneo(100, {"a0:00:00:00:00:09": ("192.168.1.9", None)})])
        self.assertIn("new_device", tipos(self.red))

    def test_dos_perdidas_no_desconectan(self):
        a = "a0:00:00:00:00:01"
        self.e.procesar([escaneo(100, {a: ("192.168.1.10", None)}), escaneo(220, {}), escaneo(340, {})])
        self.assertNotIn("device_offline", tipos(self.red))


class PruebasVarias(unittest.TestCase):
    def setUp(self):
        self.red = RedFalsa()
        self.e = EstadoRed(self.red)

    def test_calidad(self):
        self.e.procesar([{"t": "calidad", "ts": 50, "resultados": [
            {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.5", "ok": True, "ms": 3.0}]}])
        self.assertEqual(self.red.sondeos, [(50, "dev", "aa:bb:cc:dd:ee:ff", True, 3.0)])

    def test_ip_publica(self):
        self.e.procesar([{"t": "ip_publica", "ts": 1, "ip": "1.2.3.4"},
                         {"t": "ip_publica", "ts": 2, "ip": "1.2.3.4"},
                         {"t": "ip_publica", "ts": 3, "ip": "5.6.7.8"}])
        self.assertEqual(self.red.eventos, [(1, "ip_first", "IP pública inicial: 1.2.3.4"),
                                            (3, "ip_change", "IP pública cambió: 1.2.3.4 → 5.6.7.8")])
        self.assertEqual(self.red.get("ip_publica"), "5.6.7.8")

    def test_velocidad(self):
        self.e.procesar([{"t": "velocidad", "ts": 9, "down": 300.5, "up": 40.0}])
        self.assertEqual(self.red.vel, [(9, 300.5, 40.0)])

    def test_desordenadas_y_rotas(self):
        n = self.e.procesar([
            sondeo(110, wan=False), {"t": "raro", "ts": 5}, {"t": "calidad", "ts": 7},
            "basura", {"t": "sondeo"}, sondeo(100, wan=False), sondeo(105, wan=False)])
        self.assertEqual(n, 3)
        self.assertEqual(self.e.servicios()["wan"]["down_since"], 100)
        self.assertEqual(self.e.ultima_lectura(), 110)

    def test_utilidades(self):
        self.assertEqual([formato_duracion(45), formato_duracion(303), formato_duracion(7440)],
                         ["45s", "5m 3s", "2h 4m"])
        self.assertTrue(mac_privada("da:a1:19:00:00:00"))
        self.assertFalse(mac_privada("a0:00:00:00:00:00"))


if __name__ == "__main__":
    unittest.main()
