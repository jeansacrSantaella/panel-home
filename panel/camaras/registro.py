"""Registro de cámaras en panel.db: agregar, quitar y consultar (port de gestorCamaras/main.py)."""
from __future__ import annotations

import ipaddress
import json
import re
import threading
from pathlib import Path
from urllib.parse import quote

ESQUEMA = """CREATE TABLE IF NOT EXISTS camaras(id TEXT PRIMARY KEY, nombre TEXT, ip TEXT, puerto_rtsp INTEGER,
  ruta_rtsp TEXT, puerto_onvif INTEGER, usuario TEXT, clave TEXT, orden INTEGER)"""
RUTA_DEFECTO = "/live/ch00_0"
RUTA_OK = re.compile(r"^/[A-Za-z0-9_\-./?=&%]*$")
CAMPOS_PUBLICOS = ("id", "nombre", "ip", "puerto_rtsp", "ruta_rtsp", "puerto_onvif", "usuario")


class CamaraError(Exception):
    def __init__(self, mensaje: str, codigo: int = 422):
        super().__init__(mensaje)
        self.codigo = codigo  # 422 datos no válidos, 404 no existe


def validar_ip(txt: str) -> str:
    try:
        ip = ipaddress.ip_address(txt)
    except ValueError:
        raise CamaraError(f"IP no válida: {txt}")
    if not ip.is_private or ip.is_loopback:  # solo red local
        raise CamaraError(f"Solo se permiten IPs de la red local: {txt}")
    return str(ip)


def fuente_rtsp(c: dict) -> str:
    cred = ""
    if c["usuario"]:
        cred = f'{quote(c["usuario"], safe="")}:{quote(c["clave"], safe="")}@'
    # Se recodifica a propósito (ffmpeg), igual que main.fuente().
    return f'ffmpeg:rtsp://{cred}{c["ip"]}:{c["puerto_rtsp"]}{c["ruta_rtsp"]}#video=h264#audio=aac'


def publica(c: dict) -> dict:
    return {k: c[k] for k in CAMPOS_PUBLICOS} | {"tiene_clave": bool(c["clave"])}


def _id_libre(base: str, usados: set) -> str:
    """Devuelve `base` si está libre; si no, el siguiente camaraN libre."""
    if base and base not in usados:
        return base
    n = 1
    while f"camara{n}" in usados:
        n += 1
    return f"camara{n}"


class Registro:
    def __init__(self, db, max_camaras: int = 32, iniciales: str = ""):
        self.db = db
        self.max_camaras = max_camaras
        self._candado = threading.Lock()
        db._x(ESQUEMA)
        with self._candado:
            if not self._filas() and iniciales:
                self._sembrar(iniciales)

    # --- lectura ---
    def _filas(self) -> list:
        return self.db._q("SELECT * FROM camaras ORDER BY orden")

    def lista(self) -> list:
        return self._filas()

    def publicas(self) -> list:
        return [publica(c) for c in self._filas()]

    def una(self, cid: str) -> dict:
        filas = self.db._q("SELECT * FROM camaras WHERE id = ?", (cid,))
        if not filas:
            raise CamaraError(f"No existe la cámara {cid}", 404)
        return filas[0]

    # --- escritura (sin candado: quien llama debe tenerlo) ---
    def _sembrar(self, iniciales: str) -> None:
        # Primera vez: "camara1=192.168.1.69,camara2=192.168.1.72", como main._cargar.
        filas = []
        for par in iniciales.split(","):
            if "=" not in par:
                continue
            nombre, ip = (p.strip() for p in par.split("=", 1))
            usados = {f[0] for f in filas}
            cid = _id_libre(re.sub(r"[^a-z0-9_-]", "", nombre.lower()), usados)
            filas.append((cid, nombre, ip, 554, RUTA_DEFECTO, 8899, "", "", len(filas) + 1))
        self._insertar(filas)

    def _insertar(self, filas: list) -> None:
        if filas:
            self.db._x("INSERT INTO camaras(id, nombre, ip, puerto_rtsp, ruta_rtsp, puerto_onvif, usuario, clave, orden) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", filas, muchos=True)

    # --- agregar / quitar ---
    def agregar(self, ips: str, nombre: str = "", puerto_rtsp: int = 554, ruta_rtsp: str = RUTA_DEFECTO,
                puerto_onvif: int = 8899, usuario: str = "", clave: str = "") -> dict:
        lista_ips = [p for p in re.split(r"[\s,;]+", ips) if p]
        if not lista_ips:
            raise CamaraError("Escribe al menos una IP")
        lista_ips = [validar_ip(i) for i in dict.fromkeys(lista_ips)]
        if not RUTA_OK.match(ruta_rtsp):
            raise CamaraError("La ruta RTSP debe empezar con / y no llevar espacios ni #")
        if not (1 <= puerto_rtsp <= 65535 and 1 <= puerto_onvif <= 65535):
            raise CamaraError("Puerto fuera de rango")
        nombre = nombre.strip()[:40]
        with self._candado:
            actuales = self._filas()
            existentes = {c["ip"] for c in actuales}
            omitidas = [ip for ip in lista_ips if ip in existentes]
            nuevas_ips = [ip for ip in lista_ips if ip not in existentes]
            # Todo o nada: si no caben, no se guarda ninguna.
            if len(actuales) + len(nuevas_ips) > self.max_camaras:
                raise CamaraError(f"Límite de {self.max_camaras} cámaras")
            usados = {c["id"] for c in actuales}
            orden = max((c["orden"] for c in actuales), default=0)
            filas = []
            for ip in nuevas_ips:
                cid = _id_libre("", usados)
                usados.add(cid)
                orden += 1
                num = cid.removeprefix("camara")
                etiqueta = nombre if (nombre and len(lista_ips) == 1) else f"{nombre or 'Cámara'} {num}"
                filas.append((cid, etiqueta, ip, puerto_rtsp, ruta_rtsp, puerto_onvif, usuario, clave, orden))
            self._insertar(filas)
            ids = [f[0] for f in filas]
        agregadas = [self.una(i) for i in ids]
        return {"agregadas": agregadas, "omitidas": omitidas}

    def quitar(self, cid: str) -> None:
        with self._candado:
            if self.db._x("DELETE FROM camaras WHERE id = ?", (cid,)) == 0:
                raise CamaraError(f"No existe la cámara {cid}", 404)

    def importar_json(self, ruta) -> int:
        """Agrega las cámaras de un cameras.json de gestorCamaras que no existan (por id ni por ip)."""
        ruta = Path(ruta)
        if not ruta.is_file():
            return 0
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        origen = datos.get("camaras", []) if isinstance(datos, dict) else []
        with self._candado:
            actuales = self._filas()
            usados = {c["id"] for c in actuales}
            ips = {c["ip"] for c in actuales}
            orden = max((c["orden"] for c in actuales), default=0)
            filas = []
            for c in origen:
                if not isinstance(c, dict) or len(actuales) + len(filas) >= self.max_camaras:
                    continue
                try:
                    ip = validar_ip(str(c.get("ip", "")))
                    cid = str(c["id"]) if c.get("id") else _id_libre("", usados)
                    puerto_rtsp = int(c.get("puerto_rtsp", 554))
                    puerto_onvif = int(c.get("puerto_onvif", 8899))
                    ruta = str(c.get("ruta_rtsp", RUTA_DEFECTO))
                except (CamaraError, KeyError, TypeError, ValueError):
                    continue
                if not RUTA_OK.match(ruta) or not (1 <= puerto_rtsp <= 65535 and 1 <= puerto_onvif <= 65535):
                    continue
                if cid in usados or ip in ips:
                    continue
                usados.add(cid)
                ips.add(ip)
                orden += 1
                filas.append((cid, str(c.get("nombre", ""))[:40], ip, puerto_rtsp,
                              ruta, puerto_onvif,
                              str(c.get("usuario", "")), str(c.get("clave", "")), orden))
            self._insertar(filas)
        return len(filas)
