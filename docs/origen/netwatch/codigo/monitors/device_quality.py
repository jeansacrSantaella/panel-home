"""Mide latencia, jitter y pérdida con pings periódicos a cada equipo conectado."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from netwatch.core.scheduler import PeriodicTask
from netwatch.network.ping import ping
from netwatch.storage.repositories import DeviceRepository, ProbeRepository


class DeviceQualityMonitor(PeriodicTask):
    name = "devices"
    min_sleep = 1

    def __init__(self, devices: DeviceRepository, probes: ProbeRepository, interval: int, pinger: Callable = ping):
        self.interval = interval
        self._devices = devices
        self._probes = probes
        self._ping = pinger
        self._pool = ThreadPoolExecutor(16)

    def run_once(self) -> None:
        now = int(time.time())
        futures = [(d["mac"], self._pool.submit(self._ping, d["ip"], 1.0)) for d in self._devices.online()]
        for mac, f in futures:
            ok, ms = f.result()
            self._probes.add(now, "dev", mac, ok, ms)
