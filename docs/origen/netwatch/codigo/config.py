"""Configuración central: intervalos de medición, rutas y valores leídos del entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet, Mapping, Tuple

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent

DEFAULT_ALERT_KINDS = frozenset({
    "lan_down", "lan_up", "wan_down", "wan_up", "dns_down", "dns_up", "new_device", "ip_change",
})


@dataclass(frozen=True)
class Settings:
    db_path: Path = PROJECT_DIR / "netwatch.db"
    oui_path: Path = PROJECT_DIR / "oui.txt"
    static_dir: Path = PACKAGE_DIR / "static"

    probe_every: int = 5          # segundos entre mediciones de caídas
    scan_every: int = 120         # segundos entre escaneos de la red
    ip_every: int = 300           # segundos entre consultas de IP pública
    device_every: int = 30        # segundos entre pings a cada equipo
    speed_every: int = 3600       # segundos entre pruebas de velocidad
    speed_delay: int = 30         # espera antes de la primera prueba de velocidad
    speed_down_bytes: int = 10_000_000
    speed_up_bytes: int = 3_000_000

    misses_to_offline: int = 3    # escaneos fallidos antes de marcar un equipo como desconectado
    fails_to_alert: int = 3       # mediciones fallidas seguidas antes de registrar una caída
    keep_days: int = 30           # días que se guardan las mediciones

    external_hosts: Tuple[str, ...] = ("1.1.1.1", "8.8.8.8")
    contracted_down: float = 0    # Mbps de tu plan (0 = sin dato)
    contracted_up: float = 0

    # Lee el token y el chat id desde el entorno; no los guardes en el código.
    telegram_token: str = ""
    telegram_chat: str = ""
    alert_kinds: FrozenSet[str] = field(default=DEFAULT_ALERT_KINDS)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat)

    @property
    def contracted(self) -> dict:
        return {"down": self.contracted_down, "up": self.contracted_up}

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        return cls(
            db_path=Path(env.get("NETWATCH_DB", PROJECT_DIR / "netwatch.db")),
            telegram_token=env.get("TELEGRAM_TOKEN", ""),
            telegram_chat=env.get("TELEGRAM_CHAT_ID", ""),
        )
