from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from panel.db import Db
from panel.camaras.registro import Registro
from scripts.migrar_camaras import copiar_datos, main, migrar


class TestMigrarCamaras(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        self.panel_db_path = self.temp_path / "panel.db"
        self.cameras_json_path = self.temp_path / "cameras.json"

        # Crear un cameras.json de prueba con 2 cámaras
        self.datos_cameras = [
            {
                "id": "cam1",
                "nombre": "Cámara 1",
                "ip": "192.168.1.10",
                "puerto_rtsp": 554,
                "ruta_rtsp": "/stream1",
                "puerto_onvif": 80,
                "usuario": "admin",
                "clave": "1234",
            },
            {
                "id": "cam2",
                "nombre": "Cámara 2",
                "ip": "192.168.1.11",
                "puerto_rtsp": 554,
                "ruta_rtsp": "/stream2",
                "puerto_onvif": 80,
                "usuario": "admin",
                "clave": "1234",
            },
        ]
        with open(self.cameras_json_path, "w", encoding="utf-8") as f:
            json.dump({"camaras": self.datos_cameras}, f)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    def test_importar_cameras(self) -> None:
        """Verifica la importación de un cameras.json con 2 cámaras en base nueva."""
        res = migrar(self.cameras_json_path, self.panel_db_path)
        self.assertEqual(res["camaras"], 2)

        reg = Registro(Db(self.panel_db_path))
        camaras = reg.lista()
        self.assertEqual(len(camaras), 2)
        ids = {c["id"] for c in camaras}
        self.assertEqual(ids, {"cam1", "cam2"})

    def test_segunda_ejecucion_idempotente(self) -> None:
        """Verifica que la segunda ejecución del mismo archivo no duplica cámaras."""
        migrar(self.cameras_json_path, self.panel_db_path)
        res2 = migrar(self.cameras_json_path, self.panel_db_path)
        self.assertEqual(res2["camaras"], 0)

        reg = Registro(Db(self.panel_db_path))
        camaras = reg.lista()
        self.assertEqual(len(camaras), 2)

    def test_cameras_inexistente_main(self) -> None:
        """Verifica que main con ruta de cameras.json inexistente devuelva código 1."""
        no_existe = self.temp_path / "no_existe.json"
        with contextlib.redirect_stderr(io.StringIO()):
            code = main([str(no_existe), "--panel-db", str(self.panel_db_path)])
        self.assertEqual(code, 1)

    def test_copiar_datos(self) -> None:
        """Verifica la copia recursiva de fotos y clips sin sobrescribir existentes."""
        origen_datos = self.temp_path / "origen_datos"
        destino_datos = self.temp_path / "panel_data"

        # Crear estructura en origen
        foto_dir = origen_datos / "fotos" / "2026-11-01"
        foto_dir.mkdir(parents=True, exist_ok=True)
        foto_file = foto_dir / "a.jpg"
        foto_file.write_text("contenido original foto")

        clip_dir = origen_datos / "clips" / "2026-11-01"
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_file = clip_dir / "b.mp4"
        clip_file.write_text("contenido original clip")

        # Primera copia
        res1 = copiar_datos(origen_datos, destino_datos)
        self.assertEqual(res1["copiados"], 2)
        self.assertEqual(res1["existentes"], 0)
        self.assertEqual((destino_datos / "fotos" / "2026-11-01" / "a.jpg").read_text(), "contenido original foto")
        self.assertEqual((destino_datos / "clips" / "2026-11-01" / "b.mp4").read_text(), "contenido original clip")

        # Pre-crear un archivo en destino para probar que no se sobrescribe y se cuenta como existente
        foto_destino_existente = destino_datos / "fotos" / "2026-11-01" / "a.jpg"
        foto_destino_existente.write_text("contenido modificado destino")

        # Segunda copia
        res2 = copiar_datos(origen_datos, destino_datos)
        self.assertEqual(res2["copiados"], 0)  # foto y clip ya estaban en destino
        self.assertEqual(res2["existentes"], 2)
        self.assertEqual(foto_destino_existente.read_text(), "contenido modificado destino")

    def test_origen_sin_carpetas(self) -> None:
        """Verifica que un origen sin fotos ni clips devuelva ceros y no falle."""
        origen_vacio = self.temp_path / "origen_vacio"
        origen_vacio.mkdir()
        destino_datos = self.temp_path / "panel_data"

        res = copiar_datos(origen_vacio, destino_datos)
        self.assertEqual(res, {"copiados": 0, "existentes": 0})

    def test_origen_no_se_modifica(self) -> None:
        """Verifica que el origen no sea modificado (sigue existiendo con su contenido)."""
        origen_datos = self.temp_path / "origen_datos"
        foto_dir = origen_datos / "fotos" / "2026-11-01"
        foto_dir.mkdir(parents=True, exist_ok=True)
        foto_file = foto_dir / "a.jpg"
        foto_file.write_text("test")

        destino_datos = self.temp_path / "panel_data"
        copiar_datos(origen_datos, destino_datos)

        self.assertTrue(origen_datos.exists())
        self.assertTrue(foto_file.exists())
        self.assertEqual(foto_file.read_text(), "test")


if __name__ == "__main__":
    unittest.main()
