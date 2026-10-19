@echo off
rem Video TUTORIAL de S.I.E.T.E. en 2K (2560x1440) con locucion en espanol de Venezuela (ver tools\video\README.md).
rem   generar_tutorial.cmd                      -> voz masculina (es-VE-SebastianNeural)
rem   generar_tutorial.cmd es-VE-PaolaNeural    -> voz femenina
rem Necesita internet (solo para la voz) y ffmpeg en el PATH. Resultado: tools\video\salida\SIETE_tutorial_2K_locucion.mp4
setlocal
title S.I.E.T.E. - video tutorial
cd /d "%~dp0..\.."
set PY=backend\venv\Scripts\python.exe
if not exist "%PY%" (
    echo No se encuentra el entorno de Python ^(backend\venv^). Ejecute primero instalar.cmd.
    pause
    exit /b 1
)
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo Falta ffmpeg: instalelo con  winget install Gyan.FFmpeg  o descarguelo de https://www.gyan.dev/ffmpeg/builds/
    pause
    exit /b 1
)
set VOZ=%~1
if "%VOZ%"=="" set VOZ=es-VE-SebastianNeural

"%PY%" -m pip install -q -r tools\video\requirements.txt
if errorlevel 1 (
    echo No se pudieron instalar las dependencias del video.
    pause
    exit /b 1
)

rem 1) capturas 4K y clips 2K del simulador en marcha (una sola vez; borre tools\video\salida\capturas o \clips para repetirlos)
if not exist "tools\video\salida\capturas\focos.json" set FALTA=1
if not exist "tools\video\salida\clips\clip_replay\meta.json" set FALTA=1
if defined FALTA (
    netstat -ano -p TCP | findstr /r /c:":8000 .*LISTENING" >nul 2>&1
    if errorlevel 1 (
        echo Arrancando el servidor de S.I.E.T.E. para las capturas...
        start "S.I.E.T.E. - servidor" /min cmd /c ""%CD%\iniciar.cmd" /sin-navegador"
        timeout /t 10 /nobreak >nul
    )
    if not exist "tools\video\salida\capturas\focos.json" "%PY%" tools\video\capturas_video.py
    if errorlevel 1 (
        echo Fallaron las capturas.
        pause
        exit /b 1
    )
    if not exist "tools\video\salida\clips\clip_replay\meta.json" "%PY%" tools\video\clips_video.py
    if errorlevel 1 (
        echo Fallaron los clips.
        pause
        exit /b 1
    )
)

rem 2) locucion con la voz neuronal de Microsoft (un poco mas rapida que la normal)
"%PY%" tools\video\locucion.py --guion guion_tutorial --voz %VOZ% --velocidad +8%%
if errorlevel 1 (
    echo No se pudo generar la locucion: revise la conexion a internet.
    pause
    exit /b 1
)

rem 3) montaje en 2K
"%PY%" tools\video\generar_video.py --guion guion_tutorial --resolucion 2k
if errorlevel 1 (
    echo Fallo el montaje del video.
    pause
    exit /b 1
)
start "" "tools\video\salida"
pause
