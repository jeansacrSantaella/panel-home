"""Cliente de go2rtc (urllib) y sincronizador que mantiene registradas las cámaras."""
from __future__ import annotations

import json
import logging
from urllib.parse import urlencode, quote
import urllib.request
from urllib.error import HTTPError

log = logging.getLogger("panel.camaras")
SCRIPTS = ("video-stream.js", "video-rtc.js")


class Go2rtcError(Exception):
    """Error de comunicación con go2rtc. rechazo=True si go2rtc respondió con un error HTTP."""
    def __init__(self, mensaje: str, rechazo: bool = False):
        super().__init__(mensaje)
        self.rechazo = rechazo


class Go2rtc:
    def __init__(self, url: str, timeout: float = 5, abrir=None):
        # url sin "/" final; abrir = función(urllib.request.Request, timeout) -> respuesta con .read() y .status
        # (por defecto urllib.request.urlopen); se inyecta en las pruebas
        self.url = url.rstrip("/")
        self.timeout = timeout
        self._abrir = abrir or urllib.request.urlopen
        self._scripts_cache = {}

    def _pedir(self, metodo: str, ruta: str, params: dict | None = None, timeout=None) -> bytes:
        # urlencode de params; cualquier error -> Go2rtcError
        t = timeout if timeout is not None else self.timeout
        url_completa = f"{self.url}{ruta}"
        if params:
            url_completa += f"?{urlencode(params)}"
        
        req = urllib.request.Request(url_completa, method=metodo)
        try:
            with self._abrir(req, timeout=t) as resp:
                estado = getattr(resp, "status", 200) or 200
                datos = resp.read()
        except Exception as e:
            raise Go2rtcError(f"Error en petición a go2rtc ({metodo} {ruta}): {e}", isinstance(e, HTTPError)) from e
        if estado >= 400:
            raise Go2rtcError(f"go2rtc respondió HTTP {estado} ({metodo} {ruta})", rechazo=True)
        return datos

    def streams(self) -> dict | None:
        # GET /api/streams -> dict JSON; None si falla
        try:
            data = self._pedir("GET", "/api/streams")
            return json.loads(data.decode("utf-8"))
        except Exception:
            return None

    def registrar(self, cid: str, fuente: str) -> bool | None:
        # PUT /api/streams?name=cid&src=fuente. True ok; False si go2rtc la rechazó (HTTP); None si no hubo conexión.
        # luego PUT /api/preload?src=cid&query=video&audio; si ese falla solo log.warning y sigue True
        try:
            self._pedir("PUT", "/api/streams", {"name": cid, "src": fuente})
        except Go2rtcError as e:
            log.warning("go2rtc rechazó la cámara %s: %s", cid, e)
            return False if e.rechazo else None

        try:
            self._pedir("PUT", "/api/preload", {"src": cid, "query": "video&audio"})
        except Go2rtcError as e:
            log.warning("go2rtc no activó preload para %s: %s", cid, e)

        return True

    def quitar(self, cid: str) -> None:
        # DELETE /api/streams?src=cid; errores solo log
        try:
            self._pedir("DELETE", "/api/streams", {"src": cid})
        except Go2rtcError as e:
            log.warning("No se pudo quitar %s de go2rtc: %s", cid, e)

    def foto(self, cid: str, timeout: float = 15) -> bytes | None:
        # GET /api/frame.jpeg?src=cid
        try:
            return self._pedir("GET", "/api/frame.jpeg", {"src": cid}, timeout=timeout)
        except Go2rtcError:
            return None

    def script(self, nombre: str) -> bytes:
        # solo SCRIPTS (si no ValueError); GET /{nombre}; caché en memoria
        if nombre not in SCRIPTS:
            raise ValueError(f"Script no permitido: {nombre}")
        if nombre not in self._scripts_cache:
            try:
                self._scripts_cache[nombre] = self._pedir("GET", f"/{nombre}")
            except Go2rtcError as e:
                raise Go2rtcError(f"No se pudo obtener el script {nombre}: {e}") from e
        return self._scripts_cache[nombre]


class Sincronizador:
    """Mantiene en go2rtc todas las cámaras (también tras reiniciarlo)."""
    def __init__(self, go2rtc: Go2rtc, obtener_camaras, fuente):
        # obtener_camaras() -> list[dict] completas; fuente(c) -> str (registro.fuente_rtsp)
        self._go2rtc = go2rtc
        self._obtener_camaras = obtener_camaras
        self._fuente = fuente
        self._caido = False
        self._fallidas = set()
        self._registradas = {}

    @property
    def caido(self) -> bool:
        return self._caido

    def vuelta(self) -> int:
        # misma lógica que main._sincronizar (una sola pasada, sin sleep): streams(); si None marca caído (log una vez) y devuelve 0;
        # pendientes = cámaras no en fallidas y (no presentes o registrada con otra fuente); registra cada una:
        # éxito -> self._registradas[cid] = fuente; fallo -> self._fallidas.add(cid). Devuelve cuántas registró bien.
        presentes = self._go2rtc.streams()
        if presentes is None:
            if not self._caido:
                log.warning("go2rtc no responde; se reintenta")
                self._caido = True
            return 0

        if self._caido:
            log.warning("go2rtc volvió a responder")
            self._caido = False

        camaras = self._obtener_camaras()
        pendientes = []
        for c in camaras:
            cid = c["id"]
            f = self._fuente(c)
            if cid not in self._fallidas and (
                cid not in presentes or self._registradas.get(cid) != f
            ):
                pendientes.append(c)

        registradas_bien = 0
        for c in pendientes:
            cid = c["id"]
            f = self._fuente(c)
            r = self._go2rtc.registrar(cid, f)
            if r:
                self._registradas[cid] = f
                registradas_bien += 1
            elif r is False:  # rechazada: no se reintenta en bucle; sin conexión se reintenta la próxima vuelta
                self._fallidas.add(cid)

        return registradas_bien

    def registrar_ya(self, c: dict) -> bool:
        # para altas: quita de fallidas y registra al momento
        cid = c["id"]
        self._fallidas.discard(cid)
        f = self._fuente(c)
        r = self._go2rtc.registrar(cid, f)
        if r:
            self._registradas[cid] = f
        elif r is False:
            self._fallidas.add(cid)
        return bool(r)

    def olvidar(self, cid: str) -> None:
        # para bajas: quita de fallidas y registradas y llama go2rtc.quitar
        self._fallidas.discard(cid)
        self._registradas.pop(cid, None)
        self._go2rtc.quitar(cid)
