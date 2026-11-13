"""Descubrimiento de la red local: IP propia, router, tabla ARP y nombres."""
from __future__ import annotations

import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, Optional

from netwatch.network import IS_MAC

ARP_PATTERNS = [
    r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:]+)",      # arp -an
    r"(\d+\.\d+\.\d+\.\d+) .*lladdr ([0-9a-fA-F:]+)",     # ip neigh
]
IGNORED_MAC_PREFIXES = ("ff:ff", "01:00:5e")  # broadcast y multicast

_rdns_pool = ThreadPoolExecutor(4)


def local_ip() -> Optional[str]:
    # Usa connect() para elegir la interfaz de salida; UDP no envía datos aquí.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def gateway() -> Optional[str]:
    try:
        if IS_MAC:
            out = subprocess.run(["route", "-n", "get", "default"],
                                 capture_output=True, text=True, timeout=3).stdout
            m = re.search(r"gateway:\s*(\S+)", out)
        else:
            out = subprocess.run(["ip", "route", "show", "default"],
                                 capture_output=True, text=True, timeout=3).stdout
            m = re.search(r"via\s+(\S+)", out)
        return m.group(1) if m else None
    except Exception:
        return None


def parse_arp(outputs: Iterable[str]) -> Dict[str, str]:
    """Salida de arp/ip neigh -> {mac: ip} con la MAC normalizada."""
    found = {}
    for out in outputs:
        for line in out.splitlines():
            if "incomplete" in line:
                continue
            for pattern in ARP_PATTERNS:
                m = re.search(pattern, line)
                if not m:
                    continue
                parts = m.group(2).split(":")
                if len(parts) != 6:
                    continue
                mac = ":".join(x.zfill(2) for x in parts).lower()
                if not mac.startswith(IGNORED_MAC_PREFIXES):
                    found[mac] = m.group(1)
    return found


def read_arp() -> Dict[str, str]:
    outputs = []
    for cmd in (["arp", "-an"], ["ip", "neigh"]):
        try:
            outputs.append(subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout)
        except Exception:
            pass
    return parse_arp(outputs)


def reverse_dns(ip: str, timeout: float = 2.0) -> Optional[str]:
    try:
        return _rdns_pool.submit(socket.gethostbyaddr, ip).result(timeout=timeout)[0]
    except Exception:
        return None
