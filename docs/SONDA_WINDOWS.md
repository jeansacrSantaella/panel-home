# Sonda de red en Windows

La sonda mide la red de la casa desde una laptop Windows (fuera de Docker, para ver las MAC) y manda las lecturas
a panel-home. Contrato técnico en [RED.md](RED.md).

## Requisitos

- **Python 3.9 o superior para todos los usuarios**: en python.org, marca *Add python.exe to PATH*, luego
  *Customize installation* > *Advanced Options* > *Install for all users*. La tarea corre como SYSTEM.
- **panel-home corriendo en Docker Desktop** (en esta laptop o en la red de la casa).
- **El mismo `RED_TOKEN` en el `.env`** de la raíz del repo que en panel-home. La sonda lo lee sola del `.env`.

## Pasos

1. **Configurar panel-home.** En `.env` pon `RED_INTERNA=1` y `RED_TOKEN=<secreto>`. Para generar el secreto:
   `py -c "import secrets; print(secrets.token_urlsafe(32))"`. Luego:
   `docker compose up -d --build`

2. **Probar la sonda.** Doble clic en `scripts\windows\sonda.bat` (o ejecútalo desde una terminal). Debe aparecer
   una línea por lectura. Ctrl+C para detenerla.

3. **Instalarla como servicio.** PowerShell como administrador, desde la raíz del repo:
   ```
   Set-ExecutionPolicy -Scope Process Bypass
   .\scripts\windows\instalar-sonda.ps1
   ```
   Crea la tarea programada *PleyadesHome Sonda*: arranca 1 minuto después de encender el equipo, sin ventana,
   y se reinicia sola si falla.

4. **Migrar el historial de NetWatch** (una sola vez). Con el contenedor detenido (`docker compose stop`):
   ```
   py scripts\migrar_netwatch.py <ruta>\netwatch.db --panel-db data\panel.db
   ```
   Después, `docker compose start`. También puede correrse desde dentro del contenedor.

5. **Apagar NetWatch** para que no mida la misma red por separado.

## Operación

- **Ver el log:** `type data\sonda.log` o, en vivo, `Get-Content data\sonda.log -Tail 30 -Wait`.
- **Reiniciar:** `Stop-ScheduledTask -TaskName "PleyadesHome Sonda"` y luego `Start-ScheduledTask -TaskName "PleyadesHome Sonda"`.
- **Desinstalar:** PowerShell como administrador, `.\scripts\windows\desinstalar-sonda.ps1`. No borra el repo, el `.env` ni el log.

## Problemas comunes

- **Firewall:** la sonda solo hace conexiones salientes (al panel). No hace falta abrir puertos.
- **Antivirus:** algunos antivirus bloquean el ping (ICMP) o ven la sonda como sospechosa. Si las lecturas de ping
  faltan, revisa el log y la configuración del antivirus.
- **Laptop suspendida:** mientras duerme no hay lecturas. El panel lo registra como *pausa del monitor*, no como
  caída. Si la laptop debe medir siempre, desactiva la suspensión en Configuración de energía.
- **Equipos que no aparecen:** la sonda solo ve los equipos de la /24 del adaptador de red principal (Wi-Fi o
  Ethernet). Si la red de la casa está en otra subred, o hay una VPN activa, el escaneo mide otra red.
