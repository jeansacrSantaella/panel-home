"""Pruebas de fabricantes, resumen y consultas de la red (con RedDb real en memoria)."""
from __future__ import annotations

import csv
import io
import tempfile
import time
import unittest
from pathlib import Path

from panel.db import Db
from panel.red import consultas
from panel.red.almacen import RedDb
from panel.red.fabricantes import Fabricantes, mac_privada
from panel.red.resumen import ResumenRed

OUI = ("AA-BB-CC   (hex)\t\tACME Corp\nAABBCC     (base 16)\t\tACME Corp\n"
       "11-22-33   (hex)\t\tFoo Inc\n")


class FabricantesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.ruta = Path(self.dir.name) / "oui.txt"

    def test_buscar(self):
        self.ruta.write_text(OUI)
        f = Fabricantes(self.ruta)
        self.assertEqual(f.buscar("aa:bb:cc:00:00:01"), "ACME Corp")
        self.assertEqual(f.buscar("11:22:33:44:55:66"), "Foo Inc")
        self.assertIsNone(f.buscar("00:00:00:00:00:00"))
        self.assertIsNone(f.buscar(None))

    def test_descargar_una_sola_vez(self):
        llamadas = []

        def fetch(url, timeout):
            llamadas.append(url)
            return OUI.encode()

        f = Fabricantes(self.ruta, fetch)
        self.assertIsNone(f.buscar("aa:bb:cc:00:00:01"))
        f.descargar()
        f.descargar()
        self.assertEqual(len(llamadas), 1)
        self.assertEqual(f.buscar("aa:bb:cc:00:00:01"), "ACME Corp")

    def test_descargar_error_no_lanza(self):
        def fetch(url, timeout):
            raise OSError("sin red")

        Fabricantes(self.ruta, fetch).descargar()
        self.assertFalse(self.ruta.exists())

    def test_mac_privada(self):
        self.assertTrue(mac_privada("da:00:00:00:00:01"))
        self.assertFalse(mac_privada("00:11:22:33:44:55"))


class ConsultasTest(unittest.TestCase):
    def setUp(self):
        self.red = RedDb(Db(":memory:"))
        dia = int(time.mktime(time.strptime("2026-01-10", "%Y-%m-%d")))
        for i in range(30):
            self.red.agregar_evento(dia + i * 3600, "wan_down" if i % 2 else "new_device", f"e{i}")

    def test_paginas_y_filtros(self):
        p = consultas.pagina_eventos(self.red, {"size": "10", "page": "2"})
        self.assertEqual((p["total"], p["pages"], p["page"], len(p["events"])), (30, 3, 2, 10))
        dia = consultas.pagina_eventos(self.red, {"from": ["2026-01-10"], "to": ["2026-01-10"]})
        self.assertEqual(dia["total"], 24)
        self.assertEqual(consultas.pagina_eventos(self.red, {"kind": "wan_down"})["total"], 15)

    def test_validacion(self):
        for q in ({"size": "7"}, {"page": "x"}, {"page": "-1"}, {"from": "2026-13-01"},
                  {"from": "2026-01-11", "to": "2026-01-10"}):
            with self.subTest(q=q), self.assertRaises(ValueError):
                consultas.pagina_eventos(self.red, q)

    def test_edicion_de_equipos_limpia(self):
        self.red.agregar_equipo("aa", "1.1.1.1", None, False, 1)
        consultas.fijar_alias(self.red, {"mac": "aa", "alias": "  " + "x" * 80})
        consultas.fijar_red(self.red, {"mac": "aa", "network": "6 GHz"})
        d = self.red.equipo("aa")
        self.assertEqual(len(d["alias"]), 60)
        self.assertIsNone(d["network"])
        consultas.fijar_red(self.red, {"mac": "aa", "network": "Cable"})
        self.assertEqual(self.red.equipo("aa")["network"], "Cable")
        with self.assertRaises(KeyError):
            consultas.fijar_alias(self.red, {"alias": "x"})


class ResumenTest(unittest.TestCase):
    def setUp(self):
        self.red = RedDb(Db(":memory:"))
        self.ahora = int(time.time())
        self.estado = {"lan": {"label": "Red local", "down_since": None}}

    def _resumen(self):
        return ResumenRed(self.red, lambda mac: "ACME", lambda: self.estado, {"down": 0, "up": 0}).construir()

    def test_forma_del_resumen(self):
        n = self.ahora
        self.red.agregar_equipo("aa:00:00:00:00:01", "192.168.1.10", None, False, n)
        self.red.agregar_sondeos([(n - 10, "ping", "gateway", True, 2.0),
                                  (n - 10, "dev", "aa:00:00:00:00:01", True, 4.0)])
        d = self._resumen()
        self.assertEqual(set(d), {"now", "checks", "ribbon_start", "ribbon", "uptime", "series", "hours",
                                  "devices", "events", "quality", "speed", "contracted", "public_ip"})
        self.assertEqual(d["checks"], self.estado)
        self.assertEqual(len(d["ribbon"]["lan"]), 144)
        self.assertEqual(d["uptime"]["lan"], 100.0)
        self.assertEqual(d["devices"][0]["q"]["avg"], 4.0)
        self.assertEqual(d["devices"][0]["vendor"], "ACME")
        self.assertEqual(d["quality"]["gateway"]["avg"], 2.0)

    def test_orden_y_caidas_de_equipos(self):
        n = self.ahora
        self.red.agregar_equipo("aa:00:00:00:00:02", "192.168.1.9", None, False, n)
        self.red.agregar_equipo("aa:00:00:00:00:01", "192.168.1.10", None, False, n)
        self.red.agregar_equipo("aa:00:00:00:00:03", "192.168.1.2", None, False, n)
        self.red.fijar_fallos("aa:00:00:00:00:03", 3, False)
        self.red.agregar_evento(n, "device_offline", "x (aa:00:00:00:00:03) se desconectó")
        devs = self._resumen()["devices"]
        self.assertEqual([x["ip"] for x in devs], ["192.168.1.9", "192.168.1.10", "192.168.1.2"])
        self.assertEqual(devs[2]["drops"], 1)

    def test_csv(self):
        n = self.ahora
        self.red.agregar_equipo("aa:00:00:00:00:01", "192.168.1.10", "tv", False, n)
        self.red.agregar_equipo("aa:00:00:00:00:02", "192.168.1.11", None, True, n)
        self.red.agregar_evento(n, "lan_down", "Red local sin respuesta")
        texto = consultas.exportar_csv(self._resumen(), self.red)
        self.assertTrue(texto.startswith("﻿# Resumen"))
        filas = list(csv.reader(io.StringIO(texto.lstrip("﻿"))))
        i = filas.index(["# Equipos"])
        self.assertEqual(filas[i + 1][0], "alias")
        self.assertEqual(filas[i + 2][4], "aa:00:00:00:00:01")
        self.assertEqual(filas[i + 3][4], "aa:00:00:00:00:02")
        self.assertEqual(filas[i + 4], [])
        self.assertIn(["# Eventos (hasta 5000, mas recientes primero)"], filas)


if __name__ == "__main__":
    unittest.main()
