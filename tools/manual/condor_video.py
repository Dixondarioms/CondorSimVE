"""Convierte el video del condor (generado con Gemini: holograma verde sobre fondo negro con lineas y textos de
pantalla) en la animacion de la pantalla de acceso, con el mismo estilo que la del aguila del SIETE
(aguila_video.py): frontend/static/img/condor_vuelo.webm (VP9 con transparencia, 2,8 s) y
frontend/static/img/condor_posado.png (el primer cuadro: el condor posado con las alas recogidas).

Del video se toma desde que el condor esta posado hasta que despega y da la primera batida, y se reduce a 2,8
segundos (TRAMOS). A cada cuadro se le quita el fondo: la opacidad sale del brillo del holograma; las lineas,
textos y particulas sueltas de la pantalla se descartan quedandose con la figura grande; y el borde del cuadro se
desvanece (en algun cuadro la punta de un ala sale del video).

    backend\\venv\\Scripts\\python tools/manual/condor_video.py ruta\\video.mp4
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

IMG = Path(__file__).resolve().parents[2] / "frontend" / "static" / "img"
FFMPEG = shutil.which("ffmpeg") or str(next(Path.home().glob(
    "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft*/*/bin/ffmpeg.exe")))
FPS = 30
DURACION = 2.8
# (fraccion del tiempo final, segundo del video original): posado -> abre las alas -> arriba -> despega -> batida
TRAMOS = [(0.0, 1.10), (0.25, 2.20), (0.40, 2.70), (0.65, 3.40), (1.0, 4.60)]
ANCHO = 960  # ancho de trabajo (el original es 1280x720)
BORDE_PX = 28  # franja del borde del cuadro que se desvanece


def tiempo_original(u: float) -> float:
    for (u0, t0), (u1, t1) in zip(TRAMOS, TRAMOS[1:]):
        if u <= u1:
            return t0 + (t1 - t0) * (u - u0) / (u1 - u0)
    return TRAMOS[-1][1]


def quitar_fondo_condor(imagen: Image.Image) -> Image.Image:
    """El cuadro en RGBA: el holograma verde opaco segun su brillo y el fondo negro (con sus lineas) transparente."""
    c = np.asarray(imagen.convert("RGB")).astype(np.float32)
    brillo = ndimage.uniform_filter(c.max(axis=2), 3)  # ruido del video
    alfa = np.clip((brillo - 28.0) / 95.0, 0.0, 1.0)
    # silueta: el holograma cerrado y sin huecos; solo las piezas grandes (el condor, no los textos ni las chispas)
    silueta = ndimage.binary_fill_holes(ndimage.binary_closing(brillo > 50, iterations=5))
    silueta = ndimage.binary_opening(silueta, iterations=4)  # las lineas finas de la pantalla se van
    etiquetas, n = ndimage.label(silueta)
    if n > 1:
        tam = ndimage.sum(silueta, etiquetas, range(1, n + 1))
        grandes = [i + 1 for i, t in enumerate(tam) if t >= 0.08 * tam.max()]
        silueta = np.isin(etiquetas, grandes)
    zona = ndimage.gaussian_filter(ndimage.binary_dilation(silueta, iterations=4).astype(np.float32), 1.5)
    nucleo = ndimage.gaussian_filter(ndimage.binary_erosion(silueta, iterations=5).astype(np.float32), 3)
    alfa = np.maximum(alfa, 0.8 * nucleo) * zona  # el cuerpo se ve lleno, como el aguila
    # el borde del cuadro se desvanece: una punta de ala cortada por el video no deja un corte recto
    h, w = alfa.shape
    rampa_y = np.clip(np.minimum(np.arange(h), np.arange(h)[::-1]) / BORDE_PX, 0, 1)
    rampa_x = np.clip(np.minimum(np.arange(w), np.arange(w)[::-1]) / BORDE_PX, 0, 1)
    alfa *= rampa_y[:, None] * rampa_x[None, :]
    # el fondo es negro: el color del holograma es el del cuadro dividido por su opacidad
    a = alfa[..., None]
    color = np.clip(np.where(a > 0.02, c / np.maximum(a, 0.35), 0.0), 0, 255)
    return Image.fromarray(np.dstack([color, alfa * 255.0]).astype(np.uint8), "RGBA")


def main(video: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        n = int(round(FPS * DURACION))
        cuadros = []
        for i in range(n):
            t = tiempo_original(i / (n - 1))
            png = tmp / f"o{i:03d}.png"
            subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(png)],
                           check=True)
            im = Image.open(png)
            im = quitar_fondo_condor(im).resize((ANCHO, round(im.height * ANCHO / im.width)), Image.LANCZOS)
            cuadros.append(im)
        # un mismo recuadro para todos (lo que ocupa el condor en algun cuadro), con medidas pares para el video
        cajas = [c.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox() for c in cuadros]
        x0, y0 = min(b[0] for b in cajas), min(b[1] for b in cajas)
        x1, y1 = max(b[2] for b in cajas), max(b[3] for b in cajas)
        x1 += (x1 - x0) % 2
        y1 += (y1 - y0) % 2
        for i, c in enumerate(cuadros):
            c.crop((x0, y0, x1, y1)).save(tmp / f"k{i:03d}.png")
        posado = Image.open(tmp / "k000.png")
        posado.save(IMG / "condor_posado.png")
        webm = IMG / "condor_vuelo.webm"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-framerate", str(FPS), "-i", str(tmp / "k%03d.png"),
                        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28", "-auto-alt-ref", "0",
                        "-an", str(webm)], check=True)
        bp = posado.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        w, h = posado.size
        print(f"{webm} {webm.stat().st_size // 1024} KB, {w}x{h}, {n} cuadros")
        print(f"condor posado: x {bp[0] / w:.3f}-{bp[2] / w:.3f}, y {bp[1] / h:.3f}-{bp[3] / h:.3f} del recuadro")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
