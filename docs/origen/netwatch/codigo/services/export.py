"""Resumen completo en un solo CSV, en bloques separados por una línea vacía."""
from __future__ import annotations

import csv
import io
import time

from netwatch.services.summary import SummaryService
from netwatch.storage.repositories import Repositories

MAX_EVENTS = 5000


def _ts(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else ""


def _num(v):
    return "" if v is None else v


class CsvExporter:
    def __init__(self, summary: SummaryService, repos: Repositories):
        self._summary = summary
        self._repos = repos

    def export(self) -> bytes:
        d = self._summary.build()
        buf = io.StringIO()
        w = csv.writer(buf)
        for block in (self._overview, self._status, self._quality, self._devices, self._speed, self._hours,
                      self._events):
            block(w, d)
            w.writerow([])
        return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM para que Excel respete los acentos

    @staticmethod
    def _overview(w, d):
        w.writerow(["# Resumen"])
        w.writerow(["generado", _ts(d["now"])])
        w.writerow(["ip_publica", d["public_ip"] or ""])
        w.writerow(["velocidad_contratada_bajada_mbps", d["contracted"]["down"] or ""])
        w.writerow(["velocidad_contratada_subida_mbps", d["contracted"]["up"] or ""])

    @staticmethod
    def _status(w, d):
        w.writerow(["# Estado y disponibilidad 24 h"])
        w.writerow(["servicio", "estado", "caido_desde", "disponibilidad_24h_pct"])
        for k, c in d["checks"].items():
            w.writerow([c["label"], "caido" if c["down_since"] else "ok", _ts(c["down_since"]), _num(d["uptime"][k])])

    @staticmethod
    def _quality(w, d):
        w.writerow(["# Calidad ultima hora"])
        w.writerow(["destino", "latencia_media_ms", "jitter_ms", "perdida_pct"])
        for t, v in d["quality"].items():
            w.writerow([t, _num(v["avg"]), _num(v["jitter"]), v["loss"]])

    @staticmethod
    def _devices(w, d):
        w.writerow(["# Equipos"])
        w.writerow(["alias", "nombre_host", "fabricante", "ip", "mac", "mac_aleatoria", "estado", "primera_vez",
                    "ultima_vez", "red", "latencia_ms", "jitter_ms", "perdida_pct", "caidas_24h"])
        for x in d["devices"]:
            v = x["q"] or {}
            w.writerow([x["alias"] or "", x["hostname"] or "", x["vendor"] or "", x["ip"], x["mac"],
                        "si" if x["random_mac"] else "no", "conectado" if x["online"] else "desconectado",
                        _ts(x["first_seen"]), _ts(x["last_seen"]), x["network"] or "", _num(v.get("avg")),
                        _num(v.get("jitter")), _num(v.get("loss")), x["drops"]])

    def _speed(self, w, d):
        w.writerow(["# Pruebas de velocidad"])
        w.writerow(["fecha", "bajada_mbps", "subida_mbps"])
        for r in self._repos.speed.recent():
            w.writerow([_ts(r["ts"]), round(r["down"], 2), round(r["up"], 2)])

    @staticmethod
    def _hours(w, d):
        w.writerow(["# Caidas por hora del dia"])
        w.writerow(["hora", "caidas"])
        for h, c in enumerate(d["hours"]):
            w.writerow([f"{h:02d}:00", c])

    def _events(self, w, d):
        w.writerow([f"# Eventos (hasta {MAX_EVENTS}, mas recientes primero)"])
        w.writerow(["fecha", "tipo", "detalle"])
        for r in self._repos.events.recent(MAX_EVENTS):
            w.writerow([_ts(r["ts"]), r["kind"], r["detail"]])
