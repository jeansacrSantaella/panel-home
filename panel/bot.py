"""Bot de Telegram del hogar: responde comandos solo al chat configurado (long polling)."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from panel import resumen_detecciones as rd
from panel.telegram import TelegramError

log = logging.getLogger("panel.bot")

AYUDA = ("Comandos:\n"
         "/estado — internet, red, cámaras, luces y servidor\n"
         "/foto [cámara] — foto actual (todas o una, por id o nombre)\n"
         "/eventos — últimos 15 eventos\n"
         "/hoy — detecciones de hoy (hasta 10 fotos)\n"
         "/luces — luces por habitación\n"
         "/apagar — apagar todas las luces\n"
         "/rutina <nombre> — ejecutar una rutina\n"
         "/ayuda — esta lista")


def _sin_acentos(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").casefold()


class Bot:
    def __init__(self, cfg, db, cliente, red=None, camaras=None, luces=None, habitaciones=None, rutinas=None,
                 sistema: Optional[Callable[[], dict]] = None):
        self.cfg, self.db, self.cliente = cfg, db, cliente
        self.red, self.camaras, self.luces = red, camaras, luces
        self.habitaciones, self.rutinas = habitaciones, rutinas
        self._sistema = sistema
        self._parar = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self._offset = 0

    # --- comandos (devuelven texto; las fotos se mandan por el cliente) ---
    def atender(self, texto: str) -> str:
        partes = (texto or "").strip().split(None, 1)
        if not partes or not partes[0].startswith("/"):
            return ""
        cmd = partes[0].split("@")[0].lower()
        arg = partes[1].strip() if len(partes) > 1 else ""
        manejadores = {"/estado": self._estado, "/foto": self._foto, "/eventos": self._eventos, "/hoy": self._hoy,
                       "/luces": self._luces, "/apagar": self._apagar, "/rutina": self._rutina,
                       "/ayuda": self._ayuda, "/start": self._ayuda}
        fn = manejadores.get(cmd)
        if fn is None:
            return "No conozco ese comando. Usa /ayuda."
        try:
            return fn(arg)
        except TelegramError:
            raise
        except Exception:
            log.exception("falló el comando %s", cmd)
            return "Algo falló al ejecutar ese comando."

    def _ayuda(self, _arg: str) -> str:
        return AYUDA

    def _estado(self, _arg: str) -> str:
        lineas = []
        res = self.red.resumen_vivo() if self.red is not None else None
        if res is None:
            lineas.append("🌐 Red: sin datos de la sonda")
        else:
            for clave, nombre in (("wan", "Internet"), ("lan", "Red local"), ("dns", "DNS de la red interna")):
                s = (res.get("checks") or {}).get(clave)
                if s is not None:
                    lineas.append(f"{'🔴' if s.get('down_since') else '🟢'} {nombre}: {'caído' if s.get('down_since') else 'bien'}")
        if self.camaras is not None:
            salud = self.camaras.salud()
            lineas.append(f"{'🟢' if salud.get('go2rtc') else '🔴'} go2rtc: {'activo' if salud.get('go2rtc') else 'sin respuesta'}")
            for s in (salud.get("camaras") or {}).values():
                lineas.append(f"{'🟢' if s.get('estado') == 'ok' else '🔴'} {s.get('nombre')}: {s.get('estado')}")
        if self.luces is not None and self.luces.configurado:
            lu = self.luces.lista()
            enc = [l["nombre"] for l in lu if l.get("encendida")]
            lineas.append(f"💡 Luces encendidas: {len(enc)} de {len(lu)}" + (f" ({', '.join(enc)})" if enc else ""))
        lineas.append(self._servidor())
        return "\n".join(lineas)

    def _servidor(self) -> str:
        try:
            if self._sistema is not None:
                s = self._sistema()
            else:
                from panel import sistema
                s = sistema.leer_sistema(self.cfg.docker_sock)
        except Exception:
            return "🖥 Servidor: sin datos"
        partes = []
        if s.get("cpu") is not None:
            partes.append(f"CPU {s['cpu']:.0f}%")
        ram = s.get("ram")
        if ram and ram.get("total"):
            partes.append(f"RAM {100 * ram['usado'] / ram['total']:.0f}%")
        if s.get("temperatura") is not None:
            partes.append(f"{s['temperatura']:.0f} °C")
        return "🖥 Servidor: " + (" · ".join(partes) if partes else "sin datos")

    def _foto(self, arg: str) -> str:
        if self.camaras is None:
            return "Las cámaras no están activas."
        lista = self.camaras.lista()
        if arg:
            q = _sin_acentos(arg)
            lista = [c for c in lista if q in (_sin_acentos(c["id"]), _sin_acentos(c.get("nombre") or ""))] or \
                    [c for c in lista if q in _sin_acentos(c.get("nombre") or "")]
            if not lista:
                return f"No encuentro la cámara «{arg}»."
        if not lista:
            return "No hay cámaras registradas."
        fallaron = []
        for c in lista:
            foto = self.camaras.go2rtc.foto(c["id"])
            if foto:
                self.cliente.enviar_foto(foto, c.get("nombre") or c["id"])
            else:
                fallaron.append(c.get("nombre") or c["id"])
        return f"Sin imagen de: {', '.join(fallaron)}" if fallaron else ""

    def _eventos(self, _arg: str) -> str:
        evs = self.db.eventos(limite=15)
        if not evs:
            return "Sin eventos registrados."
        return "Últimos eventos:\n" + "\n".join(
            f"{time.strftime('%d/%m %H:%M', time.localtime(e['ts']))} · {e['titulo']}" for e in evs)

    def _hoy(self, _arg: str) -> str:
        if self.camaras is None:
            return "Las cámaras no están activas."
        ahora = time.time()
        inicio = time.mktime(time.localtime(ahora)[:3] + (0, 0, 0, 0, 0, -1))
        caps = rd.capturas_entre(self.camaras.grabaciones, inicio, ahora + 60)
        if not caps:
            return "Hoy no hay detecciones."
        nombres = lambda: {c["id"]: c["nombre"] for c in self.camaras.lista()}
        texto = "\n".join(["📷 Detecciones de hoy"] + rd.conteo_texto(caps, nombres))
        self.cliente.enviar_texto(texto)
        fotos = rd.leer_fotos(self.camaras.grabaciones, rd.elegir_fotos(caps))
        if fotos:
            self.cliente.enviar_album(fotos)
        return ""

    def _luces(self, _arg: str) -> str:
        if self.luces is None or not self.luces.configurado:
            return "No hay luces configuradas."
        lista = self.luces.lista()
        if self.habitaciones is not None:
            filas = [f"{h['habitacion']}: {h['encendidos']} de {h['total']} encendidas"
                     for h in self.habitaciones.resumen(lista)]
        else:
            filas = [f"{l['nombre']}: {'encendida' if l.get('encendida') else 'apagada'}" for l in lista]
        return "💡 Luces\n" + "\n".join(filas) if filas else "No hay luces."

    def _apagar(self, _arg: str) -> str:
        if self.luces is None or not self.luces.configurado:
            return "No hay luces configuradas."
        total = len(self.luces.lista())
        n = self.luces.aplicar_todas(False)
        return f"Luces apagadas: {n} de {total}."

    def _rutina(self, arg: str) -> str:
        if self.rutinas is None:
            return "Las rutinas no están disponibles."
        if not arg:
            nombres = ", ".join(r["nombre"] for r in self.rutinas.lista()) or "ninguna"
            return f"Uso: /rutina <nombre>. Disponibles: {nombres}"
        q = _sin_acentos(arg)
        for r in self.rutinas.lista():
            if _sin_acentos(r["nombre"]) == q:
                res = self.rutinas.ejecutar(r["id"], "manual")
                extra = f" (no respondió: {', '.join(res['fallaron'])})" if res["fallaron"] else ""
                return f"Rutina «{r['nombre']}»: {res['ok']} de {res['total']} focos{extra}."
        return f"No existe la rutina «{arg}»."

    # --- recepción ---
    def procesar(self, actualizacion: dict) -> bool:
        """Atiende una actualización de Telegram; ignora a cualquier chat que no sea el configurado."""
        self._offset = max(self._offset, int(actualizacion.get("update_id", 0)) + 1)
        m = actualizacion.get("message") or {}
        if str((m.get("chat") or {}).get("id")) != str(self.cfg.telegram_chat_id):
            return False
        texto = m.get("text") or ""
        if not texto.startswith("/"):
            return False
        resp = self.atender(texto)
        if resp:
            self.cliente.enviar_texto(resp)
        return True

    def _bucle(self) -> None:
        while not self._parar.is_set():
            try:
                for u in self.cliente.actualizaciones(self._offset, 25):
                    try:
                        self.procesar(u)
                    except TelegramError as e:
                        log.warning("bot: no pude responder: %s", e)
            except TelegramError as e:
                log.warning("bot de Telegram: %s", e)
                self._parar.wait(5)

    def iniciar(self) -> None:
        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name="bot-telegram", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
