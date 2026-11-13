"""Prepara los datos de /api/summary para el dashboard."""
from __future__ import annotations

import re
import time
from typing import Callable, Dict

from netwatch.core.metrics import quality
from netwatch.network.vendors import VendorLookup
from netwatch.storage.repositories import Repositories

HOUR = 3600
DAY = 86400
RIBBON_BUCKET = 600                 # tramos de 10 minutos
RIBBON_SLOTS = DAY // RIBBON_BUCKET  # 144 tramos = 24 h
SERVICES = ("lan", "wan", "dns")
MAC_IN_DETAIL = re.compile(r"\(([0-9a-f:]{17})\)")


def ip_sort_key(ip: str) -> tuple:
    return tuple(int(x) for x in (ip or "0.0.0.0").split("."))


class SummaryService:
    def __init__(self, repos: Repositories, vendors: VendorLookup, status: Callable[[], dict], contracted: dict):
        self._repos = repos
        self._vendors = vendors
        self._status = status
        self._contracted = contracted

    def build(self) -> dict:
        now = int(time.time())
        samples = self._repos.probes.samples_since(now - HOUR)
        ribbon_start, ribbon, uptime = self._availability(now)
        public_ip = self._repos.meta.get("public_ip")
        return {
            "now": now,
            "checks": self._status(),
            "ribbon_start": ribbon_start, "ribbon": ribbon, "uptime": uptime,
            "series": self._repos.probes.latency_per_minute(now - HOUR),
            "hours": self._repos.events.outages_by_hour(),
            "devices": self._devices(now, samples),
            "events": self._repos.events.recent(60),
            "quality": {t: quality(v) for (k, t), v in samples.items() if k == "ping"},
            "speed": self._repos.speed.recent(48)[::-1],
            "contracted": self._contracted,
            "public_ip": public_ip,
        }

    def _devices(self, now: int, samples: dict) -> list:
        drops: Dict[str, int] = {}
        for detail in self._repos.events.details_since("device_offline", now - DAY):
            m = MAC_IN_DETAIL.search(detail)
            if m:
                drops[m.group(1)] = drops.get(m.group(1), 0) + 1
        devices = self._repos.devices.all()
        devices.sort(key=lambda d: (-d["online"], ip_sort_key(d["ip"])))
        for d in devices:
            d["vendor"] = self._vendors.lookup(d["mac"])
            d["q"] = quality(samples.get(("dev", d["mac"]), []))
            d["drops"] = drops.get(d["mac"], 0)
        return devices

    def _availability(self, now: int):
        """Calcula aciertos por tramo y cuenta el mejor destino de cada servicio."""
        slots = [now // RIBBON_BUCKET - (RIBBON_SLOTS - 1) + i for i in range(RIBBON_SLOTS)]
        agg: Dict[str, Dict[int, float]] = {k: {} for k in SERVICES}
        for r in self._repos.probes.success_by_bucket(slots[0] * RIBBON_BUCKET, RIBBON_BUCKET):
            key = "dns" if r["kind"] == "dns" else "lan" if r["target"] == "gateway" else "wan"
            agg[key][r["b"]] = max(agg[key].get(r["b"], 0), r["a"])
        ribbon, uptime = {}, {}
        for k in SERVICES:
            vals = [agg[k].get(s) for s in slots]
            ribbon[k] = [None if v is None else round(v, 3) for v in vals]
            seen = [v for v in vals if v is not None]
            uptime[k] = round(100 * sum(seen) / len(seen), 2) if seen else None
        return slots[0] * RIBBON_BUCKET, ribbon, uptime
