from __future__ import annotations

import sys
import os
import time
import tempfile
import shutil
import subprocess
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from detector import detector as det

class TestDetectorUtilidades(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_ruta_foto(self):
        t = time.mktime((2026, 3, 5, 14, 7, 9, 0, 0, -1))
        esperado = os.path.join("/x", "2026-03-05", "cam1_14-07-09_persona-perro.jpg")
        self.assertEqual(det.ruta_foto("/x", "cam1", t, ["persona", "perro"]), esperado)

    def test_parsear_camaras(self):
        self.assertIsNone(det.parsear_camaras({"id": "1"}))
        self.assertIsNone(det.parsear_camaras("string"))
        self.assertEqual(det.parsear_camaras([]), [])
        
        datos = [{"id": "cam1"}, {"sin_id": 2}, {"id": "cam2"}]
        self.assertEqual(det.parsear_camaras(datos), [{"id": "cam1"}, {"id": "cam2"}])

    def test_leer_camaras_ok(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"id": "cam1"}]
        mock_get = MagicMock(return_value=mock_resp)

        cache_viejo = [{"id": "vieja"}]
        res = det.leer_camaras(cache_viejo, get=mock_get, url="http://url/api", token="tok")

        self.assertEqual(res, [{"id": "cam1"}])
        mock_get.assert_called_once_with(
            "http://url/api",
            headers={"Authorization": "Bearer tok"},
            timeout=5
        )

    def test_leer_camaras_error(self):
        def get_error(url, headers, timeout):
            raise RuntimeError("error")

        cache_viejo = [{"id": "vieja"}]
        res = det.leer_camaras(cache_viejo, get=get_error, url="http://url/api", token="tok")
        self.assertEqual(res, cache_viejo)

    def test_leer_camaras_no_lista(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": "no autorizado"}
        mock_get = MagicMock(return_value=mock_resp)

        cache_viejo = [{"id": "vieja"}]
        res = det.leer_camaras(cache_viejo, get=mock_get, url="http://url/api", token="tok")
        self.assertEqual(res, cache_viejo)

    def test_limpiar(self):
        fotos = os.path.join(self.tmpdir, "fotos")
        clips = os.path.join(self.tmpdir, "clips")
        
        dir_viejo_fotos = os.path.join(fotos, "2020-01-01")
        dir_viejo_clips = os.path.join(clips, "2020-01-01")
        dir_nuevo_fotos = os.path.join(fotos, "hoy")
        
        os.makedirs(dir_viejo_fotos)
        os.makedirs(dir_viejo_clips)
        os.makedirs(dir_nuevo_fotos)
        
        viejo_f = os.path.join(dir_viejo_fotos, "viejo.jpg")
        viejo_c = os.path.join(dir_viejo_clips, "viejo.mp4")
        nuevo_f = os.path.join(dir_nuevo_fotos, "nuevo.jpg")
        
        for p in (viejo_f, viejo_c, nuevo_f):
            with open(p, "w") as f:
                f.write("test")
                
        # Poner mtime antiguo a los archivos viejos (hace 48h)
        antiguo_t = time.time() - 48 * 3600
        os.utime(viejo_f, (antiguo_t, antiguo_t))
        os.utime(viejo_c, (antiguo_t, antiguo_t))
        
        det.limpiar(bases=[fotos, clips], horas=24)
        
        self.assertFalse(os.path.exists(viejo_f))
        self.assertFalse(os.path.exists(viejo_c))
        self.assertFalse(os.path.exists(dir_viejo_fotos))
        self.assertFalse(os.path.exists(dir_viejo_clips))
        
        self.assertTrue(os.path.exists(nuevo_f))
        self.assertTrue(os.path.exists(dir_nuevo_fotos))

    def test_fotos_entre(self):
        base = os.path.join(self.tmpdir, "fotos")
        sub = os.path.join(base, "2026-03-05")
        os.makedirs(sub)
        
        p1 = os.path.join(sub, "cam1_10-00-00_persona.jpg")
        p2 = os.path.join(sub, "cam2_11-00-00_perro-carro.jpg")
        
        for p in (p1, p2):
            with open(p, "w") as f:
                f.write("test")
                
        t0 = 1000000.0
        os.utime(p1, (t0 + 10, t0 + 10))
        os.utime(p2, (t0 + 20, t0 + 20))
        
        resultado = det.fotos_entre(t0 + 5, t0 + 15, base=base)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["cid"], "cam1")
        self.assertEqual(resultado[0]["clases"], ["persona"])
        self.assertEqual(resultado[0]["path"], p1)
        
        resultado2 = det.fotos_entre(t0 + 15, t0 + 25, base=base)
        self.assertEqual(len(resultado2), 1)
        self.assertEqual(resultado2[0]["cid"], "cam2")
        self.assertEqual(resultado2[0]["clases"], ["perro", "carro"])
        self.assertEqual(resultado2[0]["path"], p2)

    def test_modulo_sin_pesados(self):
        cmd = [sys.executable, "-c", "import detector.detector"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)

