@echo off
chcp 65001 >nul
title Gestor de certificados
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo.
  echo   [ FALTA ] Node.js no esta instalado o no se encuentra.
  echo   Ejecuta primero  "1 - Instalar requisitos.bat"
  echo   ^(y si acabas de instalar Node, cierra esta ventana y vuelve a abrir el gestor^).
  echo.
  pause
  exit /b
)

echo ================================================================
echo    Gestor de certificados
echo ================================================================
echo.
echo   El gestor se abrira solo en tu navegador en unos segundos.
echo   Si no abre, entra manualmente a:  http://127.0.0.1:4599
echo.
echo   *** NO cierres esta ventana mientras uses el gestor. ***
echo.
node server.js
echo.
echo El gestor se detuvo. Si arriba hay un error, esa es la causa.
pause
