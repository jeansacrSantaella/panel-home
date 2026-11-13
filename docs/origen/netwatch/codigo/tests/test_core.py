import unittest

from netwatch.core.metrics import format_duration, quality, samples_from_times
from netwatch.network.discovery import parse_arp
from netwatch.network.dns import build_query, is_valid_answer
from netwatch.network.vendors import is_private_mac


class MetricsTest(unittest.TestCase):
    def test_quality(self):
        q = quality([(10.0, 1), (20.0, 1), (None, 0), (30.0, 1)])
        self.assertEqual(q, {"avg": 20.0, "jitter": 10.0, "loss": 25.0})

    def test_quality_empty(self):
        self.assertIsNone(quality([]))
        self.assertEqual(quality([(None, 0)]), {"avg": None, "jitter": None, "loss": 100.0})

    def test_samples_from_times(self):
        self.assertEqual(samples_from_times([5.0], 3), [(5.0, 1), (None, 0), (None, 0)])

    def test_format_duration(self):
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(190), "3m 10s")
        self.assertEqual(format_duration(7500), "2h 5m")


class NetworkParsingTest(unittest.TestCase):
    def test_parse_arp_normalizes_and_filters(self):
        out = ("? (192.168.1.5) at a:b:c:d:e:f on en0\n"
               "? (192.168.1.255) at ff:ff:ff:ff:ff:ff on en0\n"
               "? (192.168.1.9) at (incomplete) on en0\n"
               "192.168.1.7 dev eth0 lladdr 00:11:22:33:44:55 REACHABLE\n")
        self.assertEqual(parse_arp([out]), {"0a:0b:0c:0d:0e:0f": "192.168.1.5",
                                            "00:11:22:33:44:55": "192.168.1.7"})

    def test_private_mac(self):
        self.assertTrue(is_private_mac("da:00:00:00:00:00"))
        self.assertFalse(is_private_mac("00:11:22:33:44:55"))

    def test_dns_answer_validation(self):
        packet = build_query(1234, "example.com")
        self.assertTrue(packet.endswith(b"\x07example\x03com\x00\x00\x01\x00\x01"))
        answer = (1234).to_bytes(2, "big") + b"\x81\x80" + b"\x00\x01" + b"\x00\x01"
        self.assertTrue(is_valid_answer(answer, 1234))
        self.assertFalse(is_valid_answer(answer, 999))
        self.assertFalse(is_valid_answer(b"\x00", 1234))


if __name__ == "__main__":
    unittest.main()
