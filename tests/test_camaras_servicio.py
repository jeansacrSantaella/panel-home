"""Fachada Camaras con go2rtc, PTZ y sesiones falsos."""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

from panel.camaras.registro import CamaraError
from panel.camaras.servicio import Camaras
from panel.config import Config, cargar
from panel.db import Db


class Go2rtcFalso:
    def __init__(self):
        self.registradas, self.quitadas = {}, []

    def streams(self):
        return {k: {} for k in self.registradas}

    def registrar(self, cid, fuente):
        self.registradas[cid] = fuente
        return True

    def quitar(self, cid):
        self.quitadas.append(cid)
        self.registradas.pop(cid, None)


class PtzFalso:
    def __init__(self):
        self.olvidadas = []

    def olvidar(self, cid):
        self.olvidadas.append(cid)


class SesionesFalsas:
    pass


class TestServicio(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = Config(camaras_internas=True, camaras_data=Path(self.tmp.name), admin_pin="1234")
        self.go, self.ptz, self.eventos = Go2rtcFalso(), PtzFalso(), []
        self.c = Camaras(self.cfg, Db(":memory:"), self.eventos.append, ptz=self.ptz,
                         sesiones=SesionesFalsas(), go2rtc=self.go)

    def test_agregar_registra_en_go2rtc_y_no_expone_clave(self):
        r = self.c.agregar({"ips": "192.168.1.50", "nombre": "Patio", "usuario": "u", "clave": "secreta"})
        self.assertEqual(r["omitidas"], [])
        self.assertEqual(len(r["agregadas"]), 1)
        self.assertNotIn("clave", r["agregadas"][0])
        self.assertTrue(r["agregadas"][0]["tiene_clave"])
        cid = r["agregadas"][0]["id"]
        self.assertIn(cid, self.go.registradas)
        self.assertEqual(self.c.lista()[0]["nombre"], "Patio")
        self.assertTrue(self.c.agregar({"ips": "192.168.1.50"})["omitidas"])

    def test_agregar_valida(self):
        with self.assertRaises(CamaraError):
            self.c.agregar({"ips": "8.8.8.8"})
        with self.assertRaises(CamaraError):
            self.c.agregar({"ips": "192.168.1.5", "puerto_rtsp": "abc"})
        with self.assertRaises(CamaraError):
            self.c.agregar({"ips": 5})

    def test_quitar_limpia_go2rtc_y_ptz(self):
        cid = self.c.agregar({"ips": "192.168.1.51"})["agregadas"][0]["id"]
        self.c.quitar(cid)
        self.assertEqual(self.c.lista(), [])
        self.assertEqual(self.go.quitadas, [cid])
        self.assertEqual(self.ptz.olvidadas, [cid])
        with self.assertRaises(CamaraError) as e:
            self.c.quitar(cid)
        self.assertEqual(e.exception.codigo, 404)

    def test_admin(self):
        self.c.exigir_admin("1234")
        for malo in ("", "0000", None):
            with self.assertRaises(CamaraError) as e:
                self.c.exigir_admin(malo)
            self.assertEqual(e.exception.codigo, 401)
        sin_pin = Camaras(dataclasses.replace(self.cfg, admin_pin=""), Db(":memory:"), ptz=self.ptz,
                          sesiones=SesionesFalsas(), go2rtc=self.go)
        sin_pin.exigir_admin("lo que sea")

    def test_salud_tareas_y_espacio(self):
        self.c.agregar({"ips": "192.168.1.52"})
        self.assertIn("camaras", self.c.salud())
        self.assertEqual([t.nombre for t in self.c.tareas()], ["camaras-sincronizar", "camaras-vigilar"])
        esp = self.c.espacio()  # mide la carpeta local aunque FOTOS_REMOTAS esté activo
        self.assertIn("total", esp)

    def test_eventos_del_vigilante(self):
        self.c.vigilante._emitir("camara_caida", "alto", "x", "d", "c1")
        self.assertEqual(self.eventos[0]["tipo"], "camara_caida")


class TestConfigCamaras(unittest.TestCase):
    def test_avisar_y_token(self):
        cfg = cargar({"CAMARAS_INTERNAS": "1", "INTERNO_TOKEN": "t"})
        self.assertEqual(cfg.interno_token, "t")
        self.assertIn("camara_caida", cfg.avisar)
        self.assertIn("fuente_caida", cfg.avisar)
        self.assertNotIn("camara_caida", cargar({}).avisar)
        self.assertEqual(cargar({"CAMARAS_INTERNAS": "1", "PANEL_AVISAR": "x"}).avisar, frozenset({"x"}))
        both = cargar({"CAMARAS_INTERNAS": "1", "RED_INTERNA": "1"})
        self.assertIn("internet_caido", both.avisar)
        self.assertIn("go2rtc_volvio", both.avisar)


if __name__ == "__main__":
    unittest.main()
