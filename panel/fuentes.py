"""Módulo para consultar fuentes de datos externas (NetWatch, cámaras, fotos y consumo)."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from panel.config import Config


class FuenteError(Exception):
    """Excepción generada cuando falla una fuente de datos externa."""


def get_json(url: str, timeout: int = 5) -> dict | list:
    """Realiza una petición HTTP GET esperando un JSON como respuesta."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        raise FuenteError(f"{url}: {e}")


def _seguro(fn):
    """Ejecuta una función y captura FuenteError devolviendo None."""
    try:
        return fn()
    except FuenteError:
        return None


def netwatch_resumen(cfg: Config) -> dict | None:
    """Obtiene el resumen del servicio NetWatch."""
    url = f"{cfg.netwatch_url.rstrip('/')}/api/summary"
    data = _seguro(lambda: get_json(url))
    return data if isinstance(data, dict) else None


def camaras_lista(cfg: Config) -> list | None:
    """Obtiene la lista de cámaras del gestor de cámaras."""
    url = f"{cfg.camaras_url.rstrip('/')}/api/camaras"
    data = _seguro(lambda: get_json(url))
    return data if isinstance(data, list) else None


def camaras_salud(cfg: Config) -> dict | None:
    """Obtiene el estado de salud de las cámaras."""
    url = f"{cfg.camaras_url.rstrip('/')}/api/salud"
    data = _seguro(lambda: get_json(url))
    return data if isinstance(data, dict) else None


FOTO = re.compile(
    r"^(?P<cam>[^_/]+)_(?P<h>\d\d)-(?P<m>\d\d)-(?P<s>\d\d)_(?P<clases>[\w-]+)\.jpg$"
)
REF = re.compile(r"^\d{4}-\d\d-\d\d/[\w.-]+\.jpg$")


def _archivos_del_dia(cfg: Config, dia: str) -> list[str] | None:
    """Obtiene la lista de nombres de archivo de foto de un día específico."""
    if getattr(cfg, "fotos_remotas", False):
        url = f"{cfg.camaras_url.rstrip('/')}/api/fotos?fecha={dia}"
        data = _seguro(lambda: get_json(url))
        if not isinstance(data, list):
            return None
        return [f for f in data if isinstance(f, str) and FOTO.match(f)]
    else:
        carpeta = cfg.camaras_data / "fotos" / dia
        if not carpeta.exists() or not carpeta.is_dir():
            return []
        archivos = []
        try:
            for archivo in carpeta.iterdir():
                if archivo.is_file() and FOTO.match(archivo.name):
                    archivos.append(archivo.name)
        except OSError:
            return []
        return archivos


def _captura(dia: str, nombre: str) -> dict | None:
    """Convierte el día y nombre de archivo en una estructura de captura."""
    m = FOTO.match(nombre)
    if not m:
        return None
    cam = m.group("cam")
    h_str, m_str, s_str = m.group("h"), m.group("m"), m.group("s")
    clases = m.group("clases").split("-")
    try:
        yyyy, mm, dd = map(int, dia.split("-"))
        dt_foto = datetime(yyyy, mm, dd, int(h_str), int(m_str), int(s_str))
    except ValueError:
        return None
    ts = int(time.mktime(dt_foto.timetuple()))
    return {
        "ts": ts,
        "camara": cam,
        "clases": clases,
        "ref": f"{dia}/{nombre}",
        "hora": f"{h_str}:{m_str}:{s_str}",
    }


def fotos_movimiento(
    cfg: Config, desde_ts: float, ahora: float | None = None
) -> list[dict]:
    """Busca fotos de movimiento generadas entre desde_ts y ahora."""
    if ahora is None:
        ahora = time.time()

    dt_ahora = datetime.fromtimestamp(ahora)
    dt_desde = datetime.fromtimestamp(desde_ts)
    fecha_ahora = dt_ahora.date()
    fecha_desde = dt_desde.date()

    fecha_inicio = max(fecha_desde, fecha_ahora - timedelta(days=7))

    resultado = []
    d = fecha_inicio
    while d <= fecha_ahora:
        dia_str = d.strftime("%Y-%m-%d")
        archivos = _archivos_del_dia(cfg, dia_str)
        if archivos is not None:
            for nombre in archivos:
                cap = _captura(dia_str, nombre)
                if cap and desde_ts < cap["ts"] <= ahora + 60:
                    resultado.append(cap)
        d += timedelta(days=1)

    resultado.sort(key=lambda x: x["ts"])
    return resultado


def capturas_del_dia(cfg: Config, dia: str) -> list[dict] | None:
    """Devuelve las capturas de movimiento de un día ordenadas por ts descendente."""
    if not re.fullmatch(r"\d{4}-\d\d-\d\d", dia):
        raise ValueError("fecha inválida")
    archivos = _archivos_del_dia(cfg, dia)
    if archivos is None:
        return None
    capturas = []
    for nombre in archivos:
        cap = _captura(dia, nombre)
        if cap is not None:
            capturas.append(cap)
    capturas.sort(key=lambda x: x["ts"], reverse=True)
    return capturas


def dias_con_capturas(cfg: Config) -> list[str]:
    """Retorna la lista de fechas con capturas registradas."""
    patron = re.compile(r"^\d{4}-\d\d-\d\d$")
    if getattr(cfg, "fotos_remotas", False):
        url = f"{cfg.camaras_url.rstrip('/')}/api/fotos/dias"
        data = _seguro(lambda: get_json(url))
        if not isinstance(data, list):
            return []
        return [d for d in data if isinstance(d, str) and patron.match(d)]
    else:
        carpeta = cfg.camaras_data / "fotos"
        if not carpeta.exists() or not carpeta.is_dir():
            return []
        dias = []
        try:
            for item in carpeta.iterdir():
                if item.is_dir() and patron.match(item.name):
                    dias.append(item.name)
        except OSError:
            return []
        dias.sort(reverse=True)
        return dias


def ruta_foto(cfg: Config, ref: str) -> Path | None:
    """Valida la referencia a una foto y retorna su ruta Path si existe."""
    if not ref or not REF.match(ref):
        return None
    base = (cfg.camaras_data / "fotos").resolve()
    p = (cfg.camaras_data / "fotos" / ref).resolve()
    try:
        p.relative_to(base)
    except ValueError:
        return None
    if p.is_file():
        return p
    return None


def leer_foto(cfg: Config, ref: str) -> bytes | None:
    """Obtiene el contenido binario de una foto según su referencia."""
    if not ref or not REF.match(ref):
        return None
    if getattr(cfg, "fotos_remotas", False):
        url = f"{cfg.camaras_url.rstrip('/')}/api/fotos/{ref}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return resp.read()
        except Exception:
            return None
        return None
    else:
        p = ruta_foto(cfg, ref)
        if p is None:
            return None
        try:
            return p.read_bytes()
        except Exception:
            return None


def leer_consumo(cfg: Config) -> dict[str, tuple[int, int]] | None:
    """Ejecuta el comando para obtener estadísticas de consumo de red."""
    if not cfg.consumo_cmd:
        return None
    try:
        res = subprocess.run(
            cfg.consumo_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if res.returncode != 0:
            return None
        data = json.loads(res.stdout)
        if not isinstance(data, dict):
            return None
        resultado = {}
        for equipo, val in data.items():
            if isinstance(val, dict) and "rx" in val and "tx" in val:
                try:
                    rx = int(val["rx"])
                    tx = int(val["tx"])
                    resultado[str(equipo).lower()] = (rx, tx)
                except (ValueError, TypeError):
                    continue
        return resultado
    except Exception:
        return None
