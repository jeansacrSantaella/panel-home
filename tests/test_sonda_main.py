"""Pruebas del arranque de la sonda (sonda/__main__.py): leer_env y main.

Sin red real ni esperas: Sonda se reemplaza por un falso que regresa enseguida.
"""
from __future__ import annotations

import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sonda.__main__ import leer_env, main


class LeerEnvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / ".env"

    def _escribir(self, texto):
        self.ruta.write_text(texto, encoding="utf-8")

    def test_no_pisa_variables_existentes(self):
        # Una variable que ya está en el entorno no se cambia ni se devuelve
        self._escribir("A=2\nB=3\n")
        env = {"A": "1"}
        cargadas = leer_env(self.ruta, env)
        self.assertEqual(env, {"A": "1", "B": "3"})
        self.assertEqual(cargadas, {"B": "3"})

    def test_ignora_lineas_vacias_y_comentarios(self):
        self._escribir("\n# comentario\n   \nX=uno\n  # otro comentario\n")
        env = {}
        self.assertEqual(leer_env(self.ruta, env), {"X": "uno"})
        self.assertEqual(env, {"X": "uno"})

    def test_quita_comillas_simples_y_dobles(self):
        self._escribir('DOBLE="uno"\nSIMPLE=\'dos\'\nSIN=tres\n')
        env = {}
        self.assertEqual(
            leer_env(self.ruta, env),
            {"DOBLE": "uno", "SIMPLE": "dos", "SIN": "tres"},
        )

    def test_devuelve_solo_las_cargadas(self):
        # Las que ya existían no aparecen en el resultado, aunque el archivo las traiga
        self._escribir("P=1\nQ=2\n")
        env = {"P": "viejo"}
        self.assertEqual(leer_env(self.ruta, env), {"Q": "2"})

    def test_archivo_inexistente_devuelve_vacio(self):
        env = {}
        self.assertEqual(leer_env(self.ruta.with_name("no_existe.env"), env), {})
        self.assertEqual(env, {})


class MainTests(unittest.TestCase):
    def setUp(self):
        # Entorno vacío en cada prueba para no depender del entorno real
        patcher = mock.patch.dict(os.environ, {}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_dir = Path(self.tmp.name)

        # main() configura logging.basicConfig: hay que cerrar sus handlers
        # y restaurar el nivel del logger raíz al terminar cada prueba
        raiz = logging.getLogger()
        nivel_previo = raiz.level
        self.addCleanup(raiz.setLevel, nivel_previo)
        self.addCleanup(self._cerrar_handlers_logging)

    def _cerrar_handlers_logging(self):
        raiz = logging.getLogger()
        for h in list(raiz.handlers):
            h.close()
            raiz.removeHandler(h)

    def _escribir_env(self, texto):
        ruta = self.tmp_dir / "test.env"
        ruta.write_text(texto, encoding="utf-8")
        return str(ruta)

    def test_token_del_env_arranca_con_0_y_registra_origen(self):
        env_path = self._escribir_env("RED_TOKEN=abc\n")
        log_path = str(self.tmp_dir / "sonda.log")
        with mock.patch("sonda.__main__.Sonda") as falso:
            falso.return_value.correr.return_value = None
            codigo = main(["--env", env_path, "--log", log_path])

        self.assertEqual(codigo, 0)
        # Sonda se construye con el panel por defecto y el token del .env
        args, _ = falso.call_args
        self.assertEqual(args[0], "http://127.0.0.1:8770")
        self.assertEqual(args[1], "abc")
        # El log existe y dice que el token vino del .env
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, encoding="utf-8") as f:
            self.assertIn("token_env: True", f.read())

    def test_entorno_gana_y_quita_barra_final_del_panel(self):
        # Con PANEL_URL en el entorno, gana el entorno; la / final se quita
        os.environ["PANEL_URL"] = "http://x:1/"
        os.environ["RED_TOKEN"] = "abc"
        env_path = str(self.tmp_dir / "no_existe.env")
        log_path = str(self.tmp_dir / "sonda.log")
        with mock.patch("sonda.__main__.Sonda") as falso:
            falso.return_value.correr.return_value = None
            codigo = main(["--env", env_path, "--log", log_path])

        self.assertEqual(codigo, 0)
        args, _ = falso.call_args
        self.assertEqual(args[0], "http://x:1")

    def test_sin_token_devuelve_2_sin_lanzar_aunque_no_haya_stderr(self):
        env_path = str(self.tmp_dir / "no_existe.env")
        log_path = str(self.tmp_dir / "sonda.log")
        with mock.patch("sonda.__main__.Sonda") as falso, mock.patch("sys.stderr", None):
            codigo = main(["--env", env_path, "--log", log_path])

        self.assertEqual(codigo, 2)
        # Sin token nunca se construye la sonda
        falso.assert_not_called()


if __name__ == "__main__":
    unittest.main()
