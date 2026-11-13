"""Ejecuta ping y ajusta -W: milisegundos en macOS y segundos en Linux."""
from __future__ import annotations

import re
import subprocess
import time
from typing import List, Optional, Tuple

from netwatch.network import IS_MAC

PingResult = Tuple[bool, Optional[float]]


def _wait_arg(timeout: float) -> str:
    return str(int(timeout * 1000)) if IS_MAC else str(max(1, int(round(timeout))))


def ping(host: str, timeout: float = 1.0) -> PingResult:
    t0 = time.time()
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", _wait_arg(timeout), host],
                           capture_output=True, text=True, timeout=timeout + 2)
    except Exception:
        return False, None
    if r.returncode != 0:
        return False, None
    m = re.search(r"time[=<]([\d.]+)", r.stdout)
    return True, float(m.group(1)) if m else (time.time() - t0) * 1000


def ping_series(host: str, count: int = 4) -> Tuple[List[float], Optional[int]]:
    """Varios pings seguidos: tiempos de respuesta y TTL de la primera respuesta."""
    try:
        out = subprocess.run(["ping", "-c", str(count), "-i", "0.2", "-W", _wait_arg(1.0), host],
                             capture_output=True, text=True, timeout=count + 5).stdout
    except Exception:
        out = ""
    times = [float(t) for t in re.findall(r"time[=<]([\d.]+)", out)]
    ttl = re.search(r"ttl=(\d+)", out, re.I)
    return times, int(ttl.group(1)) if ttl else None
