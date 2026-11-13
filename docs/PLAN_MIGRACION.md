# Plan: PleyadesHome autosuficiente (cámaras + red) y camino a app móvil

Hoy panel-home **no mide nada**: lee a NetWatch (`:8765`), a gestorCamaras (`:8080`) y a go2rtc (`:1984`), y las
pestañas Cámaras y Red son iframes hacia esos proyectos. La meta es que este repo contenga **todo** (código,
configuración, despliegue y documentación), que los otros dos repos queden archivados y que el backend quede listo
para una app Android/iOS.

Fecha: 2026-11-13 · Rama de trabajo: `feature/integracion` (desde `develop`) · Bitácora: sigue en T45.

---

## 1. Qué se migra (inventario)

### NetWatch (`../analizadorRed/NetWhatch`, ~2 100 líneas Python, solo biblioteca estándar)

| Pieza | Origen | Destino en panel-home |
|---|---|---|
| Ping, DNS, ARP, ruta por defecto, fabricantes (OUI) | `network/ping.py dns.py discovery.py vendors.py`, `oui.txt` | `panel/red/` (`ping.py`, `dns.py`, `descubrimiento.py`, `fabricantes.py`), `data/oui.txt` |
| Caídas LAN/WAN/DNS cada 5 s | `monitors/connectivity.py` | `panel/red/conectividad.py` |
| Inventario de equipos cada 2 min | `monitors/inventory.py` | `panel/red/inventario.py` |
| Calidad por equipo cada 30 s | `monitors/device_quality.py` | `panel/red/calidad.py` |
| IP pública cada 5 min | `monitors/public_ip.py` | `panel/red/ip_publica.py` |
| Prueba de velocidad cada hora | `monitors/speed.py` | `panel/red/velocidad.py` |
| Retención 30 días | `monitors/retention.py` | `Db.podar` (ya existe, se amplía) |
| Planificador de tareas periódicas | `core/scheduler.py` | `panel/tareas.py` (también lo usarán luces/rutinas) |
| Resumen, eventos, CSV, escáner de puertos, alias | `services/*.py`, `web/api.py` | `panel/red/servicios.py` + rutas en `web.py` |
| Avisos Telegram de red | `alerts/telegram.py` | `panel/avisos.py` (uno solo para todo) |
| Tablas `devices probes events meta speed` | `netwatch.db` | `panel.db`: `equipos`, `sondeos`, `velocidad`; los eventos van a `eventos` y `meta` a `estado` |
| Dashboard (equipos, escáner, eventos, velocidad…) | `static/js/widgets/*.js` | Pestaña **Red** propia (sin iframe) |
| Pruebas | `tests/test_*.py` | `tests/test_red_*.py` |

### gestorCamaras (`../Camaras/gestorCamaras`)

| Pieza | Origen | Destino en panel-home |
|---|---|---|
| Registro de cámaras (`cameras.json`, alta/baja con PIN, validación de IP) | `panel/main.py` | `panel/camaras/registro.py`, tabla `camaras` en `panel.db` |
| Alta/baja de flujos en go2rtc (`PUT/DELETE /api/streams`) | `panel/main.py` | `panel/camaras/go2rtc.py` |
| Salud cada 10 s, caída tras 45 s, red vs. video | `panel/vigilante.py` | `panel/camaras/vigilante.py` |
| Bot de Telegram (`/estado /foto /eventos /ayuda`) | `panel/vigilante.py` | `panel/bot.py` (sumando comandos de red y luces) |
| PTZ ONVIF (mover, parar, autoparada 2 s) | `panel/main.py` con `onvif-zeep` | `panel/camaras/onvif.py` en **SOAP con biblioteca estándar** (WS-Security digest con `hashlib`) |
| Límite de sesiones de video (`MAX_SESIONES`) y proxy WebSocket del video | `panel/main.py` (FastAPI + `websockets`) | `panel/camaras/video.py`: proxy de bytes tras el *upgrade* (no hace falta entender las tramas) |
| Grabaciones: fotos y clips por día, borrar, exportar `.zip`, espacio | `panel/main.py` | `panel/camaras/grabaciones.py` (ya existe parte en `fuentes.py`) |
| Detector YOLO + clips + resumen cada 2 h | `detector/detector.py` (torch, opencv, ultralytics) | `detector/` **dentro de este repo**, contenedor aparte (ver decisión D2) |
| go2rtc (`go2rtc.yaml`, imagen `alexxit/go2rtc`) | `docker-compose.yml` | `go2rtc/go2rtc.yaml` + servicio en nuestro `docker-compose.yml` |
| UI: rejilla, flechas PTZ, zoom digital, agregar cámara, grabaciones | `static/index.html`, `grabaciones.html` | Pestañas **Cámaras** y **Capturas** propias (sin iframe) |
| Guía Windows/Raspberry Pi (PDF) | raíz del repo | `docs/DESPLIEGUE.md` (texto, no PDF) |

### Lo que sigue siendo externo (y por qué)

- **go2rtc**: es el servidor de video (RTSP → MSE/WebRTC/HLS). No se reimplementa; se vuelve **parte del despliegue
  de este repo** (su configuración y su contenedor viven aquí) y deja de estar expuesto: todo pasa por panel-home.
- **Modelo YOLO**: se descarga al construir la imagen del detector (o se guarda en `data/modelos/`).

---

## 2. Principios

1. **Estrangulamiento, no big-bang.** Cada pieza nueva se pone detrás de la misma función de `fuentes.py` que hoy
   lee por HTTP (`netwatch_resumen`, `camaras_lista`, `camaras_salud`…) y devuelve **la misma forma**. Un interruptor
   (`RED_INTERNA=1`, `CAMARAS_INTERNAS=1`) elige la fuente. Así el front no se rompe y se puede comparar en paralelo.
2. **Backend sin dependencias** (regla de ARQUITECTURA.md). Excepciones aceptadas: `tinytuya` (ya está) y el detector,
   que vive en su propio contenedor con sus propias dependencias.
3. **API primero.** Todo lo que haga la web se hace por `/api/...` JSON documentado: la app móvil usará lo mismo.
4. **Sin iframes ni puertos ajenos.** El navegador o la app solo hablan con panel-home (`:8770`).
5. **Un solo avisador y un solo bot.** Se acaban los avisos duplicados y `YA_AVISADOS`.
6. Flujo de siempre: micro tareas en `.md` → worker Gemini/Gemma → revisión de Claude; Telegram `PANEL-HOME` por paso;
   fila en `BITACORA.md`; pruebas al final de cada fase.

---

## 3. Decisiones que tomar antes de empezar (con recomendación)

| # | Decisión | Recomendación |
|---|---|---|
| D1 | **Dónde corre.** El escaneo de red necesita ver la LAN (ARP, MAC). En Docker Desktop (Windows/Mac) el contenedor está detrás de NAT y **no ve las MAC**; NetWatch por eso corre fuera de Docker. | Raspberry Pi / Linux con `network_mode: host` y `cap_add: NET_RAW`. Si se queda en la Lenovo con Windows: correr panel-home **nativo** (Python) y adaptar `ping`/`arp` a Windows (tarea T49), con go2rtc y el detector en Docker. |
| D2 | **Detector**: mantener PyTorch o pasar a ONNX. | Fase 5: mover tal cual (contenedor `detector/`). Después, tarea opcional: exportar YOLO a ONNX y usar `onnxruntime` (imagen de ~2 GB a ~300 MB). |
| D3 | **ONVIF**: reescribir en stdlib o aceptar `onvif-zeep`. | Reescribir: solo se usan `GetProfiles`, `ContinuousMove` y `Stop`; son 3 sobres SOAP. Si una cámara no responde igual, plan B: `onvif-zeep` en `requirements.txt`. |
| D4 | **Datos históricos**: importar `netwatch.db`, `cameras.json` y `eventos.log` o empezar en limpio. | Importar (script de una vez, T80). Las fotos/clips no se mueven: se monta la misma carpeta `data/`. |
| D5 | **Tecnología de la app móvil.** | PWA primero y luego **Capacitor** sobre el mismo front (reutiliza todo el HTML/JS). React Native o Flutter implicarían reescribir la interfaz. |
| D6 | **Acceso fuera de casa.** | Tailscale (ya recomendado) + `tailscale serve` para tener **HTTPS** con certificado válido (iOS lo exige). Nunca abrir puertos en el módem. |

---

## 4. Fases y micro tareas

Cada tarea: pocos archivos, criterio de aceptación verificable. "W" = worker Gemini/Gemma; "C" = Claude a mano.

### Fase 0 — Preparación (½ día)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T45 | Rama `feature/integracion`; copiar a `docs/origen/` las referencias que hoy se consultan fuera: README de NetWatch y gestorCamaras, contratos de API, `go2rtc.yaml`, guía de despliegue en texto. | C | Ningún documento de panel-home enlaza a `../` |
| T46 | Pruebas de referencia: correr las suites de los 3 proyectos y guardar el conteo en la bitácora. Grabar respuestas reales de `/api/summary`, `/api/camaras`, `/api/salud` en `tests/fixtures/` (comparación más adelante). | C | Fixtures guardados, conteo anotado |
| T47 | `panel/tareas.py`: planificador de tareas periódicas (port de `core/scheduler.py`) con hilo, intervalo, primer retraso y captura de errores. | W | Pruebas con reloj simulado |
| T48 | Ampliar `Config`: `RED_INTERNA`, `CAMARAS_INTERNAS`, `GO2RTC_INTERNO_URL`, `OUI_ARCHIVO`, `RED_SUBRED`, `ADMIN_PIN`, `MAX_SESIONES`, intervalos. Quitar el valor por defecto `ROOT.parent/"Camaras"/…` de `camaras_data` (pasa a `data/`). | W | `test_panel` sigue en verde |

### Fase 1 — Red nativa (backend) (3–4 días)

> **Decidido (2026-11-13): opción B — sonda + panel-home** (ver `docs/RED.md`). La sonda (`sonda/`) mide fuera de Docker y manda lecturas a `POST /api/interno/red`; panel-home aplica las reglas de NetWatch y arma el mismo resumen. Backend hecho (R1–R7); falta la pestaña Red propia (Fase 2) y desplegar la sonda en la .94.

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T49 | `panel/red/ping.py`, `dns.py`, `descubrimiento.py` (ruta por defecto, ARP, IP local) con variantes macOS / Linux / **Windows** (`ping -n`, `arp -a`). | W | Pruebas con salidas de comando grabadas de los 3 sistemas |
| T50 | `panel/red/fabricantes.py` + `data/oui.txt` (descarga la 1ª vez, tolerante sin internet). | W | Prueba con OUI de muestra |
| T51 | Esquema en `db.py`: tablas `equipos(mac, ip, hostname, alias, vendor, online, first_seen, last_seen, fallos)`, `sondeos(ts, destino, ok, ms)`, `velocidad(ts, down, up)`; métodos de lectura/escritura; podado a 30 días. | W | Pruebas de `Db` |
| T52 | `panel/red/conectividad.py`: LAN/WAN/DNS cada 5 s, 3 fallos para caída, detección de pausa (equipo suspendido → `monitor_gap`). Escribe eventos con la forma única de panel-home (`fuente: "red"`). | W | Pruebas portadas de `test_monitors.py` |
| T53 | `panel/red/inventario.py` + `calidad.py`: escaneo /24 + ARP, equipos nuevos/conectados/desconectados, latencia-jitter-pérdida por equipo, caídas 24 h. | W | Pruebas portadas |
| T54 | `panel/red/ip_publica.py` + `velocidad.py` (Cloudflare, bytes configurables). | W | Pruebas con servidor falso |
| T55 | `panel/red/servicios.py`: `resumen()` que devuelve **exactamente** la forma de `/api/summary` de NetWatch; consulta de eventos con filtros; CSV; escáner de un host (puertos TCP, TTL, DNS); alias. | W (en 2 tareas) | La salida pasa la comparación contra el fixture de T46 |
| T56 | Conectar: `fuentes.netwatch_resumen` usa `servicios.resumen()` si `RED_INTERNA=1`; `main.py` arranca las tareas de red. Rutas: `GET /api/red/eventos`, `GET /api/red/export.csv`, `POST /api/red/escanear`, `POST /api/red/alias`. | C | Panel funcionando con `RED_INTERNA=1` y NetWatch apagado |
| T57 | Pruebas de la fase: `tests/test_red_*.py` (portadas de NetWatch + nuevas). | W | Todas en verde |

### Fase 2 — Pestaña Red propia (front) (2 días)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T58 | `static/js/red/equipos.js`: tabla paginada (10/25/50), búsqueda, alias en línea, fabricante, calidad, última vez visto. | W | Funciona en celular y escritorio |
| T59 | `static/js/red/escaner.js` + `velocidad.js` (historial vs. contratado). | W | — |
| T60 | `static/js/red/eventos.js`: filtros por fecha y tipo, exportar CSV. | W | — |
| T61 | Quitar el iframe de la pestaña Red; CSS `red.css` con identidad Pléyades; mapa de la red sigue usando los mismos datos. | C | No queda ninguna referencia a `:8765` |

### Fase 3 — Cámaras nativas (backend) (4–5 días)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T62 | `panel/camaras/registro.py` + tabla `camaras` (id, nombre, ip, puerto RTSP, ruta, puerto ONVIF, usuario, clave). La clave nunca sale por la API. Validación de IP privada y ruta (port de `_validar_ip`, `RUTA_OK`). | W | Pruebas |
| T63 | `panel/camaras/go2rtc.py`: registrar/quitar flujos por la API de go2rtc, re-registro al arrancar, cámaras rechazadas sin reintento en bucle, `frame.jpeg`. | W | Prueba con go2rtc falso |
| T64 | `panel/camaras/vigilante.py`: salud cada 10 s (TCP + bytes recibidos en go2rtc), caída tras 45 s, red vs. video, go2rtc caído, cortes 24 h. Devuelve la forma de `/api/salud`. | W | Comparación con fixture de T46 |
| T65 | `panel/camaras/onvif.py`: `GetProfiles`, `ContinuousMove`, `Stop` en SOAP con WS-Security (stdlib), reconexión y autoparada 2 s. | C (sensible) | Probado con las 2 cámaras reales (.69 y .72) |
| T66 | `panel/camaras/video.py`: sesiones de video (abrir, latido, salir, caducan 60 s, máx. `MAX_SESIONES`) y **proxy WebSocket** `/api/camaras/video?src=` hacia go2rtc, protegido por la sesión de panel-home. | C | Video en vivo sin abrir `:1984` en el navegador |
| T67 | `panel/camaras/grabaciones.py`: listar días, fotos y clips; borrar selección/día (rol admin); exportar `.zip` en streaming; espacio. | W | Pruebas con carpeta temporal |
| T68 | Rutas en `web.py`: `GET/POST/DELETE /api/camaras`, `POST /api/camaras/<id>/mover|parar`, `/api/grabaciones/...`. `fuentes.camaras_lista/salud` internos con `CAMARAS_INTERNAS=1`. | C | Panel completo con gestorCamaras apagado |
| T69 | Pruebas de la fase (`tests/test_camaras_*.py`). | W | Verde |

### Fase 4 — Pestaña Cámaras propia (front) (2–3 días)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T70 | `static/js/video.js`: reproductor propio (MSE y, en iOS, `ManagedMediaSource`; WebRTC como respaldo) contra el proxy de T66; silencio por defecto. Sustituye los iframes de `stream.html` del Resumen. | C | Funciona en Chrome, Safari macOS e iPhone |
| T71 | `static/js/camaras.js`: rejilla, pantalla completa, flechas PTZ (mantener pulsado), zoom digital (rueda/pellizco), estado y latencia. | W | — |
| T72 | Alta y baja de cámaras (diálogo, PIN/rol admin). | W | — |
| T73 | Grabaciones dentro de **Capturas**: clips además de fotos, selección múltiple, borrar, descargar `.zip`. | W | — |
| T74 | Quitar iframe de Cámaras y toda referencia a `:8080` / `:1984` en el front. | C | `grep` limpio |

### Fase 5 — Detector, bot y avisos unificados (2–3 días)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T75 | Traer `detector/` (código, Dockerfile, requirements). Lee la lista de cámaras de `GET /api/interno/camaras` (token interno), guarda en `data/fotos` y `data/clips`; ya no manda Telegram. | C | Fotos nuevas aparecen en la línea de tiempo |
| T76 | El resumen de detecciones cada 2 h (silencio 23–7) pasa a `panel/avisos.py`. | W | Pruebas |
| T77 | `panel/bot.py`: un solo bot con `/estado` (red + cámaras + luces), `/foto [id]`, `/eventos`, `/luces`, `/ayuda`, solo responde al `TELEGRAM_CHAT_ID`. | W | Prueba con API de Telegram falsa |
| T78 | Avisos: borrar `YA_AVISADOS`; tipos por defecto = los que antes avisaban NetWatch + gestorCamaras; cola sin internet (ya existe). | C | Ningún aviso duplicado |

### Fase 6 — Despliegue único y corte (2 días + 1 semana en paralelo)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T79 | `docker-compose.yml` con 3 servicios: `panel-home` (host network si D1 = Linux), `go2rtc` (solo accesible desde panel-home; `8554` interno), `detector`. `.env.example` completo. | C | `docker compose up -d --build` levanta todo desde este repo |
| T80 | `scripts/migrar.py`: importa `netwatch.db` (equipos, alias, eventos, velocidad), `cameras.json` y `eventos.log`. Idempotente (usa `clave`). | W | Correrlo dos veces no duplica |
| T81 | `docs/DESPLIEGUE.md` (Windows, Raspberry Pi, Tailscale), README y ARQUITECTURA actualizados; bitácora. | C | — |
| T82 | **Semana en paralelo**: panel nuevo con `*_INTERNA=1` y servicios viejos encendidos sin Telegram; script que compara cada hora resumen y salud. | C | Sin diferencias relevantes 7 días |
| T83 | Corte: apagar NetWatch y gestorCamaras; quitar el código de lectura HTTP y los interruptores; archivar los dos repos en GitHub con un README que apunte aquí. | C | panel-home no lee nada fuera de su repo y de go2rtc |

### Fase 7 — Backend listo para móvil (3 días)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T84 | API versionada `/api/v1/...` (alias de las actuales), errores con forma única `{"error": {"codigo", "mensaje"}}`, paginación uniforme (`limite`, `cursor`). | W + C | Front migra a v1 |
| T85 | Autenticación para apps: `POST /api/v1/dispositivos` (usuario+contraseña → token de dispositivo), `Authorization: Bearer`, lista y revocación desde el menú de cuenta. La cookie sigue para la web. | C | Pruebas de auth |
| T86 | `docs/api/openapi.yaml` con todo el contrato + página `/docs`. | W | Valida con un linter OpenAPI |
| T87 | Avisos con canal abstracto (`telegram`, `ntfy`, `push`) listo para FCM/APNs. Tabla `suscripciones_push`. | W | — |
| T88 | HTTPS: guía `tailscale serve` y cabeceras (HSTS solo bajo HTTPS). Cookies `Secure` cuando corresponda. | C | Panel abre por `https://<equipo>.ts.net` |

### Fase 8 — PWA (1–2 días)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T89 | `manifest.webmanifest`, íconos Pléyades (192/512/maskable), color obsidiana, pantalla de inicio. | W | Lighthouse "instalable" |
| T90 | `service-worker.js`: cachea solo el cascarón (HTML/CSS/JS/íconos), nunca API ni video; página "sin conexión". | W | Abre sin red mostrando el aviso |
| T91 | `API_BASE` configurable en el front (hoy todo es relativo) para que la app apunte a la casa. | C | — |

### Fase 9 — App Android/iOS con Capacitor (1–2 semanas)

| T | Qué | Quién | Aceptación |
|---|---|---|---|
| T92 | Carpeta `movil/` con Capacitor; empaqueta `static/`; pantalla inicial "Conectar con la casa" (URL Tailscale + inicio de sesión → token de T85 en el almacén seguro). | C | Corre en emulador Android y simulador iOS |
| T93 | Video nativo: WebRTC por el proxy (latencia baja, funciona en iOS). | C | — |
| T94 | Notificaciones push (FCM para Android, APNs para iOS) conectadas al canal `push` de T87. | C | Llega un aviso de cámara caída |
| T95 | Desbloqueo con biometría (opcional), ícono y splash Pléyades con "familia Astreo · Santaella". | W | — |
| T96 | Publicación: cuentas de Google Play y Apple Developer, firma, políticas de privacidad (cámaras y red = datos sensibles). | Usuario + C | Builds de prueba (TestFlight / prueba interna) |

---

## 5. Estructura final del repo

```
main.py
panel/
  config.py db.py auth.py web.py avisos.py bot.py tareas.py eventos.py fuentes.py
  luces.py rutinas.py sistema.py
  red/        ping dns descubrimiento fabricantes conectividad inventario calidad ip_publica velocidad servicios
  camaras/    registro go2rtc vigilante onvif video grabaciones
detector/     detector.py Dockerfile requirements.txt
go2rtc/       go2rtc.yaml
static/       index.html, login.html, css/, js/ (red/, camaras.js, video.js…), manifest, service-worker
movil/        proyecto Capacitor (Android/iOS)
scripts/      migrar.py, llaves_smartlife.py
docs/         ARQUITECTURA, BITACORA, DESPLIEGUE, LUCES, PLAN_MIGRACION, api/openapi.yaml, origen/
tests/        + test_red_*, test_camaras_*, fixtures/
data/         panel.db, fotos/, clips/, oui.txt, devices.json (fuera de git)
docker-compose.yml  Dockerfile
```

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Docker en Windows no ve las MAC de la LAN | Decisión D1; en modo sin MAC, identificar equipos por IP + hostname y avisarlo en la UI |
| `ping` sin permisos en contenedor | `iputils-ping` en la imagen + `cap_add: NET_RAW` |
| ONVIF en stdlib no funciona con alguna cámara | Plan B: `onvif-zeep` como dependencia opcional |
| El proxy WebSocket en `http.server` bloquea hilos | Un hilo por conexión (ya es `ThreadingHTTPServer`) y `MAX_SESIONES` = 2–4 |
| iOS no tiene MSE clásico | `ManagedMediaSource` (iOS 17.1+) o WebRTC |
| Perder historial al cortar | T80 + semana en paralelo + respaldo de `netwatch.db` y `data/` antes del corte |
| Claves de cámaras en la base | `data/` fuera de git, la API nunca las devuelve; opcional cifrarlas con una llave en `.env` |
| Cupo diario de Gemini | Tareas cortas (< ~400 líneas de salida); si se agota, agente Claude según CLAUDE.md |

## 7. Orden y estimado

F0 → F1 → F2 → F3 → F4 → F5 → F6 son la migración (≈ 3–4 semanas de trabajo con el flujo actual, más la semana en
paralelo). F7 → F8 → F9 son el camino a móvil y pueden empezar en cuanto termine F6 (F7 incluso antes, en paralelo con F4).
Cada fase termina con: pruebas en verde, fila en la bitácora, aviso `PANEL-HOME` y commit.
