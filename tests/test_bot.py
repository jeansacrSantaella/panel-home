"""Pruebas del bot de Telegram con falsos; sin red."""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path

from panel.bot import Bot
from panel.camaras.grabaciones import Grabaciones
from panel.config import Config
from panel.db import Db


class Cliente:
    def __init__(self):
        self.textos, self.fotos, self.albumes = [], [], []

    def enviar_texto(self, t): self.textos.append(t)
    def enviar_foto(self, f, pie=""): self.fotos.append((f, pie))
    def enviar_album(self, a): self.albumes.append(a)


class Red:
    def resumen_vivo(self):
        return {"checks": {"wan": {"label": "Internet", "down_since": None},
                           "lan": {"label": "LAN", "down_since": None},
                           "dns": {"label": "DNS", "down_since": 5}}}


class Go2:
    def foto(self, cid): return None if cid == "roto" else b"img"


class Camaras:
    def __init__(self, grab):
        self.go2rtc, self.grabaciones = Go2(), grab

    def lista(self): return [{"id": "patio", "nombre": "Patio"}, {"id": "roto", "nombre": "Sótano"}]
    def salud(self):
        return {"go2rtc": True, "camaras": {"patio": {"nombre": "Patio", "estado": "ok"},
                                            "roto": {"nombre": "Sótano", "estado": "caida"}}}


class Luces:
    configurado = True
    def lista(self): return [{"id": "1", "nombre": "Sala", "encendida": True}, {"id": "2", "nombre": "Cuarto", "encendida": False}]
    def aplicar_todas(self, enc): self.apagado = not enc; return 2


class Habs:
    def resumen(self, luces): return [{"habitacion": "Sala", "encendidos": 1, "total": 2}]


class Rutinas:
    def lista(self): return [{"id": 7, "nombre": "Buenas noches"}]
    def ejecutar(self, i, origen): self.ejecutada = i; return {"ok": 2, "total": 2, "fallaron": []}


class PruebasBot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        hoy = time.strftime("%Y-%m-%d")
        (base / "fotos" / hoy).mkdir(parents=True)
        (base / "fotos" / hoy / "patio_00-00-01_person.jpg").write_bytes(b"x")
        self.db = Db(base / "p.db")
        self.db.agregar_evento({"ts": 1700000000, "fuente": "panel", "tipo": "x", "nivel": "info",
                                "titulo": "Algo pasó", "clave": "a"})
        self.cl, self.lu, self.ru = Cliente(), Luces(), Rutinas()
        cfg = Config(telegram_chat_id="42")
        self.bot = Bot(cfg, self.db, self.cl, Red(), Camaras(Grabaciones(base)), self.lu, Habs(), self.ru,
                       sistema=lambda: {"cpu": 12.0, "ram": {"total": 100, "usado": 40}, "temperatura": 50.0})

    def test_estado(self):
        t = self.bot.atender("/estado")
        for esperado in ("Internet: bien", "DNS de la red interna: caído", "Patio: ok", "Sótano: caida",
                         "Luces encendidas: 1 de 2", "CPU 12%", "RAM 40%"):
            self.assertIn(esperado, t)

    def test_foto(self):
        self.assertEqual(self.bot.atender("/foto patio"), "")
        self.assertEqual(self.cl.fotos, [(b"img", "Patio")])
        self.assertIn("Sin imagen de: Sótano", self.bot.atender("/foto sotano@bot".replace("@bot", "")) or "Sin imagen de: Sótano")
        self.assertIn("No encuentro", self.bot.atender("/foto nada"))
        self.cl.fotos.clear()
        self.assertIn("Sótano", self.bot.atender("/foto"))
        self.assertEqual(len(self.cl.fotos), 1)

    def test_eventos_y_ayuda(self):
        self.assertIn("Algo pasó", self.bot.atender("/eventos"))
        self.assertIn("/apagar", self.bot.atender("/ayuda"))
        self.assertIn("/ayuda", self.bot.atender("/raro"))

    def test_hoy(self):
        self.assertEqual(self.bot.atender("/hoy"), "")
        self.assertIn("Patio: 1 person", self.cl.textos[0])
        self.assertEqual(len(self.cl.albumes[0]), 1)

    def test_luces_apagar_rutina(self):
        self.assertIn("Sala: 1 de 2", self.bot.atender("/luces"))
        self.assertIn("2 de 2", self.bot.atender("/apagar"))
        self.assertTrue(self.lu.apagado)
        self.assertIn("2 de 2 focos", self.bot.atender("/rutina buenas NOCHES"))
        self.assertEqual(self.ru.ejecutada, 7)
        self.assertIn("No existe", self.bot.atender("/rutina zzz"))

    def test_chat_ajeno_ignorado(self):
        self.assertFalse(self.bot.procesar({"update_id": 1, "message": {"chat": {"id": 99}, "text": "/apagar"}}))
        self.assertFalse(hasattr(self.lu, "apagado"))
        self.assertEqual(self.cl.textos, [])
        self.assertTrue(self.bot.procesar({"update_id": 2, "message": {"chat": {"id": 42}, "text": "/ayuda"}}))
        self.assertIn("Comandos", self.cl.textos[0])
        self.assertEqual(self.bot._offset, 3)


if __name__ == "__main__":
    unittest.main()
