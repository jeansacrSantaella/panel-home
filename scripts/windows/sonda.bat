@echo off
rem Sonda de red de PleyadesHome en primer plano, con ventana, para probarla.
rem Lee el .env de la raiz del repo. Ctrl+C la detiene.
rem Uso (desde cualquier carpeta):  scripts\windows\sonda.bat  [opciones extra]

cd /d "%~dp0..\.."

where py >nul 2>nul
if errorlevel 1 (
  echo No encuentro el lanzador "py". Instala Python 3.9 o superior desde python.org
  echo marcando "Add python.exe to PATH" e "Install for all users".
  pause
  exit /b 1
)

py -3 -m sonda --verbose %*
echo.
pause
