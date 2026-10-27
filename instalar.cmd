@echo off
rem Instalador del Condor para Windows: doble clic y listo.
rem Los parametros se pasan a instalar.ps1, p. ej.:  instalar.cmd -Demo  |  -Servicio  |  -Postgres "<url>"  |  -Https  |  -Datos <zip>  |  -Actualizar  |  -Desinstalar
setlocal
title Condor - instalacion
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
set CODIGO=%errorlevel%
echo.
if not "%CODIGO%"=="0" echo La instalacion termino con errores (codigo %CODIGO%).
pause
exit /b %CODIGO%
