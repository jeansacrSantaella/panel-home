"""Prueba de velocidad contra los servidores de Cloudflare."""
from __future__ import annotations

import os
import time
from typing import Callable, Tuple

from netwatch.core.scheduler import PeriodicTask
from netwatch.network.http import Fetcher, fetch
from netwatch.storage.repositories import SpeedRepository

DOWN_URL = "https://speed.cloudflare.com/__down?bytes={}"
UP_URL = "https://speed.cloudflare.com/__up"


class SpeedTester:
    def __init__(self, down_bytes: int, up_bytes: int, fetcher: Fetcher = fetch):
        self._down = down_bytes
        self._up = up_bytes
        self._fetch = fetcher

    def measure(self) -> Tuple[float, float]:
        """Mbps de bajada y de subida."""
        t0 = time.time()
        n = len(self._fetch(DOWN_URL.format(self._down)))
        down = n * 8 / (time.time() - t0) / 1e6
        data = os.urandom(self._up)
        t1 = time.time()
        self._fetch(UP_URL, data=data)
        up = len(data) * 8 / (time.time() - t1) / 1e6
        return down, up


class SpeedMonitor(PeriodicTask):
    name = "speed"

    def __init__(self, tester: SpeedTester, speed: SpeedRepository, internet_up: Callable[[], bool],
                 interval: int, initial_delay: int):
        self.interval = interval
        self.initial_delay = initial_delay
        self._tester = tester
        self._speed = speed
        self._internet_up = internet_up

    def run_once(self) -> None:
        if not self._internet_up():
            return
        down, up = self._tester.measure()
        self._speed.add(int(time.time()), down, up)
