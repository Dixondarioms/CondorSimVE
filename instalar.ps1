<#
.SYNOPSIS
    Instala S.I.E.T.E. (Simulador Fénix) en un PC con Windows: entorno de Python, dependencias,
    primer usuario instructor, acceso directo en el Escritorio y, opcionalmente, arranque automático.

.DESCRIPTION
    Uso normal: doble clic en instalar.cmd (que ejecuta este script). Opciones:

      -Demo           crea además el escenario de demostración (Andes/Llanos).
      -Servicio       registra la tarea programada "SIETE Servidor" para que el servidor arranque solo
                      (al iniciar Windows si se ejecuta como administrador; si no, al iniciar sesión).
      -Desinstalar    quita la tarea programada, el acceso directo y la regla del cortafuegos.
                      No borra la base de datos ni el entorno de Python.
      -Destino <dir>  carpeta donde crear el acceso directo (por defecto, el Escritorio).
      -Usuario <nombre>  nombre del primer instructor (si no se indica, se pregunta).
      -SinUsuario     no crea el primer instructor (instalación desatendida).
      -SinAccesoDirecto  no crea el acceso directo.

    El script nunca descarga instaladores: si falta Python, indica de dónde bajarlo y se detiene.
    Variables de entorno respetadas: SIMULADOR_DB (otra base SQLite), SIETE_PUERTO (puerto, 8000).

.EXAMPLE
    instalar.cmd
    instalar.cmd -Demo
    instalar.cmd -Servicio          (como administrador: arranque con Windows + cortafuegos)
    instalar.cmd -Desinstalar
#>
[CmdletBinding()]
param(
    [switch]$Demo,
    [switch]$Servicio,
    [switch]$Desinstalar,
    [string]$Destino,
    [string]$Usuario,
    [switch]$SinUsuario,
    [switch]$SinAccesoDirecto
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$Raiz = $PSScriptRoot
$Backend = Join-Path $Raiz 'backend'
$VenvPython = Join-Path $Backend 'venv\Scripts\python.exe'
$Icono = Join-Path $Raiz 'frontend\static\img\favicon.ico'
$Puerto = if ($env:SIETE_PUERTO) { [int]$env:SIETE_PUERTO } else { 8000 }
$NombreTarea = 'SIETE Servidor'
$NombreReglaFw = "S.I.E.T.E. servidor (TCP $Puerto)"
$NombreAcceso = 'S.I.E.T.E..lnk'
if (-not $Destino) { $Destino = [Environment]::GetFolderPath('Desktop') }

# Salida con acentos correcta en la consola y en lo que se envía a Python.
try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
} catch { }
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

# ------------------------------------------------------------------ utilidades
function Write-Paso($texto) { Write-Host ""; Write-Host "==> $texto" -ForegroundColor Cyan }
function Write-Ok($texto) { Write-Host "    $texto" -ForegroundColor Green }
function Write-Aviso($texto) { Write-Host "    AVISO: $texto" -ForegroundColor Yellow }
function Write-Detalle($texto) { Write-Host "    $texto" }
function Stop-ConError($texto) {
    Write-Host ""
    Write-Host "ERROR: $texto" -ForegroundColor Red
    exit 1
}

function Test-EsAdministrador {
    $identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identidad)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-Nativo {
    # Ejecuta un programa externo y devuelve su salida estándar (sin lanzar excepción por stderr).
    param([string]$Exe, [string[]]$Argumentos, [string]$Directorio, [string]$Entrada)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $psi.Arguments = ($Argumentos | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.RedirectStandardInput = ($null -ne $Entrada)
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    if ($Directorio) { $psi.WorkingDirectory = $Directorio }
    $proc = [System.Diagnostics.Process]::Start($psi)
    if ($null -ne $Entrada) {
        $escritor = New-Object System.IO.StreamWriter($proc.StandardInput.BaseStream, [System.Text.UTF8Encoding]::new($false))
        $escritor.Write($Entrada + "`n")
        $escritor.Flush()
        $escritor.Close()
    }
    $salida = $proc.StandardOutput.ReadToEnd()
    $errores = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    return [pscustomobject]@{ Codigo = $proc.ExitCode; Salida = $salida.Trim(); Errores = $errores.Trim() }
}

# ------------------------------------------------------------------ 1. Python
function Find-Python {
    # Devuelve la ruta del ejecutable de un Python 3.11+ (probando "py -3" y "python"), o $null.
    $candidatos = @(
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python'; Args = @() },
        @{ Exe = 'python3'; Args = @() }
    )
    $codigo = 'import sys; print("%d.%d|%s" % (sys.version_info[0], sys.version_info[1], sys.executable))'
    foreach ($c in $candidatos) {
        if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $r = Invoke-Nativo -Exe $c.Exe -Argumentos ($c.Args + @('-c', $codigo))
        } catch { continue }
        # El alias de la Tienda de Windows ("python" sin instalar) no imprime nada.
        if ($r.Codigo -ne 0 -or $r.Salida -notmatch '^(\d+)\.(\d+)\|(.+)$') { continue }
        $mayor = [int]$Matches[1]; $menor = [int]$Matches[2]; $ruta = $Matches[3]
        if ($mayor -gt 3 -or ($mayor -eq 3 -and $menor -ge 11)) {
            return [pscustomobject]@{ Ruta = $ruta; Version = "$mayor.$menor" }
        }
        Write-Aviso "Se encontró Python $mayor.$menor en $ruta, pero se necesita 3.11 o superior."
    }
    return $null
}

function Assert-Python {
    Write-Paso "Comprobando Python"
    $py = Find-Python
    if (-not $py) {
        Write-Host ""
        Write-Host "  No se encontró Python 3.11 o superior en este equipo." -ForegroundColor Red
        Write-Host "  1. Descargue el instalador de Windows (64 bits) desde https://www.python.org/downloads/windows/"
        Write-Host "  2. Al instalarlo marque la casilla 'Add python.exe to PATH' (agregar Python al PATH)."
        Write-Host "  3. Vuelva a ejecutar instalar.cmd."
        Stop-ConError "Falta Python. Este instalador no descarga programas por su cuenta."
    }
    Write-Ok "Python $($py.Version) en $($py.Ruta)"
    return $py
}

# ------------------------------------------------------------------ 2. Entorno virtual y dependencias
function Install-Entorno($py) {
    Write-Paso "Preparando el entorno de Python (backend\venv)"
    if (-not (Test-Path (Join-Path $Backend 'requirements.txt'))) {
        Stop-ConError "No se encuentra backend\requirements.txt. Ejecute este script desde la carpeta del simulador."
    }
    if (-not (Test-Path $VenvPython)) {
        Write-Detalle "Creando el entorno virtual..."
        & $py.Ruta -m venv (Join-Path $Backend 'venv')
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { Stop-ConError "No se pudo crear backend\venv." }
        Write-Ok "Entorno virtual creado."
    } else {
        Write-Ok "El entorno virtual ya existe."
    }

    $requisitos = Join-Path $Backend 'requirements.txt'
    $marca = Join-Path $Backend 'venv\.requisitos_instalados'
    $hash = (Get-FileHash -Path $requisitos -Algorithm SHA256).Hash
    if ((Test-Path $marca) -and ((Get-Content $marca -Raw).Trim() -eq $hash)) {
        Write-Ok "Las dependencias ya están instaladas (requirements.txt sin cambios)."
        return
    }
    Write-Detalle "Instalando las dependencias (puede tardar unos minutos la primera vez)..."
    & $VenvPython -m pip install --disable-pip-version-check -r $requisitos
    if ($LASTEXITCODE -ne 0) {
        Stop-ConError "pip no pudo instalar las dependencias. Revise la conexión a internet o el mensaje anterior."
    }
    Set-Content -Path $marca -Value $hash -Encoding ascii
    Write-Ok "Dependencias instaladas."
}

# ------------------------------------------------------------------ 3. Primer instructor
function Get-NumeroUsuarios {
    $codigo = @'
from app.db import SessionLocal, init_db
from app.models.usuario import Usuario
init_db()
with SessionLocal() as db:
    print(db.query(Usuario).count())
'@
    $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-c', $codigo) -Directorio $Backend
    if ($r.Codigo -ne 0) {
        Write-Host $r.Errores
        Stop-ConError "No se pudo abrir la base de datos del simulador."
    }
    return [int]($r.Salida -split "`n" | Select-Object -Last 1)
}

function ConvertFrom-SecureStringPlano([System.Security.SecureString]$s) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

function New-Instructor {
    Write-Paso "Primer usuario instructor"
    $n = Get-NumeroUsuarios
    if ($n -gt 0) {
        Write-Ok "La base ya tiene $n usuario(s); no se crea ninguno. (Para otro: venv\Scripts\python -m app.crear_usuario <nombre>)"
        return
    }
    if ($SinUsuario) {
        Write-Aviso "Sin usuarios en la base (-SinUsuario). Créelo con: cd backend && venv\Scripts\python -m app.crear_usuario <nombre> --rol instructor"
        return
    }
    if (-not [Environment]::UserInteractive) {
        Write-Aviso "No hay consola interactiva: no se puede pedir la contraseña. Cree el usuario con app.crear_usuario."
        return
    }
    Write-Detalle "No hay usuarios todavía. Se creará el instructor (director del ejercicio)."
    # Instalación desatendida: -Usuario <nombre> y la contraseña en la variable de entorno SIETE_CONTRASENA.
    $desatendida = ($Usuario -and $env:SIETE_CONTRASENA)
    try {
        $nombre = $Usuario
        while (-not $nombre) {
            $nombre = (Read-Host "    Nombre de usuario del instructor").Trim().ToLower()
            if ($nombre -and $nombre -notmatch '^[a-z0-9._-]{2,40}$') {
                Write-Aviso "Use solo letras, números, punto, guion o guion bajo (2 a 40 caracteres)."
                $nombre = ''
            }
        }
        for ($intento = 1; $intento -le 3; $intento++) {
            if ($desatendida) {
                $p1 = $env:SIETE_CONTRASENA; $p2 = $p1
            } else {
                $s1 = Read-Host "    Contraseña (mínimo 8 caracteres)" -AsSecureString
                $s2 = Read-Host "    Repita la contraseña" -AsSecureString
                $p1 = ConvertFrom-SecureStringPlano $s1
                $p2 = ConvertFrom-SecureStringPlano $s2
            }
            if ($p1 -ne $p2) { Write-Aviso "Las contraseñas no coinciden."; continue }
            if ($p1.Length -lt 8) { Write-Aviso "La contraseña debe tener al menos 8 caracteres."; if ($desatendida) { break }; continue }
            $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-m', 'app.crear_usuario', $nombre, '--rol', 'instructor', '--password-stdin') -Directorio $Backend -Entrada $p1
            $p1 = $null; $p2 = $null
            if ($r.Codigo -eq 0) { Write-Ok $r.Salida; return }
            Write-Aviso ("No se pudo crear el usuario: " + ($r.Salida + " " + $r.Errores).Trim())
            if ($desatendida) { break }
        }
    } catch {
        Write-Aviso "No se pudo pedir el usuario por consola ($($_.Exception.Message))."
    }
    Write-Aviso "No se creó el usuario. Puede crearlo después con: cd backend && venv\Scripts\python -m app.crear_usuario <nombre> --rol instructor"
}

# ------------------------------------------------------------------ 4. Escenario de demostración
function New-Demo {
    Write-Paso "Escenario de demostración"
    $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-m', 'app.crear_demo') -Directorio $Backend
    if ($r.Codigo -ne 0) { Write-Host $r.Errores; Write-Aviso "No se pudo crear el escenario de demostración."; return }
    Write-Ok $r.Salida
}

# ------------------------------------------------------------------ 5. Acceso directo
function New-AccesoDirecto {
    Write-Paso "Acceso directo"
    if (-not (Test-Path $Destino)) { New-Item -ItemType Directory -Path $Destino -Force | Out-Null }
    $ruta = Join-Path $Destino $NombreAcceso
    $shell = New-Object -ComObject WScript.Shell
    $acceso = $shell.CreateShortcut($ruta)
    $acceso.TargetPath = Join-Path $Raiz 'iniciar.cmd'
    $acceso.WorkingDirectory = $Raiz
    $acceso.Description = 'S.I.E.T.E. - Sistema Integral de Entrenamiento Táctico y Estratégico'
    if (Test-Path $Icono) { $acceso.IconLocation = "$Icono,0" }
    $acceso.WindowStyle = 7  # minimizada: la consola del servidor no estorba
    $acceso.Save()
    Write-Ok "Creado: $ruta"
}

function Remove-AccesoDirecto {
    $ruta = Join-Path $Destino $NombreAcceso
    if (Test-Path $ruta) { Remove-Item $ruta -Force; Write-Ok "Acceso directo eliminado: $ruta" }
    else { Write-Detalle "No había acceso directo en $Destino." }
}

# ------------------------------------------------------------------ 6. Tarea programada (arranque automático)
function Test-TareaExiste {
    $r = Invoke-Nativo -Exe 'schtasks' -Argumentos @('/Query', '/TN', $NombreTarea)
    return ($r.Codigo -eq 0)
}

function Register-Tarea($esAdmin) {
    Write-Paso "Arranque automático (tarea programada '$NombreTarea')"
    $comando = '"' + (Join-Path $Raiz 'iniciar.cmd') + '" /sin-navegador'
    if (-not $esAdmin) {
        Write-Aviso "Registrar el arranque automático requiere permisos de administrador; se omite."
        Write-Detalle "Cierre esta ventana, pulse con el botón derecho en instalar.cmd -> 'Ejecutar como administrador'"
        Write-Detalle "y vuelva a ejecutarlo con -Servicio (o ejecute como administrador:"
        Write-Host "      schtasks /Create /TN `"$NombreTarea`" /TR '$comando' /SC ONSTART /RU SYSTEM /RL HIGHEST /F )"
        return
    }
    # Al iniciar Windows, sin esperar a que nadie inicie sesión (cuenta SYSTEM, sin ventana ni navegador).
    $argumentos = @('/Create', '/TN', $NombreTarea, '/TR', $comando, '/SC', 'ONSTART', '/RU', 'SYSTEM', '/RL', 'HIGHEST', '/F')
    $r = Invoke-Nativo -Exe 'schtasks' -Argumentos $argumentos
    if ($r.Codigo -ne 0) {
        Write-Host ($r.Salida + "`n" + $r.Errores)
        Write-Aviso "No se pudo registrar la tarea programada."
        return
    }
    Write-Ok "Tarea '$NombreTarea' registrada: el servidor arrancará al iniciar Windows."
    Write-Detalle "Para arrancarlo ahora sin reiniciar: schtasks /Run /TN `"$NombreTarea`"  (o el acceso directo)."
}

function Unregister-Tarea {
    if (-not (Test-TareaExiste)) { Write-Detalle "No había tarea programada '$NombreTarea'."; return }
    $r = Invoke-Nativo -Exe 'schtasks' -Argumentos @('/Delete', '/TN', $NombreTarea, '/F')
    if ($r.Codigo -eq 0) { Write-Ok "Tarea programada '$NombreTarea' eliminada." }
    else { Write-Host $r.Errores; Write-Aviso "No se pudo eliminar la tarea (¿hace falta ser administrador?)." }
}

# ------------------------------------------------------------------ 7. Cortafuegos
function Test-ReglaFirewall {
    $r = Invoke-Nativo -Exe 'netsh' -Argumentos @('advfirewall', 'firewall', 'show', 'rule', "name=$NombreReglaFw")
    return ($r.Codigo -eq 0)
}

function Open-Firewall($esAdmin) {
    Write-Paso "Cortafuegos de Windows (puerto TCP $Puerto para los alumnos de la red local)"
    $comando = "netsh advfirewall firewall add rule name=`"$NombreReglaFw`" dir=in action=allow protocol=TCP localport=$Puerto"
    if (Test-ReglaFirewall) { Write-Ok "La regla '$NombreReglaFw' ya existe."; return }
    if (-not $esAdmin) {
        Write-Aviso "Sin permisos de administrador no se puede abrir el puerto. Ejecute como administrador:"
        Write-Host "      $comando"
        Write-Detalle "(Sin la regla, el simulador funciona en este equipo; los demás equipos de la red no podrán entrar.)"
        return
    }
    $r = Invoke-Nativo -Exe 'netsh' -Argumentos @('advfirewall', 'firewall', 'add', 'rule', "name=$NombreReglaFw", 'dir=in', 'action=allow', 'protocol=TCP', "localport=$Puerto")
    if ($r.Codigo -eq 0) { Write-Ok "Regla '$NombreReglaFw' creada." }
    else { Write-Host $r.Salida; Write-Aviso "No se pudo crear la regla del cortafuegos." }
}

function Close-Firewall($esAdmin) {
    if (-not (Test-ReglaFirewall)) { Write-Detalle "No había regla del cortafuegos '$NombreReglaFw'."; return }
    if (-not $esAdmin) {
        Write-Aviso "Para quitar la regla del cortafuegos ejecute como administrador:"
        Write-Host "      netsh advfirewall firewall delete rule name=`"$NombreReglaFw`""
        return
    }
    $r = Invoke-Nativo -Exe 'netsh' -Argumentos @('advfirewall', 'firewall', 'delete', 'rule', "name=$NombreReglaFw")
    if ($r.Codigo -eq 0) { Write-Ok "Regla del cortafuegos eliminada." } else { Write-Host $r.Salida }
}

# ------------------------------------------------------------------ principal
Write-Host ""
Write-Host "S.I.E.T.E. - Sistema Integral de Entrenamiento Táctico y Estratégico" -ForegroundColor White
Write-Host "Carpeta: $Raiz"
$esAdmin = Test-EsAdministrador
if ($esAdmin) { Write-Host "Ejecutando como administrador." } else { Write-Host "Ejecutando sin permisos de administrador." }

if ($Desinstalar) {
    Write-Paso "Desinstalando el arranque automático y los accesos"
    Unregister-Tarea
    Remove-AccesoDirecto
    Close-Firewall $esAdmin
    Write-Host ""
    Write-Host "Listo. La base de datos (backend\simulador_fenix.db), los respaldos y el entorno de Python se conservan;"
    Write-Host "para eliminarlos por completo borre la carpeta del simulador."
    exit 0
}

$py = Assert-Python
Install-Entorno $py
New-Instructor
if ($Demo) { New-Demo }
if (-not $SinAccesoDirecto) { New-AccesoDirecto }
if ($Servicio) { Register-Tarea $esAdmin }
Open-Firewall $esAdmin

Write-Host ""
Write-Host "Instalación terminada." -ForegroundColor Green
Write-Host "  - Para arrancar: doble clic en el acceso directo 'S.I.E.T.E.' (o en iniciar.cmd)."
Write-Host "  - Se abre http://localhost:$Puerto/ ; los alumnos entran por http://<ip-de-este-equipo>:$Puerto/"
Write-Host "  - Para parar el servidor: cerrar su ventana o ejecutar detener.cmd."
if (-not $Servicio) { Write-Host "  - Para que arranque solo con Windows: instalar.cmd -Servicio (como administrador)." }
exit 0
