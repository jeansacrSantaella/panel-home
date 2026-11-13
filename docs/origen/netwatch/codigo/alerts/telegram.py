"""Alertas por Telegram con cola y reintentos cuando no hay conexión."""
from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.parse
from typing import Dict, FrozenSet

from netwatch.core.events import Event
from netwatch.network.http import Fetcher, fetch

API = "https://api.telegram.org/bot{token}/{method}"
PERMANENT_ERRORS = (400, 401, 403, 404)  # token o chat id incorrectos: reintentar no sirve
LATE_AFTER = 60


class TelegramClient:
    def __init__(self, token: str, chat_id: str, fetcher: Fetcher = fetch):
        self._token = token
        self._chat = chat_id
        self._fetch = fetcher

    def send(self, text: str) -> None:
        body = urllib.parse.urlencode({"chat_id": self._chat, "text": text}).encode()
        self._fetch(API.format(token=self._token, method="sendMessage"), data=body, timeout=15)

    def chat_ids(self) -> Dict[int, str]:
        """Lista los chats que escribieron al bot para obtener TELEGRAM_CHAT_ID."""
        res = json.loads(self._fetch(API.format(token=self._token, method="getUpdates"))).get("result", [])
        return {m["message"]["chat"]["id"]: m["message"]["chat"].get("first_name", "")
                for m in res if "message" in m}


def format_alert(event: Event, late: bool) -> str:
    if event.kind.endswith("_down"):
        icon = "🔴"
    elif event.kind.endswith("_up"):
        icon = "🟢"
    elif event.kind == "new_device":
        icon = "🆕"
    else:
        icon = "🌐"
    text = f"{icon} {event.detail}\n🕐 {time.strftime('%d %b %H:%M', time.localtime(event.ts))}"
    return text + ("\n(enviado con retraso: no había conexión)" if late else "")


class TelegramNotifier:
    """Encola alertas del EventBus y envíalas en orden con reintentos."""

    def __init__(self, client: TelegramClient, kinds: FrozenSet[str], retry_delay: float = 30, maxsize: int = 100):
        self._client = client
        self._kinds = kinds
        self._retry_delay = retry_delay
        self._queue: "queue.Queue[Event]" = queue.Queue(maxsize=maxsize)

    def __call__(self, event: Event) -> None:
        if not event.notify or event.kind not in self._kinds:
            return
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            pass

    def start(self) -> None:
        threading.Thread(target=self._run, name="telegram", daemon=True).start()

    def _run(self) -> None:
        while True:
            self._deliver(self._queue.get())

    def _deliver(self, event: Event) -> None:
        while True:
            try:
                self._client.send(format_alert(event, late=time.time() - event.ts > LATE_AFTER))
                return
            except urllib.error.HTTPError as e:
                if e.code in PERMANENT_ERRORS:
                    print("telegram rechazó el mensaje:", e.code, flush=True)
                    return
            except Exception as e:
                print("telegram error:", e, flush=True)
            time.sleep(self._retry_delay)
