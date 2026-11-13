#Requires -RunAsAdministrator
<#
  Detiene y quita la tarea programada de la sonda de red de PleyadesHome.
  No borra el repo, el .env ni el log (data\sonda.log).

  Uso (PowerShell como administrador):
    .\scripts\windows\desinstalar-sonda.ps1
#>

$NombreTarea = "PleyadesHome Sonda"

Write-Host ""
Write-Host "=== Desinstalar la sonda de red (PleyadesHome) ===" -ForegroundColor Cyan

# Si la tarea no existe, no hay nada que hacer
$tarea = Get-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
if (-not $tarea) {
    Write-Host "No existe la tarea '$NombreTarea'. Nada que desinstalar." -ForegroundColor Yellow
    exit 0
}

# Detener la sonda si esta corriendo (si no esta corriendo, no es error)
Write-Host "Deteniendo la sonda..."
Stop-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue

# Quitar la tarea
Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false
Write-Host "Tarea '$NombreTarea' eliminada." -ForegroundColor Green
Write-Host "El repo, el .env y el log (data\sonda.log) siguen intactos."
