"""Fabricante por MAC a partir de la lista OUI del IEEE."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from netwatch.core.scheduler import PeriodicTask
from netwatch.network.http import Fetcher, fetch

OUI_URL = "https://standards-oui.ieee.org/oui/oui.txt"
OUI_LINE = re.compile(r"^([0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2})\s+\(hex\)\s+(.+)$")


def is_private_mac(mac: str) -> bool:
    """Bit "administrado localmente": típico de teléfonos y laptops con MAC aleatoria."""
    return bool(int(mac[:2], 16) & 2)


class VendorLookup(PeriodicTask):
    """Descarga la lista una sola vez (oui.txt) y la carga en memoria en segundo plano."""
    name = "oui"

    def __init__(self, path: Path, fetcher: Fetcher = fetch):
        self._path = path
        self._fetch = fetcher
        self._table: Dict[str, str] = {}

    def run_once(self) -> None:
        if not self._path.exists():
            self._path.write_bytes(self._fetch(OUI_URL, timeout=60))
        table = {}
        for line in self._path.read_text(errors="ignore").splitlines():
            m = OUI_LINE.match(line)
            if m:
                table[m.group(1)] = m.group(2).strip()
        self._table = table

    def lookup(self, mac: Optional[str]) -> Optional[str]:
        return self._table.get(mac[:8].upper().replace(":", "-")) if mac else None
