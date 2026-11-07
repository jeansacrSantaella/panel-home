"""Pruebas unitarias para capturas remotas, locales, pestañas y avisos con fotos."""

from __future__ import annotations

import dataclasses
from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request

from panel.avisos import Avisador
from panel.config import ROOT, Config, cargar
from panel.db import Db
from panel import fuentes, web
from panel.web import capturas, crear_servidor, estado_panel



class SesionAbierta:
    """Auth falsa con sesión siempre válida: estas pruebas revisan las rutas; la seguridad va en test_auth.py."""

    def sesion(self, token):
        return {"usuario": "admin", "debe_cambiar": False}

class TestCapturas(unittest.TestCase):
    """Casos de prueba para capturas remotas, locales, API de pestañas y avisos."""

    def tearDown(self) -> None:
        """Limpia el servidor web si fue iniciado durante las pruebas."""
        if hasattr(self, "server") and self.server:
            self.server.shutdown()
            self.server.server_close()
            if hasattr(self, "server_thread") and self.server_thread:
                self.server_thread.join()

    def test_config_fotos_remotas(self) -> None:
        """Prueba la opción fotos_remotas en la configuración."""
        cfg_defecto = cargar({})
        self.assertFalse(cfg_defecto.fotos_remotas)

        cfg_remotas = cargar({"FOTOS_REMOTAS": "1"})
        self.assertTrue(cfg_remotas.fotos_remotas)

    @patch("panel.fuentes.get_json")
    def test_fuentes_remotas(self, mock_get_json: MagicMock) -> None:
        """Prueba funciones de fuentes remotas de capturas y filtrado por fecha o rango."""
        cfg = dataclasses.replace(Config(), fotos_remotas=True, camaras_url="http://x")

        # 1. capturas_del_dia con archivos remotos
        mock_get_json.return_value = [
            "camara1_08-19-01_carro.jpg",
            "malo.txt",
            "camara2_10-00-00_persona-perro.jpg",
        ]
        res = fuentes.capturas_del_dia(cfg, "2026-11-05")
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["camara"], "camara2")
        self.assertEqual(res[0]["clases"], ["persona", "perro"])
        self.assertEqual(res[0]["hora"], "10:00:00")
        self.assertEqual(res[0]["ref"], "2026-11-05/camara2_10-00-00_persona-perro.jpg")

        # 2. get_json lanza FuenteError -> capturas_del_dia devuelve None
        mock_get_json.side_effect = fuentes.FuenteError("error HTTP")
        self.assertIsNone(fuentes.capturas_del_dia(cfg, "2026-11-05"))
        mock_get_json.side_effect = None

        # 3. capturas_del_dia con fecha inválida lanza ValueError
        with self.assertRaises(ValueError):
            fuentes.capturas_del_dia(cfg, "ayer")

        # 4. dias_con_capturas filtra valores inválidos
        mock_get_json.return_value = ["2026-11-05", "x", 3]
        dias = fuentes.dias_con_capturas(cfg)
        self.assertEqual(dias, ["2026-11-05"])

        # 5. fotos_movimiento en rango especifico
        dt_ahora = datetime(2026, 11, 5, 12, 0)
        ahora = time.mktime(dt_ahora.timetuple())
        desde_ts = ahora - 3600
        mock_get_json.return_value = [
            "camara1_11-30-00_carro.jpg",
            "camara1_08-00-00_carro.jpg",
        ]
        movs = fuentes.fotos_movimiento(cfg, desde_ts, ahora=ahora)
        self.assertEqual(len(movs), 1)
        self.assertEqual(movs[0]["hora"], "11:30:00")

    @patch("panel.fuentes.urllib.request.urlopen")
    def test_leer_foto_remota(self, mock_urlopen: MagicMock) -> None:
        """Prueba la lectura remota de foto por HTTP y validación de referencias inválidas."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b"JPG"
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        cfg = dataclasses.replace(Config(), fotos_remotas=True, camaras_url="http://x")
        foto = fuentes.leer_foto(cfg, "2026-11-05/cam1_10-00-00_carro.jpg")
        self.assertEqual(foto, b"JPG")
        mock_urlopen.assert_called_once()

        mock_urlopen.reset_mock()
        foto_bad = fuentes.leer_foto(cfg, "../x.jpg")
        self.assertIsNone(foto_bad)
        mock_urlopen.assert_not_called()

    def test_leer_foto_local(self) -> None:
        """Prueba la lectura local de foto desde el sistema de archivos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root_path = Path(tmpdir)
            carpeta = root_path / "fotos" / "2026-11-05"
            carpeta.mkdir(parents=True, exist_ok=True)
            archivo = carpeta / "a_01-02-03_carro.jpg"
            archivo.write_bytes(b"abc")

            cfg = Config(camaras_data=root_path, fotos_remotas=False)
            res = fuentes.leer_foto(cfg, "2026-11-05/a_01-02-03_carro.jpg")
            self.assertEqual(res, b"abc")

    @patch("panel.fuentes.dias_con_capturas", return_value=["2026-11-05"])
    @patch("panel.fuentes.capturas_del_dia")
    def test_web_capturas(self, mock_cdd: MagicMock, mock_dias: MagicMock) -> None:
        """Prueba la función web.capturas y presencia de campos de URL en estado_panel."""
        class RecolectorFalso:
            ultimo = {"camaras": [{"id": "camara2", "nombre": "Patio"}]}

        cfg = Config()
        recolector = RecolectorFalso()

        # Respuesta normal de capturas
        mock_cdd.return_value = [
            {"ts": 100, "camara": "camara2", "ref": "2026-11-05/camara2_10-00-00_carro.jpg"}
        ]
        res = capturas(cfg, recolector, "2026-11-05")
        self.assertEqual(res["capturas"][0]["nombre_camara"], "Patio")
        self.assertIsNone(res["error"])

        # Cuando la fuente no responde (capturas_del_dia es None)
        mock_cdd.return_value = None
        res_error = capturas(cfg, recolector, "2026-11-05")
        self.assertEqual(res_error["capturas"], [])
        self.assertIsNotNone(res_error["error"])

        # Verificar presencia de camaras_url y netwatch_url en estado_panel
        db = Db(":memory:")
        st = estado_panel(cfg, db, recolector)
        self.assertIn("camaras_url", st)
        self.assertIn("netwatch_url", st)

    def test_web_http(self) -> None:
        """Prueba las rutas HTTP para capturas y archivos estáticos de pestañas."""
        class RecolectorFalso:
            ultimo = {
                "ts": 1000,
                "netwatch": {"devices": []},
                "camaras": [],
                "salud": {"camaras": {}, "go2rtc": True},
            }

        db = Db(":memory:")
        cfg = Config(host="127.0.0.1", port=0)
        recolector = RecolectorFalso()

        self.server = crear_servidor(cfg, db, recolector, SesionAbierta())
        port = self.server.server_address[1]
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        base_url = f"http://127.0.0.1:{port}"

        # Petición a fecha inválida en capturas -> 400
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(f"{base_url}/api/capturas?fecha=mal")
        self.assertEqual(cm.exception.code, 400)

        # Petición a archivo JS de pestañas -> 200
        pestanas_file = ROOT / "static" / "js" / "pestanas.js"
        creado_temporal = False
        if not pestanas_file.exists():
            pestanas_file.parent.mkdir(parents=True, exist_ok=True)
            pestanas_file.write_text("// test", encoding="utf-8")
            creado_temporal = True

        try:
            req = urllib.request.Request(f"{base_url}/static/js/pestanas.js")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            if creado_temporal and pestanas_file.exists():
                pestanas_file.unlink()

    @patch.object(Avisador, "_telegram_foto", return_value=True)
    @patch("panel.fuentes.leer_foto", return_value=b"JPG")
    def test_avisos_foto(self, mock_leer_foto: MagicMock, mock_tg_foto: MagicMock) -> None:
        """Prueba el envío de avisos de eventos de movimiento adjuntando fotos."""
        db = Db(":memory:")
        ev = {
            "ts": int(time.time()),
            "fuente": "camaras",
            "tipo": "movimiento",
            "nivel": "medio",
            "titulo": "Movimiento detectado",
            "detalle": "persona",
            "ref": "2026-11-05/camara1_10-00-00_persona.jpg",
            "clave": "mov1",
            "avisado": 0,
        }
        db.agregar_evento(ev)

        cfg = Config(
            telegram_token="tok",
            telegram_chat_id="chat",
            avisar=frozenset({"movimiento"}),
        )
        avisador = Avisador(cfg, db)

        enviados = avisador.enviar_pendientes()
        self.assertEqual(enviados, 1)

        texto_esperado = avisador.texto(ev)
        mock_tg_foto.assert_called_once_with(
            b"JPG", "camara1_10-00-00_persona.jpg", texto_esperado
        )


if __name__ == "__main__":
    unittest.main()
