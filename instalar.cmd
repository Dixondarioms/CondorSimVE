@echo off
rem Instalador de S.I.E.T.E. para Windows: doble clic y listo.
rem Los parametros se pasan a instalar.ps1, p. ej.:  instalar.cmd -Demo   |   instalar.cmd -Servicio   |   instalar.cmd -Desinstalar
setlocal
title S.I.E.T.E. - instalacion
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
set CODIGO=%errorlevel%
echo.
if not "%CODIGO%"=="0" echo La instalacion termino con errores (codigo %CODIGO%).
pause
exit /b %CODIGO%
