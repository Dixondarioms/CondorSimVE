@echo off
rem Arranca el servidor de S.I.E.T.E. y abre el navegador.
rem   iniciar.cmd                 -> servidor en http://localhost:8000/ + navegador
rem   iniciar.cmd /sin-navegador  -> solo el servidor (tarea programada, arranque automatico)
rem Variables opcionales: SIETE_PUERTO (por defecto 8000), SIETE_HOST (por defecto 0.0.0.0).
setlocal
title S.I.E.T.E. - servidor
cd /d "%~dp0backend"
if "%SIETE_PUERTO%"=="" set SIETE_PUERTO=8000
if "%SIETE_HOST%"=="" set SIETE_HOST=0.0.0.0

if not exist "venv\Scripts\python.exe" (
    echo No se encuentra el entorno de Python ^(backend\venv^).
    echo Ejecute primero instalar.cmd en la carpeta del simulador.
    if /i not "%~1"=="/sin-navegador" pause
    exit /b 1
)

rem Si ya hay un servidor escuchando en el puerto, solo se abre el navegador.
netstat -ano -p TCP | findstr /r /c:":%SIETE_PUERTO% .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo El servidor ya esta en marcha en el puerto %SIETE_PUERTO%.
    if /i not "%~1"=="/sin-navegador" start "" "http://localhost:%SIETE_PUERTO%/"
    exit /b 0
)

if /i not "%~1"=="/sin-navegador" (
    rem Abre el navegador unos segundos despues, cuando el servidor ya responde.
    start "" /b cmd /c "timeout /t 5 /nobreak >nul & start "" "http://localhost:%SIETE_PUERTO%/""
)

echo S.I.E.T.E. - Sistema Integral de Entrenamiento Tactico y Estrategico
echo Servidor en http://localhost:%SIETE_PUERTO%/  (en la red local: http://^<ip-de-este-equipo^>:%SIETE_PUERTO%/)
echo Cierre esta ventana o ejecute detener.cmd para parar el servidor.
echo.
venv\Scripts\python.exe -m app.servidor --host %SIETE_HOST% --port %SIETE_PUERTO%
set CODIGO=%errorlevel%
if not "%CODIGO%"=="0" (
    echo.
    echo El servidor termino con un error ^(codigo %CODIGO%^).
    if /i not "%~1"=="/sin-navegador" pause
)
exit /b %CODIGO%
