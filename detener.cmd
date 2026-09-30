@echo off
rem Detiene el servidor de S.I.E.T.E. arrancado con iniciar.cmd (procesos python que ejecutan app.servidor).
rem Variable opcional: SIETE_PUERTO (por defecto 8000) para detener solo el servidor de ese puerto.
setlocal
if "%SIETE_PUERTO%"=="" set SIETE_PUERTO=8000
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -match 'app\.servidor' -and $_.CommandLine -match ('--port ' + $env:SIETE_PUERTO + '(\s|$)') };" ^
  "if (-not $p) { Write-Host ('No hay ningun servidor de S.I.E.T.E. en marcha en el puerto ' + $env:SIETE_PUERTO + '.'); exit 0 };" ^
  "foreach ($x in $p) { try { Stop-Process -Id $x.ProcessId -Force -ErrorAction Stop; Write-Host ('Servidor detenido (PID ' + $x.ProcessId + ').') } catch { Write-Host ('No se pudo detener el PID ' + $x.ProcessId + ': ' + $_.Exception.Message) } }"
if /i not "%~1"=="/silencioso" pause
