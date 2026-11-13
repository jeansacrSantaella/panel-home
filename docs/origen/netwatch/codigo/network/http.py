"""Cliente HTTP mínimo usado por las integraciones externas."""
from __future__ import annotations

import urllib.request
from typing import Callable, Optional

Fetcher = Callable[..., bytes]


def fetch(url: str, data: Optional[bytes] = None, timeout: float = 30) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0 netwatch"})
    return urllib.request.urlopen(req, timeout=timeout).read()
