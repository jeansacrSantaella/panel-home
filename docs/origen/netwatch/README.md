# netwatch

Monitor de red casera para Python 3.9 o posterior. No instales dependencias.

## Qué hace

- **Equipos:** cada 2 minutos, escanea la subred `/24` y lee la tabla ARP. Guarda IP, MAC, nombre y fechas de actividad. Te avisa cuando detecta un equipo nuevo, conectado o desconectado.
- **Caídas:** cada 5 segundos, prueba el router y dos destinos externos por ping y DNS. Distingue fallas de red local, internet y DNS.
- **IP pública:** consulta la IP cada 5 minutos y registra cada cambio.
- **Pausas:** si suspendes el equipo que ejecuta el monitor, registra una pausa en vez de una caída de red.
- **Dashboard:** consulta disponibilidad de 24 horas, latencia de la última hora, equipos, caídas por horario y eventos.
- **Escáner:** analiza un host cuando lo solicitas: identifica el equipo, mide ping y TTL, consulta DNS y revisa puertos TCP.
- **Paginación:** elige 10, 25 o 50 filas por página en las tablas de equipos y eventos.
- **Eventos:** filtra el historial por rango de fechas, tipo de evento o ambos.
- **Personalización:** reordena y expande las tarjetas, cambia el tema y guarda tus preferencias en el navegador.

## Uso

```bash
python3 main.py                  # Abre http://127.0.0.1:8765
python3 main.py --host 0.0.0.0   # Accede desde otro equipo de la red
```

En Mac, evita la suspensión mientras mide:

```bash
caffeinate -i python3 main.py
```

Ejecuta el monitor directamente en tu sistema, no en Docker: en Mac, Docker no ve la red local y no puede escanear equipos.

Guarda los datos en `netwatch.db`, en la raíz del proyecto. Conserva las mediciones durante 30 días y los eventos y equipos sin límite.

## Estructura

```
main.py              inicia la aplicación
netwatch/
  config.py          configura intervalos, rutas y entorno
  app.py             conecta los componentes
  core/              define eventos, tareas y métricas
  storage/           guarda datos en SQLite
  network/           consulta ping, DNS, ARP, router y fabricantes
  monitors/          mide conectividad, equipos y velocidad
  alerts/            envía alertas por Telegram
  services/          prepara resúmenes, CSV, eventos y escaneos
  web/               atiende rutas y endpoints
  static/            contiene el dashboard (HTML, CSS y JavaScript)
tests/               ejecuta pruebas con python3 -m unittest
```

Para añadir una medición, crea una `PeriodicTask` en `monitors/` y regístrala en `app.py`. Para añadir un endpoint, regístralo en `web/api.py`. Para añadir una tarjeta, crea un widget en `static/js/widgets/` y regístralo en `main.js`. Abre `/docs` con el monitor en marcha para consultar la documentación técnica.

## Calidad, velocidad y fabricantes

- **Jitter y pérdida:** consulta la última hora de pings al router y a `1.1.1.1` y `8.8.8.8`.
- **Por equipo:** cada 30 segundos, mide latencia, jitter y pérdida de cada equipo conectado, y cuenta sus desconexiones de las últimas 24 horas. Consulta en el dashboard cuáles no responden al ping.
- **Prueba de velocidad:** cada hora, descarga unos 10 MB y sube unos 3 MB desde Cloudflare (cerca de 300 MB al día). Ajusta `speed_every`, `speed_down_bytes` y `speed_up_bytes` en `netwatch/config.py` para cambiar la frecuencia o el volumen.
- **Fabricante:** descarga la lista IEEE en `oui.txt` la primera vez que inicies. Si no hay conexión y el archivo queda vacío, bórralo y reinicia el monitor.

## Alertas por Telegram (gratis)

1. En Telegram, abre **@BotFather**, envía `/newbot` y guarda el token. No lo compartas ni lo subas a GitHub.
2. Abre un chat con tu bot y envíale un mensaje.
3. Obtén el ID del chat:
   ```bash
   export TELEGRAM_TOKEN="tu-token"
   python3 main.py --find-chat-id
   ```
4. Define también el ID del chat y prueba la conexión:
   ```bash
   export TELEGRAM_CHAT_ID="tu-chat-id"
   python3 main.py --test-telegram
   ```
5. Inicia el monitor en esa terminal con ambas variables definidas para activar las alertas.

Recibirás avisos de caídas y recuperaciones de red local, internet y DNS, equipos nuevos y cambios de IP pública. Edita `DEFAULT_ALERT_KINDS` en `netwatch/config.py` para elegir qué avisos recibes. Si falla internet, los mensajes quedan en cola y salen al recuperar la conexión, con la hora real del evento. Tras `--reset`, omite las alertas de equipos nuevos durante el primer escaneo.

## Límites

- Aún no consultes el consumo individual de los equipos desde el dashboard.
- No encontrarás el equipo que ejecuta netwatch en la lista de dispositivos.
- Con `--host 0.0.0.0`, cualquier equipo de tu red puede ver el dashboard y cambiar alias.
- Para medir las caídas con precisión, ejecuta el monitor en un equipo siempre encendido y conectado por cable.
