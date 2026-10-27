@echo off
rem Detiene el servidor de S.I.E.T.E. arrancado con iniciar.cmd (procesos python que ejecutan app.servidor).
rem Variable opcional: SIETE_PUERTO (por defecto 8001 en el SIETE en tiempo real, u 8443 con HTTPS) para detener solo el servidor de ese
rem puerto. Se lee tambien de backend\.env, igual que en iniciar.cmd.
setlocal
if exist "%~dp0backend\.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0backend\.env") do (
        if /i "%%a"=="SIETE_PUERTO" if not defined SIETE_PUERTO set "SIETE_PUERTO=%%b"
        if /i "%%a"=="SIETE_HTTPS" if not defined SIETE_HTTPS set "SIETE_HTTPS=%%b"
    )
)
if "%SIETE_PUERTO%"=="" if "%SIETE_HTTPS%"=="1" set SIETE_PUERTO=8443
if "%SIETE_PUERTO%"=="" set SIETE_PUERTO=8001
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'app\.servidor' -and $_.CommandLine -match ('--port ' + $env:SIETE_PUERTO + '(\s|$)') };" ^
  "if (-not $p) { Write-Host ('No hay ningun servidor de S.I.E.T.E. en marcha en el puerto ' + $env:SIETE_PUERTO + '.'); exit 0 };" ^
  "foreach ($x in $p) { try { Stop-Process -Id $x.ProcessId -Force -ErrorAction Stop; Write-Host ('Servidor detenido (PID ' + $x.ProcessId + ').') } catch { Write-Host ('No se pudo detener el PID ' + $x.ProcessId + ': ' + $_.Exception.Message) } }"
if /i not "%~1"=="/silencioso" pause
