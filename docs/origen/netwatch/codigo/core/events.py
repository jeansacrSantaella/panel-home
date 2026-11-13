"""Define los eventos y el bus que los guarda y distribuye."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Protocol


@dataclass(frozen=True)
class Event:
    kind: str
    detail: str
    ts: int = field(default_factory=lambda: int(time.time()))
    notify: bool = True  # False: se guarda pero no genera alertas (p. ej. el primer escaneo)


class EventStore(Protocol):
    def add(self, event: Event) -> None: ...


Subscriber = Callable[[Event], None]


def console_log(event: Event) -> None:
    print(time.strftime("%H:%M:%S", time.localtime(event.ts)), event.kind, event.detail, flush=True)


class EventBus:
    """Publica eventos sin acoplar los monitores a sus suscriptores."""

    def __init__(self, store: EventStore):
        self._store = store
        self._subscribers: List[Subscriber] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def publish(self, kind: str, detail: str, notify: bool = True) -> Event:
        event = Event(kind, detail, notify=notify)
        self._store.add(event)
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception as e:  # un suscriptor roto no debe frenar al monitor
                print("subscriber error:", e, flush=True)
        return event
