"""Pruebas de cuentas, sesiones y protección de rutas."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from panel import auth as A
from panel.config import cargar
from panel.db import Db
from panel.eventos import Recolector
from panel.web import crear_servidor


def nueva_auth():
    d = tempfile.mkdtemp()
    db = Db(Path(d) / "t.db")
    bloqueos = []
    return A.Auth(db, lambda ip, s: bloqueos.append((ip, s))), db, bloqueos


class TestContrasenas(unittest.TestCase):
    def test_hash_y_verificacion(self):
        h = A.hash_contrasena("secreta-123", iteraciones=1000)
        self.assertTrue(h.startswith("pbkdf2_sha256$1000$"))
        self.assertNotIn("secreta", h)
        self.assertTrue(A.verificar_contrasena("secreta-123", h))
        self.assertFalse(A.verificar_contrasena("secreta-124", h))
        self.assertFalse(A.verificar_contrasena("x", "basura"))
        self.assertNotEqual(A.hash_contrasena("igual"), A.hash_contrasena("igual"))  # sal distinta

    def test_validar_nueva(self):
        for mala in ("corta", "1234", "12345678", "aaaaaaaa", "Password"):
            with self.assertRaises(ValueError):
                A.validar_nueva(mala, "1234")
        with self.assertRaises(ValueError):
            A.validar_nueva("Orion-Casa-77", "Orion-Casa-77")
        A.validar_nueva("Orion-Casa-77", "1234")


class TestAuth(unittest.TestCase):
    def test_admin_inicial_y_cambio(self):
        a, db, _ = nueva_auth()
        self.assertTrue(a.asegurar_admin())
        self.assertFalse(a.asegurar_admin())
        r = a.entrar("admin", "1234", "1.1.1.1")
        self.assertTrue(r["debe_cambiar"])
        self.assertEqual(a.sesion(r["token"]), {"usuario": "admin", "debe_cambiar": True})
        # el token nunca se guarda en claro
        self.assertFalse(db._q("SELECT 1 FROM sesiones WHERE token = ?", (r["token"],)))
        otra = a.entrar("admin", "1234", "1.1.1.2")
        with self.assertRaises(ValueError):
            a.cambiar("admin", "mala", "Orion-Casa-77", r["token"])
        a.cambiar("admin", "1234", "Orion-Casa-77", r["token"])
        self.assertFalse(a.sesion(r["token"])["debe_cambiar"])
        self.assertIsNone(a.sesion(otra["token"]))  # las demás sesiones se cierran
        self.assertIsNone(a.entrar("admin", "1234", "1.1.1.1"))
        a.salir(r["token"])
        self.assertIsNone(a.sesion(r["token"]))

    def test_sesion_vence(self):
        a, _, _ = nueva_auth()
        a.asegurar_admin()
        r = a.entrar("admin", "1234", "ip", ahora=1000)
        self.assertIsNotNone(a.sesion(r["token"], ahora=1000 + A.DURACION_SESION - 1))
        self.assertIsNone(a.sesion(r["token"], ahora=1000 + A.DURACION_SESION + 1))
        self.assertIsNone(a.sesion(""))

    def test_bloqueo_por_ip(self):
        a, _, bloqueos = nueva_auth()
        a.asegurar_admin()
        for _ in range(4):
            self.assertIsNone(a.entrar("admin", "x", "9.9.9.9", ahora=100))
        with self.assertRaises(A.Bloqueado) as e:
            a.entrar("admin", "x", "9.9.9.9", ahora=100)
        self.assertEqual(e.exception.segundos, 60)
        self.assertEqual(bloqueos, [("9.9.9.9", 60)])
        with self.assertRaises(A.Bloqueado):  # ni con la buena mientras dure
            a.entrar("admin", "1234", "9.9.9.9", ahora=130)
        self.assertIsNotNone(a.entrar("admin", "1234", "8.8.8.8", ahora=130))  # otra ip sí
        self.assertIsNotNone(a.entrar("admin", "1234", "9.9.9.9", ahora=161))

    def test_restablecer_admin(self):
        a, _, _ = nueva_auth()
        a.asegurar_admin()
        r = a.entrar("admin", "1234", "ip")
        a.cambiar("admin", "1234", "Orion-Casa-77", r["token"])
        a.restablecer_admin()
        self.assertIsNone(a.sesion(r["token"]))
        self.assertTrue(a.entrar("admin", "1234", "ip")["debe_cambiar"])


class TestRutas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = tempfile.mkdtemp()
        cfg = cargar({"PANEL_DB": f"{d}/t.db", "NETWATCH_URL": "http://127.0.0.1:1", "CAMARAS_URL": "http://127.0.0.1:1",
                      "PANEL_HOST": "127.0.0.1", "PANEL_PORT": "0"})
        db = Db(cfg.db_path)
        cls.auth = A.Auth(db)
        cls.auth.asegurar_admin()
        cls.srv = crear_servidor(cfg, db, Recolector(cfg, db), cls.auth)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def pedir(self, ruta, datos=None, galleta=None, tipo="application/json", origen=None):
        req = urllib.request.Request(self.base + ruta, data=None if datos is None else json.dumps(datos).encode())
        if datos is not None:
            req.add_header("Content-Type", tipo)
        if galleta:
            req.add_header("Cookie", galleta)
        if origen:
            req.add_header("Origin", origen)

        class SinRedireccion(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        try:
            r = urllib.request.build_opener(SinRedireccion).open(req, timeout=5)
            return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_flujo(self):
        self.assertEqual(self.pedir("/")[0], 302)
        self.assertEqual(self.pedir("/api/panel")[0], 401)
        self.assertEqual(self.pedir("/login")[0], 200)
        self.assertEqual(self.pedir("/static/css/cuenta.css")[0], 200)
        st, h, cuerpo = self.pedir("/api/login", {"usuario": "admin", "contrasena": "1234"})
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(cuerpo)["debe_cambiar"])
        galleta = h["Set-Cookie"].split(";")[0]
        self.assertIn("HttpOnly", h["Set-Cookie"])
        self.assertIn("SameSite=Strict", h["Set-Cookie"])
        self.assertEqual(self.pedir("/", galleta=galleta)[0], 200)
        self.assertEqual(self.pedir("/api/contrasena", {"actual": "1234", "nueva": "Orion-Casa-77"},
                                    galleta=galleta, origen="http://otro.sitio")[0], 403)
        self.assertEqual(self.pedir("/api/contrasena", {"actual": "1234"}, galleta=galleta, tipo="text/plain")[0], 415)
        self.assertEqual(self.pedir("/api/logout", {}, galleta=galleta)[0], 200)
        self.assertEqual(self.pedir("/api/sesion", galleta=galleta)[0], 401)


if __name__ == "__main__":
    unittest.main()
