# Arquitectura de panel-home (contrato entre módulos)

Python 3.9, **solo biblioteca estándar** (nada de pip). Usa `from __future__ import annotations`.
Todo el código, nombres y comentarios en español. Comentarios breves.

panel-home NO mide nada por sí mismo: lee dos sistemas que ya existen y los une.

- **NetWatch** (`NETWATCH_URL`, por defecto `http://127.0.0.1:8765`). `GET /api/summary` devuelve:
  `{"now", "checks", "ribbon_start", "ribbon": {"lan": [144 floats 0..1 o null], "wan": [...], "dns": [...]},
  "uptime": {"lan": %, "wan": %, "dns": %}, "series", "hours": [24 ints caídas por hora],
  "devices": [{"mac","ip","hostname","alias","vendor","online": 0|1,"first_seen","last_seen",
  "q": {"avg","jitter","loss"} o null, "drops": int}], "events": [{"ts","kind","detail"}] (últimos 60, más nuevo primero),
  "speed": [{"ts","down","up"}], "contracted", "public_ip"}`.
  Tipos (`kind`) de evento: `lan_down lan_up wan_down wan_up dns_down dns_up new_device ip_change ip_first
  device_online device_offline monitor_gap`.
- **gestorCamaras** (`CAMARAS_URL`, por defecto `http://127.0.0.1:8080`):
  `GET /api/camaras` -> `[{"id","nombre","ip",...}]`;
  `GET /api/salud` -> `{"go2rtc": bool, "camaras": {cid: {"nombre","ip","estado": "ok"|"sin_video"|"sin_red","desde": epoch,"latencia_ms","cortes_24h"}}}`.
  El detector guarda una foto por cada movimiento en `CAMARAS_DATA/fotos/AAAA-MM-DD/<cid>_<HH-MM-SS>_<clase1-clase2>.jpg`
  (ej. `camara1_08-19-01_carro.jpg`, `camara2_10-00-00_persona-perro.jpg`).
- **go2rtc** (`GO2RTC_URL`): el navegador muestra el video con `<iframe src="{go2rtc}/stream.html?src={cid}&mode=mse">`.

## Archivos

```
main.py                  arranca todo: python3 main.py [--host H] [--port P]
panel/__init__.py        vacío
panel/config.py          Config (dataclass) leída de variables de entorno
panel/db.py              SQLite: eventos, consumo, estado
panel/fuentes.py         lee NetWatch, cámaras, fotos de movimiento y consumo
panel/eventos.py         Recolector: convierte todo en eventos de la línea de tiempo
panel/avisos.py          Avisador: Telegram y ntfy (push)
panel/web.py             servidor HTTP + API JSON + archivos estáticos
static/index.html        página única
static/css/panel.css     estilos
static/js/hchart.js      librería de gráficos en HTML (sin canvas, sin SVG)
static/js/app.js         lógica del panel
```

## panel/config.py

```python
ROOT = Path(__file__).resolve().parent.parent   # raíz del proyecto
TIPOS_AVISO = frozenset({"movimiento", "fuente_caida", "fuente_ok"})  # YA_AVISADOS: lo que avisan NetWatch y gestorCamaras

@dataclass(frozen=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 8770
    db_path: Path = ROOT / "panel.db"
    netwatch_url: str = "http://127.0.0.1:8765"
    camaras_url: str = "http://127.0.0.1:8080"
    go2rtc_url: str = ""          # vacío: el navegador usa http://<host de la página>:1984
    camaras_data: Path = ROOT.parent / "Camaras" / "gestorCamaras" / "data"
    consumo_cmd: str = ""         # comando que imprime JSON {equipo: {"rx": bytes, "tx": bytes}}
    recolectar_cada: int = 15     # segundos entre ciclos
    telegram_token: str = ""
    telegram_chat_id: str = ""
    ntfy_url: str = ""            # ej. https://ntfy.sh/mi-tema-secreto
    avisar: FrozenSet[str] = TIPOS_AVISO

def cargar(env: Mapping[str, str] = os.environ) -> Config
```
Variables: `PANEL_HOST PANEL_PORT PANEL_DB NETWATCH_URL CAMARAS_URL GO2RTC_URL CAMARAS_DATA CONSUMO_CMD
RECOLECTAR_CADA TELEGRAM_TOKEN TELEGRAM_CHAT_ID NTFY_URL PANEL_AVISAR` (lista separada por comas).
URLs sin `/` final (quitarla con rstrip). Faltantes o vacías -> valor por defecto.

## Evento (dict) — forma única en todo el sistema

```python
{"id": int, "ts": int, "fuente": "red"|"camaras"|"panel", "tipo": str, "nivel": "alto"|"medio"|"bajo"|"info",
 "titulo": str, "detalle": str, "ref": str, "clave": str, "avisado": int}
```
`clave` es única (evita duplicados). `ref` es la foto (`AAAA-MM-DD/archivo.jpg`) en eventos de movimiento, si no `""`.
`avisado`: 0 pendiente, 1 enviado (o no se debe enviar).

## panel/db.py

```python
class Db:
    def __init__(self, path)                      # sqlite3 check_same_thread=False, threading.Lock, Row, WAL, crea esquema
    def agregar_evento(self, ev: dict) -> bool    # INSERT OR IGNORE por clave; True si era nuevo. ev puede traer "avisado" (def. 0)
    def eventos(self, desde=None, hasta=None, tipos=None, limite=200) -> list   # dicts, ts DESC
    def pendientes_aviso(self, tipos, limite=20) -> list   # avisado=0 y tipo en tipos, ts ASC
    def marcar_avisado(self, ids, valor=1) -> None
    def conteo_por_tipo(self, desde) -> dict      # {tipo: n}
    def guardar_consumo(self, ts, muestras) -> None   # muestras {equipo: (rx, tx)} contadores acumulados
    def consumo(self, horas=24, ahora=None) -> dict   # {equipo: {"rx": bytes, "tx": bytes, "serie": [horas ints]}}
    def podar(self, dias_eventos=90, dias_consumo=30, ahora=None) -> None
    def get(self, clave, defecto=None)            # valor guardado como JSON en tabla estado
    def set(self, clave, valor) -> None
```
Tablas: `eventos(id INTEGER PRIMARY KEY AUTOINCREMENT, ts, fuente, tipo, nivel, titulo, detalle, ref, clave TEXT UNIQUE, avisado INTEGER DEFAULT 0)`,
`consumo(ts INTEGER, equipo TEXT, rx INTEGER, tx INTEGER)`, `estado(clave TEXT PRIMARY KEY, valor TEXT)`.
Consumo: los contadores son acumulados; el uso entre dos muestras seguidas del mismo equipo es la diferencia;
si la diferencia es negativa (se reinició el router) se cuenta el valor nuevo completo.
`serie[i]` = bytes rx+tx en la hora i, donde i=0 es la más antigua de las `horas` y i=horas-1 la actual.

## panel/fuentes.py

```python
class FuenteError(Exception)
def get_json(url, timeout=5)                         # urllib; cualquier fallo -> FuenteError
def netwatch_resumen(cfg) -> dict | None             # /api/summary, None si falla
def camaras_lista(cfg) -> list | None                # /api/camaras
def camaras_salud(cfg) -> dict | None                # /api/salud
def fotos_movimiento(cfg, desde_ts, ahora=None) -> list   # [{"ts","camara","clases":[...],"ref"}] ts>desde_ts, ts ASC
def ruta_foto(cfg, ref) -> Path | None               # valida ref con ^\d{4}-\d\d-\d\d/[\w.-]+\.jpg$ y que exista
def leer_consumo(cfg) -> dict | None                 # {equipo: (rx, tx)} o None
```

## panel/eventos.py

```python
class Recolector:
    def __init__(self, cfg, db)
    ultimo: dict   # {"ts", "netwatch": dict|None, "camaras": list|None, "salud": dict|None}
    def ciclo(self, ahora=None) -> int   # nuevos eventos guardados
```

## panel/avisos.py

```python
class Avisador:
    def __init__(self, cfg, db)
    activo: bool (property)            # hay Telegram o ntfy
    def texto(self, ev) -> str
    def enviar_pendientes(self) -> int # cuántos se enviaron
```

## API web (panel/web.py)

- `GET /` -> static/index.html; `GET /static/...` -> archivos de static/ (sin salir de la carpeta)
- `GET /api/panel` -> estado completo para la página (ver web.py)
- `GET /api/eventos?desde=&hasta=&tipos=a,b&limite=` -> `{"eventos": [...]}`
- `GET /api/foto?ref=AAAA-MM-DD/x.jpg` -> la foto JPEG

## Agregado: pestañas y capturas

- `Config.fotos_remotas` (`FOTOS_REMOTAS`): las fotos se leen de gestorCamaras por HTTP en vez del disco.
- fuentes: `capturas_del_dia(cfg, dia)`, `dias_con_capturas(cfg)`, `leer_foto(cfg, ref) -> bytes` (local o remota).
- gestorCamaras: `GET /api/fotos/dias`, `GET /api/fotos?fecha=`, `GET /api/fotos/{fecha}/{archivo}`.
- web: `GET /api/capturas?fecha=` y `/api/panel` incluye `camaras_url` y `netwatch_url` para las pestañas.
- static: `pestanas.js` (hash #resumen #capturas #camaras #red) y `capturas.js` (galería).

## Agregado: almacenamiento

- gestorCamaras `GET /api/espacio` → `{total, usado, libre, fotos:{bytes,archivos,dias}, clips:{bytes,archivos,dias}, ts}` (caché 60 s).
- `fuentes.camaras_espacio(cfg)`: por HTTP si `FOTOS_REMOTAS=1`, si no mide `CAMARAS_DATA`. El recolector lo lee cada 5 min en `ultimo["espacio"]`; `/api/panel` lo devuelve como `espacio`.
- `app.js` emite el evento `panel` con los datos; `espacio.js` pinta la tarjeta.
