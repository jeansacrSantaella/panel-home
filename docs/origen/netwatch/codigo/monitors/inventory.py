"""Inventario de equipos: barrido de ping de la subred /24 y lectura de la tabla ARP."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional

from netwatch.core.events import EventBus
from netwatch.core.scheduler import PeriodicTask
from netwatch.network import discovery
from netwatch.network.ping import ping
from netwatch.network.vendors import VendorLookup, is_private_mac
from netwatch.storage.repositories import DeviceRepository


class InventoryScanner(PeriodicTask):
    name = "scan"

    def __init__(self, devices: DeviceRepository, bus: EventBus, vendors: VendorLookup,
                 interval: int, misses_to_offline: int,
                 find_local_ip: Callable = discovery.local_ip, read_arp: Callable = discovery.read_arp,
                 reverse_dns: Callable = discovery.reverse_dns, pinger: Callable = ping):
        self.interval = interval
        self._devices = devices
        self._bus = bus
        self._vendors = vendors
        self._misses_to_offline = misses_to_offline
        self._local_ip = find_local_ip
        self._read_arp = read_arp
        self._rdns = reverse_dns
        self._ping = pinger
        # No alertes de cada equipo al iniciar con la base vacía; activa alertas tras el primer escaneo.
        self.initialized: Optional[bool] = None

    def run_once(self) -> None:
        if self.initialized is None:
            self.initialized = self._devices.exists_any()
        ip = self._local_ip()
        if not ip:
            return
        base = ".".join(ip.split(".")[:3])
        self._sweep(base)
        found = {mac: addr for mac, addr in self._read_arp().items() if addr.startswith(base + ".")}
        now = int(time.time())
        for mac, addr in found.items():
            self._record_seen(mac, addr, now)
        self._record_missing(found)
        self.initialized = True

    def _sweep(self, base: str) -> None:
        # Llena la tabla ARP con pings; ignora las respuestas.
        with ThreadPoolExecutor(64) as pool:
            list(pool.map(lambda h: self._ping(h, 0.6), [f"{base}.{i}" for i in range(1, 255)]))

    def _record_seen(self, mac: str, addr: str, now: int) -> None:
        known = self._devices.get(mac)
        if known is None:
            host = self._rdns(addr)
            private = is_private_mac(mac)
            self._devices.add(mac, addr, host, private, now)
            vendor = self._vendors.lookup(mac)
            extra = (f" · {vendor}" if vendor else "") + \
                    (" · MAC privada (típico de teléfonos y laptops)" if private else "")
            self._bus.publish("new_device", f"Equipo nuevo: {mac} en {addr}" + (f" ({host})" if host else "") + extra,
                              notify=self.initialized)
            return
        if not known["online"]:
            self._bus.publish("device_online", f"{mac} volvió a la red en {addr}")
        self._devices.mark_seen(mac, addr, now)

    def _record_missing(self, found: Dict[str, str]) -> None:
        for d in self._devices.all():
            if d["mac"] in found:
                continue
            misses = d["misses"] + 1
            offline = misses >= self._misses_to_offline
            self._devices.set_misses(d["mac"], misses, False if offline else bool(d["online"]))
            if offline and d["online"]:
                name = d["alias"] or d["hostname"] or d["ip"]
                self._bus.publish("device_offline", f"{name} ({d['mac']}) se desconectó")
