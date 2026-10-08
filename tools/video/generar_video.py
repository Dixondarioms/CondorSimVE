"""Video de presentacion de S.I.E.T.E. en 4K con locucion (voces neuronales de Microsoft, ver locucion.py).

Arma el video a partir del guion (guion.py), las capturas 4K de la interfaz (capturas_video.py) y la locucion: placa de
apertura con el emblema de la DIDA y el logotipo de S.I.E.T.E., una escena por tema con movimientos de camara sobre
las capturas, rotulo del capitulo, subtitulos sincronizados con la voz, musica de fondo que baja mientras se habla y
placa de cierre con los creditos. El largo de cada escena lo marca su locucion.

Pasos (con el servidor de S.I.E.T.E. en marcha para las capturas):

    python tools/video/capturas_video.py      # capturas 4K de la interfaz
    python tools/video/locucion.py            # voz (necesita internet)
    python tools/video/generar_video.py       # -> tools/video/salida/SIETE_presentacion_4K_locucion.mp4

Opciones: --resolucion 1080 (borrador rapido), --musica archivo.mp3 (en lugar de la generada), --sin-musica,
--sin-subtitulos, --preset (de x264: slow da archivos mas chicos). Sin locucion generada se arma un BORRADOR mudo con
los tiempos estimados, util para revisar el montaje. Requiere ffmpeg en el PATH y `pip install -r requirements.txt`.
"""

import argparse
import json
import math
import re
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
sys.path.insert(0, str(AQUI))
from guion import CREDITOS, ESCENAS  # noqa: E402

CAPTURAS = AQUI / "salida" / "capturas"
LOCUCION = AQUI / "salida" / "locucion"
EMBLEMA = AQUI / "recursos" / "dida_logo.jpg"
EMBLEMA_CIRCULO = (514, 540, 416)  # centro y radio del emblema circular dentro de la imagen
LOGO_SIETE = RAIZ / "frontend" / "static" / "img" / "siete_logo_recortado.jpg"

FPS = 30
FUNDIDO = 0.8  # segundos de fundido encadenado entre escenas
FUNDIDO_IMAGEN = 0.6  # entre las capturas de una misma escena
ANTES, DESPUES = 0.5, 0.9  # silencio por defecto antes y despues de la voz de cada escena
CARACTERES_POR_SEGUNDO = 14.5  # para estimar la duracion sin locucion (borrador)
ZOOM_MAXIMO = 2.3
SR = 48000

AZUL_NOCHE = (5, 13, 34)
AZUL = (13, 42, 92)
DORADO = (212, 175, 55)
BLANCO = (245, 247, 250)

FUENTES = {
    "negrita": ["recursos/fuentes/negrita.ttf", r"C:\Windows\Fonts\segoeuib.ttf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
                r"C:\Windows\Fonts\arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "semi": ["recursos/fuentes/semi.ttf", r"C:\Windows\Fonts\seguisb.ttf", "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
             r"C:\Windows\Fonts\arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "normal": ["recursos/fuentes/normal.ttf", r"C:\Windows\Fonts\segoeui.ttf", "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
               r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


@lru_cache(maxsize=None)
def fuente(tipo: str, tam: int) -> ImageFont.FreeTypeFont:
    for ruta in FUENTES[tipo]:
        p = Path(ruta) if Path(ruta).is_absolute() else AQUI / ruta
        if p.exists():
            return ImageFont.truetype(str(p), tam)
    return ImageFont.load_default(tam)


def suave(x: float) -> float:
    """Curva de aceleracion y frenado (smootherstep) en [0, 1]."""
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)


def duracion_audio(ruta: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ruta)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def leer_audio(ruta: Path) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(ruta), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


# ======================================================================= linea de tiempo
def trozos_subtitulo(texto: str, maximo=120) -> list[str]:
    """Frases del guion, partidas en las comas si son largas, para no pasar de dos lineas."""
    frases = [f for f in re.split(r"(?<=[.:;?!])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])", texto.strip()) if f]
    salida = []
    for f in frases:
        while len(f) > maximo:
            cortes = [m.end() for m in re.finditer(r"[,:;]\s", f) if 35 < m.end() <= maximo]
            if not cortes:
                cortes = [m.start() + 1 for m in re.finditer(r"\s", f) if 35 < m.start() <= maximo]
            if not cortes:
                break
            corte = cortes[-1]
            salida.append(f[:corte].strip())
            f = f[corte:].strip()
        salida.append(f)
    return salida


def armar_linea_de_tiempo() -> tuple[list[dict], float, bool]:
    escenas, inicio, con_voz = [], 0.0, True
    for e in ESCENAS:
        e = dict(e)
        mp3, meta = LOCUCION / f"{e['id']}.mp3", LOCUCION / f"{e['id']}.json"
        if mp3.exists() and meta.exists():
            e["audio"] = mp3
            e["voz"] = duracion_audio(mp3)
            limites = json.loads(meta.read_text(encoding="utf-8")).get("frases", [])
        else:
            con_voz = False
            e["voz"] = len(e["texto"]) / CARACTERES_POR_SEGUNDO
            limites = []
        e.setdefault("antes", ANTES)
        e.setdefault("despues", DESPUES)
        e["inicio"] = inicio
        e["dur"] = e["antes"] + e["voz"] + e["despues"]
        # subtitulos: cada frase con los tiempos que dio la voz; si no cuadran, en proporcion a los caracteres
        frases = [f for f in re.split(r"(?<=[.:;?!])\s+(?=[A-ZÁÉÍÓÚÑ¿¡])", e["texto"].strip()) if f]
        if len(limites) == len(frases):
            tramos = [(lim["inicio"], lim["inicio"] + lim["duracion"]) for lim in limites]
        else:
            total, t, tramos = sum(len(f) for f in frases), 0.0, []
            for f in frases:
                d = e["voz"] * len(f) / total
                tramos.append((t, t + d))
                t += d
        subs = []
        for f, (t0, t1) in zip(frases, tramos):
            partes = trozos_subtitulo(f)
            total = sum(len(p) for p in partes)
            for p in partes:
                d = (t1 - t0) * len(p) / total
                subs.append([e["antes"] + t0, e["antes"] + t0 + d, p])
                t0 += d
        for a, b in zip(subs, subs[1:]):
            a[1] = min(b[0], a[1] + 0.35)  # que el subtitulo quede un poco despues de la voz, sin pisar el siguiente
        e["subs"] = subs
        escenas.append(e)
        inicio += e["dur"] - FUNDIDO
    total = escenas[-1]["inicio"] + escenas[-1]["dur"]
    numero, previo = 0, None
    for e in escenas:
        if e.get("capitulo") and e["capitulo"] != previo:
            numero += 1
            e["capitulo_nuevo"] = True
        e["capitulo_n"] = numero
        previo = e.get("capitulo")
    return escenas, total, con_voz


# ======================================================================= graficos
class Lienzo:
    """Todo lo que se dibuja, a la escala de la salida (S = 1 en 4K)."""

    def __init__(self, ancho: int, alto: int):
        self.W, self.H, self.S = ancho, alto, ancho / 3840
        self.capturas: dict[str, np.ndarray] = {}
        self.focos = json.loads((CAPTURAS / "focos.json").read_text(encoding="utf-8")) if (CAPTURAS / "focos.json").exists() else {}
        self.fondo = self._fondo_tecnologico()
        self.emblema = self._emblema()
        self.logo_siete = self._logo_siete()
        self.sello = self._escalar(self.emblema, int(170 * self.S))
        self._cache: dict = {}

    def s(self, v: float) -> int:
        return int(round(v * self.S))

    # ------------------------------------------------------------ recursos
    def _emblema(self) -> np.ndarray:
        im = Image.open(EMBLEMA).convert("RGB")
        cx, cy, r = EMBLEMA_CIRCULO
        m = Image.new("L", (im.width * 4, im.height * 4), 0)
        ImageDraw.Draw(m).ellipse([(cx - r) * 4, (cy - r) * 4, (cx + r) * 4, (cy + r) * 4], fill=255)
        im.putalpha(m.resize(im.size, Image.LANCZOS))
        return np.asarray(im.crop((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2)))

    def _logo_siete(self) -> np.ndarray:
        im = Image.open(LOGO_SIETE).convert("RGB")
        ancho = self.s(1250)
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)
        borde, radio = max(2, self.s(6)), self.s(36)
        lienzo = Image.new("RGBA", (im.width + 2 * borde, im.height + 2 * borde), (0, 0, 0, 0))
        d = ImageDraw.Draw(lienzo)
        d.rounded_rectangle([0, 0, lienzo.width - 1, lienzo.height - 1], radio + borde, fill=DORADO + (255,))
        m = Image.new("L", im.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radio, fill=255)
        lienzo.paste(im, (borde, borde), m)
        return np.asarray(lienzo)

    @staticmethod
    def _escalar(rgba: np.ndarray, ancho: int) -> np.ndarray:
        alto = round(rgba.shape[0] * ancho / rgba.shape[1])
        return cv2.resize(rgba, (ancho, alto), interpolation=cv2.INTER_AREA)

    def _fondo_tecnologico(self) -> np.ndarray:
        """Fondo azul noche con reticula y nodos de circuito (como el del emblema), algo mas grande que la pantalla
        para poder desplazarlo despacio."""
        W, H = int(self.W * 1.12), int(self.H * 1.12)
        rng = np.random.default_rng(7)
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot((x - W / 2) / W, (y - H * 0.45) / H)
        base = np.clip(1 - r * 1.5, 0, 1)[..., None]
        fondo = (np.array(AZUL_NOCHE, np.float32) * (1 - base) + np.array(AZUL, np.float32) * base)
        im = Image.fromarray(fondo.astype(np.uint8)).convert("RGBA")
        capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(capa)
        paso = self.s(120)
        for gx in range(0, W, paso):
            d.line([(gx, 0), (gx, H)], fill=(80, 140, 220, 12), width=max(1, self.s(2)))
        for gy in range(0, H, paso):
            d.line([(0, gy), (W, gy)], fill=(80, 140, 220, 12), width=max(1, self.s(2)))
        for _ in range(140):  # pistas de circuito: tramos en angulo recto que terminan en un nodo
            px, py = rng.integers(0, W // paso) * paso, rng.integers(0, H // paso) * paso
            pts = [(px, py)]
            for _ in range(rng.integers(2, 5)):
                if rng.random() < 0.5:
                    px += int(rng.integers(-3, 4)) * paso
                else:
                    py += int(rng.integers(-3, 4)) * paso
                pts.append((px, py))
            alfa = int(rng.integers(28, 85))
            d.line(pts, fill=(110, 180, 255, alfa), width=max(1, self.s(3)))
            rr = self.s(rng.integers(7, 14))
            d.ellipse([px - rr, py - rr, px + rr, py + rr], outline=(140, 200, 255, alfa + 60), width=max(1, self.s(3)))
        brillo = capa.filter(ImageFilter.GaussianBlur(self.s(10)))
        im.alpha_composite(brillo)
        im.alpha_composite(capa)
        return np.asarray(im.convert("RGB")).copy()

    def captura(self, nombre: str) -> np.ndarray:
        if nombre not in self.capturas:
            ruta = CAPTURAS / f"{nombre}.png"
            if not ruta.exists():
                raise SystemExit(f"Falta la captura {ruta.name}: ejecute tools/video/capturas_video.py")
            im = cv2.cvtColor(cv2.imread(str(ruta), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
            if im.shape[1] != self.W:  # borrador: se reduce una vez (la camara solo acerca)
                im = cv2.resize(im, (self.W, round(im.shape[0] * self.W / im.shape[1])), interpolation=cv2.INTER_AREA)
            self.capturas[nombre] = im
        return self.capturas[nombre]

    def olvidar_capturas(self, usadas: set[str]):
        for k in list(self.capturas):
            if k not in usadas:
                del self.capturas[k]

    # ------------------------------------------------------------ textos y paneles
    def texto(self, contenido: str, tipo: str, tam: int, color=BLANCO, espaciado=0) -> np.ndarray:
        clave = ("t", contenido, tipo, tam, color, espaciado)
        if clave not in self._cache:
            f = fuente(tipo, self.s(tam))
            if espaciado:
                anchos = [f.getlength(c) + self.s(espaciado) for c in contenido]
                w = int(sum(anchos)) + 4
            else:
                w = int(f.getlength(contenido)) + 4
            a, d = f.getmetrics()
            im = Image.new("RGBA", (w, a + d + 4), (0, 0, 0, 0))
            dib = ImageDraw.Draw(im)
            if espaciado:
                x = 0.0
                for c, ac in zip(contenido, anchos):
                    dib.text((x, 2), c, font=f, fill=color + (255,))
                    x += ac
            else:
                dib.text((2, 2), contenido, font=f, fill=color + (255,))
            sombra = Image.new("RGBA", im.size, (0, 0, 0, 0))
            sombra.putalpha(im.getchannel("A").filter(ImageFilter.GaussianBlur(max(1, self.s(5)))).point(lambda v: v * 0.7))
            sombra.alpha_composite(im)
            self._cache[clave] = np.asarray(sombra)
        return self._cache[clave]

    def subtitulo(self, contenido: str) -> np.ndarray:
        clave = ("sub", contenido)
        if clave not in self._cache:
            f = fuente("semi", self.s(66))
            ancho_max = self.s(3000)
            lineas, actual = [], ""
            for palabra in contenido.split():
                prueba = f"{actual} {palabra}".strip()
                if f.getlength(prueba) <= ancho_max or not actual:
                    actual = prueba
                else:
                    lineas.append(actual)
                    actual = palabra
            lineas.append(actual)
            if len(lineas) == 2 and len(lineas[1]) < 18:  # evita la viuda: reparte las dos lineas
                palabras = contenido.split()
                mejor = min(range(1, len(palabras)), key=lambda i: abs(f.getlength(" ".join(palabras[:i])) - f.getlength(" ".join(palabras[i:]))))
                lineas = [" ".join(palabras[:mejor]), " ".join(palabras[mejor:])]
            a, d = f.getmetrics()
            alto_linea = int((a + d) * 1.12)
            pad_x, pad_y = self.s(56), self.s(30)
            w = int(max(f.getlength(l) for l in lineas)) + 2 * pad_x
            h = alto_linea * len(lineas) + 2 * pad_y
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            dib = ImageDraw.Draw(im)
            dib.rounded_rectangle([0, 0, w - 1, h - 1], self.s(22), fill=(4, 10, 26, 185))
            dib.rectangle([0, self.s(22), max(2, self.s(8)), h - self.s(22)], fill=DORADO + (255,))
            for i, l in enumerate(lineas):
                dib.text((w / 2, pad_y + i * alto_linea + alto_linea / 2), l, font=f, fill=BLANCO + (255,), anchor="mm")
            self._cache[clave] = np.asarray(im)
        return self._cache[clave]

    def rotulo_capitulo(self, numero: int, titulo: str) -> np.ndarray:
        clave = ("cap", numero, titulo)
        if clave not in self._cache:
            fn, ft = fuente("negrita", self.s(84)), fuente("semi", self.s(56))
            num = f"{numero:02d}"
            pad, sep = self.s(40), self.s(34)
            wn, wt = fn.getlength(num), ft.getlength(titulo.upper())
            h = self.s(150)
            w = int(self.s(14) + pad + wn + sep + self.s(4) + sep + wt + pad)
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle([0, 0, w - 1, h - 1], self.s(18), fill=(4, 12, 32, 205))
            d.rounded_rectangle([0, 0, self.s(14), h - 1], self.s(7), fill=DORADO + (255,))
            x = self.s(14) + pad
            d.text((x, h / 2), num, font=fn, fill=DORADO + (255,), anchor="lm")
            x += wn + sep
            d.rectangle([x, self.s(36), x + self.s(4), h - self.s(36)], fill=(255, 255, 255, 110))
            d.text((x + self.s(4) + sep, h / 2), titulo.upper(), font=ft, fill=BLANCO + (255,), anchor="lm")
            self._cache[clave] = np.asarray(im)
        return self._cache[clave]


def pegar(cuadro: np.ndarray, rgba: np.ndarray, x: int, y: int, opacidad: float = 1.0):
    """Superpone una imagen RGBA en (x, y) con su transparencia (recortada a los bordes del cuadro)."""
    if opacidad <= 0.004:
        return
    H, W = cuadro.shape[:2]
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    trozo = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = trozo[..., 3:4].astype(np.uint16)
    if opacidad < 1:
        a = (a * int(opacidad * 256)) >> 8
    zona = cuadro[y0:y1, x0:x1]
    zona[:] = ((trozo[..., :3].astype(np.uint16) * a + zona.astype(np.uint16) * (255 - a) + 127) // 255).astype(np.uint8)


def mezclar(a: np.ndarray, b: np.ndarray, peso_b: float) -> np.ndarray:
    return cv2.addWeighted(a, 1 - peso_b, b, peso_b, 0)


# ======================================================================= camara sobre las capturas
def rect_16_9(L: Lienzo, x: float, y: float, w: float, h: float, margen=0.06) -> tuple[float, float, float]:
    """Recuadro 16:9 que contiene (x, y, w, h) con un margen, sin pasar del zoom maximo ni salir de la imagen.
    Devuelve (cx, cy, ancho) en pixeles 4K."""
    w, h = w * (1 + 2 * margen), h * (1 + 2 * margen)
    cx, cy = x + w / (2 * (1 + 2 * margen)), y + h / (2 * (1 + 2 * margen))
    ancho = max(w, h * 16 / 9, 3840 / ZOOM_MAXIMO)
    ancho = min(ancho, 3840)
    alto = ancho * 9 / 16
    cx = min(max(cx, ancho / 2), 3840 - ancho / 2)
    cy = min(max(cy, alto / 2), 2160 - alto / 2)
    return cx, cy, ancho


def recorrido_camara(L: Lienzo, nombre: str, mov) -> tuple[tuple, tuple, str]:
    entero = (1920.0, 1080.0, 3840.0)
    if mov == "empuje":
        return entero, (1920.0, 1080.0, 3840 / 1.09), "lineal"
    if mov == "fijo":
        return entero, entero, "lineal"
    if mov == "desde_centro":
        return (1920.0, 1080.0, 3840 / 1.14), entero, "lineal"
    if isinstance(mov, (tuple, list)):
        x, y, w = mov
        destino = rect_16_9(L, x, y, w, w * 9 / 16, margen=0)
        return (1920.0, 1080.0, 3840 / 1.02), destino, "foco"
    foco = L.focos.get(nombre)
    destino = rect_16_9(L, *foco) if foco else (1920.0, 1080.0, 3840 / 1.09)
    if mov == "desde_foco":
        return destino, entero, "foco"
    return (1920.0, 1080.0, 3840 / 1.02), destino, "foco"


def cuadro_captura(L: Lienzo, nombre: str, mov, p: float) -> np.ndarray:
    """Captura vista por la camara en el avance p (0 a 1) de su tramo."""
    a, b, tipo = recorrido_camara(L, nombre, mov)
    if tipo == "foco":  # llega al foco en el primer 60 % del tramo y despues se acerca muy poco mas
        k = suave(p / 0.6)
        deriva = 1 - 0.035 * max(0.0, (p - 0.6) / 0.4)
    else:
        k, deriva = p * (2 - p) if p < 1 else 1, 1.0  # frena suave al final
    cx = a[0] + (b[0] - a[0]) * k
    cy = a[1] + (b[1] - a[1]) * k
    ancho = (a[2] + (b[2] - a[2]) * k) * deriva
    src = L.captura(nombre)
    esc_src = src.shape[1] / 3840
    zoom = L.W / (ancho * esc_src)
    M = np.array([[zoom, 0, L.W / 2 - cx * esc_src * zoom], [0, zoom, L.H / 2 - cy * esc_src * zoom]], np.float32)
    interp = cv2.INTER_CUBIC if zoom > 1.01 else cv2.INTER_LINEAR
    return cv2.warpAffine(src, M, (L.W, L.H), flags=interp, borderMode=cv2.BORDER_REPLICATE)


def escena_capturas(L: Lienzo, e: dict, t: float) -> np.ndarray:
    imgs = e["imagenes"]
    n = len(imgs)
    tramo = (e["dur"] + FUNDIDO_IMAGEN * (n - 1)) / n
    i = min(n - 1, int(t // (tramo - FUNDIDO_IMAGEN))) if n > 1 else 0
    t_i = t - i * (tramo - FUNDIDO_IMAGEN)
    cuadro = cuadro_captura(L, imgs[i][0], imgs[i][1], t_i / tramo)
    if i + 1 < n and t_i > tramo - FUNDIDO_IMAGEN:  # fundido con la siguiente captura
        t_j = t_i - (tramo - FUNDIDO_IMAGEN)
        siguiente = cuadro_captura(L, imgs[i + 1][0], imgs[i + 1][1], t_j / tramo)
        cuadro = mezclar(cuadro, siguiente, suave(t_j / FUNDIDO_IMAGEN))
    return cuadro


# ======================================================================= placas de apertura y cierre
def fondo_animado(L: Lienzo, t: float) -> np.ndarray:
    F = L.fondo
    mx, my = F.shape[1] - L.W, F.shape[0] - L.H
    x = mx * (0.5 + 0.45 * math.sin(t * 0.07))
    y = my * (0.5 + 0.45 * math.cos(t * 0.05))
    M = np.array([[1, 0, -x], [0, 1, -y]], np.float32)
    return cv2.warpAffine(F, M, (L.W, L.H), flags=cv2.INTER_LINEAR)


def pegar_centrado(cuadro, rgba, cx, cy, opacidad=1.0):
    pegar(cuadro, rgba, int(cx - rgba.shape[1] / 2), int(cy - rgba.shape[0] / 2), opacidad)


def placa_intro(L: Lienzo, e: dict, t: float) -> np.ndarray:
    c = fondo_animado(L, t)
    cambio = e["antes"] + e["voz"] * e["texto"].index("S.I.E.T.E.") / len(e["texto"]) - 0.4
    # 1) emblema de la DIDA
    if t < cambio + 0.8:
        entra = suave(t / 1.6)
        sale = 1 - suave((t - cambio) / 0.8)
        escala = 0.86 + 0.14 * suave(t / 2.2) + 0.03 * (t / max(cambio, 1))
        em = L._escalar(L.emblema, L.s(1180 * escala))
        pegar_centrado(c, em, L.W / 2, L.H * 0.46, entra * sale)
        pres = L.texto("PRESENTA", "semi", 54, DORADO, espaciado=18)
        pegar_centrado(c, pres, L.W / 2, L.H * 0.9, suave((t - cambio + 2.0) / 0.8) * sale)
    # 2) logotipo y nombre de S.I.E.T.E.
    if t > cambio:
        u = t - cambio
        logo = L.logo_siete
        pegar_centrado(c, logo, L.W / 2, L.H * 0.36 - L.s(40) * (1 - suave(u / 1.5)), suave(u / 1.0))
        titulo = L.texto("S.I.E.T.E.", "negrita", 170, DORADO, espaciado=26)
        pegar_centrado(c, titulo, L.W / 2, L.H * 0.70, suave((u - 0.5) / 0.9))
        ancho_linea = int(L.s(1500) * suave((u - 0.9) / 1.0))
        if ancho_linea > 2:
            y = int(L.H * 0.765)
            c[y:y + max(2, L.s(5)), L.W // 2 - ancho_linea // 2:L.W // 2 + ancho_linea // 2] = DORADO
        sub = L.texto("SISTEMA INTEGRAL DE ENTRENAMIENTO TÁCTICO Y ESTRATÉGICO", "semi", 62, BLANCO, espaciado=6)
        pegar_centrado(c, sub, L.W / 2, L.H * 0.82, suave((u - 1.2) / 0.9))
        amb = L.texto("AVIACIÓN MILITAR BOLIVARIANA  ·  DIDA", "normal", 46, (190, 205, 230), espaciado=8)
        pegar_centrado(c, amb, L.W / 2, L.H * 0.885, suave((u - 1.8) / 0.9))
    negro = 1 - suave(t / 1.0)
    if negro > 0:
        c = (c * (1 - negro)).astype(np.uint8)
    return c


def placa_cierre(L: Lienzo, e: dict, t: float) -> np.ndarray:
    c = fondo_animado(L, t + 40)
    em = L._escalar(L.emblema, L.s(1100))
    pegar_centrado(c, em, L.W * 0.27, L.H * 0.5, suave(t / 1.2))
    x0 = int(L.W * 0.50)
    elementos = [
        (L.texto("S.I.E.T.E.", "negrita", 160, DORADO, espaciado=24), 0.30, 0.4),
        (L.texto("Sistema Integral de Entrenamiento Táctico y Estratégico", "semi", 58), 0.40, 0.8),
    ] + [(L.texto(linea, "normal", 48, (200, 212, 232)), 0.52 + 0.065 * i, 1.4 + 0.4 * i) for i, linea in enumerate(CREDITOS)] + [
        (L.texto("EL INFINITO ES EL LÍMITE", "negrita", 64, DORADO, espaciado=14), 0.79, 2.9),
    ]
    for img, y, retardo in elementos:
        k = suave((t - retardo) / 0.9)
        pegar(c, img, int(x0 + L.s(60) * (1 - k)), int(L.H * y - img.shape[0] / 2), k)
    ancho = int(L.s(1500) * suave((t - 1.0) / 1.0))
    if ancho > 2:
        y = int(L.H * 0.465)
        c[y:y + max(2, L.s(5)), x0:x0 + ancho] = DORADO
    negro = suave((t - (e["dur"] - 1.8)) / 1.8)
    if negro > 0:
        c = (c * (1 - negro)).astype(np.uint8)
    return c


# ======================================================================= cuadro de una escena
def cuadro_escena(L: Lienzo, e: dict, t: float, subtitulos: bool, borrador: bool) -> np.ndarray:
    if e.get("placa") == "intro":
        return placa_intro(L, e, t)
    if e.get("placa") == "cierre":
        return placa_cierre(L, e, t)
    c = escena_capturas(L, e, t)
    if not c.flags.writeable:
        c = c.copy()
    # rotulo del capitulo (entra deslizandose al comenzar un capitulo nuevo)
    if e.get("capitulo"):
        rot = L.rotulo_capitulo(e["capitulo_n"], e["capitulo"])
        k = suave((t - 0.3) / 0.7) if e.get("capitulo_nuevo") else 1.0
        pegar(c, rot, int(L.s(90) - L.s(140) * (1 - k)), L.s(90), k)
    # sello de la DIDA
    pegar(c, L.sello, L.W - L.sello.shape[1] - L.s(70), L.s(70), 0.92)
    if subtitulos:
        for t0, t1, texto in e["subs"]:
            if t0 - 0.12 <= t <= t1 + 0.12:
                k = min(suave((t - t0 + 0.12) / 0.24), 1 - suave((t - t1) / 0.24))
                sub = L.subtitulo(texto)
                pegar(c, sub, (L.W - sub.shape[1]) // 2, L.H - sub.shape[0] - L.s(110), k)
                break
    if borrador:
        marca = L.texto("BORRADOR · SIN LOCUCIÓN", "negrita", 40, (255, 190, 60))
        pegar(c, marca, L.s(90), L.H - marca.shape[0] - L.s(40), 0.85)
    return c


# ======================================================================= audio
def musica_generada(segundos: float) -> np.ndarray:
    """Fondo ambiental sobrio: acordes largos (Re menor, Si bemol, Fa, Do) con armonicos suaves y un bajo."""
    n = int(segundos * SR)
    t = np.arange(n, dtype=np.float64) / SR
    acordes = [[146.83, 174.61, 220.00, 293.66], [116.54, 174.61, 233.08, 293.66],
               [174.61, 220.00, 261.63, 349.23], [130.81, 196.00, 261.63, 329.63]]
    bajos = [73.42, 58.27, 87.31, 65.41]
    largo = 8.0
    salida = np.zeros(n)
    for k in range(int(segundos // largo) + 2):
        t0 = k * largo - 1.5
        i0, i1 = max(0, int(t0 * SR)), min(n, int((t0 + largo + 3.0) * SR))
        if i0 >= i1:
            continue
        tt = t[i0:i1] - t0
        env = np.clip(tt / 2.5, 0, 1) * np.clip((largo + 3.0 - tt) / 3.0, 0, 1)
        env = env * env * (3 - 2 * env)
        acorde = acordes[k % 4]
        s = np.zeros(i1 - i0)
        for f in acorde:
            for desaf in (-0.6, 0.6):
                fase = 2 * np.pi * (f + desaf) * tt
                s += np.sin(fase) + 0.25 * np.sin(2 * fase) + 0.08 * np.sin(3 * fase)
        s += 1.6 * np.sin(2 * np.pi * bajos[k % 4] * tt)
        salida[i0:i1] += s * env
    trem = 1 + 0.06 * np.sin(2 * np.pi * 0.11 * t)
    salida *= trem
    # filtro paso bajo sencillo (dos polos) para quitarle brillo
    b = np.exp(-2 * np.pi * 1800 / SR)
    for _ in range(2):
        salida = lfilter1(salida, b)
    salida /= np.max(np.abs(salida)) + 1e-9
    return salida.astype(np.float32)


def lfilter1(x: np.ndarray, b: float) -> np.ndarray:
    try:
        from scipy.signal import lfilter
        return lfilter([1 - b], [1, -b], x)
    except ImportError:  # sin scipy: media movil equivalente aproximada
        ventana = max(1, int(1 / (1 - b)))
        return np.convolve(x, np.ones(ventana) / ventana, mode="same")


def armar_audio(escenas: list[dict], total: float, musica: str | None, sin_musica: bool, destino: Path) -> None:
    n = int(math.ceil(total * SR)) + SR
    voz = np.zeros(n, np.float32)
    for e in escenas:
        if "audio" in e:
            a = leer_audio(e["audio"])
            pico = np.max(np.abs(a)) or 1
            a = a * (0.89 / pico)  # -1 dBFS
            i = int((e["inicio"] + e["antes"]) * SR)
            voz[i:i + len(a)] += a[:max(0, n - i)]
    mezcla = voz.copy()
    if not sin_musica:
        if musica:
            m = leer_audio(Path(musica))
            if len(m) < n:
                m = np.tile(m, n // len(m) + 1)
            m = m[:n] / (np.max(np.abs(m)) or 1)
        else:
            m = musica_generada(n / SR)[:n]
        # baja la musica mientras habla la voz (envolvente suavizada de la voz)
        hay_voz = np.abs(voz) > 0.02
        bloque = SR // 20
        nb = n // bloque
        act = hay_voz[:nb * bloque].reshape(nb, bloque).any(axis=1).astype(np.float32)
        ventana = 12  # ~0,6 s
        act = np.convolve(act, np.ones(ventana * 2 + 1) / (ventana * 2 + 1), mode="same")
        act = np.clip(act * 2, 0, 1)
        nivel = 10 ** ((-17 + (-27 + 17) * act) / 20)  # -17 dB sin voz, -27 dB con voz
        nivel = np.repeat(nivel, bloque)
        nivel = np.concatenate([nivel, np.full(n - len(nivel), nivel[-1] if len(nivel) else 0.1)])
        fade = np.ones(n, np.float32)
        fi, fo = int(2.0 * SR), int(3.5 * SR)
        fin = int(total * SR)
        fade[:fi] = np.linspace(0, 1, fi)
        fade[fin - fo:fin] = np.linspace(1, 0, fo)
        fade[fin:] = 0
        mezcla += m * nivel * fade * 1.0
    mezcla = np.clip(mezcla, -1, 1)
    estereo = np.repeat((mezcla * 32767).astype(np.int16)[:, None], 2, axis=1)
    import wave
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(estereo.tobytes())


# ======================================================================= principal
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resolucion", choices=["4k", "1080"], default="4k")
    ap.add_argument("--salida", help="archivo MP4 de salida")
    ap.add_argument("--musica", help="archivo de audio para el fondo musical (en lugar del generado)")
    ap.add_argument("--sin-musica", action="store_true")
    ap.add_argument("--sin-subtitulos", action="store_true")
    ap.add_argument("--preset", default="medium", help="preset de x264 (ultrafast ... veryslow)")
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--desde", type=float, default=0, help="renderizar desde este segundo (pruebas)")
    ap.add_argument("--hasta", type=float, help="renderizar hasta este segundo (pruebas)")
    ap.add_argument("--cuadro", type=float, help="solo guarda el cuadro de ese segundo como PNG (pruebas)")
    a = ap.parse_args()

    ancho, alto = (3840, 2160) if a.resolucion == "4k" else (1920, 1080)
    escenas, total, con_voz = armar_linea_de_tiempo()
    print(f"{len(escenas)} escenas, {total:.1f} s ({total / 60:.1f} min){'' if con_voz else ' - BORRADOR: falta la locucion (locucion.py)'}")
    L = Lienzo(ancho, alto)

    def cuadro_en(T: float) -> np.ndarray:
        activas = [e for e in escenas if e["inicio"] <= T < e["inicio"] + e["dur"]] or [escenas[-1]]
        c = cuadro_escena(L, activas[0], T - activas[0]["inicio"], not a.sin_subtitulos, not con_voz)
        if len(activas) > 1:
            b = activas[1]
            c2 = cuadro_escena(L, b, T - b["inicio"], not a.sin_subtitulos, not con_voz)
            c = mezclar(c, c2, suave((T - b["inicio"]) / FUNDIDO))
        return c

    if a.cuadro is not None:
        destino = AQUI / "salida" / f"cuadro_{a.cuadro:.1f}.png"
        Image.fromarray(cuadro_en(a.cuadro)).save(destino)
        print(destino)
        return

    sufijo = "4K" if a.resolucion == "4k" else "1080p"
    nombre = f"SIETE_presentacion_{sufijo}_locucion.mp4" if con_voz else f"SIETE_presentacion_{sufijo}_BORRADOR.mp4"
    salida = Path(a.salida) if a.salida else AQUI / "salida" / nombre
    salida.parent.mkdir(parents=True, exist_ok=True)
    desde, hasta = a.desde, min(total, a.hasta or total)
    wav = AQUI / "salida" / "mezcla.wav"
    armar_audio(escenas, total, a.musica, a.sin_musica, wav)

    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ancho}x{alto}", "-r", str(FPS), "-i", "-",
           "-ss", f"{desde:.3f}", "-t", f"{hasta - desde:.3f}", "-i", str(wav),
           "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-level", "5.1" if a.resolucion == "4k" else "4.1", "-tune", "film",
           "-c:a", "aac", "-b:a", "256k", "-ar", str(SR), "-movflags", "+faststart",
           "-metadata", "title=S.I.E.T.E. - Sistema Integral de Entrenamiento Táctico y Estratégico",
           "-metadata", "artist=DIDA - Aviación Militar Bolivariana", "-shortest", str(salida)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = int(desde * FPS), int(hasta * FPS)
    reloj = time.time()
    try:
        for k in range(n0, n1):
            T = k / FPS
            ff.stdin.write(cuadro_en(T).tobytes())
            if k % (FPS * 10) == 0:
                usadas = {img for e in escenas if e["inicio"] - 2 <= T < e["inicio"] + e["dur"] for img, _ in e.get("imagenes", [])}
                L.olvidar_capturas(usadas)
                hecho = (k - n0 + 1) / (n1 - n0)
                trans = time.time() - reloj
                print(f"  {T:6.1f} s / {hasta:.0f} s  ({hecho * 100:4.1f} %, quedan ~{trans / hecho * (1 - hecho) / 60:.1f} min)", flush=True)
    finally:
        ff.stdin.close()
        ff.wait()
    if ff.returncode:
        raise SystemExit("ffmpeg fallo")
    print(f"Listo: {salida} ({salida.stat().st_size / 1e6:.0f} MB, {(time.time() - reloj) / 60:.1f} min)")


if __name__ == "__main__":
    main()
