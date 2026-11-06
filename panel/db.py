"""Guarda eventos, muestras de consumo y estado del panel en SQLite."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Iterable, Optional

ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, fuente TEXT, tipo TEXT, nivel TEXT,
    titulo TEXT, detalle TEXT, ref TEXT, clave TEXT UNIQUE, avisado INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS eventos_ts ON eventos(ts);
CREATE TABLE IF NOT EXISTS consumo(ts INTEGER, equipo TEXT, rx INTEGER, tx INTEGER);
CREATE INDEX IF NOT EXISTS consumo_ts ON consumo(equipo, ts);
CREATE TABLE IF NOT EXISTS estado(clave TEXT PRIMARY KEY, valor TEXT);
"""


class Db:
    def __init__(self, path):
        self._con = sqlite3.connect(str(path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.executescript(ESQUEMA)

    def _q(self, sql: str, args=()) -> list:
        with self._lock:
            return [dict(r) for r in self._con.execute(sql, tuple(args))]

    def _x(self, sql: str, args=(), muchos: bool = False) -> int:
        with self._lock:
            cur = self._con.executemany(sql, args) if muchos else self._con.execute(sql, tuple(args))
            self._con.commit()
            return cur.rowcount

    # --- eventos ---
    def agregar_evento(self, ev: dict) -> bool:
        n = self._x("INSERT OR IGNORE INTO eventos(ts, fuente, tipo, nivel, titulo, detalle, ref, clave, avisado) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (int(ev["ts"]), ev["fuente"], ev["tipo"], ev["nivel"], ev["titulo"], ev.get("detalle", ""),
                     ev.get("ref", ""), ev["clave"], int(ev.get("avisado", 0))))
        return n == 1

    def eventos(self, desde=None, hasta=None, tipos=None, limite=200) -> list:
        cond, args = [], []
        if desde is not None:
            cond.append("ts >= ?"); args.append(int(desde))
        if hasta is not None:
            cond.append("ts < ?"); args.append(int(hasta))
        tipos = list(tipos or [])
        if tipos:
            cond.append(f"tipo IN ({','.join('?' * len(tipos))})"); args += tipos
        where = f"WHERE {' AND '.join(cond)}" if cond else ""
        args.append(max(1, min(1000, int(limite))))
        return self._q(f"SELECT * FROM eventos {where} ORDER BY ts DESC, id DESC LIMIT ?", args)

    def pendientes_aviso(self, tipos, limite=20) -> list:
        tipos = list(tipos or [])
        if not tipos:
            return []
        return self._q(f"SELECT * FROM eventos WHERE avisado=0 AND tipo IN ({','.join('?' * len(tipos))}) "
                       "ORDER BY ts ASC, id ASC LIMIT ?", tipos + [int(limite)])

    def marcar_avisado(self, ids: Iterable[int], valor: int = 1) -> None:
        ids = list(ids)
        if ids:
            self._x(f"UPDATE eventos SET avisado=? WHERE id IN ({','.join('?' * len(ids))})", [valor] + ids)

    def conteo_por_tipo(self, desde) -> dict:
        return {r["tipo"]: r["n"] for r in
                self._q("SELECT tipo, COUNT(*) AS n FROM eventos WHERE ts >= ? GROUP BY tipo", (int(desde),))}

    # --- consumo ---
    def guardar_consumo(self, ts, muestras: dict) -> None:
        filas = [(int(ts), str(eq), int(rx), int(tx)) for eq, (rx, tx) in muestras.items()]
        if filas:
            self._x("INSERT INTO consumo(ts, equipo, rx, tx) VALUES (?,?,?,?)", filas, muchos=True)

    def consumo(self, horas: int = 24, ahora: Optional[int] = None) -> dict:
        ahora = int(time.time()) if ahora is None else int(ahora)
        inicio = ahora - horas * 3600
        filas = self._q("SELECT ts, equipo, rx, tx FROM consumo WHERE ts >= ? ORDER BY equipo, ts", (inicio - 3600,))
        res, previo = {}, {}
        for f in filas:
            p = previo.get(f["equipo"])
            previo[f["equipo"]] = f
            if p is None or f["ts"] < inicio:
                continue
            # contadores acumulados: si bajan, el router se reinició y cuenta el valor nuevo
            drx = f["rx"] - p["rx"] if f["rx"] >= p["rx"] else f["rx"]
            dtx = f["tx"] - p["tx"] if f["tx"] >= p["tx"] else f["tx"]
            d = res.setdefault(f["equipo"], {"rx": 0, "tx": 0, "serie": [0] * horas})
            d["rx"] += drx
            d["tx"] += dtx
            d["serie"][min(horas - 1, max(0, (f["ts"] - inicio) // 3600))] += drx + dtx
        return res

    def podar(self, dias_eventos: int = 90, dias_consumo: int = 30, ahora: Optional[int] = None) -> None:
        ahora = int(time.time()) if ahora is None else int(ahora)
        self._x("DELETE FROM eventos WHERE ts < ?", (ahora - dias_eventos * 86400,))
        self._x("DELETE FROM consumo WHERE ts < ?", (ahora - dias_consumo * 86400,))

    # --- estado clave/valor ---
    def get(self, clave: str, defecto=None):
        filas = self._q("SELECT valor FROM estado WHERE clave=?", (clave,))
        return json.loads(filas[0]["valor"]) if filas else defecto

    def set(self, clave: str, valor) -> None:
        self._x("INSERT OR REPLACE INTO estado(clave, valor) VALUES (?,?)", (clave, json.dumps(valor)))
