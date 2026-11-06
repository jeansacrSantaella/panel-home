"""Módulo de lectura de métricas e información del sistema.

Lee estadísticas de hardware, sistema operativo y contenedores Docker
accediendo a los pseudo-archivos del sistema (/proc, /sys) y la API de Docker.
"""
from __future__ import annotations

import glob
import http.client
import json
import os
import socket
import time

# Variable global para almacenar la muestra previa de CPU (total, idle)
_previo: tuple[int, int] | None = None


class _UnixHTTPConnection(http.client.HTTPConnection):
    """Conexión HTTP a través de un socket UNIX local."""

    def __init__(self, socket_path: str, timeout: float = 3.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        """Crea y conecta el socket de tipo AF_UNIX."""
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def leer_cpu() -> float | None:
    """Calcula el porcentaje de uso de CPU entre la llamada actual y la anterior.

    Returns:
        Porcentaje redondeado a 1 decimal, o None si no hay lectura previa o falla.
    """
    global _previo

    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            primera_linea = f.readline()

        if not primera_linea.startswith("cpu "):
            return None

        partes = primera_linea.split()
        valores = [int(x) for x in partes[1:]]

        total = sum(valores)
        # Campos 4 y 5 (idle e iowait, base 1 -> índices 3 y 4 en la lista de valores)
        ocio = valores[3] + valores[4]

        if _previo is None:
            _previo = (total, ocio)
            return None

        prev_total, prev_ocio = _previo
        _previo = (total, ocio)

        diff_total = total - prev_total
        diff_ocio = ocio - prev_ocio

        if diff_total <= 0:
            return None

        uso = ((diff_total - diff_ocio) / diff_total) * 100.0
        return round(uso, 1)
    except (OSError, ValueError, IndexError):
        return None


def leer_ram() -> dict | None:
    """Obtiene la memoria RAM total, usada y libre en bytes desde /proc/meminfo.

    Returns:
        Diccionario con claves total, usado y libre, o None si falla.
    """
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            contenido = f.read()

        mem_total = None
        mem_avail = None

        for linea in contenido.splitlines():
            if linea.startswith("MemTotal:"):
                mem_total = int(linea.split()[1]) * 1024
            elif linea.startswith("MemAvailable:"):
                mem_avail = int(linea.split()[1]) * 1024

        if mem_total is None or mem_avail is None:
            return None

        return {
            "total": mem_total,
            "usado": mem_total - mem_avail,
            "libre": mem_avail,
        }
    except (OSError, ValueError, IndexError):
        return None


def leer_carga() -> list[float] | None:
    """Obtiene la carga del sistema en los últimos 1, 5 y 15 minutos desde /proc/loadavg.

    Returns:
        Lista de 3 flotantes con la carga promedio, o None si falla.
    """
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as f:
            contenido = f.read()

        partes = contenido.split()
        return [float(partes[0]), float(partes[1]), float(partes[2])]
    except (OSError, ValueError, IndexError):
        return None


def leer_uptime() -> int | None:
    """Obtiene el tiempo encendido del sistema en segundos desde /proc/uptime.

    Returns:
        Segundos en valor entero, o None si falla.
    """
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            contenido = f.read()

        primer_valor = contenido.split()[0]
        return int(float(primer_valor))
    except (OSError, ValueError, IndexError):
        return None


def leer_temperatura() -> float | None:
    """Obtiene la temperatura máxima registrada en las zonas térmicas del sistema.

    Returns:
        Temperatura máxima en grados Celsius redondeada a 1 decimal, o None si no hay datos.
    """
    try:
        archivos = glob.glob("/sys/class/thermal/thermal_zone*/temp")
        if not archivos:
            return None

        temperaturas = []
        for ruta in archivos:
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    valor_raw = f.read().strip()
                    temperaturas.append(float(valor_raw) / 1000.0)
            except (OSError, ValueError):
                continue

        if not temperaturas:
            return None

        return round(max(temperaturas), 1)
    except (OSError, ValueError, IndexError):
        return None


def leer_contenedores(sock: str) -> list[dict] | None:
    """Consulta la API de Docker mediante socket UNIX para listar los contenedores.

    Args:
        sock: Ruta al socket UNIX de Docker.

    Returns:
        Lista de diccionarios con la información del contenedor ordenada por nombre,
        o None si el socket no existe o falla la comunicación.
    """
    if not sock or not os.path.exists(sock):
        return None

    try:
        conn = _UnixHTTPConnection(sock, timeout=3.0)
        conn.request("GET", "/containers/json?all=1", headers={"Host": "docker"})
        res = conn.getresponse()

        if res.status != 200:
            conn.close()
            return None

        cuerpo = res.read()
        conn.close()

        datos = json.loads(cuerpo.decode("utf-8"))
        if not isinstance(datos, list):
            return None

        resultado = []
        for c in datos:
            nombres = c.get("Names", [])
            raw_nombre = nombres[0] if nombres else ""
            nombre = raw_nombre[1:] if raw_nombre.startswith("/") else raw_nombre

            imagen = c.get("Image", "")
            estado = c.get("State", "")
            status_str = c.get("Status", "")

            # Determinación de estado de salud basado en la cadena Status
            salud = None
            if "(healthy)" in status_str:
                salud = "healthy"
            elif "(unhealthy)" in status_str:
                salud = "unhealthy"
            elif "(health: starting)" in status_str:
                salud = "starting"

            resultado.append(
                {
                    "nombre": nombre,
                    "imagen": imagen,
                    "estado": estado,
                    "salud": salud,
                    "detalle": status_str,
                }
            )

        resultado.sort(key=lambda x: x["nombre"])
        return resultado
    except Exception:
        return None


def leer_sistema(sock: str = "") -> dict:
    """Recopila todo el estado del sistema en un único diccionario.

    Args:
        sock: Ruta opcional al socket UNIX de Docker.

    Returns:
        Diccionario con las lecturas de CPU, RAM, carga, uptime, temperatura,
        contenedores y timestamp actual.
    """
    try:
        cpu = leer_cpu()
    except (OSError, ValueError, IndexError):
        cpu = None

    try:
        nucleos = os.cpu_count()
    except (OSError, ValueError, IndexError):
        nucleos = None

    try:
        ram = leer_ram()
    except (OSError, ValueError, IndexError):
        ram = None

    try:
        carga = leer_carga()
    except (OSError, ValueError, IndexError):
        carga = None

    try:
        uptime = leer_uptime()
    except (OSError, ValueError, IndexError):
        uptime = None

    try:
        temperatura = leer_temperatura()
    except (OSError, ValueError, IndexError):
        temperatura = None

    try:
        contenedores = leer_contenedores(sock)
    except (OSError, ValueError, IndexError):
        contenedores = None

    return {
        "cpu": cpu,
        "nucleos": nucleos,
        "ram": ram,
        "carga": carga,
        "uptime": uptime,
        "temperatura": temperatura,
        "contenedores": contenedores,
        "ts": int(time.time()),
    }
