"""Sesiones de video y puente WebSocket hacia go2rtc (solo biblioteca estándar)."""
from __future__ import annotations

import secrets
import socket
import threading
import time
from typing import Callable, Dict, List
from urllib.parse import quote, urlparse


class SinLugar(Exception):
    """No hay lugar para otra sesión; `info` lista las abiertas."""

    def __init__(self, info: List[dict]):
        super().__init__("sin lugar")
        self.info = info


class Sesiones:
    def __init__(self, maximo: int = 2, caduca: float = 60, reloj: Callable[[], float] = time.time):
        self.maximo = maximo
        self.caduca = caduca
        self._reloj = reloj
        self._sesiones: Dict[str, dict] = {}
        self._candado = threading.Lock()

    def _limpiar(self) -> None:
        ahora = self._reloj()
        for sid, s in list(self._sesiones.items()):
            if ahora - s["visto"] > self.caduca:
                del self._sesiones[sid]

    def abrir(self) -> dict:
        with self._candado:
            self._limpiar()
            ahora = self._reloj()
            if len(self._sesiones) >= self.maximo:
                raise SinLugar([{"desde": s["inicio"], "visto": s["visto"]}
                                for s in self._sesiones.values()])
            sid = secrets.token_urlsafe(12)
            self._sesiones[sid] = {"inicio": ahora, "visto": ahora}
            return {"id": sid, "maximo": self.maximo}

    def latido(self, sid: str) -> str:
        with self._candado:
            self._limpiar()
            s = self._sesiones.get(sid)
            if not s:
                return "expulsada"
            s["visto"] = self._reloj()
            return "ok"

    def salir(self, sid: str) -> None:
        with self._candado:
            self._sesiones.pop(sid, None)

    def valida(self, sid: str) -> bool:
        with self._candado:
            self._limpiar()
            return sid in self._sesiones


def _leer_cabecera(sock: socket.socket, limite: int = 65536) -> bytes:
    """Lee hasta \\r\\n\\r\\n (puede traer bytes extra después)."""
    datos = b""
    while b"\r\n\r\n" not in datos and len(datos) < limite:
        trozo = sock.recv(4096)
        if not trozo:
            break
        datos += trozo
    return datos


def _copiar(origen: socket.socket, destino: socket.socket) -> None:
    try:
        while True:
            datos = origen.recv(65536)
            if not datos:
                break
            destino.sendall(datos)
    except OSError:
        pass
    finally:
        # Despierta al otro hilo para que termine
        for s in (origen, destino):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def puente_websocket(handler, go2rtc_url: str, src: str, timeout: float = 10.0) -> None:
    cab = handler.headers
    if "websocket" not in (cab.get("Upgrade") or "").lower() or not cab.get("Sec-WebSocket-Key"):
        handler.send_error(400, "Se esperaba un WebSocket")
        return
    u = urlparse(go2rtc_url)
    host = u.hostname or "127.0.0.1"
    puerto = u.port or 80
    try:
        remoto = socket.create_connection((host, puerto), timeout=timeout)
    except OSError:
        handler.send_error(502, "go2rtc no responde")
        return
    cliente = handler.connection
    try:
        lineas = [
            "GET /api/ws?src=%s HTTP/1.1" % quote(src, safe=""),
            "Host: %s:%d" % (host, puerto),
            "Origin: http://%s:%d" % (host, puerto),
            "Upgrade: websocket",
            "Connection: Upgrade",
            "Sec-WebSocket-Key: %s" % cab.get("Sec-WebSocket-Key"),
            "Sec-WebSocket-Version: %s" % (cab.get("Sec-WebSocket-Version") or "13"),
        ]
        for nombre in ("Sec-WebSocket-Protocol", "Sec-WebSocket-Extensions"):
            if cab.get(nombre):
                lineas.append("%s: %s" % (nombre, cab.get(nombre)))
        try:
            remoto.sendall(("\r\n".join(lineas) + "\r\n\r\n").encode("latin-1"))
            resp = _leer_cabecera(remoto)
        except OSError:
            resp = b""
        if not resp.split(b"\r\n", 1)[0].split(b" ")[1:2] == [b"101"]:
            handler.send_error(502, "go2rtc rechazó el WebSocket")
            return
        remoto.settimeout(None)
        handler.wfile.flush()
        cliente.sendall(resp)  # 101 y lo que haya llegado pegado
        hilo = threading.Thread(target=_copiar, args=(remoto, cliente), daemon=True)
        hilo.start()
        _copiar(cliente, remoto)
        hilo.join(2)
    finally:
        try:
            remoto.close()
        except OSError:
            pass
        handler.close_connection = True
