"""Convierte el video del aguila (generado con Gemini, fondo cuadriculado gris pintado) en la animacion de la
pantalla de acceso: frontend/static/img/aguila_vuelo.webm (VP9 con transparencia, 1,8 s) y
frontend/static/img/siete_aguila_posada.png (el primer cuadro: el aguila posada con las alas recogidas).

Del video se toma desde que el aguila esta posada hasta que termina la primera batida, y se reduce a 1,8 segundos
acelerando poco la apertura y la batida y mas el momento en que sostiene las alas arriba (TRAMOS). A cada cuadro
se le quita el fondo como a las imagenes (quitar_fondo_aguila.py) y todos se recortan al mismo recuadro.

    backend\\venv\\Scripts\\python tools/manual/aguila_video.py ruta\\video.mp4
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quitar_fondo_aguila import IMG, quitar_fondo_rgb  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or str(next(Path.home().glob(
    "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft*/*/bin/ffmpeg.exe")))
FPS = 30
DURACION = 1.8
# (fraccion del segundo final, segundo del video original): posada -> abre las alas -> arriba -> batida
TRAMOS = [(0.0, 1.30), (0.39, 2.40), (0.53, 3.00), (1.0, 4.10)]
ANCHO = 960  # ancho de trabajo (el original es 1280x720)


def tiempo_original(u: float) -> float:
    for (u0, t0), (u1, t1) in zip(TRAMOS, TRAMOS[1:]):
        if u <= u1:
            return t0 + (t1 - t0) * (u - u0) / (u1 - u0)
    return TRAMOS[-1][1]


def main(video: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        n = int(round(FPS * DURACION))
        cuadros = []
        for i in range(n):
            t = tiempo_original(i / (n - 1))
            png = tmp / f"o{i:03d}.png"
            subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", str(png)], check=True)
            im = Image.open(png)
            im = quitar_fondo_rgb(im, nucleo_px=6).resize((ANCHO, round(im.height * ANCHO / im.width)), Image.LANCZOS)
            cuadros.append(im)
        # un mismo recuadro para todos (lo que ocupa el aguila en algun cuadro), con medidas pares para el video
        cajas = [c.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox() for c in cuadros]
        x0, y0 = min(b[0] for b in cajas), min(b[1] for b in cajas)
        x1, y1 = max(b[2] for b in cajas), max(b[3] for b in cajas)
        x1 += (x1 - x0) % 2
        y1 += (y1 - y0) % 2
        for i, c in enumerate(cuadros):
            c.crop((x0, y0, x1, y1)).save(tmp / f"k{i:03d}.png")
        posada = Image.open(tmp / "k000.png")
        posada.save(IMG / "siete_aguila_posada.png")
        webm = IMG / "aguila_vuelo.webm"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-framerate", str(FPS), "-i", str(tmp / "k%03d.png"),
                        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28", "-auto-alt-ref", "0",
                        "-an", str(webm)], check=True)
        bp = posada.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        w, h = posada.size
        print(f"{webm} {webm.stat().st_size // 1024} KB, {w}x{h}, {n} cuadros")
        print(f"aguila posada: x {bp[0] / w:.3f}-{bp[2] / w:.3f}, y {bp[1] / h:.3f}-{bp[3] / h:.3f} del recuadro")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
