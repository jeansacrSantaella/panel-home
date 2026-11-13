"""Centraliza el SQL y separa las consultas por tabla."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from netwatch.core.events import Event
from netwatch.storage.database import Database

OUTAGE_KINDS = ("lan_down", "wan_down", "dns_down")


class DeviceRepository:
    def __init__(self, db: Database):
        self._db = db

    def get(self, mac: str) -> Optional[dict]:
        rows = self._db.query("SELECT * FROM devices WHERE mac=?", (mac,))
        return dict(rows[0]) if rows else None

    def all(self) -> List[dict]:
        return [dict(r) for r in self._db.query("SELECT * FROM devices")]

    def online(self) -> List[dict]:
        return [dict(r) for r in self._db.query("SELECT mac, ip FROM devices WHERE online=1")]

    def exists_any(self) -> bool:
        return bool(self._db.query("SELECT 1 FROM devices LIMIT 1"))

    def add(self, mac: str, ip: str, hostname: Optional[str], random_mac: bool, now: int) -> None:
        self._db.execute(
            "INSERT INTO devices(mac, ip, hostname, alias, random_mac, first_seen, last_seen, online, misses) "
            "VALUES (?,?,?,NULL,?,?,?,1,0)", (mac, ip, hostname, int(random_mac), now, now))

    def mark_seen(self, mac: str, ip: str, now: int) -> None:
        self._db.execute("UPDATE devices SET ip=?, last_seen=?, online=1, misses=0 WHERE mac=?", (ip, now, mac))

    def set_misses(self, mac: str, misses: int, online: bool) -> None:
        self._db.execute("UPDATE devices SET misses=?, online=? WHERE mac=?", (misses, int(online), mac))

    def set_alias(self, mac: str, alias: Optional[str]) -> None:
        self._db.execute("UPDATE devices SET alias=? WHERE mac=?", (alias, mac))

    def set_network(self, mac: str, network: Optional[str]) -> None:
        self._db.execute("UPDATE devices SET network=? WHERE mac=?", (network, mac))


class ProbeRepository:
    def __init__(self, db: Database):
        self._db = db

    def add(self, ts: int, kind: str, target: str, ok: bool, ms: Optional[float]) -> None:
        self._db.execute("INSERT INTO probes VALUES (?,?,?,?,?)", (ts, kind, target, int(ok), ms))

    def samples_since(self, since: int) -> Dict[Tuple[str, str], List[Tuple[Optional[float], int]]]:
        """Agrupa por (kind, target) los pings a destinos y equipos, en orden."""
        per: Dict[Tuple[str, str], list] = {}
        for r in self._db.query("SELECT kind, target, ms, ok FROM probes WHERE ts>? AND kind IN ('ping','dev') "
                                "ORDER BY ts", (since,)):
            per.setdefault((r["kind"], r["target"]), []).append((r["ms"], r["ok"]))
        return per

    def success_by_bucket(self, since: int, bucket: int) -> list:
        """Proporción de mediciones correctas por tramo de `bucket` segundos."""
        return self._db.query(
            "SELECT ts/? AS b, kind, target, AVG(ok) AS a FROM probes "
            "WHERE ts>? AND kind IN ('ping','dns') GROUP BY b, kind, target", (bucket, since))

    def latency_per_minute(self, since: int) -> Dict[str, list]:
        series: Dict[str, list] = {}
        for r in self._db.query("SELECT target, ts/60 AS m, AVG(ms) AS ms, MIN(ok) AS ok FROM probes "
                                "WHERE ts>? AND kind='ping' GROUP BY target, m ORDER BY m", (since,)):
            series.setdefault(r["target"], []).append([r["m"] * 60, r["ms"], r["ok"]])
        return series

    def purge_before(self, ts: int) -> None:
        self._db.execute("DELETE FROM probes WHERE ts<?", (ts,))


@dataclass(frozen=True)
class EventFilter:
    start: Optional[int] = None  # incluido
    end: Optional[int] = None    # excluido
    kind: str = ""

    def where(self) -> Tuple[str, list]:
        clauses, args = [], []
        if self.start is not None:
            clauses.append("ts>=?")
            args.append(self.start)
        if self.end is not None:
            clauses.append("ts<?")
            args.append(self.end)
        if self.kind:
            clauses.append("kind=?")
            args.append(self.kind)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), args


class EventRepository:
    def __init__(self, db: Database):
        self._db = db

    def add(self, event: Event) -> None:
        self._db.execute("INSERT INTO events VALUES (?,?,?)", (event.ts, event.kind, event.detail))

    def recent(self, limit: int) -> List[dict]:
        return [dict(r) for r in self._db.query("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))]

    def details_since(self, kind: str, since: int) -> List[str]:
        return [r["detail"] for r in self._db.query("SELECT detail FROM events WHERE kind=? AND ts>?", (kind, since))]

    def outages_by_hour(self) -> List[int]:
        marks = ",".join("?" * len(OUTAGE_KINDS))
        hours = [0] * 24
        for r in self._db.query("SELECT strftime('%H', ts, 'unixepoch', 'localtime') AS h, COUNT(*) AS c "
                                f"FROM events WHERE kind IN ({marks}) GROUP BY h", OUTAGE_KINDS):
            hours[int(r["h"])] = r["c"]
        return hours

    def kinds(self) -> List[str]:
        return [r["kind"] for r in self._db.query("SELECT DISTINCT kind FROM events ORDER BY kind")]

    def count(self, flt: EventFilter) -> int:
        where, args = flt.where()
        return self._db.query("SELECT COUNT(*) AS total FROM events" + where, args)[0]["total"]

    def page(self, flt: EventFilter, limit: int, offset: int) -> List[dict]:
        where, args = flt.where()
        return [dict(r) for r in self._db.query(
            "SELECT ts, kind, detail FROM events" + where + " ORDER BY ts DESC LIMIT ? OFFSET ?",
            (*args, limit, offset))]


class SpeedRepository:
    def __init__(self, db: Database):
        self._db = db

    def add(self, ts: int, down: float, up: float) -> None:
        self._db.execute("INSERT INTO speed VALUES (?,?,?)", (ts, down, up))

    def recent(self, limit: Optional[int] = None) -> List[dict]:
        sql = "SELECT ts, down, up FROM speed ORDER BY ts DESC"
        rows = self._db.query(sql + " LIMIT ?", (limit,)) if limit else self._db.query(sql)
        return [dict(r) for r in rows]


class MetaRepository:
    def __init__(self, db: Database):
        self._db = db

    def get(self, key: str) -> Optional[str]:
        rows = self._db.query("SELECT value FROM meta WHERE key=?", (key,))
        return rows[0]["value"] if rows else None

    def set(self, key: str, value: str) -> None:
        self._db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))


@dataclass(frozen=True)
class Repositories:
    devices: DeviceRepository
    probes: ProbeRepository
    events: EventRepository
    speed: SpeedRepository
    meta: MetaRepository

    @classmethod
    def on(cls, db: Database) -> "Repositories":
        return cls(DeviceRepository(db), ProbeRepository(db), EventRepository(db), SpeedRepository(db),
                   MetaRepository(db))
