"""Define run_once() e interval; ejecuta cada tarea en su propio hilo."""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Iterable, Optional


class PeriodicTask(ABC):
    name: str = "task"
    interval: Optional[float] = None  # None: se ejecuta una sola vez
    initial_delay: float = 0
    min_sleep: float = 0.5

    @abstractmethod
    def run_once(self) -> None: ...


class Scheduler:
    def __init__(self, tasks: Iterable[PeriodicTask]):
        self._tasks = list(tasks)

    def start(self) -> None:
        for task in self._tasks:
            threading.Thread(target=self._loop, args=(task,), name=task.name, daemon=True).start()

    @staticmethod
    def _loop(task: PeriodicTask) -> None:
        time.sleep(task.initial_delay)
        while True:
            t0 = time.time()
            try:
                task.run_once()
            except Exception as e:  # el hilo sigue vivo aunque falle una vuelta
                print(f"{task.name} error:", e, flush=True)
            if task.interval is None:
                return
            time.sleep(max(task.min_sleep, task.interval - (time.time() - t0)))
