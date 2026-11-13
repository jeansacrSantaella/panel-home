"""Consulta la IP pública y registra cada cambio."""
from __future__ import annotations

from netwatch.core.events import EventBus
from netwatch.core.scheduler import PeriodicTask
from netwatch.network.http import Fetcher, fetch
from netwatch.storage.repositories import MetaRepository

IP_URL = "https://api.ipify.org"
META_KEY = "public_ip"


class PublicIpMonitor(PeriodicTask):
    name = "public_ip"

    def __init__(self, meta: MetaRepository, bus: EventBus, interval: int, fetcher: Fetcher = fetch):
        self.interval = interval
        self._meta = meta
        self._bus = bus
        self._fetch = fetcher

    def run_once(self) -> None:
        try:
            ip = self._fetch(IP_URL, timeout=5).decode().strip()
        except Exception:
            return  # sin internet: lo registra el monitor de conectividad
        previous = self._meta.get(META_KEY)
        if previous is None:
            self._bus.publish("ip_first", f"IP pública inicial: {ip}")
        elif previous != ip:
            self._bus.publish("ip_change", f"IP pública cambió: {previous} → {ip}")
        self._meta.set(META_KEY, ip)
