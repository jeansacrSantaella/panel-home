"""Reglas de la red: procesan las lecturas de la sonda (caídas, equipos, IP pública)."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Optional

log = logging.getLogger("panel.red")

ETIQUETAS = {"lan": "Red local", "wan": "Internet", "dns": "DNS"}


def formato_duracion(seg) -> str:
    s = int(seg)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    return f"{s // 3600}h {s % 3600 // 60}m"


def mac_privada(mac: str) -> bool:
    """Bit "administrado localmente": MAC aleatoria de teléfonos y laptops."""
    return bool(int(mac[:2], 16) & 2)


class _Servicio:
    """Exige varios fallos seguidos antes de declarar una caída."""

    def __init__(self, nombre: str, fallos_para_caida: int, datos: Optional[dict] = None):
        self.nombre = nombre
        self.etiqueta = ETIQUETAS[nombre]
        self._umbral = fallos_para_caida
        datos = datos or {}
        self.fallos = int(datos.get("fallos") or 0)
        self.primer_fallo: Optional[int] = datos.get("primer_fallo")
        self.down_since: Optional[int] = datos.get("down_since")

    def actualizar(self, ok: bool, ahora: int, evento: Callable) -> None:
        if ok:
            if self.down_since:
                evento(f"{self.nombre}_up",
                       f"{self.etiqueta} restablecida tras {formato_duracion(ahora - self.down_since)}")
                self.down_since = None
            self.fallos, self.primer_fallo = 0, None
            return
        self.fallos += 1
        self.primer_fallo = self.primer_fallo or ahora
        if self.fallos >= self._umbral and not self.down_since:
            self.down_since = self.primer_fallo  # la caída empieza en el primer fallo
            evento(f"{self.nombre}_down", f"{self.etiqueta} sin respuesta")

    def a_dict(self) -> dict:
        return {"fallos": self.fallos, "primer_fallo": self.primer_fallo, "down_since": self.down_since}


class EstadoRed:
    def __init__(self, red, fallos_para_caida: int = 3, intervalo_sondeo: int = 5,
                 perdidas_para_desconectar: int = 3, fabricante: Optional[Callable] = None,
                 reloj: Callable = time.time):
        self.red = red
        self._intervalo = intervalo_sondeo
        self._perdidas = perdidas_para_desconectar
        self._fabricante = fabricante or (lambda mac: None)
        self._reloj = reloj
        self._lock = threading.Lock()
        self._inicializado: Optional[bool] = None
        guardado = red.get("servicios") or {}
        self._servicios: Dict[str, _Servicio] = {
            k: _Servicio(k, fallos_para_caida, guardado.get(k)) for k in ETIQUETAS}

    # ---- consulta ----
    def servicios(self) -> dict:
        with self._lock:
            return {k: {"label": s.etiqueta, "down_since": s.down_since} for k, s in self._servicios.items()}

    def internet_ok(self) -> bool:
        with self._lock:
            return not self._servicios["wan"].down_since

    def ultima_lectura(self) -> Optional[int]:
        valor = self.red.get("ultima_lectura")
        return int(valor) if valor is not None else None

    def podar(self, dias: int = 30, ahora: Optional[float] = None) -> None:
        ahora = self._reloj() if ahora is None else ahora
        self.red.podar_sondeos(int(ahora - dias * 86400))

    # ---- proceso ----
    def procesar(self, lecturas: list) -> int:
        validas = []
        for lec in lecturas or []:
            try:
                validas.append((int(lec["ts"]), lec))
            except (KeyError, TypeError, ValueError):
                log.warning("lectura sin ts válido ignorada: %r", lec)
        validas.sort(key=lambda p: p[0])
        manejadores = {"sondeo": self._sondeo, "escaneo": self._escaneo, "calidad": self._calidad,
                       "ip_publica": self._ip_publica, "velocidad": self._velocidad}
        hechas, maximo = 0, None
        with self._lock:
            for ts, lec in validas:
                fn = manejadores.get(lec.get("t")) if isinstance(lec, dict) else None
                if fn is None:
                    log.warning("lectura de tipo desconocido ignorada: %r", lec.get("t"))
                    continue
                try:
                    fn(ts, lec)
                except Exception as e:  # una lectura rota no frena las demás
                    log.warning("lectura %s mal formada (%s)", lec.get("t"), e)
                    continue
                hechas += 1
                maximo = ts if maximo is None else max(maximo, ts)
            if maximo is not None:
                previo = self.red.get("ultima_lectura")
                self.red.set("ultima_lectura", max(maximo, int(previo)) if previo is not None else maximo)
        return hechas

    def _evento(self, ts: int) -> Callable:
        return lambda kind, detail: self.red.agregar_evento(ts, kind, detail)

    def _sondeo(self, ts: int, lec: dict) -> None:
        res = {}
        for r in lec["resultados"]:
            res[(r["kind"], r["target"])] = (bool(r["ok"]), r.get("ms"))
        filas = [(ts, k, t, ok, ms) for (k, t), (ok, ms) in res.items()]
        self.red.agregar_sondeos(filas)
        evento = self._evento(ts)
        anterior = self.red.get("ultimo_sondeo")
        if anterior is not None and ts - int(anterior) > self._intervalo * 4:
            evento("monitor_gap", f"El monitor estuvo detenido {formato_duracion(ts - int(anterior))} "
                                  "(¿equipo suspendido?)")
        externos = {t for (_, t) in res if t != "gateway"}
        hay_gw = ("ping", "gateway") in res
        lan_ok = res[("ping", "gateway")][0] if hay_gw else True
        wan_ok = any(res[("ping", h)][0] for h in externos if ("ping", h) in res)
        dns_ok = any(ok for (kind, _), (ok, _) in res.items() if kind == "dns")
        antes = {k: s.a_dict() for k, s in self._servicios.items()}
        self._servicios["lan"].actualizar(lan_ok, ts, evento)
        self._servicios["wan"].actualizar(wan_ok or not lan_ok, ts, evento)  # no culpar a internet si cae la LAN
        self._servicios["dns"].actualizar(dns_ok or not wan_ok, ts, evento)  # ni al DNS si no hay internet
        ahora = {k: s.a_dict() for k, s in self._servicios.items()}
        if ahora != antes or self.red.get("servicios") is None:
            self.red.set("servicios", ahora)
        self.red.set("ultimo_sondeo", ts)

    def _escaneo(self, ts: int, lec: dict) -> None:
        red = self.red
        if self._inicializado is None:
            self._inicializado = bool(red.hay_equipos())
        evento = self._evento(ts)
        encontrados = {}
        for mac, info in lec["equipos"].items():
            encontrados[mac] = info["ip"]
            host = info.get("hostname")
            conocido = red.equipo(mac)
            if conocido is None:
                privada = mac_privada(mac)
                red.agregar_equipo(mac, info["ip"], host, privada, ts)
                if self._inicializado:
                    fab = self._fabricante(mac)
                    extra = (f" · {fab}" if fab else "") + \
                            (" · MAC privada (típico de teléfonos y laptops)" if privada else "")
                    evento("new_device", f"Equipo nuevo: {mac} en {info['ip']}"
                                         + (f" ({host})" if host else "") + extra)
                continue
            if not conocido["online"]:
                evento("device_online", f"{mac} volvió a la red en {info['ip']}")
            red.marcar_visto(mac, info["ip"], ts)
        for d in red.equipos():
            if d["mac"] in encontrados:
                continue
            fallos = (d.get("misses") or 0) + 1
            fuera = fallos >= self._perdidas
            red.fijar_fallos(d["mac"], fallos, False if fuera else bool(d["online"]))
            if fuera and d["online"]:
                nombre = d.get("alias") or d.get("hostname") or d["ip"]
                evento("device_offline", f"{nombre} ({d['mac']}) se desconectó")
        self._inicializado = True

    def _calidad(self, ts: int, lec: dict) -> None:
        self.red.agregar_sondeos([(ts, "dev", r["mac"], bool(r["ok"]), r.get("ms"))
                                  for r in lec["resultados"]])

    def _ip_publica(self, ts: int, lec: dict) -> None:
        ip = lec["ip"]
        previa = self.red.get("ip_publica")
        if previa is None:
            self._evento(ts)("ip_first", f"IP pública inicial: {ip}")
        elif previa != ip:
            self._evento(ts)("ip_change", f"IP pública cambió: {previa} → {ip}")
        self.red.set("ip_publica", ip)

    def _velocidad(self, ts: int, lec: dict) -> None:
        self.red.agregar_velocidad(ts, lec["down"], lec["up"])
