@echo off
chcp 65001 >nul
title Instalar requisitos del Gestor de certificados
cd /d "%~dp0"
echo ================================================================
echo    INSTALADOR DE REQUISITOS - Gestor de certificados
echo ================================================================
echo.
echo Este paso se hace UNA sola vez en cada computadora nueva.
echo.

echo [1/3] Comprobando Node.js...
where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo   [ FALTA ] Node.js no esta instalado.
  echo   1^) Abre https://nodejs.org  y descarga la version "LTS".
  echo   2^) Instalalo con las opciones por defecto.
  echo   3^) Vuelve a ejecutar este archivo.
  echo.
  pause
  exit /b
)
echo         OK - Node.js encontrado.
echo.

echo [2/3] Comprobando Python...
set "PY=py"
%PY% --version >nul 2>nul
if errorlevel 1 (
  set "PY=python"
  %PY% --version >nul 2>nul
  if errorlevel 1 (
    echo.
    echo   [ FALTA ] Python no esta instalado.
    echo   1^) Abre https://www.python.org/downloads  y descarga Python.
    echo   2^) MUY IMPORTANTE: en el instalador marca la casilla
    echo      "Add Python to PATH" antes de darle a Install.
    echo   3^) Vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b
  )
)
echo         OK - Python encontrado.
echo.

echo [3/3] Instalando componentes (puede tardar 1-2 minutos)...
echo.
echo   - Librerias de Python...
%PY% -m pip install --quiet --disable-pip-version-check pypdfium2 pillow "qrcode[pil]" openpyxl
if errorlevel 1 (
  echo   [ ERROR ] No se pudieron instalar las librerias de Python.
  pause
  exit /b
)
echo     OK
echo   - Dependencias de Node (se descargan de internet)...
if exist "node_modules" rmdir /s /q "node_modules"
call npm install --no-audit --no-fund
if errorlevel 1 (
  echo   [ ERROR ] No se pudieron descargar las dependencias de Node.
  echo            Verifica que haya conexion a internet y vuelve a intentar.
  pause
  exit /b
)
echo     OK
echo.
echo ================================================================
echo    LISTO. Ya puedes abrir  "Gestor de certificados.bat"
echo ================================================================
echo.
pause
