"""Rutinas de luces: un conjunto de acciones sobre varios focos que se ejecuta con un clic o a una hora.

Cada rutina guarda `acciones` (por foco: encendida y, si enciende, brillo y temperatura o color) y un `horario`
opcional ({"hora": "HH:MM", "dias": [0..6]}, 0 = lunes). Un hilo revisa cada 20 s y ejecuta las que tocan;
`ultima` ("AAAA-MM-DD HH:MM") evita repetir la misma ejecución.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime

from panel.luces import Luces

log = logging.getLogger("panel.rutinas")
HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MAX_RUTINAS = 30
VENTANA_MIN = 2  # si el ciclo se atrasa, aún se ejecuta hasta 2 min después de la hora

ESQUEMA = """CREATE TABLE IF NOT EXISTS rutinas(
    id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, acciones TEXT NOT NULL,
    horario TEXT, activa INTEGER NOT NULL DEFAULT 1, ultima TEXT, creado INTEGER)"""


class Rutinas:
    def __init__(self, db, luces, al_ejecutar=None, cada: int = 20):
        self.db = db
        self.luces = luces
        self.al_ejecutar = al_ejecutar  # (rutina, resultado, origen) -> None
        self.cada = cada
        self._parar = threading.Event()
        db._x(ESQUEMA)

    # --- lectura ---
    @staticmethod
    def _fila(r: dict) -> dict:
        return {"id": r["id"], "nombre": r["nombre"], "acciones": json.loads(r["acciones"]),
                "horario": json.loads(r["horario"]) if r["horario"] else None,
                "activa": bool(r["activa"]), "ultima": r["ultima"]}

    def lista(self) -> list:
        return [self._fila(r) for r in self.db._q("SELECT * FROM rutinas ORDER BY nombre COLLATE NOCASE")]

    def una(self, ident: int) -> dict:
        filas = self.db._q("SELECT * FROM rutinas WHERE id = ?", (int(ident),))
        if not filas:
            raise KeyError(ident)
        return self._fila(filas[0])

    # --- escritura ---
    def _validar(self, datos: dict) -> tuple:
        nombre = datos.get("nombre")
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError("Ponle un nombre a la rutina")
        nombre = nombre.strip()[:40]
        focos = {l["id"] for l in self.luces.lista()} if self.luces is not None else set()
        acciones = datos.get("acciones")
        if not isinstance(acciones, list) or not acciones:
            raise ValueError("Elige al menos un foco")
        limpias, vistos = [], set()
        for a in acciones:
            if not isinstance(a, dict) or a.get("id") not in focos:
                raise ValueError("La rutina tiene un foco que no existe")
            if a["id"] in vistos:
                raise ValueError("Un foco aparece dos veces")
            vistos.add(a["id"])
            cambios = Luces._validar({k: a[k] for k in ("encendida", "brillo", "temperatura", "color") if k in a})
            if "encendida" not in cambios:
                raise ValueError("Cada foco debe decir si se enciende o se apaga")
            if not cambios["encendida"]:
                cambios = {"encendida": False}  # al apagar no tiene sentido el brillo ni el color
            if "color" in cambios and "temperatura" in cambios:
                cambios.pop("temperatura")
            limpias.append({"id": a["id"], **cambios})
        horario = datos.get("horario")
        if horario is not None:
            if not isinstance(horario, dict) or not isinstance(horario.get("hora"), str) or not HORA.match(horario["hora"]):
                raise ValueError("La hora debe ser HH:MM")
            dias = horario.get("dias")
            if not isinstance(dias, list) or not dias or any(isinstance(d, bool) or d not in range(7) for d in dias):
                raise ValueError("Elige al menos un día")
            horario = {"hora": horario["hora"], "dias": sorted(set(dias))}
        return nombre, limpias, horario

    def guardar(self, datos: dict) -> dict:
        nombre, acciones, horario = self._validar(datos)
        ident = datos.get("id")
        args = (nombre, json.dumps(acciones), json.dumps(horario) if horario else None)
        if ident is None:
            if len(self.db._q("SELECT id FROM rutinas")) >= MAX_RUTINAS:
                raise ValueError(f"Máximo {MAX_RUTINAS} rutinas")
            self.db._x("INSERT INTO rutinas(nombre, acciones, horario, activa, creado) VALUES (?,?,?,1,?)",
                       (*args, int(time.time())))
            return self._fila(self.db._q("SELECT * FROM rutinas ORDER BY id DESC LIMIT 1")[0])
        if isinstance(ident, bool) or not isinstance(ident, int):
            raise ValueError("id inválido")
        if self.db._x("UPDATE rutinas SET nombre = ?, acciones = ?, horario = ?, ultima = NULL WHERE id = ?",
                      (*args, ident)) == 0:
            raise KeyError(ident)
        return self.una(ident)

    def activar(self, ident: int, activa: bool) -> dict:
        if self.db._x("UPDATE rutinas SET activa = ? WHERE id = ?", (int(bool(activa)), int(ident))) == 0:
            raise KeyError(ident)
        return self.una(ident)

    def borrar(self, ident: int) -> None:
        if self.db._x("DELETE FROM rutinas WHERE id = ?", (int(ident),)) == 0:
            raise KeyError(ident)

    # --- ejecución ---
    def ejecutar(self, ident: int, origen: str = "manual") -> dict:
        rutina = self.una(ident)
        nombres = {l["id"]: l["nombre"] for l in self.luces.lista()}
        ok, fallaron, candado = [], [], threading.Lock()

        def uno(accion):
            cambios = {k: v for k, v in accion.items() if k != "id"}
            try:
                self.luces.aplicar(accion["id"], cambios)
                with candado:
                    ok.append(accion["id"])
            except Exception:
                with candado:
                    fallaron.append(nombres.get(accion["id"], accion["id"]))

        hilos = [threading.Thread(target=uno, args=(a,), daemon=True) for a in rutina["acciones"]]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=12)
        resultado = {"ok": len(ok), "total": len(rutina["acciones"]), "fallaron": sorted(fallaron)}
        if self.al_ejecutar:
            try:
                self.al_ejecutar(rutina, resultado, origen)
            except Exception:
                log.exception("falló al registrar la rutina")
        return resultado

    def pendientes(self, ahora: datetime | None = None) -> list:
        """Rutinas programadas que tocan ahora y aún no se ejecutaron en este horario."""
        ahora = ahora or datetime.now()
        minuto = ahora.hour * 60 + ahora.minute
        listas = []
        for r in self.lista():
            h = r["horario"]
            if not r["activa"] or not h or ahora.weekday() not in h["dias"]:
                continue
            hh, mm = map(int, h["hora"].split(":"))
            clave = f"{ahora:%Y-%m-%d} {h['hora']}"
            if 0 <= minuto - (hh * 60 + mm) <= VENTANA_MIN and r["ultima"] != clave:
                listas.append((r["id"], clave))
        return listas

    def revisar(self, ahora: datetime | None = None) -> int:
        n = 0
        for ident, clave in self.pendientes(ahora):
            self.db._x("UPDATE rutinas SET ultima = ? WHERE id = ?", (clave, ident))  # antes: nunca dos veces
            self.ejecutar(ident, origen="programada")
            n += 1
        return n

    def iniciar(self) -> None:
        def bucle():
            while not self._parar.is_set():
                try:
                    self.revisar()
                except Exception:
                    log.exception("falló la revisión de rutinas")
                self._parar.wait(self.cada)

        threading.Thread(target=bucle, name="rutinas", daemon=True).start()

    def detener(self) -> None:
        self._parar.set()
