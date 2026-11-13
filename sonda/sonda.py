"""Sonda: toma lecturas, las junta en una cola y las manda al panel."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional

from . import medir

log = logging.getLogger("sonda")

REFRESCO_GATEWAY = 60  # segundos entre consultas de la ruta por defecto
URL_IP = "https://api.ipify.org"
URL_BAJADA = "https://speed.cloudflare.com/__down?bytes={}"
URL_SUBIDA = "https://speed.cloudflare.com/__up"


def _post_http(url: str, cuerpo: bytes, cabeceras: dict) -> int:
    req = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


class Sonda:
    def __init__(self, panel_url, token, nombre, medidor=None, externos=("1.1.1.1", "8.8.8.8"),
                 reloj=time.time, enviar_http=None, max_cola=20000, lote=500,
                 bajada=10_000_000, subida=3_000_000, con_velocidad=True):
        self.panel_url = panel_url.rstrip("/")
        self.token = token
        self.nombre = nombre
        self.m = medidor if medidor is not None else medir
        self.externos = list(externos)
        self.reloj = reloj
        self.enviar_http = enviar_http or _post_http
        self.lote = lote
        self.bajada = bajada
        self.subida = subida
        self.con_velocidad = con_velocidad
        self._cola: deque = deque(maxlen=max_cola)
        self._candado = threading.Lock()
        self._gw: Optional[str] = None
        self._gw_en: Optional[float] = None
        self._hay_internet = False
        self._base: Optional[str] = None
        self._equipos: Dict[str, dict] = {}
        self._nombres: Dict[str, Optional[str]] = {}  # hostname por MAC, consultado una sola vez
        self._pool = ThreadPoolExecutor(12)

    # --- lecturas ---

    def sondeo(self) -> dict:
        ahora = self.reloj()
        if self._gw_en is None or ahora - self._gw_en > REFRESCO_GATEWAY:
            self._gw, self._gw_en = self.m.gateway(), ahora
        objetivos = {h: h for h in self.externos}
        if self._gw:
            objetivos = {"gateway": self._gw, **objetivos}
        futuros = []
        for nombre, host in objetivos.items():
            futuros.append(("ping", nombre, self._pool.submit(self.m.ping, host)))
            futuros.append(("dns", nombre, self._pool.submit(self.m.dns_query, host)))
        resultados = []
        for kind, nombre, f in futuros:
            ok, ms = f.result()
            resultados.append({"kind": kind, "target": nombre, "ok": bool(ok),
                               "ms": round(ms, 2) if ms is not None else None})
        self._hay_internet = any(r["ok"] for r in resultados if r["kind"] == "ping" and r["target"] in self.externos)
        return {"t": "sondeo", "ts": int(ahora), "gateway": self._gw, "resultados": resultados}

    def escaneo(self) -> Optional[dict]:
        propia = self.m.local_ip()
        if not propia:
            return None
        base = propia.rsplit(".", 1)[0]
        with ThreadPoolExecutor(64) as pool:
            list(pool.map(lambda i: self.m.ping(f"{base}.{i}", 0.6), range(1, 255)))
        equipos = {}
        for mac, ip in self.m.read_arp().items():
            if not ip.startswith(base + "."):
                continue
            if mac not in self._nombres:
                self._nombres[mac] = self.m.reverse_dns(ip)
            equipos[mac] = {"ip": ip, "hostname": self._nombres[mac]}
        self._base, self._equipos = base, equipos
        return {"t": "escaneo", "ts": int(self.reloj()), "base": base, "propia": propia, "equipos": equipos}

    def calidad(self) -> Optional[dict]:
        if self._base is None:
            return None
        items = list(self._equipos.items())
        with ThreadPoolExecutor(16) as pool:
            medidas = list(pool.map(lambda kv: self.m.ping(kv[1]["ip"], 1.0), items))
        resultados = [{"mac": mac, "ip": d["ip"], "ok": bool(ok), "ms": round(ms, 2) if ms is not None else None}
                      for (mac, d), (ok, ms) in zip(items, medidas)]
        return {"t": "calidad", "ts": int(self.reloj()), "resultados": resultados}

    def ip_publica(self) -> Optional[dict]:
        try:
            ip = self.m.fetch(URL_IP, timeout=5).decode().strip()
        except Exception:
            return None
        return {"t": "ip_publica", "ts": int(self.reloj()), "ip": ip} if ip else None

    def velocidad(self) -> Optional[dict]:
        if not self._hay_internet:
            return None
        try:
            t0 = time.time()
            n = len(self.m.fetch(URL_BAJADA.format(self.bajada), timeout=30))
            bajada = n * 8 / max(time.time() - t0, 1e-6) / 1e6
            datos = os.urandom(self.subida)
            t1 = time.time()
            self.m.fetch(URL_SUBIDA, timeout=30, data=datos)
            subida = len(datos) * 8 / max(time.time() - t1, 1e-6) / 1e6
        except Exception as e:
            log.warning("velocidad falló: %s", e)
            return None
        return {"t": "velocidad", "ts": int(self.reloj()), "down": round(bajada, 2), "up": round(subida, 2)}

    # --- cola y envío ---

    def encolar(self, lectura) -> None:
        with self._candado:
            self._cola.append(lectura)  # con la cola llena, deque descarta la más vieja

    def pendientes(self) -> int:
        with self._candado:
            return len(self._cola)

    def enviar(self) -> bool:
        with self._candado:
            lote = list(self._cola)[:self.lote]
        if not lote:
            return True
        cuerpo = json.dumps({"sonda": self.nombre, "version": 1, "enviado": int(self.reloj()),
                             "lecturas": lote}).encode()
        cabeceras = {"Content-Type": "application/json", "Authorization": "Bearer " + self.token}
        try:
            estado = self.enviar_http(self.panel_url + "/api/interno/red", cuerpo, cabeceras)
        except Exception as e:
            log.warning("panel sin respuesta (%s); se reintenta", e)
            return False
        if estado == 200:
            with self._candado:
                for _ in range(min(len(lote), len(self._cola))):
                    self._cola.popleft()
            return True
        if estado == 401:
            log.error("el panel rechazó la sonda: token incorrecto")
        else:
            log.warning("el panel respondió %s; se reintenta", estado)
        return False

    # --- ejecución ---

    def _midiendo(self, funcion: Callable) -> Callable:
        def tarea():
            lectura = funcion()
            if lectura is not None:
                self.encolar(lectura)
        return tarea

    def tareas(self) -> list:
        """[(nombre, cada_s, retraso_s, función)]"""
        lista = [
            ("sondeo", 5, 0, self._midiendo(self.sondeo)),
            ("escaneo", 120, 0, self._midiendo(self.escaneo)),
            ("calidad", 30, 10, self._midiendo(self.calidad)),
            ("ip_publica", 300, 0, self._midiendo(self.ip_publica)),
        ]
        if self.con_velocidad:
            lista.append(("velocidad", 3600, 30, self._midiendo(self.velocidad)))
        lista.append(("envio", 15, 3, self.enviar))
        return lista

    @staticmethod
    def _bucle(nombre: str, cada: float, retraso: float, funcion: Callable, parar: threading.Event) -> None:
        if parar.wait(retraso):
            return
        while not parar.is_set():
            t0 = time.time()
            try:
                funcion()
            except Exception as e:  # una vuelta fallida no mata el hilo
                log.error("%s: error: %s", nombre, e)
            if parar.wait(max(0.5, cada - (time.time() - t0))):
                return

    def correr(self, parar: Optional[threading.Event] = None) -> None:
        parar = parar or threading.Event()
        for nombre, cada, retraso, funcion in self.tareas():
            threading.Thread(target=self._bucle, args=(nombre, cada, retraso, funcion, parar),
                             name=nombre, daemon=True).start()
        parar.wait()
