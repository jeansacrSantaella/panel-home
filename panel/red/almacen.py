"""Base de datos de la red sobre SQLite utilizando panel.db.Db."""
from __future__ import annotations

OUTAGE_KINDS = ("lan_down", "wan_down", "dns_down")


class RedDb:
    def __init__(self, db) -> None:
        self._db = db
        # Crear tablas e índices de la red
        self._db._x(
            "CREATE TABLE IF NOT EXISTS red_equipos("
            "mac TEXT PRIMARY KEY, ip TEXT, hostname TEXT, alias TEXT, "
            "random_mac INTEGER, first_seen INTEGER, last_seen INTEGER, "
            "online INTEGER, misses INTEGER DEFAULT 0, network TEXT)"
        )
        self._db._x(
            "CREATE TABLE IF NOT EXISTS red_sondeos("
            "ts INTEGER, kind TEXT, target TEXT, ok INTEGER, ms REAL)"
        )
        self._db._x("CREATE INDEX IF NOT EXISTS red_sondeos_ts ON red_sondeos(ts)")
        self._db._x(
            "CREATE TABLE IF NOT EXISTS red_eventos("
            "ts INTEGER, kind TEXT, detail TEXT)"
        )
        self._db._x("CREATE INDEX IF NOT EXISTS red_eventos_ts ON red_eventos(ts)")
        self._db._x(
            "CREATE TABLE IF NOT EXISTS red_velocidad("
            "ts INTEGER, down REAL, up REAL)"
        )

    # --- Equipos ---

    def equipo(self, mac: str) -> dict | None:
        filas = self._db._q("SELECT * FROM red_equipos WHERE mac=?", (mac,))
        return filas[0] if filas else None

    def equipos(self) -> list[dict]:
        return self._db._q("SELECT * FROM red_equipos")

    def en_linea(self) -> list[dict]:
        return self._db._q("SELECT * FROM red_equipos WHERE online=1")

    def hay_equipos(self) -> bool:
        return bool(self._db._q("SELECT 1 FROM red_equipos LIMIT 1"))

    def agregar_equipo(self, mac: str, ip: str, hostname: str | None, random_mac: bool, ts: int) -> None:
        self._db._x(
            "INSERT INTO red_equipos(mac, ip, hostname, alias, random_mac, first_seen, last_seen, online, misses, network) "
            "VALUES (?,?,?,NULL,?,?,?,1,0,NULL)",
            (mac, ip, hostname, int(random_mac), ts, ts),
        )

    def marcar_visto(self, mac: str, ip: str, ts: int) -> None:
        self._db._x(
            "UPDATE red_equipos SET ip=?, last_seen=?, online=1, misses=0 WHERE mac=?",
            (ip, ts, mac),
        )

    def fijar_fallos(self, mac: str, misses: int, online: bool) -> None:
        self._db._x(
            "UPDATE red_equipos SET misses=?, online=? WHERE mac=?",
            (misses, int(online), mac),
        )

    def fijar_alias(self, mac: str, alias: str | None) -> None:
        val = alias if alias else None
        self._db._x("UPDATE red_equipos SET alias=? WHERE mac=?", (val, mac))

    def fijar_red(self, mac: str, network: str | None) -> None:
        val = network if network else None
        self._db._x("UPDATE red_equipos SET network=? WHERE mac=?", (val, mac))

    # --- Sondeos ---

    def agregar_sondeos(self, filas: list) -> None:
        if not filas:
            return
        datos = [(f[0], f[1], f[2], int(f[3]), f[4]) for f in filas]
        self._db._x(
            "INSERT INTO red_sondeos(ts, kind, target, ok, ms) VALUES (?,?,?,?,?)",
            datos,
            muchos=True,
        )

    def muestras_desde(self, desde: int) -> dict:
        filas = self._db._q(
            "SELECT kind, target, ms, ok FROM red_sondeos WHERE ts>? AND kind IN ('ping','dev') ORDER BY ts",
            (desde,),
        )
        res: dict = {}
        for r in filas:
            res.setdefault((r["kind"], r["target"]), []).append((r["ms"], r["ok"]))
        return res

    def exito_por_tramo(self, desde: int, tramo: int) -> list:
        return self._db._q(
            "SELECT ts/? AS b, kind, target, AVG(ok) AS a FROM red_sondeos "
            "WHERE ts>? AND kind IN ('ping','dns') GROUP BY b, kind, target",
            (tramo, desde),
        )

    def latencia_por_minuto(self, desde: int) -> dict:
        filas = self._db._q(
            "SELECT target, ts/60 AS m, AVG(ms) AS ms, MIN(ok) AS ok FROM red_sondeos "
            "WHERE ts>? AND kind='ping' GROUP BY target, m ORDER BY m",
            (desde,),
        )
        series: dict = {}
        for r in filas:
            series.setdefault(r["target"], []).append([r["m"] * 60, r["ms"], r["ok"]])
        return series

    def podar_sondeos(self, antes: int) -> None:
        self._db._x("DELETE FROM red_sondeos WHERE ts<?", (antes,))

    # --- Eventos ---

    def agregar_evento(self, ts: int, kind: str, detail: str) -> None:
        self._db._x(
            "INSERT INTO red_eventos(ts, kind, detail) VALUES (?,?,?)",
            (ts, kind, detail),
        )

    def eventos_recientes(self, limite: int) -> list:
        return self._db._q(
            "SELECT ts, kind, detail FROM red_eventos ORDER BY ts DESC LIMIT ?",
            (limite,),
        )

    def detalles_desde(self, kind: str, desde: int) -> list:
        filas = self._db._q(
            "SELECT detail FROM red_eventos WHERE kind=? AND ts>?",
            (kind, desde),
        )
        return [r["detail"] for r in filas]

    def caidas_por_hora(self) -> list:
        marcas = ",".join("?" * len(OUTAGE_KINDS))
        horas = [0] * 24
        filas = self._db._q(
            "SELECT strftime('%H', ts, 'unixepoch', 'localtime') AS h, COUNT(*) AS c "
            f"FROM red_eventos WHERE kind IN ({marcas}) GROUP BY h",
            OUTAGE_KINDS,
        )
        for r in filas:
            if r["h"] is not None:
                horas[int(r["h"])] = r["c"]
        return horas

    def tipos_evento(self) -> list:
        filas = self._db._q("SELECT DISTINCT kind FROM red_eventos ORDER BY kind")
        return [r["kind"] for r in filas]

    def _filtro_eventos(self, inicio: int | None, fin: int | None, kind: str) -> tuple[str, list]:
        clausulas, args = [], []
        if inicio is not None:
            clausulas.append("ts>=?")
            args.append(inicio)
        if fin is not None:
            clausulas.append("ts<?")
            args.append(fin)
        if kind:
            clausulas.append("kind=?")
            args.append(kind)
        where = (" WHERE " + " AND ".join(clausulas)) if clausulas else ""
        return where, args

    def contar_eventos(self, inicio: int | None = None, fin: int | None = None, kind: str = "") -> int:
        where, args = self._filtro_eventos(inicio, fin, kind)
        res = self._db._q("SELECT COUNT(*) AS total FROM red_eventos" + where, args)
        return res[0]["total"] if res else 0

    def pagina_eventos(
        self,
        inicio: int | None = None,
        fin: int | None = None,
        kind: str = "",
        limite: int = 25,
        desplazamiento: int = 0,
    ) -> list:
        where, args = self._filtro_eventos(inicio, fin, kind)
        args.extend([limite, desplazamiento])
        return self._db._q(
            "SELECT ts, kind, detail FROM red_eventos" + where + " ORDER BY ts DESC LIMIT ? OFFSET ?",
            args,
        )

    # --- Velocidad ---

    def agregar_velocidad(self, ts: int, down: float, up: float) -> None:
        self._db._x(
            "INSERT INTO red_velocidad(ts, down, up) VALUES (?,?,?)",
            (ts, down, up),
        )

    def velocidad_reciente(self, limite: int | None = None) -> list:
        if limite is not None:
            return self._db._q("SELECT ts, down, up FROM red_velocidad ORDER BY ts DESC LIMIT ?", (limite,))
        return self._db._q("SELECT ts, down, up FROM red_velocidad ORDER BY ts DESC")

    # --- Estado global con prefijo red: ---

    def get(self, clave: str, defecto=None):
        return self._db.get("red:" + clave, defecto)

    def set(self, clave: str, valor) -> None:
        self._db.set("red:" + clave, valor)
