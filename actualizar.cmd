@echo off
rem Actualiza el Condor (atajo de instalar.cmd -Actualizar): respalda la base de datos, trae el codigo
rem nuevo (git pull o zip de GitHub), reinstala dependencias, migra la base y reinicia la tarea programada.
setlocal
title Condor - actualizacion
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" -Actualizar %*
set CODIGO=%errorlevel%
echo.
if not "%CODIGO%"=="0" echo La actualizacion termino con errores (codigo %CODIGO%).
pause
exit /b %CODIGO%
