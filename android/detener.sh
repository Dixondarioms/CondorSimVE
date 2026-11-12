#!/data/data/com.termux/files/usr/bin/bash
# Detiene el servidor del Cóndor en la tablet (los ejercicios quedan guardados en la base).
pkill -f "app.servidor" && echo "Cóndor detenido." || echo "El Cóndor no estaba corriendo."
termux-wake-unlock 2>/dev/null || true
