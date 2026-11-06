"""Enviador de notificaciones a través de Telegram y ntfy."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from panel import fuentes

logger = logging.getLogger("panel.avisos")

ICONO = {"alto": "🔴", "medio": "🟠", "bajo": "🔵", "info": "🟢"}
PRIORIDAD_NTFY = {"alto": "high", "medio": "default", "bajo": "low", "info": "low"}


class Avisador:
    """Gestiona el envío de notificaciones pendientes por Telegram y ntfy."""

    def __init__(self, cfg: Any, db: Any) -> None:
        self.cfg = cfg
        self.db = db

    @property
    def activo(self) -> bool:
        """Indica si al menos un canal de avisos está configurado."""
        telegram_ok = bool(self.cfg.telegram_token and self.cfg.telegram_chat_id)
        ntfy_ok = bool(self.cfg.ntfy_url)
        return telegram_ok or ntfy_ok

    def texto(self, ev: dict) -> str:
        """Formatea el evento en un texto de varias líneas para notificar."""
        nivel = ev.get("nivel", "")
        icono = ICONO.get(nivel, "⚪")
        titulo = ev.get("titulo", "")
        lineas = [f"{icono} {titulo}"]

        if ev.get("detalle"):
            lineas.append(ev["detalle"])

        hora_str = time.strftime("%d/%m %H:%M:%S", time.localtime(ev["ts"]))
        lineas.append(hora_str)
        return "\n".join(lineas)

    def enviar_pendientes(self) -> int:
        """Envía los eventos pendientes de aviso. Devuelve la cantidad enviada."""
        if not self.activo:
            return 0

        pendientes = self.db.pendientes_aviso(self.cfg.avisar)
        ahora = time.time()
        enviados = 0

        for ev in pendientes:
            if ahora - ev["ts"] > 86400:
                self.db.marcar_avisado([ev["id"]], valor=2)
                continue

            ok = self._enviar(ev)
            if ok:
                self.db.marcar_avisado([ev["id"]])
                enviados += 1
            else:
                break

        return enviados

    def _enviar(self, ev: dict) -> bool:
        """Envía el evento a los canales activos. True si al menos uno tuvo éxito."""
        texto = self.texto(ev)
        resultados = []

        if self.cfg.telegram_token and self.cfg.telegram_chat_id:
            foto = None
            if ev.get("tipo") == "movimiento" and ev.get("ref"):
                foto = fuentes.leer_foto(self.cfg, ev["ref"])

            if foto:
                resultados.append(self._telegram_foto(foto, ev["ref"].split("/")[-1], texto))
            else:
                resultados.append(self._telegram_texto(texto))

        if self.cfg.ntfy_url:
            resultados.append(self._ntfy(ev, texto))

        return any(resultados) if resultados else False

    def _telegram_texto(self, texto: str) -> bool:
        """Envía un mensaje de texto por la API de Telegram."""
        url = f"https://api.telegram.org/bot{self.cfg.telegram_token}/sendMessage"
        datos = urllib.parse.urlencode({
            "chat_id": self.cfg.telegram_chat_id,
            "text": texto,
        }).encode("utf-8")

        req = urllib.request.Request(url, data=datos, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return bool(res.get("ok"))
        except Exception as e:
            logger.warning("Error enviando texto por Telegram: %s", e)
            return False

    def _telegram_foto(self, contenido_foto: bytes, nombre: str, texto: str) -> bool:
        """Envía una foto con descripción por la API de Telegram."""
        boundary = uuid.uuid4().hex
        crlf = b"\r\n"
        body = bytearray()

        # Campo chat_id
        body.extend(f"--{boundary}".encode("utf-8") + crlf)
        body.extend(b'Content-Disposition: form-data; name="chat_id"' + crlf + crlf)
        body.extend(str(self.cfg.telegram_chat_id).encode("utf-8") + crlf)

        # Campo caption
        body.extend(f"--{boundary}".encode("utf-8") + crlf)
        body.extend(b'Content-Disposition: form-data; name="caption"' + crlf + crlf)
        body.extend(texto.encode("utf-8") + crlf)

        # Archivo photo
        body.extend(f"--{boundary}".encode("utf-8") + crlf)
        body.extend(f'Content-Disposition: form-data; name="photo"; filename="{nombre}"'.encode("utf-8") + crlf)
        body.extend(b"Content-Type: image/jpeg" + crlf + crlf)
        body.extend(contenido_foto + crlf)
        body.extend(f"--{boundary}--".encode("utf-8") + crlf)

        url = f"https://api.telegram.org/bot{self.cfg.telegram_token}/sendPhoto"
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        req = urllib.request.Request(url, data=bytes(body), headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return bool(res.get("ok"))
        except Exception as e:
            logger.warning("Error enviando foto por Telegram: %s", e)
            return False

    def _ntfy(self, ev: dict, texto: str) -> bool:
        """Envía un aviso a través de ntfy."""
        nivel = ev.get("nivel", "")
        prioridad = PRIORIDAD_NTFY.get(nivel, "low")
        tag = "rotating_light" if nivel == "alto" else "house"

        headers = {
            "Priority": prioridad,
            "Tags": tag,
        }

        req = urllib.request.Request(
            self.cfg.ntfy_url,
            data=texto.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return 200 <= resp.status < 300
        except Exception as e:
            logger.warning("Error enviando aviso por ntfy: %s", e)
            return False
