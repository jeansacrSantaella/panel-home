import time
import unittest

from netwatch.core.events import Event
from netwatch.services.devices import DeviceService
from netwatch.services.event_query import EventQueryService
from netwatch.services.scanner import HostScanner, os_hint, parse_ports
from netwatch.services.summary import SummaryService
from tests.helpers import FakeVendors, memory_repos


class PortsTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_ports("22, 80,8000-8002"), [22, 80, 8000, 8001, 8002])
        self.assertIn(22, parse_ports(None))

    def test_rejects_invalid(self):
        for spec in ("abc", "0", "1-70000", "100-50", ",", "1-6000"):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                parse_ports(spec)

    def test_os_hint(self):
        self.assertIsNone(os_hint(None))
        self.assertIn("Linux", os_hint(63))
        self.assertEqual(os_hint(120), "Windows")


class ScannerTest(unittest.TestCase):
    def test_scan_with_fakes(self):
        _, repos = memory_repos()
        repos.devices.add("aa:00:00:00:00:01", "127.0.0.1", "box", False, 1)
        scanner = HostScanner(
            repos.devices, FakeVendors(),
            pinger=lambda ip, count: ([1.0, 3.0], 64),
            resolver=lambda ip, timeout: (False, None),
            read_arp=lambda: {"aa:00:00:00:00:01": "127.0.0.1"},
            reverse_dns=lambda ip: "localhost",
            port_probe=lambda ip, port: {"port": port, "service": "ssh", "banner": ""} if port == 22 else None)
        r = scanner.scan("127.0.0.1", "20-25")
        self.assertEqual([p["port"] for p in r["open"]], [22])
        self.assertEqual(r["ping"]["loss"], 50.0)
        self.assertEqual(r["known"]["hostname"], "box")
        self.assertEqual(r["vendor"], "ACME")

    def test_rejects_bad_host(self):
        _, repos = memory_repos()
        with self.assertRaises(ValueError):
            HostScanner(repos.devices, FakeVendors()).scan("a b; rm", "common")


class EventQueryTest(unittest.TestCase):
    def setUp(self):
        _, self.repos = memory_repos()
        day = int(time.mktime(time.strptime("2026-01-10", "%Y-%m-%d")))
        for i in range(30):
            self.repos.events.add(Event("wan_down" if i % 2 else "new_device", f"e{i}", ts=day + i * 3600))
        self.service = EventQueryService(self.repos.events)

    def test_paging_and_filters(self):
        page = self.service.page({"size": ["10"], "page": ["2"]})
        self.assertEqual((page["total"], page["pages"], page["page"], len(page["events"])), (30, 3, 2, 10))
        only_day = self.service.page({"from": ["2026-01-10"], "to": ["2026-01-10"]})
        self.assertEqual(only_day["total"], 24)
        kind = self.service.page({"kind": ["wan_down"]})
        self.assertEqual(kind["total"], 15)

    def test_validation(self):
        for params in ({"size": ["7"]}, {"page": ["x"]}, {"from": ["2026-13-01"]},
                       {"from": ["2026-01-11"], "to": ["2026-01-10"]}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.service.page(params)


class SummaryAndDevicesTest(unittest.TestCase):
    def test_summary_shape(self):
        _, repos = memory_repos()
        now = int(time.time())
        repos.devices.add("aa:00:00:00:00:01", "192.168.1.10", None, False, now)
        repos.probes.add(now - 10, "ping", "gateway", True, 2.0)
        repos.probes.add(now - 10, "dev", "aa:00:00:00:00:01", True, 4.0)
        status = {"lan": {"label": "Red local", "down_since": None}}
        d = SummaryService(repos, FakeVendors(), lambda: status, {"down": 0, "up": 0}).build()
        self.assertEqual(d["checks"], status)
        self.assertEqual(len(d["ribbon"]["lan"]), 144)
        self.assertEqual(d["uptime"]["lan"], 100.0)
        self.assertEqual(d["devices"][0]["q"]["avg"], 4.0)
        self.assertEqual(d["quality"]["gateway"]["avg"], 2.0)

    def test_device_edits_are_sanitized(self):
        _, repos = memory_repos()
        repos.devices.add("aa", "1.1.1.1", None, False, 1)
        service = DeviceService(repos.devices)
        service.set_alias("aa", "  " + "x" * 80)
        service.set_network("aa", "6 GHz")
        device = repos.devices.get("aa")
        self.assertEqual(len(device["alias"]), 60)
        self.assertIsNone(device["network"])


if __name__ == "__main__":
    unittest.main()
