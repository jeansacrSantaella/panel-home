# Detector de movimiento

Contenedor aparte que vigila las cámaras de panel-home. Cada `INTERVALO` segundos toma una foto de cada cámara
desde go2rtc, detecta si hubo movimiento (máscara de diferencias) y, si lo hubo, pasa YOLO para reconocer
personas, carros, motos, gatos y perros. Si encuentra algo, guarda la foto anotada y, al detectar una persona,
graba un clip corto con ffmpeg desde RTSP.

Fotos: `fotos/AAAA-MM-DD/<cid>_<HH-MM-SS>_<clases>.jpg`. Clips: `clips/AAAA-MM-DD/<cid>_<HH-MM-SS>_persona.mp4`.
Se borran los archivos más viejos que `RETENCION_HORAS`.

No envía Telegram. El resumen cada 2 h (sin imágenes de 23:00 a 7:00) lo manda panel-home.

## Variables

| Variable | Por defecto | Uso |
|---|---|---|
| `PANEL_URL` | `http://panel-home:8770` | Lista de cámaras: `GET /api/interno/camaras` |
| `INTERNO_TOKEN` | (vacío) | Cabecera `Authorization: Bearer` para la lista de cámaras |
| `GO2RTC_URL` | `http://go2rtc:1984` | Fotos: `/api/frame.jpeg?src=<cid>` |
| `RTSP_URL` | `rtsp://go2rtc:8554` | Origen de los clips |
| `INTERVALO` | `1.5` | Segundos entre rondas |
| `CONFIANZA` | `0.5` | Confianza mínima de YOLO |
| `MOVIMIENTO` | `0.004` | Fracción mínima de píxeles que cambian para pasar a YOLO |
| `ENFRIAMIENTO` | `30` | Segundos sin repetir la misma clase en la misma cámara |
| `RETENCION_HORAS` | `24` | Antigüedad máxima de fotos y clips |
| `CLIP_SEG` | `15` | Duración del clip (0 lo desactiva) |
| `MODELO` | `yolo11n.pt` | Modelo de Ultralytics |
| `DATA_DIR` | `/data` | Carpeta de `fotos/` y `clips/` (la misma `data/` del panel) |

## Pruebas

Las pruebas de funciones puras no necesitan torch ni OpenCV:

    python3 -m unittest tests.test_detector_utilidades

familia Astreo · Santaella
