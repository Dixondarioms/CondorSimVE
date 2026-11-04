"""Fotos de referencia de las aeronaves, drones y buques del simulador, desde Wikimedia Commons.

Se ejecuta en un equipo con internet (el del instructor). Para cada unidad busca en Commons fotos con licencia
libre (CC BY, CC BY-SA, CC0 o dominio publico), descarga la mejor, la reduce a 720 px y anota autor, licencia y
origen en frontend/static/fotos/referencias.json, que el servidor lee al arrancar (ver
backend/app/engine/catalogo.py, aplicar_referencias). Tambien rehace la tabla de creditos de
frontend/static/fotos/CREDITOS.md y deja una hoja con las fotos candidatas para revisarlas:

    backend\\venv\\Scripts\\python tools/fotos/fotos_referencia.py                    # descarga lo que falte
    backend\\venv\\Scripts\\python tools/fotos/fotos_referencia.py --elegir helo_ataque=3
    backend\\venv\\Scripts\\python tools/fotos/fotos_referencia.py --archivo fragata="File:Nombre.jpg"
    backend\\venv\\Scripts\\python tools/fotos/fotos_referencia.py --forzar           # vuelve a elegir todas
    backend\\venv\\Scripts\\python tools/fotos/fotos_referencia.py --quitar destructor  # vuelve al dibujo
    backend\\venv\\Scripts\\python tools/fotos/fotos_referencia.py --uniformar         # rehace el encuadre sin red

Encuadre uniforme: si esta instalado `rembg` (pip install -r tools/fotos/requirements.txt), cada foto se recorta
(solo la aeronave o el buque, sin el resto de la escena) y se centra, a un mismo tamano, sobre el mismo fondo que
las ilustraciones del simulador (720 x 405). El original reducido queda en tools/fotos/originales/ para rehacerlo
con --uniformar, que tambien encuadra las fotos del catalogo (F-16 y Su-30). Sin `rembg`, se guarda la foto tal cual.

La hoja tools/fotos/salida/candidatas.html muestra, por unidad, las candidatas numeradas y la elegida; con
--elegir <clave>=<numero> se cambia por otra. Donde la FANB tiene el equipo se busca primero el venezolano; para
el resto (destructor, portaaviones, guerra electronica...) se usa un ejemplo real como imagen de referencia.
El F-16 y el Su-30 ya tienen su foto en el catalogo y no se tocan. Despues de descargar, reinicie el servidor.
"""

import argparse
import html
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2]
FOTOS = RAIZ / "frontend" / "static" / "fotos"
MANIFIESTO = FOTOS / "referencias.json"
CREDITOS = FOTOS / "CREDITOS.md"
SALIDA = Path(__file__).resolve().parent / "salida"
ORIGINALES = Path(__file__).resolve().parent / "originales"  # fotos reducidas sin encuadrar (para --uniformar)
FOTOS_CATALOGO = ("f16.jpg", "su30.jpg")  # fotos del catalogo que tambien se encuadran
ANCHO, ALTO = 960, 540  # 16:9, como las ilustraciones SVG (640 x 360), con resolucion para pantallas densas
API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia pide un User-Agent que identifique la herramienta.
AGENTE = "SIETE-simulador/1.0 (fotos de referencia; https://github.com/Dixondarioms/simulador-fenix)"
LADO_MAX = 1280
CANDIDATAS = 8
CANDIDATAS_AUTO = 16  # con --auto se revisan hasta estas por unidad
INICIO_TABLA, FIN_TABLA = "<!-- referencias:inicio -->", "<!-- referencias:fin -->"

# (seccion, clave, que representa, busquedas en orden de preferencia). "modelos": modelos de aeronave de
# catalogo.MODELOS; "clases": clases de catalogo.CLASES sin modelo (los buques).
UNIDADES = [
    ("modelos", "ataque_ligero", "Avion de ataque ligero", ["K-8W Venezuela", "Hongdu K-8 Karakorum"]),
    ("modelos", "helo_ataque", "Helicoptero de ataque", ["Mi-35M Venezuela", "Mi-35M"]),
    ("modelos", "helo_transporte", "Helicoptero de transporte artillado", ["Mi-17V-5 Venezuela", "Mi-17 Venezuela",
                                                                            "Mi-17V-5"]),
    ("modelos", "uav_reco", "Dron de reconocimiento", ["ANSU-100", "Arpia UAV Venezuela", "ScanEagle UAV"]),
    ("modelos", "uav_armado", "Dron armado", ["ANSU-200", "Mohajer drone", "MQ-1 Predator"]),
    ("modelos", "merodeadora", "Municion merodeadora", ["IAI Harop", "Switchblade loitering munition"]),
    ("modelos", "ge_aereo", "Avion de guerra electronica", ["EC-130H Compass Call", "EA-18G Growler"]),
    ("modelos", "caza_embarcado", "Caza embarcado", ["F/A-18E Super Hornet aircraft carrier", "Rafale M carrier"]),
    ("modelos", "crucero", "Misil de crucero", ["Tomahawk cruise missile launch", "Kalibr cruise missile"]),
    # sistemas de defensa aerea (engine/defensa_aerea.py)
    ("modelos", "zu23_2", "Canon antiaereo ZU-23-2", ["ZU-23-2 Venezuela", "ZU-23-2"]),
    ("modelos", "pechora_2m", "S-125 Pechora-2M", ["Pechora-2M Venezuela", "S-125 Pechora-2M", "S-125 Neva"]),
    ("modelos", "buk_m2e", "Buk-M2E", ["Buk-M2E Venezuela", "Buk-M2E", "9A317 Buk-M2"]),
    ("modelos", "s300vm", "S-300VM Antey-2500", ["S-300VM Venezuela", "S-300VM Antey-2500", "9A83 launcher"]),
    # clases terrestres sin modelo (la foto es la de la clase)
    ("clases", "infanteria", "Infanteria", ["Venezuelan Army soldiers", "Ejercito Bolivariano soldados", "infantry soldiers rifle"]),
    ("clases", "blindado", "Tanque", ["T-72B1 Venezuela", "T-72B1 tank", "T-72B tank"]),
    ("clases", "artilleria", "Artilleria autopropulsada", ["2S19 Msta-S Venezuela", "2S19 Msta-S", "Msta-S howitzer"]),
    ("clases", "reconocimiento", "Vehiculo de reconocimiento", ["BRDM-2 Venezuela", "BRDM-2"]),
    ("clases", "ingenieros", "Ingenieros de combate", ["IMR-2 engineering vehicle", "combat engineering vehicle", "MT-55 bridge layer"]),
    ("clases", "transporte", "Convoy logistico", ["Kamaz Venezuela", "Kamaz 6350 military truck", "Kamaz military truck"]),
    ("clases", "lanzador_misiles", "Lanzacohetes", ["BM-30 Smerch Venezuela", "9A52-2 Smerch", "BM-30 Smerch"]),
    ("clases", "radar", "Radar de vigilancia", ["JY-27 radar", "JYL-1 radar", "P-18 radar"]),
    ("clases", "guerra_electronica", "Guerra electronica", ["electronic warfare vehicle", "Krasukha-4", "R-330Zh Zhitel"]),
    ("clases", "antiaerea_portatil", "Antiaerea portatil", ["Igla-S Venezuela", "9K338 Igla-S", "Igla MANPADS"]),
    ("clases", "antiaerea", "Antiaerea", ["Pechora-2M Venezuela", "surface-to-air missile launcher"]),
    ("clases", "artilleria_antiaerea", "Artilleria antiaerea", ["ZU-23-2 Venezuela", "ZU-23-2"]),
    ("modelos", "mistral", "Misil Mistral", ["Mistral missile Venezuela", "Mistral MANPADS", "Mistral ATLAS"]),
    ("modelos", "rbs70", "RBS 70", ["RBS 70 Venezuela", "RBS 70", "RBS-70 missile"]),
    # aeronaves de EE. UU. de la plantilla del 3 de enero de 2026 (fotos oficiales de dominio publico, en su mayoria)
    ("modelos", "f22", "F-22A Raptor", ["F-22 Raptor flight", "F-22A Raptor"]),
    ("modelos", "f35a", "F-35A Lightning II", ["F-35A Lightning II flight", "F-35A Lightning II"]),
    ("modelos", "f35b", "F-35B Lightning II", ["F-35B Lightning II flight", "F-35B Lightning II"]),
    ("modelos", "fa18ef", "F/A-18E/F Super Hornet", ["F/A-18E Super Hornet flight", "F/A-18F Super Hornet flight"]),
    ("modelos", "ea18g", "EA-18G Growler", ["EA-18G Growler flight", "EA-18G Growler"]),
    ("modelos", "b1b", "B-1B Lancer", ["B-1B Lancer flight", "B-1B Lancer"]),
    ("modelos", "p8a", "P-8A Poseidon", ["P-8A Poseidon flight", "P-8A Poseidon"]),
    ("modelos", "e2d", "E-2D Advanced Hawkeye", ["E-2D Advanced Hawkeye flight", "E-2D Hawkeye"]),
    ("modelos", "e3g", "E-3G Sentry (AWACS)", ["E-3 Sentry AWACS flight", "E-3 Sentry"]),
    ("modelos", "rc135", "RC-135V/W Rivet Joint", ["RC-135V Rivet Joint", "RC-135W Rivet Joint"]),
    ("modelos", "ec130h", "EC-130H Compass Call", ["EC-130H Compass Call flight", "EC-130H Compass Call"]),
    ("modelos", "kc135", "KC-135R Stratotanker", ["KC-135 Stratotanker flight", "KC-135R Stratotanker"]),
    ("modelos", "rq170", "RQ-170 Sentinel", ["RQ-170 Sentinel", "RQ-170 Sentinel replica"]),
    ("modelos", "mq9", "MQ-9A Reaper", ["MQ-9 Reaper flight", "MQ-9 Reaper"]),
    ("modelos", "lucas", "Dron de ataque de un solo uso (tipo LUCAS)", ["LUCAS one-way attack drone", "SpektreWorks FLM 136"]),
    ("modelos", "mh47g", "MH-47G Chinook", ["MH-47G Chinook", "MH-47 Chinook 160th"]),
    ("modelos", "mh60m", "MH-60M Black Hawk", ["MH-60M Black Hawk", "MH-60 Black Hawk 160th"]),
    ("modelos", "mh60dap", "MH-60M DAP", ["MH-60 DAP Black Hawk", "MH-60L DAP"]),
    ("modelos", "ah6m", "AH-6M Little Bird", ["AH-6M Little Bird", "AH-6 Little Bird"]),
    ("modelos", "mh6m", "MH-6M Little Bird", ["MH-6M Little Bird", "MH-6 Little Bird"]),
    ("clases", "fragata", "Fragata", ["Mariscal Sucre F-21", "Almirante Brion F-22", "fragata Venezuela Armada"]),
    ("clases", "patrullero", "Patrullero", ["GC-21 Guaicamacuto", "Guaicamacuto", "PC-22 Warao",
                                            "Armada Bolivariana patrullero"]),
    ("clases", "destructor", "Destructor", ["Arleigh Burke class destroyer underway"]),
    ("clases", "portaaviones", "Portaaviones", ["Nimitz class aircraft carrier underway", "Charles de Gaulle R91"]),
    ("clases", "submarino", "Submarino", ["Sabalo S-31 submarino", "submarino Armada Venezuela",
                                          "Type 209 submarine"]),
    ("clases", "buque_desembarco", "Buque de desembarco anfibio", ["Capana T-61", "clase Capana", "T-64 Los Llanos",
                                                                   "landing ship tank"]),
    # trafico civil (engine/trafico.py)
    ("clases", "buque_mercante", "Buque mercante", ["container ship at sea", "cargo ship Caribbean", "bulk carrier at sea"]),
    ("clases", "pesquero", "Pesquero", ["fishing boat Venezuela", "fishing trawler at sea", "Margarita fishing boat"]),
    # guerra antisubmarina (engine/asw.py)
    ("clases", "torpedo", "Torpedo", ["Mark 48 torpedo", "Mk 54 torpedo", "heavyweight torpedo museum"]),
    # misiles balisticos (engine/balisticos.py)
    ("clases", "lanzador_balistico", "Lanzador de misiles balísticos", ["Iskander-M launcher", "9K720 Iskander", "Iskander TEL"]),
    # minas navales (engine/minas.py)
    ("clases", "cazaminas", "Cazaminas", ["minehunter underway", "Tripartite class minehunter", "Avenger class mine countermeasures ship"]),
    # reabastecimiento en el mar (engine/orders.py, convoyes navales)
    ("clases", "buque_logistico", "Buque logístico", ["replenishment at sea", "underway replenishment oiler", "fleet replenishment oiler"]),
]
# catalogo ampliado del Condor (backend/app/engine/catalogo_ampliado.py) y modelos que cambiaron de identidad
sys.path.insert(0, str(Path(__file__).resolve().parent))
from busquedas_ampliado import BUSQUEDAS, RENOVAR  # noqa: E402

for _i, _consultas in RENOVAR.items():
    UNIDADES = [u if u[1] != _i else (u[0], u[1], _consultas[0], _consultas) for u in UNIDADES]
UNIDADES += [("modelos", _i, _consultas[0], _consultas) for _i, _consultas in BUSQUEDAS.items()]
POR_CLAVE = {clave: (seccion, que, busquedas) for seccion, clave, que, busquedas in UNIDADES}


def _pedir(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _bajar(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=120) as r:
        return r.read()


def _texto(valor: str) -> str:
    """Quita el HTML de los metadatos de Commons (el autor suele venir como enlace)."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", valor or ""))).strip()


def licencia_libre(nombre: str) -> bool:
    n = nombre.lower()
    if "nc" in re.split(r"[\s\-]", n) or "nd" in re.split(r"[\s\-]", n):
        return False
    return n.startswith(("cc by", "cc-by", "cc0", "public domain", "pd")) or n == "attribution"


_PROPS = {"prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1600",
          "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|ObjectName"}


def _autor(texto: str) -> str:
    """Autor corto: algunas fichas de Commons traen en el autor todo el texto de su plantilla de licencia."""
    if not texto:
        return "Desconocido"
    return texto if len(texto) <= 100 else texto[:97].rsplit(" ", 1)[0] + "..."


def _candidata(pagina: dict) -> dict | None:
    info = (pagina.get("imageinfo") or [None])[0]
    if not info or info.get("mime") not in ("image/jpeg", "image/png"):
        return None
    meta = info.get("extmetadata") or {}
    licencia = _texto((meta.get("LicenseShortName") or {}).get("value", ""))
    if not licencia_libre(licencia):
        return None
    titulo = pagina["title"]
    return {
        "titulo": titulo,
        "obra": _texto((meta.get("ObjectName") or {}).get("value", "")) or Path(titulo.split(":", 1)[1]).stem,
        "autor": _autor(_texto((meta.get("Artist") or {}).get("value", ""))),
        "licencia": licencia,
        "url_licencia": (meta.get("LicenseUrl") or {}).get("value", "") or "https://commons.wikimedia.org/wiki/Commons:Licensing",
        "pagina": info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(titulo)}",
        "miniatura": info.get("thumburl") or info["url"],
        "ancho": info.get("width", 0), "alto": info.get("height", 0),
    }


# titulos que no muestran la plataforma (mapas de operadores, sellos, tripulaciones, ceremonias, diagramas...)
DESCARTAR = re.compile(r"operators|operadores|\bmap\b|mapa|stamp|booklet|sailors|secretary|ceremon|cerim|flag|logo|"
                       r"diagram|insignia|patch|cockpit|interior|crew|personnel|soldiers|wreck|destroyed|"
                       r"explosion|shock\s*trial|airport|aeroporto|aeropuerto|rendering|model\b|toy|stamp|"
                       r"зоны|caracal-\d|blenny|escenius|formation|formacion|\bpair\b|\b\d+\s*x\s|\band\b|\bwith\b|\bteam\b|"
                       r"flypast|lineup|line-up|parade|desfile", re.IGNORECASE)


def buscar(busquedas: list[str], cuantas: int = CANDIDATAS) -> list[dict]:
    """Candidatas con licencia libre, apaisadas y de buen tamano, en el orden de las busquedas."""
    vistas, candidatas = set(), []
    for consulta in busquedas:
        datos = _pedir({"action": "query", "generator": "search", "gsrsearch": f"{consulta} filetype:bitmap",
                        "gsrnamespace": "6", "gsrlimit": "20", **_PROPS})
        paginas = sorted((datos.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
        for p in paginas:
            c = _candidata(p)
            if (c and c["titulo"] not in vistas and c["ancho"] >= 800 and c["ancho"] >= c["alto"]
                    and not DESCARTAR.search(c["titulo"])):
                vistas.add(c["titulo"])
                candidatas.append(c)
        if len(candidatas) >= cuantas:
            break
    return candidatas[:cuantas]


def por_titulo(titulo: str) -> dict:
    if not titulo.startswith("File:"):
        titulo = "File:" + titulo
    paginas = (_pedir({"action": "query", "titles": titulo, **_PROPS}).get("query") or {}).get("pages") or []
    c = _candidata(paginas[0]) if paginas else None
    if c is None:
        raise SystemExit(f"{titulo}: no existe en Commons, no es JPG/PNG o su licencia no es libre.")
    return c


# ---------------------------------------------------------------- encuadre uniforme
_SESION = None


def _rembg():
    """Modulo y sesion de rembg, o None si no esta instalado (la foto se guarda entonces sin encuadrar)."""
    global _SESION
    import os
    import tempfile
    # numba (dependencia de rembg) guarda una cache junto al paquete; en Windows la ruta puede pasar de 260 letras
    os.environ.setdefault("NUMBA_CACHE_DIR", str(Path(tempfile.gettempdir()) / "siete_numba"))
    try:
        import rembg
    except ImportError:
        return None
    if _SESION is None:
        _SESION = rembg.new_session("isnet-general-use")
    return rembg, _SESION


def fondo() -> Image.Image:
    """El fondo de las ilustraciones SVG: degradado #1d2433 -> #4a5568, brillo arriba y franja de suelo."""
    from PIL import ImageDraw, ImageFilter
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


def solo_lo_principal(alfa: Image.Image, minimo: float = 0.3) -> Image.Image:
    """Deja en la mascara la pieza mas grande y las que miden al menos `minimo` de ella (quita lanchas, personas
    o restos sueltos de la escena)."""
    import numpy as np
    from scipy import ndimage
    m = np.array(alfa) > 24
    etiquetas, n = ndimage.label(m)
    if n <= 1:
        return alfa
    areas = ndimage.sum(m, etiquetas, range(1, n + 1))
    quedan = [i + 1 for i, a in enumerate(areas) if a >= minimo * areas.max()]
    return Image.fromarray(np.where(np.isin(etiquetas, quedan), np.array(alfa), 0).astype("uint8"))


def evaluar(img: Image.Image) -> tuple[bool, str]:
    """La foto sirve de referencia si, recortado el fondo, queda una sola pieza grande (sin otra aeronave, personas ni
    vehiculos al lado), entera (no cortada por dos bordes) y con resolucion (al menos 520 px de ancho)."""
    import numpy as np
    from scipy import ndimage
    r = _rembg()
    if r is None:
        return True, "sin rembg: no se revisa"
    rembg, sesion = r
    alfa = np.array(rembg.remove(img.convert("RGB"), session=sesion, post_process_mask=True,
                                 only_mask=True)) > 24
    etiquetas, n = ndimage.label(alfa)
    if n == 0:
        return False, "no se distingue nada"
    areas = ndimage.sum(alfa, etiquetas, range(1, n + 1))
    principal = int(np.argmax(areas)) + 1
    otras = sum(1 for i, a in enumerate(areas) if i + 1 != principal and a >= 0.05 * areas.max())
    if otras:
        return False, f"{otras} pieza(s) mas ademas de la principal (otra aeronave, personas o vehiculos)"
    ys, xs = np.nonzero(etiquetas == principal)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    if x1 - x0 < 520:
        return False, f"la aeronave mide solo {x1 - x0} px de ancho"
    bordes = (x0 <= 2) + (x1 >= img.width - 3) + (y0 <= 2) + (y1 >= img.height - 3)
    if bordes >= 2:
        return False, "la aeronave sale cortada por los bordes"
    if (x1 - x0) * (y1 - y0) > 0.92 * img.width * img.height:
        return False, "el recorte ocupa toda la foto (no separo la aeronave del fondo)"
    return True, "ok"


def encuadrar(img: Image.Image) -> Image.Image | None:
    """La aeronave o el buque recortado, centrado y a la misma escala sobre el fondo comun (None sin rembg)."""
    from PIL import ImageDraw, ImageFilter
    r = _rembg()
    if r is None:
        return None
    rembg, sesion = r
    recorte = rembg.remove(img.convert("RGB"), session=sesion, post_process_mask=True).convert("RGBA")
    recorte.putalpha(solo_lo_principal(recorte.getchannel("A")))
    caja = recorte.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if caja:
        recorte = recorte.crop(caja)
    k = min(ANCHO * 0.84 / recorte.width, ALTO * 0.66 / recorte.height)
    recorte = recorte.resize((max(1, round(recorte.width * k)), max(1, round(recorte.height * k))), Image.LANCZOS)
    lienzo = fondo()
    x, y = (ANCHO - recorte.width) // 2, round(ALTO * 0.52 - recorte.height / 2)
    sombra = Image.new("RGBA", lienzo.size, (0, 0, 0, 0))
    base = y + recorte.height
    ImageDraw.Draw(sombra).ellipse([x + recorte.width * 0.1, base - 6, x + recorte.width * 0.9, base + 16],
                                   fill=(0, 0, 0, 90))
    lienzo = Image.alpha_composite(lienzo, sombra.filter(ImageFilter.GaussianBlur(8)))
    lienzo.alpha_composite(recorte, (x, y))
    return lienzo.convert("RGB")


def publicar(original: Image.Image, nombre: str) -> None:
    """Guarda el original en tools/fotos/originales y la version encuadrada (o el original) en las fotos."""
    ORIGINALES.mkdir(parents=True, exist_ok=True)
    original.save(ORIGINALES / nombre, "JPEG", quality=88, optimize=True)
    final = encuadrar(original) or original
    final.save(FOTOS / nombre, "JPEG", quality=85, optimize=True, progressive=True)


def uniformar_todas() -> None:
    """Rehace el encuadre de todas las fotos desde sus originales (sin red)."""
    if _rembg() is None:
        raise SystemExit("Falta rembg: backend\\venv\\Scripts\\python -m pip install -r tools\\fotos\\requirements.txt")
    ORIGINALES.mkdir(parents=True, exist_ok=True)
    # la primera vez (fotos del catalogo o bajadas antes del encuadre), la foto publicada es el original
    for nombre in [*FOTOS_CATALOGO, *(f.name for f in FOTOS.glob("ref_*.jpg"))]:
        if not (ORIGINALES / nombre).is_file() and (FOTOS / nombre).is_file():
            (ORIGINALES / nombre).write_bytes((FOTOS / nombre).read_bytes())
    for original in sorted(ORIGINALES.glob("*.jpg")):
        encuadrar(Image.open(original).convert("RGB")).save(FOTOS / original.name, "JPEG", quality=85, optimize=True,
                                                            progressive=True)
        print(f"  {original.name}: encuadrada")


def bajar_imagen(c: dict) -> Image.Image:
    img = Image.open(io.BytesIO(_bajar(c["miniatura"]))).convert("RGB")
    img.thumbnail((LADO_MAX, LADO_MAX), Image.LANCZOS)
    return img


def guardar_foto(clave: str, c: dict, img: Image.Image | None = None) -> str:
    nombre = f"ref_{clave}.jpg"
    publicar(img or bajar_imagen(c), nombre)
    return f"/static/fotos/{nombre}"


def elegir_automatica(clave: str, busquedas: list[str]) -> tuple[dict | None, Image.Image | None, list[str]]:
    """La primera candidata que pasa el control de calidad (evaluar), y el motivo de cada descarte."""
    motivos = []
    for i, c in enumerate(buscar(busquedas, CANDIDATAS_AUTO), 1):
        try:
            img = bajar_imagen(c)
        except OSError as e:
            motivos.append(f"{i}: no se pudo bajar ({e})")
            continue
        if min(img.size) < 500:
            motivos.append(f"{i}: foto chica ({img.width} x {img.height})")
            continue
        ok, motivo = evaluar(img)
        if ok:
            return c, img, motivos
        motivos.append(f"{i} ({c['titulo'][5:60]}): {motivo}")
    return None, None, motivos


def leer_manifiesto() -> dict:
    if MANIFIESTO.is_file():
        datos = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
        return {"modelos": datos.get("modelos") or {}, "clases": datos.get("clases") or {}}
    return {"modelos": {}, "clases": {}}


def escribir_manifiesto(m: dict) -> None:
    datos = {"_comentario": "Generado por tools/fotos/fotos_referencia.py: fotos de referencia de Wikimedia Commons.",
             "modelos": dict(sorted(m["modelos"].items())), "clases": dict(sorted(m["clases"].items()))}
    MANIFIESTO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _md(texto: str) -> str:
    return texto.replace("|", "\\|")


def escribir_creditos(m: dict) -> None:
    filas = ["| Archivo | Unidad | Obra | Autor | Licencia | Origen |", "|---|---|---|---|---|---|"]
    for seccion, clave, que, _ in UNIDADES:
        e = m[seccion].get(clave)
        if e:
            filas.append(f"| `{Path(e['foto']).name}` | `{clave}` · {que} | {_md(e['obra'])} | {_md(e['autor'])} | "
                         f"[{_md(e['licencia'])}]({e['url_licencia']}) | {e['pagina']} |")
    bloque = "\n".join([INICIO_TABLA, "## Fotos de referencia (Wikimedia Commons)", "",
                        "Descargadas por `tools/fotos/fotos_referencia.py`, reducidas y recortadas sobre un fondo "
                        "uniforme (los originales reducidos están en `tools/fotos/originales/`). "
                        "Donde la FANB no tiene el equipo, la foto es un ejemplo real que sirve de referencia; las "
                        "cifras del simulador siguen siendo genéricas.", "", *filas, FIN_TABLA])
    texto = CREDITOS.read_text(encoding="utf-8")
    if INICIO_TABLA in texto:
        antes, resto = texto.split(INICIO_TABLA, 1)
        texto = antes + bloque + resto.split(FIN_TABLA, 1)[1]
    else:
        texto = texto.rstrip("\n") + "\n\n" + bloque + "\n"
    CREDITOS.write_text(texto, encoding="utf-8")


def escribir_hoja(candidatas: dict, m: dict) -> Path:
    SALIDA.mkdir(parents=True, exist_ok=True)
    partes = ["<!doctype html><meta charset='utf-8'><title>Fotos candidatas</title><style>"
              "body{font:14px sans-serif;background:#111;color:#ddd;margin:16px}h2{margin:24px 0 6px}"
              ".fila{display:flex;flex-wrap:wrap;gap:10px}figure{margin:0;width:230px;background:#222;padding:6px;"
              "border:2px solid #333}figure.elegida{border-color:#4c4}img{width:100%;height:140px;object-fit:cover}"
              "figcaption{font-size:11px}code{color:#9cf}</style>",
              "<h1>Fotos de referencia: candidatas</h1><p>Para cambiar una: <code>fotos_referencia.py --elegir "
              "&lt;clave&gt;=&lt;numero&gt;</code>. En verde, la elegida.</p>"]
    for seccion, clave, que, _ in UNIDADES:
        elegida = (m[seccion].get(clave) or {}).get("pagina")
        partes.append(f"<h2>{html.escape(que)} <code>{clave}</code></h2><div class='fila'>")
        lista = candidatas.get(clave) or []
        if not lista:
            partes.append("<p>(sin buscar en esta ejecucion; use --forzar o --elegir para ver candidatas)</p>")
        for i, c in enumerate(lista, 1):
            clase = " class='elegida'" if c["pagina"] == elegida else ""
            partes.append(f"<figure{clase}><a href='{html.escape(c['pagina'])}' target='_blank'>"
                          f"<img src='{html.escape(c['miniatura'])}' loading='lazy'></a><figcaption><b>{i}</b> · "
                          f"{html.escape(c['obra'])}<br>{html.escape(c['autor'])} · {html.escape(c['licencia'])}"
                          f"</figcaption></figure>")
        partes.append("</div>")
    hoja = SALIDA / "candidatas.html"
    hoja.write_text("\n".join(partes), encoding="utf-8")
    return hoja


def _pares(valores: list[str], opcion: str) -> dict:
    pares = {}
    for v in valores or []:
        clave, _, dato = v.partition("=")
        if clave not in POR_CLAVE or not dato:
            raise SystemExit(f"{opcion} {v!r}: use <clave>=<valor> con una clave de: {', '.join(POR_CLAVE)}")
        pares[clave] = dato.strip().strip('"')
    return pares


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elegir", action="append", metavar="CLAVE=N", help="usar la candidata numero N de la hoja")
    ap.add_argument("--archivo", action="append", metavar="CLAVE=TITULO", help="usar un archivo concreto de Commons")
    ap.add_argument("--forzar", action="store_true", help="volver a elegir tambien las que ya tienen foto")
    ap.add_argument("--quitar", action="append", metavar="CLAVE", help="quitar la foto (vuelve a la ilustracion)")
    ap.add_argument("--uniformar", action="store_true", help="rehacer el encuadre de todas desde los originales")
    ap.add_argument("--solo", action="append", metavar="CLAVE", help="procesar solo estas claves (se puede repetir)")
    ap.add_argument("--auto", action="store_true",
                    help="elegir sola la primera candidata con una sola aeronave, entera, sin personas y con resolucion")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")  # consola de Windows: autores con caracteres fuera de su codificacion
    if args.uniformar:
        uniformar_todas()
        return 0
    elegir = {k: int(v) for k, v in _pares(args.elegir, "--elegir").items()}
    archivos = _pares(args.archivo, "--archivo")
    m = leer_manifiesto()

    for clave in args.quitar or []:
        if clave not in POR_CLAVE:
            raise SystemExit(f"--quitar {clave!r}: clave desconocida")
        e = m[POR_CLAVE[clave][0]].pop(clave, None)
        if e:
            (FOTOS / Path(e["foto"]).name).unlink(missing_ok=True)
            (ORIGINALES / Path(e["foto"]).name).unlink(missing_ok=True)
            print(f"  {clave}: foto quitada")

    candidatas, faltan = {}, []
    for seccion, clave, que, busquedas in UNIDADES:
        if args.quitar and clave in args.quitar:
            continue
        if args.solo and clave not in args.solo:
            continue
        actual = m[seccion].get(clave)
        tiene = actual and (FOTOS / Path(actual["foto"]).name).is_file()
        if tiene and not (args.forzar or clave in elegir or clave in archivos):
            print(f"  {clave}: ya tiene foto ({actual['obra']})")
            continue
        try:
            if clave in archivos:
                c = por_titulo(archivos[clave])
            elif args.auto and clave not in elegir:
                c, img, motivos = elegir_automatica(clave, busquedas)
                for mo in motivos:
                    print(f"    descartada {mo}")
                if c is None:
                    print(f"  {clave}: ninguna candidata paso el control de calidad")
                    faltan.append(clave)
                    continue
                foto = guardar_foto(clave, c, img)
                m[seccion][clave] = {"foto": foto, "obra": c["obra"], "autor": c["autor"], "licencia": c["licencia"],
                                     "url_licencia": c["url_licencia"], "pagina": c["pagina"]}
                print(f"  {clave}: {c['obra']} ({c['autor']}, {c['licencia']})")
                continue
            else:
                candidatas[clave] = buscar(busquedas)
                n = elegir.get(clave, 1)
                if not 1 <= n <= len(candidatas[clave]):
                    print(f"  {clave}: no hay candidata numero {n} ({len(candidatas[clave])} encontradas)")
                    faltan.append(clave)
                    continue
                c = candidatas[clave][n - 1]
            foto = guardar_foto(clave, c)
        except OSError as e:
            print(f"  {clave}: no se pudo descargar ({e})")
            faltan.append(clave)
            continue
        m[seccion][clave] = {"foto": foto, "obra": c["obra"], "autor": c["autor"], "licencia": c["licencia"],
                             "url_licencia": c["url_licencia"], "pagina": c["pagina"]}
        print(f"  {clave}: {c['obra']} ({c['autor']}, {c['licencia']})")

    escribir_manifiesto(m)
    escribir_creditos(m)
    hoja = escribir_hoja(candidatas, m)
    print(f"\nManifiesto: {MANIFIESTO}\nCandidatas: {hoja}")
    if faltan:
        print("Sin foto (siguen con su ilustracion o sin imagen): " + ", ".join(faltan))
    print("Reinicie el servidor para ver las fotos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
