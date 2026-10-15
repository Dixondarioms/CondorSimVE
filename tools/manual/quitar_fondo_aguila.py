"""Quita el fondo cuadriculado gris (falsa transparencia) de una imagen del aguila del SIETE y la deja en PNG
con transparencia real en frontend/static/img/ (por omision siete_aguila.png, alas desplegadas; la de alas
recogidas es siete_aguila_plegada.png).

El fondo es gris neutro (R = G = B) y el aguila es verde y amarilla, asi que la opacidad sale del croma
(max - min de los canales); el interior del aguila se rellena entero y el halo se limpia del gris de fondo.

    backend\\venv\\Scripts\\python tools/manual/quitar_fondo_aguila.py ruta\\imagen.jpg [siete_aguila_plegada.png]
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

IMG = Path(__file__).resolve().parents[2] / "frontend" / "static" / "img"


def quitar_fondo(origen: Path) -> Image.Image:
    c = np.asarray(Image.open(origen).convert("RGB")).astype(np.float32)
    croma = c.max(axis=2) - c.min(axis=2)
    croma = ndimage.uniform_filter(croma, 3)  # ruido del JPEG
    alfa = np.clip((croma - 8.0) / 45.0, 0.0, 1.0)
    # silueta: todo lo que tiene color, cerrado y sin huecos; su nucleo es opaco
    silueta = ndimage.binary_fill_holes(ndimage.binary_closing(croma > 22, iterations=6))
    silueta = ndimage.binary_opening(silueta, iterations=2)
    etiquetas, n = ndimage.label(silueta)
    if n > 1:  # solo la pieza grande (el aguila)
        tam = ndimage.sum(silueta, etiquetas, range(1, n + 1))
        silueta = etiquetas == (1 + int(np.argmax(tam)))
    nucleo = ndimage.binary_erosion(silueta, iterations=10)
    nucleo = ndimage.gaussian_filter(nucleo.astype(np.float32), 3)
    alfa = np.maximum(alfa, nucleo)
    # halo: se resta el gris del fondo (el canal minimo) en proporcion a la transparencia
    fondo = c.min(axis=2, keepdims=True)
    a = alfa[..., None]
    color = np.where(a > 0.02, (c - fondo * (1.0 - a)) / np.maximum(a, 0.02), 0.0)
    color = np.clip(color, 0, 255)
    rgba = np.dstack([color, alfa * 255.0]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA")
    return im.crop(im.getbbox())


if __name__ == "__main__":
    destino = IMG / (sys.argv[2] if len(sys.argv) > 2 else "siete_aguila.png")
    im = quitar_fondo(Path(sys.argv[1]))
    im.save(destino)
    print(destino, im.size)
