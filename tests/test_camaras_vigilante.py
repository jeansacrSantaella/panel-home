from __future__ import annotations

import unittest

from panel.camaras.vigilante import Vigilante, bytes_recibidos, duracion


class Reloj:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Go2rtcFalso:
    def __init__(self):
        self.datos = {}

    def streams(self):
        return self.datos


class Entorno:
    def __init__(self, **kw):
        self.reloj = Reloj()
        self.go = Go2rtcFalso()
        self.lat = 5
        self.camaras = [{"id": "c1", "nombre": "Sala", "ip": "10.0.0.2", "puerto_rtsp": 554}]
        self.eventos = []
        self.bytes = 0
        self.flujo()
        self.v = Vigilante(lambda: self.camaras, self.go, caida_tras=45, cada=10,
                           al_evento=self.eventos.append, probar_red=lambda ip, p: self.lat,
                           reloj=self.reloj, **kw)

    def flujo(self):
        self.go.datos = {"c1": {"producers": [{"bytes_recv": self.bytes}]}}

    def paso(self, seg=10, crece=True):
        self.reloj.t += seg
        if crece:
            self.bytes += 100
        self.flujo()
        self.v.revisar()

    def tipos(self):
        return [e["tipo"] for e in self.eventos]


class PruebasVigilante(unittest.TestCase):
    def test_auxiliares(self):
        self.assertEqual(duracion(12), "12 s")
        self.assertEqual(duracion(180), "3 min")
        self.assertEqual(duracion(3900), "1 h 5 min")
        self.assertEqual(bytes_recibidos({"producers": [{"bytes_recv": 7}, {"receivers": [{"bytes": 3}]}]}), 10)

    def test_estados(self):
        e = Entorno()
        e.paso()
        self.assertEqual(e.v.salud()["camaras"]["c1"]["estado"], "ok")
        e.paso(crece=False)
        self.assertEqual(e.v.salud()["camaras"]["c1"]["estado"], "sin_video")
        e.lat = None
        e.paso(crece=False)
        self.assertEqual(e.v.salud()["camaras"]["c1"]["estado"], "sin_red")
        self.assertIsNone(e.v.salud()["camaras"]["c1"]["latencia_ms"])

    def test_caida_y_vuelta(self):
        e = Entorno()
        e.paso()
        for _ in range(4):
            e.paso(10, crece=False)
        self.assertEqual(e.tipos(), [])
        e.paso(10, crece=False)
        self.assertEqual(e.tipos(), [])
        e.paso(10, crece=False)
        self.assertEqual(e.tipos(), ["camara_caida"])
        ev = e.eventos[0]
        self.assertEqual((ev["fuente"], ev["nivel"], ev["titulo"]), ("camaras", "alto", "Sala sin video"))
        self.assertTrue(ev["detalle"].startswith("IP 10.0.0.2. "))
        self.assertTrue(ev["clave"].startswith("vig:camara_caida:c1:"))
        e.paso(10, crece=False)
        self.assertEqual(e.tipos(), ["camara_caida"])
        e.paso(10)
        self.assertEqual(e.tipos(), ["camara_caida", "camara_volvio"])
        self.assertEqual(e.eventos[1]["nivel"], "info")
        self.assertEqual(e.eventos[1]["titulo"], "Sala volvió")
        self.assertEqual(e.eventos[1]["detalle"], "tras 1 min")
        self.assertEqual(e.v.salud()["camaras"]["c1"]["cortes_24h"], 1)
        e.paso(86401)
        self.assertEqual(e.v.salud()["camaras"]["c1"]["cortes_24h"], 0)

    def test_fallo_corto(self):
        e = Entorno()
        e.paso()
        e.paso(10, crece=False)
        e.paso(10, crece=False)
        e.paso(10)
        self.assertEqual(e.eventos, [])

    def test_go2rtc(self):
        e = Entorno()
        e.paso()
        e.go.streams = lambda: None
        e.reloj.t += 10
        e.v.revisar()
        self.assertFalse(e.v.salud()["go2rtc"])
        self.assertEqual(e.eventos, [])
        e.reloj.t += 50
        e.v.revisar()
        e.v.revisar()
        self.assertEqual(e.tipos(), ["go2rtc_sin_respuesta"])
        del e.go.streams
        e.paso()
        self.assertTrue(e.v.salud()["go2rtc"])
        self.assertEqual(e.tipos(), ["go2rtc_sin_respuesta", "go2rtc_volvio"])

    def test_go2rtc_corto_no_avisa_al_volver(self):
        e = Entorno()
        e.go.streams = lambda: None
        e.v.revisar()
        del e.go.streams
        e.paso()
        self.assertEqual(e.eventos, [])

    def test_suspension(self):
        e = Entorno()
        e.v.vuelta()
        e.reloj.t += 600
        e.flujo()
        e.v.vuelta()
        self.assertEqual(e.tipos(), ["servidor_suspendido"])
        self.assertEqual(e.eventos[0]["nivel"], "medio")
        self.assertIn("Unos 10 min sin vigilar", e.eventos[0]["detalle"])
        e.reloj.t += 10
        e.v.vuelta()
        self.assertEqual(len(e.eventos), 1)

    def test_camara_retirada(self):
        e = Entorno()
        e.paso()
        self.assertIn("c1", e.v.salud()["camaras"])
        e.camaras = []
        e.paso()
        self.assertEqual(e.v.salud()["camaras"], {})

    def test_al_evento_que_falla(self):
        e = Entorno()
        e.v._al_evento = lambda ev: 1 / 0
        e.paso()
        with self.assertLogs("panel.camaras", level="ERROR"):
            for _ in range(6):
                e.paso(10, crece=False)
        self.assertEqual(e.v.salud()["camaras"]["c1"]["cortes_24h"], 1)


if __name__ == "__main__":
    unittest.main()
