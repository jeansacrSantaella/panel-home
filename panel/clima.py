from __future__ import annotations

import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

URL_PRONOSTICO = "https://api.open-meteo.com/v1/forecast"
URL_GEO = "https://geocoding-api.open-meteo.com/v1/search"
URL_IP = "https://ipapi.co/json/"

# código WMO -> (descripción en español, ícono)
CODIGOS: dict[int, tuple[str, str]] = {
    0: ("Despejado", "sol"),
    1: ("Mayormente despejado", "parcial"),
    2: ("Parcialmente nublado", "parcial"),
    3: ("Nublado", "nubes"),
    45: ("Niebla", "niebla"),
    48: ("Niebla con escarcha", "niebla"),
    51: ("Llovizna ligera", "llovizna"),
    53: ("Llovizna moderada", "llovizna"),
    55: ("Llovizna densa", "llovizna"),
    56: ("Llovizna helada ligera", "llovizna"),
    57: ("Llovizna helada densa", "llovizna"),
    61: ("Lluvia ligera", "lluvia"),
    63: ("Lluvia moderada", "lluvia"),
    65: ("Lluvia fuerte", "lluvia"),
    66: ("Lluvia helada ligera", "lluvia"),
    67: ("Lluvia helada fuerte", "lluvia"),
    71: ("Nieve ligera", "nieve"),
    73: ("Nieve moderada", "nieve"),
    75: ("Nieve fuerte", "nieve"),
    77: ("Granos de nieve", "nieve"),
    80: ("Chubascos ligeros", "lluvia"),
    81: ("Chubascos moderados", "lluvia"),
    82: ("Chubascos violentos", "lluvia"),
    85: ("Chubascos de nieve ligeros", "nieve"),
    86: ("Chubascos de nieve fuertes", "nieve"),
    95: ("Tormenta", "tormenta"),
    96: ("Tormenta con granizo ligero", "tormenta"),
    99: ("Tormenta con granizo fuerte", "tormenta"),
}

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

def describir(codigo: int | None) -> tuple[str, str]:
    """Devuelve descripción e ícono para un código WMO."""
    if codigo is None or codigo not in CODIGOS:
        return ("—", "nubes")
    return CODIGOS[codigo]

def _fetch_default(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "PleyadesHome"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

class Clima:
    def __init__(self, db, ciudad: str = "", lat: float | None = None, lon: float | None = None, fetch=None, reloj=time.time):
        self.db = db
        self._ciudad = ciudad
        self._lat = lat
        self._lon = lon
        self.fetch = fetch or _fetch_default
        self.reloj = reloj
        self.error: str | None = None
        self._memoria: dict | None = None
        self._cache_dispositivos: list[tuple[tuple[float, float], float, dict]] = []

    @property
    def configurado(self) -> bool:
        return True

    @property
    def origen(self) -> str:
        if self._lat is not None and self._lon is not None:
            return "coordenadas"
        if self._ciudad:
            return "ciudad"
        return "ip"

    def ubicacion(self) -> tuple[float, float, str] | None:
        if self._lat is not None and self._lon is not None:
            return (self._lat, self._lon, self._ciudad)
        
        if not self._ciudad:
            # Ubicar por IP
            ahora = int(self.reloj())
            guardado = self.db.get("clima:ubicacion_ip")
            if guardado and (ahora - guardado.get("ts", 0)) < 86400:
                return (guardado["lat"], guardado["lon"], guardado["ciudad"])

            try:
                raw = self.fetch(URL_IP)
                data = json.loads(raw.decode("utf-8"))
                if data.get("error") or "latitude" not in data or "longitude" not in data:
                    self.error = "Error al obtener ubicación por IP"
                    if guardado:
                        return (guardado["lat"], guardado["lon"], guardado["ciudad"])
                    return None
                
                lat = float(data["latitude"])
                lon = float(data["longitude"])
                city = data.get("city", "")
                region = data.get("region", "")
                ciudad_fmt = f"{city}, {region}" if region else city
                
                ubic = {"lat": lat, "lon": lon, "ciudad": ciudad_fmt, "ts": ahora}
                self.db.set("clima:ubicacion_ip", ubic)
                return (lat, lon, ciudad_fmt)
            except Exception as e:
                self.error = str(e)
                if guardado:
                    return (guardado["lat"], guardado["lon"], guardado["ciudad"])
                return None

        # Verificar si ya está en db
        guardado = self.db.get("clima:ubicacion")
        if guardado and guardado.get("consulta") == self._ciudad:
            return (guardado["lat"], guardado["lon"], guardado["ciudad"])

        # Geocodificar
        params = {"name": self._ciudad, "count": "1", "language": "es", "format": "json"}
        url = f"{URL_GEO}?{urllib.parse.urlencode(params)}"
        try:
            raw = self.fetch(url)
            data = json.loads(raw.decode("utf-8"))
            results = data.get("results")
            if not results:
                self.error = f"Ciudad no encontrada: {self._ciudad}"
                return None
            res = results[0]
            lat = float(res["latitude"])
            lon = float(res["longitude"])
            name = res.get("name", "")
            admin1 = res.get("admin1", "")
            ciudad_fmt = f"{name}, {admin1}" if admin1 else name
            
            ubic = {"ciudad": ciudad_fmt, "lat": lat, "lon": lon, "consulta": self._ciudad}
            self.db.set("clima:ubicacion", ubic)
            return (lat, lon, ciudad_fmt)
        except Exception as e:
            self.error = str(e)
            return None

    def _pronostico(self, lat: float, lon: float, ciudad: str, origen: str = "") -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": "5"
        }
        url = f"{URL_PRONOSTICO}?{urllib.parse.urlencode(params)}"
        raw = self.fetch(url)
        data = json.loads(raw.decode("utf-8"))
        
        cur = data.get("current", {})
        daily = data.get("daily", {})
        
        codigo_act = cur.get("weather_code")
        desc, icono = describir(codigo_act)
        
        actual = {
            "temp": round(float(cur.get("temperature_2m", 0)), 1),
            "sensacion": round(float(cur.get("apparent_temperature", 0)), 1),
            "humedad": int(cur.get("relative_humidity_2m", 0)),
            "codigo": int(codigo_act) if codigo_act is not None else 0,
            "descripcion": desc,
            "icono": icono,
            "es_dia": bool(cur.get("is_day", 1))
        }

        times = daily.get("time", [])
        tmax = daily.get("temperature_2m_max", [])
        tmin = daily.get("temperature_2m_min", [])
        wc = daily.get("weather_code", [])

        hoy = None
        dias = []
        
        for i, fecha_str in enumerate(times):
            max_t = round(float(tmax[i]), 1) if i < len(tmax) and tmax[i] is not None else 0.0
            min_t = round(float(tmin[i]), 1) if i < len(tmin) and tmin[i] is not None else 0.0
            c_dia = wc[i] if i < len(wc) else 0
            d_desc, d_ico = describir(c_dia)
            
            dt = datetime.strptime(fecha_str, "%Y-%m-%d")
            dia_sem = DIAS_SEMANA[dt.weekday()]
            
            item = {
                "fecha": fecha_str,
                "dia": dia_sem,
                "codigo": int(c_dia) if c_dia is not None else 0,
                "descripcion": d_desc,
                "icono": d_ico,
                "max": max_t,
                "min": min_t
            }
            if i == 0:
                hoy = {"max": max_t, "min": min_t}
            else:
                dias.append(item)

        orig = origen if origen else self.origen
        return {
            "configurado": True,
            "origen": orig,
            "ciudad": ciudad,
            "actualizado": int(self.reloj()),
            "error": None,
            "actual": actual,
            "hoy": hoy,
            "dias": dias
        }

    def actualizar(self) -> bool:
        ubic = self.ubicacion()
        if not ubic:
            return False
        lat, lon, nombre_ciudad = ubic

        try:
            resultado = self._pronostico(lat, lon, nombre_ciudad)
            self.error = None
            self._memoria = resultado
            self.db.set("clima:ultimo", resultado)
            return True
        except Exception as e:
            self.error = str(e)
            ultimo = self.db.get("clima:ultimo", {})
            if ultimo:
                ultimo["error"] = self.error
                self._memoria = ultimo
            else:
                self._memoria = {
                    "configurado": self.configurado,
                    "origen": self.origen,
                    "ciudad": self._ciudad,
                    "actualizado": None,
                    "error": self.error,
                    "actual": None,
                    "hoy": None,
                    "dias": []
                }
            return False

    def datos_para(self, lat: float, lon: float) -> dict:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("coordenadas inválidas")
        
        lat_r = round(lat, 2)
        lon_r = round(lon, 2)
        clave_coord = (lat_r, lon_r)
        ahora = self.reloj()

        # Limpiar caché y buscar
        self._cache_dispositivos = [item for item in self._cache_dispositivos if ahora - item[1] < 900]
        for coord, ts, res in self._cache_dispositivos:
            if coord == clave_coord:
                return res

        try:
            res = self._pronostico(lat_r, lon_r, "Tu ubicación", origen="dispositivo")
            self._cache_dispositivos.append((clave_coord, ahora, res))
            if len(self._cache_dispositivos) > 50:
                self._cache_dispositivos.pop(0)
            return res
        except Exception as e:
            self.error = str(e)
            casa = self.datos()
            casa_copia = dict(casa)
            casa_copia["error"] = self.error
            return casa_copia

    def datos(self) -> dict:
        if self._memoria is not None:
            return self._memoria
        
        ultimo = self.db.get("clima:ultimo")
        if ultimo is not None:
            self._memoria = ultimo
            return ultimo

        return {
            "configurado": self.configurado,
            "origen": self.origen,
            "ciudad": self._ciudad,
            "actualizado": None,
            "error": self.error,
            "actual": None,
            "hoy": None,
            "dias": []
        }
