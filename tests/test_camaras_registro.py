from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from panel.camaras.registro import CamaraError, Registro, fuente_rtsp, publica
from panel.db import Db


class RegistroTest(unittest.TestCase):
    def setUp(self):
        self.db = Db(":memory:")
        self.reg = Registro(self.db)

    def ids(self):
        return [c["id"] for c in self.reg.lista()]

    def test_siembra_con_iniciales(self):
        reg = Registro(Db(":memory:"), iniciales="camara1=192.168.1.69,camara2=192.168.1.72")
        self.assertEqual(["camara1", "camara2"], [c["id"] for c in reg.lista()])
        self.assertEqual(["192.168.1.69", "192.168.1.72"], [c["ip"] for c in reg.lista()])

    def test_no_siembra_si_ya_hay_camaras(self):
        self.reg.agregar("192.168.1.10")
        reg = Registro(self.db, iniciales="camara1=192.168.1.69")
        self.assertEqual(["192.168.1.10"], [c["ip"] for c in reg.lista()])

    def test_agregar_una_ip_con_nombre(self):
        res = self.reg.agregar("192.168.1.10", nombre="  Patio  ")
        self.assertEqual([], res["omitidas"])
        self.assertEqual("camara1", res["agregadas"][0]["id"])
        self.assertEqual("Patio", res["agregadas"][0]["nombre"])
        self.assertEqual("/live/ch00_0", res["agregadas"][0]["ruta_rtsp"])

    def test_varias_ips_tienen_etiquetas_numeradas(self):
        res = self.reg.agregar("192.168.1.10, 192.168.1.11;192.168.1.12", nombre="Garaje")
        self.assertEqual(["Garaje 1", "Garaje 2", "Garaje 3"], [c["nombre"] for c in res["agregadas"]])
        self.assertEqual(["camara1", "camara2", "camara3"], self.ids())

    def test_ip_repetida_se_omite(self):
        self.reg.agregar("192.168.1.10")
        res = self.reg.agregar("192.168.1.10 192.168.1.20")
        self.assertEqual(["192.168.1.10"], res["omitidas"])
        self.assertEqual(["192.168.1.20"], [c["ip"] for c in res["agregadas"]])

    def test_ip_publica_o_invalida_da_422(self):
        for txt in ("8.8.8.8", "abc"):
            with self.subTest(ip=txt), self.assertRaises(CamaraError) as cm:
                self.reg.agregar(txt)
            self.assertEqual(422, cm.exception.codigo)
        self.assertEqual([], self.ids())

    def test_ruta_sin_barra_da_422(self):
        with self.assertRaises(CamaraError) as cm:
            self.reg.agregar("192.168.1.10", ruta_rtsp="sin/barra")
        self.assertEqual(422, cm.exception.codigo)

    def test_limite_max_camaras(self):
        reg = Registro(Db(":memory:"), max_camaras=2)
        reg.agregar("192.168.1.1,192.168.1.2")
        with self.assertRaises(CamaraError) as cm:
            reg.agregar("192.168.1.3")
        self.assertEqual(422, cm.exception.codigo)
        self.assertEqual(2, len(reg.lista()))

    def test_publicas_no_tienen_clave(self):
        self.reg.agregar("192.168.1.10", usuario="admin", clave="secreta")
        self.reg.agregar("192.168.1.11")
        pub = self.reg.publicas()
        self.assertNotIn("clave", pub[0])
        self.assertTrue(all("secreta" not in str(p.values()) for p in pub))
        self.assertEqual([True, False], [p["tiene_clave"] for p in pub])
        self.assertEqual(publica(self.reg.lista()[0])["tiene_clave"], True)

    def test_fuente_rtsp_escapa_credenciales(self):
        c = {"usuario": "a b", "clave": "p@ss", "ip": "192.168.1.5", "puerto_rtsp": 554,
             "ruta_rtsp": "/live/ch00_0"}
        self.assertEqual("ffmpeg:rtsp://a%20b:p%40ss@192.168.1.5:554/live/ch00_0#video=h264#audio=aac",
                         fuente_rtsp(c))

    def test_quitar_existente_y_no_existente(self):
        self.reg.agregar("192.168.1.10")
        self.reg.quitar("camara1")
        self.assertEqual([], self.ids())
        with self.assertRaises(CamaraError) as cm:
            self.reg.quitar("camara1")
        self.assertEqual(404, cm.exception.codigo)

    def test_importar_json_conserva_ids_y_no_duplica(self):
        datos = {"camaras": [{"id": "camara7", "nombre": "Entrada", "ip": "192.168.1.50", "puerto_rtsp": 554,
                              "ruta_rtsp": "/live/ch00_0", "puerto_onvif": 8899, "usuario": "u", "clave": "k"}]}
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "cameras.json"
            ruta.write_text(json.dumps(datos), encoding="utf-8")
            self.assertEqual(1, self.reg.importar_json(ruta))
            self.assertEqual(0, self.reg.importar_json(ruta))
        self.assertEqual(["camara7"], self.ids())
        self.assertEqual("k", self.reg.una("camara7")["clave"])

    def test_importar_archivo_inexistente_da_cero(self):
        self.assertEqual(0, self.reg.importar_json("/no/existe/cameras.json"))


if __name__ == "__main__":
    unittest.main()
