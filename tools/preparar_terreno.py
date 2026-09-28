"""Descarga y prepara los datos de terreno de Venezuela para uso 100% offline.

Se ejecuta UNA vez con internet. Genera:
  frontend/static/tiles/{z}/{x}/{y}.jpg   mapa de terreno (relieve + clases)
  frontend/static/geo/*.geojson           limites, rios, lagos, poblaciones
  backend/data/terreno/clases.bin.z       grilla de clases para el motor
  backend/data/terreno/meta.json

Fuentes (datos abiertos):
  - Elevacion: AWS Terrain Tiles (Terrarium), s3.amazonaws.com/elevation-tiles-prod
    (SRTM/GMTED/ETOPO1 via Mapzen).
  - Vectores: Natural Earth (dominio publico), github.com/nvkelso/natural-earth-vector
  - Cobertura terrestre: ESA WorldCover 2021 (CC BY 4.0), esa-worldcover.s3.eu-central-1.amazonaws.com
Uso:  python tools/preparar_terreno.py [--cache DIR]
Requiere: pillow, numpy, rasterio, scipy (tools/requirements.txt).
"""

import argparse
import json
import math
import sys
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
TILES_OUT = RAIZ / "frontend" / "static" / "tiles"
GEO_OUT = RAIZ / "frontend" / "static" / "geo"
DATA_OUT = RAIZ / "backend" / "data" / "terreno"

Z = 9
BBOX = (-73.5, 0.5, -59.5, 12.5)  # lon_min, lat_min, lon_max, lat_max
TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"

# Clases de terreno (deben coincidir con backend/app/terreno.py)
AGUA, LLANO, BOSQUE, URBANO, MONTANA, PANTANO, RIO = 0, 1, 2, 3, 4, 5, 6

# ESA WorldCover 2021 (10 m, CC BY 4.0), tiles de 3x3 grados como COG con vistas reducidas.
WORLDCOVER = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
              "ESA_WorldCover_10m_2021_v200_{nombre}_Map.tif")
WC_FACTOR = 32          # 10 m * 32 = 320 m/pixel, similar al z9 (~300 m)
WC_TILE = 36000 // WC_FACTOR
# Clases WorldCover: 10 arboles, 20 matorral, 30 pastizal, 40 cultivo, 50 urbano,
# 60 suelo desnudo, 70 nieve, 80 agua, 90 humedal herbaceo, 95 manglar, 100 musgo.


def px(lon, lat, x0, y0):
    n = 2 ** Z * 256
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x - x0 * 256, y - y0 * 256


def tile_xy(lon, lat):
    n = 2 ** Z
    x = int((lon + 180.0) / 360.0 * n)
    lr = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lr)) / math.pi) / 2.0 * n)
    return x, y


def descargar(url, destino, reintentos=4):
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    for i in range(reintentos):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                datos = r.read()
            destino.write_bytes(datos)
            return destino
        except Exception as e:  # noqa: BLE001
            if i == reintentos - 1:
                raise RuntimeError(f"No se pudo descargar {url}: {e}") from e
    return destino


def construir_mosaico(cache):
    xa, ya = tile_xy(BBOX[0], BBOX[3])
    xb, yb = tile_xy(BBOX[2], BBOX[1])
    coords = [(x, y) for y in range(ya, yb + 1) for x in range(xa, xb + 1)]
    print(f"Descargando {len(coords)} tiles de elevacion z{Z}...")

    def bajar(c):
        x, y = c
        return c, descargar(TERRARIUM.format(z=Z, x=x, y=y), cache / "terrarium" / str(Z) / str(x) / f"{y}.png")

    with ThreadPoolExecutor(8) as ex:
        rutas = dict(ex.map(bajar, coords))

    w, h = (xb - xa + 1) * 256, (yb - ya + 1) * 256
    elev = np.zeros((h, w), dtype=np.float32)
    for (x, y), ruta in rutas.items():
        a = np.asarray(Image.open(ruta).convert("RGB"), dtype=np.float32)
        e = a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0
        elev[(y - ya) * 256:(y - ya + 1) * 256, (x - xa) * 256:(x - xa + 1) * 256] = e
    return elev, xa, ya


def poligono_mask(shape, puntos_px):
    img = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(img).polygon(puntos_px, fill=1)
    return np.asarray(img, dtype=bool)


def cargar_ne(nombre, cache):
    ruta = descargar(NE.format(nombre), cache / "ne" / f"{nombre}.geojson")
    return json.loads(ruta.read_text(encoding="utf-8"))["features"]


def geoms(feature):
    g = feature["geometry"]
    if g is None:
        return []
    if g["type"] == "Polygon":
        return [g["coordinates"]]
    if g["type"] == "MultiPolygon":
        return g["coordinates"]
    return []


def en_bbox(pt):
    return BBOX[0] <= pt[0] <= BBOX[2] and BBOX[1] <= pt[1] <= BBOX[3]


def redondear(obj, nd=3):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, list):
        return [redondear(o, nd) for o in obj]
    return obj


def vectores(cache):
    GEO_OUT.mkdir(parents=True, exist_ok=True)

    paises = cargar_ne("ne_10m_admin_0_countries", cache)
    ven = [f for f in paises if f["properties"].get("ADM0_A3") == "VEN"]
    fronteras = [{"type": "Feature", "properties": {"name": "Venezuela"},
                  "geometry": {"type": f["geometry"]["type"], "coordinates": redondear(f["geometry"]["coordinates"])}}
                 for f in ven]

    estados = [f for f in cargar_ne("ne_10m_admin_1_states_provinces", cache)
               if f["properties"].get("adm0_a3") == "VEN"]
    estados = [{"type": "Feature", "properties": {"name": f["properties"].get("name")},
                "geometry": {"type": f["geometry"]["type"], "coordinates": redondear(f["geometry"]["coordinates"])}}
               for f in estados]

    rios = []
    for f in cargar_ne("ne_10m_rivers_lake_centerlines", cache):
        g = f["geometry"]
        if g is None:
            continue
        lineas = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        lineas = [ln for ln in lineas if any(en_bbox(p) for p in ln)]
        if lineas:
            rios.append({"type": "Feature", "properties": {"name": f["properties"].get("name")},
                         "geometry": {"type": "MultiLineString", "coordinates": redondear(lineas)}})

    lagos = []
    lagos_poly = []
    for f in cargar_ne("ne_10m_lakes", cache):
        for poly in geoms(f):
            if any(en_bbox(p) for p in poly[0]):
                lagos.append({"type": "Feature", "properties": {"name": f["properties"].get("name")},
                              "geometry": {"type": "Polygon", "coordinates": redondear(poly)}})
                lagos_poly.append(poly[0])

    lugares = []
    ciudades = []
    for f in cargar_ne("ne_10m_populated_places_simple", cache):
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        if not en_bbox((lon, lat)):
            continue
        pop = p.get("pop_max") or 0
        if pop >= 30000 or p.get("adm0cap"):
            lugares.append({"type": "Feature", "properties": {"name": p.get("name"), "pop": pop},
                            "geometry": {"type": "Point", "coordinates": [round(lon, 4), round(lat, 4)]}})
        if pop >= 50000:
            ciudades.append((lon, lat, pop))

    def guardar(nombre, feats):
        (GEO_OUT / nombre).write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                 separators=(",", ":")), encoding="utf-8")
        print(f"  {nombre}: {len(feats)} elementos")

    guardar("fronteras.geojson", fronteras)
    guardar("estados.geojson", estados)
    guardar("rios.geojson", rios)
    guardar("lagos.geojson", lagos)
    guardar("lugares.geojson", lugares)
    return lagos_poly, ciudades


def lat_de_fila(ya, h):
    n = 2 ** Z * 256
    yy = (ya * 256 + np.arange(h) + 0.5) / n
    return np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * yy))))


def cobertura(cache, xa, ya, shape):
    """Muestrea WorldCover sobre la grilla z9. Devuelve (clases_wc, agua_grande, rios)."""
    import rasterio
    from rasterio.enums import Resampling
    from scipy import ndimage

    lon0 = math.floor(BBOX[0] / 3) * 3
    lon1 = math.ceil(BBOX[2] / 3) * 3
    lat0 = math.floor(BBOX[1] / 3) * 3
    lat1 = math.ceil(BBOX[3] / 3) * 3
    ancho = (lon1 - lon0) // 3 * WC_TILE
    alto = (lat1 - lat0) // 3 * WC_TILE
    mosaico = np.zeros((alto, ancho), dtype=np.uint8)  # 0 = sin dato (mar abierto)

    print(f"  WorldCover: {((lon1 - lon0) // 3) * ((lat1 - lat0) // 3)} tiles de 3x3 grados")
    for lat in range(lat0, lat1, 3):
        for lon in range(lon0, lon1, 3):
            nombre = f"N{lat:02d}{'W' if lon < 0 else 'E'}{abs(lon):03d}"
            ruta = cache / "worldcover" / f"{nombre}.npy"
            if not ruta.exists():
                ruta.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with rasterio.open(WORLDCOVER.format(nombre=nombre)) as ds:
                        a = ds.read(1, out_shape=(WC_TILE, WC_TILE), resampling=Resampling.mode)
                except rasterio.errors.RasterioIOError:
                    a = np.zeros((WC_TILE, WC_TILE), dtype=np.uint8)  # tile inexistente: solo mar
                np.save(ruta, a)
            a = np.load(ruta)
            fila = (lat1 - (lat + 3)) // 3 * WC_TILE
            col = (lon - lon0) // 3 * WC_TILE
            mosaico[fila:fila + WC_TILE, col:col + WC_TILE] = a
            print(f"    {nombre}: {'ok' if a.any() else 'sin datos'}")

    # Agua "grande": se descartan rios y canales angostos (apertura morfologica de
    # ~1.5 km) para que las unidades terrestres puedan cruzarlos; lagos, embalses
    # y tramos muy anchos de rio siguen siendo obstaculos.
    agua_total = mosaico == 80
    agua_mosaico = ndimage.binary_opening(agua_total, structure=np.ones((3, 3)), iterations=2)
    # Rios y cauces: agua permanente que no es un lago/embalse. Son transitables a pie (vadeo) pero
    # los vehiculos pesados solo los cruzan sobre un puente o vado tendido por ingenieros.
    rios_mosaico = agua_total & ~agua_mosaico

    h, w = shape
    n = 2 ** Z * 256
    lon = (xa * 256 + np.arange(w) + 0.5) / n * 360.0 - 180.0
    lat = lat_de_fila(ya, h)
    ix = np.clip(((lon - lon0) / (lon1 - lon0) * ancho).astype(int), 0, ancho - 1)
    iy = np.clip(((lat1 - lat) / (lat1 - lat0) * alto).astype(int), 0, alto - 1)
    return mosaico[iy][:, ix], agua_mosaico[iy][:, ix], rios_mosaico[iy][:, ix]


def clasificar(elev, xa, ya, lagos_poly, ciudades, cob, agua_cob, rio_cob):
    h, w = elev.shape
    lat_fila = np.empty(h, dtype=np.float64)
    n = 2 ** Z * 256
    for i in range(h):
        yy = (ya * 256 + i + 0.5) / n
        lat_fila[i] = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy))))
    pm = (156543.03392 * np.cos(np.radians(lat_fila)) / 2 ** Z)[:, None]  # m/pixel

    gy, gx = np.gradient(elev)
    dzdx = gx / pm
    dzdy = -gy / pm  # norte positivo
    pendiente = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))

    clases = np.full(elev.shape, LLANO, dtype=np.uint8)
    clases[cob == 10] = BOSQUE
    clases[(cob == 90) | (cob == 95)] = PANTANO
    clases[(elev >= 1500) | (pendiente >= 9.0)] = MONTANA
    clases[cob == 50] = URBANO
    clases[rio_cob & (elev > 0.5)] = RIO

    urb = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(urb)
    for lon, lat, pop in ciudades:
        x, y = px(lon, lat, xa, ya)
        r_km = min(12.0, max(2.0, 6.0 * math.sqrt(pop / 1e6)))
        r_px = r_km * 1000.0 / (156543.03392 * math.cos(math.radians(lat)) / 2 ** Z)
        d.ellipse([x - r_px, y - r_px, x + r_px, y + r_px], fill=1)
    clases[np.asarray(urb, dtype=bool)] = URBANO

    agua = (elev <= 0.5) | agua_cob
    for poly in lagos_poly:
        pts = [px(lo, la, xa, ya) for lo, la in poly]
        agua |= poligono_mask(elev.shape, pts)
    clases[agua] = AGUA

    return clases, dzdx, dzdy


def colorear(elev, clases, dzdx, dzdy):
    z = 2.5
    nx, ny, nz = -z * dzdx, -z * dzdy, np.ones_like(dzdx)
    norma = np.sqrt(nx * nx + ny * ny + nz * nz)
    az, alt = math.radians(315), math.radians(45)
    lx, ly, lz = math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt)
    sombra = np.clip((nx * lx + ny * ly + nz * lz) / norma, 0, 1)
    factor = (0.45 + 0.75 * sombra)[..., None]

    t = np.clip(elev / 2500.0, 0, 1)[..., None]
    base = np.zeros(elev.shape + (3,), dtype=np.float32)
    llano = np.array([196, 205, 140], np.float32)
    bosque = np.array([88, 132, 84], np.float32)
    urbano = np.array([158, 154, 150], np.float32)
    pantano = np.array([124, 156, 138], np.float32)
    rio = np.array([96, 150, 205], np.float32)
    monta_bajo = np.array([170, 140, 100], np.float32)
    monta_alto = np.array([235, 228, 220], np.float32)
    base[:] = llano
    base = np.where((clases == BOSQUE)[..., None], bosque, base)
    base = np.where((clases == PANTANO)[..., None], pantano, base)
    base = np.where((clases == RIO)[..., None], rio, base)
    base = np.where((clases == MONTANA)[..., None], monta_bajo * (1 - t) + monta_alto * t, base)
    base = np.where((clases == URBANO)[..., None], urbano, base)

    rgb = base * factor
    profundidad = np.clip(-elev / 3000.0, 0, 1)[..., None]
    mar = np.array([120, 170, 205], np.float32) * (1 - profundidad) + np.array([40, 80, 130], np.float32) * profundidad
    rgb = np.where((clases == AGUA)[..., None], mar * (0.85 + 0.15 * sombra[..., None]), rgb)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def cortar_tiles(rgb, xa, ya):
    h, w = rgb.shape[:2]
    total = 0
    for z in range(Z, 4, -1):
        k = Z - z
        f = 2 ** k
        # Se rellena el mosaico (replicando bordes) hasta alinearlo con la
        # grilla global de tiles de este zoom; si no, los tiles quedarian
        # desplazados cuando el origen no es multiplo de 2**k.
        px0, py0 = (xa % f) * 256, (ya % f) * 256
        ancho = -(-(px0 + w) // (256 * f)) * 256 * f
        alto = -(-(py0 + h) // (256 * f)) * 256 * f
        relleno = np.pad(rgb, ((py0, alto - h - py0), (px0, ancho - w - px0), (0, 0)), mode="edge")
        im = Image.fromarray(relleno)
        if k:
            im = im.resize((ancho >> k, alto >> k), Image.LANCZOS)
        tx0, ty0 = xa >> k, ya >> k
        nx, ny = im.size[0] // 256, im.size[1] // 256
        for j in range(ny):
            for i in range(nx):
                t = im.crop((i * 256, j * 256, (i + 1) * 256, (j + 1) * 256))
                ruta = TILES_OUT / str(z) / str(tx0 + i) / f"{ty0 + j}.jpg"
                ruta.parent.mkdir(parents=True, exist_ok=True)
                t.save(ruta, "JPEG", quality=82, optimize=True)
                total += 1
    print(f"  {total} tiles escritos")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(RAIZ / "tools" / "cache"))
    args = ap.parse_args()
    cache = Path(args.cache)

    elev, xa, ya = construir_mosaico(cache)
    print(f"Mosaico {elev.shape[1]}x{elev.shape[0]} px, elevacion {elev.min():.0f}..{elev.max():.0f} m")

    print("Vectores Natural Earth...")
    lagos_poly, ciudades = vectores(cache)

    print("Cobertura terrestre ESA WorldCover...")
    cob, agua_cob, rio_cob = cobertura(cache, xa, ya, elev.shape)

    print("Clasificando terreno...")
    clases, dzdx, dzdy = clasificar(elev, xa, ya, lagos_poly, ciudades, cob, agua_cob, rio_cob)
    for nombre, c in (("agua", AGUA), ("llano", LLANO), ("bosque", BOSQUE), ("pantano", PANTANO),
                      ("urbano", URBANO), ("montana", MONTANA), ("rio", RIO)):
        print(f"  {nombre}: {100.0 * (clases == c).mean():.1f}%")

    DATA_OUT.mkdir(parents=True, exist_ok=True)
    (DATA_OUT / "clases.bin.z").write_bytes(zlib.compress(clases.tobytes(), 9))
    (DATA_OUT / "meta.json").write_text(json.dumps(
        {"z": Z, "x0": xa, "y0": ya, "ancho": int(clases.shape[1]), "alto": int(clases.shape[0])}), encoding="utf-8")

    print("Renderizando tiles...")
    cortar_tiles(colorear(elev, clases, dzdx, dzdy), xa, ya)
    print("Listo.")


if __name__ == "__main__":
    sys.exit(main())
