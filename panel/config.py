"""Configuración global del panel de control."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import FrozenSet, Mapping, Optional

ROOT = Path(__file__).resolve().parent.parent

# Ya los avisan otros proyectos; aquí no se repiten (se pueden activar con PANEL_AVISAR).
# NetWatch: internet, red local, DNS, equipos nuevos y cambio de IP.
# gestorCamaras: cámaras sin red / sin video / de vuelta y go2rtc.
YA_AVISADOS: FrozenSet[str] = frozenset({
    "internet_caido", "internet_ok", "red_local_caida", "red_local_ok", "dns_caido", "dns_ok",
    "equipo_nuevo", "cambio_ip",
    "camara_sin_red", "camara_sin_video", "camara_ok", "go2rtc_caido", "go2rtc_ok",
})

# Lo que avisaba NetWatch; con RED_INTERNA=1 lo avisa panel-home
AVISOS_RED: FrozenSet[str] = frozenset({
    "internet_caido", "internet_ok", "red_local_caida", "red_local_ok", "dns_caido", "dns_ok",
    "equipo_nuevo", "cambio_ip",
})

# Lo que avisaba gestorCamaras; con CAMARAS_INTERNAS=1 lo avisa panel-home (vigilante de cámaras)
AVISOS_CAMARAS: FrozenSet[str] = frozenset({
    "camara_caida", "camara_volvio", "go2rtc_sin_respuesta", "go2rtc_volvio", "servidor_suspendido",
})

# Solo lo que nadie más avisa: cuando NetWatch o gestorCamaras dejan de responder.
# El movimiento NO se avisa al instante (solo va a la línea de tiempo): el detector ya manda un resumen cada 2 h.
# Contenedores caídos tampoco los avisa nadie más (p. ej. si se detiene el detector).
TIPOS_AVISO: FrozenSet[str] = frozenset({"fuente_caida", "fuente_ok", "contenedor_caido", "contenedor_ok"})


@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 8770
    db_path: Path = ROOT / "panel.db"
    netwatch_url: str = "http://127.0.0.1:8765"
    camaras_url: str = "http://127.0.0.1:8080"
    go2rtc_url: str = ""
    camaras_data: Path = ROOT / "data"
    fotos_remotas: bool = False   # True: las capturas se piden por HTTP a gestorCamaras
    consumo_cmd: str = ""
    recolectar_cada: int = 15
    telegram_token: str = ""
    telegram_chat_id: str = ""
    ntfy_url: str = ""
    luces_archivo: Path = ROOT / "data" / "devices.json"  # focos Tuya (tinytuya wizard); ver docs/LUCES.md
    docker_sock: str = "/var/run/docker.sock"  # para ver los contenedores; vacío = no consultar
    avisar: FrozenSet[str] = TIPOS_AVISO
    camaras_internas: bool = False
    go2rtc_interno_url: str = "http://127.0.0.1:1984"
    admin_pin: str = ""
    max_camaras: int = 32
    max_sesiones: int = 2
    sesion_caduca: int = 60
    vigilar_cada: int = 10
    caida_tras: int = 45
    onvif_timeout: float = 5.0
    camaras_iniciales: str = ""
    interno_token: str = ""       # secreto del detector (GET /api/interno/camaras)
    red_interna: bool = False     # True: la red la mide la sonda (sonda/) y la procesa panel-home; ver docs/RED.md
    red_token: str = ""           # secreto compartido con la sonda (POST /api/interno/red)
    oui_archivo: Path = ROOT / "data" / "oui.txt"   # fabricantes por MAC (se descarga solo)
    clima_ciudad: str = ""        # Open-Meteo: ciudad (se geocodifica una vez) o lat/lon exactos
    clima_lat: Optional[float] = None
    clima_lon: Optional[float] = None

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

    def _entero(clave: str, minimo: int | None = None) -> int | None:
        val = _obtener(clave)
        if not val:
            return None
        try:
            n = int(val)
        except ValueError:
            raise ValueError(f"{clave} debe ser un entero válido, valor recibido: {val!r}")
        if minimo is not None:
            return max(minimo, n)
        return n

    def _decimal(clave: str, minimo: float | None = None) -> float | None:
        val = _obtener(clave)
        if not val:
            return None
        try:
            f = float(val)
        except ValueError:
            raise ValueError(f"{clave} debe ser un número válido, valor recibido: {val!r}")
        if minimo is not None:
            return max(minimo, f)
        return f

    def _booleano(clave: str) -> bool | None:
        val = _obtener(clave)
        if not val:
            return None
        return val.lower() in ("1", "si", "sí", "true", "yes")

    val = _obtener("PANEL_HOST")
    if val:
        kwargs["host"] = val

    n_port = _entero("PANEL_PORT")
    if n_port is not None:
        kwargs["port"] = n_port

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

    val = _obtener("LUCES_ARCHIVO")
    if val:
        kwargs["luces_archivo"] = Path(val).expanduser()

    if "DOCKER_SOCK" in env:
        kwargs["docker_sock"] = _obtener("DOCKER_SOCK")

    b_fotos = _booleano("FOTOS_REMOTAS")
    if b_fotos is not None:
        kwargs["fotos_remotas"] = b_fotos

    val = _obtener("CONSUMO_CMD")
    if val:
        kwargs["consumo_cmd"] = val

    n_recol = _entero("RECOLECTAR_CADA", minimo=5)
    if n_recol is not None:
        kwargs["recolectar_cada"] = n_recol

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

    b_cam_int = _booleano("CAMARAS_INTERNAS")
    if b_cam_int is not None:
        kwargs["camaras_internas"] = b_cam_int

    val = _obtener("GO2RTC_INTERNO_URL")
    if val:
        kwargs["go2rtc_interno_url"] = val.rstrip("/")

    val = _obtener("ADMIN_PIN")
    if val:
        kwargs["admin_pin"] = val

    n_max_cam = _entero("MAX_CAMARAS", minimo=1)
    if n_max_cam is not None:
        kwargs["max_camaras"] = n_max_cam

    n_max_ses = _entero("MAX_SESIONES", minimo=1)
    if n_max_ses is not None:
        kwargs["max_sesiones"] = n_max_ses

    n_ses_cad = _entero("SESION_CADUCA", minimo=10)
    if n_ses_cad is not None:
        kwargs["sesion_caduca"] = n_ses_cad

    n_vig = _entero("VIGILAR_CADA", minimo=2)
    if n_vig is not None:
        kwargs["vigilar_cada"] = n_vig

    n_caida = _entero("CAIDA_TRAS", minimo=5)
    if n_caida is not None:
        kwargs["caida_tras"] = n_caida

    f_onvif = _decimal("ONVIF_TIMEOUT", minimo=1.0)
    if f_onvif is not None:
        kwargs["onvif_timeout"] = f_onvif

    val = _obtener("INTERNO_TOKEN")
    if val:
        kwargs["interno_token"] = val

    val = _obtener("CAMARAS")
    if val:
        kwargs["camaras_iniciales"] = val

    b_red = _booleano("RED_INTERNA")
    if b_red is not None:
        kwargs["red_interna"] = b_red

    val = _obtener("RED_TOKEN")
    if val:
        kwargs["red_token"] = val

    val = _obtener("OUI_ARCHIVO")
    if val:
        kwargs["oui_archivo"] = Path(val).expanduser()

    val = _obtener("CLIMA_CIUDAD")
    if val:
        kwargs["clima_ciudad"] = val
    for clave, campo in (("CLIMA_LAT", "clima_lat"), ("CLIMA_LON", "clima_lon")):
        n = _decimal(clave)
        if n is not None:
            kwargs[campo] = n

    # Sin NetWatch, los avisos de la red los manda panel-home (salvo que PANEL_AVISAR diga otra cosa)
    if "avisar" not in kwargs:
        extra = (AVISOS_RED if kwargs.get("red_interna") else frozenset()) | \
                (AVISOS_CAMARAS if kwargs.get("camaras_internas") else frozenset())
        if extra:
            kwargs["avisar"] = TIPOS_AVISO | extra

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
