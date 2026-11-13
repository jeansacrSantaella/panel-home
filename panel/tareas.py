"""Planificador de tareas periódicas: un hilo por tarea, sigue vivo aunque una vuelta falle."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

log = logging.getLogger("panel.tareas")

class Tarea:
    """Base de una tarea periódica. Subclases definen ejecutar()."""
    nombre: str = "tarea"
    cada: float | None = None     # segundos entre vueltas; None = una sola vez
    retraso: float = 0            # espera antes de la primera vuelta
    minimo: float = 0.5           # pausa mínima entre vueltas
    def ejecutar(self) -> None: raise NotImplementedError

class Planificador:
    def __init__(self, tareas=(), dormir=None):
        self._tareas: list[Tarea] = list(tareas)
        self._parar = threading.Event()
        self._dormir = dormir or self._parar.wait
        self._hilos: list[threading.Thread] = []

    def agregar(self, tarea: Tarea) -> None:
        self._tareas.append(tarea)

    def iniciar(self) -> None:
        self._parar.clear()
        self._hilos = []
        for tarea in self._tareas:
            hilo = threading.Thread(target=self._bucle, args=(tarea,), name=tarea.nombre, daemon=True)
            self._hilos.append(hilo)
            hilo.start()

    def detener(self) -> None:
        self._parar.set()
        for hilo in self._hilos:
            hilo.join(timeout=1.0)

    def vuelta(self, tarea: Tarea) -> bool:
        try:
            tarea.ejecutar()
            return True
        except Exception:
            log.exception("Error ejecutando tarea %s", tarea.nombre)
            return False

    def _bucle(self, tarea: Tarea) -> None:
        if tarea.retraso > 0:
            if self._dormir(tarea.retraso):
                return

        while not self._parar.is_set():
            t0 = time.monotonic()
            self.vuelta(tarea)
            
            if tarea.cada is None:
                break

            duracion = time.monotonic() - t0
            espera = max(tarea.minimo, tarea.cada - duracion)
            if self._dormir(espera):
                break


def cada(nombre: str, segundos: float, funcion: Callable[[], None], retraso: float = 0) -> Tarea:
    """Crea una Tarea que llama a funcion() cada `segundos`."""
    class _TareaDinamica(Tarea):
        def ejecutar(self) -> None:
            funcion()

    t = _TareaDinamica()
    t.nombre = nombre
    t.cada = segundos
    t.retraso = retraso
    return t
