"""Carreteras reales para el motor y para el mapa: backend/data/terreno/<region>/vias.bin.z y
frontend/static/geo/<region>/carreteras.geojson.

Fuentes:
  - Venezuela y vecinos (`--fuente osm`, por defecto en esa region): OpenStreetMap por Overpass, autopistas,
    troncales, principales y secundarias (`highway=motorway|trunk|primary|secondary` y sus enlaces), por celdas
    de 2 x 2 grados con cache en tools/cache/osm_vias/ (reanudable). Si una celda no se puede bajar, se usa
    Natural Earth en esa celda.
  - El resto (`--fuente ne`): Natural Earth 10m roads (tools/cache/ne/ne_10m_roads.geojson, dominio publico),
    autopistas y carreteras principales y secundarias.

La grilla de vias tiene el mismo tamano e indice que la de clases de terreno (un byte por celda): 0 = sin via,
1 = secundaria, 2 = principal. Las lineas se dibujan con 2 celdas de ancho (1 en las regiones gruesas) para que el
motor, que recorre los movimientos a pasos de 1 km, no las salte. Donde una via cruza un rio o el agua hay un puente
(ver backend/app/engine/movimiento.py).

    python tools/preparar_vias.py                       # venezuela (OSM) y america (Natural Earth)
    python tools/preparar_vias.py --region venezuela --fuente ne
"""

import argparse
import json
import math
import sys
import time
import zlib
from pathlib import Path

from PIL import Image, ImageDraw

sys.setrecursionlimit(20000)  # simplificar() es recursivo y algunas vias de OSM tienen miles de nodos

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
import preparar_aerodromos as osm  # noqa: E402  (cliente de Overpass con espejos)

DATOS = RAIZ / "backend" / "data" / "terreno"
GEO = RAIZ / "frontend" / "static" / "geo"
CACHE = RAIZ / "tools" / "cache"
NE_ROADS = CACHE / "ne" / "ne_10m_roads.geojson"
CELDA = 2.0
PRINCIPALES = {"motorway", "trunk", "primary", "motorway_link", "trunk_link", "primary_link"}
SECUNDARIAS = {"secondary", "secondary_link"}
NE_NIVEL = {"Major Highway": 2, "Beltway": 2, "Bypass": 2, "Secondary Highway": 1, "Road": 1}
FUENTE_OSM = "© colaboradores de OpenStreetMap (ODbL 1.0)"
FUENTE_NE = "Natural Earth (dominio público)"


# ---------------------------------------------------------------- geometria
def px(lon, lat, z, x0, y0):
    n = 256 * 2 ** z
    x = (lon + 180) / 360 * n - x0 * 256
    s = math.sin(math.radians(max(-85.05, min(85.05, lat))))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n - y0 * 256
    return x, y


def simplificar(puntos, tol):
    """Douglas-Peucker (grados): reduce el tamano del GeoJSON sin cambiar la forma a la escala del mapa."""
    if len(puntos) < 3:
        return puntos
    (x1, y1), (x2, y2) = puntos[0], puntos[-1]
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy) or 1e-12
    i_max, d_max = 0, 0.0
    for i in range(1, len(puntos) - 1):
        x, y = puntos[i]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / largo
        if d > d_max:
            i_max, d_max = i, d
    if d_max <= tol:
        return [puntos[0], puntos[-1]]
    return simplificar(puntos[:i_max + 1], tol)[:-1] + simplificar(puntos[i_max:], tol)


# ---------------------------------------------------------------- fuentes
def lineas_ne(bbox):
    """(nivel, nombre, ref, [(lon, lat), ...]) de Natural Earth dentro del recuadro."""
    if not NE_ROADS.is_file():
        raise SystemExit(f"Falta {NE_ROADS}: ejecute antes tools/preparar_terreno.py (descarga Natural Earth)")
    oeste, sur, este, norte = bbox
    for f in json.loads(NE_ROADS.read_text(encoding="utf-8"))["features"]:
        nivel = NE_NIVEL.get(f["properties"].get("type"))
        if not nivel or not f.get("geometry"):
            continue
        g = f["geometry"]
        partes = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for parte in partes:
            if any(oeste <= x <= este and sur <= y <= norte for x, y in parte):
                yield nivel, f["properties"].get("name") or "", "", [tuple(p[:2]) for p in parte]


def consulta_osm(sur, oeste, norte, este):
    tipos = "|".join(sorted(PRINCIPALES | SECUNDARIAS))
    return (f'[out:json][timeout:180];way["highway"~"^({tipos})$"]({sur},{oeste},{norte},{este});'
            'out tags geom;')


def lineas_osm(bbox):
    """Por celdas de 2 x 2 grados, con cache; las celdas que no bajan se completan con Natural Earth."""
    oeste, sur, este, norte = bbox
    carpeta = CACHE / "osm_vias"
    carpeta.mkdir(parents=True, exist_ok=True)
    espejos = None
    faltan = []
    lat = sur
    while lat < norte:
        lon = oeste
        while lon < este:
            celda = (lat, lon, min(lat + CELDA, norte), min(lon + CELDA, este))
            archivo = carpeta / f"{celda[0]:+.1f}_{celda[1]:+.1f}.json"
            if not archivo.is_file():
                if espejos is None:
                    espejos = osm.espejos_disponibles()
                print(f"  OSM {archivo.stem} ...", flush=True)
                datos = osm.consultar_overpass(consulta_osm(*celda), espejos) if espejos else None
                if datos is None:
                    faltan.append(celda)
                    lon += CELDA
                    continue
                tmp = archivo.with_suffix(".tmp")
                tmp.write_text(json.dumps(datos), encoding="utf-8")
                tmp.replace(archivo)
                time.sleep(osm.PAUSA_S)
            for e in json.loads(archivo.read_text(encoding="utf-8")).get("elements", []):
                t = e.get("tags", {})
                h = t.get("highway", "")
                nivel = 2 if h in PRINCIPALES else 1 if h in SECUNDARIAS else 0
                if nivel and e.get("geometry"):
                    yield nivel, t.get("name", ""), t.get("ref", ""), [(g["lon"], g["lat"]) for g in e["geometry"]]
            lon += CELDA
        lat += CELDA
    for celda in faltan:
        print(f"  (Natural Earth en la celda {celda[0]:+.1f}, {celda[1]:+.1f}: OSM no respondio)", flush=True)
        s, o, n, e_ = celda
        yield from lineas_ne((o, s, e_, n))


# ---------------------------------------------------------------- generacion
def generar(region: str, fuente: str) -> None:
    carpeta = DATOS / region
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    bbox = tuple(meta["bbox"])
    z, x0, y0, ancho, alto = meta["z"], meta["x0"], meta["y0"], meta["ancho"], meta["alto"]
    grueso = z <= 7
    print(f"Region {region}: {fuente.upper()}, grilla {ancho} x {alto} (zoom {z})", flush=True)
    lineas = list(lineas_osm(bbox) if fuente == "osm" else lineas_ne(bbox))
    print(f"  {len(lineas)} tramos", flush=True)

    img = Image.new("L", (ancho, alto), 0)
    d = ImageDraw.Draw(img)
    for nivel_dibujo in (1, 2):  # las principales encima
        for nivel, _, _, pts in lineas:
            if nivel == nivel_dibujo and len(pts) >= 2:
                d.line([px(x, y, z, x0, y0) for x, y in pts], fill=nivel, width=1 if grueso else 2)
    (carpeta / "vias.bin.z").write_bytes(zlib.compress(img.tobytes(), 9))
    meta["vias_fuente"] = FUENTE_OSM if fuente == "osm" else FUENTE_NE
    (carpeta / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    tol, nd = (0.004, 3) if grueso else (0.0008, 4)
    oeste, sur, este, norte = bbox
    features = []
    for nivel, nombre, ref, pts in lineas:
        pts = [p for p in simplificar(pts, tol)]
        if len(pts) < 2 or not any(oeste <= x <= este and sur <= y <= norte for x, y in pts):
            continue
        features.append({"type": "Feature", "properties": {"nivel": nivel, "nombre": nombre, "ref": ref},
                         "geometry": {"type": "LineString", "coordinates": [[round(x, nd), round(y, nd)] for x, y in pts]}})
    destino = GEO / region / "carreteras.geojson"
    destino.write_text(json.dumps({"type": "FeatureCollection", "fuente": meta["vias_fuente"], "features": features},
                                  separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    celdas = sum(img.histogram()[1:])
    print(f"  vias.bin.z: {celdas} celdas con via; {destino.name}: {len(features)} tramos, "
          f"{destino.stat().st_size // 1024} KB", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--region", action="append", help="region (por defecto: todas las generadas)")
    ap.add_argument("--fuente", choices=("osm", "ne"), help="por defecto: osm en venezuela, ne en el resto")
    args = ap.parse_args()
    regiones = args.region or sorted(p.name for p in DATOS.iterdir() if (p / "meta.json").is_file())
    for r in regiones:
        generar(r, args.fuente or ("osm" if r == "venezuela" else "ne"))


if __name__ == "__main__":
    main()
