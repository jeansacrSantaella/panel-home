"""Escáner bajo demanda de un host: identidad, calidad, DNS y puertos TCP abiertos."""
from __future__ import annotations

import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional

from netwatch.core.metrics import quality, samples_from_times
from netwatch.network import discovery
from netwatch.network.dns import dns_query
from netwatch.network.ping import ping_series
from netwatch.network.vendors import VendorLookup, is_private_mac
from netwatch.storage.repositories import DeviceRepository

COMMON_PORTS = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http", 110: "pop3", 135: "msrpc",
    139: "netbios", 143: "imap", 443: "https", 445: "smb", 548: "afp", 554: "rtsp", 631: "ipp",
    993: "imaps", 995: "pop3s", 1883: "mqtt", 3306: "mysql", 3389: "rdp", 5000: "upnp/http",
    5432: "postgres", 5900: "vnc", 6379: "redis", 7000: "airplay", 8000: "http-alt", 8008: "http-alt",
    8009: "chromecast", 8080: "http-proxy", 8443: "https-alt", 8888: "http-alt", 9100: "impresora",
    32400: "plex", 49152: "upnp", 62078: "iphone-sync",
}
HTTP_PORTS = {80, 5000, 7000, 8000, 8008, 8080, 8888, 32400}
MAX_SCAN_PORTS = 5000
PING_COUNT = 4
HOST_PATTERN = re.compile(r"[A-Za-z0-9.\-:]+")


def parse_ports(spec: Optional[str]) -> List[int]:
    """'common', '1-1024' o una lista como '22,80,8000-8100'."""
    spec = (spec or "common").strip().lower()
    if spec == "common":
        return sorted(COMMON_PORTS)
    ports = set()
    for part in (p.strip() for p in spec.split(",")):
        if not part:
            continue
        a, _, b = part.partition("-")
        if not a.isdigit() or (b and not b.isdigit()):
            raise ValueError(f"rango de puertos inválido: {part}")
        lo, hi = int(a), int(b or a)
        if not 1 <= lo <= hi <= 65535:
            raise ValueError(f"puertos fuera de rango: {part}")
        ports.update(range(lo, hi + 1))
        if len(ports) > MAX_SCAN_PORTS:
            raise ValueError(f"como máximo {MAX_SCAN_PORTS} puertos por escaneo")
    if not ports:
        raise ValueError("no se indicaron puertos")
    return sorted(ports)


def os_hint(ttl: Optional[int]) -> Optional[str]:
    # Estima el sistema con el TTL inicial y sus saltos típicos.
    if ttl is None:
        return None
    if ttl <= 64:
        return "Linux, macOS, iOS o Android"
    if ttl <= 128:
        return "Windows"
    return "Equipo de red (router, impresora…)"


def service_name(port: int) -> str:
    try:
        return COMMON_PORTS.get(port) or socket.getservbyport(port, "tcp")
    except OSError:
        return ""


def grab_banner(sock: socket.socket, host: str, port: int) -> str:
    try:
        sock.settimeout(1.0)
        if port in HTTP_PORTS:
            sock.sendall(f"HEAD / HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
            lines = sock.recv(1024).decode(errors="ignore").splitlines()
            server = next((line for line in lines if line.lower().startswith("server:")), "")
            return " · ".join(x for x in (lines[0] if lines else "", server) if x)
        try:
            data = sock.recv(256)
        except socket.timeout:
            return ""
        text = data.decode(errors="ignore").strip()
        return text.splitlines()[0][:120] if text else ""
    except Exception:
        return ""


def scan_port(ip: str, port: int, timeout: float = 0.5) -> Optional[dict]:
    try:
        with socket.create_connection((ip, port), timeout=timeout) as s:
            banner = grab_banner(s, ip, port)
    except Exception:
        return None
    return {"port": port, "service": service_name(port), "banner": banner}


class HostScanner:
    def __init__(self, devices: DeviceRepository, vendors: VendorLookup,
                 pinger: Callable = ping_series, resolver: Callable = dns_query,
                 read_arp: Callable = discovery.read_arp, reverse_dns: Callable = discovery.reverse_dns,
                 port_probe: Callable = scan_port):
        self._devices = devices
        self._vendors = vendors
        self._ping = pinger
        self._dns = resolver
        self._read_arp = read_arp
        self._rdns = reverse_dns
        self._probe = port_probe

    def scan(self, host: Optional[str], ports_spec: Optional[str]) -> dict:
        host = (host or "").strip()
        if not host or len(host) > 253 or not HOST_PATTERN.fullmatch(host):
            raise ValueError("host inválido")
        ports = parse_ports(ports_spec)
        steps = []
        t0 = time.time()
        try:
            ip = socket.gethostbyname(host)
        except OSError as exc:
            raise ValueError(f"no se pudo resolver {host}") from exc
        steps.append(f"Resolución de nombre: {host} → {ip}")

        hostname = self._rdns(ip)
        steps.append("DNS inverso: " + (hostname or "sin nombre"))

        times, ttl = self._ping(ip, PING_COUNT)
        ping_q = quality(samples_from_times(times, PING_COUNT))
        steps.append(f"Ping x{PING_COUNT}: {100 - ping_q['loss']:.0f} % de respuestas" + (f", TTL {ttl}" if ttl else ""))

        mac = next((m for m, i in self._read_arp().items() if i == ip), None)
        known = self._devices.get(mac) if mac else None
        steps.append("Tabla ARP: " + (mac or "no está en la red local"))

        dns_ok, dns_ms = self._dns(ip, timeout=1.0)
        steps.append("Servidor DNS: " + (f"responde en {dns_ms:.1f} ms" if dns_ok else "no responde"))

        with ThreadPoolExecutor(min(256, len(ports))) as pool:
            found = [r for r in pool.map(lambda p: self._probe(ip, p), ports) if r]
        steps.append(f"Puertos TCP: {len(ports)} probados, {len(found)} abiertos")

        return {
            "host": host, "ip": ip, "hostname": hostname, "mac": mac,
            "vendor": self._vendors.lookup(mac),
            "random_mac": bool(mac and is_private_mac(mac)),
            "known": {k: known[k] for k in ("alias", "hostname", "network", "first_seen")} if known else None,
            "ping": ping_q, "ttl": ttl, "os_hint": os_hint(ttl),
            "dns": {"ok": dns_ok, "ms": round(dns_ms, 1) if dns_ms else None},
            "ports_scanned": len(ports), "open": found,
            "steps": steps, "elapsed": round(time.time() - t0, 1),
        }
