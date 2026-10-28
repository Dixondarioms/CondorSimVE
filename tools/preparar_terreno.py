"""Descarga y prepara los datos de terreno de una REGION del mapa para uso 100% offline.

El simulador trabaja con varias regiones superpuestas, cada una con su propio zoom nativo (resolucion):
  venezuela   Venezuela y vecinos, zoom 9 (~300 m/pixel): el area de detalle para ejercicios tacticos.
  america     Todo el continente (Alaska - Tierra del Fuego), zoom 7 (~1 km/pixel): incluida en el repositorio.
  mundo       El planeta entero, zoom 6 (~2,4 km/pixel): OPCIONAL, la genera el usuario si la quiere
              (python tools/preparar_terreno.py --region mundo; unos 250 MB de descarga y ~270 MB de RAM
              en el servidor para la grilla del motor).
  (recuadro)  Cualquier rectangulo con --bbox/--zoom/--id, p. ej. un teatro concreto con mas detalle.
En el mapa se dibujan todas: la mas detallada encima de las demas. El motor consulta la clase de terreno en
la region mas detallada que cubra el punto (backend/app/terreno.py).

Se ejecuta UNA vez con internet por region. Genera:
  frontend/static/tiles/<region>/{z}/{x}/{y}.jpg   mapa de terreno (relieve + clases), del zoom nativo al minimo
  frontend/static/geo/<region>/*.geojson           limites, rios, lagos, poblaciones
  backend/data/terreno/<region>/clases.bin.z       grilla de clases para el motor
  backend/data/terreno/<region>/meta.json          id, nombre, bbox, zoom, origen y tamano de la grilla

Fuentes (datos abiertos):
  - Elevacion: AWS Terrain Tiles (Terrarium), s3.amazonaws.com/elevation-tiles-prod
    (SRTM/GMTED/ETOPO1 via Mapzen).
  - Vectores: Natural Earth (dominio publico), github.com/nvkelso/natural-earth-vector
  - Cobertura terrestre: ESA WorldCover 2021 (CC BY 4.0), esa-worldcover.s3.eu-central-1.amazonaws.com
Uso:
  python tools/preparar_terreno.py                         # region venezuela
  python tools/preparar_terreno.py --region america
  python tools/preparar_terreno.py --region mundo
  python tools/preparar_terreno.py --id caribe --nombre "Caribe" --bbox -90 8 -58 27 --zoom 8
  python tools/preparar_terreno.py --listar                 # regiones definidas y generadas
  python tools/preparar_terreno.py --piramides              # recompone los zooms bajos de todas las regiones
Requiere: pillow, numpy, rasterio, scipy (tools/requirements.txt). Las descargas quedan en tools/cache/ y el
proceso es reanudable (lo ya bajado no se vuelve a pedir).
"""

import argparse
import json
import math
import sys
import urllib.request
import zlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
TILES_OUT = RAIZ / "frontend" / "static" / "tiles"
GEO_OUT = RAIZ / "frontend" / "static" / "geo"
DATA_OUT = RAIZ / "backend" / "data" / "terreno"

TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"

# Clases de terreno (deben coincidir con backend/app/terreno.py)
AGUA, LLANO, BOSQUE, URBANO, MONTANA, PANTANO, RIO = 0, 1, 2, 3, 4, 5, 6

# ESA WorldCover 2021 (10 m, CC BY 4.0), tiles de 3x3 grados como COG con vistas reducidas.
WORLDCOVER = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
              "ESA_WorldCover_10m_2021_v200_{nombre}_Map.tif")
WC_PX = 36000  # pixeles por lado de cada tile de 3 grados
# Clases WorldCover: 10 arboles, 20 matorral, 30 pastizal, 40 cultivo, 50 urbano,
# 60 suelo desnudo, 70 nieve, 80 agua, 90 humedal herbaceo, 95 manglar, 100 musgo.

PIXELES_POR_BANDA = 24_000_000  # el mosaico se procesa por franjas horizontales para no agotar la memoria
COLOR_MAR = (104, 156, 198)


@dataclass(frozen=True)
class Region:
    id: str
    nombre: str
    bbox: tuple  # lon_min, lat_min, lon_max, lat_max
    z: int  # zoom nativo (resolucion de la grilla y de las teselas mas detalladas)
    z_min: int  # zoom mas bajo de la piramide de teselas
    escala_ne: str  # escala de Natural Earth para limites, rios y lagos: 10m, 50m o 110m
    pob_min: int  # poblacion minima para rotular una ciudad en el mapa

    @property
    def wc_factor(self) -> int:
        """Reduccion de WorldCover (10 m) para muestrearlo a una resolucion parecida a la del zoom nativo."""
        return min(1024, 32 * 2 ** max(0, 9 - self.z))

    def teselas(self):
        """Rango de teselas (xa, ya, xb, yb) del zoom nativo que cubre el recuadro."""
        xa, ya = tile_xy(self.bbox[0], self.bbox[3], self.z)
        xb, yb = tile_xy(self.bbox[2], self.bbox[1], self.z)
        return xa, ya, xb, yb

    def meta(self) -> dict:
        xa, ya, xb, yb = self.teselas()
        return {"id": self.id, "nombre": self.nombre, "bbox": list(self.bbox), "z": self.z, "z_min": self.z_min,
                "x0": xa, "y0": ya, "ancho": (xb - xa + 1) * 256, "alto": (yb - ya + 1) * 256,
                "metros_por_pixel": round(156543.03 * math.cos(math.radians((self.bbox[1] + self.bbox[3]) / 2)) / 2 ** self.z)}


REGIONES = {
    "venezuela": Region("venezuela", "Venezuela y vecinos", (-73.5, 0.5, -59.5, 12.5), 9, 5, "10m", 30000),
    "america": Region("america", "América", (-170.0, -56.0, -30.0, 72.0), 7, 3, "50m", 250000),
    "mundo": Region("mundo", "Mundo", (-180.0, -60.0, 180.0, 84.0), 6, 2, "110m", 1000000),  # hasta donde llega WorldCover
}
BBOX = REGIONES["venezuela"].bbox  # area de detalle (la usa preparar_satelite.py)


def px(lon, lat, x0, y0, z):
    n = 2 ** z * 256
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(max(-85.05, min(85.05, lat))))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x - x0 * 256, y - y0 * 256


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lr = math.radians(max(-85.05, min(85.05, lat)))
    y = int((1.0 - math.asinh(math.tan(lr)) / math.pi) / 2.0 * n)
    return max(0, min(n - 1, x)), max(0, min(n - 1, y))


def lat_de_fila(ya, h, z):
    n = 2 ** z * 256
    yy = (ya * 256 + np.arange(h) + 0.5) / n
    return np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * yy))))


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


def existe_url(url) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------------------- elevacion

def mosaico_elevacion(reg, cache, xa, xb, ya, yb):
    """Elevacion (m) de las teselas [xa..xb] x [ya..yb] del zoom nativo, como una matriz (alto, ancho)."""
    coords = [(x, y) for y in range(ya, yb + 1) for x in range(xa, xb + 1)]

    def bajar(c):
        x, y = c
        return c, descargar(TERRARIUM.format(z=reg.z, x=x, y=y), cache / "terrarium" / str(reg.z) / str(x) / f"{y}.png")

    with ThreadPoolExecutor(8) as ex:
        rutas = dict(ex.map(bajar, coords))

    w, h = (xb - xa + 1) * 256, (yb - ya + 1) * 256
    elev = np.zeros((h, w), dtype=np.float32)
    for (x, y), ruta in rutas.items():
        a = np.asarray(Image.open(ruta).convert("RGB"), dtype=np.float32)
        e = a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0
        elev[(y - ya) * 256:(y - ya + 1) * 256, (x - xa) * 256:(x - xa + 1) * 256] = e
    return elev


# ----------------------------------------------------------------------------- vectores

def poligono_mask(shape, puntos_px):
    img = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(img).polygon(puntos_px, fill=1)
    return np.asarray(img, dtype=bool)


def cargar_ne(nombre, cache):
    ruta = descargar(NE.format(nombre), cache / "ne" / f"{nombre}.geojson")
    return json.loads(ruta.read_text(encoding="utf-8"))["features"]


def geoms(feature):
    return _anillos(feature["geometry"])


def _anillos(geometry):
    if geometry is None:
        return []
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    return []


def en_bbox(pt, bbox):
    return bbox[0] <= pt[0] <= bbox[2] and bbox[1] <= pt[1] <= bbox[3]


def _recorta_semiplano(anillo, dentro, interseccion):
    """Sutherland-Hodgman contra un semiplano: `anillo` puede ser concavo, el semiplano es convexo."""
    if not anillo:
        return anillo
    salida = []
    prev = anillo[-1]
    prev_in = dentro(prev)
    for cur in anillo:
        cur_in = dentro(cur)
        if cur_in != prev_in:
            salida.append(interseccion(prev, cur))
        if cur_in:
            salida.append(cur)
        prev, prev_in = cur, cur_in
    return salida


def _recorta_anillo_a_bbox(anillo, bbox):
    """Recorta un anillo (poligono, posiblemente concavo) al rectangulo bbox."""
    x0, y0, x1, y1 = bbox

    def cruce_x(a, b, x):
        t = (x - a[0]) / (b[0] - a[0])
        return [x, a[1] + t * (b[1] - a[1])]

    def cruce_y(a, b, y):
        t = (y - a[1]) / (b[1] - a[1])
        return [a[0] + t * (b[0] - a[0]), y]

    anillo = _recorta_semiplano(anillo, lambda p: p[0] >= x0, lambda a, b: cruce_x(a, b, x0))
    anillo = _recorta_semiplano(anillo, lambda p: p[0] <= x1, lambda a, b: cruce_x(a, b, x1))
    anillo = _recorta_semiplano(anillo, lambda p: p[1] >= y0, lambda a, b: cruce_y(a, b, y0))
    anillo = _recorta_semiplano(anillo, lambda p: p[1] <= y1, lambda a, b: cruce_y(a, b, y1))
    return anillo


def recorta_geometria_a_bbox(geometry, bbox):
    """Poligono o multipoligono recortado al area del mapa, para no arrastrar en el GeoJSON el contorno entero
    de un pais vecino (p. ej. Brasil) cuando solo un borde entra en el mapa. None si no queda nada."""
    polis_out = []
    for poli in _anillos(geometry):
        anillos_out = [_recorta_anillo_a_bbox(anillo, bbox) for anillo in poli]
        if len(anillos_out[0]) >= 3:  # el anillo exterior sobrevivio
            polis_out.append([a for a in anillos_out if len(a) >= 3])
    if not polis_out:
        return None
    if geometry["type"] == "Polygon" and len(polis_out) == 1:
        return {"type": "Polygon", "coordinates": polis_out[0]}
    return {"type": "MultiPolygon", "coordinates": polis_out}


def redondear(obj, nd=3):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, list):
        return [redondear(o, nd) for o in obj]
    return obj


def regiones_generadas():
    """Metadatos de las regiones ya generadas (backend/data/terreno/*/meta.json), de mas a menos detallada."""
    metas = []
    for meta in sorted(DATA_OUT.glob("*/meta.json")):
        try:
            metas.append(json.loads(meta.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return sorted(metas, key=lambda m: -m["z"])


def vectores(reg, cache):
    """Fronteras, estados, rios, lagos y poblaciones del recuadro. Devuelve (poligonos de lagos, ciudades)."""
    salida = GEO_OUT / reg.id
    salida.mkdir(parents=True, exist_ok=True)
    esc = reg.escala_ne
    bbox = reg.bbox
    nd = 3 if reg.z >= 8 else 2
    # las ciudades que caen en una region mas detallada ya generada no se repiten (evita rotulos duplicados)
    finas = [tuple(m["bbox"]) for m in regiones_generadas() if m["z"] > reg.z and m["id"] != reg.id]

    def solapa(geometry):
        lons, lats = [], []
        for poly in _anillos(geometry):
            for anillo in poly:
                lons += [p[0] for p in anillo]
                lats += [p[1] for p in anillo]
        return bool(lons) and not (max(lons) < bbox[0] or min(lons) > bbox[2] or max(lats) < bbox[1] or min(lats) > bbox[3])

    nombres_es = {}
    fronteras = []
    for f in cargar_ne(f"ne_{esc}_admin_0_countries", cache):
        p = f["properties"]
        iso = p.get("ADM0_A3") or p.get("adm0_a3")
        nombres_es[iso] = p.get("NAME_ES") or p.get("name_es") or p.get("NAME") or p.get("name")
        if not solapa(f["geometry"]):
            continue
        recortada = recorta_geometria_a_bbox(f["geometry"], bbox)
        if recortada is None:
            continue
        fronteras.append({"type": "Feature", "properties": {"name": nombres_es[iso], "pais": iso},
                          "geometry": {"type": recortada["type"], "coordinates": redondear(recortada["coordinates"], nd)}})

    estados = []
    for f in cargar_ne(f"ne_{esc}_admin_1_states_provinces", cache):
        if not solapa(f["geometry"]):
            continue
        iso = f["properties"].get("adm0_a3")
        recortada = recorta_geometria_a_bbox(f["geometry"], bbox)
        if recortada is None:
            continue
        estados.append({"type": "Feature", "properties": {"name": f["properties"].get("name"), "pais": iso},
                        "geometry": {"type": recortada["type"], "coordinates": redondear(recortada["coordinates"], nd)}})

    rios = []
    for f in cargar_ne(f"ne_{esc}_rivers_lake_centerlines", cache):
        g = f["geometry"]
        if g is None:
            continue
        lineas = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        lineas = [ln for ln in lineas if any(en_bbox(p, bbox) for p in ln)]
        if lineas:
            rios.append({"type": "Feature", "properties": {"name": f["properties"].get("name")},
                         "geometry": {"type": "MultiLineString", "coordinates": redondear(lineas, nd)}})

    lagos = []
    lagos_poly = []
    for f in cargar_ne(f"ne_{esc}_lakes", cache):
        for poly in geoms(f):
            if any(en_bbox(p, bbox) for p in poly[0]):
                lagos.append({"type": "Feature", "properties": {"name": f["properties"].get("name")},
                              "geometry": {"type": "Polygon", "coordinates": redondear(poly, nd)}})
                lagos_poly.append(poly[0])

    lugares = []
    ciudades = []
    for f in cargar_ne("ne_10m_populated_places_simple", cache):
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        if not en_bbox((lon, lat), bbox):
            continue
        pop = p.get("pop_max") or 0
        iso = p.get("adm0_a3")
        if pop >= 50000:
            ciudades.append((lon, lat, pop))
        if any(en_bbox((lon, lat), fb) for fb in finas):
            continue
        if pop >= reg.pob_min or p.get("adm0cap"):
            props = {"name": p.get("name"), "pop": pop}
            if iso != "VEN":
                props["pais"] = nombres_es.get(iso) or p.get("adm0name") or ""
            lugares.append({"type": "Feature", "properties": props,
                            "geometry": {"type": "Point", "coordinates": [round(lon, 4), round(lat, 4)]}})

    def guardar(nombre, feats):
        (salida / nombre).write_text(json.dumps({"type": "FeatureCollection", "features": feats},
                                                separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(f"  {reg.id}/{nombre}: {len(feats)} elementos")

    guardar("fronteras.geojson", fronteras)
    guardar("estados.geojson", estados)
    guardar("rios.geojson", rios)
    guardar("lagos.geojson", lagos)
    guardar("lugares.geojson", lugares)
    return lagos_poly, ciudades


# ----------------------------------------------------------------------------- cobertura terrestre

class Cobertura:
    """Mosaico de WorldCover del recuadro, muestreado a la resolucion de la region (en memoria)."""

    def __init__(self, reg, cache):
        import rasterio
        from rasterio.enums import Resampling
        from scipy import ndimage

        bbox = reg.bbox
        self.lon0 = math.floor(bbox[0] / 3) * 3
        self.lon1 = math.ceil(bbox[2] / 3) * 3
        self.lat0 = max(-60, math.floor(bbox[1] / 3) * 3)  # WorldCover cubre 60S..84N
        self.lat1 = min(84, math.ceil(bbox[3] / 3) * 3)
        lado = WC_PX // reg.wc_factor
        self.ancho = (self.lon1 - self.lon0) // 3 * lado
        self.alto = (self.lat1 - self.lat0) // 3 * lado
        mosaico = np.zeros((self.alto, self.ancho), dtype=np.uint8)  # 0 = sin dato (mar abierto)

        celdas = [(lat, lon) for lat in range(self.lat0, self.lat1, 3) for lon in range(self.lon0, self.lon1, 3)]
        print(f"  WorldCover: {len(celdas)} celdas de 3x3 grados (factor {reg.wc_factor}, {lado} px por celda)")

        def nombre_de(lat, lon):
            return f"{'S' if lat < 0 else 'N'}{abs(lat):02d}{'W' if lon < 0 else 'E'}{abs(lon):03d}"

        def bajar(celda):
            lat, lon = celda
            nombre = nombre_de(lat, lon)
            ruta = cache / "worldcover" / f"{nombre}_f{reg.wc_factor}.npy"
            if ruta.exists():
                return celda, ruta
            ruta.parent.mkdir(parents=True, exist_ok=True)
            url = WORLDCOVER.format(nombre=nombre)
            a = np.zeros((lado, lado), dtype=np.uint8)  # celda inexistente: solo mar
            if existe_url(url):
                for intento in range(3):
                    try:
                        with rasterio.open(url) as ds:
                            a = ds.read(1, out_shape=(lado, lado), resampling=Resampling.mode)
                        break
                    except rasterio.errors.RasterioIOError:
                        if intento == 2:
                            raise
            np.save(ruta, a)
            return celda, ruta

        hechas = 0
        with ThreadPoolExecutor(6) as ex:
            for (lat, lon), ruta in ex.map(bajar, celdas):
                a = np.load(ruta)
                fila = (self.lat1 - (lat + 3)) // 3 * lado
                col = (lon - self.lon0) // 3 * lado
                mosaico[fila:fila + lado, col:col + lado] = a
                hechas += 1
                if hechas % 50 == 0 or hechas == len(celdas):
                    print(f"    {hechas}/{len(celdas)} celdas")

        # Agua "grande": se descartan rios y canales angostos (apertura morfologica de unos 5 pixeles) para que
        # las unidades terrestres puedan cruzarlos; lagos, embalses y tramos muy anchos de rio siguen siendo
        # obstaculos. Rios y cauces: agua permanente que no es un lago/embalse; transitables a pie (vadeo), los
        # vehiculos pesados solo los cruzan sobre un puente o vado tendido por ingenieros.
        agua_total = mosaico == 80
        self.agua = ndimage.binary_opening(agua_total, structure=np.ones((3, 3)), iterations=2)
        self.rios = agua_total & ~self.agua
        self.clases = mosaico

    def muestrear(self, reg, xa, ya, shape):
        """(clases_wc, agua_grande, rios) sobre la grilla del zoom nativo que empieza en la tesela (xa, ya)."""
        h, w = shape
        n = 2 ** reg.z * 256
        lon = (xa * 256 + np.arange(w) + 0.5) / n * 360.0 - 180.0
        lat = lat_de_fila(ya, h, reg.z)
        ix = np.clip(((lon - self.lon0) / (self.lon1 - self.lon0) * self.ancho).astype(int), 0, self.ancho - 1)
        iy = np.clip(((self.lat1 - lat) / (self.lat1 - self.lat0) * self.alto).astype(int), 0, self.alto - 1)
        fuera = (lat < self.lat0) | (lat > self.lat1)  # fuera de la cobertura de WorldCover: sin dato
        c, a, r = self.clases[iy][:, ix], self.agua[iy][:, ix], self.rios[iy][:, ix]
        if fuera.any():
            c, a, r = c.copy(), a.copy(), r.copy()
            c[fuera], a[fuera], r[fuera] = 0, False, False
        return c, a, r


# ----------------------------------------------------------------------------- clasificacion y color

def clasificar(reg, elev, xa, ya, lagos_poly, ciudades, cob, agua_cob, rio_cob):
    h, w = elev.shape
    lat_fila = lat_de_fila(ya, h, reg.z)
    pm = (156543.03392 * np.cos(np.radians(lat_fila)) / 2 ** reg.z)[:, None]  # m/pixel

    gy, gx = np.gradient(elev)
    dzdx = gx / pm
    dzdy = -gy / pm  # norte positivo
    pendiente = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    # con pixeles mas grandes la pendiente medida se suaviza: el umbral baja para seguir marcando las sierras
    pendiente_min = 9.0 * 0.75 ** max(0, 9 - reg.z)

    clases = np.full(elev.shape, LLANO, dtype=np.uint8)
    clases[cob == 10] = BOSQUE
    clases[(cob == 90) | (cob == 95)] = PANTANO
    clases[(elev >= 1500) | (pendiente >= pendiente_min)] = MONTANA
    clases[cob == 50] = URBANO
    clases[rio_cob & (elev > 0.5)] = RIO

    urb = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(urb)
    for lon, lat, pop in ciudades:
        x, y = px(lon, lat, xa, ya, reg.z)
        if not (-50 <= x <= w + 50 and -50 <= y <= h + 50):
            continue
        r_km = min(12.0, max(2.0, 6.0 * math.sqrt(pop / 1e6)))
        r_px = r_km * 1000.0 / (156543.03392 * math.cos(math.radians(lat)) / 2 ** reg.z)
        d.ellipse([x - r_px, y - r_px, x + r_px, y + r_px], fill=1)
    clases[np.asarray(urb, dtype=bool)] = URBANO

    agua = (elev <= 0.5) | agua_cob
    for poly in lagos_poly:
        pts = [px(lo, la, xa, ya, reg.z) for lo, la in poly]
        if all(p[0] < 0 or p[0] > w for p in pts) or all(p[1] < 0 or p[1] > h for p in pts):
            continue
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


# ----------------------------------------------------------------------------- teselas

def escribir_nativas(reg, rgb, xa, ya):
    """Teselas del zoom nativo de una franja del mosaico cuyo pixel (0, 0) es la esquina de la tesela (xa, ya)."""
    h, w = rgb.shape[:2]
    im = Image.fromarray(rgb)
    total = 0
    for j in range(h // 256):
        for i in range(w // 256):
            ruta = TILES_OUT / reg.id / str(reg.z) / str(xa + i) / f"{ya + j}.jpg"
            ruta.parent.mkdir(parents=True, exist_ok=True)
            im.crop((i * 256, j * 256, (i + 1) * 256, (j + 1) * 256)).save(ruta, "JPEG", quality=82, optimize=True)
            total += 1
    return total


def _fondo(z, x, y, gruesas):
    """Tesela (z, x, y) de la region menos detallada que la cubra (para rellenar los bordes de la piramide de
    una region fina con lo que se ve debajo), o mar si ninguna la tiene."""
    for m in gruesas:
        ruta = TILES_OUT / m["id"] / str(z) / str(x) / f"{y}.jpg"
        if ruta.is_file():
            return Image.open(ruta).convert("RGB")
        if z > m["z"]:  # la region gruesa no llega a este zoom: se amplia el trozo de su tesela nativa
            k = z - m["z"]
            ruta = TILES_OUT / m["id"] / str(m["z"]) / str(x >> k) / f"{y >> k}.jpg"
            if ruta.is_file():
                lado = 256 >> k
                cx, cy = (x % (1 << k)) * lado, (y % (1 << k)) * lado
                return Image.open(ruta).convert("RGB").crop((cx, cy, cx + lado, cy + lado)).resize((256, 256), Image.BILINEAR)
    return Image.new("RGB", (256, 256), COLOR_MAR)


def piramide(meta, gruesas):
    """Compone los zooms bajos (z-1 .. z_min) de una region a partir de sus teselas nativas. Donde una tesela
    baja se sale del recuadro, el hueco se rellena con la region menos detallada de abajo (o mar)."""
    carpeta = TILES_OUT / meta["id"]
    total = 0
    for z in range(meta["z"] - 1, meta["z_min"] - 1, -1):
        hijos = {(int(p.parent.name), int(p.stem)) for p in (carpeta / str(z + 1)).glob("*/*.jpg")}
        padres = {(x // 2, y // 2) for x, y in hijos}
        for x, y in sorted(padres):
            im = _fondo(z, x, y, gruesas)
            for dx in (0, 1):
                for dy in (0, 1):
                    hijo = carpeta / str(z + 1) / str(2 * x + dx) / f"{2 * y + dy}.jpg"
                    if hijo.is_file():
                        im.paste(Image.open(hijo).convert("RGB").resize((128, 128), Image.LANCZOS), (dx * 128, dy * 128))
            ruta = carpeta / str(z) / str(x) / f"{y}.jpg"
            ruta.parent.mkdir(parents=True, exist_ok=True)
            im.save(ruta, "JPEG", quality=82, optimize=True)
            total += 1
    print(f"  {meta['id']}: {total} teselas de zoom {meta['z_min']}..{meta['z'] - 1} recompuestas")


def _solapan(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def recomponer_piramides(solo_mas_finas_que=None):
    """Recompone la piramide de cada region generada (o solo de las mas detalladas que la dada, tras generarla),
    usando como fondo las regiones menos detalladas que la solapan."""
    metas = regiones_generadas()
    for m in metas:
        if solo_mas_finas_que is not None and not (m["z"] > solo_mas_finas_que["z"] and _solapan(m["bbox"], solo_mas_finas_que["bbox"])):
            continue
        gruesas = [g for g in metas if g["z"] < m["z"] and _solapan(g["bbox"], m["bbox"])]
        piramide(m, gruesas)


# ----------------------------------------------------------------------------- region completa

def generar_region(reg, cache):
    xa, ya, xb, yb = reg.teselas()
    ancho_t, alto_t = xb - xa + 1, yb - ya + 1
    print(f"Region '{reg.id}' ({reg.nombre}): zoom {reg.z}, {ancho_t}x{alto_t} teselas, "
          f"{ancho_t * 256}x{alto_t * 256} px, ~{reg.meta()['metros_por_pixel']} m/pixel")

    print("Vectores Natural Earth...")
    lagos_poly, ciudades = vectores(reg, cache)

    print("Cobertura terrestre ESA WorldCover...")
    cob = Cobertura(reg, cache)

    filas_por_banda = max(1, PIXELES_POR_BANDA // (ancho_t * 256 * 256))
    clases_total = np.zeros((alto_t * 256, ancho_t * 256), dtype=np.uint8)
    teselas = 0
    print(f"Elevacion, clasificacion y teselas en franjas de {filas_por_banda} filas de teselas...")
    for f0 in range(ya, yb + 1, filas_por_banda):
        f1 = min(yb, f0 + filas_por_banda - 1)
        e0, e1 = max(ya, f0 - 1), min(yb, f1 + 1)  # una fila extra arriba y abajo para el gradiente
        elev = mosaico_elevacion(reg, cache, xa, xb, e0, e1)
        c, a, r = cob.muestrear(reg, xa, e0, elev.shape)
        clases, dzdx, dzdy = clasificar(reg, elev, xa, e0, lagos_poly, ciudades, c, a, r)
        rgb = colorear(elev, clases, dzdx, dzdy)
        r0, r1 = (f0 - e0) * 256, (f1 - e0 + 1) * 256  # recorte de la franja util
        clases_total[(f0 - ya) * 256:(f1 - ya + 1) * 256] = clases[r0:r1]
        teselas += escribir_nativas(reg, rgb[r0:r1], xa, f0)
        print(f"  filas {f0}..{f1}: elevacion {elev.min():.0f}..{elev.max():.0f} m, {teselas} teselas nativas")
        del elev, clases, dzdx, dzdy, rgb

    for nombre, c in (("agua", AGUA), ("llano", LLANO), ("bosque", BOSQUE), ("pantano", PANTANO),
                      ("urbano", URBANO), ("montana", MONTANA), ("rio", RIO)):
        print(f"  {nombre}: {100.0 * (clases_total == c).mean():.1f}%")

    salida = DATA_OUT / reg.id
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "clases.bin.z").write_bytes(zlib.compress(clases_total.tobytes(), 9))
    (salida / "meta.json").write_text(json.dumps(reg.meta(), ensure_ascii=False), encoding="utf-8")
    del clases_total
    # grilla de alturas para la linea de vista de los sensores (lee las teselas de elevacion recien bajadas)
    from preparar_elevacion import generar as generar_elevacion
    r = generar_elevacion(salida)
    print(f"Alturas para la linea de vista: celdas de ~{r['metros_por_celda']} m, {r['kb']} KB")

    print("Piramide de zooms bajos...")
    meta = reg.meta()
    metas = regiones_generadas()
    piramide(meta, [g for g in metas if g["z"] < meta["z"] and _solapan(g["bbox"], meta["bbox"])])
    recomponer_piramides(solo_mas_finas_que=meta)
    print("Listo.")


def listar():
    generadas = {m["id"]: m for m in regiones_generadas()}
    print("Regiones definidas:")
    for reg in REGIONES.values():
        estado = "generada" if reg.id in generadas else "no generada"
        print(f"  {reg.id:<12} {reg.nombre:<24} zoom {reg.z} (min {reg.z_min})  bbox {reg.bbox}  [{estado}]")
    otras = [m for m in generadas.values() if m["id"] not in REGIONES]
    if otras:
        print("Otras regiones generadas:")
        for m in otras:
            print(f"  {m['id']:<12} {m['nombre']:<24} zoom {m['z']} (min {m['z_min']})  bbox {tuple(m['bbox'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="venezuela", choices=sorted(REGIONES), help="region predefinida (por defecto: venezuela)")
    ap.add_argument("--id", help="identificador de una region a medida (con --bbox); solo letras, numeros y guiones")
    ap.add_argument("--nombre", help="nombre visible de la region a medida")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LON_MIN", "LAT_MIN", "LON_MAX", "LAT_MAX"),
                    help="recuadro de la region a medida")
    ap.add_argument("--zoom", type=int, help="zoom nativo (resolucion): 9 = ~300 m, 8 = ~600 m, 7 = ~1,2 km, 6 = ~2,4 km")
    ap.add_argument("--cache", default=str(RAIZ / "tools" / "cache"))
    ap.add_argument("--solo-vectores", action="store_true",
                    help="regenerar solo fronteras/estados/rios/lagos/lugares (rapido, no toca las teselas ni la grilla)")
    ap.add_argument("--piramides", action="store_true", help="solo recomponer los zooms bajos de todas las regiones generadas")
    ap.add_argument("--listar", action="store_true", help="mostrar las regiones definidas y generadas")
    args = ap.parse_args()
    cache = Path(args.cache)

    if args.listar:
        return listar()
    if args.piramides:
        return recomponer_piramides()

    if args.id or args.bbox:
        if not (args.id and args.bbox):
            ap.error("una region a medida necesita --id y --bbox")
        if not args.id.replace("-", "").replace("_", "").isalnum() or args.id in REGIONES:
            ap.error("--id: use letras, numeros y guiones, distinto de las regiones predefinidas")
        z = args.zoom or 8
        reg = Region(args.id, args.nombre or args.id.capitalize(), tuple(args.bbox), z, max(2, z - 4),
                     "10m" if z >= 8 else "50m" if z >= 6 else "110m", 30000 if z >= 8 else 250000)
    else:
        reg = REGIONES[args.region]
        if args.zoom:
            reg = Region(reg.id, reg.nombre, reg.bbox, args.zoom, min(reg.z_min, args.zoom - 1), reg.escala_ne, reg.pob_min)
    if reg.z < 3 or reg.z > 11:
        ap.error("--zoom: entre 3 y 11")

    if args.solo_vectores:
        print("Vectores Natural Earth...")
        vectores(reg, cache)
        return
    generar_region(reg, cache)


if __name__ == "__main__":
    sys.exit(main())
