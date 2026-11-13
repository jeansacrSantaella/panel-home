"""Rutas web de red interna (sonda), clima y habitaciones de luces, con el servidor real y sesión iniciada."""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from panel.auth import COOKIE, Auth
from panel.clima import Clima
from panel.config import Config
from panel.db import Db
from panel.eventos import Recolector
from panel.habitaciones import Habitaciones
from panel.red.servicio import Red
from panel.web import crear_servidor

AHORA = int(time.time())
TOKEN = "tok-red"
MAC_TV = "aa:00:00:00:00:01"
MAC_PC = "aa:00:00:00:00:02"

PRONOSTICO = json.dumps({
    "current": {"temperature_2m": 20.5, "apparent_temperature": 19.8, "relative_humidity_2m": 45,
                "weather_code": 0, "is_day": 1},
    "daily": {"time": ["2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17"],
              "weather_code": [0, 1, 3, 61, 95],
              "temperature_2m_max": [22.0, 23.5, 19.0, 18.2, 21.0],
              "temperature_2m_min": [12.0, 13.0, 11.5, 10.0, 14.1]},
}).encode()


def lote_sonda(ts=AHORA):
    """Lote con el formato de docs/RED.md: sondeo, escaneo de 2 equipos, calidad, IP pública y velocidad."""
    return {"sonda": "lenovo", "version": 1, "enviado": ts, "lecturas": [
        {"t": "sondeo", "ts": ts - 5, "gateway": "192.168.1.1", "resultados": [
            {"kind": "ping", "target": "gateway", "ok": True, "ms": 2.0},
            {"kind": "ping", "target": "1.1.1.1", "ok": True, "ms": 12.0},
            {"kind": "dns", "target": "8.8.8.8", "ok": True, "ms": 20.0}]},
        {"t": "escaneo", "ts": ts - 4, "base": "192.168.1", "propia": "192.168.1.5", "equipos": {
            MAC_TV: {"ip": "192.168.1.50", "hostname": "tv"},
            MAC_PC: {"ip": "192.168.1.51", "hostname": "pc"}}},
        {"t": "calidad", "ts": ts - 3, "resultados": [
            {"mac": MAC_TV, "ip": "192.168.1.50", "ok": True, "ms": 5.0},
            {"mac": MAC_PC, "ip": "192.168.1.51", "ok": True, "ms": 7.0}]},
        {"t": "ip_publica", "ts": ts - 2, "ip": "203.0.113.7"},
        {"t": "velocidad", "ts": ts - 1, "down": 300.0, "up": 50.0},
    ]}


class LucesFalsas:
    """Misma interfaz que panel.luces.Luces para lo que usa web.py y habitaciones.py."""

    configurado = True
    motivo = ""

    def __init__(self):
        self.focos = [
            {"id": "f1", "nombre": "Techo", "encendida": False, "en_linea": True, "brillo": None},
            {"id": "f2", "nombre": "Lámpara", "encendida": False, "en_linea": True, "brillo": None},
        ]
        self.llamadas = []

    def lista(self):
        return [dict(f) for f in self.focos]

    def aplicar(self, ident, cambios):
        if ident not in {f["id"] for f in self.focos}:
            raise KeyError(ident)
        self.llamadas.append((ident, dict(cambios)))
        return {"id": ident, **cambios}

    def aplicar_todas(self, encendida):
        return len(self.focos)

    def nombre_por_ip(self):
        return {}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def servidor(self, con_red=False, token=TOKEN, clima=None, luces=None, con_habitaciones=False):
        cfg = Config(host="127.0.0.1", port=0, camaras_data=self.dir, red_token=token, red_interna=con_red)
        db = Db(":memory:")
        auth = Auth(db)
        auth.asegurar_admin()
        red = None
        if con_red:
            red = Red(db, self.dir / "oui.txt", reloj=lambda: AHORA, fetch=lambda url, timeout=10: b"")
        habitaciones = Habitaciones(db) if con_habitaciones else None
        self.luces = luces
        self.habitaciones = habitaciones
        self.db = db
        srv = crear_servidor(cfg, db, Recolector(cfg, db), auth, luces=luces, red=red, clima=clima,
                             habitaciones=habitaciones)
        self.srv = srv
        self.puerto = srv.server_address[1]
        hilo = threading.Thread(target=srv.serve_forever, daemon=True)
        hilo.start()

        def parar():
            srv.shutdown()
            srv.server_close()
            hilo.join()
        self.addCleanup(parar)

    def pedir(self, metodo, ruta, cuerpo=None, cab=None, crudo=False, tipo="application/json"):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        cab = dict(cab or {})
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            if tipo:
                cab["Content-Type"] = tipo
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

    def sesion(self):
        """Inicia sesión con el admin real (Auth + /api/login) y devuelve la cabecera Cookie."""
        st, _, r = self.pedir("POST", "/api/login", {"usuario": "admin", "contrasena": "1234"})
        self.assertEqual(st, 200)
        return {"Cookie": r.getheader("Set-Cookie").split(";")[0]}

    def bearer(self, valor=TOKEN):
        return {"Authorization": f"Bearer {valor}"}


class TestSaludYSesion(Base):
    def test_salud_sin_sesion_y_panel_pide_sesion(self):
        self.servidor()
        self.assertEqual(self.pedir("GET", "/salud")[:2], (200, {"ok": True}))
        self.assertEqual(self.pedir("GET", "/api/panel")[0], 401)
        self.assertEqual(self.pedir("GET", "/api/panel", cab=self.sesion())[0], 200)


class TestSondaRed(Base):
    def test_sin_token_configurado_responde_404(self):
        self.servidor(con_red=True, token="")
        self.assertEqual(self.pedir("POST", "/api/interno/red", lote_sonda(), self.bearer())[0], 404)

    def test_token_malo_401_y_no_guarda_nada(self):
        self.servidor(con_red=True)
        st, d, _ = self.pedir("POST", "/api/interno/red", lote_sonda(), self.bearer("mal"))
        self.assertEqual((st, d), (401, {"error": "token incorrecto"}))
        self.assertEqual(self.pedir("POST", "/api/interno/red", lote_sonda(), {})[0], 401)
        self.assertEqual(self.pedir("GET", "/api/red/resumen", cab=self.sesion())[1]["vivo"], False)

    def test_lote_realista_y_resumen_con_sesion(self):
        self.servidor(con_red=True)
        st, d, _ = self.pedir("POST", "/api/interno/red", lote_sonda(), self.bearer())
        self.assertEqual(st, 200)
        self.assertEqual((d["ok"], d["recibidas"]), (True, 5))
        cab = self.sesion()

        st, r, _ = self.pedir("GET", "/api/red/resumen", cab=cab)
        self.assertEqual(st, 200)
        self.assertTrue(r["vivo"])
        self.assertEqual(r["sonda"]["nombre"], "lenovo")
        macs = sorted(e["mac"] for e in r["resumen"]["devices"])
        self.assertEqual(macs, sorted([MAC_TV, MAC_PC]))
        self.assertEqual(r["resumen"]["public_ip"], "203.0.113.7")

        st, ev, _ = self.pedir("GET", "/api/red/eventos?page=0&size=10", cab=cab)
        self.assertEqual(st, 200)
        self.assertIn("events", ev)

        st, cuerpo, rr = self.pedir("GET", "/api/red/export.csv", cab=cab, crudo=True)
        self.assertEqual(st, 200)
        self.assertTrue(rr.getheader("Content-Type").startswith("text/csv"))
        self.assertTrue(cuerpo)

    def test_alias_se_refleja_en_resumen(self):
        self.servidor(con_red=True)
        self.pedir("POST", "/api/interno/red", lote_sonda(), self.bearer())
        cab = self.sesion()
        st, d, _ = self.pedir("POST", "/api/red/alias", {"mac": MAC_TV, "alias": "Tele sala"}, cab)
        self.assertEqual((st, d), (200, {"ok": True}))
        r = self.pedir("GET", "/api/red/resumen", cab=cab)[1]["resumen"]
        por_mac = {e["mac"]: e for e in r["devices"]}
        self.assertEqual(por_mac[MAC_TV]["alias"], "Tele sala")

    def test_cuerpo_mayor_de_2mb_responde_413(self):
        self.servidor(con_red=True)
        # Solo cabeceras: el servidor rechaza por Content-Length sin leer el cuerpo.
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        con.putrequest("POST", "/api/interno/red")
        con.putheader("Authorization", f"Bearer {TOKEN}")
        con.putheader("Content-Type", "application/json")
        con.putheader("Content-Length", str(2 * 1024 * 1024 + 1))
        con.endheaders()
        r = con.getresponse()
        self.assertEqual(r.status, 413)
        con.close()

    def test_sin_red_interna_responde_409(self):
        self.servidor(con_red=False)
        self.assertEqual(self.pedir("GET", "/api/red/resumen", cab=self.sesion())[0], 409)


class TestClima(Base):
    def test_sin_configurar(self):
        clima = Clima(Db(":memory:"))
        self.servidor(clima=clima)
        st, d, _ = self.pedir("GET", "/api/clima", cab=self.sesion())
        self.assertEqual(st, 200)
        self.assertFalse(d["configurado"])

    def test_sin_objeto_clima_responde_solo_configurado_false(self):
        self.servidor(clima=None)
        self.assertEqual(self.pedir("GET", "/api/clima", cab=self.sesion())[1], {"configurado": False})

    def test_con_fetch_falso_y_actualizar(self):
        llamadas = []

        def fetch(url, timeout=10):
            llamadas.append(url)
            return PRONOSTICO

        clima = Clima(Db(":memory:"), ciudad="", lat=40.4165, lon=-3.70256, fetch=fetch, reloj=lambda: AHORA)
        self.assertTrue(clima.actualizar())
        self.servidor(clima=clima)
        st, d, _ = self.pedir("GET", "/api/clima", cab=self.sesion())
        self.assertEqual(st, 200)
        self.assertIs(d["configurado"], True)
        self.assertEqual(d["actual"]["temp"], 20.5)
        self.assertEqual(len(d["dias"]), 4)
        self.assertEqual(len(llamadas), 1)


class TestHabitaciones(Base):
    def preparar(self):
        self.servidor(luces=LucesFalsas(), con_habitaciones=True)
        self.cab = self.sesion()

    def test_luces_trae_habitacion_por_foco(self):
        self.preparar()
        self.assertEqual(self.pedir("POST", "/api/luces/f1/habitacion", {"habitacion": "Sala"}, self.cab)[0], 200)
        st, d, _ = self.pedir("GET", "/api/luces", cab=self.cab)
        self.assertEqual(st, 200)
        por_id = {f["id"]: f for f in d["luces"]}
        self.assertEqual(por_id["f1"]["habitacion"], "Sala")
        self.assertIsNone(por_id["f2"]["habitacion"])

    def test_asignar_y_listar_habitaciones(self):
        self.preparar()
        st, d, _ = self.pedir("POST", "/api/luces/f2/habitacion", {"habitacion": "Sala"}, self.cab)
        self.assertEqual((st, d), (200, {"id": "f2", "habitacion": "Sala"}))
        st, d, _ = self.pedir("GET", "/api/luces/habitaciones", cab=self.cab)
        self.assertEqual(st, 200)
        self.assertIn("Sala", d["nombres"])
        sala = [h for h in d["habitaciones"] if h["habitacion"] == "Sala"][0]
        self.assertEqual(sala["focos"], ["f2"])

    def test_foco_inexistente_404(self):
        self.preparar()
        self.assertEqual(self.pedir("POST", "/api/luces/nada/habitacion", {"habitacion": "Sala"}, self.cab)[0], 404)

    def test_nombre_de_41_caracteres_400(self):
        self.preparar()
        st, d, _ = self.pedir("POST", "/api/luces/f1/habitacion", {"habitacion": "x" * 41}, self.cab)
        self.assertEqual(st, 400)
        self.assertIn("error", d)

    def test_aplicar_habitacion_llama_a_cada_foco(self):
        self.preparar()
        self.pedir("POST", "/api/luces/f1/habitacion", {"habitacion": "Sala"}, self.cab)
        self.pedir("POST", "/api/luces/f2/habitacion", {"habitacion": "Sala"}, self.cab)
        st, d, _ = self.pedir("POST", "/api/luces/habitacion", {"habitacion": "Sala", "encendida": True}, self.cab)
        self.assertEqual(st, 200)
        self.assertEqual((d["habitacion"], d["total"], d["ok"], d["fallaron"]), ("Sala", 2, 2, []))
        self.assertEqual(sorted(self.luces.llamadas), [("f1", {"encendida": True}), ("f2", {"encendida": True})])

    def test_habitacion_vacia_404(self):
        self.preparar()
        st, _, _ = self.pedir("POST", "/api/luces/habitacion", {"habitacion": "Vacia", "encendida": True}, self.cab)
        self.assertEqual(st, 404)
        self.assertEqual(self.luces.llamadas, [])

    def test_sin_cambios_400(self):
        self.preparar()
        self.pedir("POST", "/api/luces/f1/habitacion", {"habitacion": "Sala"}, self.cab)
        self.assertEqual(self.pedir("POST", "/api/luces/habitacion", {"habitacion": "Sala"}, self.cab)[0], 400)
        self.assertEqual(self.luces.llamadas, [])

    def test_post_sin_content_type_415(self):
        self.preparar()
        st, _, _ = self.pedir("POST", "/api/luces/f1/habitacion", {"habitacion": "Sala"}, self.cab, tipo=None)
        self.assertEqual(st, 415)


if __name__ == "__main__":
    unittest.main()
