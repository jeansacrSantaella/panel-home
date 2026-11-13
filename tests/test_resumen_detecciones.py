"""Pruebas del resumen de detecciones con un cliente de Telegram falso."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from panel.camaras.grabaciones import Grabaciones
from panel.config import Config
from panel.db import Db
from panel.resumen_detecciones import ResumenDetecciones
from panel.telegram import TelegramError


class Falso:
    def __init__(self, falla=False):
        self.textos, self.albumes, self.falla = [], [], falla

    def enviar_texto(self, t):
        if self.falla:
            raise TelegramError("sin red")
        self.textos.append(t)

    def enviar_album(self, fotos):
        self.albumes.append(fotos)


def ts(h, m=0):
    return datetime(2026, 11, 13, h, m).timestamp()


class PruebasResumen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        carpeta = Path(self.tmp.name) / "fotos" / "2026-11-13"
        carpeta.mkdir(parents=True)
        for nombre in ("patio_08-10-00_person.jpg", "patio_08-20-00_person-cat.jpg", "frente_09-00-00_car.jpg",
                       "patio_21-30-00_person.jpg", "patio_22-30-00_person.jpg"):
            (carpeta / nombre).write_bytes(b"jpg")
        self.db = Db(Path(self.tmp.name) / "p.db")
        self.cliente = Falso()
        self.r = ResumenDetecciones(Config(), Grabaciones(Path(self.tmp.name)),
                                    lambda: {"patio": "Patio"}, self.cliente, db=self.db)

    def test_toca_en_horas_pares_y_no_repite(self):
        self.assertFalse(self.r.toca(ts(9, 30)))     # primera vez solo marca el bloque (8:00)
        self.assertFalse(self.r.toca(ts(9, 59)))
        self.assertTrue(self.r.toca(ts(10, 0)))
        self.assertTrue(self.r.enviar(ts(10, 0)))
        self.assertFalse(self.r.toca(ts(11, 59)))
        self.assertTrue(self.r.toca(ts(12, 1)))
        # el último bloque queda en db: otra instancia tampoco repite
        otra = ResumenDetecciones(Config(), self.r.grabaciones, lambda: {}, self.cliente, db=self.db)
        self.assertFalse(otra.toca(ts(11, 0)))

    def test_texto_con_conteos(self):
        t = self.r.texto(ts(8), ts(10))
        self.assertIn("Detecciones de 08:00 a 10:00", t)
        self.assertIn("• Patio: 2 person, 1 cat", t)
        self.assertIn("• frente: 1 car", t)
        self.assertIn("Sin detecciones", self.r.texto(ts(14), ts(16)))

    def test_envia_texto_y_fotos_de_dia(self):
        self.assertTrue(self.r.enviar(ts(10, 0)))
        self.assertEqual(len(self.cliente.textos), 1)
        self.assertEqual(len(self.cliente.albumes), 1)
        self.assertEqual(len(self.cliente.albumes[0]), 3)

    def test_silencio_sin_fotos(self):
        self.assertTrue(self.r.en_silencio(ts(23, 30)))
        self.assertTrue(self.r.en_silencio(ts(3)))
        self.assertFalse(self.r.en_silencio(ts(7)))
        self.assertTrue(self.r.enviar(datetime(2026, 11, 14, 0, 5).timestamp()))    # resumen de 22:00 a 00:00
        self.assertEqual(self.cliente.albumes, [])
        self.assertIn("sin fotos", self.cliente.textos[0])
        self.assertIn("1 person", self.cliente.textos[0])

    def test_fallo_no_marca_para_reintentar(self):
        self.r.toca(ts(9))
        self.cliente.falla = True
        self.assertFalse(self.r.enviar(ts(10)))
        self.assertTrue(self.r.toca(ts(10, 1)))
        self.cliente.falla = False
        self.assertTrue(self.r.enviar(ts(10, 1)))
        self.assertFalse(self.r.toca(ts(10, 2)))


if __name__ == "__main__":
    unittest.main()
