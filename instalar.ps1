<#
.SYNOPSIS
    Instala S.I.E.T.E. (Simulador Fénix) en un PC con Windows: entorno de Python, dependencias,
    datos de mapa, primer usuario instructor, acceso directo en el Escritorio y, opcionalmente,
    arranque automático, PostgreSQL y HTTPS. También actualiza una instalación existente.

.DESCRIPTION
    Uso normal: doble clic en instalar.cmd (que ejecuta este script). Opciones:

      -Demo           crea además el escenario de demostración (Andes/Llanos).
      -Servicio       registra la tarea programada "SIETE Servidor" para que el servidor arranque solo
                      (al iniciar Windows si se ejecuta como administrador; si no, al iniciar sesión).
      -Desinstalar    quita la tarea programada, el acceso directo y la regla del cortafuegos.
                      No borra la base de datos ni el entorno de Python.
      -Actualizar     actualiza una instalación existente: respalda la base de datos en backend\respaldos,
                      trae el código nuevo (git pull --ff-only si la carpeta es un repositorio y hay git;
                      si no, descarga el zip de GitHub y sobrescribe todo salvo la base de datos, los
                      respaldos, los certificados, .env y los datos de mapa), reinstala las dependencias,
                      aplica las migraciones y reinicia la tarea programada si existe. (Atajo: actualizar.cmd)
      -Datos <zip>    instala los datos de mapa desde un zip ya descargado (siete_datos_*.zip) o una URL.
                      Sin esta opción, si faltan los datos se ofrece descargarlos de la URL configurada
                      al inicio de este script ($DatosUrl: release de GitHub siete_datos.zip).
      -SinDatos       no pregunta ni descarga los datos de mapa.
      -Postgres <url> usa PostgreSQL: postgresql://usuario:clave@host:5432/base. Se guarda en backend\.env
                      (SIMULADOR_DATABASE_URL), se prueba la conexión y se aplican las migraciones.
                      La clave nunca se muestra en pantalla ni queda en registros.
      -Https          genera un certificado autofirmado en backend\certs (con Python cryptography o
                      New-SelfSignedCertificate) y deja iniciar.cmd / la tarea programada arrancando
                      con HTTPS en el puerto 8443 (SIETE_HTTPS=1 en backend\.env).
      -Destino <dir>  carpeta donde crear el acceso directo (por defecto, el Escritorio).
      -Usuario <nombre>  con la variable SIETE_CONTRASENA, crea ese instructor en lugar de la cuenta admin
                      (instalación desatendida). Sin estas opciones se crea "admin" con la contraseña
                      inicial siete1234, que se pide cambiar al entrar por primera vez.
      -SinUsuario     no crea ningún usuario (el servidor crea "admin" igualmente al arrancar con la base vacía).
      -SinAccesoDirecto  no crea el acceso directo.

    El script nunca descarga instaladores de programas: si falta Python, indica de dónde bajarlo y se
    detiene. Solo descarga (previa confirmación) el paquete de datos de mapa y, con -Actualizar sin git,
    el código del propio simulador. Variables de entorno respetadas: SIMULADOR_DB (otra base SQLite),
    SIMULADOR_DATABASE_URL (PostgreSQL), SIETE_PUERTO (puerto, 8000 u 8443 con HTTPS); también se leen
    de backend\.env.

.EXAMPLE
    instalar.cmd
    instalar.cmd -Demo
    instalar.cmd -Servicio          (como administrador: arranque con Windows + cortafuegos)
    instalar.cmd -Datos D:\siete_datos_20260930.zip
    instalar.cmd -Postgres "postgresql://simulador:clave@localhost:5432/simulador"
    instalar.cmd -Https -Servicio
    instalar.cmd -Actualizar        (o actualizar.cmd)
    instalar.cmd -Desinstalar
#>
[CmdletBinding()]
param(
    [switch]$Demo,
    [switch]$Servicio,
    [switch]$Desinstalar,
    [switch]$Actualizar,
    [string]$Destino,
    [string]$Usuario,
    [switch]$SinUsuario,
    [switch]$SinAccesoDirecto,
    [string]$Datos,
    [switch]$SinDatos,
    [string]$Postgres,
    [switch]$Https
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

# ------------------------------------------------------------------ configuración
# Paquete de datos de mapa (release de GitHub; se genera con tools\empaquetar_datos.py --nombre siete_datos).
$DatosUrl = "https://github.com/Dixondarioms/simulador-fenix/releases/latest/download/siete_datos.zip"
# Código del simulador para -Actualizar cuando la carpeta no es un repositorio git.
$CodigoZipUrl = "https://github.com/Dixondarioms/simulador-fenix/archive/refs/heads/main.zip"
# Rutas (relativas a la raíz, con /) que -Actualizar sin git nunca sobrescribe.
$ConservarEnActualizacion = @('backend/simulador_fenix.db', 'backend/respaldos', 'backend/certs', 'backend/.env', '.env',
                              'backend/venv', 'backend/data/terreno', 'frontend/static/tiles', 'frontend/static/tiles_sat',
                              'frontend/static/geo', 'dist')

$Raiz = $PSScriptRoot
$Backend = Join-Path $Raiz 'backend'
$VenvPython = Join-Path $Backend 'venv\Scripts\python.exe'
$ArchivoEnv = Join-Path $Backend '.env'
$Icono = Join-Path $Raiz 'frontend\static\img\icono_escritorio.ico'
$NombreTarea = 'SIETE Servidor'
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

# ------------------------------------------------------------------ backend\.env (configuración persistente)
function Import-ArchivoEnv {
    # Carga backend\.env en el entorno de este proceso sin pisar las variables ya definidas, para que
    # el script y los comandos de Python vean la base de datos y el puerto configurados.
    if (-not (Test-Path $ArchivoEnv)) { return }
    foreach ($linea in @(Get-Content $ArchivoEnv -Encoding UTF8)) {
        $l = "$linea".Trim()
        if (-not $l -or $l.StartsWith('#') -or $l -notmatch '^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { continue }
        $clave = $Matches[1]; $valor = $Matches[2].Trim()
        if ($valor.Length -ge 2 -and ($valor[0] -eq '"' -or $valor[0] -eq "'") -and $valor[0] -eq $valor[-1]) {
            $valor = $valor.Substring(1, $valor.Length - 2)
        }
        if (-not [Environment]::GetEnvironmentVariable($clave)) { [Environment]::SetEnvironmentVariable($clave, $valor) }
    }
}

function Set-VariableEnv([string]$Clave, [string]$Valor) {
    # Escribe o reemplaza CLAVE=valor en backend\.env conservando el resto de líneas (también sustituye la
    # línea comentada "# CLAVE=..."). El valor no se muestra nunca. Queda activo en este proceso.
    $lineas = @()
    if (Test-Path $ArchivoEnv) { $lineas = @(Get-Content $ArchivoEnv -Encoding UTF8) }
    $patron = '^\s*#?\s*' + [regex]::Escape($Clave) + '\s*='
    $nuevas = @(); $reemplazada = $false
    foreach ($l in $lineas) {
        if (-not $reemplazada -and "$l" -match $patron) { $nuevas += "$Clave=$Valor"; $reemplazada = $true }
        else { $nuevas += "$l" }
    }
    if (-not $reemplazada) {
        if ($nuevas.Count -eq 0) { $nuevas += '# Configuración de S.I.E.T.E. (la escribe instalar.cmd; no se sube al repositorio).' }
        $nuevas += "$Clave=$Valor"
    }
    [IO.File]::WriteAllLines($ArchivoEnv, [string[]]$nuevas, [System.Text.UTF8Encoding]::new($false))
    [Environment]::SetEnvironmentVariable($Clave, $Valor)
}

function Get-ClaveSecreta {
    # Contraseña de la URL de PostgreSQL (de -Postgres o de la variable ya configurada), para ocultarla.
    foreach ($u in @($Postgres, $env:SIMULADOR_DATABASE_URL, $env:DATABASE_URL)) {
        if ($u -and $u -match '://[^:/@]+:([^@]+)@') { return $Matches[1] }
    }
    return $null
}

function Protect-Texto([string]$texto) {
    # Quita la contraseña de PostgreSQL de cualquier mensaje antes de mostrarlo.
    if (-not $texto) { return $texto }
    $clave = Get-ClaveSecreta
    if ($clave) { $texto = $texto.Replace($clave, '***').Replace([Uri]::EscapeDataString($clave), '***') }
    return ($texto -replace '(://[^:/@\s]+:)[^@\s]*@', '$1***@')
}

Import-ArchivoEnv
if ($Https -and -not $env:SIETE_PUERTO) { $env:SIETE_PUERTO = '8443' }
$Puerto = if ($env:SIETE_PUERTO) { [int]$env:SIETE_PUERTO } else { 8000 }
$Esquema = if ($Https -or $env:SIETE_HTTPS -eq '1') { 'https' } else { 'http' }
$NombreReglaFw = "S.I.E.T.E. servidor (TCP $Puerto)"

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
function Install-Entorno($py, [switch]$Forzar) {
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
    if (-not $Forzar -and (Test-Path $marca) -and ((Get-Content $marca -Raw).Trim() -eq $hash)) {
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

# ------------------------------------------------------------------ 3. Datos de mapa
function Test-DatosMapa {
    return ((Test-Path (Join-Path $Backend 'data\terreno\venezuela\meta.json')) -and
            (Test-Path (Join-Path $Raiz 'frontend\static\tiles\venezuela')))
}

function Install-DatosMapa {
    Write-Paso "Datos de mapa (teselas, vectores y grilla de terreno)"
    if ((Test-DatosMapa) -and -not $Datos) { Write-Ok "Los datos de mapa ya están en su sitio."; return }
    $script = Join-Path $Raiz 'tools\instalar_datos.py'
    if ($Datos) {
        if ($Datos -match '^https?://') {
            $argumentos = @($script, $Datos)
        } else {
            if (-not (Test-Path $Datos)) { Stop-ConError "No existe el archivo de datos $Datos" }
            $argumentos = @($script, '--zip', (Resolve-Path $Datos).Path)
        }
    } else {
        if ($SinDatos) { Write-Aviso "Faltan los datos de mapa (-SinDatos): el mapa saldrá vacío hasta instalarlos."; return }
        Write-Detalle "Faltan los datos de mapa (unos 550 MB con la foto satelital). Se pueden descargar de:"
        Write-Detalle "  $DatosUrl"
        Write-Detalle "o instalar desde un zip ya descargado con:  instalar.cmd -Datos <ruta\siete_datos.zip>"
        if (-not [Environment]::UserInteractive) { Write-Aviso "Sin consola interactiva: no se descargan."; return }
        $respuesta = Read-Host "    ¿Descargar ahora? [S/n]"
        if ($respuesta -and $respuesta.Trim().ToLower().StartsWith('n')) {
            Write-Aviso "Sin datos de mapa el mapa sale vacío y todo el terreno es llano. Instálelos después con -Datos."
            return
        }
        $argumentos = @($script, $DatosUrl)
    }
    # Salida directa a la consola (barra de progreso). La descarga se reanuda si se corta.
    & $VenvPython @argumentos
    if ($LASTEXITCODE -ne 0) {
        Write-Aviso "No se pudieron instalar los datos de mapa (código $LASTEXITCODE)."
        Write-Detalle "Reintente con: backend\venv\Scripts\python tools\instalar_datos.py $DatosUrl"
        return
    }
    Write-Ok "Datos de mapa instalados."
}

# ------------------------------------------------------------------ 4. PostgreSQL
function Invoke-Migraciones {
    Write-Paso "Migraciones de la base de datos"
    $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-c', 'from app.db import migrar; migrar()') -Directorio $Backend
    if ($r.Codigo -ne 0) { Write-Host (Protect-Texto $r.Errores); Stop-ConError "Fallaron las migraciones de la base de datos." }
    Write-Ok "Base de datos al día."
}

function Set-Postgres {
    Write-Paso "PostgreSQL"
    if ($Postgres -notmatch '^postgres(ql)?(\+psycopg)?://\S+') {
        Stop-ConError "-Postgres espera una URL con la forma postgresql://usuario:clave@host:5432/base"
    }
    Write-Detalle ("Base: " + (Protect-Texto $Postgres))
    Set-VariableEnv 'SIMULADOR_DATABASE_URL' $Postgres
    Write-Ok "Guardado en backend\.env (SIMULADOR_DATABASE_URL). La clave no se muestra ni se registra."
    # Prueba de conexión: la URL viaja por el entorno, nunca por la línea de comandos.
    $codigo = @'
import os, re, sys
try:
    import psycopg
except ImportError:
    print("SIN_PSYCOPG"); sys.exit(0)
url = re.sub(r"^postgres(ql)?(\+psycopg)?://", "postgresql://", os.environ["SIMULADOR_DATABASE_URL"])
with psycopg.connect(url, connect_timeout=10) as con:
    print(con.execute("select version()").fetchone()[0])
'@
    $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-c', $codigo) -Directorio $Backend
    if ($r.Codigo -ne 0) {
        Write-Host (Protect-Texto ($r.Salida + "`n" + $r.Errores))
        Stop-ConError "No se pudo conectar con PostgreSQL. Compruebe que el servidor está en marcha, la base existe y el usuario tiene permisos."
    }
    if ($r.Salida -eq 'SIN_PSYCOPG') { Write-Aviso "psycopg no está instalado: no se probó la conexión." }
    else { Write-Ok ("Conexión correcta: " + ($r.Salida -split "`n" | Select-Object -Last 1)) }
    Invoke-Migraciones
}

# ------------------------------------------------------------------ 5. HTTPS
function ConvertTo-Pem([string]$etiqueta, [byte[]]$bytes) {
    $b64 = [Convert]::ToBase64String($bytes)
    $lineas = for ($i = 0; $i -lt $b64.Length; $i += 64) { $b64.Substring($i, [Math]::Min(64, $b64.Length - $i)) }
    return "-----BEGIN $etiqueta-----`n" + ($lineas -join "`n") + "`n-----END $etiqueta-----`n"
}

function New-CertificadoPowerShell([string]$carpeta) {
    # Certificado con New-SelfSignedCertificate exportado a PEM. Exportar la clave privada a PKCS#8 requiere
    # .NET Core (PowerShell 7); en Windows PowerShell 5.1 se avisa y se devuelve $false.
    if (-not (Get-Command New-SelfSignedCertificate -ErrorAction SilentlyContinue)) { return $false }
    try {
        $ips = @('127.0.0.1') + @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                                  ForEach-Object { $_.IPAddress } | Where-Object { $_ -notlike '169.254.*' })
        $san = (@("DNS=localhost", "DNS=$env:COMPUTERNAME") + ($ips | Sort-Object -Unique | ForEach-Object { "IPAddress=$_" })) -join '&'
        $c = New-SelfSignedCertificate -Subject 'CN=S.I.E.T.E.' -TextExtension @("2.5.29.17={text}$san") `
            -CertStoreLocation 'Cert:\CurrentUser\My' -FriendlyName 'S.I.E.T.E. (autofirmado)' -NotAfter (Get-Date).AddYears(2) `
            -KeyExportPolicy Exportable -KeyAlgorithm RSA -KeyLength 2048
        try {
            $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($c)
            if (-not ($rsa | Get-Member -Name ExportPkcs8PrivateKey -ErrorAction SilentlyContinue)) {
                Write-Aviso "Esta versión de PowerShell no puede exportar la clave privada a PEM (hace falta PowerShell 7 o Python cryptography)."
                return $false
            }
            New-Item -ItemType Directory -Path $carpeta -Force | Out-Null
            [IO.File]::WriteAllText((Join-Path $carpeta 'cert.pem'), (ConvertTo-Pem 'CERTIFICATE' $c.RawData))
            [IO.File]::WriteAllText((Join-Path $carpeta 'key.pem'), (ConvertTo-Pem 'PRIVATE KEY' $rsa.ExportPkcs8PrivateKey()))
        } finally {
            # Ya está en PEM: no hace falta dejarlo en el almacén de certificados.
            Remove-Item ("Cert:\CurrentUser\My\" + $c.Thumbprint) -ErrorAction SilentlyContinue
        }
        Write-Ok "Certificado generado con New-SelfSignedCertificate."
        return $true
    } catch {
        Write-Aviso "New-SelfSignedCertificate falló: $($_.Exception.Message)"
        return $false
    }
}

function New-CertificadoHttps {
    Write-Paso "HTTPS (certificado autofirmado en backend\certs)"
    $certs = Join-Path $Backend 'certs'
    if ((Test-Path (Join-Path $certs 'cert.pem')) -and (Test-Path (Join-Path $certs 'key.pem'))) {
        Write-Ok "Ya existe backend\certs\cert.pem; se conserva (bórrelo para generar otro)."
    } else {
        $hecho = $false
        # 1) Python + cryptography (viene en requirements.txt): incluye localhost, el nombre del equipo y las IP locales.
        $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-c', 'import cryptography') -Directorio $Backend
        if ($r.Codigo -eq 0) {
            $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-m', 'app.gen_cert') -Directorio $Backend
            if ($r.Codigo -eq 0) { $hecho = $true; Write-Ok "Certificado generado con Python (cryptography)." }
            else { Write-Host $r.Errores }
        }
        # 2) PowerShell (New-SelfSignedCertificate), si lo anterior no fue posible.
        if (-not $hecho) { $hecho = New-CertificadoPowerShell $certs }
        if (-not $hecho) {
            Stop-ConError "No se pudo generar el certificado. Instale cryptography (backend\venv\Scripts\python -m pip install cryptography) o copie cert.pem y key.pem a backend\certs."
        }
    }
    Set-VariableEnv 'SIETE_HTTPS' '1'
    Set-VariableEnv 'SIETE_PUERTO' "$Puerto"
    Write-Ok "iniciar.cmd y la tarea programada arrancarán con HTTPS en el puerto $Puerto (backend\.env)."
    Write-Aviso "Certificado autofirmado: el navegador mostrará un aviso de seguridad la primera vez en cada equipo"
    Write-Detalle "(«La conexión no es privada»: pulse Avanzado -> Continuar). Para evitarlo, instale backend\certs\cert.pem"
    Write-Detalle "como certificado de confianza en cada estación (README, sección HTTPS)."
}

# ------------------------------------------------------------------ 6. Primer instructor
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
        Write-Host (Protect-Texto $r.Errores)
        Stop-ConError "No se pudo abrir la base de datos del simulador."
    }
    return [int]($r.Salida -split "`n" | Select-Object -Last 1)
}

function New-Instructor {
    Write-Paso "Cuenta del administrador"
    $n = Get-NumeroUsuarios
    if ($n -gt 0) {
        Write-Ok "La base ya tiene $n usuario(s); no se crea ninguno. (Para recuperar el acceso: cd backend && venv\Scripts\python -m app.restablecer_admin)"
        return
    }
    if ($SinUsuario) {
        Write-Aviso "Sin usuarios en la base (-SinUsuario). Al arrancar, el servidor crea la cuenta admin con la contraseña inicial."
        return
    }
    # Instalación desatendida: -Usuario <nombre> y la contraseña en la variable de entorno SIETE_CONTRASENA.
    if ($Usuario -and $env:SIETE_CONTRASENA) {
        $nombre = $Usuario.Trim().ToLower()
        if ($env:SIETE_CONTRASENA.Length -lt 8) {
            Write-Aviso "SIETE_CONTRASENA debe tener al menos 8 caracteres: se crea la cuenta admin en su lugar."
        } else {
            $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-m', 'app.crear_usuario', $nombre, '--rol', 'instructor', '--password-stdin') -Directorio $Backend -Entrada $env:SIETE_CONTRASENA
            if ($r.Codigo -eq 0) { Write-Ok $r.Salida; return }
            Write-Aviso ("No se pudo crear el usuario: " + (Protect-Texto ($r.Salida + " " + $r.Errores)).Trim())
        }
    }
    # Cuenta admin con la contraseña inicial: se pide cambiarla al entrar por primera vez. Los demás usuarios
    # se solicitan desde la pantalla de acceso y el instructor los aprueba (o los crea él en el panel Usuarios).
    $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-m', 'app.restablecer_admin', '--si-no-hay-usuarios') -Directorio $Backend
    if ($r.Codigo -ne 0) {
        Write-Aviso ("No se pudo crear la cuenta admin: " + (Protect-Texto $r.Errores).Trim())
        Write-Aviso "Al arrancar, el servidor la crea igualmente si la base no tiene usuarios."
        return
    }
    Write-Ok "Cuenta del administrador creada."
    Write-Detalle "Usuario: admin    Contraseña inicial: siete1234"
    Write-Detalle "Al entrar por primera vez se le pedirá elegir una contraseña nueva."
}

# ------------------------------------------------------------------ 7. Escenario de demostración
function New-Demo {
    Write-Paso "Escenario de demostración"
    $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-m', 'app.crear_demo') -Directorio $Backend
    if ($r.Codigo -ne 0) { Write-Host (Protect-Texto $r.Errores); Write-Aviso "No se pudo crear el escenario de demostración."; return }
    Write-Ok $r.Salida
}

# ------------------------------------------------------------------ 8. Acceso directo
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

# ------------------------------------------------------------------ 9. Tarea programada (arranque automático)
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

function Restart-Tarea($esAdmin) {
    # Tras actualizar (o activar HTTPS): para el servidor que dejó la tarea y la vuelve a lanzar.
    if (-not (Test-TareaExiste)) { return }
    Write-Paso "Reiniciando la tarea programada '$NombreTarea'"
    if (-not $esAdmin) {
        Write-Aviso "Hace falta ser administrador para reiniciar la tarea. Reinicie el equipo o ejecute como administrador:"
        Write-Host "      schtasks /End /TN `"$NombreTarea`" & detener.cmd /silencioso & schtasks /Run /TN `"$NombreTarea`""
        return
    }
    Invoke-Nativo -Exe 'schtasks' -Argumentos @('/End', '/TN', $NombreTarea) | Out-Null
    # schtasks /End solo cierra el cmd de la tarea: el servidor de Python se para con detener.cmd.
    & (Join-Path $Raiz 'detener.cmd') /silencioso
    $r = Invoke-Nativo -Exe 'schtasks' -Argumentos @('/Run', '/TN', $NombreTarea)
    if ($r.Codigo -eq 0) { Write-Ok "Tarea '$NombreTarea' reiniciada." }
    else { Write-Host ($r.Salida + "`n" + $r.Errores); Write-Aviso "No se pudo reiniciar la tarea." }
}

# ------------------------------------------------------------------ 10. Cortafuegos
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

# ------------------------------------------------------------------ 11. Actualización
function Backup-BaseDatos {
    Write-Paso "Respaldo de la base de datos (backend\respaldos)"
    if (-not (Test-Path $VenvPython)) { Stop-ConError "No existe backend\venv: ejecute instalar.cmd (sin -Actualizar) primero." }
    $r = Invoke-Nativo -Exe $VenvPython -Argumentos @('-m', 'app.respaldo') -Directorio $Backend
    if ($r.Codigo -eq 0 -and $r.Salida -match 'Respaldo creado') { Write-Ok $r.Salida; return }
    Write-Host (Protect-Texto ($r.Salida + "`n" + $r.Errores))
    Write-Aviso "No se pudo respaldar la base de datos (con PostgreSQL hace falta pg_dump en el PATH)."
    if (-not [Environment]::UserInteractive) { Stop-ConError "No se actualiza sin respaldo." }
    $respuesta = Read-Host "    ¿Continuar la actualización sin respaldo? [s/N]"
    if (-not ($respuesta -and $respuesta.Trim().ToLower().StartsWith('s'))) { Stop-ConError "Actualización cancelada." }
}

function Copy-ArbolConservando([string]$origen, [string]$destino) {
    # Copia todos los archivos de $origen sobre $destino salvo los de $ConservarEnActualizacion y las bases *.db.
    $n = 0
    foreach ($f in @(Get-ChildItem -Path $origen -Recurse -File)) {
        $rel = ($f.FullName.Substring($origen.Length).TrimStart('\', '/')) -replace '\\', '/'
        $conservar = ($rel -like '*.db')
        foreach ($c in $ConservarEnActualizacion) { if ($rel -eq $c -or $rel.StartsWith($c + '/')) { $conservar = $true; break } }
        if ($conservar) { continue }
        $ruta = Join-Path $destino ($rel -replace '/', '\')
        $dir = Split-Path $ruta -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Copy-Item -Path $f.FullName -Destination $ruta -Force
        $n++
    }
    return $n
}

function Update-Codigo {
    Write-Paso "Código nuevo"
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ((Test-Path (Join-Path $Raiz '.git')) -and $git) {
        Write-Detalle "La carpeta es un repositorio git: git pull --ff-only"
        & $git.Source -C $Raiz pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            Stop-ConError "git pull falló. Si hay cambios locales, guárdelos (git stash) o resuelva el conflicto y vuelva a ejecutar actualizar.cmd."
        }
        Write-Ok "Código actualizado con git."
        return
    }
    Write-Detalle "Sin git: se descarga el código de $CodigoZipUrl"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('siete_actualizacion_' + [IO.Path]::GetRandomFileName().Replace('.', ''))
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    $zip = Join-Path $tmp 'codigo.zip'
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $CodigoZipUrl -OutFile $zip -UseBasicParsing
        Expand-Archive -Path $zip -DestinationPath $tmp -Force
    } catch {
        Stop-ConError "No se pudo descargar el código: $($_.Exception.Message)"
    }
    $origen = Get-ChildItem -Path $tmp -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'backend\requirements.txt') } | Select-Object -First 1
    if (-not $origen) { Stop-ConError "El zip descargado no tiene la estructura esperada (falta backend\requirements.txt)." }
    $n = Copy-ArbolConservando $origen.FullName $Raiz
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Write-Ok "Código actualizado desde GitHub ($n archivos copiados). Base de datos, respaldos, certificados, .env y datos de mapa conservados."
}

function Update-Simulador($esAdmin) {
    Backup-BaseDatos
    Update-Codigo
    $py = Assert-Python
    Install-Entorno $py -Forzar
    Invoke-Migraciones
    Restart-Tarea $esAdmin
    # Si ya hay acceso directo, se rehace para que tome el icono vigente.
    if (Test-Path (Join-Path $Destino $NombreAcceso)) { New-AccesoDirecto }
    Write-Host ""
    Write-Host "Actualización terminada." -ForegroundColor Green
    if (-not (Test-TareaExiste)) { Write-Host "  - Si el servidor estaba en marcha, ciérrelo (detener.cmd) y vuelva a abrirlo con el acceso directo." }
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

if ($Actualizar) {
    Update-Simulador $esAdmin
    exit 0
}

$py = Assert-Python
Install-Entorno $py
if ($Postgres) { Set-Postgres }
Install-DatosMapa
New-Instructor
if ($Demo) { New-Demo }
if ($Https) { New-CertificadoHttps }
if (-not $SinAccesoDirecto) { New-AccesoDirecto }
if ($Servicio) { Register-Tarea $esAdmin } elseif ($Https) { Restart-Tarea $esAdmin }
Open-Firewall $esAdmin

Write-Host ""
Write-Host "Instalación terminada." -ForegroundColor Green
Write-Host "  - Para arrancar: doble clic en el acceso directo 'S.I.E.T.E.' (o en iniciar.cmd)."
Write-Host "  - Se abre ${Esquema}://localhost:$Puerto/ ; los alumnos entran por ${Esquema}://<ip-de-este-equipo>:$Puerto/"
Write-Host "  - Para parar el servidor: cerrar su ventana o ejecutar detener.cmd."
if (-not $Servicio) { Write-Host "  - Para que arranque solo con Windows: instalar.cmd -Servicio (como administrador)." }
Write-Host "  - Para actualizar más adelante: actualizar.cmd (respalda la base, trae el código nuevo y migra)."
exit 0
