# Despliegue en Windows (Docker Desktop)

## Requisitos

- Docker Desktop instalado y encendido.
- Python 3.9 o superior para todos los usuarios (ver [SONDA_WINDOWS.md](SONDA_WINDOWS.md)).
- Git.
- El archivo `.env` de la laptop.
- Nota: gestorCamaras y NetWatch pueden seguir sirviendo durante la prueba.

## Clonar y configurar .env

1. Abre una terminal y ejecuta `git clone <url-del-repo> panel-home` y entra a la carpeta.
2. Copia el archivo `.env.example` a `.env`.
3. Llena las siguientes variables en tu `.env`:

| Variable | Qué poner |
|---|---|
| `RED_INTERNA` | Pon `1`. |
| `RED_TOKEN` | Secreto generado con `py -c "import secrets; print(secrets.token_urlsafe(32))"`. Usa el mismo en la sonda. |
| `CAMARAS_INTERNAS` | Pon `1` (cámaras dentro de panel-home; durante la prueba ver la sección de paralelo). |
| `INTERNO_TOKEN` | Secreto; lo usa el detector para leer la lista de cámaras. Generar igual que `RED_TOKEN`. |
| `CLIMA_CIUDAD` | Tu ciudad, por ejemplo Ciudad de México. |
| `TELEGRAM_TOKEN` | Tu token de Telegram (lo da @BotFather). |
| `TELEGRAM_CHAT_ID` | Tu chat ID de Telegram. |

- Nota: Las URLs del `.env` usan la IP de la laptop (ej. `192.168.1.94`), no `localhost`.
- Nota: El archivo `.env` no se sube a git.

## Levantar

1. Ejecuta `docker compose up -d --build`.
2. Ejecuta `docker compose ps` para verificar que panel-home y go2rtc están en estado "running". El detector NO arranca por defecto.
3. Abre `http://<IP>:8770` desde el celular o la laptop.
- Explicación: go2rtc no publica puertos; solo panel-home habla con él.

## Sonda de red

- Consulta los detalles en [SONDA_WINDOWS.md](SONDA_WINDOWS.md).
- Resumen en 2 pasos: prueba ejecutando `scripts\windows\sonda.bat`, luego instala el servicio con `instalar-sonda.ps1`.
- Sin la sonda, la pestaña Red mostrará "sin lecturas" tras 90 segundos.

## Migrar NetWatch

Realiza esta migración una sola vez:

1. Ejecuta `docker compose stop panel-home`.
2. Ejecuta `py scripts\migrar_netwatch.py <ruta>\netwatch.db --panel-db data\panel.db`.
3. Ejecuta `docker compose start panel-home`.
- Explicación: `<ruta>` es la carpeta de NetWatch donde está `netwatch.db`.

## Migrar cámaras

Realiza esta migración una sola vez:

1. Ejecuta `docker compose stop panel-home`.
2. Ejecuta `py scripts\migrar_camaras.py <ruta>\gestorCamaras\data\cameras.json --panel-db data\panel.db --datos <ruta>\gestorCamaras\data`.
3. Ejecuta `docker compose start panel-home`.
- Explicación: importa las cámaras (se pueden repetir sin duplicar) y copia fotos y clips a `data\` sin borrar nada de gestorCamaras. La salida indica cuántas cámaras importó y cuántos archivos copió.

## Probar en paralelo una semana

Mantén gestorCamaras y NetWatch encendidos durante la prueba:

- Para no recibir avisos dobles, en `.env` pon `PANEL_AVISAR=fuente_caida,fuente_ok,contenedor_caido,contenedor_ok` (esta lista reemplaza la lista por defecto; así panel-home avisa solo lo que nadie más avisa).
- Explicación: NetWatch y gestorCamaras ya avisan internet, red, cámaras y go2rtc.
- Ejecuta `docker compose up -d`.
- NO enciendas el perfil `camaras` todavía (el detector de gestorCamaras sigue activo; dos detectores gastan CPU y guardan fotos por separado).
- Revisa cada día la pestaña Red, Cámaras y la línea de tiempo: compara con NetWatch y gestorCamaras.
- Si algo no cuadra, anótalo; no se corta hasta que la semana esté limpia.

## Corte

Cuando la semana de prueba esté bien:

1. En la carpeta de gestorCamaras, ejecuta `docker compose down` (apaga sus contenedores; no borra sus datos).
2. Detén NetWatch (cierra el programa o detén su servicio).
3. En `.env` quita `PANEL_AVISAR` (o déjala vacía) para que panel-home avise la red y las cámaras.
4. En la carpeta de panel-home, ejecuta `docker compose --profile camaras up -d`.
5. Verifica con `docker compose ps` que panel-home, panel-go2rtc y panel-detector estén en "running".

## Respaldo de data

- Con `docker compose stop`, copia la carpeta `data` completa a un disco externo (contiene `panel.db`, `devices.json`, fotos y clips). Hazlo antes de actualizar y una vez por semana.
- Nota: la carpeta `data\` no se sube a git.

## Actualizar

1. Haz el respaldo de `data\` (arriba).
2. Ejecuta `git pull` y luego `docker compose up -d --build`.

## Problemas comunes

| Síntoma | Qué revisa |
|---|---|
| Cámara sin video en el panel | `docker compose logs go2rtc`; revisa la IP y la clave de la cámara. |
| El panel no ve las cámaras | Revisa que `CAMARAS_INTERNAS=1` esté en `.env` y repite `docker compose up -d`. |
| La pestaña Red dice "sin lecturas" | La sonda no corre o el `RED_TOKEN` no coincide (ver SONDA_WINDOWS.md). |
| No llegan avisos a Telegram | Revisa `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` y `PANEL_AVISAR`. |
| El detector no guarda fotos | Confirma que se levantó con `--profile camaras` y revisa `docker compose logs detector`. |
| Puerto 8770 ocupado o el panel no abre | Revisa el firewall de Windows y la IP. |
| Ver logs en general | `docker compose logs -f panel-home`. |

familia Astreo · Santaella
