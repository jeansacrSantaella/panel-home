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
