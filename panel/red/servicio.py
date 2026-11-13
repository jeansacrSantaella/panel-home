"""Fachada de la red: la usan el servidor web, el recolector y main.py."""
from __future__ import annotations

import time
from typing import Optional

from panel import tareas as _tareas
from panel.red import consultas
from panel.red.almacen import RedDb
from panel.red.escaner import Escaner
from panel.red.estado import EstadoRed
from panel.red.fabricantes import Fabricantes
from panel.red.resumen import ResumenRed


class Red:
    def __init__(self, db, oui_archivo, vivo_tras: int = 90, contratado=None, reloj=time.time, fetch=None):
        self._reloj = reloj
        self._vivo_tras = vivo_tras
        self.base = RedDb(db)
        self.fabricantes = Fabricantes(oui_archivo, fetch)
        self.estado = EstadoRed(self.base, fabricante=self.fabricantes.buscar, reloj=reloj)
        self._resumen = ResumenRed(self.base, self.fabricantes.buscar, self.estado.servicios, contratado, reloj)
        self._escaner = Escaner(self.base, fabricante=self.fabricantes.buscar)

    def recibir(self, datos) -> int:
        """Procesa el cuerpo del POST de la sonda y devuelve cuántas lecturas se aplicaron."""
        if not isinstance(datos, dict) or not isinstance(datos.get("lecturas"), list):
            raise ValueError("se esperaba {lecturas: [...]}")
        n = self.estado.procesar(datos["lecturas"])
        self.base.set("sonda", {"nombre": datos.get("sonda"), "version": datos.get("version"),
                                "visto": int(self._reloj()), "lecturas": n})
        return n

    def resumen(self) -> dict:
        return self._resumen.construir()

    def resumen_vivo(self, ahora=None) -> Optional[dict]:
        """El resumen, o None si la sonda dejó de mandar lecturas."""
        ultima = self.estado.ultima_lectura()
        if ultima is None:
            return None
        ahora = self._reloj() if ahora is None else ahora
        if ahora - ultima > self._vivo_tras:
            return None
        return self.resumen()

    def eventos(self, consulta: dict) -> dict:
        return consultas.pagina_eventos(self.base, consulta)

    def csv(self) -> str:
        return consultas.exportar_csv(self.resumen(), self.base)

    def alias(self, datos) -> None:
        consultas.fijar_alias(self.base, datos)

    def network(self, datos) -> None:
        consultas.fijar_red(self.base, datos)

    def escanear(self, host, puertos=None) -> dict:
        return self._escaner.escanear(host, puertos)

    def sonda(self) -> Optional[dict]:
        return self.base.get("sonda")

    def tareas(self) -> list:
        return [
            _tareas.cada("red-fabricantes", 7 * 86400, self.fabricantes.descargar, retraso=5),
            _tareas.cada("red-podar", 86400, self.estado.podar, retraso=60),
        ]
