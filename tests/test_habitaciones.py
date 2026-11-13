from __future__ import annotations

import unittest
from panel.db import Db
from panel.habitaciones import Habitaciones


class LucesFalsas:
    def __init__(self, luces_iniciales, ids_fallan_runtime=None, ids_fallan_value=None):
        self._luces = luces_iniciales
        self.llamadas = []
        self.ids_fallan_runtime = ids_fallan_runtime or []
        self.ids_fallan_value = ids_fallan_value or []

    def lista(self):
        return self._luces

    def aplicar(self, ident, cambios):
        self.llamadas.append((ident, cambios))
        if ident in self.ids_fallan_value:
            raise ValueError("Cambio inválido")
        if ident in self.ids_fallan_runtime:
            raise RuntimeError("El foco no respondió")
        return {"id": ident, **cambios}


class HabitacionesTest(unittest.TestCase):
    def setUp(self):
        self.db = Db(":memory:")
        self.habs = Habitaciones(self.db)

    def test_asignar_y_quitar(self):
        res = self.habs.asignar("f1", "  sala   de  estar ")
        self.assertEqual(res, "sala de estar")
        self.assertEqual(self.habs.de("f1"), "sala de estar")

        # Quitar con None o ""
        self.assertIsNone(self.habs.asignar("f1", ""))
        self.assertIsNone(self.habs.de("f1"))

        self.habs.asignar("f1", "Cocina")
        self.assertIsNone(self.habs.asignar("f1", None))
        self.assertIsNone(self.habs.de("f1"))

    def test_valores_invalidos(self):
        # Largo mayor a 40
        with self.assertRaises(ValueError):
            self.habs.asignar("f1", "a" * 41)

        # Caracter de control
        with self.assertRaises(ValueError):
            self.habs.asignar("f1", "sala\nestar")

        # Tipo no str
        with self.assertRaises(ValueError):
            self.habs.asignar("f1", 123)  # type: ignore

    def test_nombres_ordenados_y_acentos(self):
        self.habs.asignar("f1", "Ático")
        self.habs.asignar("f2", "cocina")
        self.habs.asignar("f3", "Baño")

        # Orden sin distinguir mayúsculas/acentos: Atico, Bano, cocina
        self.assertEqual(self.habs.nombres(), ["Ático", "Baño", "cocina"])

    def test_con_habitacion(self):
        luces = [
            {"id": "f1", "nombre": "Foco 1"},
            {"id": "f2", "nombre": "Foco 2"},
        ]
        self.habs.asignar("f1", "Dormitorio")
        resultado = self.habs.con_habitacion(luces)

        # No debe modificar la original
        self.assertNotIn("habitacion", luces[0])
        self.assertEqual(resultado[0]["habitacion"], "Dormitorio")
        self.assertIsNone(resultado[1]["habitacion"])

    def test_resumen(self):
        luces = [
            {"id": "f1", "encendida": True, "en_linea": True, "brillo": 50},
            {"id": "f2", "encendida": True, "en_linea": True, "brillo": 80},
            {"id": "f3", "encendida": False, "en_linea": True, "brillo": 10},
            {"id": "f4", "encendida": True, "en_linea": False, "brillo": None},
        ]
        self.habs.asignar("f1", "Cocina")
        self.habs.asignar("f2", "Cocina")
        self.habs.asignar("f3", "Sala")

        resumen = self.habs.resumen(luces)
        # Habitaciones ordenadas: Cocina, Sala, luego "Sin habitación" al final (f4)
        self.assertEqual(len(resumen), 3)
        self.assertEqual(resumen[0]["habitacion"], "Cocina")
        self.assertEqual(resumen[0]["total"], 2)
        self.assertEqual(resumen[0]["encendidos"], 2)
        self.assertEqual(resumen[0]["en_linea"], 2)
        self.assertEqual(resumen[0]["brillo"], 65)  # round((50+80)/2)

        self.assertEqual(resumen[1]["habitacion"], "Sala")
        self.assertEqual(resumen[1]["brillo"], None)  # No encendido con brillo válido

        self.assertEqual(resumen[2]["habitacion"], "Sin habitación")
        self.assertEqual(resumen[2]["focos"], ["f4"])

    def test_aplicar_paralelo_exitoso_y_fallos(self):
        luces = [
            {"id": "f1", "nombre": "Luz F1"},
            {"id": "f2", "nombre": "Luz F2"},
            {"id": "f3", "nombre": "Luz F3"},
        ]
        self.habs.asignar("f1", "Oficina")
        self.habs.asignar("f2", "Oficina")
        self.habs.asignar("f3", "Oficina")

        luces_falsas = LucesFalsas(luces, ids_fallan_runtime=["f2"])
        res = self.habs.aplicar(luces_falsas, "Oficina", {"encendida": True})

        self.assertEqual(res["habitacion"], "Oficina")
        self.assertEqual(res["total"], 3)
        self.assertEqual(res["ok"], 2)
        self.assertEqual(res["fallaron"], ["Luz F2"])

    def test_aplicar_key_error_si_vacia(self):
        luces_falsas = LucesFalsas([])
        with self.assertRaises(KeyError):
            self.habs.aplicar(luces_falsas, "Inexistente", {"encendida": True})

    def test_aplicar_value_error_se_propaga(self):
        luces = [
            {"id": "f1", "nombre": "Luz F1"},
            {"id": "f2", "nombre": "Luz F2"},
        ]
        self.habs.asignar("f1", "Oficina")
        self.habs.asignar("f2", "Oficina")

        luces_falsas = LucesFalsas(luces, ids_fallan_value=["f2"])
        with self.assertRaises(ValueError):
            self.habs.aplicar(luces_falsas, "Oficina", {"brillo": 150})
