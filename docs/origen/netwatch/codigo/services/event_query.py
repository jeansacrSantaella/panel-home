"""Filtra y pagina el historial completo de eventos (/api/events)."""
from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Dict, List, Optional

from netwatch.storage.repositories import EventFilter, EventRepository

PAGE_SIZES = (10, 25, 50)


def _param(params: Dict[str, List[str]], name: str, default: str = "") -> str:
    return params.get(name, [default])[0]


def _day_start(value: str, offset_days: int = 0) -> Optional[int]:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("fecha inválida") from exc
    if parsed.isoformat() != value:
        raise ValueError("fecha inválida")
    try:
        return int(time.mktime((parsed + timedelta(days=offset_days)).timetuple()))
    except (OverflowError, OSError) as exc:
        raise ValueError("fecha fuera de rango") from exc


def parse_filter(params: Dict[str, List[str]]) -> EventFilter:
    start = _day_start(_param(params, "from"))
    end = _day_start(_param(params, "to"), offset_days=1)  # "hasta" incluye el día completo
    if start is not None and end is not None and end <= start:
        raise ValueError("el rango de fechas no es válido")
    return EventFilter(start, end, _param(params, "kind"))


class EventQueryService:
    def __init__(self, events: EventRepository):
        self._events = events

    def page(self, params: Dict[str, List[str]]) -> dict:
        try:
            page = int(_param(params, "page", "0"))
            size = int(_param(params, "size", "10"))
        except ValueError as exc:
            raise ValueError("page y size deben ser números enteros") from exc
        if page < 0 or size not in PAGE_SIZES:
            raise ValueError("page o size fuera de rango")
        flt = parse_filter(params)
        total = self._events.count(flt)
        pages = (total + size - 1) // size
        page = min(page, max(0, pages - 1))
        return {"events": self._events.page(flt, size, page * size), "kinds": self._events.kinds(),
                "total": total, "page": page, "pages": pages}
