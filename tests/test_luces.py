"""Pruebas del control de luces con un foco Tuya simulado (no hace falta tinytuya ni focos reales)."""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from panel import luces as L

APAGADOS = set()  # ids que "no responden"


class FocoFalso:
    def __init__(self, dev_id, address=None, local_key="", version=3.3):
        self.id, self.address, self.local_key, self.version = dev_id, address, local_key, version
        self.bulb_configured = False
        self.has_colour = True
        self.has_colourtemp = True
        self.e = {"is_on": False, "mode": "white", "brillo": 50, "temp": 30, "rgb": (255, 0, 0)}
        FocoFalso.ultimo = self

    def set_socketTimeout(self, s): pass
    def set_socketRetryLimit(self, n): pass
    def set_socketPersistent(self, p): pass

    def status(self):
        self.bulb_configured = True
        return {"dps": {}}

    def state(self):
        if self.id in APAGADOS:
            return {"Error": "Network Error: Device Unreachable"}
        return dict(self.e)

    def get_brightness_percentage(self, est): return est["brillo"]
    def get_colourtemp_percentage(self, est): return est["temp"]
    def colour_rgb(self, est): return est["rgb"]
    def turn_on(self):
        if self.id in APAGADOS:
            return {"Error": "Network Error: Device Unreachable"}
        self.e["is_on"] = True
    def turn_off(self): self.e["is_on"] = False
    def set_brightness_percentage(self, b): self.e["brillo"] = b
    def set_colourtemp_percentage(self, t): self.e["temp"] = t
    def set_white_percentage(self, b, t): self.e.update(brillo=b, temp=t, mode="white")
    def set_colour(self, r, g, b): self.e.update(rgb=(r, g, b), mode="colour")


TT = types.SimpleNamespace(BulbDevice=FocoFalso)
FOCOS = [
    {"name": "Sala", "id": "aaa111", "key": "k1", "ip": "192.168.1.64", "version": "3.3", "category": "dj", "mac": "AA:01"},
    {"name": "Cochera", "id": "bbb222", "key": "k2", "ip": "", "category": "dj", "mac": "AA:02"},
    {"name": "Enchufe", "id": "ccc333", "key": "k3", "ip": "192.168.1.70", "category": "cz"},  # no es foco
]


def archivo(datos=FOCOS) -> Path:
    p = Path(tempfile.mkdtemp()) / "devices.json"
    p.write_text(json.dumps(datos))
    return p


class TestLuces(unittest.TestCase):
    def setUp(self):
        APAGADOS.clear()

    def test_sin_tinytuya_o_sin_archivo(self):
        with patch.object(L, "_tinytuya", return_value=None):
            self.assertIn("tinytuya", L.Luces(archivo()).motivo)
        with patch.object(L, "_tinytuya", return_value=TT):
            l = L.Luces(Path("/no/existe.json"))
            self.assertFalse(l.configurado)
            self.assertIn("devices.json", l.motivo)
            self.assertFalse(L.Luces(archivo([FOCOS[2]])).configurado)  # solo un enchufe

    def test_lectura_y_mac(self):
        with patch.object(L, "_tinytuya", return_value=TT):
            l = L.Luces(archivo(), ips_por_mac=lambda: {"aa:02": "192.168.1.65"})
            self.assertTrue(l.configurado)
            l.sondear()
            lista = l.lista()
            self.assertEqual([x["nombre"] for x in lista], ["Cochera", "Sala"])  # el enchufe no entra
            cochera = lista[0]
            self.assertEqual(cochera["ip"], "192.168.1.65")  # la IP salió de NetWatch por la MAC
            self.assertTrue(cochera["en_linea"])
            self.assertEqual((cochera["brillo"], cochera["temperatura"], cochera["color"]), (50, 30, "#ff0000"))
            self.assertEqual(l.nombre_por_ip()["192.168.1.64"], "Sala")
            self.assertNotIn("k1", json.dumps(lista))  # la llave nunca sale

    def test_comandos_y_eventos(self):
        cambios = []
        with patch.object(L, "_tinytuya", return_value=TT):
            l = L.Luces(archivo(), al_cambiar=lambda luz, enc: cambios.append((luz["nombre"], enc)))
            l.sondear()
            self.assertEqual(cambios, [])  # la primera lectura no es un cambio
            r = l.aplicar("aaa111", {"encendida": True, "brillo": 80})
            self.assertTrue(r["encendida"])
            self.assertEqual(r["brillo"], 80)
            self.assertEqual(cambios, [("Sala", True)])
            r = l.aplicar("aaa111", {"color": "#00FF7f"})
            self.assertEqual((r["color"], r["modo"]), ("#00ff7f", "colour"))
            r = l.aplicar("aaa111", {"temperatura": 90, "brillo": 40})
            self.assertEqual((r["temperatura"], r["brillo"], r["modo"]), (90, 40, "white"))
            for malo in ({"brillo": 0}, {"brillo": "x"}, {"color": "rojo"}, {"encendida": 1}, {"temperatura": 101}):
                with self.assertRaises(ValueError):
                    l.aplicar("aaa111", malo)
            with self.assertRaises(KeyError):
                l.aplicar("zzz", {"encendida": True})

    def test_foco_sin_respuesta(self):
        with patch.object(L, "_tinytuya", return_value=TT):
            l = L.Luces(archivo())
            APAGADOS.add("aaa111")
            l.sondear()
            sala = next(x for x in l.lista() if x["id"] == "aaa111")
            self.assertFalse(sala["en_linea"])
            self.assertIn("Unreachable", sala["error"])
            cochera = next(x for x in l.lista() if x["id"] == "bbb222")
            self.assertIn("Sin IP", cochera["error"])  # sin IP en el archivo ni en NetWatch
            self.assertEqual(l.aplicar_todas(True), 0)  # ninguno responde: uno apagado y otro sin IP
            with self.assertRaises(RuntimeError):
                l.aplicar("aaa111", {"encendida": True})
