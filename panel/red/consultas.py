"""Consultas y ediciones de la red: eventos paginados, CSV, alias y tipo de conexión."""
from __future__ import annotations

import csv
import io
import time
from datetime import date, timedelta

TAMANOS = (10, 25, 50)
REDES = ("5 GHz", "2.4 GHz", "Cable")
MAX_ALIAS = 60
MAX_EVENTOS = 5000


def _param(consulta: dict, nombre: str, defecto: str = "") -> str:
    v = consulta.get(nombre, defecto)
    if isinstance(v, (list, tuple)):  # admite {k: [v]} y {k: v}
        v = v[0] if v else defecto
    return defecto if v is None else str(v)


def _inicio_dia(valor: str, desplazar_dias: int = 0):
    if not valor:
        return None
    try:
        f = date.fromisoformat(valor)
    except ValueError as e:
        raise ValueError("fecha inválida") from e
    if f.isoformat() != valor:
        raise ValueError("fecha inválida")
    try:
        return int(time.mktime((f + timedelta(days=desplazar_dias)).timetuple()))
    except (OverflowError, OSError) as e:
        raise ValueError("fecha fuera de rango") from e


def pagina_eventos(red, consulta: dict) -> dict:
    try:
        pagina = int(_param(consulta, "page", "0"))
        tam = int(_param(consulta, "size", "10"))
    except ValueError as e:
        raise ValueError("page y size deben ser números enteros") from e
    if pagina < 0 or tam not in TAMANOS:
        raise ValueError("page o size fuera de rango")
    inicio = _inicio_dia(_param(consulta, "from"))
    fin = _inicio_dia(_param(consulta, "to"), 1)  # "hasta" incluye el día completo
    if inicio is not None and fin is not None and fin <= inicio:
        raise ValueError("el rango de fechas no es válido")
    kind = _param(consulta, "kind")
    total = red.contar_eventos(inicio, fin, kind)
    paginas = (total + tam - 1) // tam
    pagina = min(pagina, max(0, paginas - 1))
    return {"events": red.pagina_eventos(inicio, fin, kind, tam, pagina * tam), "kinds": red.tipos_evento(),
            "total": total, "page": pagina, "pages": paginas}


def _ts(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else ""


def _num(v):
    return "" if v is None else v


def exportar_csv(resumen: dict, red) -> str:
    """Resumen completo en un CSV, en bloques separados por una línea vacía (con BOM para Excel)."""
    d = resumen
    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(["# Resumen"])
    w.writerow(["generado", _ts(d["now"])])
    w.writerow(["ip_publica", d["public_ip"] or ""])
    w.writerow(["velocidad_contratada_bajada_mbps", d["contracted"]["down"] or ""])
    w.writerow(["velocidad_contratada_subida_mbps", d["contracted"]["up"] or ""])
    w.writerow([])

    w.writerow(["# Estado y disponibilidad 24 h"])
    w.writerow(["servicio", "estado", "caido_desde", "disponibilidad_24h_pct"])
    for k, c in d["checks"].items():
        w.writerow([c["label"], "caido" if c["down_since"] else "ok", _ts(c["down_since"]), _num(d["uptime"][k])])
    w.writerow([])

    w.writerow(["# Calidad ultima hora"])
    w.writerow(["destino", "latencia_media_ms", "jitter_ms", "perdida_pct"])
    for t, v in d["quality"].items():
        w.writerow([t, _num(v["avg"]), _num(v["jitter"]), v["loss"]])
    w.writerow([])

    w.writerow(["# Equipos"])
    w.writerow(["alias", "nombre_host", "fabricante", "ip", "mac", "mac_aleatoria", "estado", "primera_vez",
                "ultima_vez", "red", "latencia_ms", "jitter_ms", "perdida_pct", "caidas_24h"])
    for x in d["devices"]:
        v = x["q"] or {}
        w.writerow([x["alias"] or "", x["hostname"] or "", x["vendor"] or "", x["ip"], x["mac"],
                    "si" if x["random_mac"] else "no", "conectado" if x["online"] else "desconectado",
                    _ts(x["first_seen"]), _ts(x["last_seen"]), x["network"] or "", _num(v.get("avg")),
                    _num(v.get("jitter")), _num(v.get("loss")), x["drops"]])
    w.writerow([])

    w.writerow(["# Pruebas de velocidad"])
    w.writerow(["fecha", "bajada_mbps", "subida_mbps"])
    for r in red.velocidad_reciente():
        w.writerow([_ts(r["ts"]), round(r["down"], 2), round(r["up"], 2)])
    w.writerow([])

    w.writerow(["# Caidas por hora del dia"])
    w.writerow(["hora", "caidas"])
    for h, c in enumerate(d["hours"]):
        w.writerow([f"{h:02d}:00", c])
    w.writerow([])

    w.writerow([f"# Eventos (hasta {MAX_EVENTOS}, mas recientes primero)"])
    w.writerow(["fecha", "tipo", "detalle"])
    for r in red.eventos_recientes(MAX_EVENTOS):
        w.writerow([_ts(r["ts"]), r["kind"], r["detail"]])
    w.writerow([])
    return "﻿" + buf.getvalue()


def fijar_alias(red, datos: dict) -> None:
    mac = datos["mac"]  # KeyError si falta
    if not isinstance(mac, str) or not mac:
        raise ValueError("mac inválida")
    red.fijar_alias(mac, (datos.get("alias") or "").strip()[:MAX_ALIAS] or None)


def fijar_red(red, datos: dict) -> None:
    mac = datos["mac"]
    if not isinstance(mac, str) or not mac:
        raise ValueError("mac inválida")
    red_dato = datos.get("network")
    red.fijar_red(mac, red_dato if red_dato in REDES else None)
