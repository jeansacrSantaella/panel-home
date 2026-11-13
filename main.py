"""Arranca el panel del hogar: recolector + avisos en segundo plano y el servidor web."""
from __future__ import annotations

import argparse
import dataclasses
import logging
import threading
import time

from panel.auth import Auth
from panel.avisos import Avisador
from panel.config import cargar, leer_env
from panel.db import Db
from panel.eventos import Recolector
from panel.luces import Luces
from panel.rutinas import Rutinas
from panel.tareas import Planificador
from panel.web import crear_servidor

log = logging.getLogger("panel")


def bucle(recolector: Recolector, avisador: Avisador, cada: int, parar: threading.Event) -> None:
    """Cada `cada` segundos recolecta eventos y envía los avisos pendientes."""
    while not parar.is_set():
        try:
            nuevos = recolector.ciclo()
            if nuevos:
                log.info("%d eventos nuevos", nuevos)
            avisador.enviar_pendientes()
        except Exception:
            log.exception("falló el ciclo")
        parar.wait(cada)


def main() -> None:
    ap = argparse.ArgumentParser(description="Panel unificado del hogar")
    ap.add_argument("--host", help="interfaz (0.0.0.0 para verlo desde otros equipos)")
    ap.add_argument("--port", type=int)
    ap.add_argument("--restablecer-admin", action="store_true",
                    help="regresa la cuenta admin a la contraseña 1234 (pedirá cambiarla) y sale")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    leer_env()  # .env de la raíz del proyecto; las variables ya exportadas tienen prioridad
    cfg = cargar()
    cambios = {k: v for k, v in (("host", args.host), ("port", args.port)) if v}
    cfg = dataclasses.replace(cfg, **cambios)

    db = Db(cfg.db_path)

    def al_bloquear(ip: str, segundos: int) -> None:
        # queda en la línea de tiempo (grupo Sistema); no se avisa por Telegram salvo que se pida en PANEL_AVISAR
        ahora = int(time.time())
        db.agregar_evento({"ts": ahora, "fuente": "panel", "tipo": "acceso_bloqueado", "nivel": "medio",
                           "titulo": "Intentos fallidos de entrar al panel",
                           "detalle": f"Desde {ip}: bloqueado {segundos} s", "clave": f"acceso:{ip}:{ahora}"})

    auth = Auth(db, al_bloquear)
    if args.restablecer_admin:
        auth.restablecer_admin()
        print("Cuenta admin restablecida: entra con admin / 1234 y cámbiala.")
        return
    if auth.asegurar_admin():
        log.warning("Cuenta creada: admin / 1234. Entra al panel y cámbiala.")
    red = None
    planificador = Planificador()
    if cfg.red_interna:
        from panel.red.servicio import Red
        red = Red(db, cfg.oui_archivo)
        for t in red.tareas():
            planificador.agregar(t)
        if not cfg.red_token:
            log.warning("RED_INTERNA=1 sin RED_TOKEN: la sonda no podrá mandar lecturas (docs/RED.md)")
        log.info("Red interna: esperando lecturas de la sonda en POST /api/interno/red")
    planificador.iniciar()
    recolector = Recolector(cfg, db, red)
    avisador = Avisador(cfg, db)
    if not avisador.activo:
        log.info("Sin TELEGRAM_TOKEN/TELEGRAM_CHAT_ID ni NTFY_URL: los avisos solo se verán en la web")

    parar = threading.Event()
    hilo = threading.Thread(target=bucle, args=(recolector, avisador, cfg.recolectar_cada, parar), daemon=True)
    hilo.start()

    def ips_por_mac() -> dict:
        nw = recolector.ultimo.get("netwatch") or {}
        return {(d.get("mac") or "").lower(): d.get("ip") for d in nw.get("devices", []) if d.get("mac")}

    def al_cambiar_luz(luz: dict, encendida: bool) -> None:
        ahora = int(time.time())
        db.agregar_evento({"ts": ahora, "fuente": "luces", "tipo": "luz_encendida" if encendida else "luz_apagada",
                           "nivel": "info" if encendida else "bajo",
                           "titulo": f"{luz['nombre']}: {'encendida' if encendida else 'apagada'}",
                           "detalle": f"IP {luz.get('ip') or '—'}",
                           "clave": f"luz:{luz['id']}:{ahora}:{int(encendida)}", "avisado": 1})

    luces = Luces(cfg.luces_archivo, ips_por_mac=ips_por_mac, al_cambiar=al_cambiar_luz)
    if luces.configurado:
        luces.iniciar()
        log.info("Luces: %d focos Tuya", len(luces.lista()))
    else:
        log.info("Luces: %s", luces.motivo)

    def al_ejecutar_rutina(rutina: dict, r: dict, origen: str) -> None:
        ahora = int(time.time())
        detalle = f"{r['ok']} de {r['total']} focos" + (f" · no respondió: {', '.join(r['fallaron'])}" if r["fallaron"] else "")
        db.agregar_evento({"ts": ahora, "fuente": "luces", "tipo": "rutina_ejecutada",
                           "nivel": "info" if r["ok"] == r["total"] else "medio",
                           "titulo": f"Rutina «{rutina['nombre']}»" + (" (programada)" if origen == "programada" else ""),
                           "detalle": detalle, "clave": f"rutina:{rutina['id']}:{ahora}:{origen}", "avisado": 1})

    rutinas = Rutinas(db, luces, al_ejecutar=al_ejecutar_rutina)
    if luces.configurado:
        rutinas.iniciar()

    servidor = crear_servidor(cfg, db, recolector, auth, luces, rutinas, red)
    log.info("Red: %s · Cámaras: %s · go2rtc: %s", "sonda (interna)" if red else cfg.netwatch_url, cfg.camaras_url, cfg.go2rtc_url or "(host de la página):1984")
    log.info("Panel en http://%s:%d", cfg.host, cfg.port)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
        planificador.detener()
        servidor.server_close()


if __name__ == "__main__":
    main()
