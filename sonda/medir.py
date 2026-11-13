"""Mediciones de red (port de network/ de NetWatch): macOS, Linux y Windows, solo biblioteca estándar."""
from __future__ import annotations

import platform
import random
import re
import socket
import struct
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, Optional, Tuple

SISTEMA = platform.system()
ES_WINDOWS = SISTEMA == "Windows"
ES_MAC = SISTEMA == "Darwin"

# En Windows evita que cada comando abra una ventana de consola.
_FLAGS = {"creationflags": 0x08000000} if ES_WINDOWS else {}

_PATRONES_ARP = [
    r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})",    # macOS/Linux arp -an
    r"^\s*(\d+\.\d+\.\d+\.\d+)\s.*lladdr\s+([0-9a-fA-F]{1,2}(?::[0-9a-fA-F]{1,2}){5})",  # ip neigh
    r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\b",        # Windows arp -a
]
_IGNORADAS = ("ff:ff:ff:ff:ff:ff", "01:00:5e", "33:33")  # broadcast y multicast

_pool_rdns = ThreadPoolExecutor(4)


def _decodificar(datos: bytes) -> str:
    """Decodifica la salida de un comando; en Windows usa la página OEM de la consola (cp850 en español)."""
    if ES_WINDOWS:
        try:
            return datos.decode("oem", errors="replace")
        except LookupError:  # sin códec "oem"
            return datos.decode("cp850", errors="replace")
    return datos.decode("utf-8", errors="replace")


def _ejecutar(cmd: List[str], timeout: float) -> Tuple[int, str]:
    """Corre un comando y devuelve (código de salida, salida estándar ya decodificada)."""
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, **_FLAGS)
    return r.returncode, _decodificar(r.stdout or b"")


def _correr(cmd: List[str], timeout: float) -> str:
    return _ejecutar(cmd, timeout)[1]


def _espera(timeout: float) -> str:
    """Argumento de espera de ping: ms en macOS y Windows, segundos en Linux."""
    if ES_MAC or ES_WINDOWS:
        return str(int(timeout * 1000))
    return str(max(1, int(round(timeout))))


def _cmd_ping(host: str, cuenta: int, timeout: float, intervalo: bool = False) -> List[str]:
    if ES_WINDOWS:
        return ["ping", "-n", str(cuenta), "-w", _espera(timeout), host]
    cmd = ["ping", "-c", str(cuenta)]
    if intervalo:
        cmd += ["-i", "0.2"]
    return cmd + ["-W", _espera(timeout), host]


_RE_TIEMPO = re.compile(r"(?:time|tiempo)\s*[=<]\s*([\d.,]+)", re.I)
_RE_TTL = re.compile(r"\bttl\s*=\s*(\d+)", re.I)


def _respuestas_ping(texto: str) -> List[Tuple[Optional[float], int]]:
    """Líneas de respuesta real (con TTL=n): [(tiempo ms o None, ttl)]. 'TTL expirado' no cuenta."""
    res = []
    for linea in texto.splitlines():
        ttl = _RE_TTL.search(linea)
        if not ttl:
            continue
        t = _RE_TIEMPO.search(linea)
        res.append((float(t.group(1).replace(",", ".")) if t else None, int(ttl.group(1))))
    return res


def parse_ping(texto: str) -> Tuple[List[float], Optional[int]]:
    """Tiempos y TTL de la salida de ping (Unix, Windows en español o inglés)."""
    res = _respuestas_ping(texto)
    return [t for t, _ in res if t is not None], (res[0][1] if res else None)


def ping(host: str, timeout: float = 1.0) -> Tuple[bool, Optional[float]]:
    t0 = time.time()
    try:
        rc, salida = _ejecutar(_cmd_ping(host, 1, timeout), timeout + 2)
    except Exception:
        return False, None
    res = _respuestas_ping(salida)
    if ES_WINDOWS:  # el código de salida es 0 aunque el destino sea inalcanzable: manda el TTL
        if not res:
            return False, None
    elif rc != 0:
        return False, None
    if res and res[0][0] is not None:
        return True, res[0][0]
    return True, (time.time() - t0) * 1000


def ping_series(host: str, count: int = 4) -> Tuple[List[float], Optional[int]]:
    """Varios pings seguidos: tiempos de respuesta y TTL."""
    try:
        return parse_ping(_correr(_cmd_ping(host, count, 1.0, intervalo=True), count + 5))
    except Exception:
        return [], None


def _consulta_dns(qid: int, nombre: str) -> bytes:
    paquete = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    paquete += b"".join(bytes([len(p)]) + p.encode() for p in nombre.split(".")) + b"\0"
    return paquete + struct.pack(">HH", 1, 1)


def _respuesta_valida(datos: bytes, qid: int) -> bool:
    if len(datos) < 8:
        return False
    rid, flags, _, respuestas = struct.unpack(">HHHH", datos[:8])
    return rid == qid and (flags & 0xF) == 0 and respuestas > 0


def dns_query(server: str, name: str = "example.com", timeout: float = 2.0) -> Tuple[bool, Optional[float]]:
    qid = random.randint(0, 65535)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.time()
    try:
        s.sendto(_consulta_dns(qid, name), (server, 53))
        datos, _ = s.recvfrom(512)
    except Exception:
        return False, None
    finally:
        s.close()
    ok = _respuesta_valida(datos, qid)
    return ok, (time.time() - t0) * 1000 if ok else None


def _es_virtual(ip: str) -> bool:
    """IP de adaptador virtual (WSL/Docker/Hyper-V en 172.16.0.0/12) o autoasignada 169.254.x."""
    try:
        o = [int(x) for x in ip.split(".")]
    except ValueError:
        return False
    return (o[0] == 172 and 16 <= o[1] <= 31) or (o[0] == 169 and o[1] == 254)


def elegir_ip_local(ip_udp: Optional[str], gw: Optional[str], candidatas: Iterable[str]) -> Optional[str]:
    """Si la IP de salida es virtual, prefiere la candidata en el /24 del gateway; si no, la deja."""
    if not ip_udp or not gw or not _es_virtual(ip_udp):
        return ip_udp
    prefijo = gw.rsplit(".", 1)[0] + "."
    for ip in candidatas:
        if ip.startswith(prefijo) and not _es_virtual(ip):
            return ip
    return ip_udp


_RE_INTERFAZ_ARP = re.compile(r"^\s*(?:Interfaz|Interface)\s*:\s*(\d+\.\d+\.\d+\.\d+)", re.I | re.M)


def parse_interfaces_arp(texto: str) -> List[str]:
    """IPs de las secciones 'Interfaz: x.x.x.x --- 0x5' de arp -a."""
    return _RE_INTERFAZ_ARP.findall(texto)


def local_ip() -> Optional[str]:
    # connect() en UDP solo elige la interfaz de salida; no envía datos.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()
    if ES_WINDOWS and _es_virtual(ip):
        try:
            return elegir_ip_local(ip, gateway(), parse_interfaces_arp(_correr(["arp", "-a"], 5)))
        except Exception:
            pass
    return ip


_RE_RUTA_DEFECTO = re.compile(
    r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s+\d+\.\d+\.\d+\.\d+\s+(\d+)\b", re.M)


def parse_route_print(texto: str) -> Optional[str]:
    """Gateway de la ruta 0.0.0.0 de menor métrica en 'route print' (ignora 'En vínculo'/'On-link')."""
    rutas = [(int(m.group(2)), m.group(1)) for m in _RE_RUTA_DEFECTO.finditer(texto)]
    return min(rutas)[1] if rutas else None


def gateway() -> Optional[str]:
    try:
        if ES_WINDOWS:
            return parse_route_print(_correr(["route", "print", "0.0.0.0"], 5))
        if ES_MAC:
            m = re.search(r"gateway:\s*(\S+)", _correr(["route", "-n", "get", "default"], 3))
        else:
            m = re.search(r"via\s+(\S+)", _correr(["ip", "route", "show", "default"], 3))
        return m.group(1) if m else None
    except Exception:
        return None


def _normalizar_mac(texto: str) -> Optional[str]:
    partes = re.split(r"[:-]", texto)
    if len(partes) != 6:
        return None
    return ":".join(p.zfill(2) for p in partes).lower()


def parse_arp(salidas: Iterable[str]) -> Dict[str, str]:
    """Salidas de arp / ip neigh -> {mac en minúsculas con ':': ip}."""
    halladas: Dict[str, str] = {}
    for salida in salidas:
        for linea in salida.splitlines():
            if "incomplete" in linea.lower() or "failed" in linea.lower():
                continue
            for patron in _PATRONES_ARP:
                m = re.search(patron, linea)
                if not m:
                    continue
                mac = _normalizar_mac(m.group(2))
                if mac and mac != "00:00:00:00:00:00" and not mac.startswith(_IGNORADAS):
                    halladas[mac] = m.group(1)
                break
    return halladas


def read_arp() -> Dict[str, str]:
    comandos = [["arp", "-a"]] if ES_WINDOWS else [["arp", "-an"], ["ip", "neigh"]]
    salidas = []
    for cmd in comandos:
        try:
            salidas.append(_correr(cmd, 5))
        except Exception:
            pass
    return parse_arp(salidas)


def reverse_dns(ip: str, timeout: float = 2.0) -> Optional[str]:
    try:
        return _pool_rdns.submit(socket.gethostbyaddr, ip).result(timeout=timeout)[0]
    except Exception:
        return None


def fetch(url: str, timeout: float = 10, data: Optional[bytes] = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Mozilla/5.0 sonda"})
    return urllib.request.urlopen(req, timeout=timeout).read()
