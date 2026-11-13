"""Edición de equipos desde el dashboard: alias y tipo de conexión."""
from __future__ import annotations

from typing import Optional

from netwatch.storage.repositories import DeviceRepository

NETWORKS = ("5 GHz", "2.4 GHz", "Cable")
MAX_ALIAS = 60


class DeviceService:
    def __init__(self, devices: DeviceRepository):
        self._devices = devices

    def set_alias(self, mac: str, alias: Optional[str]) -> None:
        self._devices.set_alias(mac, (alias or "").strip()[:MAX_ALIAS] or None)

    def set_network(self, mac: str, network: Optional[str]) -> None:
        self._devices.set_network(mac, network if network in NETWORKS else None)
