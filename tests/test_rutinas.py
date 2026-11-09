"""Pruebas de las rutinas de luces con focos simulados y un reloj controlado."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from panel.db import Db
from panel.rutinas import Rutinas


class LucesFalsas:
    """Tres focos; 'banio' no responde."""

    def __init__(self):
        self.ordenes = []

    def lista(self):
        return [{"id": i, "nombre": n} for i, n in (("sala", "Sala"), ("cuarto", "Cuarto"), ("banio", "Baño"))]

    def aplicar(self, ident, cambios):
        if ident == "banio":
            raise RuntimeError("El foco no respondió")
        self.ordenes.append((ident, cambios))
        return {}


def nuevas():
    db = Db(Path(tempfile.mkdtemp()) / "t.db")
    registro = []
    luces = LucesFalsas()
    return Rutinas(db, luces, al_ejecutar=lambda r, res, o: registro.append((r["nombre"], res, o))), luces, registro


NOCHE = {"nombre": "  Noche ", "acciones": [
    {"id": "sala", "encendida": True, "brillo": 30, "temperatura": 5},
    {"id": "cuarto", "encendida": False, "brillo": 80, "color": "#ff0000"},  # al apagar se ignora el resto
    {"id": "banio", "encendida": True, "color": "#FF9500", "temperatura": 50}],  # color gana a temperatura
    "horario": {"hora": "19:30", "dias": [4, 0, 1, 2, 3, 3]}}


class TestRutinas(unittest.TestCase):
    def test_guardar_y_limpiar(self):
        rt, _, _ = nuevas()
        r = rt.guardar(NOCHE)
        self.assertEqual(r["nombre"], "Noche")
        self.assertEqual(r["horario"], {"hora": "19:30", "dias": [0, 1, 2, 3, 4]})
        self.assertEqual(r["acciones"][1], {"id": "cuarto", "encendida": False})
        self.assertEqual(r["acciones"][2], {"id": "banio", "encendida": True, "color": "#ff9500"})
        r2 = rt.guardar({**NOCHE, "id": r["id"], "nombre": "Noche tranquila", "horario": None})
        self.assertEqual((r2["nombre"], r2["horario"]), ("Noche tranquila", None))
        self.assertEqual(len(rt.lista()), 1)
        rt.borrar(r["id"])
        self.assertEqual(rt.lista(), [])
        with self.assertRaises(KeyError):
            rt.borrar(r["id"])

    def test_validaciones(self):
        rt, _, _ = nuevas()
        malos = [
            {**NOCHE, "nombre": " "},
            {**NOCHE, "acciones": []},
            {**NOCHE, "acciones": [{"id": "garage", "encendida": True}]},
            {**NOCHE, "acciones": [{"id": "sala", "encendida": True}, {"id": "sala", "encendida": False}]},
            {**NOCHE, "acciones": [{"id": "sala", "brillo": 50}]},
            {**NOCHE, "acciones": [{"id": "sala", "encendida": True, "brillo": 0}]},
            {**NOCHE, "horario": {"hora": "25:00", "dias": [0]}},
            {**NOCHE, "horario": {"hora": "07:00", "dias": []}},
            {**NOCHE, "horario": {"hora": "07:00", "dias": [7]}},
            {**NOCHE, "id": "1"},
        ]
        for datos in malos:
            with self.assertRaises((ValueError, KeyError), msg=str(datos)[:80]):
                rt.guardar(datos)

    def test_ejecutar_con_un_foco_caido(self):
        rt, luces, registro = nuevas()
        r = rt.guardar(NOCHE)
        res = rt.ejecutar(r["id"])
        self.assertEqual(res, {"ok": 2, "total": 3, "fallaron": ["Baño"]})
        self.assertIn(("sala", {"encendida": True, "brillo": 30, "temperatura": 5}), luces.ordenes)
        self.assertEqual(registro[0][0], "Noche")
        self.assertEqual(registro[0][2], "manual")

    def test_horario(self):
        rt, luces, registro = nuevas()
        r = rt.guardar(NOCHE)  # L–V 19:30
        lunes = datetime(2026, 11, 9, 19, 29)
        self.assertEqual(rt.revisar(lunes), 0)                                 # aún no
        self.assertEqual(rt.revisar(lunes.replace(minute=31)), 1)              # dentro de la ventana
        self.assertEqual(rt.revisar(lunes.replace(minute=32)), 0)              # no se repite
        self.assertEqual(registro[-1][2], "programada")
        self.assertEqual(rt.revisar(datetime(2026, 11, 10, 19, 30)), 1)        # martes, otra vez
        self.assertEqual(rt.revisar(datetime(2026, 11, 14, 19, 30)), 0)        # sábado no
        self.assertEqual(rt.revisar(datetime(2026, 11, 11, 19, 33)), 0)        # se pasó la ventana
        rt.activar(r["id"], False)
        self.assertEqual(rt.revisar(datetime(2026, 11, 12, 19, 30)), 0)        # pausada
        rt.activar(r["id"], True)
        self.assertEqual(rt.revisar(datetime(2026, 11, 12, 19, 30)), 1)


if __name__ == "__main__":
    unittest.main()
