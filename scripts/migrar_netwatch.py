from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import panel.config
from panel.db import Db
from panel.red.almacen import RedDb


def migrar(
    origen: sqlite3.Connection,
    red: RedDb,
    sondeos_dias: int = 1,
    ahora: int | None = None,
) -> dict:
    """Migra datos de una base NetWatch a RedDb de forma idempotente."""
    if ahora is None:
        ahora = int(time.time())

    res = {
        "equipos": 0,
        "eventos": 0,
        "sondeos": 0,
        "velocidad": 0,
        "ip_publica": 0,
    }

    # 1. Equipos
    # No se usa red.agregar_equipo porque fija alias/network a NULL, misses a 0,
    # y no conserva first_seen, last_seen, online ni misses de la base origen.
    info = origen.execute("PRAGMA table_info(devices)").fetchall()
    columnas = [r[1] for r in info]
    if "network" in columnas:
        sql_dev = "SELECT mac, ip, hostname, alias, random_mac, first_seen, last_seen, online, misses, network FROM devices"
    else:
        sql_dev = "SELECT mac, ip, hostname, alias, random_mac, first_seen, last_seen, online, misses, NULL AS network FROM devices"

    filas_dev = origen.execute(sql_dev).fetchall()
    for row in filas_dev:
        mac = row["mac"]
        alias = row["alias"]
        network = row["network"]
        existente = red.equipo(mac)

        if existente:
            if not existente.get("alias") and alias:
                red.fijar_alias(mac, alias)
            if not existente.get("network") and network:
                red.fijar_red(mac, network)
        else:
            args = (
                mac,
                row["ip"],
                row["hostname"],
                alias,
                int(row["random_mac"]) if row["random_mac"] is not None else 0,
                row["first_seen"],
                row["last_seen"],
                int(row["online"]) if row["online"] is not None else 0,
                int(row["misses"]) if row["misses"] is not None else 0,
                network,
            )
            rc = red._db._x(
                "INSERT OR IGNORE INTO red_equipos(mac, ip, hostname, alias, random_mac, first_seen, last_seen, online, misses, network) VALUES (?,?,?,?,?,?,?,?,?,?)",
                args,
            )
            if rc == 1:
                res["equipos"] += 1

    # 2. Eventos
    existentes_ev = {
        (r["ts"], r["kind"], r["detail"])
        for r in red._db._q("SELECT ts, kind, detail FROM red_eventos")
    }
    filas_ev = origen.execute("SELECT ts, kind, detail FROM events").fetchall()
    for r in filas_ev:
        clave_ev = (r["ts"], r["kind"], r["detail"])
        if clave_ev not in existentes_ev:
            red.agregar_evento(r["ts"], r["kind"], r["detail"])
            existentes_ev.add(clave_ev)
            res["eventos"] += 1

    # 3. Sondeos
    if sondeos_dias > 0:
        max_res = red._db._q("SELECT MAX(ts) AS max_ts FROM red_sondeos")
        max_ts = max_res[0]["max_ts"] if max_res and max_res[0]["max_ts"] is not None else 0
        corte_ts = ahora - sondeos_dias * 86400
        filas_probes = origen.execute(
            "SELECT ts, kind, target, ok, ms FROM probes WHERE ts > ? AND ts >= ? ORDER BY ts",
            (max_ts, corte_ts),
        ).fetchall()
        filas_agregar = [(r["ts"], r["kind"], r["target"], r["ok"], r["ms"]) for r in filas_probes]
        if filas_agregar:
            red.agregar_sondeos(filas_agregar)
            res["sondeos"] = len(filas_agregar)

    # 4. Velocidad
    existentes_vel = {
        (r["ts"], r["down"], r["up"])
        for r in red._db._q("SELECT ts, down, up FROM red_velocidad")
    }
    filas_speed = origen.execute("SELECT ts, down, up FROM speed").fetchall()
    for r in filas_speed:
        clave_vel = (r["ts"], r["down"], r["up"])
        if clave_vel not in existentes_vel:
            red.agregar_velocidad(r["ts"], r["down"], r["up"])
            existentes_vel.add(clave_vel)
            res["velocidad"] += 1

    # 5. IP pública
    filas_meta = origen.execute("SELECT value FROM meta WHERE key = 'public_ip'").fetchall()
    if filas_meta:
        pub_ip = filas_meta[0]["value"]
        if pub_ip and not red.get("ip_publica"):
            red.set("ip_publica", pub_ip)
            res["ip_publica"] = 1

    return res


def main(argv: list[str] | None = None) -> int:
    panel.config.leer_env()
    cfg = panel.config.cargar()

    parser = argparse.ArgumentParser(description="Migrar datos de NetWatch a RedDb")
    parser.add_argument("ruta_origen", metavar="RUTA/netwatch.db", help="Ruta a la base de datos origen de NetWatch")
    parser.add_argument("--panel-db", default=str(cfg.db_path), help="Ruta a la base de datos destino del panel")
    parser.add_argument("--sondeos-dias", type=int, default=1, help="Días de sondeos a copiar (0 para omitir)")

    args = parser.parse_args(argv)

    path_origen = Path(args.ruta_origen).resolve()
    if not path_origen.is_file():
        print(f"Error: El archivo de origen '{args.ruta_origen}' no existe.", file=sys.stderr)
        return 1

    uri_origen = f"{path_origen.as_uri()}?mode=ro"
    con_origen = sqlite3.connect(uri_origen, uri=True)
    con_origen.row_factory = sqlite3.Row

    db_panel = Db(args.panel_db)
    red = RedDb(db_panel)

    try:
        resultado = migrar(con_origen, red, sondeos_dias=args.sondeos_dias)
    finally:
        con_origen.close()

    print("Resumen de migración:")
    print(f"  Equipos: {resultado['equipos']}")
    print(f"  Eventos: {resultado['eventos']}")
    print(f"  Sondeos: {resultado['sondeos']}")
    print(f"  Velocidad: {resultado['velocidad']}")
    print(f"  IP pública: {resultado['ip_publica']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
