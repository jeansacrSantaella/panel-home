# Luces: conectar los focos Tuya

> **Camino corto (recomendado):** pon tu *Código de usuario* de Smart Life (Yo → ⚙️ → Cuenta y seguridad) en
> `data/smartlife.json` como `{"user_code": "..."}`, corre `python3 scripts/llaves_smartlife.py`, escanea el QR con
> Smart Life y listo: escribe `data/devices.json`. No necesitas la cuenta de desarrollador de abajo.

PleyadesHome controla los focos **por la red de la casa** (puerto 6668), sin pasar por la nube de Tuya.
Para eso necesita la **llave local** de cada foco. Solo se obtiene una vez, con tu cuenta de la app.
Toma unos 15 minutos.

> Las llaves y la clave de API son secretas: quedan en `data/`, que **no** se sube a git ni entra en la imagen de Docker.

## 1. Crea una cuenta de desarrollador (gratis)

1. Entra a <https://iot.tuya.com> y regístrate (puede ser el mismo correo de la app).
2. **Cloud → Development → Create Cloud Project**:
   - *Industry*: Smart Home · *Development Method*: Smart Home
   - *Data Center*: **Western America Data Center** (el de México)
3. Acepta los servicios de API que propone (IoT Core, Authorization Token Management…).

## 2. Vincula tu app

1. En el proyecto: **Devices → Link App Account → Add App Account**.
2. En la app **Smart Life** (o Tuya Smart): **Yo / Me → ícono de escanear** (arriba a la derecha) y escanea el código.
3. Elige *Automatic link* y permisos *Read, write and manage*.
4. Verás tus 5 focos en la lista **All Devices** del proyecto. Copia el **Device ID** de cualquiera.
5. En **Overview** copia el **Access ID/Client ID** y el **Access Secret/Client Secret**.

## 3. Descarga las llaves (en tu Mac, conectada al wifi de la casa)

```bash
cd ~/Documents/Desarrollo/Portfolio/panel-home
python3 -m pip install -r requirements.txt
mkdir -p data && cd data
python3 -m tinytuya wizard
```

El asistente pregunta:

| Pregunta | Respuesta |
|---|---|
| API Key | el Access ID |
| API Secret | el Access Secret |
| Device ID | el que copiaste |
| Region | `us` (Western America) |
| Download DP Name mappings? | `Y` |
| Poll local devices? | `Y` (así guarda la IP y versión de cada foco) |

Al terminar quedan en `data/`: **`devices.json`** (nombres, IPs y llaves) y `tinytuya.json` (tu clave de API).
`tinytuya.json` ya no hace falta: bórralo si no piensas repetir el asistente.

## 4. Llévalo a la Lenovo

1. Copia `data/devices.json` a `panel-home/data/devices.json` en la Lenovo (USB o carpeta compartida).
2. En PowerShell, dentro de `panel-home`: `git pull` y `docker compose up -d --build`.
3. Abre el panel: la tarjeta **Luces** muestra los 5 focos.

## Si algo falla

- **"Sin respuesta"**: el foco está apagado del interruptor de pared o cambió de IP. Si falta la IP, el panel la
  busca por la MAC en NetWatch; también puedes reservar IPs fijas en el módem.
- **Volviste a emparejar un foco en la app**: su llave cambia. Repite el paso 3.
- **La prueba gratuita de IoT Core venció**: no importa. La nube solo se usa para sacar las llaves; el control
  es local. Si necesitas repetir el asistente, renueva la prueba en el portal.
