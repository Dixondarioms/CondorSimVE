#!/data/data/com.termux/files/usr/bin/bash
# Abre el Cóndor en la tablet: arranca el servidor (si no está corriendo) y abre el navegador.
# CONDOR_RED=1 condor  -> también acepta tablets, PC y celulares de la misma red wifi (para usarla de servidor).
DESTINO="$HOME/condor"
PUERTO="${CONDOR_PUERTO:-8001}"
HOST="127.0.0.1"
[ "${CONDOR_RED:-0}" = "1" ] && HOST="0.0.0.0"
REGISTRO="$DESTINO/backend/condor.log"

if ! curl -s -o /dev/null "http://127.0.0.1:$PUERTO/" 2>/dev/null; then
    termux-wake-lock 2>/dev/null || true   # que Android no duerma el servidor mientras se usa
    cd "$DESTINO/backend" || exit 1
    nohup "$DESTINO/venv/bin/python" -m app.servidor --host "$HOST" --port "$PUERTO" > "$REGISTRO" 2>&1 &
    echo "Arrancando el Cóndor..."
    for _ in $(seq 1 60); do
        sleep 1
        curl -s -o /dev/null "http://127.0.0.1:$PUERTO/" 2>/dev/null && break
    done
fi

if curl -s -o /dev/null "http://127.0.0.1:$PUERTO/" 2>/dev/null; then
    termux-open-url "http://127.0.0.1:$PUERTO/" 2>/dev/null || am start -a android.intent.action.VIEW -d "http://127.0.0.1:$PUERTO/" >/dev/null 2>&1
    echo "Cóndor abierto en http://127.0.0.1:$PUERTO/"
    if [ "$HOST" = "0.0.0.0" ]; then
        IP="$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)"
        [ -n "$IP" ] && echo "Desde otros equipos de la red: http://$IP:$PUERTO/"
    fi
else
    echo "El Cóndor no arrancó. Revise $REGISTRO" >&2
    tail -20 "$REGISTRO" >&2
    exit 1
fi
