"""Fotos que el instructor carga para un tipo de unidad (un modelo del catalogo, del sistema o propio) o para una clase.

El simulador las deja en el mismo formato que las fotos de referencia (tools/fotos/fotos_referencia.py): la unidad
recortada (sin el resto de la escena), centrada y a la misma escala sobre el fondo comun de las ilustraciones, en
720 x 405. El recorte usa `rembg` si esta instalado (pip install -r tools/fotos/requirements.txt); si no, o si el
instructor lo pide, la foto entera se encaja en el mismo marco.

Se guardan con los datos de la instalacion, no con el codigo: backend/data/fotos_usuario/ (la variable
SIMULADOR_FOTOS_USUARIO cambia la carpeta), con fotos.json como indice. Al arrancar se aplican sobre el catalogo
(catalogo.FOTOS_PROPIAS) y tienen prioridad sobre la foto de referencia o la ilustracion; quitarlas devuelve la de antes.
"""

from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path

from app.engine import catalogo

log = logging.getLogger("uvicorn.error")

CARPETA = Path(os.environ.get("SIMULADOR_FOTOS_USUARIO")
               or Path(__file__).resolve().parent.parent.parent / "data" / "fotos_usuario")
INDICE = "fotos.json"
ANCHO, ALTO = 720, 405
LADO_ENTRADA = 1600  # se reduce la foto a esto antes de recortarla
MAX_BYTES = 12 * 1024 * 1024
FORMATOS = ("JPEG", "PNG", "WEBP")
SECCIONES = ("modelos", "clases")
_NOMBRE = re.compile(r"^(modelos|clases)_[a-z0-9_]{1,60}_\d{10,}\.jpg$")
_SESION = None


class FotoInvalida(ValueError):
    """La imagen o los datos no sirven (la API lo traduce a 400)."""


# ---------------------------------------------------------------------------------------------- encuadre
def _rembg():
    """Modulo y sesion de rembg, o None si no esta instalado."""
    global _SESION
    os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(tempfile.gettempdir()) / "siete_numba"))
    try:
        import rembg
    except ImportError:
        return None
    if _SESION is None:
        _SESION = rembg.new_session("isnet-general-use")
    return rembg, _SESION


def fondo():
    """El fondo de las ilustraciones: degradado #1d2433 -> #4a5568, brillo arriba y franja de suelo."""
    from PIL import Image, ImageDraw, ImageFilter
    arriba, abajo = (0x1D, 0x24, 0x33), (0x4A, 0x55, 0x68)
    im = Image.new("RGB", (ANCHO, ALTO))
    d = ImageDraw.Draw(im)
    for y in range(ALTO):
        t = y / (ALTO - 1)
        d.line([(0, y), (ANCHO, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(arriba, abajo)))
    brillo = Image.new("L", (ANCHO, ALTO), 0)
    ImageDraw.Draw(brillo).ellipse([ANCHO * -0.1, ALTO * -0.25, ANCHO * 1.1, ALTO * 0.95], fill=42)
    im = Image.composite(Image.new("RGB", im.size, "white"), im, brillo.filter(ImageFilter.GaussianBlur(120)))
    suelo = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    ImageDraw.Draw(suelo).rectangle([0, round(ALTO * 300 / 360), ANCHO, ALTO], fill=(0x3B, 0x4A, 0x3A, 140))
    return Image.alpha_composite(im.convert("RGBA"), suelo)


def _solo_lo_principal(alfa, minimo: float = 0.3):
    """La pieza mas grande de la mascara y las que miden al menos `minimo` de ella (quita personas o restos sueltos)."""
    try:
        import numpy as np
        from scipy import ndimage
    except ImportError:
        return alfa
    from PIL import Image
    m = np.array(alfa) > 24
    etiquetas, n = ndimage.label(m)
    if n <= 1:
        return alfa
    areas = ndimage.sum(m, etiquetas, range(1, n + 1))
    quedan = [i + 1 for i, a in enumerate(areas) if a >= minimo * areas.max()]
    return Image.fromarray(np.where(np.isin(etiquetas, quedan), np.array(alfa), 0).astype("uint8"))


def _sobre_fondo(recorte, ancho_max: float, alto_max: float, sombra: bool):
    from PIL import Image, ImageDraw, ImageFilter
    k = min(ANCHO * ancho_max / recorte.width, ALTO * alto_max / recorte.height)
    recorte = recorte.resize((max(1, round(recorte.width * k)), max(1, round(recorte.height * k))), Image.LANCZOS)
    lienzo = fondo()
    x, y = (ANCHO - recorte.width) // 2, round(ALTO * 0.52 - recorte.height / 2)
    if sombra:
        capa = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
        base = y + recorte.height
        ImageDraw.Draw(capa).ellipse([x + recorte.width * 0.1, base - 6, x + recorte.width * 0.9, base + 16], fill=(0, 0, 0, 90))
        lienzo = Image.alpha_composite(lienzo, capa.filter(ImageFilter.GaussianBlur(8)))
    lienzo.alpha_composite(recorte.convert("RGBA"), (x, y))
    return lienzo.convert("RGB")


def encuadrar(img, recortar: bool = True):
    """(imagen de 720 x 405, metodo): "recorte" (la unidad sola sobre el fondo comun) o "marco" (la foto entera)."""
    r = _rembg() if recortar else None
    if r is not None:
        rembg, sesion = r
        recorte = rembg.remove(img.convert("RGB"), session=sesion, post_process_mask=True).convert("RGBA")
        recorte.putalpha(_solo_lo_principal(recorte.getchannel("A")))
        caja = recorte.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
        if caja and (caja[2] - caja[0]) * (caja[3] - caja[1]) > 0.02 * img.width * img.height:
            return _sobre_fondo(recorte.crop(caja), 0.84, 0.66, True), "recorte"
    return _sobre_fondo(img.convert("RGB"), 0.9, 0.8, False), "marco"


# ---------------------------------------------------------------------------------------------- indice
def _leer() -> dict:
    ruta = CARPETA / INDICE
    if not ruta.is_file():
        return {s: {} for s in SECCIONES}
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.warning("fotos del instructor: no se pudo leer %s: %s (se ignora)", ruta, e)
        return {s: {} for s in SECCIONES}
    return {s: dict(d.get(s) or {}) for s in SECCIONES}


def _escribir(d: dict) -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    tmp = CARPETA / (INDICE + ".tmp")
    tmp.write_text(json.dumps({"_comentario": "Fotos cargadas por el instructor (Consola -> Catalogo propio).", **d},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(CARPETA / INDICE)


def url(nombre: str) -> str:
    return f"/api/catalogo/fotos/archivo/{nombre}"


def aplicar() -> int:
    """Pone en el catalogo las fotos del indice que existen. Devuelve cuantas."""
    catalogo.FOTOS_PROPIAS.clear()
    for seccion, entradas in _leer().items():
        for id_, e in entradas.items():
            if (CARPETA / str(e.get("archivo", ""))).is_file():
                catalogo.FOTOS_PROPIAS[f"{seccion}:{id_}"] = {
                    "foto": url(e["archivo"]),
                    "credito": {"obra": e.get("obra") or "", "autor": e.get("autor") or "Foto cargada por el instructor",
                                "licencia": e.get("licencia") or "uso académico", "url_licencia": "",
                                "pagina": e.get("fuente") or ""}}
    return len(catalogo.FOTOS_PROPIAS)


def archivo(nombre: str) -> Path | None:
    """La ruta de una foto guardada (None si el nombre no es valido o no existe)."""
    if not _NOMBRE.match(nombre or ""):
        return None
    ruta = CARPETA / nombre
    return ruta if ruta.is_file() else None


# ---------------------------------------------------------------------------------------------- carga y quita
def _decodificar(imagen: str) -> bytes:
    texto = (imagen or "").strip()
    if texto.startswith("data:"):
        texto = texto.split(",", 1)[-1]
    try:
        datos = base64.b64decode(texto, validate=True)
    except (binascii.Error, ValueError):
        raise FotoInvalida("La imagen no llegó bien (base64 inválido)") from None
    if not datos:
        raise FotoInvalida("Falta la imagen")
    if len(datos) > MAX_BYTES:
        raise FotoInvalida(f"La imagen pesa más de {MAX_BYTES // (1024 * 1024)} MB")
    return datos


def _objetivo_valido(seccion: str, id_: str) -> str:
    if seccion == "modelos" and id_ in catalogo.MODELOS:
        return catalogo.MODELOS[id_].nombre
    if seccion == "clases" and id_ in catalogo.CLASES:
        return catalogo.CLASES[id_].nombre
    raise FotoInvalida("Elija un tipo de unidad o una clase del catálogo")


def guardar(seccion: str, id_: str, imagen: str, autor: str = "", fuente: str = "", recortar: bool = True) -> dict:
    """Procesa y guarda la foto de un tipo (o clase); queda puesta al instante. Devuelve {foto, metodo, nombre}."""
    from PIL import Image, UnidentifiedImageError
    nombre_objetivo = _objetivo_valido(seccion, id_)
    datos = _decodificar(imagen)
    try:
        img = Image.open(io.BytesIO(datos))
        formato = img.format
        img.load()
    except (UnidentifiedImageError, OSError):
        raise FotoInvalida("El archivo no es una imagen (use JPG, PNG o WEBP)") from None
    if formato not in FORMATOS:
        raise FotoInvalida("Formato no admitido: use JPG, PNG o WEBP")
    img = img.convert("RGB")
    img.thumbnail((LADO_ENTRADA, LADO_ENTRADA), Image.LANCZOS)
    final, metodo = encuadrar(img, recortar)
    CARPETA.mkdir(parents=True, exist_ok=True)
    nombre = f"{seccion}_{re.sub(r'[^a-z0-9_]', '_', id_.lower())[:60]}_{time.time_ns() // 1000}.jpg"
    final.save(CARPETA / nombre, "JPEG", quality=86, optimize=True, progressive=True)
    (CARPETA / "originales").mkdir(exist_ok=True)
    img.save(CARPETA / "originales" / nombre, "JPEG", quality=88)
    d = _leer()
    previa = d[seccion].get(id_)
    d[seccion][id_] = {"archivo": nombre, "obra": nombre_objetivo, "autor": (autor or "").strip()[:120],
                       "fuente": (fuente or "").strip()[:300], "licencia": "uso académico", "metodo": metodo}
    _escribir(d)
    if previa and previa.get("archivo") != nombre:
        for ruta in (CARPETA / previa["archivo"], CARPETA / "originales" / previa["archivo"]):
            ruta.unlink(missing_ok=True)
    aplicar()
    return {"foto": url(nombre), "metodo": metodo, "nombre": nombre_objetivo}


def quitar(seccion: str, id_: str) -> bool:
    """Quita la foto del instructor: vuelve la de referencia o la ilustracion."""
    d = _leer()
    e = d.get(seccion, {}).pop(id_, None)
    if e is None:
        return False
    _escribir(d)
    for ruta in (CARPETA / e.get("archivo", "-"), CARPETA / "originales" / e.get("archivo", "-")):
        if ruta.name != "-":
            ruta.unlink(missing_ok=True)
    aplicar()
    return True


def listado() -> dict:
    return {s: {id_: {k: e.get(k) for k in ("autor", "fuente", "metodo")} | {"foto": url(e["archivo"])}
                for id_, e in entradas.items()} for s, entradas in _leer().items()}


aplicar()
