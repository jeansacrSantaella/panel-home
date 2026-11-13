# Referencias de origen (copiadas para no consultar fuera)

Copias de los proyectos que panel-home está absorbiendo (ver `docs/PLAN_MIGRACION.md`).
Son de solo lectura: sirven de contrato y referencia durante la migración.

| Carpeta | Proyecto | Commit copiado |
|---|---|---|
| `gestorCamaras/` | `Camaras/gestorCamaras` (FastAPI + go2rtc + detector YOLO) | `3e982ce` (2026-11-06) |
| `netwatch/` | `analizadorRed/NetWhatch` (monitor de red, stdlib) | `9f55249` (2026-10-31) |

- `gestorCamaras/README.md`, `docker-compose.yml`, `go2rtc.yaml`, `env.example` (sin secretos) y la guía de despliegue en PDF.
- `netwatch/README.md` y `docs-api.html` (la documentación técnica que NetWatch sirve en `/docs`).

## Contrato HTTP de gestorCamaras (`panel/main.py`)

| Método y ruta | Qué hace |
|---|---|
| `GET /api/camaras` | lista pública `[{id, nombre, ip, …}]` (sin usuario ni clave) |
| `POST /api/camaras` | alta `{nombre, ip, puerto_rtsp, ruta, puerto_onvif, usuario, clave}`; cabecera `X-Admin` = `ADMIN_PIN` si está configurado |
| `DELETE /api/camaras/{cid}` | baja (con `X-Admin`) |
| `GET /api/salud` | `{"go2rtc": bool, "camaras": {cid: {nombre, ip, estado: ok\|sin_video\|sin_red, desde, latencia_ms, cortes_24h}}}` |
| `GET /api/config/estado` | si pide PIN |
| `POST /api/sesion` · `POST /api/sesion/{sid}/latido` · `POST /api/sesion/{sid}/salir` | sesiones de video (máx. `MAX_SESIONES`, caducan a los `SESION_CADUCA` s) |
| `WS /api/ws?src=&sesion=` | proxy del WebSocket de go2rtc (MSE/WebRTC) |
| `GET /go2rtc/{video-stream.js,video-rtc.js}` | scripts del reproductor de go2rtc (en caché) |
| `POST /api/{cid}/mover` `{x, y}` (cabecera `X-Sesion`) · `POST /api/{cid}/parar` | PTZ ONVIF `ContinuousMove` / `Stop`; autoparada a los 2 s |
| `GET /api/fotos/dias` · `GET /api/fotos?fecha=` · `GET /api/fotos/{fecha}/{archivo}.jpg` | capturas del detector |
| `GET /api/clips?fecha=` · `GET /api/clips/{fecha}/{archivo}.mp4` | clips (persona) |
| `POST /api/grabaciones/borrar` · `DELETE /api/grabaciones/dia/{fecha}` | borrar (con `X-Admin`) |
| `POST /api/grabaciones/exportar` · `GET /api/grabaciones/exportar/{fecha}` | `.zip` |
| `GET /api/espacio` | disco y bytes de fotos/clips (caché 60 s) |

Archivos en `data/`: `cameras.json`, `eventos.log`, `fotos/AAAA-MM-DD/<cid>_<HH-MM-SS>_<clases>.jpg`,
`clips/AAAA-MM-DD/<cid>_<HH-MM-SS>.mp4`.
