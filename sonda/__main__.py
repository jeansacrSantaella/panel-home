"""python3 -m sonda [--panel URL] [--token TOKEN] [--nombre N] [--log ARCHIVO] [--env .env] [--sin-velocidad] [--verbose]

Lee el .env de la raíz del repo (RED_TOKEN, PANEL_URL, SONDA_NOMBRE, SONDA_LOG) sin pisar el entorno;
el panel por defecto es http://127.0.0.1:8770 (la máquina donde corre Docker)."""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import platform
import sys
import threading
from pathlib import Path

from .sonda import Sonda

RAIZ = Path(__file__).resolve().parent.parent


def leer_env(ruta: Path, env: dict) -> dict:
    """Lee un archivo .env y carga variables en env si no existen previamente."""
    cargadas = {}
    if not ruta.is_file():
        return cargadas
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "=" in linea:
            k, v = linea.split("=", 1)
            k, v = k.strip(), v.strip().strip('"\'')
            if k and k not in env:
                env[k] = v
                cargadas[k] = v
    return cargadas


def main(argv=None) -> int:
    # Procesar --env antes de argparse
    args_raw = argv if argv is not None else sys.argv[1:]
    env_path = RAIZ / ".env"
    i = 0
    while i < len(args_raw):
        if args_raw[i] == "--env" and i + 1 < len(args_raw):
            env_path = Path(args_raw[i + 1])
            break
        i += 1
    
    cargadas = leer_env(env_path, os.environ)

    p = argparse.ArgumentParser(prog="sonda", description="Sonda de red de panel-home")
    p.add_argument("--panel", default=os.environ.get("PANEL_URL", "http://127.0.0.1:8770"), help="URL del panel (o PANEL_URL)")
    p.add_argument("--token", default=os.environ.get("RED_TOKEN"), help="secreto compartido (o RED_TOKEN)")
    p.add_argument("--nombre", default=os.environ.get("SONDA_NOMBRE") or platform.node() or "sonda")
    p.add_argument("--env", help=argparse.SUPPRESS)
    p.add_argument("--log", default=os.environ.get("SONDA_LOG"), help="archivo de log")
    p.add_argument("--sin-velocidad", action="store_true", help="no medir la velocidad")
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args(argv)

    # Quitar / final del panel
    if a.panel:
        a.panel = a.panel.rstrip("/")

    # Configurar logging (consola + archivo rotativo si corresponde)
    nivel = logging.DEBUG if a.verbose else logging.INFO
    handlers = []
    
    # Consola (si sys.stdout está disponible, ej. no estamos en pythonw)
    if sys.stdout is not None:
        consola = logging.StreamHandler(sys.stdout)
        consola.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S"))
        handlers.append(consola)

    # Archivo de log: --log/SONDA_LOG o data/sonda.log (con pythonw es la única salida)
    log_path = Path(a.log) if a.log else RAIZ / "data" / "sonda.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        archivo = logging.handlers.RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        archivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        handlers.append(archivo)
    except OSError as e:
        if sys.stderr is not None:
            print(f"No pude abrir el log {log_path}: {e}", file=sys.stderr)

    logging.basicConfig(level=nivel, handlers=handlers, force=True)
    log = logging.getLogger("sonda")

    if not a.token or not a.panel:
        msg = "Falta el token (--token o RED_TOKEN) o la URL del panel (--panel o PANEL_URL)."
        if sys.stderr is not None:  # con pythonw no hay consola
            print(msg, file=sys.stderr)
        log.error(msg)
        return 2

    # Verificar si el token vino del .env
    token_en_env = cargadas.get("RED_TOKEN") == a.token

    log.info("sonda '%s' enviando a %s (so: %s, token_env: %s)", a.nombre, a.panel, platform.system(), token_en_env)
    
    sonda = Sonda(a.panel, a.token, a.nombre, con_velocidad=not a.sin_velocidad)
    parar = threading.Event()
    try:
        sonda.correr(parar)
    except KeyboardInterrupt:
        parar.set()
        log.info("sonda detenida")
    return 0


if __name__ == "__main__":
    sys.exit(main())
