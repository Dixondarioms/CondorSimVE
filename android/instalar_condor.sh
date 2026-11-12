#!/data/data/com.termux/files/usr/bin/bash
# Instala el Cóndor completo en una tablet Android, dentro de Termux (servidor, mapas y base propia; funciona sin
# internet y sin la PC). Se ejecuta una sola vez, con internet, desde Termux:
#
#     termux-setup-storage                                  (permite leer la carpeta Descargas)
#     bash ~/storage/downloads/Condor_Android/android/instalar_condor.sh
#
# Copia el Cóndor a ~/condor, instala Python y sus paquetes (la primera vez tarda: compila una parte) y crea el
# acceso «Cóndor» para la pantalla de inicio (widget de Termux:Widget). Se puede repetir para actualizar: no borra la
# base de datos de la tablet si ya existe.
set -e

ORIGEN="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$HOME/condor"

echo "== Cóndor para Android =="
echo "Origen: $ORIGEN"
echo "Destino: $DESTINO"

if [ ! -f "$ORIGEN/backend/app/main.py" ]; then
    echo "No encuentro el Cóndor junto a este script (falta backend/app/main.py)." >&2
    exit 1
fi

echo "-- 1/4 Paquetes de Termux (Python, imágenes y compiladores)..."
pkg update -y
pkg install -y python python-pip python-pillow rust binutils clang make curl

echo "-- 2/4 Copiando el Cóndor (mapas incluidos; puede tardar unos minutos)..."
mkdir -p "$DESTINO"
BASE_PREVIA=""
if [ -f "$DESTINO/backend/simulador_fenix.db" ]; then
    BASE_PREVIA="$DESTINO/backend/simulador_fenix.db.conservada"
    cp -f "$DESTINO/backend/simulador_fenix.db" "$BASE_PREVIA"
    echo "   (la base de datos que ya tenía la tablet se conserva)"
fi
cp -rf "$ORIGEN/backend" "$ORIGEN/frontend" "$ORIGEN/android" "$DESTINO/"
if [ -n "$BASE_PREVIA" ]; then
    mv -f "$BASE_PREVIA" "$DESTINO/backend/simulador_fenix.db"
fi
chmod +x "$DESTINO"/android/*.sh

echo "-- 3/4 Paquetes de Python (la primera vez compila pydantic: 10 a 30 minutos)..."
cd "$DESTINO"
if [ ! -d venv ]; then
    python -m venv --system-site-packages venv
fi
# pydantic-core se compila con Rust; estas variables le dicen a qué Android apunta
export ANDROID_API_LEVEL="$(getprop ro.build.version.sdk)"
export DISABLE_SQLALCHEMY_CEXT=1
./venv/bin/python -m pip install --upgrade pip wheel
./venv/bin/python -m pip install -r android/requirements-android.txt

echo "-- 4/4 Acceso directo «Cóndor» y comandos..."
mkdir -p "$HOME/.shortcuts" "$HOME/bin"
cp -f android/condor.sh "$HOME/.shortcuts/Condor"
cp -f android/detener.sh "$HOME/.shortcuts/Detener Condor"
chmod +x "$HOME/.shortcuts/Condor" "$HOME/.shortcuts/Detener Condor"
ln -sf "$DESTINO/android/condor.sh" "$HOME/bin/condor"
ln -sf "$DESTINO/android/detener.sh" "$HOME/bin/detener-condor"

echo
echo "Listo. Para abrir el Cóndor:"
echo "  - toque el widget «Condor» de Termux:Widget en la pantalla de inicio, o"
echo "  - escriba  condor  en Termux."
echo "Se abre en el navegador (http://127.0.0.1:8001). Entre con las mismas cuentas de la PC (si copió la base)"
echo "o, en una base nueva, con el usuario admin y la contraseña inicial del Cóndor; le pedirá cambiarla."
