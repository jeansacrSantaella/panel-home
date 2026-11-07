"""Cuentas, contraseñas y sesiones del panel.

- Contraseñas con PBKDF2-SHA256 (200 000 iteraciones, sal aleatoria); nunca en claro.
- Sesiones con token aleatorio en una cookie; en la base solo vive el SHA-256 del token.
- Bloqueo por IP tras 5 intentos fallidos (1 min, se duplica hasta 15 min).
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
import secrets
import threading
import time

ITERACIONES = 200_000
DURACION_SESION = 30 * 86400
USUARIO_INICIAL = "admin"
CLAVE_INICIAL = "1234"
MIN_LARGO = 8
COOKIE = "orion_sesion"
FALLOS_PERMITIDOS = 5
FACILES = {"12345678", "123456789", "1234567890", "contraseña", "contrasena", "password", "admin1234",
           "qwertyui", "qwerty123", "orionhome"}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios(
    nombre TEXT PRIMARY KEY, hash TEXT NOT NULL, debe_cambiar INTEGER NOT NULL DEFAULT 1,
    creado INTEGER, cambiado INTEGER);
CREATE TABLE IF NOT EXISTS sesiones(
    token TEXT PRIMARY KEY, usuario TEXT NOT NULL, creado INTEGER, expira INTEGER, ultimo INTEGER, ip TEXT);
"""


def hash_contrasena(contrasena: str, sal: bytes | None = None, iteraciones: int = ITERACIONES) -> str:
    """Devuelve "pbkdf2_sha256$iter$sal$hash" (hex)."""
    sal = os.urandom(16) if sal is None else sal
    dk = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${sal.hex()}${dk.hex()}"


def verificar_contrasena(contrasena: str, guardado: str) -> bool:
    """Compara en tiempo constante; un formato inválido nunca coincide."""
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), bytes.fromhex(sal), int(iteraciones))
        return hmac.compare_digest(dk.hex(), esperado)
    except (ValueError, TypeError):
        return False


def validar_nueva(nueva: str, actual: str) -> None:
    """Lanza ValueError (mensaje para el usuario) si la nueva contraseña no sirve."""
    if len(nueva) < MIN_LARGO:
        raise ValueError(f"La contraseña debe tener al menos {MIN_LARGO} caracteres")
    if nueva in (CLAVE_INICIAL, actual):
        raise ValueError("Elige una contraseña distinta a la actual")
    if nueva.lower() in FACILES or len(set(nueva)) <= 2:
        raise ValueError("Esa contraseña es demasiado fácil de adivinar")


def _h(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Bloqueado(Exception):
    """Demasiados intentos desde la misma IP; `segundos` que faltan para reintentar."""

    def __init__(self, segundos: int):
        super().__init__(f"bloqueado {segundos} s")
        self.segundos = segundos


class Auth:
    def __init__(self, db, al_bloquear=None):
        self.db = db
        self.al_bloquear = al_bloquear
        self._fallos: dict = {}  # ip -> [fallos, bloqueado_hasta]
        self._lock = threading.Lock()
        self._ficticio = hash_contrasena("x" * 12)  # iguala el tiempo con usuarios que no existen
        for sentencia in filter(None, (x.strip() for x in ESQUEMA.split(";"))):
            db._x(sentencia)

    # --- cuentas ---
    def asegurar_admin(self) -> bool:
        """Primera vez: crea admin / 1234 marcada para cambiarse. Devuelve True si la creó."""
        if self.db._q("SELECT 1 FROM usuarios LIMIT 1"):
            return False
        self.db._x("INSERT INTO usuarios(nombre, hash, debe_cambiar, creado) VALUES (?,?,1,?)",
                   (USUARIO_INICIAL, hash_contrasena(CLAVE_INICIAL), int(time.time())))
        return True

    def restablecer_admin(self) -> None:
        """Regresa admin a 1234 (con cambio obligatorio) y cierra todas sus sesiones."""
        h = hash_contrasena(CLAVE_INICIAL)
        if self.db._x("UPDATE usuarios SET hash = ?, debe_cambiar = 1 WHERE nombre = ?", (h, USUARIO_INICIAL)) == 0:
            self.db._x("INSERT INTO usuarios(nombre, hash, debe_cambiar, creado) VALUES (?,?,1,?)",
                       (USUARIO_INICIAL, h, int(time.time())))
        self.db._x("DELETE FROM sesiones WHERE usuario = ?", (USUARIO_INICIAL,))

    def cambiar(self, usuario: str, actual: str, nueva: str, token_actual: str | None = None) -> None:
        """Cambia la contraseña y cierra las demás sesiones del usuario."""
        fila = self.db._q("SELECT hash FROM usuarios WHERE nombre = ?", (usuario,))
        if not fila or not verificar_contrasena(actual, fila[0]["hash"]):
            raise ValueError("La contraseña actual no es correcta")
        validar_nueva(nueva, actual)
        self.db._x("UPDATE usuarios SET hash = ?, debe_cambiar = 0, cambiado = ? WHERE nombre = ?",
                   (hash_contrasena(nueva), int(time.time()), usuario))
        self.db._x("DELETE FROM sesiones WHERE usuario = ? AND token != ?", (usuario, _h(token_actual or "")))

    # --- sesiones ---
    def entrar(self, usuario: str, contrasena: str, ip: str, ahora: float | None = None) -> dict | None:
        ahora = time.time() if ahora is None else ahora
        with self._lock:
            fallos, hasta = self._fallos.get(ip, [0, 0.0])
            if hasta > ahora:
                raise Bloqueado(math.ceil(hasta - ahora))
        nombre = (usuario or "").strip()
        fila = self.db._q("SELECT nombre, hash, debe_cambiar FROM usuarios WHERE nombre = ?", (nombre,))
        ok = verificar_contrasena(contrasena or "", fila[0]["hash"] if fila else self._ficticio) and bool(fila)
        if not ok:
            with self._lock:
                fallos = self._fallos.get(ip, [0, 0.0])[0] + 1
                segundos = 0
                if fallos >= FALLOS_PERMITIDOS:
                    segundos = min(900, 60 * 2 ** (fallos - FALLOS_PERMITIDOS))
                self._fallos[ip] = [fallos, ahora + segundos]
            if segundos:
                if self.al_bloquear:
                    try:
                        self.al_bloquear(ip, segundos)
                    except Exception:  # un aviso que falla no debe abrir la puerta ni tumbar el login
                        pass
                raise Bloqueado(segundos)
            return None
        with self._lock:
            self._fallos.pop(ip, None)
        t = int(ahora)
        self.db._x("DELETE FROM sesiones WHERE expira < ?", (t,))
        token = secrets.token_urlsafe(32)
        self.db._x("INSERT INTO sesiones(token, usuario, creado, expira, ultimo, ip) VALUES (?,?,?,?,?,?)",
                   (_h(token), fila[0]["nombre"], t, t + DURACION_SESION, t, ip))
        return {"token": token, "usuario": fila[0]["nombre"], "debe_cambiar": bool(fila[0]["debe_cambiar"])}

    def sesion(self, token: str | None, ahora: float | None = None) -> dict | None:
        if not token:
            return None
        ahora = int(time.time() if ahora is None else ahora)
        h = _h(token)
        fila = self.db._q("SELECT s.usuario, s.expira, s.ultimo, u.debe_cambiar FROM sesiones s "
                          "LEFT JOIN usuarios u ON u.nombre = s.usuario WHERE s.token = ?", (h,))
        if not fila:
            return None
        s = fila[0]
        if s["expira"] < ahora or s["debe_cambiar"] is None:  # vencida o el usuario ya no existe
            self.db._x("DELETE FROM sesiones WHERE token = ?", (h,))
            return None
        if ahora - (s["ultimo"] or 0) > 300:
            self.db._x("UPDATE sesiones SET ultimo = ? WHERE token = ?", (ahora, h))
        return {"usuario": s["usuario"], "debe_cambiar": bool(s["debe_cambiar"])}

    def salir(self, token: str | None) -> None:
        if token:
            self.db._x("DELETE FROM sesiones WHERE token = ?", (_h(token),))
