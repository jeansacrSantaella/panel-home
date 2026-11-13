import unittest

from netwatch.monitors.connectivity import ConnectivityMonitor
from netwatch.monitors.inventory import InventoryScanner
from tests.helpers import FakeVendors, RecordingBus, memory_repos

OK, FAIL = (True, 5.0), (False, None)


def results(gw, wan, dns):
    return {("ping", "gateway"): gw, ("ping", "1.1.1.1"): wan, ("ping", "8.8.8.8"): wan,
            ("dns", "gateway"): dns, ("dns", "1.1.1.1"): dns, ("dns", "8.8.8.8"): dns}


class ConnectivityTest(unittest.TestCase):
    def setUp(self):
        _, repos = memory_repos()
        self.bus = RecordingBus()
        self.monitor = ConnectivityMonitor(repos.probes, self.bus, ["1.1.1.1", "8.8.8.8"], 5, 3)

    def test_needs_consecutive_failures_and_dates_from_first(self):
        for t in (100, 105):
            self.monitor.evaluate(results(OK, FAIL, OK), t)
        self.assertEqual(self.bus.kinds(), [])
        self.monitor.evaluate(results(OK, FAIL, OK), 110)
        self.assertEqual(self.bus.kinds(), ["wan_down"])
        self.assertEqual(self.monitor.services["wan"].down_since, 100)
        self.assertFalse(self.monitor.is_up("wan"))

        self.monitor.evaluate(results(OK, OK, OK), 160)
        self.assertEqual(self.bus.kinds(), ["wan_down", "wan_up"])
        self.assertIn("1m 0s", self.bus.published[-1].detail)

    def test_lan_outage_does_not_blame_internet_or_dns(self):
        for t in range(3):
            self.monitor.evaluate(results(FAIL, FAIL, FAIL), t)
        self.assertEqual(self.bus.kinds(), ["lan_down"])


class InventoryTest(unittest.TestCase):
    def setUp(self):
        _, self.repos = memory_repos()
        self.bus = RecordingBus()
        self.arp = {"aa:00:00:00:00:01": "192.168.1.10"}
        self.scanner = InventoryScanner(
            self.repos.devices, self.bus, FakeVendors(), interval=120, misses_to_offline=2,
            find_local_ip=lambda: "192.168.1.2", read_arp=lambda: dict(self.arp),
            reverse_dns=lambda ip: "tv.local", pinger=lambda host, timeout: (False, None))

    def test_first_scan_is_silent_then_tracks_offline_and_online(self):
        self.scanner.run_once()
        self.assertEqual(self.bus.kinds(), ["new_device"])
        self.assertFalse(self.bus.published[0].notify)  # base vacía: no alerta

        self.arp = {}
        self.scanner.run_once()
        self.scanner.run_once()
        self.assertEqual(self.bus.kinds()[-1], "device_offline")

        self.arp = {"aa:00:00:00:00:01": "192.168.1.11", "aa:00:00:00:00:02": "192.168.1.12"}
        self.scanner.run_once()
        self.assertIn("device_online", self.bus.kinds())
        self.assertTrue(self.bus.published[-1].notify)  # equipo nuevo después del primer escaneo
        self.assertEqual(self.repos.devices.get("aa:00:00:00:00:01")["ip"], "192.168.1.11")

    def test_ignores_other_subnets(self):
        self.arp = {"aa:00:00:00:00:09": "10.0.0.4"}
        self.scanner.run_once()
        self.assertFalse(self.repos.devices.exists_any())


if __name__ == "__main__":
    unittest.main()
