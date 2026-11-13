from __future__ import annotations

import contextlib
import io
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

from panel.db import Db
from panel.red.almacen import RedDb
from scripts.migrar_netwatch import main, migrar

AHORA = 1_800_000_000


class TestMigrarNetwatch(unittest.TestCase):
    def setUp(self) -> None:
        # Directorio y base de datos temporal
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "netwatch.db")
        self._crear_base_origen(self.db_path)

        # Conexión origen
        self.origen = sqlite3.connect(self.db_path)
        self.origen.row_factory = sqlite3.Row

        # Destino en memoria
        self.red = RedDb(Db(":memory:"))

    def tearDown(self) -> None:
        self.origen.close()
        shutil.rmtree(self.temp_dir)

    def _crear_base_origen(self, ruta: str) -> None:
        """Crea y pobla la base de datos de origen NetWatch."""
        con = sqlite3.connect(ruta)
        con.execute(
            "CREATE TABLE devices(mac TEXT PRIMARY KEY, ip TEXT, hostname TEXT, alias TEXT, "
            "random_mac INTEGER, first_seen INTEGER, last_seen INTEGER, online INTEGER, "
            "misses INTEGER DEFAULT 0, network TEXT)"
        )
        con.execute("CREATE TABLE probes(ts INTEGER, kind TEXT, target TEXT, ok INTEGER, ms REAL)")
        con.execute("CREATE TABLE events(ts INTEGER, kind TEXT, detail TEXT)")
        con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        con.execute("CREATE TABLE speed(ts INTEGER, down REAL, up REAL)")

        # Equipos (uno con alias y uno sin alias)
        con.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("aa:bb:cc:00:00:01", "192.168.1.1", "router", "Router", 0, AHORA - 1000, AHORA, 1, 0, "192.168.1.0/24"),
        )
        con.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("aa:bb:cc:00:00:02", "192.168.1.2", "pc", None, 0, AHORA - 1000, AHORA, 1, 0, "192.168.1.0/24"),
        )

        # Eventos
        con.execute("INSERT INTO events VALUES (?, ?, ?)", (AHORA - 100, "lan_down", "Caida LAN"))
        con.execute("INSERT INTO events VALUES (?, ?, ?)", (AHORA - 50, "lan_up", "Recuperacion LAN"))
        con.execute("INSERT INTO events VALUES (?, ?, ?)", (AHORA - 10, "wan_down", "Caida WAN"))

        # Sondeos (uno antiguo y uno reciente)
        con.execute("INSERT INTO probes VALUES (?, ?, ?, ?, ?)", (AHORA - 2 * 86400, "ping", "gateway", 1, 2.5))
        con.execute("INSERT INTO probes VALUES (?, ?, ?, ?, ?)", (AHORA - 3600, "ping", "gateway", 1, 1.2))

        # Velocidades
        con.execute("INSERT INTO speed VALUES (?, ?, ?)", (AHORA - 7200, 100.0, 10.0))
        con.execute("INSERT INTO speed VALUES (?, ?, ?)", (AHORA - 3600, 95.5, 9.5))

        # Meta
        con.execute("INSERT INTO meta VALUES (?, ?)", ("public_ip", "203.0.113.7"))

        con.commit()
        con.close()

    def test_conteos(self) -> None:
        """Verifica los conteos retornados en la primera migración."""
        res = migrar(self.origen, self.red, sondeos_dias=1, ahora=AHORA)
        self.assertEqual(res["equipos"], 2)
        self.assertEqual(res["eventos"], 3)
        self.assertEqual(res["sondeos"], 1)
        self.assertEqual(res["velocidad"], 2)
        self.assertEqual(res["ip_publica"], 1)

    def test_sondeos_solo_recientes(self) -> None:
        """Verifica el filtrado de sondeos según sondeos_dias."""
        migrar(self.origen, self.red, sondeos_dias=1, ahora=AHORA)
        filas = self.red._db._q("SELECT ts FROM red_sondeos")
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["ts"], AHORA - 3600)

        # Con sondeos_dias=0 no debe ingresar ninguno
        red_cero = RedDb(Db(":memory:"))
        migrar(self.origen, red_cero, sondeos_dias=0, ahora=AHORA)
        filas_cero = red_cero._db._q("SELECT ts FROM red_sondeos")
        self.assertEqual(len(filas_cero), 0)

    def test_segunda_corrida_en_cero(self) -> None:
        """Verifica la idempotencia en una segunda ejecución de migrar."""
        migrar(self.origen, self.red, sondeos_dias=1, ahora=AHORA)
        res2 = migrar(self.origen, self.red, sondeos_dias=1, ahora=AHORA)
        self.assertEqual(res2["equipos"], 0)
        self.assertEqual(res2["eventos"], 0)
        self.assertEqual(res2["sondeos"], 0)
        self.assertEqual(res2["velocidad"], 0)
        self.assertEqual(res2["ip_publica"], 0)

    def test_no_pisa_alias(self) -> None:
        """Verifica que el alias existente en panel se conserve y se asigne si faltaba."""
        mac_router = "aa:bb:cc:00:00:01"
        self.red.agregar_equipo(mac_router, "192.168.1.1", None, False, AHORA)
        self.red.fijar_alias(mac_router, "Mi alias")

        migrar(self.origen, self.red, sondeos_dias=1, ahora=AHORA)
        self.assertEqual(self.red.equipo(mac_router)["alias"], "Mi alias")

        # Si el equipo no tenía alias en el panel, debe tomar el del origen
        red2 = RedDb(Db(":memory:"))
        red2.agregar_equipo(mac_router, "192.168.1.1", None, False, AHORA)
        migrar(self.origen, red2, sondeos_dias=1, ahora=AHORA)
        self.assertEqual(red2.equipo(mac_router)["alias"], "Router")

    def test_sin_columna_network(self) -> None:
        """Verifica migración cuando el esquema de devices no posee columna network."""
        db_sin_net = os.path.join(self.temp_dir, "sin_network.db")
        con = sqlite3.connect(db_sin_net)
        con.execute(
            "CREATE TABLE devices(mac TEXT PRIMARY KEY, ip TEXT, hostname TEXT, alias TEXT, "
            "random_mac INTEGER, first_seen INTEGER, last_seen INTEGER, online INTEGER, "
            "misses INTEGER DEFAULT 0)"
        )
        con.execute("CREATE TABLE probes(ts INTEGER, kind TEXT, target TEXT, ok INTEGER, ms REAL)")
        con.execute("CREATE TABLE events(ts INTEGER, kind TEXT, detail TEXT)")
        con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        con.execute("CREATE TABLE speed(ts INTEGER, down REAL, up REAL)")

        con.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("aa:bb:cc:00:00:01", "192.168.1.1", "r", "Router", 0, AHORA - 100, AHORA, 1, 0),
        )
        con.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("aa:bb:cc:00:00:02", "192.168.1.2", "p", None, 0, AHORA - 100, AHORA, 1, 0),
        )
        con.commit()
        con.row_factory = sqlite3.Row

        red_sin = RedDb(Db(":memory:"))
        res = migrar(con, red_sin, sondeos_dias=1, ahora=AHORA)
        con.close()

        self.assertEqual(res["equipos"], 2)
        self.assertIsNone(red_sin.equipo("aa:bb:cc:00:00:01")["network"])

    def test_ip_publica_no_pisa(self) -> None:
        """Verifica que si ya existe la IP pública en el panel no se sobreescriba."""
        self.red.set("ip_publica", "198.51.100.1")
        res = migrar(self.origen, self.red, sondeos_dias=1, ahora=AHORA)
        self.assertEqual(res["ip_publica"], 0)
        self.assertEqual(self.red.get("ip_publica"), "198.51.100.1")

    def test_main_origen_inexistente(self) -> None:
        """Verifica que main retorne 1 cuando la ruta del origen no existe."""
        ruta_inexistente = os.path.join(self.temp_dir, "no_existe.db")
        panel_db_temp = os.path.join(self.temp_dir, "panel_temp.db")
        # sin leer el .env real: no debe cambiar el entorno de las demás pruebas
        with contextlib.redirect_stderr(io.StringIO()), mock.patch("panel.config.leer_env", return_value={}):
            code = main([ruta_inexistente, "--panel-db", panel_db_temp])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
