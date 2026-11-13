import tempfile
import unittest
from pathlib import Path

from netwatch.alerts.telegram import TelegramNotifier, format_alert
from netwatch.core.events import Event
from netwatch.web.http import Request, Response
from netwatch.web.router import Router
from netwatch.web.static import StaticFiles


class RouterTest(unittest.TestCase):
    def test_dispatch_and_fallback(self):
        router = Router()
        router.add("GET", "/a", lambda r: Response.text("a"))
        self.assertEqual(router.dispatch(Request("GET", "/a")).body, b"a")
        self.assertEqual(router.dispatch(Request("POST", "/a")).status, 404)
        router.fallback("GET", lambda r: Response.text("static"))
        self.assertEqual(router.dispatch(Request("GET", "/zzz")).body, b"static")


class StaticFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name) / "static"
        (root / "js").mkdir(parents=True)
        (root / "js" / "app.js").write_text("ok")
        (Path(self.tmp.name) / "secret.txt").write_text("no")
        self.static = StaticFiles(root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_serves_known_types(self):
        r = self.static(Request("GET", "/static/js/app.js"))
        self.assertEqual((r.status, r.body), (200, b"ok"))
        self.assertTrue(r.content_type.startswith("text/javascript"))

    def test_blocks_traversal(self):
        for path in ("/static/../secret.txt", "/static/js/../../secret.txt", "/secret.txt"):
            with self.subTest(path=path):
                self.assertEqual(self.static(Request("GET", path)).status, 404)


class TelegramNotifierTest(unittest.TestCase):
    def test_filters_events(self):
        notifier = TelegramNotifier(client=None, kinds=frozenset({"wan_down"}))
        notifier(Event("wan_down", "x"))
        notifier(Event("wan_down", "x", notify=False))
        notifier(Event("device_online", "x"))
        self.assertEqual(notifier._queue.qsize(), 1)

    def test_format(self):
        text = format_alert(Event("wan_down", "Internet sin respuesta", ts=0), late=True)
        self.assertTrue(text.startswith("🔴 Internet sin respuesta"))
        self.assertIn("con retraso", text)


if __name__ == "__main__":
    unittest.main()
