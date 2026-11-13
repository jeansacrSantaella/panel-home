from __future__ import annotations

import unittest
from panel.db import Db
from panel.clima import Clima, URL_IP

RESPUESTA_IP = '{"latitude": 19.43, "longitude": -99.13, "city": "Ciudad de México", "region": "CDMX"}'.encode("utf-8")
RESPUESTA_IP_ERROR = b'{"error": true}'

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

class TestClimaUbicacion(unittest.TestCase):
    def setUp(self):
        self.db = Db(":memory:")

    def test_ubicacion_ip_cache_y_tiempos(self):
        tiempo_actual = 1000000
        def reloj_falso():
            return tiempo_actual

        llamadas_ip = [0]
        def fetch_falso(url, timeout=10):
            if url == URL_IP:
                llamadas_ip[0] += 1
                return RESPUESTA_IP
            return RESPUESTA_PRONOSTICO

        c = Clima(self.db, fetch=fetch_falso, reloj=reloj_falso)
        self.assertEqual(c.origen, "ip")

        # Primera llamada usa URL_IP y guarda
        ubic = c.ubicacion()
        self.assertEqual(ubic, (19.43, -99.13, "Ciudad de México, CDMX"))
        self.assertEqual(llamadas_ip[0], 1)

        # Segunda llamada dentro de 24 h no vuelve a consultar ipapi
        tiempo_actual += 3600 # 1 hora después
        ubic2 = c.ubicacion()
        self.assertEqual(ubic2, (19.43, -99.13, "Ciudad de México, CDMX"))
        self.assertEqual(llamadas_ip[0], 1)

        # Pasadas 25 h sí vuelve a consultar ipapi
        tiempo_actual += 25 * 3600 # 25 horas después de la original
        ubic3 = c.ubicacion()
        self.assertEqual(ubic3, (19.43, -99.13, "Ciudad de México, CDMX"))
        self.assertEqual(llamadas_ip[0], 2)

    def test_ipapi_error(self):
        def fetch_error_ip(url, timeout=10):
            if url == URL_IP:
                return RESPUESTA_IP_ERROR
            return RESPUESTA_PRONOSTICO

        c = Clima(self.db, fetch=fetch_error_ip)
        ubic = c.ubicacion()
        self.assertIsNone(ubic)
        self.assertIsNotNone(c.error)

    def test_origenes_y_datos_para(self):
        # Verificar orígenes correctos
        c_coord = Clima(self.db, lat=19.43, lon=-99.13)
        self.assertEqual(c_coord.origen, "coordenadas")

        c_ciudad = Clima(self.db, ciudad="Madrid")
        self.assertEqual(c_ciudad.origen, "ciudad")

        c_ip = Clima(self.db)
        self.assertEqual(c_ip.origen, "ip")

        # Probar datos_para con coordenadas
        llamadas_pronostico = [0]
        def fetch_falso(url, timeout=10):
            llamadas_pronostico[0] += 1
            return RESPUESTA_PRONOSTICO

        tiempo = 1000
        c = Clima(self.db, fetch=fetch_falso, reloj=lambda: tiempo)

        # Dos llamadas a coordenadas que redondean igual dentro de 15 min hacen UNA sola descarga
        res1 = c.datos_para(19.431, -99.132)
        self.assertEqual(res1["origen"], "dispositivo")
        self.assertEqual(res1["ciudad"], "Tu ubicación")
        self.assertEqual(llamadas_pronostico[0], 1)

        res2 = c.datos_para(19.434, -99.131) # Redondean a 19.43, -99.13
        self.assertEqual(llamadas_pronostico[0], 1)

        # Pasados 16 min otra descarga
        tiempo += 16 * 60
        res3 = c.datos_para(19.431, -99.132)
        self.assertEqual(llamadas_pronostico[0], 2)

    def test_coordenadas_fuera_de_rango(self):
        c = Clima(self.db)
        with self.assertRaises(ValueError):
            c.datos_para(95.0, -99.13)
        with self.assertRaises(ValueError):
            c.datos_para(19.43, -200.0)

    def test_fallo_red_en_datos_para(self):
        def fetch_error(url, timeout=10):
            raise RuntimeError("Red caída")

        c = Clima(self.db, fetch=fetch_error)
        res = c.datos_para(19.43, -99.13)
        self.assertIsNotNone(res["error"])
        self.assertIn("Red caída", res["error"])
