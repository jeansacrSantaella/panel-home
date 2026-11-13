"""Fotos y clips grabados por el detector: listar, resolver, borrar y exportar sin FastAPI."""
from __future__ import annotations

import re
import time
import zipfile
from pathlib import Path

DIA_OK = re.compile(r"^\d{4}-\d\d-\d\d$")
FOTO_OK = re.compile(r"^[\w.-]+\.jpg$")
CLIP_OK = re.compile(r"^[\w.-]+\.mp4$")
MAX_SELECCION = 2000

# tipo -> (patrón del nombre, mime)
TIPOS = {"fotos": (FOTO_OK, "image/jpeg"), "clips": (CLIP_OK, "video/mp4")}


class GrabacionError(Exception):
    def __init__(self, mensaje: str, codigo: int = 422):
        super().__init__(mensaje)
        self.codigo = codigo


class _SoloEscribe:
    """Adaptador: zipfile pide flush() al cerrar, pero la salida puede no tenerlo."""

    def __init__(self, salida):
        self.salida = salida

    def write(self, datos: bytes) -> int:
        return self.salida.write(datos)

    def flush(self) -> None:
        if hasattr(self.salida, "flush"):
            self.salida.flush()


def _quitar_si_vacia(carpeta: Path) -> None:
    try:
        carpeta.rmdir()  # solo funciona si está vacía
    except OSError:
        pass


class Grabaciones:
    def __init__(self, data: Path):
        self.data = Path(data)

    def dias(self) -> list[str]:
        """Días con fotos o clips, del más nuevo al más viejo."""
        dias = set()
        for tipo in TIPOS:
            base = self.data / tipo
            if base.is_dir():
                dias.update(d.name for d in base.iterdir() if DIA_OK.fullmatch(d.name) and d.is_dir())
        return sorted(dias, reverse=True)

    def _listar(self, tipo: str, fecha: str) -> list[str]:
        if not DIA_OK.fullmatch(fecha):
            raise GrabacionError("fecha inválida (AAAA-MM-DD)", 422)
        carpeta = self.data / tipo / fecha
        if not carpeta.is_dir():
            return []
        patron = TIPOS[tipo][0]
        return sorted(f.name for f in carpeta.iterdir() if patron.fullmatch(f.name) and f.is_file())

    def fotos(self, fecha: str) -> list[str]:
        return self._listar("fotos", fecha)

    def clips(self, fecha: str) -> list[str]:
        return self._listar("clips", fecha)

    def ruta(self, tipo: str, fecha: str, archivo: str) -> Path:
        """Ruta segura dentro de data/; 404 si el tipo, la fecha o el nombre no son válidos."""
        if tipo not in TIPOS or not DIA_OK.fullmatch(fecha) or not TIPOS[tipo][0].fullmatch(archivo):
            raise GrabacionError("no existe", 404)
        ruta = self.data / tipo / fecha / archivo
        # Un enlace simbólico dentro de data/ no puede llevar fuera
        if self.data.resolve() not in ruta.resolve().parents:
            raise GrabacionError("no existe", 404)
        return ruta

    def tipo_mime(self, tipo: str) -> str:
        if tipo not in TIPOS:
            raise GrabacionError("no existe", 404)
        return TIPOS[tipo][1]

    def resolver(self, fotos: list[str], clips: list[str]) -> list[tuple[Path, str]]:
        """Convierte "AAAA-MM-DD/archivo" en (ruta, arcname); omite los que no existen."""
        if len(fotos) + len(clips) > MAX_SELECCION:
            raise GrabacionError("demasiados elementos", 422)
        res = []
        for tipo, lista in (("fotos", fotos), ("clips", clips)):
            for elem in lista:
                if "/" not in elem:
                    raise GrabacionError("elemento inválido", 422)
                fecha, archivo = elem.split("/", 1)
                ruta = self.ruta(tipo, fecha, archivo)
                if ruta.is_file():
                    res.append((ruta, f"{tipo}/{fecha}/{archivo}"))
        return res

    def borrar(self, fotos: list[str], clips: list[str]) -> int:
        n = 0
        carpetas = set()
        for ruta, _ in self.resolver(fotos, clips):
            try:
                ruta.unlink()
                n += 1
                carpetas.add(ruta.parent)
            except OSError:
                pass
        for carpeta in carpetas:
            _quitar_si_vacia(carpeta)
        return n

    def borrar_dia(self, fecha: str) -> int:
        n = 0
        for ruta, _ in self.pares_dia(fecha):
            try:
                ruta.unlink()
                n += 1
            except OSError:
                pass
        for tipo in TIPOS:
            _quitar_si_vacia(self.data / tipo / fecha)
        return n

    def pares_dia(self, fecha: str) -> list[tuple[Path, str]]:
        """Todas las fotos y clips de un día, para exportar."""
        pares = []
        for tipo in TIPOS:
            for nombre in self._listar(tipo, fecha):
                pares.append((self.data / tipo / fecha / nombre, f"{tipo}/{fecha}/{nombre}"))
        return pares

    def escribir_zip(self, pares: list[tuple[Path, str]], salida) -> None:
        """Escribe el zip sin compresión en `salida`, que puede no admitir seek."""
        if not pares:
            raise GrabacionError("Nada que exportar", 404)
        with zipfile.ZipFile(_SoloEscribe(salida), "w", zipfile.ZIP_STORED) as z:
            for ruta, arcname in pares:
                z.write(ruta, arcname=arcname)

    @staticmethod
    def nombre_zip() -> str:
        return f"grabaciones_{time.strftime('%Y-%m-%d_%H-%M')}.zip"
