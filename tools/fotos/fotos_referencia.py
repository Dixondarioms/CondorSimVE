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
API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia pide un User-Agent que identifique la herramienta.
AGENTE = "SIETE-simulador/1.0 (fotos de referencia; https://github.com/Dixondarioms/simulador-fenix)"
LADO_MAX = 720
CANDIDATAS = 8
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
    ("modelos", "merodeadora", "Municion merodeadora", ["Switchblade loitering munition", "IAI Harop"]),
    ("modelos", "ge_aereo", "Avion de guerra electronica", ["EC-130H Compass Call", "EA-18G Growler"]),
    ("modelos", "caza_embarcado", "Caza embarcado", ["F/A-18E Super Hornet aircraft carrier", "Rafale M carrier"]),
    ("modelos", "crucero", "Misil de crucero", ["Tomahawk cruise missile launch", "Kalibr cruise missile"]),
    ("clases", "fragata", "Fragata", ["Mariscal Sucre F-21", "Almirante Brion F-22", "fragata Venezuela Armada"]),
    ("clases", "patrullero", "Patrullero", ["Guaicamacuto patrullero", "Armada Bolivariana patrullero",
                                            "Guaiqueri PO-11"]),
    ("clases", "destructor", "Destructor", ["Arleigh Burke class destroyer underway"]),
    ("clases", "portaaviones", "Portaaviones", ["Nimitz class aircraft carrier underway", "Charles de Gaulle R91"]),
    ("clases", "submarino", "Submarino", ["Sabalo S-31 submarino", "submarino Armada Venezuela",
                                          "Type 209 submarine"]),
    ("clases", "buque_desembarco", "Buque de desembarco anfibio", ["Capana T-61", "Armada Bolivariana Capana",
                                                                   "landing ship tank"]),
]
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


_PROPS = {"prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1280",
          "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|ObjectName"}


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
        "autor": _texto((meta.get("Artist") or {}).get("value", "")) or "Desconocido",
        "licencia": licencia,
        "url_licencia": (meta.get("LicenseUrl") or {}).get("value", "") or "https://commons.wikimedia.org/wiki/Commons:Licensing",
        "pagina": info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(titulo)}",
        "miniatura": info.get("thumburl") or info["url"],
        "ancho": info.get("width", 0), "alto": info.get("height", 0),
    }


def buscar(busquedas: list[str]) -> list[dict]:
    """Candidatas con licencia libre, apaisadas y de buen tamano, en el orden de las busquedas."""
    vistas, candidatas = set(), []
    for consulta in busquedas:
        datos = _pedir({"action": "query", "generator": "search", "gsrsearch": f"{consulta} filetype:bitmap",
                        "gsrnamespace": "6", "gsrlimit": "20", **_PROPS})
        paginas = sorted((datos.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
        for p in paginas:
            c = _candidata(p)
            if c and c["titulo"] not in vistas and c["ancho"] >= 800 and c["ancho"] >= c["alto"]:
                vistas.add(c["titulo"])
                candidatas.append(c)
        if len(candidatas) >= CANDIDATAS:
            break
    return candidatas[:CANDIDATAS]


def por_titulo(titulo: str) -> dict:
    if not titulo.startswith("File:"):
        titulo = "File:" + titulo
    paginas = (_pedir({"action": "query", "titles": titulo, **_PROPS}).get("query") or {}).get("pages") or []
    c = _candidata(paginas[0]) if paginas else None
    if c is None:
        raise SystemExit(f"{titulo}: no existe en Commons, no es JPG/PNG o su licencia no es libre.")
    return c


def guardar_foto(clave: str, c: dict) -> str:
    img = Image.open(io.BytesIO(_bajar(c["miniatura"]))).convert("RGB")
    img.thumbnail((LADO_MAX, LADO_MAX), Image.LANCZOS)
    nombre = f"ref_{clave}.jpg"
    img.save(FOTOS / nombre, "JPEG", quality=85, optimize=True, progressive=True)
    return f"/static/fotos/{nombre}"


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
                        "Descargadas y reducidas a 720 px por `tools/fotos/fotos_referencia.py`, sin otra modificación. "
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
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")  # consola de Windows: autores con caracteres fuera de su codificacion
    elegir = {k: int(v) for k, v in _pares(args.elegir, "--elegir").items()}
    archivos = _pares(args.archivo, "--archivo")
    m = leer_manifiesto()

    for clave in args.quitar or []:
        if clave not in POR_CLAVE:
            raise SystemExit(f"--quitar {clave!r}: clave desconocida")
        e = m[POR_CLAVE[clave][0]].pop(clave, None)
        if e:
            (FOTOS / Path(e["foto"]).name).unlink(missing_ok=True)
            print(f"  {clave}: foto quitada")

    candidatas, faltan = {}, []
    for seccion, clave, que, busquedas in UNIDADES:
        if args.quitar and clave in args.quitar:
            continue
        actual = m[seccion].get(clave)
        tiene = actual and (FOTOS / Path(actual["foto"]).name).is_file()
        if tiene and not (args.forzar or clave in elegir or clave in archivos):
            print(f"  {clave}: ya tiene foto ({actual['obra']})")
            continue
        try:
            if clave in archivos:
                c = por_titulo(archivos[clave])
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
