#Requires -RunAsAdministrator
<#
  Instala la sonda de red de PleyadesHome como tarea programada de Windows.
  La tarea arranca al encender el equipo (con 1 minuto de espera), corre como SYSTEM
  con pythonw.exe (sin ventana) y se reinicia sola si falla.

  Uso (PowerShell como administrador, desde la raiz del repo):
    Set-ExecutionPolicy -Scope Process Bypass
    .\scripts\windows\instalar-sonda.ps1
#>

$ErrorActionPreference = "Stop"

# Nombre de la tarea y URL del panel (solo para la prueba; la sonda usa su propio valor por defecto)
$NombreTarea = "PleyadesHome Sonda"
$UrlPanel = "http://127.0.0.1:8770/login"

# La raiz del repo es dos niveles arriba de scripts\windows
$Raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$CarpetaData = Join-Path $Raiz "data"
$RutaLog = Join-Path $CarpetaData "sonda.log"

Write-Host ""
Write-Host "=== Instalar la sonda de red (PleyadesHome) ===" -ForegroundColor Cyan
Write-Host "Raiz del repo: $Raiz"

# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

# Devuelve la ruta de python.exe que responda, o $null.
function Obtener-Python {
    # 1) El lanzador "py" de Python para Windows
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            $ruta = & py -3 -c "import sys;print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ruta) { return ($ruta | Select-Object -First 1).Trim() }
        } catch { }
    }
    # 2) "python" en el PATH (ojo: el alias de la Tienda de Microsoft no funciona)
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $ruta = & $cmd.Source -c "import sys;print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $ruta) { return ($ruta | Select-Object -First 1).Trim() }
        } catch { }
    }
    return $null
}

# Indica si ese python es 3.9 o superior.
function Version-Valida([string]$exe) {
    try {
        & $exe -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

# ---------------------------------------------------------------------------
# 1. Python 3.9+
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[1/5] Buscando Python 3.9 o superior..." -ForegroundColor Cyan

$python = Obtener-Python
if (-not $python -or -not (Version-Valida $python)) {
    Write-Host "No encuentro Python 3.9 o superior." -ForegroundColor Red
    Write-Host ""
    Write-Host "Como instalarlo:"
    Write-Host "  1. Descarga Python desde https://www.python.org/downloads/ (instalador de Windows 64 bits)."
    Write-Host "  2. Ejecuta el instalador y marca 'Add python.exe to PATH'."
    Write-Host "  3. Elige 'Customize installation' y en 'Advanced Options' marca 'Install for all users'."
    Write-Host "     (La tarea corre como SYSTEM; necesita un Python que SYSTEM pueda usar.)"
    Write-Host "  4. Cierra esta ventana, abre PowerShell como administrador y vuelve a ejecutar este script."
    exit 1
}
Write-Host "Python encontrado: $python" -ForegroundColor Green

# La tarea usa pythonw.exe (sin ventana), que va en la misma carpeta que python.exe
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Host "No encuentro pythonw.exe junto a $python." -ForegroundColor Red
    Write-Host "Reinstala Python desde python.org (Customize installation, no quites los componentes por defecto)."
    exit 1
}
Write-Host "Se usara: $pythonw" -ForegroundColor Green

if ($python -match '\\Users\\') {
    Write-Host "AVISO: este Python esta instalado solo para tu usuario. La tarea corre como SYSTEM" -ForegroundColor Yellow
    Write-Host "       y podria no poder usarlo. Si falla, reinstala con 'Install for all users'." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 2. Archivo .env con RED_TOKEN
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/5] Revisando el archivo .env (RED_TOKEN)..." -ForegroundColor Cyan

$rutaEnv = Join-Path $Raiz ".env"
if (-not (Test-Path $rutaEnv)) {
    Write-Host "No existe el archivo .env en la raiz del repo." -ForegroundColor Red
    Write-Host ""
    Write-Host "Crea el archivo .env (copiando .env.example) y genera el secreto con:"
    Write-Host '  py -c "import secrets; print(secrets.token_urlsafe(32))"'
    Write-Host "Pon el resultado en la linea RED_TOKEN=... del .env."
    Write-Host "Debe ser EL MISMO valor que usa panel-home, y luego ejecuta: docker compose up -d"
    exit 1
}

$token = $null
foreach ($linea in Get-Content -Path $rutaEnv -Encoding UTF8) {
    if ($linea -match '^\s*RED_TOKEN\s*=\s*(.*)$') {
        $token = $matches[1].Trim().Trim('"').Trim("'")
    }
}
if (-not $token) {
    Write-Host "El .env no tiene RED_TOKEN o esta vacio." -ForegroundColor Red
    Write-Host ""
    Write-Host "Genera un secreto con:"
    Write-Host '  py -c "import secrets; print(secrets.token_urlsafe(32))"'
    Write-Host "Ponlo en el .env como RED_TOKEN=<secreto>. Debe ser el mismo que usa panel-home."
    Write-Host "Despues de cambiarlo, ejecuta: docker compose up -d --build"
    exit 1
}
Write-Host "RED_TOKEN encontrado en .env." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 3. Prueba del panel (no aborta si falla)
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/5] Probando el panel en $UrlPanel ..." -ForegroundColor Cyan

try {
    Invoke-WebRequest -UseBasicParsing -Uri $UrlPanel -TimeoutSec 5 | Out-Null
    Write-Host "El panel responde." -ForegroundColor Green
} catch {
    if ($_.Exception.Response) {
        # Respondio con un codigo HTTP de error: el panel esta vivo
        Write-Host "El panel responde (con un codigo de error HTTP, pero esta arriba)." -ForegroundColor Green
    } else {
        Write-Host "AVISO: el panel no responde en $UrlPanel." -ForegroundColor Yellow
        Write-Host "       Revisa que Docker Desktop este abierto y que panel-home este corriendo"
        Write-Host "       (docker compose up -d). La tarea se instala igual: la sonda reintenta sola."
    }
}

# ---------------------------------------------------------------------------
# 4. Registrar la tarea programada
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/5] Registrando la tarea programada '$NombreTarea'..." -ForegroundColor Cyan

if (-not (Test-Path $CarpetaData)) {
    New-Item -ItemType Directory -Path $CarpetaData -Force | Out-Null
}

# Si ya existe, la detenemos antes de reemplazarla (-Force la sobrescribe)
if (Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue) {
    Write-Host "La tarea ya existe; se reemplaza." -ForegroundColor Yellow
    Stop-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
}

# Accion: pythonw.exe -m sonda --log "<raiz>\data\sonda.log", desde la raiz del repo
$argumentos = "-m sonda --log `"$RutaLog`""
$accion = New-ScheduledTaskAction -Execute $pythonw -Argument $argumentos -WorkingDirectory $Raiz

# Disparador: al iniciar el sistema, con 60 s de retraso (red y Docker tiempo de arrancar)
$disparador = New-ScheduledTaskTrigger -AtStartup
$disparador.Delay = "PT1M"

# Cuenta SYSTEM con privilegios maximos
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

# Configuracion: reinicio cada 1 min hasta 999 veces, sin limite de tiempo, con bateria, una sola instancia
$config = New-ScheduledTaskSettingsSet `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $NombreTarea `
    -Action $accion `
    -Trigger $disparador `
    -Principal $principal `
    -Settings $config `
    -Description "Sonda de red de PleyadesHome: mide la red local y envia lecturas al panel. Familia Astreo - Santaella." `
    -Force | Out-Null

Write-Host "Tarea registrada." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 5. Arrancar y mostrar el log
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/5] Arrancando la sonda..." -ForegroundColor Cyan

Start-ScheduledTask -TaskName $NombreTarea
Write-Host "Esperando 20 segundos para que escriba el log..."
Start-Sleep -Seconds 20

$estado = (Get-ScheduledTask -TaskName $NombreTarea).State
Write-Host "Estado de la tarea: $estado"
Write-Host ""
Write-Host "Ultimas lineas de $RutaLog :" -ForegroundColor Cyan
if (Test-Path $RutaLog) {
    Get-Content -Path $RutaLog -Tail 15 -Encoding UTF8
} else {
    Write-Host "Todavia no hay log. Espera un minuto y revisalo con:" -ForegroundColor Yellow
    Write-Host "  Get-Content '$RutaLog' -Tail 30"
}

Write-Host ""
Write-Host "Listo. La sonda arrancara sola cada vez que enciendas el equipo." -ForegroundColor Green
Write-Host "Documentacion: docs\SONDA_WINDOWS.md"
