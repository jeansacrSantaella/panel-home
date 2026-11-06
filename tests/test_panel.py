"""Pruebas unitarias para los módulos del panel de control."""

from __future__ import annotations

import dataclasses
from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from panel.avisos import Avisador
from panel.config import Config, cargar
from panel.db import Db
from panel import fuentes
from panel.eventos import Recolector
from panel.web import crear_servidor, estado_panel


class TestPanel(unittest.TestCase):
    """Casos de prueba para config, db, fuentes, eventos, avisos y web."""

    def tearDown(self) -> None:
        """Limpia el servidor web si fue iniciado durante las pruebas."""
        if hasattr(self, "server") and self.server:
            self.server.shutdown()
            self.server.server_close()
            if hasattr(self, "server_thread") and self.server_thread:
                self.server_thread.join()

    def test_config(self) -> None:
        """Prueba la función cargar() de la configuración."""
        cfg = cargar({})
        self.assertEqual(cfg.port, 8770)

        cfg_av = cargar({"PANEL_AVISAR": " internet_caido , movimiento "})
        self.assertEqual(cfg_av.avisar, frozenset({"internet_caido", "movimiento"}))

        with self.assertRaises(ValueError):
            cargar({"PANEL_PORT": "x"})

        cfg_url = cargar({"NETWATCH_URL": "http://127.0.0.1:8765/"})
        self.assertEqual(cfg_url.netwatch_url, "http://127.0.0.1:8765")

    def test_db(self) -> None:
        """Prueba inserción, filtrado, pendientes, consumo y estado en Db."""
        db = Db(":memory:")

        ev1 = {
            "ts": 100,
            "fuente": "red",
            "tipo": "internet_caido",
            "nivel": "alto",
            "titulo": "Internet caído",
            "detalle": "Error WAN",
            "ref": "",
            "clave": "c1",
            "avisado": 0,
        }
        self.assertTrue(db.agregar_evento(ev1))
        self.assertFalse(db.agregar_evento(ev1))
        self.assertEqual(len(db.eventos()), 1)

        ev2 = {
            "ts": 101,
            "fuente": "camaras",
            "tipo": "movimiento",
            "nivel": "medio",
            "titulo": "Movimiento",
            "detalle": "carro",
            "ref": "foto.jpg",
            "clave": "c2",
            "avisado": 0,
        }
        db.agregar_evento(ev2)
        evs_mov = db.eventos(tipos=["movimiento"])
        self.assertEqual(len(evs_mov), 1)
        self.assertEqual(evs_mov[0]["tipo"], "movimiento")

        pends = db.pendientes_aviso(tipos=["internet_caido", "movimiento"])
        self.assertEqual(len(pends), 2)
        id_ev1 = pends[0]["id"] if pends[0]["clave"] == "c1" else pends[1]["id"]
        db.marcar_avisado([id_ev1])
        pends_after = db.pendientes_aviso(tipos=["internet_caido"])
        self.assertEqual(len(pends_after), 0)

        t = 1000000
        db.guardar_consumo(t, {"router": (100, 10)})
        db.guardar_consumo(t + 60, {"router": (300, 30)})
        c = db.consumo(horas=24, ahora=t + 3600)
        self.assertEqual(c["router"]["rx"], 200)
        self.assertEqual(c["router"]["tx"], 20)

        db.guardar_consumo(t + 120, {"router": (50, 5)})
        c2 = db.consumo(horas=24, ahora=t + 3600)
        self.assertEqual(c2["router"]["rx"], 250)

        db.set("miclave", {"foo": "bar", "num": 42})
        self.assertEqual(db.get("miclave"), {"foo": "bar", "num": 42})

    def test_fuentes(self) -> None:
        """Prueba funciones de lectura de fotos, validación de ruta y comando de consumo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root_path = Path(tmpdir)
            cfg = dataclasses.replace(Config(), camaras_data=root_path)

            hoy = datetime.now().date()
            fecha_str = hoy.strftime("%Y-%m-%d")
            carpeta_dia = root_path / "fotos" / fecha_str
            carpeta_dia.mkdir(parents=True, exist_ok=True)

            dt_foto = datetime(hoy.year, hoy.month, hoy.day, 0, 0, 1)
            ts_foto = time.mktime(dt_foto.timetuple())
            (carpeta_dia / "camara1_00-00-01_carro.jpg").write_text("foto")
            (carpeta_dia / "invalido.jpg").write_text("no")

            ahora = ts_foto + 10
            desde_ts = ts_foto - 10
            fotos = fuentes.fotos_movimiento(cfg, desde_ts, ahora=ahora)
            self.assertEqual(len(fotos), 1)
            self.assertEqual(fotos[0]["camara"], "camara1")
            self.assertEqual(fotos[0]["clases"], ["carro"])

            self.assertIsNone(fuentes.ruta_foto(cfg, "../x.jpg"))
            ruta_valida = fuentes.ruta_foto(cfg, f"{fecha_str}/camara1_00-00-01_carro.jpg")
            self.assertIsNotNone(ruta_valida)

        cfg_cmd = dataclasses.replace(
            Config(), consumo_cmd="echo '{\"AA:BB\": {\"rx\": 5, \"tx\": 6}}'"
        )
        res = fuentes.leer_consumo(cfg_cmd)
        self.assertEqual(res, {"aa:bb": (5, 6)})

        cfg_fail = dataclasses.replace(Config(), consumo_cmd="exit 1")
        self.assertIsNone(fuentes.leer_consumo(cfg_fail))

    @patch("panel.fuentes.leer_consumo", return_value=None)
    @patch("panel.fuentes.fotos_movimiento", return_value=[])
    @patch("panel.fuentes.camaras_salud", return_value={"go2rtc": True, "camaras": {}})
    @patch("panel.fuentes.camaras_lista", return_value=[])
    @patch("panel.fuentes.netwatch_resumen")
    def test_eventos(self, mock_nw, mock_cl, mock_cs, mock_fm, mock_lc) -> None:
        """Prueba la generación de eventos en ciclos del recolector."""
        db = Db(":memory:")
        cfg = Config()
        recolector = Recolector(cfg, db)

        mock_nw.return_value = {"events": [{"ts": 100, "kind": "wan_down", "detail": "detalle"}]}
        recolector.ciclo(ahora=100)
        evs = db.eventos()
        self.assertGreater(len(evs), 0)
        for ev in evs:
            self.assertEqual(ev["avisado"], 1)

        mock_nw.return_value = {
            "events": [
                {"ts": 100, "kind": "wan_down", "detail": "detalle"},
                {"ts": 105, "kind": "wan_down", "detail": "caida2"},
            ]
        }
        recolector.ciclo(ahora=105)
        evs_segundo = db.eventos(desde=104)
        self.assertEqual(len(evs_segundo), 1)
        self.assertEqual(evs_segundo[0]["tipo"], "internet_caido")
        self.assertEqual(evs_segundo[0]["avisado"], 0)

        mock_cs.return_value = {
            "go2rtc": True,
            "camaras": {"c1": {"nombre": "Cam 1", "estado": "ok", "desde": 105}},
        }
        recolector.ciclo(ahora=106)
        mock_cs.return_value = {
            "go2rtc": True,
            "camaras": {"c1": {"nombre": "Cam 1", "estado": "sin_red", "desde": 110}},
        }
        recolector.ciclo(ahora=110)
        evs_cam = db.eventos(tipos=["camara_sin_red"])
        self.assertEqual(len(evs_cam), 1)

        mock_nw.return_value = None
        recolector.ciclo(ahora=115)
        evs_fc = db.eventos(tipos=["fuente_caida"])
        self.assertEqual(len(evs_fc), 1)

        mock_fm.return_value = [
            {"ts": 120, "camara": "c1", "clases": ["persona"], "ref": "2026-01-01/c1_12-00-00_persona.jpg"}
        ]
        recolector.ciclo(ahora=120)
        evs_mov = db.eventos(tipos=["movimiento"])
        self.assertEqual(len(evs_mov), 1)
        self.assertEqual(evs_mov[0]["ref"], "2026-01-01/c1_12-00-00_persona.jpg")

    @patch.object(Avisador, "_ntfy", return_value=True)
    @patch.object(Avisador, "_telegram_foto", return_value=True)
    @patch.object(Avisador, "_telegram_texto")
    def test_avisos(self, mock_tg_txt, mock_tg_foto, mock_ntfy) -> None:
        """Prueba el envío de avisos pendientes y formato de mensaje."""
        db = Db(":memory:")

        cfg_sin = Config(telegram_token="", telegram_chat_id="", ntfy_url="")
        avisador_sin = Avisador(cfg_sin, db)
        self.assertEqual(avisador_sin.enviar_pendientes(), 0)

        cfg_tg = Config(telegram_token="token", telegram_chat_id="chat", ntfy_url="",
                        avisar=frozenset({"internet_caido"}))
        avisador_tg = Avisador(cfg_tg, db)
        ahora = time.time()
        ev1 = {
            "ts": int(ahora - 10),
            "fuente": "red",
            "tipo": "internet_caido",
            "nivel": "alto",
            "titulo": "Caída de red",
            "detalle": "Sin conexion",
            "clave": "k1",
            "avisado": 0,
        }
        db.agregar_evento(ev1)
        mock_tg_txt.return_value = True

        enviados = avisador_tg.enviar_pendientes()
        self.assertEqual(enviados, 1)
        pends = db.pendientes_aviso(cfg_tg.avisar)
        self.assertEqual(len(pends), 0)

        ev2 = {
            "ts": int(ahora - 5),
            "fuente": "red",
            "tipo": "internet_caido",
            "nivel": "alto",
            "titulo": "Caída 2",
            "detalle": "Fallo",
            "clave": "k2",
            "avisado": 0,
        }
        db.agregar_evento(ev2)
        mock_tg_txt.return_value = False

        enviados_fallo = avisador_tg.enviar_pendientes()
        self.assertEqual(enviados_fallo, 0)
        pends_fallo = db.pendientes_aviso(cfg_tg.avisar)
        self.assertEqual(len(pends_fallo), 1)

        ev_viejo = {
            "ts": int(ahora - 90000),
            "fuente": "red",
            "tipo": "internet_caido",
            "nivel": "alto",
            "titulo": "Caída vieja",
            "detalle": "Antiguo",
            "clave": "kv",
            "avisado": 0,
        }
        db.agregar_evento(ev_viejo)
        mock_tg_txt.reset_mock()

        avisador_tg.enviar_pendientes()
        evs_viejos = db._q("SELECT * FROM eventos WHERE clave='kv'")
        self.assertEqual(evs_viejos[0]["avisado"], 2)

        txt = avisador_tg.texto(ev1)
        self.assertIn("Caída de red", txt)
        self.assertIn("Sin conexion", txt)

    def test_web(self) -> None:
        """Prueba estado_panel y las rutas HTTP del servidor de la API web."""
        class RecolectorFalso:
            def __init__(self) -> None:
                self.ultimo = {
                    "ts": 1000,
                    "netwatch": {
                        "devices": [
                            {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.10", "online": 1, "vendor": "VendorX"}
                        ]
                    },
                    "camaras": [{"id": "c1", "nombre": "Cam 1", "ip": "192.168.1.20"}],
                    "salud": {"camaras": {"c1": {"estado": "ok", "latencia_ms": 5}}, "go2rtc": True},
                }

        db = Db(":memory:")
        db.guardar_consumo(900, {"aa:bb:cc:dd:ee:ff": (100, 50)})
        db.guardar_consumo(960, {"aa:bb:cc:dd:ee:ff": (300, 150)})

        cfg = Config(host="127.0.0.1", port=0)
        recolector = RecolectorFalso()

        st = estado_panel(cfg, db, recolector, ahora=1000)
        self.assertEqual(len(st["equipos"]), 1)
        self.assertIsNotNone(st["equipos"][0]["consumo"])
        self.assertEqual(len(st["camaras"]), 1)
        self.assertEqual(st["camaras"][0]["estado"], "ok")

        self.server = crear_servidor(cfg, db, recolector)
        port = self.server.server_address[1]
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        base_url = f"http://127.0.0.1:{port}"

        req = urllib.request.Request(f"{base_url}/api/panel")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("equipos", data)

        req = urllib.request.Request(f"{base_url}/api/eventos?limite=5")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("eventos", data)

        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(f"{base_url}/api/eventos?limite=x")
        self.assertEqual(cm.exception.code, 400)

        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(f"{base_url}/static/../panel/db.py")
        self.assertEqual(cm.exception.code, 404)

        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(f"{base_url}/api/foto?ref=../x")
        self.assertEqual(cm.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
