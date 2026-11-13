"""Cálculos puros sobre mediciones."""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

Sample = Tuple[Optional[float], int]  # (ms, ok)


def quality(rows: Sequence[Sample]) -> Optional[dict]:
    """rows: [(ms, ok)] en orden -> latencia media, jitter y % de pérdida."""
    if not rows:
        return None
    ms = [r[0] for r in rows if r[1] and r[0] is not None]
    diffs = [abs(a - b) for a, b in zip(ms, ms[1:])]
    return {"avg": round(sum(ms) / len(ms), 1) if ms else None,
            "jitter": round(sum(diffs) / len(diffs), 1) if diffs else None,
            "loss": round(100 * (1 - sum(r[1] for r in rows) / len(rows)), 1)}


def samples_from_times(times: Iterable[float], sent: int) -> list:
    """Convierte los tiempos de respuesta de `sent` pings en muestras para quality()."""
    rows = [(t, 1) for t in times]
    return rows + [(None, 0)] * max(0, sent - len(rows))


def format_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    return f"{s // 3600}h {s % 3600 // 60}m"
