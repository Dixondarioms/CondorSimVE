#!/data/data/com.termux/files/usr/bin/bash
# Instala el Cóndor directamente desde Condor_Android.zip en Descargas, sin descomprimirlo a mano (lo descomprime
# dentro de Termux, que es más rápido y no depende del administrador de archivos). Desde Termux, con internet:
#
#     termux-setup-storage
#     bash ~/storage/downloads/instalar_desde_zip.sh
#
# Deja el registro en Descargas/condor_instalacion.log (se puede leer desde la PC).
ZIP="${1:-$HOME/storage/downloads/Condor_Android.zip}"
REGISTRO="$HOME/storage/downloads/condor_instalacion.log"
TEMP="$HOME/paquete_condor"
{
    set -e
    echo "== Cóndor: instalación desde $ZIP ($(date)) =="
    [ -f "$ZIP" ] || { echo "No encuentro $ZIP"; exit 1; }
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get -y install unzip
    rm -rf "$TEMP"
    mkdir -p "$TEMP"
    echo "-- Descomprimiendo el paquete (unos minutos)..."
    unzip -q -o "$ZIP" -d "$TEMP"
    # un instalar_condor.sh más nuevo puesto en Descargas reemplaza al del paquete
    if [ -f "$HOME/storage/downloads/instalar_condor.sh" ]; then
        cp -f "$HOME/storage/downloads/instalar_condor.sh" "$TEMP/Condor_Android/android/instalar_condor.sh"
    fi
    bash "$TEMP/Condor_Android/android/instalar_condor.sh"
    rm -rf "$TEMP"
    echo "== INSTALACION TERMINADA =="
} 2>&1 | tee "$REGISTRO"
exit "${PIPESTATUS[0]}"
