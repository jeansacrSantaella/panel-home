"""Configuración global del panel de control."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import FrozenSet, Mapping

ROOT = Path(__file__).resolve().parent.parent

# Ya los avisan otros proyectos; aquí no se repiten (se pueden activar con PANEL_AVISAR).
# NetWatch: internet, red local, DNS, equipos nuevos y cambio de IP.
# gestorCamaras: cámaras sin red / sin video / de vuelta y go2rtc.
YA_AVISADOS: FrozenSet[str] = frozenset({
    "internet_caido", "internet_ok", "red_local_caida", "red_local_ok", "dns_caido", "dns_ok",
    "equipo_nuevo", "cambio_ip",
    "camara_sin_red", "camara_sin_video", "camara_ok", "go2rtc_caido", "go2rtc_ok",
})

# Solo lo que nadie más avisa: cuando NetWatch o gestorCamaras dejan de responder.
# El movimiento NO se avisa al instante (solo va a la línea de tiempo): el detector ya manda un resumen cada 2 h.
TIPOS_AVISO: FrozenSet[str] = frozenset({"fuente_caida", "fuente_ok"})


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 8770
    db_path: Path = ROOT / "panel.db"
    netwatch_url: str = "http://127.0.0.1:8765"
    camaras_url: str = "http://127.0.0.1:8080"
    go2rtc_url: str = ""
    camaras_data: Path = ROOT.parent / "Camaras" / "gestorCamaras" / "data"
    fotos_remotas: bool = False   # True: las capturas se piden por HTTP a gestorCamaras
    consumo_cmd: str = ""
    recolectar_cada: int = 15
    telegram_token: str = ""
    telegram_chat_id: str = ""
    ntfy_url: str = ""
    avisar: FrozenSet[str] = TIPOS_AVISO

    @property
    def telegram_activo(self) -> bool:
        """Indica si la integración con Telegram está activa."""
        return bool(self.telegram_token and self.telegram_chat_id)


def cargar(env: Mapping[str, str] = os.environ) -> Config:
    """Carga la configuración desde las variables de entorno."""
    kwargs = {}

    def _obtener(clave: str) -> str:
        valor = env.get(clave, "")
        return valor.strip() if valor else ""

    val = _obtener("PANEL_HOST")
    if val:
        kwargs["host"] = val

    val = _obtener("PANEL_PORT")
    if val:
        try:
            kwargs["port"] = int(val)
        except ValueError:
            raise ValueError(f"PANEL_PORT debe ser un entero válido, valor recibido: {val!r}")

    val = _obtener("PANEL_DB")
    if val:
        kwargs["db_path"] = Path(val)

    val = _obtener("NETWATCH_URL")
    if val:
        kwargs["netwatch_url"] = val.rstrip("/")

    val = _obtener("CAMARAS_URL")
    if val:
        kwargs["camaras_url"] = val.rstrip("/")

    val = _obtener("GO2RTC_URL")
    if val:
        kwargs["go2rtc_url"] = val.rstrip("/")

    val = _obtener("CAMARAS_DATA")
    if val:
        kwargs["camaras_data"] = Path(val).expanduser()

    val = _obtener("FOTOS_REMOTAS")
    if val:
        kwargs["fotos_remotas"] = val.lower() in ("1", "si", "sí", "true", "yes")

    val = _obtener("CONSUMO_CMD")
    if val:
        kwargs["consumo_cmd"] = val

    val = _obtener("RECOLECTAR_CADA")
    if val:
        try:
            segundos = int(val)
        except ValueError:
            raise ValueError(f"RECOLECTAR_CADA debe ser un entero válido, valor recibido: {val!r}")
        kwargs["recolectar_cada"] = max(5, segundos)

    val = _obtener("TELEGRAM_TOKEN")
    if val:
        kwargs["telegram_token"] = val

    val = _obtener("TELEGRAM_CHAT_ID")
    if val:
        kwargs["telegram_chat_id"] = val

    val = _obtener("NTFY_URL")
    if val:
        kwargs["ntfy_url"] = val.rstrip("/")

    val = _obtener("PANEL_AVISAR")
    if val:
        nombres = [item.strip() for item in val.split(",") if item.strip()]
        kwargs["avisar"] = frozenset(nombres)

    return Config(**kwargs)


def leer_env(ruta: Path = ROOT / ".env", env: dict = None) -> dict:
    """Carga KEY=valor de un archivo .env sin pisar variables que ya existan. Devuelve las que cargó."""
    env = os.environ if env is None else env
    cargadas = {}
    if not ruta.is_file():
        return cargadas
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip().strip('"').strip("'")
        if clave and clave not in env:
            env[clave] = valor
            cargadas[clave] = valor
    return cargadas
