from __future__ import annotations

import re
import threading
import unicodedata
from panel.db import Db

ESQUEMA = "CREATE TABLE IF NOT EXISTS luz_habitacion(id TEXT PRIMARY KEY, habitacion TEXT NOT NULL)"
MAX_NOMBRE = 40


class Habitaciones:
    def __init__(self, db: Db):
        self.db = db
        self.db._x(ESQUEMA)

    def _normalizar(self, valor: str | None) -> str | None:
        if valor is None:
            return None
        if not isinstance(valor, str):
            raise ValueError("nombre de habitación inválido")
        # Los caracteres de control se rechazan antes de colapsar espacios (si no, \n pasaría como espacio)
        if any(unicodedata.category(c) == "Cc" for c in valor):
            raise ValueError("nombre de habitación inválido")

        # Colapsar espacios internos y recortar
        limpio = re.sub(r"\s+", " ", valor).strip()
        if not limpio:
            return None

        if len(limpio) > MAX_NOMBRE:
            raise ValueError("nombre de habitación inválido")

        return limpio

    def todas(self) -> dict:
        filas = self.db._q("SELECT id, habitacion FROM luz_habitacion")
        return {f["id"]: f["habitacion"] for f in filas}

    def de(self, ident: str) -> str | None:
        filas = self.db._q("SELECT habitacion FROM luz_habitacion WHERE id = ?", (ident,))
        if not filas:
            return None
        return filas[0]["habitacion"]

    def asignar(self, ident: str, habitacion: str | None) -> str | None:
        nombre = self._normalizar(habitacion)
        if nombre is None:
            self.db._x("DELETE FROM luz_habitacion WHERE id = ?", (ident,))
            return None

        self.db._x(
            "INSERT OR REPLACE INTO luz_habitacion(id, habitacion) VALUES (?, ?)",
            (ident, nombre),
        )
        return nombre

    def nombres(self) -> list[str]:
        filas = self.db._q("SELECT DISTINCT habitacion FROM luz_habitacion")
        
        def clave_orden(hab: str) -> str:
            # Quitar marcas combinantes y pasar a casefold
            nfkd = unicodedata.normalize("NFD", hab)
            sin_acentos = "".join([c for c in nfkd if unicodedata.category(c) != "Mn"])
            return sin_acentos.casefold()

        nombres_unicos = [f["habitacion"] for f in filas]
        return sorted(nombres_unicos, key=clave_orden)

    def con_habitacion(self, luces: list) -> list:
        asignaciones = self.todas()
        resultado = []
        for luz in luces:
            copia = dict(luz)
            copia["habitacion"] = asignaciones.get(luz.get("id"))
            resultado.append(copia)
        return resultado

    def resumen(self, luces: list) -> list:
        asignaciones = self.todas()
        
        # Mapear foco_id -> luz
        luz_map = {l.get("id"): l for l in luces if l.get("id") is not None}
        
        # Agrupar por habitación
        grupos: dict[str, list] = {}
        sin_hab: list = []

        for lid, hab in asignaciones.items():
            if lid not in luz_map:
                continue
            grupos.setdefault(hab, []).append(luz_map[lid])

        # Focos en luces que no están en asignaciones van a Sin habitación
        asignados_ids = set(asignaciones.keys())
        for lid, luz in luz_map.items():
            if lid not in asignados_ids:
                sin_hab.append(luz)

        def clave_orden(hab: str) -> str:
            nfkd = unicodedata.normalize("NFD", hab)
            sin_ac = "".join([c for c in nfkd if unicodedata.category(c) != "Mn"])
            return sin_ac.casefold()

        habitaciones_ordenadas = sorted(grupos.keys(), key=clave_orden)
        
        resultado = []
        for hab in habitaciones_ordenadas:
            focos_grupo = grupos[hab]
            focos_ids = [f.get("id") for f in focos_grupo if f.get("id") is not None]
            total = len(focos_grupo)
            encendidos = sum(1 for f in focos_grupo if f.get("encendida") is True)
            en_linea = sum(1 for f in focos_grupo if f.get("en_linea") is True)
            
            brillos_vals = [
                f.get("brillo") for f in focos_grupo
                if f.get("encendida") is True and f.get("brillo") is not None
            ]
            if brillos_vals:
                brillo_prom = round(sum(brillos_vals) / len(brillos_vals))
            else:
                brillo_prom = None

            resultado.append({
                "habitacion": hab,
                "focos": focos_ids,
                "total": total,
                "encendidos": encendidos,
                "en_linea": en_linea,
                "brillo": brillo_prom,
            })

        if sin_hab:
            focos_ids = [f.get("id") for f in sin_hab if f.get("id") is not None]
            total = len(sin_hab)
            encendidos = sum(1 for f in sin_hab if f.get("encendida") is True)
            en_linea = sum(1 for f in sin_hab if f.get("en_linea") is True)
            brillos_vals = [
                f.get("brillo") for f in sin_hab
                if f.get("encendida") is True and f.get("brillo") is not None
            ]
            if brillos_vals:
                brillo_prom = round(sum(brillos_vals) / len(brillos_vals))
            else:
                brillo_prom = None

            resultado.append({
                "habitacion": "Sin habitación",
                "focos": focos_ids,
                "total": total,
                "encendidos": encendidos,
                "en_linea": en_linea,
                "brillo": brillo_prom,
            })

        return resultado

    def aplicar(self, luces_obj, habitacion: str, cambios: dict) -> dict:
        asignaciones = self.todas()
        focos_hab = [
            lid for lid, hab in asignaciones.items()
            if hab == habitacion
        ]

        if not focos_hab:
            raise KeyError(habitacion)

        # Mapear nombres de focos desde luces_obj.lista()
        lista_luces = luces_obj.lista()
        luz_info = {l.get("id"): l.get("nombre", l.get("id")) for l in lista_luces}

        # Filtrar solo los que existen actualmente en luces_obj.lista()
        focos_a_aplicar = [lid for lid in focos_hab if lid in luz_info]
        if not focos_a_aplicar:
            raise KeyError(habitacion)

        lock = threading.Lock()
        n_ok = 0
        fallaron = []
        error_val_capturado = [None]

        def worker(identificador: str):
            nonlocal n_ok
            try:
                luces_obj.aplicar(identificador, cambios)
                with lock:
                    n_ok += 1
            except ValueError as ve:
                error_val_capturado[0] = ve
            except Exception:
                with lock:
                    nombre_foco = luz_info.get(identificador, identificador)
                    fallaron.append(nombre_foco)

        hilos = []
        for lid in focos_a_aplicar:
            t = threading.Thread(target=worker, args=(lid,), daemon=True)
            hilos.append(t)
            t.start()

        for t in hilos:
            t.join()

        if error_val_capturado[0] is not None:
            raise error_val_capturado[0]

        fallaron.sort()
        return {
            "habitacion": habitacion,
            "total": len(focos_a_aplicar),
            "ok": n_ok,
            "fallaron": fallaron,
        }
