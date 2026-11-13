"""Rutas web de cámaras y grabaciones con el servidor real y sesión iniciada."""
from __future__ import annotations

import dataclasses
import http.client
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

from panel.camaras.servicio import Camaras
from panel.camaras.video import SinLugar
from panel.config import Config
from panel.db import Db
from panel.eventos import Recolector
from panel.web import crear_servidor


class SesionAbierta:
    def sesion(self, token):
        return {"usuario": "admin", "debe_cambiar": False}


class SinSesion:
    def sesion(self, token):
        return None


class Go2rtcFalso:
    def __init__(self):
        self.registradas = {}

    def streams(self):
        return {k: {} for k in self.registradas}

    def registrar(self, cid, fuente):
        self.registradas[cid] = fuente
        return True

    def quitar(self, cid):
        self.registradas.pop(cid, None)

    def foto(self, cid):
        return b"\xff\xd8JPEG"

    def script(self, nombre):
        if nombre != "video-rtc.js":
            raise ValueError(nombre)
        return b"// js"


class PtzFalso:
    def __init__(self):
        self.llamadas = []

    def mover(self, cid, x, y):
        self.llamadas.append(("mover", cid, x, y))

    def parar(self, cid):
        self.llamadas.append(("parar", cid))

    def olvidar(self, cid):
        pass


class SesionesFalsas:
    def __init__(self):
        self.abiertas = set()

    def abrir(self):
        if len(self.abiertas) >= 1:
            raise SinLugar([{"id": "x"}])
        self.abiertas.add("s1")
        return {"id": "s1", "maximo": 1}

    def latido(self, sid):
        return "ok" if sid in self.abiertas else "expulsada"

    def salir(self, sid):
        self.abiertas.discard(sid)

    def valida(self, sid):
        return sid in self.abiertas


class Base(unittest.TestCase):
    interno = True
    pin = "1234"
    token = "tok-detector"
    auth = SesionAbierta

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.cfg = Config(host="127.0.0.1", port=0, camaras_internas=self.interno, admin_pin=self.pin,
                          camaras_data=self.data, interno_token=self.token)
        db = Db(":memory:")
        self.ptz, self.ses = PtzFalso(), SesionesFalsas()
        self.camaras = Camaras(self.cfg, db, ptz=self.ptz, sesiones=self.ses, go2rtc=Go2rtcFalso()) \
            if self.interno else None
        self.srv = crear_servidor(self.cfg, db, Recolector(self.cfg, db), self.auth(), camaras=self.camaras)
        self.puerto = self.srv.server_address[1]
        self.hilo = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.hilo.start()
        self.addCleanup(self._parar)

    def _parar(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.hilo.join()

    def pedir(self, metodo, ruta, cuerpo=None, cab=None, crudo=False):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        cab = dict(cab or {})
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            cab["Content-Type"] = "application/json"
        con.request(metodo, ruta, datos, cab)
        r = con.getresponse()
        raw = r.read()
        con.close()
        if crudo:
            return r.status, raw, r
        try:
            return r.status, json.loads(raw), r
        except ValueError:
            return r.status, raw, r

    def poner(self, tipo, fecha, nombre, datos=b"0123456789"):
        d = self.data / tipo / fecha
        d.mkdir(parents=True, exist_ok=True)
        (d / nombre).write_bytes(datos)


class TestCamarasWeb(Base):
    def test_alta_lista_borrado_con_pin(self):
        adm = {"X-Admin": "1234"}
        self.assertEqual(self.pedir("POST", "/api/camaras", {"ips": "192.168.1.60"})[0], 401)
        self.assertEqual(self.pedir("POST", "/api/camaras", {"ips": "192.168.1.60"}, {"X-Admin": "mal"})[0], 401)
        st, d, _ = self.pedir("POST", "/api/camaras", {"ips": "192.168.1.60", "nombre": "Patio"}, adm)
        self.assertEqual(st, 200)
        cid = d["agregadas"][0]["id"]
        self.assertNotIn("clave", d["agregadas"][0])
        self.assertEqual(self.pedir("POST", "/api/camaras", {"ips": "8.8.8.8"}, adm)[0], 422)
        st, lista, _ = self.pedir("GET", "/api/camaras")
        self.assertEqual([c["id"] for c in lista], [cid])
        self.assertEqual(self.pedir("DELETE", f"/api/camaras/{cid}")[0], 401)
        self.assertEqual(self.pedir("DELETE", f"/api/camaras/{cid}", cab=adm)[0], 200)
        self.assertEqual(self.pedir("DELETE", f"/api/camaras/{cid}", cab=adm)[0], 404)
        d = self.pedir("POST", "/api/camaras", {"ips": "192.168.1.61"}, adm)[1]
        otro = d["agregadas"][0]["id"]
        self.assertEqual(self.pedir("POST", f"/api/camaras/{otro}/borrar", {}, adm)[0], 200)
        self.assertEqual(self.pedir("GET", "/api/camaras")[1], [])

    def test_delete_rechaza_otro_origen(self):
        st, _, _ = self.pedir("DELETE", "/api/camaras/x", cab={"X-Admin": "1234", "Origin": "http://malo.com"})
        self.assertEqual(st, 403)

    def test_salud_config_foto_script(self):
        self.assertIn("go2rtc", self.pedir("GET", "/api/camaras/salud")[1])
        self.assertEqual(self.pedir("GET", "/api/camaras/config")[1], {"protegido": True, "maximo_sesiones": 2})
        cid = self.pedir("POST", "/api/camaras", {"ips": "192.168.1.62"}, {"X-Admin": "1234"})[1]["agregadas"][0]["id"]
        st, cuerpo, r = self.pedir("GET", f"/api/camaras/{cid}/foto", crudo=True)
        self.assertEqual((st, r.getheader("Content-Type")), (200, "image/jpeg"))
        self.assertEqual(self.pedir("GET", "/api/camaras/nada/foto")[0], 404)
        self.assertEqual(self.pedir("GET", "/api/camaras/go2rtc/video-rtc.js", crudo=True)[1], b"// js")
        self.assertEqual(self.pedir("GET", "/api/camaras/go2rtc/otro.js")[0], 404)

    def test_sesiones_y_ptz(self):
        cid = self.pedir("POST", "/api/camaras", {"ips": "192.168.1.63"}, {"X-Admin": "1234"})[1]["agregadas"][0]["id"]
        self.assertEqual(self.pedir("POST", f"/api/camaras/{cid}/mover", {"x": 1, "y": 0})[0], 403)
        st, s, _ = self.pedir("POST", "/api/camaras/sesion", {})
        self.assertEqual((st, s["id"]), (200, "s1"))
        st, lleno, _ = self.pedir("POST", "/api/camaras/sesion", {})
        self.assertEqual(st, 409)
        self.assertEqual(lleno["sesiones"], [{"id": "x"}])
        self.assertEqual(self.pedir("POST", "/api/camaras/sesion/s1/latido", {})[1], {"estado": "ok"})
        sid = {"X-Sesion": "s1"}
        self.assertEqual(self.pedir("POST", f"/api/camaras/{cid}/mover", {"x": 5, "y": -0.5}, sid)[0], 200)
        self.assertEqual(self.ptz.llamadas[-1], ("mover", cid, 1.0, -0.5))
        self.assertEqual(self.pedir("POST", f"/api/camaras/{cid}/mover", {"x": "a", "y": 0}, sid)[0], 400)
        self.assertEqual(self.pedir("POST", f"/api/camaras/{cid}/parar", {})[0], 200)
        self.assertEqual(self.ptz.llamadas[-1], ("parar", cid))
        self.pedir("POST", "/api/camaras/sesion/s1/salir", {})
        self.assertEqual(self.pedir("POST", "/api/camaras/sesion/s1/latido", {})[1], {"estado": "expulsada"})

    def test_video_exige_sesion_valida(self):
        cab = {"Upgrade": "websocket", "Connection": "Upgrade"}
        self.assertEqual(self.pedir("GET", "/api/camaras/video?src=x&sesion=zz", cab=cab)[0], 403)
        self.assertEqual(self.pedir("GET", "/api/camaras/video?src=x&sesion=zz")[0], 400)
        self.ses.abrir()
        self.assertEqual(self.pedir("GET", "/api/camaras/video?src=exec:ls&sesion=s1", cab=cab)[0], 404)

    def test_interno_con_y_sin_token(self):
        self.pedir("POST", "/api/camaras", {"ips": "192.168.1.64", "clave": "x"}, {"X-Admin": "1234"})
        self.assertEqual(self.pedir("GET", "/api/interno/camaras")[0], 401)
        self.assertEqual(self.pedir("GET", "/api/interno/camaras", cab={"Authorization": "Bearer mal"})[0], 401)
        st, lista, _ = self.pedir("GET", "/api/interno/camaras", cab={"Authorization": "Bearer tok-detector"})
        self.assertEqual(st, 200)
        self.assertEqual(lista[0]["ip"], "192.168.1.64")
        self.assertNotIn("clave", lista[0])


class TestGrabacionesWeb(Base):
    def test_listas_archivo_y_range(self):
        self.poner("fotos", "2026-05-01", "a.jpg", b"\xff\xd8x")
        self.poner("clips", "2026-05-01", "c.mp4", b"0123456789")
        self.assertEqual(self.pedir("GET", "/api/grabaciones/dias")[1], {"dias": ["2026-05-01"]})
        d = self.pedir("GET", "/api/grabaciones?fecha=2026-05-01")[1]
        self.assertEqual((d["fotos"], d["clips"]), (["a.jpg"], ["c.mp4"]))
        self.assertEqual(self.pedir("GET", "/api/grabaciones?fecha=mal")[0], 422)
        st, cuerpo, r = self.pedir("GET", "/api/grabaciones/clips/2026-05-01/c.mp4", crudo=True)
        self.assertEqual((st, cuerpo, r.getheader("Content-Type")), (200, b"0123456789", "video/mp4"))
        st, cuerpo, r = self.pedir("GET", "/api/grabaciones/clips/2026-05-01/c.mp4", cab={"Range": "bytes=2-4"}, crudo=True)
        self.assertEqual((st, cuerpo, r.getheader("Content-Range")), (206, b"234", "bytes 2-4/10"))
        st, cuerpo, _ = self.pedir("GET", "/api/grabaciones/clips/2026-05-01/c.mp4", cab={"Range": "bytes=7-"}, crudo=True)
        self.assertEqual((st, cuerpo), (206, b"789"))
        st, cuerpo, _ = self.pedir("GET", "/api/grabaciones/clips/2026-05-01/c.mp4", cab={"Range": "bytes=-3"}, crudo=True)
        self.assertEqual((st, cuerpo), (206, b"789"))
        self.assertEqual(self.pedir("GET", "/api/grabaciones/clips/2026-05-01/c.mp4", cab={"Range": "bytes=50-"})[0], 416)
        self.assertEqual(self.pedir("GET", "/api/grabaciones/clips/2026-05-01/nada.mp4")[0], 404)
        self.assertEqual(self.pedir("GET", "/api/grabaciones/clips/2026-05-01/..%2Fx.mp4")[0], 404)

    def test_zip_borrar(self):
        self.poner("fotos", "2026-05-01", "a.jpg", b"AAA")
        self.poner("clips", "2026-05-01", "c.mp4", b"CCCC")
        st, cuerpo, r = self.pedir("GET", "/api/grabaciones/exportar/2026-05-01", crudo=True)
        self.assertEqual((st, r.getheader("Content-Type")), (200, "application/zip"))
        z = zipfile.ZipFile(io.BytesIO(cuerpo))
        self.assertEqual(sorted(z.namelist()), ["clips/2026-05-01/c.mp4", "fotos/2026-05-01/a.jpg"])
        self.assertEqual(z.read("fotos/2026-05-01/a.jpg"), b"AAA")
        st, cuerpo, _ = self.pedir("POST", "/api/grabaciones/exportar", {"fotos": ["2026-05-01/a.jpg"], "clips": []}, crudo=True)
        self.assertEqual(zipfile.ZipFile(io.BytesIO(cuerpo)).namelist(), ["fotos/2026-05-01/a.jpg"])
        self.assertEqual(self.pedir("POST", "/api/grabaciones/exportar", {"fotos": ["2026-05-01/nada.jpg"]})[0], 404)
        self.assertEqual(self.pedir("GET", "/api/grabaciones/exportar/2030-01-01")[0], 404)
        # borrar necesita PIN
        sel = {"fotos": ["2026-05-01/a.jpg"], "clips": []}
        self.assertEqual(self.pedir("POST", "/api/grabaciones/borrar", sel)[0], 401)
        self.assertEqual(self.pedir("POST", "/api/grabaciones/borrar", sel, {"X-Admin": "1234"})[1], {"borrados": 1})
        self.assertEqual(self.pedir("POST", "/api/grabaciones/borrar-dia", {"fecha": "2026-05-01"})[0], 401)
        self.assertEqual(self.pedir("POST", "/api/grabaciones/borrar-dia", {"fecha": "2026-05-01"},
                                    {"X-Admin": "1234"})[1], {"borrados": 1})
        self.assertEqual(self.pedir("GET", "/api/grabaciones/dias")[1], {"dias": []})

    def test_seleccion_grande(self):
        sel = {"fotos": [f"2026-05-01/f{i}.jpg" for i in range(1000)], "clips": []}  # > 4 KB, < 256 KB
        self.assertEqual(self.pedir("POST", "/api/grabaciones/exportar", sel)[0], 404)  # nada existe, pero se leyó
        self.assertEqual(self.pedir("POST", "/api/camaras", {"ips": "192.168.1.5", "nombre": "x" * 5000})[0], 413)


class TestSinCamaras(Base):
    interno = False

    def test_409_sin_camaras_internas(self):
        for metodo, ruta in (("GET", "/api/camaras"), ("GET", "/api/camaras/salud"), ("POST", "/api/camaras/sesion"),
                             ("POST", "/api/camaras/x/mover"), ("GET", "/api/camaras/video?src=x&sesion=s"),
                             ("DELETE", "/api/camaras/x")):
            st, d, _ = self.pedir(metodo, ruta, {} if metodo == "POST" else None)
            self.assertEqual(st, 409, ruta)
            self.assertIn("CAMARAS_INTERNAS=1", d["error"])
        self.assertEqual(self.pedir("GET", "/api/interno/camaras", cab={"Authorization": "Bearer tok-detector"})[0], 404)

    def test_grabaciones_funcionan_sin_camaras_internas(self):
        self.poner("fotos", "2026-05-02", "a.jpg")
        self.assertEqual(self.pedir("GET", "/api/grabaciones/dias")[1], {"dias": ["2026-05-02"]})
        self.assertEqual(self.pedir("POST", "/api/grabaciones/borrar", {"fotos": ["2026-05-02/a.jpg"]},
                                    {"X-Admin": "1234"})[1], {"borrados": 1})


class TestGrabacionesRemotas(Base):
    interno = False

    def test_409_si_son_remotas(self):
        # otro servidor con FOTOS_REMOTAS
        cfg = dataclasses.replace(self.cfg, fotos_remotas=True)
        db = Db(":memory:")
        srv = crear_servidor(cfg, db, Recolector(cfg, db), SesionAbierta())
        hilo = threading.Thread(target=srv.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close(), hilo.join()))
        self.puerto = srv.server_address[1]
        st, d, _ = self.pedir("GET", "/api/grabaciones/dias")
        self.assertEqual(st, 409)
        self.assertIn("gestorCamaras", d["error"])
        self.assertEqual(self.pedir("POST", "/api/grabaciones/borrar", {})[0], 409)


class TestTokenSinSesion(Base):
    auth = SinSesion

    def test_interno_no_necesita_sesion(self):
        self.camaras.registro.agregar("192.168.1.70")
        st, lista, _ = self.pedir("GET", "/api/interno/camaras", cab={"Authorization": "Bearer tok-detector"})
        self.assertEqual((st, len(lista)), (200, 1))
        self.assertEqual(self.pedir("GET", "/api/camaras")[0], 401)
        self.assertEqual(self.pedir("DELETE", "/api/camaras/x")[0], 401)


if __name__ == "__main__":
    unittest.main()
