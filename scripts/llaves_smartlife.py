"""Saca las llaves locales de los focos Tuya iniciando sesión con tu cuenta de Smart Life (sin proyecto de desarrollador).

Usa la misma vía que la integración oficial de Tuya en Home Assistant: un QR que apruebas desde la app.

    python3 scripts/llaves_smartlife.py

1. Lee tu "código de usuario" de data/smartlife.json ({"user_code": "..."}); en la app: Yo → ⚙️ → Cuenta y seguridad → Código de usuario.
2. Abre un QR en el navegador: escanéalo con Smart Life (Yo → ícono de escanear) y aprueba.
3. Escribe data/devices.json (nombre, id, llave, IP y versión locales) en el formato de tinytuya que usa el panel.

No guarda los tokens de sesión y nunca imprime las llaves. Requiere: pip install tuya-device-sharing-sdk qrcode
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

CLIENT_ID = "HA_3y9q4ak7g4ephrvke"   # cliente de la integración oficial de Tuya para Home Assistant
SCHEMA = "haauthorize"
DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> int:
    try:
        import qrcode
        import qrcode.image.svg
        from tuya_sharing import LoginControl, Manager
    except ImportError:
        print("Instala primero: python3 -m pip install tuya-device-sharing-sdk qrcode")
        return 1

    conf = DATA / "smartlife.json"
    user_code = json.loads(conf.read_text()).get("user_code", "").strip() if conf.exists() else ""
    if not user_code or "PEGA" in user_code:
        print(f"Escribe tu código de usuario de Smart Life en {conf}")
        return 1

    login = LoginControl()
    r = login.qr_code(CLIENT_ID, SCHEMA, user_code)
    if not r.get("success"):
        print("Tuya rechazó el código de usuario:", r.get("code"), r.get("msg"))
        return 1
    token = r["result"]["qrcode"]

    # QR en una página local que se abre sola en el navegador
    svg = qrcode.make(f"tuyaSmart--qrLogin?token={token}", image_factory=qrcode.image.svg.SvgPathImage, box_size=12)
    pagina = DATA / "qr-smartlife.html"
    pagina.write_text("<!doctype html><meta charset=utf-8><title>Escanea con Smart Life</title>"
                      "<body style='font:16px system-ui;text-align:center;padding:30px'>"
                      "<h2>Escanea con Smart Life</h2><p>Yo → ícono de escanear (arriba a la derecha) → aprueba</p>"
                      f"<div style='background:#fff;display:inline-block;padding:16px'>{svg.to_string(encoding='unicode')}</div>"
                      "<p>Esta página se puede cerrar cuando termine.</p></body>")
    subprocess.run(["open", str(pagina)], check=False)
    print("QR abierto en el navegador. Esperando a que lo apruebes en la app (3 min)…", flush=True)

    info = None
    for _ in range(90):
        time.sleep(2)
        ok, resp = login.login_result(token, CLIENT_ID, user_code)
        if ok:
            info = resp
            break
    pagina.unlink(missing_ok=True)
    if not info:
        print("No se aprobó el QR a tiempo. Vuelve a correr el script.")
        return 1

    token_info = {k: info[k] for k in ("t", "uid", "expire_time", "access_token", "refresh_token")}
    manager = Manager(CLIENT_ID, user_code, info["terminal_id"], info["endpoint"], token_info)
    manager.update_device_cache()

    # IP y versión locales: del escaneo de la red que hizo tinytuya (data/snapshot.json)
    locales = {}
    snap = DATA / "snapshot.json"
    if snap.exists():
        locales = {d.get("id"): d for d in json.loads(snap.read_text()).get("devices", [])}

    salida = []
    for d in manager.device_map.values():
        loc = locales.get(d.id, {})
        salida.append({"name": d.name, "id": d.id, "key": d.local_key, "category": d.category,
                       "product_name": d.product_name, "uuid": d.uuid, "mac": loc.get("mac", ""),
                       "ip": loc.get("ip", ""), "version": loc.get("ver", "")})
    (DATA / "devices.json").write_text(json.dumps(salida, indent=2, ensure_ascii=False))
    print(f"Listo: {len(salida)} dispositivos guardados en data/devices.json")
    for x in salida:
        print(f"  - {x['name']} · {x['category']} · {x['product_name']} · IP local {x['ip'] or '—'} · llave {'sí' if x['key'] else 'NO'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
