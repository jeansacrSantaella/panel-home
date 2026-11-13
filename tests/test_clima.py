from __future__ import annotations

import unittest
from panel.db import Db
from panel.clima import Clima, describir

RESPUESTA_GEO = b'{"results": [{"id": 3117735, "name": "Madrid", "latitude": 40.4165, "longitude": -3.70256, "admin1": "Comunidad de Madrid"}]}'

RESPUESTA_PRONOSTICO = b'''{
    "current": {
        "temperature_2m": 20.5,
        "apparent_temperature": 19.8,
        "relative_humidity_2m": 45,
        "weather_code": 0,
        "is_day": 1
    },
    "daily": {
        "time": ["2023-10-01", "2023-10-02", "2023-10-03", "2023-10-04", "2023-10-05"],
        "weather_code": [0, 1, 3, 61, 95],
        "temperature_2m_max": [22.0, 23.5, 19.0, 18.2, 21.0],
        "temperature_2m_min": [12.0, 13.0, 11.5, 10.0, 14.1]
    }
}'''

class TestClima(unittest.TestCase):
    def setUp(self):
        self.db = Db(":memory:")

    def test_describir(self):
        self.assertEqual(describir(0), ("Despejado", "sol"))
        self.assertEqual(describir(99), ("Tormenta con granizo fuerte", "tormenta"))
        self.assertEqual(describir(9999), ("—", "nubes"))
        self.assertEqual(describir(None), ("—", "nubes"))

    def test_con_lat_lon(self):
        llamadas = [0]
        def fetch_falso(url, timeout=10):
            llamadas[0] += 1
            return RESPUESTA_PRONOSTICO

        c = Clima(self.db, lat=40.4165, lon=-3.70256, fetch=fetch_falso)
        self.assertTrue(c.configurado)
        
        ok = c.actualizar()
        self.assertTrue(ok)
        
        d = c.datos()
        self.assertTrue(d["configurado"])
        self.assertIsNotNone(d["actual"])
        self.assertEqual(d["actual"]["temp"], 20.5)
        self.assertEqual(d["hoy"]["max"], 22.0)
        self.assertEqual(d["hoy"]["min"], 12.0)
        self.assertEqual(len(d["dias"]), 4)
        self.assertEqual(d["dias"][0]["dia"], "Lun") # 2023-10-02 fue Lunes

    def test_con_solo_ciudad(self):
        llamadas = 0
        def fetch_falso(url, timeout=10):
            nonlocal llamadas
            llamadas += 1
            if "geocoding" in url:
                return RESPUESTA_GEO
            return RESPUESTA_PRONOSTICO

        c = Clima(self.db, ciudad="Madrid", fetch=fetch_falso)
        self.assertTrue(c.configurado)
        
        # Primera actualización (geocodifica + pronóstico)
        ok = c.actualizar()
        self.assertTrue(ok)
        self.assertEqual(llamadas, 2)

        # Segunda actualización (debe usar caché de ubicación, solo pronóstico)
        ok2 = c.actualizar()
        self.assertTrue(ok2)
        self.assertEqual(llamadas, 3)

        # Cambiar ciudad debe volver a geocodificar
        c2 = Clima(self.db, ciudad="Barcelona", fetch=fetch_falso)
        ok3 = c2.actualizar()
        self.assertTrue(ok3)
        # 1 geocodificación de Barcelona + 1 pronóstico = 5 llamadas acumuladas
        self.assertEqual(llamadas, 5)

    def test_error_de_red(self):
        def fetch_error(url, timeout=10):
            raise RuntimeError("Fallo de red")

        c = Clima(self.db, lat=40.0, lon=-3.0, fetch=fetch_error)
        ok = c.actualizar()
        self.assertFalse(ok)
        
        d = c.datos()
        self.assertIsNotNone(d["error"])
        self.assertIn("Fallo de red", d["error"])

    def test_sin_configuracion(self):
        c = Clima(self.db)
        self.assertFalse(c.configurado)
        d = c.datos()
        self.assertFalse(d["configurado"])
