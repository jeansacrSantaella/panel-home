# Cámaras dentro de panel-home (contrato)

Reemplaza a gestorCamaras (código de referencia en `docs/origen/gestorCamaras/codigo/`). Se activa con
`CAMARAS_INTERNAS=1`; mientras tanto el panel sigue leyendo gestorCamaras por HTTP. go2rtc sigue siendo un
servicio aparte (video), pero **solo panel-home habla con él**: el navegador nunca abre `:1984`.

## Módulos (`panel/camaras/`)

| Archivo | Clase / función | Estado |
|---|---|---|
| `registro.py` | `Registro(db, max_camaras, iniciales)`: `lista()`, `publicas()`, `una(cid)`, `agregar(...)`, `quitar(cid)`, `importar_json(ruta)`; `fuente_rtsp(c)`, `publica(c)`, `CamaraError(mensaje, codigo)` | hecho |
| `go2rtc.py` | `Go2rtc(url)`: `streams()`, `registrar()`, `quitar()`, `foto(cid)`, `script(nombre)`; `Sincronizador(go2rtc, obtener, fuente)`: `vuelta()`, `registrar_ya(c)`, `olvidar(cid)` | hecho |
| `vigilante.py` | `Vigilante(obtener, go2rtc, caida_tras, cada, al_evento)`: `vuelta()`, `salud()` | hecho |
| `grabaciones.py` | `Grabaciones(data)`: `dias()`, `fotos(f)`, `clips(f)`, `ruta(tipo, f, a)`, `tipo_mime(tipo)`, `resolver(fotos, clips)`, `borrar(...)`, `borrar_dia(f)`, `pares_dia(f)`, `escribir_zip(pares, salida)`, `nombre_zip()`; `GrabacionError(mensaje, codigo)` | hecho |
| `onvif.py` | ver abajo | nuevo |
| `video.py` | ver abajo | nuevo |
| `servicio.py` | `Camaras` (fachada) | nuevo |

### `onvif.py` (PTZ sin dependencias: SOAP + WS-Security con hashlib)
```python
class OnvifError(Exception)
class Onvif:
    def __init__(self, ip, puerto=8899, usuario="", clave="", timeout=5.0, abrir=None)  # abrir(Request, timeout) -> resp (inyectable)
    def perfil(self) -> str                       # GetProfiles (servicio media) -> token del primer perfil (en caché)
    def mover(self, x: float, y: float, zoom: float = 0.0) -> None   # ContinuousMove, valores -1..1
    def parar(self) -> None                       # Stop PanTilt y Zoom
class ControlPTZ:
    def __init__(self, obtener_camara, timeout=5.0, autoparada=2.0, fabrica=Onvif)   # obtener_camara(cid) -> dict completo (ip, puerto_onvif, usuario, clave)
    def mover(self, cid, x, y) -> None            # reintenta una vez reconectando; programa parada automática a los `autoparada` s
    def parar(self, cid) -> None
    def olvidar(self, cid) -> None                # al borrar o cambiar una cámara
```

### `video.py` (sesiones de video y puente WebSocket hacia go2rtc)
```python
class SinLugar(Exception)                         # .info = lista de sesiones abiertas (para mostrar "hay N viendo")
class Sesiones:
    def __init__(self, maximo=2, caduca=60, reloj=time.time)
    def abrir(self) -> dict                       # {"id": sid, "maximo": n}; si no hay lugar -> SinLugar
    def latido(self, sid) -> str                  # "ok" | "expulsada" (caducó o no existe)
    def salir(self, sid) -> None
    def valida(self, sid) -> bool
def puente_websocket(handler, go2rtc_url: str, src: str, timeout=10.0) -> None
    # handler = BaseHTTPRequestHandler que recibió "GET /api/camaras/video?src=..&sesion=.." con Upgrade: websocket.
    # Abre TCP a host:puerto de go2rtc, reenvía la petición de upgrade a /api/ws?src=<src> (mismas cabeceras
    # Sec-WebSocket-*), devuelve la respuesta 101 al cliente y copia bytes en ambos sentidos (dos hilos) hasta que
    # uno cierre. No interpreta tramas. Si go2rtc no responde -> 502 normal.
```

### `servicio.py`
```python
class Camaras:
    def __init__(self, cfg, db, al_evento=None)   # arma Registro, Go2rtc(cfg.go2rtc_interno_url), Sincronizador, Vigilante,
                                                  # Grabaciones(cfg.camaras_data), ControlPTZ, Sesiones(cfg.max_sesiones, cfg.sesion_caduca)
    registro, go2rtc, sincronizador, vigilante, grabaciones, ptz, sesiones   # atributos públicos
    def tareas(self) -> list                      # sincronizar cada 10 s, vigilar cada cfg.vigilar_cada
    def lista(self) -> list ; def salud(self) -> dict ; def espacio(self) -> dict
    def agregar(self, datos: dict) -> dict ; def quitar(self, cid) -> None     # mantienen go2rtc y PTZ al día
    def exigir_admin(self, pin: str) -> None      # CamaraError 401 si cfg.admin_pin y no coincide (compare_digest)
```

## Rutas (todas con sesión del panel, salvo `/api/interno/camaras`)

| Ruta | Qué |
|---|---|
| `GET /api/camaras` | `publicas()` |
| `POST /api/camaras` | alta `{ips, nombre, puerto_rtsp, ruta_rtsp, puerto_onvif, usuario, clave}`, cabecera `X-Admin` |
| `DELETE /api/camaras/<cid>` | baja, `X-Admin` (se acepta también `POST /api/camaras/<cid>/borrar`) |
| `GET /api/camaras/salud` | `salud()` |
| `GET /api/camaras/config` | `{"protegido": bool, "maximo_sesiones": n}` |
| `POST /api/camaras/sesion` · `POST /api/camaras/sesion/<sid>/latido` · `POST /api/camaras/sesion/<sid>/salir` | sesiones de video (409 + lista si no hay lugar) |
| `GET /api/camaras/video?src=&sesion=` | WebSocket hacia go2rtc (`puente_websocket`); sesión inválida -> 403 |
| `GET /api/camaras/go2rtc/<video-stream.js|video-rtc.js>` | scripts del reproductor de go2rtc |
| `GET /api/camaras/<cid>/foto` | JPEG actual de go2rtc |
| `POST /api/camaras/<cid>/mover {x, y}` (cabecera `X-Sesion` válida) · `POST /api/camaras/<cid>/parar` | PTZ |
| `GET /api/grabaciones/dias` · `GET /api/grabaciones?fecha=` -> `{fotos, clips}` | listas |
| `GET /api/grabaciones/<fotos|clips>/<fecha>/<archivo>` | archivo (clips con soporte de `Range` para el `<video>`) |
| `POST /api/grabaciones/borrar {fotos, clips}` · `POST /api/grabaciones/borrar-dia {fecha}` | `X-Admin` |
| `POST /api/grabaciones/exportar {fotos, clips}` · `GET /api/grabaciones/exportar/<fecha>` | `.zip` en streaming |
| `GET /api/interno/camaras` | para el detector: lista completa SIN claves, con `Authorization: Bearer <INTERNO_TOKEN>` |

Con `CAMARAS_INTERNAS=1` el recolector usa `lista()`/`salud()`/`espacio()` y las capturas se leen de `cfg.camaras_data`;
los eventos del vigilante (`camara_caida`, `camara_volvio`, `go2rtc_sin_respuesta`, `go2rtc_volvio`, `servidor_suspendido`)
entran a la línea de tiempo y se avisan (se agregan a `avisar` por defecto, como la red).

## Modo de transición con `GO2RTC_URL` (sin cámaras internas)

Con `CAMARAS_INTERNAS=0` y `GO2RTC_URL` definido, `/api/panel` trae `camaras_puente: true` y el video de Inicio y
Resumen pasa por el panel, no por un iframe de go2rtc. Así el botón 🔇/🔊 del reproductor controla el audio, cosa que un
iframe de otro origen no permite.
- `GET /api/camaras/go2rtc/video-stream.js` y `video-rtc.js` se piden al go2rtc de `GO2RTC_URL`.
- `GET /api/camaras/video?src=` (WebSocket) se conecta a ese go2rtc **sin sesión de video**. Solo acepta fuentes
  que go2rtc ya conoce (`/api/streams`, la lista se refresca cada 60 s); otra fuente → 404.
- Sin `GO2RTC_URL` se queda el iframe a `stream.html`, que no tiene control de audio.

Todos los videos arrancan en silencio; el audio se activa con un toque en 🔇.

## Detector (`detector/`, contenedor aparte)

Igual que el de gestorCamaras pero: lee las cámaras de `GET {PANEL_URL}/api/interno/camaras` con `INTERNO_TOKEN`,
guarda en `/data/fotos` y `/data/clips` (misma carpeta `data/` del panel), y **no manda Telegram**: el resumen cada
2 h (silencio de 23 a 7) lo manda panel-home (`panel/resumen_detecciones.py`).
