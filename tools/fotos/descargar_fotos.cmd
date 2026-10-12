@echo off
rem Descarga de Wikimedia Commons las fotos de referencia de aeronaves, drones y buques (ver tools\fotos\fotos_referencia.py).
rem   descargar_fotos.cmd                          -> descarga las que falten
rem   descargar_fotos.cmd --elegir fragata=2       -> cambia una foto por otra candidata (ver la hoja que se abre)
rem Necesita internet. Despues, reinicie el servidor (detener.cmd e iniciar.cmd) para ver las fotos.
setlocal
title S.I.E.T.E. - fotos de referencia
cd /d "%~dp0..\.."
set PY=backend\venv\Scripts\python.exe
if not exist "%PY%" (
    echo No se encuentra el entorno de Python ^(backend\venv^). Ejecute primero instalar.cmd.
    pause
    exit /b 1
)
"%PY%" tools\fotos\fotos_referencia.py %*
if errorlevel 1 (
    echo No se pudieron descargar las fotos: revise la conexion a internet.
    pause
    exit /b 1
)
if exist "tools\fotos\salida\candidatas.html" start "" "tools\fotos\salida\candidatas.html"
pause
