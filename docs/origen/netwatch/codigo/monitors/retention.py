"""Borra una vez al día las mediciones más antiguas que el periodo de retención."""
from __future__ import annotations

import time

from netwatch.core.scheduler import PeriodicTask
from netwatch.storage.repositories import ProbeRepository

DAY = 86400


class RetentionTask(PeriodicTask):
    name = "retention"
    interval = DAY

    def __init__(self, probes: ProbeRepository, keep_days: int):
        self._probes = probes
        self._keep_days = keep_days

    def run_once(self) -> None:
        self._probes.purge_before(int(time.time()) - self._keep_days * DAY)
