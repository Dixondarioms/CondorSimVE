"""Recorta el fondo gris del escudo de la DIDA (frontend/static/img/dida_logo.jpg) y deja solo el disco, con fondo
transparente, en frontend/static/img/dida_logo_recortado.png (lo usan los manuales).

El disco se ubica por su azul (el fondo es gris, sin color) y se le suma el aro plateado del borde.

    backend\\venv\\Scripts\\python tools/recortar_logo_dida.py
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

IMG = Path(__file__).resolve().parent.parent / "frontend" / "static" / "img"
ORIGEN = IMG / "dida_logo.jpg"
DESTINO = IMG / "dida_logo_recortado.png"
ARO = 0.035  # ancho del aro plateado, como fraccion del radio del disco azul
ESCALA = 4  # sobremuestreo del borde para que no quede dentado


def main() -> None:
    im = Image.open(ORIGEN).convert("RGB")
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    azul = (b - np.maximum(r, g) > 25) & (b > 50)
    filas = np.where(azul.sum(axis=1) > azul.shape[1] * 0.02)[0]
    cols = np.where(azul.sum(axis=0) > azul.shape[0] * 0.02)[0]
    cy, cx = (filas[0] + filas[-1]) / 2, (cols[0] + cols[-1]) / 2
    radio = max(filas[-1] - filas[0], cols[-1] - cols[0]) / 2 * (1 + ARO)

    mascara = Image.new("L", (im.width * ESCALA, im.height * ESCALA), 0)
    ImageDraw.Draw(mascara).ellipse([(cx - radio) * ESCALA, (cy - radio) * ESCALA, (cx + radio) * ESCALA, (cy + radio) * ESCALA], fill=255)
    mascara = mascara.resize(im.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6))
    salida = im.convert("RGBA")
    salida.putalpha(mascara)
    caja = (int(cx - radio) - 2, int(cy - radio) - 2, int(cx + radio) + 3, int(cy + radio) + 3)
    salida.crop(caja).save(DESTINO, optimize=True)
    print(f"{DESTINO} centro ({cx:.0f}, {cy:.0f}) radio {radio:.0f}")


if __name__ == "__main__":
    main()
