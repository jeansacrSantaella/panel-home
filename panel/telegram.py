"""Cliente mínimo de la API de Telegram (solo urllib): texto, fotos, álbumes y getUpdates."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Callable, List, Optional, Tuple

API = "https://api.telegram.org"


class TelegramError(Exception):
    """Fallo al hablar con Telegram (red, HTTP o respuesta con ok=false)."""

    def __init__(self, mensaje: str, codigo: int = 0):
        super().__init__(mensaje)
        self.codigo = codigo


def multipart(campos: dict, archivos: List[Tuple[str, str, bytes]]) -> Tuple[bytes, str]:
    """Arma un cuerpo multipart/form-data. archivos: [(campo, nombre, contenido)]."""
    limite = uuid.uuid4().hex
    crlf = b"\r\n"
    cuerpo = bytearray()
    for k, v in campos.items():
        cuerpo += f"--{limite}".encode() + crlf
        cuerpo += f'Content-Disposition: form-data; name="{k}"'.encode() + crlf + crlf
        cuerpo += str(v).encode("utf-8") + crlf
    for campo, nombre, datos in archivos:
        cuerpo += f"--{limite}".encode() + crlf
        cuerpo += f'Content-Disposition: form-data; name="{campo}"; filename="{nombre}"'.encode() + crlf
        cuerpo += b"Content-Type: image/jpeg" + crlf + crlf
        cuerpo += datos + crlf
    cuerpo += f"--{limite}--".encode() + crlf
    return bytes(cuerpo), f"multipart/form-data; boundary={limite}"


class Telegram:
    def __init__(self, token: str, chat_id: str, abrir: Optional[Callable] = None, timeout: float = 15):
        self.token = token
        self.chat_id = str(chat_id)
        self.timeout = timeout
        self._abrir = abrir or urllib.request.urlopen

    def _llamar(self, metodo: str, datos: bytes, tipo: str, timeout: Optional[float] = None) -> dict:
        req = urllib.request.Request(f"{API}/bot{self.token}/{metodo}", data=datos,
                                     headers={"Content-Type": tipo}, method="POST")
        try:
            with self._abrir(req, timeout=timeout or self.timeout) as resp:
                res = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise TelegramError(f"{metodo}: HTTP {e.code}", e.code) from None
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise TelegramError(f"{metodo}: {e}") from None
        if not res.get("ok"):
            raise TelegramError(f"{metodo}: {res.get('description', 'respuesta sin ok')}", res.get("error_code", 0))
        return res

    def _formulario(self, metodo: str, campos: dict, timeout: Optional[float] = None) -> dict:
        return self._llamar(metodo, urllib.parse.urlencode(campos).encode("utf-8"),
                            "application/x-www-form-urlencoded", timeout)

    def enviar_texto(self, texto: str) -> None:
        self._formulario("sendMessage", {"chat_id": self.chat_id, "text": texto[:4096]})

    def enviar_foto(self, foto: bytes, pie: str = "") -> None:
        cuerpo, tipo = multipart({"chat_id": self.chat_id, "caption": pie[:1024]}, [("photo", "foto.jpg", foto)])
        self._llamar("sendPhoto", cuerpo, tipo)

    def enviar_album(self, fotos: List[Tuple[bytes, str]]) -> None:
        """Hasta 10 fotos juntas; con una sola usa sendPhoto."""
        fotos = fotos[:10]
        if not fotos:
            return
        if len(fotos) == 1:
            return self.enviar_foto(*fotos[0])
        media = [{"type": "photo", "media": f"attach://f{i}", "caption": pie[:1024]}
                 for i, (_, pie) in enumerate(fotos)]
        cuerpo, tipo = multipart({"chat_id": self.chat_id, "media": json.dumps(media)},
                                 [(f"f{i}", f"f{i}.jpg", datos) for i, (datos, _) in enumerate(fotos)])
        self._llamar("sendMediaGroup", cuerpo, tipo, timeout=60)

    def actualizaciones(self, offset: int = 0, espera: int = 25) -> list:
        """getUpdates con long polling; devuelve la lista de actualizaciones."""
        res = self._formulario("getUpdates", {"offset": offset, "timeout": espera}, timeout=espera + 10)
        return res.get("result", [])
