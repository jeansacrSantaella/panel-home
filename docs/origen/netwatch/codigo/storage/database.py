"""Comparte la conexión SQLite entre hilos y serializa el acceso con un candado."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Iterable, List, Sequence, Union

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices(
    mac TEXT PRIMARY KEY, ip TEXT, hostname TEXT, alias TEXT,
    random_mac INTEGER, first_seen INTEGER, last_seen INTEGER,
    online INTEGER, misses INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS probes(
    ts INTEGER, kind TEXT, target TEXT, ok INTEGER, ms REAL);
CREATE INDEX IF NOT EXISTS probes_ts ON probes(ts);
CREATE TABLE IF NOT EXISTS events(ts INTEGER, kind TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS speed(ts INTEGER, down REAL, up REAL);
"""

# Declara aquí cada columna nueva que debas migrar: (tabla, columna, tipo).
MIGRATIONS = [("devices", "network", "TEXT")]

TABLES = ("devices", "probes", "events", "speed", "meta")


class Database:
    def __init__(self, path: Union[str, Path]):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def query(self, sql: str, args: Sequence = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def execute(self, sql: str, args: Sequence = ()) -> None:
        with self._lock:
            self._conn.execute(sql, args)
            self._conn.commit()

    def migrate(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA)
            for table, column, kind in MIGRATIONS:
                columns = [r[1] for r in self._conn.execute(f"PRAGMA table_info({table})")]
                if column not in columns:
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
            self._conn.commit()

    def clear(self, tables: Iterable[str] = TABLES) -> None:
        for table in tables:
            if table not in TABLES:
                raise ValueError(f"tabla desconocida: {table}")
            self.execute(f"DELETE FROM {table}")
