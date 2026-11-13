# Bitácora

Una línea por paso: qué se hizo y quién lo hizo.

## 2026-11-05 — Panel unificado + alertas

| Paso | Qué | Quién |
|---|---|---|
| 0 | Contrato entre módulos en `docs/ARQUITECTURA.md`. panel-home lee NetWatch y gestorCamaras, no mide nada propio. | Claude |
| T02 | `panel/db.py`: SQLite con eventos (clave única), consumo (contadores acumulados) y estado clave/valor. | Claude |
| T01 | `panel/config.py`: configuración por variables de entorno (ver `.env.example`). | Gemini, revisado por Claude |
| T03 | `panel/fuentes.py`: lee NetWatch, gestorCamaras, fotos de movimiento del detector y el comando de consumo. | Gemini, revisado por Claude |
| T04 | `panel/eventos.py`: cada 15 s convierte todo en eventos con clave única; el primer arranque no avisa el historial. | Claude |
| T05 | `panel/avisos.py`: envía por Telegram (con foto si es movimiento) y ntfy; si no hay internet reintenta después. | Gemini, revisado por Claude |
| T06 | `panel/web.py`: `/api/panel`, `/api/eventos`, `/api/foto` y archivos estáticos. | Claude |
| T07 | `main.py` y `.env.example`: hilo de recolección + avisos y servidor web. | Claude |
| T09 | `static/index.html` y `static/css/panel.css`: tarjetas de cámaras, mapa, caídas, consumo y línea de tiempo. | Claude |
| T08 | `static/js/hchart.js`: librería de gráficos solo con HTML/CSS (barras, columnas, cinta, dona, chispa, mapa radial). Claude corrigió especificidad de colores, hueco de la dona y fuga del ResizeObserver. | Gemini, revisado por Claude |
| T10 | `static/js/app.js` + `static/js/linea.js`. El primer intento de Gemini se cortó por largo; se dividió en T10a (tarjetas) y T10b (línea de tiempo, notificaciones del navegador). Claude corrigió la rejilla de cintas y latencias nulas. | Gemini, revisado por Claude |
| Prueba de humo | Servidor contra NetWatch y cámaras simulados + captura en Chrome. Se corrigieron cintas (separación y alto). | Claude |
| T11 | `tests/test_panel.py`: 6 pruebas (53 aserciones) de config, db, fuentes, eventos, avisos y web. `python3 -m unittest` → OK. | Gemini, revisado por Claude |

### Pendiente
- Configurar `CONSUMO_CMD` con el router real (ver README) para ver consumo por dispositivo.
- Decidir si se apagan los avisos propios de NetWatch y gestorCamaras para no recibir duplicados.
| Ajuste | Sin avisos duplicados: por defecto solo se avisa movimiento y "fuente no responde"; lo demás ya lo mandan NetWatch y gestorCamaras (`YA_AVISADOS` en config.py). | Claude |
| Configuración | `.env` apunta a NetWatch, cámaras y go2rtc en 192.168.1.94. Probado con datos reales: video, 30 equipos y eventos OK. Las fotos de movimiento solo se ven si panel-home corre en la .94. | Claude |
| Telegram | `.env` usa el mismo bot que gestorCamaras; mensaje de prueba enviado. | Claude |
| Arreglo | `main.py` lee `.env` solo (antes había que exportarlo y el panel arrancaba vacío). Al iniciar muestra a qué NetWatch/Cámaras/go2rtc se conecta. | Claude |

## 2026-11-05 — Pestañas y capturas del día

| Paso | Qué | Quién |
|---|---|---|
| T12 | gestorCamaras: rutas de solo lectura `/api/fotos/dias`, `/api/fotos?fecha=`, `/api/fotos/{fecha}/{archivo}`. Falta desplegar en la .94. | Claude |
| T13 | `fuentes.py`: capturas locales o por HTTP (`FOTOS_REMOTAS=1`), `capturas_del_dia`, `dias_con_capturas`, `leer_foto`. | Gemini, revisado por Claude |
| T14 | `static/js/capturas.js`: galería por día y cámara, agrupada por hora, se recarga cada minuto si es hoy. | Gemini, revisado por Claude |
| T15 | Pestañas Resumen / Capturas / Cámaras (:8080) / Red (:8765); `/api/capturas`; avisos de Telegram con foto remota. El iframe de cámaras se cierra al salir para liberar sesión. | Claude |
| T16 | `tests/test_capturas.py`: 7 pruebas nuevas. Total 13/13 OK. | Gemini, revisado por Claude |
| T17 | Visor tipo carrusel (`static/js/visor.js`): flechas ‹ ›, teclado ← →, deslizar con el dedo, contador "2 / 5". En Capturas recorre las fotos del día/cámara filtrada; en la línea de tiempo, las fotos visibles. | Gemini (visor.js), Claude (HTML/CSS y llamadas) |
| T18 | Docker: `Dockerfile`, `docker-compose.yml` (puerto 8770, base en `data/`), `.dockerignore`; guía en README. Probado en contenedor contra la .94: healthy. | Gemini, revisado por Claude |
| T19 | gestorCamaras: `GET /api/espacio` (disco libre, bytes y archivos de fotos y clips; caché 60 s). Falta desplegar en la Lenovo. | Gemini, revisado por Claude |
| T20 | `static/js/espacio.js`: tarjeta "Almacenamiento de grabaciones" (KPIs, dona, barra; ámbar < 20 % libre, rojo < 10 %). | Gemini, revisado por Claude |
| T21 | `fuentes.camaras_espacio` (remoto o local), recolector cada 5 min, `espacio` en `/api/panel`, evento `panel` en app.js. | Claude |
| T22 | `static/js/hchart-calor.js`: `HChart.calor`, mapa de calor en HTML/CSS. | Gemini, revisado por Claude |
| T23 | `static/js/calor.js` + `Db.calor_movimiento`: movimiento por día y hora, 4 semanas. | Gemini + Claude |
| T24 | `panel/sistema.py`: CPU, RAM, carga, encendido, temperatura y contenedores por el socket de Docker. Corregido: "Restarting" contaba como "starting". | Gemini, revisado por Claude |
| T25 | `static/js/sistema.js`: tarjeta Servidor; eventos `contenedor_caido`/`contenedor_ok` (tras 2 lecturas, se avisan); socket montado en compose. | Gemini + Claude |
| Nota | Avisos de movimiento: ya estaban apagados (solo los resúmenes del detector). Consumo (Sercomm FG6122TM): sin API ni SNMP; pendiente revisar su web con usuario. | Claude |
| T26 | Tarjeta de consumo renombrada a "Calidad por dispositivo" mientras no haya `CONSUMO_CMD` (el módem Telmex no da bytes por equipo). | Claude |
| Nota | Módem Telmex: la página "Estado WAN" tiene bytes Rx/Tx totales (consumo de la casa), pero el login es HMAC, los datos vienen cifrados con SJCL/AES y solo admite una sesión. Se deja sin integrar por ahora. | Claude |
| T27 | Rediseño UI/UX de `panel.css`: tokens claro/oscuro, cabecera translúcida, rejilla 1/2/3 columnas (línea de tiempo lateral en escritorio), barra de pestañas inferior en móvil, visor a pantalla completa en móvil, foco visible y objetivos táctiles. Arreglo: sin backdrop-filter en móvil (atrapaba la barra fija). | Gemini, revisado por Claude |
| T28 | `static/js/tema.js` + script en `<head>`: tema automático / claro / oscuro guardado en el navegador, sin parpadeo; mide cabecera y barra para los iframes. HTML con íconos SVG en pestañas. | Gemini + Claude |
| T29 | `static/css/orion.css`: identidad Orión (obsidiana, degradado violeta→azul→cian), cielo de estrellas en oscuro, marca OrionHome · Santaella, estrellitas en títulos, indicadores de carga. | Gemini, revisado por Claude |
| T30 | `static/js/carga.js`: pantalla de inicio con Orión dibujándose (completa la 1ª vez de la sesión, rápida al recargar; sale al llegar datos, clic o tecla); `OrionCarga.en()` para la galería; tarjetas en espera con el cinturón. Logos `static/img/orionhome.svg` (de OrionGit) y `orion-marca.svg`. | Gemini + Claude |
| T31 | `panel/auth.py`: admin/1234 inicial con cambio obligatorio, PBKDF2-SHA256, sesiones por cookie (hash del token), bloqueo por IP, `--restablecer-admin`. Gemini agotó su cuota diaria: lo escribió Claude. | Claude |
| T32 | `static/login.html` + `static/js/login.js`: entrada con identidad Orión y paso para cambiar la contraseña de fábrica (o "Más tarde"). | Claude (HTML), Gemini (JS) |
| T33 | `static/js/cuenta.js`: menú de cuenta, recordatorio fijo hasta cambiar la contraseña, diálogo de cambio, salida a /login si la sesión vence. Arreglo: el logout no mandaba JSON. | Gemini, revisado por Claude |
| T34 | `static/css/cuenta.css`; servidor: rutas protegidas, POST solo JSON del mismo origen, cabeceras de seguridad, sin versión de Python. `tests/test_auth.py` (7 pruebas). Total 20/20 OK. | Gemini + Claude |
| T35 | Cámaras en silencio: los iframes de go2rtc (Resumen) y de gestorCamaras (pestaña Cámaras) ya no delegan `autoplay`; el navegador solo permite arrancar mudo y go2rtc cae a `muted` solo (se puede subir el volumen a mano). | Claude |
| T36 | Identidad Pléyades: el proyecto pasa a **PleyadesHome** (familia OrionGit · Santaella). Logos `static/img/pleyades.svg` y `pleyades-marca.svg` con posiciones reales de M45 (Alcyone = la casa, nebulosa azul de reflexión); pantalla de inicio redibujada; se quitaron los SVG de Orión. | Claude |
| T37 | Familia de marca: "Astreo" (engloba OrionGit, PleyadesHome y los proyectos futuros con constelación) en el pie, la entrada, los SVG y el README. | Claude |
| T38 | Astreo fuera de este repo: sección en `~/.claude/CLAUDE.md` global; OrionGit (client-git) firma "familia Astreo · Santaella" en Acerca de, pantalla de inicio y copyright. 144/144 pruebas de OrionGit OK y recompilado con Tauri. | Claude |
| T39 | "Acerca de PleyadesHome" (menú de cuenta y pie): pestañas Información (versión, familia Astreo, servicios conectados en vivo, datos del panel), Tecnología (todo lo que usa) y Licencias; `GET /api/acerca`; `VERSION = 1.0.0`. Arreglos: `<dialog>` sin escapar en el texto rompía la ventana; hueco en el título. | Gemini (JS, CSS) + Claude |
| T40 | Luces Tuya: `panel/luces.py` (control local con tinytuya 1.20, sondeo en paralelo, IP por MAC, llaves nunca en logs), rutas `/api/luces`, tarjeta `luces.js` + `luces.css`, filtro Luces, nombres en el mapa, Docker con `requirements.txt`, guía `docs/LUCES.md`, 4 pruebas con foco simulado. Gemini solo logró `luces.css`; `luces.py` y `luces.js` los escribió Claude tras fallar dos veces el worker. Pendiente: probar con los focos reales cuando exista `data/devices.json`. | Claude + Gemini |
| T41 | Llaves de los focos sin plataforma de desarrollador: `scripts/llaves_smartlife.py` (inicio de sesión por QR con la cuenta de Smart Life, vía oficial de la integración Tuya de Home Assistant; cruza IPs del escaneo local; no guarda tokens). 6 dispositivos: 5 focos con llave y un enchufe. Prueba real: Cuarto, Descanso, Trabajito y Trabajo responden; Baño fuera de la red (apagado del interruptor). Se borraron las credenciales de iot.tuya.com. | Claude |
| T42 | Rutinas de luces: `panel/rutinas.py` (validación, ejecución en paralelo, reloj de horarios sin repetir), rutas `/api/rutinas`, `rutinas.js` (Gemini) + `rutinas.css` (Claude, el worker se atoró), 4 pruebas. Prueba real: rutina con 4 focos → 4 de 4. Arreglo: Ejecutar/Borrar mandaban POST sin JSON. | Claude + Gemini |
| T43 | Luces en dos niveles: tarjeta del Resumen compacta (punto de color, nombre e interruptor, "Ver todo →") y pestaña nueva **Luces** con detalle por foco (brillo, blanco, color), estado de conexión (Conectado / Sin respuesta, IP, "contestó hace…", motivo) y las rutinas. Barra inferior del celular con 5 pestañas. | Claude |
| T44 | Menú responsivo: en el celular, botón ☰ que abre un menú vertical deslizante (marca, 5 secciones con ícono, se cierra con ✕, fondo, Escape o al elegir; `inert` cuando está cerrado) y la sección actual bajo la marca; se quitó la barra inferior. Tableta: chips en su propia fila. Campana 🔔 compacta en el celular. Arreglos: ☰ visible en escritorio y fondo oscuro encima del menú. | Claude |

## 2026-11-13 — Plan de migración (cámaras + red) y camino a móvil

| Paso | Qué | Quién |
|---|---|---|
| Plan | `docs/PLAN_MIGRACION.md`: inventario de NetWatch y gestorCamaras, decisiones D1–D6, fases 0–9 (T45–T96) hasta app Android/iOS con Capacitor. | Claude |

## 2026-11-13 — Fase 0 de la migración (rama `feature/integracion`)

| Paso | Qué | Quién |
|---|---|---|
| T45 | `docs/origen/`: README, compose, go2rtc.yaml, env.example (sin secretos), guía PDF y código de referencia de gestorCamaras; README y docs técnicos de NetWatch; contrato HTTP de gestorCamaras en `docs/origen/README.md`. | Claude |
| T46 | `tests/fixtures/camaras/`: respuestas reales de gestorCamaras en la .94 (`camaras`, `salud`, `espacio`, `fotos_dias`, `fotos_dia`, `clips_dia`, `config_estado`). Las de NetWatch se posponen con la revisión de red. | Claude |
| T47 | `panel/tareas.py`: `Tarea`, `Planificador` (un hilo por tarea, sobrevive a errores, `detener()`), `cada()`. | Gemini 3.5 flash-lite, revisado por Claude |
| T48 | `Config`: `CAMARAS_INTERNAS`, `GO2RTC_INTERNO_URL`, `ADMIN_PIN`, `MAX_CAMARAS`, `MAX_SESIONES`, `SESION_CADUCA`, `VIGILAR_CADA`, `CAIDA_TRAS`, `ONVIF_TIMEOUT`, `CAMARAS`; `camaras_data` por defecto `data/`; helpers `_entero/_decimal/_booleano`. | Gemini 3.5 flash-lite, revisado por Claude |
| Nota | Red (NetWatch) queda **en revisión a detalle** antes de migrar; se sigue con cámaras. Las IPs reales de las cámaras hoy son .74 y .76. | Claude |

## 2026-11-13 — Fase 3 (cámaras, backend) — módulos sueltos, aún sin conectar

| Paso | Qué | Quién |
|---|---|---|
| T62 | `panel/camaras/registro.py`: tabla `camaras` en panel.db, alta/baja con validación (IP local, ruta, puertos, límite todo-o-nada), `publica()` sin clave, `fuente_rtsp`, siembra con `CAMARAS`, `importar_json` (cameras.json conservando ids). 13 pruebas. | Gemini falló (código 3, sin archivos) → agente Claude Haiku |
| T63 | `panel/camaras/go2rtc.py`: cliente urllib (streams, registrar+preload, quitar, foto, scripts en caché) y `Sincronizador`. Arreglo: distinguir "rechazada" (no se reintenta) de "sin conexión" (sí se reintenta); pruebas con go2rtc falso con estado. 5 pruebas. | Gemini 3.5 flash-lite, corregido por Claude |
| T64 | `panel/camaras/vigilante.py`: salud con la forma de `/api/salud`; eventos `camara_caida`/`camara_volvio`/`go2rtc_sin_respuesta`/`go2rtc_volvio`/`servidor_suspendido` con los tiempos de antes (45 s). Arreglo: go2rtc y pruebas TCP fuera del candado. 9 pruebas. | Agente Claude Sonnet, corregido por Claude |
| T67 | `panel/camaras/grabaciones.py`: días, fotos, clips, rutas seguras (no sale de data/), borrar, borrar día, `.zip` en streaming sobre un flujo sin seek. 15 pruebas. | Agente Claude Haiku |
| Pruebas | Suite completa: 80/80 OK (antes 20 + luces/rutinas). Arreglo en `test_tareas` (la especificación contaba mal las vueltas). | Claude |

## 2026-11-13 — Red sin NetWatch: opción B (sonda + panel-home)

| Paso | Qué | Quién |
|---|---|---|
| R0 | Diseño y contrato `docs/RED.md`: la sonda mide fuera de Docker (ARP/MAC), panel-home aplica reglas y arma el mismo `/api/summary`. Código de NetWatch copiado a `docs/origen/netwatch/codigo/`. | Claude |
| R1 | `sonda/`: mediciones macOS/Linux/Windows, lecturas, cola con tope, envío con token, `python3 -m sonda`. 19 pruebas; probada contra la red real en macOS (Windows solo con texto de ejemplo). | Agente Claude Sonnet |
| R2 | `panel/red/almacen.py` (`RedDb`): tablas `red_*` con las mismas consultas que NetWatch. 4 pruebas. | Gemini 3.5 flash |
| R3 | `panel/red/estado.py` (`EstadoRed`): caídas con 3 fallos, pausas, inventario, IP pública; estado de servicios persistente. 18 pruebas. | Agente Claude Sonnet |
| R4 | `fabricantes.py`, `resumen.py`, `consultas.py` y la fachada `servicio.py`. 16 pruebas. | Gemini (503/timeout) → agente Claude Sonnet |
| R5 | `panel/red/escaner.py`: puertos, ping, TTL, DNS desde panel-home. 17 pruebas. | Agente Claude Haiku |
| R6 | Integración: `RED_INTERNA`, `RED_TOKEN`, `OUI_ARCHIVO`; avisos de red los manda panel-home; recolector con `red`; rutas web; `main.py` con `Planificador`; Dockerfile (`sonda/`, `iputils-ping`); README y ARQUITECTURA. | Claude |
| R7 | `scripts/migrar_netwatch.py`: idempotente. Con la copia local de netwatch.db: 34 equipos, 519 eventos, 61 velocidades; 2ª corrida 0. 7 pruebas (arreglo: no cargar el .env real en la prueba). | Agente Haiku → Gemini 3.5 flash, revisado por Claude |
| Prueba | Panel + sonda real 50 s: token malo 401, lan/wan/dns 100 %, 14 equipos con calidad, IP pública, eventos, CSV, escáner del router (53/80/443), "Sonda de red" en Acerca de. Suite 161/161. | Claude |

## 2026-11-13 — Sonda nativa en Windows (la .94 solo corre Windows)

| Paso | Qué | Quién |
|---|---|---|
| W1 | `sonda/medir.py` para Windows en español/inglés: ping solo con `TTL=` (TTL expirado = fallo), `tiempo<1m`, decodificación OEM/cp850, `arp -a` con varias interfaces (vEthernet), `route print` con la ruta de menor métrica, IP local evitando adaptadores virtuales. 18 pruebas con salidas de ejemplo; verificado que en macOS sigue midiendo bien. | Agente Claude Sonnet |
| W2 | `sonda/__main__.py`: lee el `.env` del repo, panel por defecto `http://127.0.0.1:8770`, `--log` con rotación (con `pythonw` es la única salida). Arreglos: sin consola no truena, fecha en el log, `force=True`. Pruebas (8). | Gemini 3.5 flash-lite (código) + Claude (arreglos) + agente Haiku (pruebas, Gemini no las escribió) |
| W3 | `scripts/windows/instalar-sonda.ps1` (tarea programada "PleyadesHome Sonda": SYSTEM, al iniciar +1 min, reinicio cada minuto), `desinstalar-sonda.ps1`, `sonda.bat`, guía `docs/SONDA_WINDOWS.md`. Sin probar en Windows real. | Agente Claude Haiku |

## 2026-11-13 — Diseño de tablero (referencia del usuario, colores Astreo) y pestaña Red propia

| Paso | Qué | Quién |
|---|---|---|
| Diseño | `docs/DISENO.md`: estructura (lateral, ruta, buscador), clases genéricas y contrato de gráficas `HChart.anillo/progreso/bloques/area/anillos`. Memoria `diseno-tablero`. | Claude |
| D1 | `static/css/tablero.css` + cabecera de `index.html` + `menu.js`: lateral fija 232 px (íconos en 760–1023, ☰ la contrae), grupo SERVICIOS con puntos de estado, ruta "PANEL / SECCIÓN", buscador global → Red, campana y avatar. | Agente Claude Sonnet |
| D2 | `static/js/hchart-tablero.js` + `static/demo-tablero.html`. | Gemini (en corrección: anillos desbordan, área rota) |
| Red | `/api/red/resumen`; `static/js/red/nucleo.js` (Claude), `estado.js` + `velocidad.js` (Gemini flash-lite vía agente Haiku), `equipos.js` (Gemini flash-lite; arreglos de Claude: doble guardado del alias, datos en `detail.resumen`, clases), `escaner.js` (Gemini 3 flash preview), `eventos.js` + `red.css` (agente Haiku). Se quitó el iframe de NetWatch. | varios |
| Revisión | Capturas con Chrome headless (panel + sonda real) en escritorio, tableta y celular para revisar el diseño. | Claude |
| Arreglos | Gráficas: anillos dentro de su caja, área con relleno y línea continua (clip-path), bloques/progreso con degradado continuo (agente Sonnet, verificado con capturas). CSS: campos y selectores del tablero, rejilla de KPIs, nada desborda en celular, chips en la barra (agente Sonnet). Claude: equipos.js leía `detail` en vez de `detail.resumen` (tabla vacía), fabricante repetido, punto de estado invisible, tabla sin partir datos. | varios |
| Prueba | Capturas finales escritorio/tableta: lateral, ruta, anillos segmentados, progreso, tabla de 15 equipos reales, velocidad, eventos. Suite 187/187. | Claude |

## 2026-11-13 — Inicio tipo panel de pared + vidrio + clima + habitaciones

| Paso | Qué | Quién |
|---|---|---|
| Ajuste | Indicadores de estado (`#chips`) bajados de la barra superior a una franja en el cuerpo: ya no se cortan según el ancho. Chip "Sonda de red" con RED_INTERNA. | Claude |
| Diseño | Segunda referencia (glassmorphism, panel de casa): contrato "Piel de vidrio" y "Pestaña Inicio" en `docs/DISENO.md`; esqueleto de `#pestana-inicio` (portada), `static/js/inicio/nucleo.js`. | Claude |
| C1 | `panel/clima.py`: Open-Meteo sin llave (ciudad geocodificada una vez o lat/lon), actual + 4 días, último dato guardado; `CLIMA_CIUDAD/LAT/LON`; tarea cada 15 min; `GET /api/clima`. | Gemini 3.5 flash-lite |
| C2 | `panel/habitaciones.py`: habitación por foco (tabla `luz_habitacion`), resumen por habitación, aplicar a toda la habitación en paralelo; rutas `/api/luces/habitaciones`, `/api/luces/<id>/habitacion`, `/api/luces/habitacion`. 8 pruebas. | Gemini flash-lite vía agente Haiku (+ arreglo de validación) ; rutas: Claude |
| Inicio | `reloj.js` + `dock.js`, `clima.js`, `camara.js` (Gemini); `habitacion.js` (arco) + `habitaciones.js` (agente Sonnet); `atajos.js`, `agenda.js`, campo Habitación en Luces, fecha de capturas desde la agenda (Gemini vía agente Haiku). Endurecido `iconoClima`. | varios |
| Vidrio | `static/css/vidrio.css`: tokens de vidrio claro/oscuro, nebulosa de fondo, vidrio en tarjetas, barra, lateral, chips, diálogos y botones; sin desenfoque en celular. | Agente Claude Sonnet (verificado con capturas) |

## 2026-11-13 — Puntos 4 (diseño) y 5 (migración de cámaras) de una vez

| Paso | Qué | Quién |
|---|---|---|
| Contrato | `docs/CAMARAS.md`: módulos, fachada y rutas. Se quitó `static/demo-tablero.html` (era pública). | Claude |
| T65 | `panel/camaras/onvif.py`: PTZ por SOAP + WS-Security sin dependencias, `ControlPTZ` con reintento y autoparada. Prueba real de lectura: perfil `PROFILE_000` en .74 y .76. 13 pruebas. | Agente Claude Sonnet |
| T66 | `panel/camaras/video.py`: sesiones de video y puente WebSocket a go2rtc (copia de bytes). 7 pruebas; prueba real pendiente (la .94 no respondía). | Agente Claude Sonnet |
| T68 | `panel/camaras/servicio.py` + todas las rutas de cámaras, PTZ, video, sesiones, grabaciones (Range, zip en streaming) e interna para el detector; recolector y main con `CAMARAS_INTERNAS`; `INTERNO_TOKEN`; avisos de cámaras. Pruebas web. | Agente Claude Sonnet |
| Detector | `detector/` en el repo: cámaras desde `/api/interno/camaras`, sin Telegram; utilidades probadas sin torch. 8 pruebas. | Gemini flash-lite vía agente Haiku |
| Bot | `panel/telegram.py`, `panel/bot.py` (/estado /foto /eventos /hoy /luces /apagar /rutina /ayuda), `panel/resumen_detecciones.py` (cada 2 h, silencio 23–7); solo con CAMARAS_INTERNAS para no chocar con gestorCamaras. 11 pruebas. | Agente Claude Sonnet |
| Despliegue | `docker-compose.yml` (go2rtc interno + panel + detector con perfil `camaras`), `go2rtc/go2rtc.yaml`, `scripts/migrar_camaras.py`, `docs/DESPLIEGUE.md`. | Gemini flash-lite vía agente Haiku |
| Cámaras | Pestaña Cámaras propia (sin iframe): `static/js/camaras/reproductor.js` (sesión compartida, `<video-stream>` por el panel o iframe de respaldo), `camaras.js` (rejilla, PTZ, zoom digital, alta/baja con PIN), `camaras.css`; Inicio y Resumen usan el reproductor. | Agente Claude Sonnet |
| Capturas | Fotos y clips, selección, borrar con PIN, zip, clips en el visor; modo remoto conservado. | Agente Claude Sonnet |
| Diseño | Resumen con anillos/área/progreso/actividad (Sonnet), Luces agrupadas por habitación en mosaicos (Gemini vía Haiku), notas de "lo último en casa" junto al reloj de Inicio (Gemini + CSS de Claude). | varios |
| Prueba | Suite 265/265 (dos corridas), todos los JS compilan, sin referencias a :1984/:8080 en el navegador. | Claude |
| Arreglo | Healthcheck de Docker a `/salud` (público, sin datos): antes pegaba en `/api/panel` → 401 → "unhealthy" y el panel avisaba de sí mismo. Contenedores `panel-go2rtc`/`panel-detector` para no chocar con los de gestorCamaras en la semana en paralelo. | Claude |

## 2026-11-13 — README, prueba del navegador y pruebas web

| Paso | Qué | Quién |
|---|---|---|
| README | Reescrito con el proyecto actual: pestañas, modos de transición (`RED_INTERNA`, `CAMARAS_INTERNAS`), despliegue en 5 pasos, variables por grupo, scripts, bot, estructura e índice de docs. | Agente Claude Haiku |
| Navegador | `scripts/prueba_navegador.py` + `tests/test_navegador.py`: levanta el panel aislado con datos falsos, inyecta un capturador de errores y abre cada pestaña con Chrome headless; falla si hay errores de JS. 6/6 pestañas OK (verificado que sí detecta un error inyectado). | Agente Claude Sonnet |
| Web | `tests/test_web_red_clima_hab.py`: 18 pruebas de `/salud`, sonda (404/401/200/413/409), resumen, eventos, CSV, alias, clima y habitaciones. Sin bugs. | Agente Claude Haiku |
| Prueba | Suite completa 284/284. | Claude |

## 2026-11-13 — Cámaras como antes (zoom, mover, grabaciones, audio)

| Paso | Qué | Quién |
|---|---|---|
| Transición | Con `CAMARAS_INTERNAS=0` la pestaña Cámaras vuelve a mostrar gestorCamaras embebido ("En vivo" / "Grabaciones" / "Abrir en otra ventana"), sin autoplay (arranca en silencio, su botón 🔇 Audio activa el sonido); el iframe se quita al salir para liberar la sesión de video. Verificado con las cámaras reales: video, Audio, flechas y zoom. | Agente Sonnet (cortado por límite de uso) + Claude |
| Interno | Reproductor con botón 🔇/🔊 (arranca en silencio, `play()` en el gesto); "📁 Grabaciones" por cámara → Capturas filtrada por esa cámara y hoy; Inicio y Resumen con audio. | Agente Sonnet |
| Prueba real | Puente WebSocket contra el go2rtc de la .94: 101 + 825 KB en ~3 s, video H.264 y audio AAC. Suite 284/284; navegador sin errores. | Claude |
| Clima | Ubicación del cliente: el navegador (solo HTTPS/localhost, con permiso) manda su ubicación redondeada a ~1 km y `/api/clima?lat=&lon=` da su pronóstico (caché 15 min); sin ella y sin `CLIMA_CIUDAD`, la casa se ubica por IP pública con ipapi.co (caché 24 h). Prueba real: Guadalajara, Jalisco, 20.8°. Suite 290/290. | Gemini flash-lite (backend y pruebas, 2 arreglos de Claude) + Claude (ruta, front) |
| Esqueletos | Sistema común de esqueletos de carga (`esqueletos.js` + `esqueletos.css`, 10 formas, fundido a los 300 ms, se quitan solos) en 27 contenedores de Inicio, Resumen, Luces, Capturas y Red; reemplaza las "tres estrellas" del Resumen. Clima y Habitación ya no pisan el esqueleto con "Cargando…". Verificado con capturas simulando API lenta. Regla en memoria y en `docs/DISENO.md`. | Gemini (CSS; el JS se cortó 2 veces) + agente Haiku (JS) + Claude (marcado, arreglos, capturas) |
| Inicio/Luces | Habitaciones pasa a la pestaña Luces (carga propia, toque → su grupo de focos, insignia enciende/apaga la habitación). En Inicio, "Última hora": carrusel de capturas de los últimos 60 min (auto cada 5 s, flechas, deslizar, teclado, miniaturas con la foto, visor). Verificado con fotos reales de la .94. | Gemini (carrusel, CSS, luces-habitaciones vía agente Haiku) + Claude (marcado, miniaturas) |
