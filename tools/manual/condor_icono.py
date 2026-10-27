"""Iconos del Cóndor a partir del condor posado (frontend/static/img/condor_posado.png, de condor_video.py), con el
estilo del escudo del SIETE: fondo oscuro con reticula verde, borde luminoso y el condor holografico; en los tamaños
grandes, la palabra CÓNDOR debajo.

Genera en frontend/static/img/: condor_icono_{32,48,64,128,192,256,512}.png, favicon.ico (16, 32, 48 y 256),
icono_escritorio.png e icono_escritorio.ico (acceso directo y ejecutable).

    backend\\venv\\Scripts\\python tools/manual/condor_icono.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

IMG = Path(__file__).resolve().parents[2] / "frontend" / "static" / "img"
FUENTE = Path("C:/Windows/Fonts/arialbd.ttf")
VERDE = (60, 255, 110)
LADO = 512


def condor() -> Image.Image:
    im = Image.open(IMG / "condor_posado.png").convert("RGBA")
    return im.crop(im.getchannel("A").point(lambda a: 255 if a > 10 else 0).getbbox())


def fondo(lado: int) -> Image.Image:
    """Placa redondeada oscura con reticula y borde verde luminoso."""
    f = lado / LADO
    base = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    placa = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(placa)
    radio, margen = round(70 * f), round(10 * f)
    caja = (margen, margen, lado - margen, lado - margen)
    d.rounded_rectangle(caja, radius=radio, fill=(12, 22, 18, 255))
    # degradado: mas claro al centro
    luz = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(luz).ellipse((lado * 0.1, lado * 0.05, lado * 0.9, lado * 0.85), fill=70)
    luz = luz.filter(ImageFilter.GaussianBlur(lado * 0.12))
    verde_suave = Image.new("RGBA", (lado, lado), (30, 90, 55, 255))
    placa = Image.composite(verde_suave, placa, luz.point(lambda v: v))
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(caja, radius=radio, fill=255)
    placa.putalpha(mascara)
    # reticula
    if lado >= 128:
        ret = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ret)
        paso = lado // 12
        for i in range(paso, lado, paso):
            dr.line((i, 0, i, lado), fill=(*VERDE, 22), width=max(1, round(f)))
            dr.line((0, i, lado, i), fill=(*VERDE, 22), width=max(1, round(f)))
        ret.putalpha(Image.composite(ret.getchannel("A"), Image.new("L", (lado, lado), 0), mascara))
        placa.alpha_composite(ret)
    base.alpha_composite(placa)
    # borde luminoso
    borde = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    ImageDraw.Draw(borde).rounded_rectangle(caja, radius=radio, outline=(*VERDE, 255), width=max(1, round(6 * f)))
    brillo = borde.filter(ImageFilter.GaussianBlur(max(1, 6 * f)))
    base.alpha_composite(brillo)
    base.alpha_composite(borde)
    return base


def icono(lado: int, con_texto: bool) -> Image.Image:
    im = fondo(lado)
    c = condor()
    alto_max = lado * (0.66 if con_texto else 0.80)
    ancho_max = lado * 0.80
    escala = min(alto_max / c.height, ancho_max / c.width)
    c = c.resize((max(1, round(c.width * escala)), max(1, round(c.height * escala))), Image.LANCZOS)
    y = round(lado * (0.07 if con_texto else 0.10))
    x = (lado - c.width) // 2
    halo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    halo.alpha_composite(c, (x, y))
    halo = halo.filter(ImageFilter.GaussianBlur(max(1, lado / 60)))
    im.alpha_composite(halo)
    im.alpha_composite(c, (x, y))
    if con_texto:
        d = ImageDraw.Draw(im)
        fuente = ImageFont.truetype(str(FUENTE), round(lado * 0.13))
        texto = "CÓNDOR"
        caja = d.textbbox((0, 0), texto, font=fuente)
        tx, ty = (lado - (caja[2] - caja[0])) // 2 - caja[0], round(lado * 0.77)
        sombra = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        ImageDraw.Draw(sombra).text((tx, ty), texto, font=fuente, fill=(*VERDE, 255))
        im.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(lado / 90)))
        d.text((tx, ty), texto, font=fuente, fill=(225, 255, 230, 255))
    return im


def main() -> None:
    grande = icono(LADO, True)
    chico = icono(LADO, False)
    for n in (32, 48, 64, 128, 192, 256, 512):
        fuente = grande if n >= 128 else chico
        fuente.resize((n, n), Image.LANCZOS).save(IMG / f"condor_icono_{n}.png")
    chico.save(IMG / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    grande.save(IMG / "icono_escritorio.png")
    grande.save(IMG / "icono_escritorio.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("iconos del Cóndor listos en", IMG)


if __name__ == "__main__":
    main()
