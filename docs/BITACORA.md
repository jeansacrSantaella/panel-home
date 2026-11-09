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
