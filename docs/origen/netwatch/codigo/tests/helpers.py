from netwatch.core.events import EventBus
from netwatch.storage.database import Database
from netwatch.storage.repositories import Repositories


def memory_repos():
    db = Database(":memory:")
    db.migrate()
    return db, Repositories.on(db)


class RecordingBus(EventBus):
    """EventBus en memoria que recuerda lo publicado."""

    def __init__(self, store=None):
        super().__init__(store or _NullStore())
        self.published = []
        self.subscribe(self.published.append)

    def kinds(self):
        return [e.kind for e in self.published]


class _NullStore:
    def add(self, event):
        pass


class FakeVendors:
    def lookup(self, mac):
        return "ACME" if mac else None
