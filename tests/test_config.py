from __future__ import annotations

from pathlib import Path
import unittest

from panel.config import ROOT, Config, cargar


class TestConfig(unittest.TestCase):

    def test_cargar_defectos(self):
        cfg = cargar({})
        self.assertFalse(cfg.camaras_internas)
        self.assertEqual(cfg.go2rtc_interno_url, "http://127.0.0.1:1984")
        self.assertEqual(cfg.admin_pin, "")
        self.assertEqual(cfg.max_camaras, 32)
        self.assertEqual(cfg.max_sesiones, 2)
        self.assertEqual(cfg.sesion_caduca, 60)
        self.assertEqual(cfg.vigilar_cada, 10)
        self.assertEqual(cfg.caida_tras, 45)
        self.assertEqual(cfg.onvif_timeout, 5.0)
        self.assertEqual(cfg.camaras_iniciales, "")
        self.assertEqual(cfg.camaras_data, ROOT / "data")

    def test_valores_validos_y_rstrip(self):
        env = {
            "CAMARAS_INTERNAS": "1",
            "GO2RTC_INTERNO_URL": "http://127.0.0.1:1984/",
            "ADMIN_PIN": "1234",
            "MAX_CAMARAS": "10",
            "MAX_SESIONES": "5",
            "SESION_CADUCA": "30",
            "VIGILAR_CADA": "15",
            "CAIDA_TRAS": "20",
            "ONVIF_TIMEOUT": "2.5",
            "CAMARAS": "cam1=192.168.1.5",
        }
        cfg = cargar(env)
        self.assertTrue(cfg.camaras_internas)
        self.assertEqual(cfg.go2rtc_interno_url, "http://127.0.0.1:1984")
        self.assertEqual(cfg.admin_pin, "1234")
        self.assertEqual(cfg.max_camaras, 10)
        self.assertEqual(cfg.max_sesiones, 5)
        self.assertEqual(cfg.sesion_caduca, 30)
        self.assertEqual(cfg.vigilar_cada, 15)
        self.assertEqual(cfg.caida_tras, 20)
        self.assertEqual(cfg.onvif_timeout, 2.5)
        self.assertEqual(cfg.camaras_iniciales, "cam1=192.168.1.5")

    def test_minimos(self):
        env = {
            "MAX_SESIONES": "0",
            "VIGILAR_CADA": "1",
            "ONVIF_TIMEOUT": "0.2",
        }
        cfg = cargar(env)
        self.assertEqual(cfg.max_sesiones, 1)
        self.assertEqual(cfg.vigilar_cada, 2)
        self.assertEqual(cfg.onvif_timeout, 1.0)

    def test_error_formato_entero(self):
        with self.assertRaises(ValueError) as ctx:
            cargar({"MAX_SESIONES": "x"})
        self.assertIn("MAX_SESIONES", str(ctx.exception))

    def test_booleano_variaciones(self):
        self.assertTrue(cargar({"CAMARAS_INTERNAS": "Sí"}).camaras_internas)
        self.assertTrue(cargar({"CAMARAS_INTERNAS": "si"}).camaras_internas)
        self.assertTrue(cargar({"CAMARAS_INTERNAS": "TRUE"}).camaras_internas)
        self.assertTrue(cargar({"CAMARAS_INTERNAS": "yes"}).camaras_internas)
        self.assertFalse(cargar({"CAMARAS_INTERNAS": "0"}).camaras_internas)
        self.assertFalse(cargar({"CAMARAS_INTERNAS": "no"}).camaras_internas)
