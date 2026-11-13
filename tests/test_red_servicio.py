"""Pruebas de la fachada Red (sonda -> estado -> resumen)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from panel.db import Db
from panel.red.servicio import Red

MAC = "aa:00:00:00:00:01"


class ServicioTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.t = 1_000_000
        self.red = Red(Db(":memory:"), Path(self.dir.name) / "oui.txt", reloj=lambda: self.t,
                       fetch=lambda url, timeout: b"")

    def _lote(self):
        ts = self.t
        return {"sonda": "lenovo", "version": 1, "enviado": ts, "lecturas": [
            {"t": "sondeo", "ts": ts - 5, "gateway": "192.168.1.1", "resultados": [
                {"kind": "ping", "target": "gateway", "ok": True, "ms": 2.0},
                {"kind": "ping", "target": "1.1.1.1", "ok": True, "ms": 12.0},
                {"kind": "dns", "target": "8.8.8.8", "ok": True, "ms": 20.0}]},
            {"t": "escaneo", "ts": ts - 4, "base": "192.168.1", "propia": "192.168.1.5",
             "equipos": {MAC: {"ip": "192.168.1.50", "hostname": "tv"}}},
            {"t": "calidad", "ts": ts - 3, "resultados": [{"mac": MAC, "ip": "192.168.1.50", "ok": True, "ms": 5.0}]},
            {"t": "ip_publica", "ts": ts - 2, "ip": "203.0.113.7"},
            {"t": "velocidad", "ts": ts - 1, "down": 300.0, "up": 50.0},
        ]}

    def test_recibir_y_resumen_vivo(self):
        self.assertIsNone(self.red.resumen_vivo())
        self.assertEqual(self.red.recibir(self._lote()), 5)
        r = self.red.resumen_vivo(self.t)
        self.assertEqual([d["mac"] for d in r["devices"]], [MAC])
        self.assertEqual(r["devices"][0]["q"]["avg"], 5.0)
        self.assertEqual(r["uptime"]["lan"], 100.0)
        self.assertEqual(r["public_ip"], "203.0.113.7")
        self.assertEqual(r["speed"][0]["down"], 300.0)
        self.assertIn("lan", r["checks"])

    def test_resumen_vivo_caduca(self):
        self.red.recibir(self._lote())
        self.assertIsNotNone(self.red.resumen_vivo(self.t - 1 + 90))
        self.assertIsNone(self.red.resumen_vivo(self.t - 1 + 91))

    def test_cuerpo_invalido(self):
        for cuerpo in (None, [], {}, {"lecturas": "x"}):
            with self.subTest(cuerpo=cuerpo), self.assertRaises(ValueError):
                self.red.recibir(cuerpo)

    def test_tareas(self):
        ts = self.red.tareas()
        self.assertEqual([t.nombre for t in ts], ["red-fabricantes", "red-podar"])
        self.assertEqual([t.cada for t in ts], [7 * 86400, 86400])

    def test_sonda(self):
        self.assertIsNone(self.red.sonda())
        self.red.recibir(self._lote())
        s = self.red.sonda()
        self.assertEqual((s["nombre"], s["visto"], s["lecturas"]), ("lenovo", self.t, 5))

    def test_alias_eventos_y_csv(self):
        self.red.recibir(self._lote())
        self.red.alias({"mac": MAC, "alias": "Sala"})
        self.red.network({"mac": MAC, "network": "Cable"})
        self.assertGreater(self.red.eventos({})["total"], 0)
        self.assertIn("Sala", self.red.csv())


if __name__ == "__main__":
    unittest.main()
