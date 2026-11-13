"""Pruebas unitarias para la base de datos de red RedDb."""
from __future__ import annotations

import time
import unittest

from panel.db import Db
from panel.red.almacen import RedDb


class TestRedAlmacen(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Db(":memory:")
        self.almacen = RedDb(self.db)

    def test_equipos_operaciones_basicas(self) -> None:
        self.assertFalse(self.almacen.hay_equipos())
        self.assertEqual(self.almacen.equipos(), [])
        self.assertEqual(self.almacen.en_linea(), [])

        mac = "11:22:33:44:55:66"
        ts = 1000
        self.almacen.agregar_equipo(mac, "192.168.1.50", "mi-pc", False, ts)

        self.assertTrue(self.almacen.hay_equipos())
        eq = self.almacen.equipo(mac)
        self.assertIsNotNone(eq)
        self.assertEqual(eq["mac"], mac)
        self.assertEqual(eq["ip"], "192.168.1.50")
        self.assertEqual(eq["hostname"], "mi-pc")
        self.assertEqual(eq["alias"], None)
        self.assertEqual(eq["online"], 1)
        self.assertEqual(eq["misses"], 0)
        self.assertEqual(eq["first_seen"], ts)
        self.assertEqual(eq["last_seen"], ts)

        # marcar_visto
        self.almacen.marcar_visto(mac, "192.168.1.51", 1005)
        eq = self.almacen.equipo(mac)
        self.assertEqual(eq["ip"], "192.168.1.51")
        self.assertEqual(eq["last_seen"], 1005)

        # fijar_fallos
        self.almacen.fijar_fallos(mac, 3, False)
        eq = self.almacen.equipo(mac)
        self.assertEqual(eq["misses"], 3)
        self.assertEqual(eq["online"], 0)
        self.assertEqual(len(self.almacen.en_linea()), 0)

        # fijar_alias y fijar_red
        self.almacen.fijar_alias(mac, "Servidor")
        eq = self.almacen.equipo(mac)
        self.assertEqual(eq["alias"], "Servidor")

        self.almacen.fijar_alias(mac, "")
        eq = self.almacen.equipo(mac)
        self.assertIsNone(eq["alias"])

        self.almacen.fijar_red(mac, "lan")
        eq = self.almacen.equipo(mac)
        self.assertEqual(eq["network"], "lan")

    def test_sondeos_y_agregaciones(self) -> None:
        filas = [
            (100, "ping", "gateway", True, 2.5),
            (105, "ping", "gateway", False, None),
            (110, "dev", "11:22:33:44:55:66", True, 1.2),
            (115, "dns", "1.1.1.1", True, 15.0),
        ]
        self.almacen.agregar_sondeos(filas)

        # muestras_desde agrupa por (kind, target), excluye dns
        muestras = self.almacen.muestras_desde(90)
        self.assertIn(("ping", "gateway"), muestras)
        self.assertIn(("dev", "11:22:33:44:55:66"), muestras)
        self.assertNotIn(("dns", "1.1.1.1"), muestras)
        self.assertEqual(len(muestras[("ping", "gateway")]), 2)
        self.assertEqual(muestras[("ping", "gateway")][0], (2.5, 1))
        self.assertEqual(muestras[("ping", "gateway")][1], (None, 0))

        # respeta desde
        muestras_recientes = self.almacen.muestras_desde(102)
        self.assertEqual(len(muestras_recientes[("ping", "gateway")]), 1)

        # exito_por_tramo (2 ok y 2 fallidos -> a = 0.5)
        sondeos_tramo = [
            (200, "ping", "1.1.1.1", True, 10.0),
            (210, "ping", "1.1.1.1", True, 12.0),
            (220, "ping", "1.1.1.1", False, None),
            (230, "ping", "1.1.1.1", False, None),
        ]
        self.almacen.agregar_sondeos(sondeos_tramo)
        exito = self.almacen.exito_por_tramo(190, 300)
        t_1_1_1_1 = [e for e in exito if e["target"] == "1.1.1.1"]
        self.assertEqual(len(t_1_1_1_1), 1)
        self.assertAlmostEqual(t_1_1_1_1[0]["a"], 0.5)

        # latencia_por_minuto agrupa por minuto (ts/60)
        lat = self.almacen.latencia_por_minuto(190)
        self.assertIn("1.1.1.1", lat)
        self.assertEqual(len(lat["1.1.1.1"]), 1)
        ts_minuto, ms_prom, ok_min = lat["1.1.1.1"][0]
        self.assertEqual(ts_minuto, 180)  # 200 // 60 * 60
        self.assertAlmostEqual(ms_prom, 11.0)
        self.assertEqual(ok_min, 0)

        # podar_sondeos
        self.almacen.podar_sondeos(200)
        muestras_post_poda = self.almacen.muestras_desde(0)
        self.assertNotIn(("dev", "11:22:33:44:55:66"), muestras_post_poda)

    def test_eventos_y_caidas(self) -> None:
        self.almacen.agregar_evento(100, "lan_down", "Caída LAN 1")
        self.almacen.agregar_evento(200, "wan_down", "Caída WAN 1")
        self.almacen.agregar_evento(300, "lan_down", "Caída LAN 2")
        self.almacen.agregar_evento(400, "dispositivo_nuevo", "Nuevo equipo")

        recientes = self.almacen.eventos_recientes(2)
        self.assertEqual(len(recientes), 2)
        self.assertEqual(recientes[0]["ts"], 400)
        self.assertEqual(recientes[1]["ts"], 300)

        detalles = self.almacen.detalles_desde("lan_down", 150)
        self.assertEqual(detalles, ["Caída LAN 2"])

        tipos = self.almacen.tipos_evento()
        self.assertEqual(tipos, ["dispositivo_nuevo", "lan_down", "wan_down"])

        # contar y página
        total = self.almacen.contar_eventos(100, 400)  # 100 incluido, 400 excluido
        self.assertEqual(total, 3)

        pagina = self.almacen.pagina_eventos(inicio=100, fin=400, limite=2, desplazamiento=0)
        self.assertEqual(len(pagina), 2)
        self.assertEqual(pagina[0]["ts"], 300)

        pagina_filtrada = self.almacen.pagina_eventos(kind="lan_down")
        self.assertEqual(len(pagina_filtrada), 2)

        # caidas_por_hora
        caidas = self.almacen.caidas_por_hora()
        self.assertEqual(len(caidas), 24)
        self.assertEqual(sum(caidas), 3)

    def test_velocidad_y_estado(self) -> None:
        self.almacen.agregar_velocidad(100, 100.5, 20.0)
        self.almacen.agregar_velocidad(200, 200.0, 50.0)

        vel_todas = self.almacen.velocidad_reciente()
        self.assertEqual(len(vel_todas), 2)
        self.assertEqual(vel_todas[0]["ts"], 200)

        vel_lim = self.almacen.velocidad_reciente(limite=1)
        self.assertEqual(len(vel_lim), 1)
        self.assertEqual(vel_lim[0]["ts"], 200)

        # get y set con prefijo red:
        self.almacen.set("config", {"scan_interval": 30})
        val = self.almacen.get("config")
        self.assertEqual(val, {"scan_interval": 30})
        self.assertEqual(self.db.get("red:config"), {"scan_interval": 30})


if __name__ == "__main__":
    unittest.main()
