"""Control local de los focos Tuya (puerto 6668) con tinytuya.

Las llaves vienen de `devices.json` (lo genera `python -m tinytuya wizard`, ver docs/LUCES.md) y nunca se
escriben en los registros. Un hilo lee el estado de los focos cada `cada` segundos; los comandos se aplican
al momento. Sin tinytuya instalado el panel sigue funcionando: `configurado` queda en False.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("panel.luces")
CATEGORIAS = {"dj", "dd", "xdd", "fwd", "dc", "tgq"}  # focos, tiras y lámparas
COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _tinytuya():
    try:
        import tinytuya  # noqa: WPS433 (dependencia opcional)
        return tinytuya
    except ImportError:
        return None


def _corto(texto) -> str:
    return str(texto)[:120]


class Luces:
    def __init__(self, archivo: Path, ips_por_mac=None, cada: int = 20, al_cambiar=None):
        self.archivo = Path(archivo)
        self.ips_por_mac = ips_por_mac
        self.cada = cada
        self.al_cambiar = al_cambiar
        self._tt = _tinytuya()
        self._focos: dict = {}      # id -> datos del archivo (incluye la llave)
        self._equipos: dict = {}    # id -> tinytuya.BulbDevice
        self._candados: dict = {}   # id -> Lock (no mezclar comandos y lecturas del mismo foco)
        self._cache: dict = {}      # id -> último estado público
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._motivo = ""
        self._cargar()

    # --- configuración ---
    def _cargar(self) -> None:
        if self._tt is None:
            self._motivo = "Falta instalar tinytuya."
            return
        if not self.archivo.is_file():
            self._motivo = "No encontré devices.json."
            return
        try:
            datos = json.loads(self.archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self._motivo = "devices.json no se pudo leer."
            return
        for d in datos if isinstance(datos, list) else []:
            if not isinstance(d, dict) or not d.get("id") or not d.get("key"):
                continue
            if d.get("category") and d["category"] not in CATEGORIAS:
                continue
            self._focos[str(d["id"])] = d
            self._candados[str(d["id"])] = threading.Lock()
            self._cache[str(d["id"])] = self._vacio(d)
        if not self._focos:
            self._motivo = "devices.json no tiene focos."

    @property
    def configurado(self) -> bool:
        return self._tt is not None and bool(self._focos)

    @property
    def motivo(self) -> str:
        return "" if self.configurado else self._motivo

    @staticmethod
    def _vacio(d: dict) -> dict:
        return {"id": str(d["id"]), "nombre": d.get("name") or str(d["id"]), "ip": d.get("ip") or d.get("last_ip") or None,
                "en_linea": False, "encendida": None, "brillo": None, "modo": None, "temperatura": None, "color": None,
                "tiene_color": False, "tiene_temperatura": False, "error": None, "visto": 0}

    def _ip(self, d: dict) -> str | None:
        ip = d.get("ip") or d.get("last_ip")
        if not ip and self.ips_por_mac and d.get("mac"):
            try:
                ip = self.ips_por_mac().get(str(d["mac"]).lower())
            except Exception:
                ip = None
        return ip or None

    def _equipo(self, ident: str):
        """BulbDevice del foco (se crea una vez y se recrea si cambia la IP)."""
        d = self._focos[ident]
        ip = self._ip(d)
        if not ip:
            raise RuntimeError("Sin IP: agrégala en devices.json")
        eq = self._equipos.get(ident)
        if eq is None or getattr(eq, "address", None) != ip:
            try:
                version = float(d.get("version") or 3.3)
            except (TypeError, ValueError):
                version = 3.3
            eq = self._tt.BulbDevice(ident, address=ip, local_key=d["key"], version=version)
            eq.set_socketTimeout(3)
            eq.set_socketRetryLimit(1)
            eq.set_socketPersistent(False)
            self._equipos[ident] = eq
        return eq

    # --- lectura ---
    def _leer(self, ident: str) -> dict:
        """Estado actual de un foco (sin lanzar excepciones)."""
        d = self._focos[ident]
        r = self._vacio(d)
        r["visto"] = self._cache.get(ident, {}).get("visto", 0)
        try:
            eq = self._equipo(ident)
            r["ip"] = eq.address
            est = eq.state()
            if not isinstance(est, dict) or "Error" in est:
                raise RuntimeError((est or {}).get("Error", "sin respuesta") if isinstance(est, dict) else "sin respuesta")
        except Exception as e:  # el foco puede estar apagado del interruptor o fuera de la red
            r["error"] = _corto(e) or "Sin respuesta"
            return r
        r.update(en_linea=True, error=None, visto=int(time.time()), encendida=bool(est.get("is_on")), modo=est.get("mode"),
                 tiene_color=bool(getattr(eq, "has_colour", False)), tiene_temperatura=bool(getattr(eq, "has_colourtemp", False)))
        for campo, fn in (("brillo", eq.get_brightness_percentage), ("temperatura", eq.get_colourtemp_percentage)):
            try:
                r[campo] = max(0, min(100, round(fn(est))))
            except Exception:
                r[campo] = None
        if r["tiene_color"]:
            try:
                rr, gg, bb = eq.colour_rgb(est)
                r["color"] = "#%02x%02x%02x" % (int(rr), int(gg), int(bb))
            except Exception:
                r["color"] = None
        return r

    def _actualizar(self, ident: str, nuevo: dict, avisar: bool = True) -> None:
        with self._lock:
            previo = self._cache.get(ident) or {}
            self._cache[ident] = nuevo
        cambio = previo.get("en_linea") and nuevo["en_linea"] and previo.get("encendida") != nuevo["encendida"]
        if avisar and cambio and self.al_cambiar:
            try:
                self.al_cambiar(dict(nuevo), bool(nuevo["encendida"]))
            except Exception:
                log.exception("falló al registrar el cambio de un foco")

    def _leer_y_guardar(self, ident: str) -> None:
        with self._candados[ident]:
            self._actualizar(ident, self._leer(ident))

    def sondear(self) -> None:
        """Lee todos los focos en paralelo."""
        hilos = [threading.Thread(target=self._leer_y_guardar, args=(i,), daemon=True) for i in self._focos]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=8)

    def iniciar(self) -> None:
        if not self.configurado:
            return

        def bucle():
            while not self._parar.is_set():
                try:
                    self.sondear()
                except Exception:
                    log.exception("falló la lectura de los focos")
                self._parar.wait(self.cada)

        threading.Thread(target=bucle, name="luces", daemon=True).start()

    def detener(self) -> None:
        self._parar.set()

    def lista(self) -> list:
        with self._lock:
            return sorted((dict(v) for v in self._cache.values()), key=lambda x: x["nombre"].lower())

    def nombre_por_ip(self) -> dict:
        with self._lock:
            return {v["ip"]: v["nombre"] for v in self._cache.values() if v.get("ip")}

    # --- comandos ---
    @staticmethod
    def _validar(cambios: dict) -> dict:
        ok = {}
        if "encendida" in cambios:
            if not isinstance(cambios["encendida"], bool):
                raise ValueError("'encendida' debe ser verdadero o falso")
            ok["encendida"] = cambios["encendida"]
        for campo, minimo in (("brillo", 1), ("temperatura", 0)):
            if campo in cambios:
                v = cambios[campo]
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not minimo <= v <= 100:
                    raise ValueError(f"'{campo}' debe ir de {minimo} a 100")
                ok[campo] = int(round(v))
        if "color" in cambios:
            if not isinstance(cambios["color"], str) or not COLOR.match(cambios["color"]):
                raise ValueError("'color' debe ser #rrggbb")
            ok["color"] = cambios["color"].lower()
        return ok

    def aplicar(self, ident: str, cambios: dict) -> dict:
        if ident not in self._focos:
            raise KeyError(ident)
        ok = self._validar(cambios)
        with self._candados[ident]:
            try:
                eq = self._equipo(ident)
                if not eq.bulb_configured:
                    eq.status()  # detecta el tipo de foco (mapa de datos) antes de mandar órdenes
                if "encendida" in ok:
                    r = eq.turn_on() if ok["encendida"] else eq.turn_off()
                    self._revisar(r)
                if "color" in ok:
                    c = ok["color"]
                    self._revisar(eq.set_colour(int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)))
                if "temperatura" in ok:
                    if "brillo" in ok:
                        self._revisar(eq.set_white_percentage(ok["brillo"], ok["temperatura"]))
                    else:
                        self._revisar(eq.set_colourtemp_percentage(ok["temperatura"]))
                elif "brillo" in ok:
                    self._revisar(eq.set_brightness_percentage(ok["brillo"]))
            except (ValueError, KeyError):
                raise
            except Exception as e:
                log.info("foco %s no respondió: %s", self._focos[ident].get("name"), _corto(e))
                raise RuntimeError("El foco no respondió") from None
            nuevo = self._leer(ident)
            self._actualizar(ident, nuevo)
        return dict(nuevo)

    @staticmethod
    def _revisar(respuesta) -> None:
        if isinstance(respuesta, dict) and "Error" in respuesta:
            raise RuntimeError(respuesta["Error"])

    def aplicar_todas(self, encendida: bool) -> int:
        respondieron = []

        def uno(ident):
            try:
                self.aplicar(ident, {"encendida": encendida})
                respondieron.append(ident)
            except Exception:
                pass

        hilos = [threading.Thread(target=uno, args=(i,), daemon=True) for i in self._focos]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=10)
        return len(respondieron)
