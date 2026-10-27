@echo off
rem Arranca el servidor de S.I.E.T.E. y abre el navegador.
rem   iniciar.cmd                 -> servidor en http://localhost:8001/ + navegador
rem   iniciar.cmd /sin-navegador  -> solo el servidor (tarea programada, arranque automatico)
rem Variables opcionales: SIETE_PUERTO (por defecto 8001 en el SIETE en tiempo real, para convivir con el SIETE por turnos en el 8000; 8443 con HTTPS), SIETE_HOST (por defecto 0.0.0.0),
rem SIETE_HTTPS=1 (certificado autofirmado de backend\certs). Se leen tambien de backend\.env
rem (lo escribe instalar.cmd -Https / -Postgres); la variable ya definida en el entorno tiene prioridad.
setlocal
title S.I.E.T.E. - servidor
cd /d "%~dp0backend"
if exist ".env" call :leer_env ".env"
if "%SIETE_PUERTO%"=="" if "%SIETE_HTTPS%"=="1" set SIETE_PUERTO=8443
if "%SIETE_PUERTO%"=="" set SIETE_PUERTO=8001
if "%SIETE_HOST%"=="" set SIETE_HOST=0.0.0.0
set ESQUEMA=http
set OPCION_HTTPS=
if "%SIETE_HTTPS%"=="1" (
    set ESQUEMA=https
    set OPCION_HTTPS=--https
)

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
    if /i not "%~1"=="/sin-navegador" start "" "%ESQUEMA%://localhost:%SIETE_PUERTO%/"
    exit /b 0
)

if /i not "%~1"=="/sin-navegador" (
    rem Abre el navegador unos segundos despues, cuando el servidor ya responde.
    start "" /b cmd /c "timeout /t 5 /nobreak >nul & start "" "%ESQUEMA%://localhost:%SIETE_PUERTO%/""
)

echo S.I.E.T.E. - Sistema Integral de Entrenamiento Tactico y Estrategico
echo Servidor en %ESQUEMA%://localhost:%SIETE_PUERTO%/  (en la red local: %ESQUEMA%://^<ip-de-este-equipo^>:%SIETE_PUERTO%/)
if "%SIETE_HTTPS%"=="1" echo HTTPS con certificado autofirmado: el navegador avisara la primera vez ^(ver README, seccion HTTPS^).
echo Cierre esta ventana o ejecute detener.cmd para parar el servidor.
echo.
venv\Scripts\python.exe -m app.servidor --host %SIETE_HOST% --port %SIETE_PUERTO% %OPCION_HTTPS%
set CODIGO=%errorlevel%
if not "%CODIGO%"=="0" (
    echo.
    echo El servidor termino con un error ^(codigo %CODIGO%^).
    if /i not "%~1"=="/sin-navegador" pause
)
exit /b %CODIGO%

:leer_env
rem Lee solo las variables SIETE_* de backend\.env (el resto, p. ej. la base de datos, las lee Python).
rem No pisa una variable ya definida en el entorno.
for /f "usebackq eol=# tokens=1,* delims==" %%a in (%1) do (
    if /i "%%a"=="SIETE_PUERTO" if not defined SIETE_PUERTO set "SIETE_PUERTO=%%b"
    if /i "%%a"=="SIETE_HOST" if not defined SIETE_HOST set "SIETE_HOST=%%b"
    if /i "%%a"=="SIETE_HTTPS" if not defined SIETE_HTTPS set "SIETE_HTTPS=%%b"
)
exit /b 0
