"""Fabricante por MAC a partir de la lista OUI del IEEE."""
from __future__ import annotations

import logging
import re
import threading
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Optional

from panel.red.estado import mac_privada  # noqa: F401  (se reexporta aquí)

log = logging.getLogger("panel.red")

OUI_URL = "https://standards-oui.ieee.org/oui/oui.txt"
OUI_LINEA = re.compile(r"^([0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2})\s+\(hex\)\s+(.+)$")


def _descargar_url(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "panel-home"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


class Fabricantes:
    def __init__(self, ruta: Path, fetch: Optional[Callable] = None):
        self._ruta = Path(ruta)
        self._fetch = fetch or _descargar_url
        self._tabla: Optional[Dict[str, str]] = None
        self._lock = threading.Lock()

    def descargar(self) -> None:
        """Baja la lista solo si falta o está vacía; los errores solo se registran."""
        try:
            if self._ruta.exists() and self._ruta.stat().st_size > 0:
                return
            datos = self._fetch(OUI_URL, 60)
            self._ruta.parent.mkdir(parents=True, exist_ok=True)
            self._ruta.write_bytes(datos)
            with self._lock:
                self._tabla = None  # recargar con el archivo nuevo
        except Exception as e:
            log.warning("no se pudo descargar la lista OUI: %s", e)

    def _cargar(self) -> Dict[str, str]:
        tabla: Dict[str, str] = {}
        try:
            texto = self._ruta.read_text(errors="ignore")
        except OSError:
            return tabla
        for linea in texto.splitlines():
            m = OUI_LINEA.match(linea)
            if m:
                tabla[m.group(1)] = m.group(2).strip()
        return tabla

    def buscar(self, mac) -> Optional[str]:
        if not mac:
            return None
        with self._lock:
            if self._tabla is None:
                self._tabla = self._cargar()
            return self._tabla.get(mac[:8].upper().replace(":", "-"))
