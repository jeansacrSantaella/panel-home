"""Rama Windows de sonda.medir con salidas de ejemplo (español e inglés), sin ejecutar comandos."""
from __future__ import annotations

import unittest
from unittest import mock

from sonda import medir

PING_OK_ES = """
Haciendo ping a 192.168.1.1 con 32 bytes de datos:
Respuesta desde 192.168.1.1: bytes=32 tiempo=3ms TTL=64

Estadísticas de ping para 192.168.1.1:
    Paquetes: enviados = 1, recibidos = 1, perdidos = 0
    (0% perdidos),
"""
PING_MENOR_ES = "Respuesta desde 192.168.1.1: bytes=32 tiempo<1m TTL=64\n"
PING_OK_EN = "Reply from 8.8.8.8: bytes=32 time=12ms TTL=118\n"
PING_MENOR_EN = "Reply from 192.168.1.1: bytes=32 time<1ms TTL=64\n"
PING_ESPACIO = "Respuesta desde 1.1.1.1: bytes=32 tiempo=12 ms TTL=57\n"
PING_FALLOS = [
    "Haciendo ping a 192.168.1.77 con 32 bytes de datos:\nTiempo de espera agotado para esta solicitud.\n",
    "Respuesta desde 192.168.1.94: Host de destino inaccesible.\n",
    "Request timed out.\n",
    "Reply from 192.168.1.94: Destination host unreachable.\n",
    "Error general.\n",
    "La solicitud de ping no pudo encontrar el host nombre.invalido. Compruebe el nombre y vuelva a intentarlo.\n",
    "Respuesta desde 10.0.0.1: TTL expirado en tránsito.\n",
    "Reply from 10.0.0.1: TTL expired in transit.\n",
]

ARP_ES = """
Interfaz: 192.168.1.94 --- 0x5
  Dirección de Internet          Dirección física      Tipo
  192.168.1.1           aa-bb-cc-dd-ee-ff     dinámico
  192.168.1.20          11-22-33-44-55-66     dinámico
  192.168.1.255         ff-ff-ff-ff-ff-ff     estático
  224.0.0.22            01-00-5e-00-00-16     estático
  239.255.255.250       01-00-5e-7f-ff-fa     estático
  255.255.255.255       ff-ff-ff-ff-ff-ff     estático

Interfaz: 172.28.48.1 --- 0x12
  Dirección de Internet          Dirección física      Tipo
  172.28.50.10          00-15-5d-aa-bb-cc     dinámico
  172.28.63.255         ff-ff-ff-ff-ff-ff     estático
  224.0.0.22            01-00-5e-00-00-16     estático
  ff02::16              33-33-00-00-00-16     estático

Interfaz: 172.17.0.1 --- 0x14
  Dirección de Internet          Dirección física      Tipo
  172.17.0.2            02-42-ac-11-00-02     dinámico
  172.17.0.9            00-00-00-00-00-00     estático
"""
ARP_EN = """
Interface: 192.168.1.94 --- 0x5
  Internet Address      Physical Address      Type
  192.168.1.30          de-ad-be-ef-00-01     dynamic
  192.168.1.255         ff-ff-ff-ff-ff-ff     static
  224.0.0.251           01-00-5e-00-00-fb     static
"""

ROUTE_ES = """===========================================================================
Lista de interfaces
  5...a4 bb 6d 11 22 33 ......Intel(R) Wi-Fi 6 AX201 160MHz
 18...00 15 5d aa bb cc ......Hyper-V Virtual Ethernet Adapter
===========================================================================

IPv4 Tabla de enrutamiento
===========================================================================
Rutas activas:
Destino de red    Máscara de red  Puerta de enlace   Interfaz  Métrica
          0.0.0.0          0.0.0.0      172.28.48.2    172.28.48.1     5000
          0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.94      35
        127.0.0.0        255.0.0.0         En vínculo         127.0.0.1    331
      172.28.48.0    255.255.240.0         En vínculo       172.28.48.1   5256
===========================================================================
Rutas persistentes:
  Ninguno
"""
ROUTE_EN = """IPv4 Route Table
===========================================================================
Active Routes:
Network Destination        Netmask          Gateway       Interface  Metric
          0.0.0.0          0.0.0.0      192.168.1.1    192.168.1.94     50
          0.0.0.0          0.0.0.0      10.0.0.1       10.0.0.7         25
        127.0.0.0        255.0.0.0         On-link         127.0.0.1    331
===========================================================================
Persistent Routes:
  Network Address          Netmask  Gateway Address  Metric
          0.0.0.0          0.0.0.0      192.168.1.1  Default
"""
ROUTE_SIN = "Rutas activas:\n        127.0.0.0        255.0.0.0         En vínculo         127.0.0.1    331\n"


def _win():
    return mock.patch.object(medir, "ES_WINDOWS", True)


class TestPingWindows(unittest.TestCase):
    def test_parse_exitos(self):
        self.assertEqual(medir.parse_ping(PING_OK_ES), ([3.0], 64))
        self.assertEqual(medir.parse_ping(PING_MENOR_ES), ([1.0], 64))
        self.assertEqual(medir.parse_ping(PING_OK_EN), ([12.0], 118))
        self.assertEqual(medir.parse_ping(PING_MENOR_EN), ([1.0], 64))
        self.assertEqual(medir.parse_ping(PING_ESPACIO), ([12.0], 57))

    def test_parse_fallos(self):
        for t in PING_FALLOS:
            self.assertEqual(medir.parse_ping(t), ([], None), t)

    def test_ping_ok(self):
        with _win(), mock.patch.object(medir, "_ejecutar", return_value=(0, PING_OK_ES)):
            self.assertEqual(medir.ping("192.168.1.1"), (True, 3.0))
        with _win(), mock.patch.object(medir, "_ejecutar", return_value=(0, PING_MENOR_ES)):
            self.assertEqual(medir.ping("192.168.1.1"), (True, 1.0))

    def test_ping_fallos_con_codigo_cero(self):
        for t in PING_FALLOS:
            with _win(), mock.patch.object(medir, "_ejecutar", return_value=(0, t)):
                self.assertEqual(medir.ping("x"), (False, None), t)

    def test_ping_excepcion(self):
        with _win(), mock.patch.object(medir, "_ejecutar", side_effect=OSError):
            self.assertEqual(medir.ping("x"), (False, None))

    def test_ping_series(self):
        salida = PING_OK_ES + PING_MENOR_ES + PING_FALLOS[0] + PING_FALLOS[6]
        with _win(), mock.patch.object(medir, "_correr", return_value=salida) as c:
            self.assertEqual(medir.ping_series("192.168.1.1", 4), ([3.0, 1.0], 64))
            self.assertEqual(c.call_args[0][0][:3], ["ping", "-n", "4"])
        with _win(), mock.patch.object(medir, "_correr", return_value=PING_FALLOS[0]):
            self.assertEqual(medir.ping_series("x"), ([], None))


class TestCodificacion(unittest.TestCase):
    def test_cp850(self):
        datos = "dinámico estático Dirección".encode("cp850")
        with _win():
            texto = medir._decodificar(datos)
        self.assertIn("din", texto)
        self.assertIn("Dirección", texto)  # cp850 es el OEM del español; 'oem' solo existe en Windows

    def test_nunca_falla(self):
        with _win():
            self.assertIsInstance(medir._decodificar(bytes(range(256))), str)
        self.assertIsInstance(medir._decodificar(bytes(range(256))), str)

    def test_arp_desde_bytes_oem(self):
        datos = ARP_ES.encode("cp850")
        with _win(), mock.patch.object(medir.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=datos)
            self.assertEqual(medir.read_arp()["aa:bb:cc:dd:ee:ff"], "192.168.1.1")


class TestArpWindows(unittest.TestCase):
    def test_tres_interfaces(self):
        self.assertEqual(medir.parse_arp([ARP_ES]), {
            "aa:bb:cc:dd:ee:ff": "192.168.1.1",
            "11:22:33:44:55:66": "192.168.1.20",
            "00:15:5d:aa:bb:cc": "172.28.50.10",
            "02:42:ac:11:00:02": "172.17.0.2",
        })

    def test_ingles(self):
        self.assertEqual(medir.parse_arp([ARP_EN]), {"de:ad:be:ef:00:01": "192.168.1.30"})

    def test_interfaces(self):
        self.assertEqual(medir.parse_interfaces_arp(ARP_ES), ["192.168.1.94", "172.28.48.1", "172.17.0.1"])
        self.assertEqual(medir.parse_interfaces_arp(ARP_EN), ["192.168.1.94"])

    def test_read_arp_usa_arp_a(self):
        with _win(), mock.patch.object(medir, "_correr", return_value=ARP_EN) as c:
            self.assertEqual(medir.read_arp(), {"de:ad:be:ef:00:01": "192.168.1.30"})
            c.assert_called_once_with(["arp", "-a"], 5)


class TestGatewayWindows(unittest.TestCase):
    def test_menor_metrica(self):
        self.assertEqual(medir.parse_route_print(ROUTE_ES), "192.168.1.1")
        self.assertEqual(medir.parse_route_print(ROUTE_EN), "10.0.0.1")

    def test_sin_ruta(self):
        self.assertIsNone(medir.parse_route_print(ROUTE_SIN))
        self.assertIsNone(medir.parse_route_print(""))

    def test_gateway(self):
        with _win(), mock.patch.object(medir, "_correr", return_value=ROUTE_ES) as c:
            self.assertEqual(medir.gateway(), "192.168.1.1")
            c.assert_called_once_with(["route", "print", "0.0.0.0"], 5)
        with _win(), mock.patch.object(medir, "_correr", side_effect=OSError):
            self.assertIsNone(medir.gateway())


class TestIpLocal(unittest.TestCase):
    def test_elegir(self):
        cand = medir.parse_interfaces_arp(ARP_ES)
        self.assertEqual(medir.elegir_ip_local("172.28.48.1", "192.168.1.1", cand), "192.168.1.94")
        self.assertEqual(medir.elegir_ip_local("169.254.3.4", "192.168.1.1", cand), "192.168.1.94")
        self.assertEqual(medir.elegir_ip_local("192.168.1.94", "192.168.1.1", cand), "192.168.1.94")
        self.assertEqual(medir.elegir_ip_local("172.15.0.1", "192.168.1.1", cand), "172.15.0.1")  # no es 172.16/12
        self.assertEqual(medir.elegir_ip_local("172.28.48.1", "192.168.1.1", ["172.17.0.1"]), "172.28.48.1")
        self.assertEqual(medir.elegir_ip_local("172.28.48.1", None, cand), "172.28.48.1")
        self.assertIsNone(medir.elegir_ip_local(None, "192.168.1.1", cand))

    def test_local_ip_integrada(self):
        sock = mock.Mock()
        sock.getsockname.return_value = ("172.28.48.1", 1234)
        with _win(), mock.patch.object(medir.socket, "socket", return_value=sock), \
                mock.patch.object(medir, "gateway", return_value="192.168.1.1"), \
                mock.patch.object(medir, "_correr", return_value=ARP_ES):
            self.assertEqual(medir.local_ip(), "192.168.1.94")


if __name__ == "__main__":
    unittest.main()
