#!/usr/bin/env python3
"""Prueba del navegador: abre cada pestaña del panel en Chrome headless y falla si hay errores de JavaScript.

Levanta main.py con una base temporal y servicios inalcanzables a propósito (nada sale a la red de la casa ni a
internet), carga datos falsos, entra como admin y sirve un proxy local que añade la cookie e inyecta en el HTML un
recolector de errores (window.onerror, unhandledrejection, console.error). Solo biblioteca estándar.

Uso: python3 scripts/prueba_navegador.py [--pestanas inicio,red] [--espera-ms 6000]
Salida: tabla por pestaña; código 1 si alguna tiene errores.

Filtro (ESPERADOS): se ignoran solo los errores de red causados por los servicios inalcanzables a propósito
(go2rtc, cámara, sonda, NetWatch): "Failed to fetch", "NetworkError", "ERR_CONNECTION_REFUSED", "Failed to load
resource" (recursos 4xx/5xx) y los "Load failed". Cualquier otro (TypeError, ReferenceError, SyntaxError...) falla.
"""
import argparse
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import date
from html import unescape
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PESTANAS = ("inicio", "resumen", "luces", "capturas", "camaras", "red")
ESPERADOS = re.compile(
    r"Failed to fetch|NetworkError|ERR_CONNECTION_REFUSED|ERR_CONNECTION_RESET|ERR_EMPTY_RESPONSE|ERR_INVALID_HTTP_RESPONSE"
    r"|Failed to load resource|Load failed|ERR_ABORTED|ERR_TIMED_OUT|AbortError|The operation was aborted",
    re.I)
JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001400010000000000000000000000000000000affc40014100100000000000000000000000000000000ffda0008010100003f00d2cf20ffd9")

CHROMES = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "google-chrome-stable",
           "chromium", "chromium-browser")


def buscar_chrome():
    for c in CHROMES:
        ruta = c if os.path.isabs(c) else shutil.which(c)
        if ruta and os.path.exists(ruta):
            return ruta
    return None


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pedir(url, datos=None, cabeceras=None, timeout=15):
    cab = dict(cabeceras or {})
    cuerpo = None
    if datos is not None:
        cuerpo = json.dumps(datos).encode()
        cab["Content-Type"] = "application/json"
    return urllib.request.urlopen(urllib.request.Request(url, data=cuerpo, headers=cab), timeout=timeout)


def preparar_datos(tmp):
    hoy = date.today().isoformat()
    cam = tmp / "camaras"
    (cam / "fotos" / hoy).mkdir(parents=True)
    (cam / "clips" / hoy).mkdir(parents=True)
    for i in (1, 2):
        (cam / "fotos" / hoy / f"prueba{i}.jpg").write_bytes(JPEG)
    (cam / "clips" / hoy / "prueba1.mp4").write_bytes(b"clip-falso")
    (tmp / "oui.txt").write_text("000000 Xerox\n")
    return cam


def entorno(tmp, puerto, cam):
    # Entorno limpio: el .env del repo no pisa lo que ya está definido, así que se definen todas (aunque vacías).
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT")}
    env.update(
        PANEL_HOST="127.0.0.1", PANEL_PORT=str(puerto), PANEL_DB=str(tmp / "panel.db"),
        RED_INTERNA="1", RED_TOKEN="prueba", CAMARAS_INTERNAS="1",
        GO2RTC_INTERNO_URL="http://127.0.0.1:9", NETWATCH_URL="http://127.0.0.1:9", CAMARAS_URL="http://127.0.0.1:9",
        CAMARAS_DATA=str(cam), TELEGRAM_TOKEN="", TELEGRAM_CHAT_ID="", NTFY_URL="", DOCKER_SOCK="", CLIMA_CIUDAD="",
        LUCES_ARCHIVO=str(tmp / "nada.json"), OUI_ARCHIVO=str(tmp / "oui.txt"), PANEL_AVISAR="",
        PYTHONUNBUFFERED="1")
    return env


def cargar_datos(base):
    ahora = int(time.time())
    macs = {"aa:bb:cc:00:00:01": ("192.168.1.10", "laptop"), "aa:bb:cc:00:00:02": ("192.168.1.11", None),
            "aa:bb:cc:00:00:03": ("192.168.1.12", "tele")}
    lecturas = [
        {"t": "sondeo", "ts": ahora - 5, "gateway": "192.168.1.1",
         "resultados": [{"kind": "ping", "target": "gateway", "ok": True, "ms": 2.5},
                        {"kind": "ping", "target": "1.1.1.1", "ok": True, "ms": 14.0},
                        {"kind": "dns", "target": "8.8.8.8", "ok": True, "ms": 20.0}]},
        {"t": "escaneo", "ts": ahora - 4, "base": "192.168.1", "propia": "192.168.1.10",
         "equipos": {m: {"ip": ip, "hostname": h} for m, (ip, h) in macs.items()}},
        {"t": "calidad", "ts": ahora - 3, "resultados": [{"mac": m, "ip": ip, "ok": True, "ms": 3.0} for m, (ip, _) in macs.items()]},
        {"t": "ip_publica", "ts": ahora - 2, "ip": "203.0.113.7"},
        {"t": "velocidad", "ts": ahora - 1, "down": 320.5, "up": 90.2},
    ]
    pedir(base + "/api/interno/red", {"sonda": "prueba", "version": 1, "enviado": ahora, "lecturas": lecturas},
          {"Authorization": "Bearer prueba"})


INYECCION = """<script>(function(){var e=[];window.__erroresPrueba=e;
function t(x){try{return typeof x==='string'?x:(x&&x.stack)||JSON.stringify(x)||String(x)}catch(_){return String(x)}}
window.addEventListener('error',function(ev){e.push((ev.message||'error')+(ev.filename?' @ '+ev.filename+':'+ev.lineno:''))});
window.addEventListener('unhandledrejection',function(ev){e.push('unhandledrejection: '+t(ev.reason))});
var ce=console.error;console.error=function(){try{e.push('console.error: '+Array.prototype.map.call(arguments,t).join(' '))}catch(_){}return ce.apply(console,arguments)};
setTimeout(function(){var p=document.createElement('pre');p.id='errores-prueba';p.textContent=JSON.stringify(e);document.body.appendChild(p)},%d);
})();</script>"""


def hacer_proxy(puerto_panel, cookie, espera_ms):
    inyeccion = (INYECCION % espera_ms).encode()

    class Proxy(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            req = urllib.request.Request(f"http://127.0.0.1:{puerto_panel}{self.path}", headers={"Cookie": cookie})
            try:
                with urllib.request.urlopen(req, timeout=20) as res:
                    cuerpo, cod, tipo = res.read(), res.status, res.headers.get("Content-Type", "")
            except urllib.error.HTTPError as e:
                cuerpo, cod, tipo = e.read(), e.code, e.headers.get("Content-Type", "")
            except Exception:
                cuerpo, cod, tipo = b"", 502, "text/plain"
            if self.path.split("?")[0] in ("/", "/index.html") and cod == 200:
                cuerpo = cuerpo.replace(b"<head>", b"<head>" + inyeccion, 1)
            self.send_response(cod)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def probar_pestana(chrome, url_proxy, pestana, perfil, espera_ms):
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run", "--disable-extensions",
           f"--user-data-dir={perfil}", "--dump-dom", f"--virtual-time-budget={espera_ms + 2000}",
           f"{url_proxy}/#{pestana}"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60, text=True, errors="replace")
    except subprocess.TimeoutExpired:
        return None, ["Chrome no terminó en 60 s"]
    m = re.search(r'<pre id="errores-prueba">(.*?)</pre>', r.stdout, re.S)
    if not m:
        return None, ["no se encontró #errores-prueba en el DOM (¿la página no cargó?) " + r.stderr[-200:]]
    try:
        return json.loads(unescape(m.group(1))), []
    except ValueError:
        return None, ["JSON de errores ilegible: " + m.group(1)[:200]]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pestanas", default=",".join(PESTANAS))
    ap.add_argument("--espera-ms", type=int, default=6000)
    args = ap.parse_args()
    pestanas = [p.strip() for p in args.pestanas.split(",") if p.strip()]
    chrome = buscar_chrome()
    if not chrome:
        print("No se encontró Chrome/Chromium", file=sys.stderr)
        return 2
    tmp = Path(tempfile.mkdtemp(prefix="prueba-navegador-"))
    panel = None
    srv = None
    try:
        cam = preparar_datos(tmp)
        puerto = puerto_libre()
        base = f"http://127.0.0.1:{puerto}"
        log = open(tmp / "panel.log", "w")
        panel = subprocess.Popen([sys.executable, "main.py"], cwd=RAIZ, env=entorno(tmp, puerto, cam), stdout=log,
                                 stderr=subprocess.STDOUT)
        for _ in range(60):
            if panel.poll() is not None:
                print("main.py terminó:\n" + (tmp / "panel.log").read_text()[-1500:], file=sys.stderr)
                return 2
            try:
                pedir(base + "/api/login", {"usuario": "x", "contrasena": "x"}, timeout=2)
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("El panel no arrancó a tiempo", file=sys.stderr)
            return 2
        cargar_datos(base)
        r = pedir(base + "/api/login", {"usuario": "admin", "contrasena": "1234"})
        cookie = r.headers["Set-Cookie"].split(";")[0]
        try:
            pedir(base + "/api/camaras", {"ips": "192.0.2.10", "nombre": "Prueba"}, {"Cookie": cookie})
        except Exception as e:
            print("aviso: no se pudo agregar la cámara:", e, file=sys.stderr)
        srv = hacer_proxy(puerto, cookie, args.espera_ms)
        url_proxy = f"http://127.0.0.1:{srv.server_address[1]}"
        fallo = False
        print(f"{'pestaña':<10} resultado")
        for p in pestanas:
            errores, problemas = probar_pestana(chrome, url_proxy, p, tmp / f"perfil-{p}", args.espera_ms)
            reales = problemas + [e for e in (errores or []) if not ESPERADOS.search(e)]
            ign = len(errores or []) - len([e for e in (errores or []) if not ESPERADOS.search(e)])
            if reales:
                fallo = True
                print(f"{p:<10} ERRORES ({len(reales)})")
                for e in reales:
                    print("    - " + e.replace("\n", " ")[:400])
            else:
                print(f"{p:<10} OK" + (f" ({ign} errores de red esperados ignorados)" if ign else ""))
        return 1 if fallo else 0
    finally:
        if srv:
            srv.shutdown()
        if panel and panel.poll() is None:
            panel.terminate()
            try:
                panel.wait(5)
            except subprocess.TimeoutExpired:
                panel.kill()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
