"""Abre cada pestaña del panel en Chrome headless y falla si hay errores de JavaScript."""
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "prueba_navegador.py"
sys.path.insert(0, str(RAIZ / "scripts"))
import prueba_navegador  # noqa: E402


@unittest.skipUnless(prueba_navegador.buscar_chrome(), "Chrome/Chromium no está instalado")
class TestNavegador(unittest.TestCase):
    def test_pestanas_sin_errores_js(self):
        try:
            r = subprocess.run([sys.executable, str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True, timeout=110)
        except subprocess.TimeoutExpired as e:
            self.fail(f"la prueba del navegador excedió 110 s\n{e.stdout or ''}")
        self.assertEqual(r.returncode, 0, f"\n{r.stdout}\n{r.stderr}")


if __name__ == "__main__":
    unittest.main()
