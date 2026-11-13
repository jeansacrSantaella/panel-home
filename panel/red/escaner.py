"""Escáner bajo demanda de un equipo: identidad, calidad de ping, TTL, DNS y puertos TCP abiertos."""
from __future__ import annotations

import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional

# Puertos comunes y su servicio habitual
PUERTOS_COMUNES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http", 110: "pop3", 135: "msrpc",
    139: "netbios", 143: "imap", 443: "https", 445: "smb", 548: "afp", 554: "rtsp", 631: "ipp",
    993: "imaps", 995: "pop3s", 1883: "mqtt", 3306: "mysql", 3389: "rdp", 5000: "upnp/http",
    5432: "postgres", 5900: "vnc", 6379: "redis", 7000: "airplay", 8000: "http-alt", 8008: "http-alt",
    8009: "chromecast", 8080: "http-proxy", 8443: "https-alt", 8888: "http-alt", 9100: "impresora",
    32400: "plex", 49152: "upnp", 62078: "iphone-sync",
}
PUERTOS_HTTP = {80, 5000, 7000, 8000, 8008, 8080, 8888, 32400}
MAX_PUERTOS = 5000
PINGS = 4
NOMBRE_DNS = "example.com"
PATRON_HOST = re.compile(r"[A-Za-z0-9.\-:]+")

# Pool para la búsqueda inversa de nombres (con tiempo máximo)
_pool_rdns = ThreadPoolExecutor(max_workers=8)


def parse_puertos(spec) -> list[int]:
    """'common', '1-1024' o una lista como '22,80,8000-8100'."""
    spec = (spec or "common").strip().lower()
    if spec == "common":
        return sorted(PUERTOS_COMUNES)
    puertos = set()
    for parte in (p.strip() for p in spec.split(",")):
        if not parte:
            continue
        a, _, b = parte.partition("-")
        if not a.isdigit() or (b and not b.isdigit()):
            raise ValueError(f"rango de puertos inválido: {parte}")
        lo, hi = int(a), int(b or a)
        if not 1 <= lo <= hi <= 65535:
            raise ValueError(f"puertos fuera de rango: {parte}")
        puertos.update(range(lo, hi + 1))
        if len(puertos) > MAX_PUERTOS:
            raise ValueError(f"como máximo {MAX_PUERTOS} puertos por escaneo")
    if not puertos:
        raise ValueError("no se indicaron puertos")
    return sorted(puertos)


def pista_so(ttl) -> Optional[str]:
    # Estima el sistema con el TTL inicial y sus saltos típicos.
    if ttl is None:
        return None
    if ttl <= 64:
        return "Linux, macOS, iOS o Android"
    if ttl <= 128:
        return "Windows"
    return "Equipo de red (router, impresora…)"


def nombre_servicio(puerto: int) -> str:
    try:
        return PUERTOS_COMUNES.get(puerto) or socket.getservbyport(puerto, "tcp")
    except OSError:
        return ""


def _leer_banner(sock: socket.socket, host: str, puerto: int) -> str:
    try:
        sock.settimeout(1.0)
        if puerto in PUERTOS_HTTP:
            sock.sendall(f"HEAD / HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
            lineas = sock.recv(1024).decode(errors="ignore").splitlines()
            server = next((l for l in lineas if l.lower().startswith("server:")), "")
            return " · ".join(x for x in (lineas[0] if lineas else "", server) if x)
        try:
            datos = sock.recv(256)
        except socket.timeout:
            return ""
        texto = datos.decode(errors="ignore").strip()
        return texto.splitlines()[0][:120] if texto else ""
    except Exception:
        return ""


def escanear_puerto(ip: str, puerto: int, timeout: float = 0.5) -> Optional[dict]:
    try:
        with socket.create_connection((ip, puerto), timeout=timeout) as s:
            banner = _leer_banner(s, ip, puerto)
    except Exception:
        return None
    return {"port": puerto, "service": nombre_servicio(puerto), "banner": banner}


def _quality(filas) -> Optional[dict]:
    """filas: [(ms, ok)] en orden -> latencia media, jitter y % de pérdida."""
    if not filas:
        return None
    ms = [f[0] for f in filas if f[1] and f[0] is not None]
    diffs = [abs(a - b) for a, b in zip(ms, ms[1:])]
    return {"avg": round(sum(ms) / len(ms), 1) if ms else None,
            "jitter": round(sum(diffs) / len(diffs), 1) if diffs else None,
            "loss": round(100 * (1 - sum(f[1] for f in filas) / len(filas)), 1)}


def _samples_from_times(tiempos, enviados: int) -> list:
    """Convierte los tiempos de respuesta de `enviados` pings en muestras para _quality()."""
    filas = [(t, 1) for t in tiempos]
    return filas + [(None, 0)] * max(0, enviados - len(filas))


def _mac_privada(mac: str) -> bool:
    """Bit "administrado localmente": típico de teléfonos y laptops con MAC aleatoria."""
    return bool(int(mac[:2], 16) & 2)


def _dns_inverso(ip: str, timeout: float = 2.0) -> Optional[str]:
    try:
        return _pool_rdns.submit(socket.gethostbyaddr, ip).result(timeout=timeout)[0]
    except Exception:
        return None


def _validar_lista(puertos: list) -> list[int]:
    """Lista de puertos ya dada (no texto): mismas reglas que parse_puertos."""
    try:
        valores = sorted({int(p) for p in puertos})
    except (TypeError, ValueError) as exc:
        raise ValueError("puertos inválidos") from exc
    if not valores:
        raise ValueError("no se indicaron puertos")
    if len(valores) > MAX_PUERTOS:
        raise ValueError(f"como máximo {MAX_PUERTOS} puertos por escaneo")
    if valores[0] < 1 or valores[-1] > 65535:
        raise ValueError("puertos fuera de rango")
    return valores


class Escaner:
    def __init__(self, red, fabricante: Optional[Callable] = None, ping_series: Optional[Callable] = None,
                 dns_query: Optional[Callable] = None, resolver_nombre: Optional[Callable] = None):
        self._red = red
        self._fabricante = fabricante or (lambda mac: None)
        # Si no se inyectan, sonda.medir se importa al escanear (no al cargar el módulo)
        self._ping = ping_series
        self._dns = dns_query
        self._resolver = resolver_nombre or socket.gethostbyname

    def escanear(self, host: Optional[str], puertos=None) -> dict:
        host = (host or "").strip()
        if not host or len(host) > 253 or not PATRON_HOST.fullmatch(host):
            raise ValueError("host inválido")
        if isinstance(puertos, (list, tuple, set)):
            lista = _validar_lista(list(puertos))
        else:
            lista = parse_puertos(puertos)

        ping, dns = self._ping, self._dns
        if ping is None or dns is None:
            from sonda.medir import dns_query, ping_series
            ping = ping or ping_series
            dns = dns or dns_query

        pasos = []
        t0 = time.time()
        try:
            ip = self._resolver(host)
        except OSError as exc:
            raise ValueError(f"no se pudo resolver {host}") from exc
        pasos.append(f"Resolución de nombre: {host} → {ip}")

        nombre = _dns_inverso(ip)
        pasos.append("DNS inverso: " + (nombre or "sin nombre"))

        tiempos, ttl = ping(ip, PINGS)
        calidad_ping = _quality(_samples_from_times(tiempos, PINGS))
        pasos.append(f"Ping x{PINGS}: {100 - calidad_ping['loss']:.0f} % de respuestas" + (f", TTL {ttl}" if ttl else ""))

        # La identidad sale de la base de equipos (alimentada por la tabla ARP)
        equipo = next((e for e in self._red.equipos() if e.get("ip") == ip), None)
        mac = equipo.get("mac") if equipo else None
        conocido = {k: equipo.get(k) for k in ("alias", "hostname", "network", "first_seen")} if equipo else None
        pasos.append("Tabla ARP: " + (mac or "no está en la red local"))

        dns_ok, dns_ms = dns(ip, name=NOMBRE_DNS, timeout=1.0)
        pasos.append("Servidor DNS: " + (f"responde en {dns_ms:.1f} ms" if dns_ok else "no responde"))

        with ThreadPoolExecutor(min(256, len(lista))) as pool:
            abiertos = [r for r in pool.map(lambda p: escanear_puerto(ip, p), lista) if r]
        pasos.append(f"Puertos TCP: {len(lista)} probados, {len(abiertos)} abiertos")

        return {
            "host": host, "ip": ip, "hostname": nombre, "mac": mac,
            "vendor": self._fabricante(mac) if mac else None,
            "random_mac": bool(mac and _mac_privada(mac)),
            "known": conocido,
            "ping": calidad_ping, "ttl": ttl, "os_hint": pista_so(ttl),
            "dns": {"ok": dns_ok, "ms": round(dns_ms, 1) if dns_ms else None},
            "ports_scanned": len(lista), "open": abiertos,
            "steps": pasos, "elapsed": round(time.time() - t0, 1),
        }
