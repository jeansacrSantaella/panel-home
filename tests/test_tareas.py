from __future__ import annotations

import unittest
import threading
import time
from panel.tareas import Tarea, Planificador, cada


class TareaOk(Tarea):
    nombre = "ok"
    def ejecutar(self) -> None:
        pass


class TareaError(Tarea):
    nombre = "error"
    def ejecutar(self) -> None:
        raise ValueError("fallo intencionado")


class TestTareas(unittest.TestCase):

    def test_vuelta_exito_y_error(self):
        plan = Planificador()
        self.assertTrue(plan.vuelta(TareaOk()))
        self.assertFalse(plan.vuelta(TareaError()))

    def test_bucle_una_sola_vez(self):
        contador = 0
        class TareaUnaVez(Tarea):
            nombre = "una"
            cada = None
            def ejecutar(self):
                nonlocal contador
                contador += 1

        plan = Planificador(dormir=lambda s: False)
        plan._bucle(TareaUnaVez())
        self.assertEqual(contador, 1)

    def test_bucle_con_cada(self):
        contador = 0
        class TareaPeriodica(Tarea):
            nombre = "per"
            cada = 10
            minimo = 0.0
            def ejecutar(self):
                nonlocal contador
                contador += 1

        llamadas_dormir = 0
        def dormir_mock(segundos):
            nonlocal llamadas_dormir
            llamadas_dormir += 1
            if llamadas_dormir >= 3:
                return True
            return False

        plan = Planificador(dormir=dormir_mock)
        plan._bucle(TareaPeriodica())
        self.assertEqual(contador, 3)  # sin retraso: corre, duerme, corre, duerme, corre, duerme(True)

    def test_retraso_interrumpido(self):
        ejecutada = False
        class TareaRetraso(Tarea):
            nombre = "ret"
            retraso = 5.0
            def ejecutar(self):
                nonlocal ejecutada
                ejecutada = True

        plan = Planificador(dormir=lambda s: True)
        plan._bucle(TareaRetraso())
        self.assertFalse(ejecutada)

    def test_iniciar_detener_real(self):
        contador = 0
        t = cada("rapida", 0.05, lambda: nonlocal_inc())

        def nonlocal_inc():
            nonlocal contador
            contador += 1

        plan = Planificador(tareas=[t])
        plan.iniciar()
        time.sleep(0.3)
        plan.detener()

        self.assertGreaterEqual(contador, 1)

