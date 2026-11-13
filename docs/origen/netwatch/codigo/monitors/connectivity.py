"""Caídas de red local, internet y DNS."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional, Sequence

from netwatch.core.events import EventBus
from netwatch.core.metrics import format_duration
from netwatch.core.scheduler import PeriodicTask
from netwatch.network.discovery import gateway
from netwatch.network.dns import dns_query
from netwatch.network.ping import ping
from netwatch.storage.repositories import ProbeRepository

LABELS = {"lan": "Red local", "wan": "Internet", "dns": "DNS"}
GATEWAY_REFRESH = 60  # segundos entre consultas de la ruta por defecto


class ServiceState:
    """Exige varios fallos seguidos antes de declarar una caída."""

    def __init__(self, name: str, fails_to_alert: int, bus: EventBus):
        self.name = name
        self.label = LABELS[name]
        self._fails_to_alert = fails_to_alert
        self._bus = bus
        self.fails = 0
        self.first_fail: Optional[int] = None
        self.down_since: Optional[int] = None

    def update(self, ok: bool, now: int) -> None:
        if ok:
            if self.down_since:
                self._bus.publish(f"{self.name}_up",
                                  f"{self.label} restablecida tras {format_duration(now - self.down_since)}")
                self.down_since = None
            self.fails, self.first_fail = 0, None
            return
        self.fails += 1
        self.first_fail = self.first_fail or now
        if self.fails >= self._fails_to_alert and not self.down_since:
            self.down_since = self.first_fail  # la caída empieza en el primer fallo, no en el último
            self._bus.publish(f"{self.name}_down", f"{self.label} sin respuesta")


class ConnectivityMonitor(PeriodicTask):
    name = "probe"

    def __init__(self, probes: ProbeRepository, bus: EventBus, external_hosts: Sequence[str],
                 interval: int, fails_to_alert: int,
                 pinger: Callable = ping, resolver: Callable = dns_query, find_gateway: Callable = gateway):
        self.interval = interval
        self._probes = probes
        self._bus = bus
        self._external = list(external_hosts)
        self._ping = pinger
        self._dns = resolver
        self._find_gateway = find_gateway
        self._pool = ThreadPoolExecutor(12)
        self._gw: Optional[str] = None
        self._gw_at = 0
        self._last: Optional[int] = None
        self.services: Dict[str, ServiceState] = {k: ServiceState(k, fails_to_alert, bus) for k in LABELS}

    def is_up(self, name: str) -> bool:
        return not self.services[name].down_since

    def status(self) -> dict:
        return {k: {"label": s.label, "down_since": s.down_since} for k, s in self.services.items()}

    def run_once(self) -> None:
        now = int(time.time())
        if self._last and now - self._last > self.interval * 4:
            self._bus.publish("monitor_gap", f"El monitor estuvo detenido {format_duration(now - self._last)} "
                                             "(¿equipo suspendido?)")
        if now - self._gw_at > GATEWAY_REFRESH:
            self._gw, self._gw_at = self._find_gateway(), now
        self.evaluate(self._measure(now), now)
        self._last = now

    def _targets(self) -> Dict[str, str]:
        targets = {h: h for h in self._external}
        return {"gateway": self._gw, **targets} if self._gw else targets

    def _measure(self, now: int) -> dict:
        targets = self._targets()
        futures = {("ping", k): self._pool.submit(self._ping, v) for k, v in targets.items()}
        futures.update({("dns", k): self._pool.submit(self._dns, v) for k, v in targets.items()})
        results = {key: f.result() for key, f in futures.items()}
        for (kind, target), (ok, ms) in results.items():
            self._probes.add(now, kind, target, ok, ms)
        return results

    def evaluate(self, results: dict, now: int) -> None:
        has_gw = ("ping", "gateway") in results
        lan_ok = results[("ping", "gateway")][0] if has_gw else True
        wan_ok = any(results[("ping", h)][0] for h in self._external if ("ping", h) in results)
        dns_ok = any(ok for (kind, _), (ok, _) in results.items() if kind == "dns")
        self.services["lan"].update(lan_ok, now)
        self.services["wan"].update(wan_ok or not lan_ok, now)   # si la red local cae, no culpar al internet
        self.services["dns"].update(dns_ok or not wan_ok, now)   # si no hay internet, no culpar al DNS
