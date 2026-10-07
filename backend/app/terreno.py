"""Consulta de clases de terreno a partir de las grillas generadas por tools/preparar_terreno.py
(elevacion SRTM + cobertura WorldCover + ciudades), una por region del mapa.

Hay varias regiones superpuestas con distinta resolucion (Venezuela a ~300 m, America a ~1 km, el mundo si el
usuario lo genero, recuadros a medida): en cada punto se consulta la mas detallada que lo cubra. Cada region vive
en backend/data/terreno/<id>/ (meta.json + clases.bin.z)."""

import json
import math
import zlib
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "terreno"
# foto satelital por region (tools/preparar_satelite.py): tiles_sat/<id>/{z}/{x}/{y}.jpg
TILES_SAT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "static" / "tiles_sat"

AGUA, LLANO, BOSQUE, URBANO, MONTANA, PANTANO, RIO = 0, 1, 2, 3, 4, 5, 6
NOMBRES = {
    AGUA: "agua", LLANO: "llano", BOSQUE: "bosque", URBANO: "urbano", MONTANA: "montana", PANTANO: "pantano",
    RIO: "rio",
}

# Factor sobre la fuerza defensiva de una unidad terrestre segun el terreno.
FACTOR_DEFENSA = {
    "agua": 1.0, "llano": 1.0, "bosque": 1.3, "urbano": 1.5, "montana": 1.6, "pantano": 1.0, "rio": 1.0,
}
# Fraccion de velocidad de una unidad terrestre segun el terreno (0 = intransitable). En "rio" es el
# vadeo a pie; los vehiculos pesados no lo cruzan sin puente o vado (ver engine/movimiento.py).
FACTOR_MOVIMIENTO = {
    "agua": 0.0, "llano": 1.0, "bosque": 0.6, "urbano": 0.7, "montana": 0.4, "pantano": 0.5, "rio": 0.5,
}
# Multiplicador del radio de deteccion enemigo sobre un objetivo terrestre.
OCULTAMIENTO = {
    "agua": 1.0, "llano": 1.0, "bosque": 0.6, "urbano": 0.7, "montana": 0.75, "pantano": 0.9, "rio": 1.0,
}


class Grilla:
    """Grilla de clases de una region: teselas [x0, x0+ancho/256) x [y0, y0+alto/256) del zoom z."""

    def __init__(self, meta: dict, clases: bytes, elevacion: memoryview | None = None):
        self.meta = meta
        self.clases = clases
        # alturas (m, enteros de 16 bits) a 1/elev_paso de la resolucion de las clases (tools/preparar_elevacion.py)
        self.elevacion = elevacion

    def altura(self, lat: float, lon: float) -> float | None:
        """Metros sobre el nivel del mar del punto (lo mas alto de su celda), o None si la region no tiene alturas
        o el punto cae fuera."""
        if self.elevacion is None:
            return None
        lat = max(-85.0, min(85.0, lat))
        n = 2 ** self.z * 256
        x = (lon + 180.0) / 360.0 * n - self.meta["x0"] * 256
        s = math.sin(math.radians(lat))
        y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n - self.meta["y0"] * 256
        paso = self.meta.get("elev_paso", 1)
        xi, yi = int(x) // paso, int(y) // paso
        ancho = self.meta.get("elev_ancho", self.meta["ancho"] // paso)
        if x < 0 or y < 0 or not (0 <= xi < ancho and 0 <= yi < self.meta.get("elev_alto", self.meta["alto"] // paso)):
            return None
        return float(self.elevacion[yi * ancho + xi])

    @property
    def id(self) -> str:
        return self.meta.get("id", "venezuela")

    @property
    def z(self) -> int:
        return int(self.meta["z"])

    def indice(self, lat: float, lon: float) -> int | None:
        """Posicion en `clases` de la celda que contiene el punto, o None si cae fuera de la region."""
        lat = max(-85.0, min(85.0, lat))
        n = 2 ** self.z * 256
        x = (lon + 180.0) / 360.0 * n - self.meta["x0"] * 256
        s = math.sin(math.radians(lat))
        y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n - self.meta["y0"] * 256
        xi, yi = int(x), int(y)
        if not (0 <= xi < self.meta["ancho"] and 0 <= yi < self.meta["alto"]):
            return None
        return yi * self.meta["ancho"] + xi

    def resumen(self) -> dict:
        """Lo que necesita el frontend para dibujar la region (GET /api/terreno/mapas)."""
        m = self.meta
        return {"id": self.id, "nombre": m.get("nombre", self.id), "bbox": m.get("bbox"), "z": self.z,
                "z_min": int(m.get("z_min", max(2, self.z - 4))), "metros_por_pixel": m.get("metros_por_pixel"),
                "satelite": satelite_de(self.id)}


def satelite_de(id_: str) -> dict | None:
    """Zooms {z_min, z_max} de la foto satelital descargada para la region, o None si no tiene."""
    carpeta = TILES_SAT_DIR / id_
    if not carpeta.is_dir():
        return None
    zooms = sorted(int(p.name) for p in carpeta.iterdir() if p.is_dir() and p.name.isdigit() and any(p.iterdir()))
    return {"z_min": zooms[0], "z_max": zooms[-1]} if zooms else None


class Terreno:
    def __init__(self, meta: dict | None = None, clases: bytes | None = None, grillas: list[Grilla] | None = None):
        # (meta, clases) se conserva por compatibilidad: una sola region
        self.grillas = list(grillas or [])
        if meta is not None and clases is not None:
            self.grillas.append(Grilla(meta, clases))
        self.grillas.sort(key=lambda g: -g.z)  # de mas a menos detallada

    @property
    def disponible(self) -> bool:
        return bool(self.grillas)

    @property
    def meta(self) -> dict | None:
        return self.grillas[0].meta if self.grillas else None

    def regiones(self) -> list[dict]:
        return [g.resumen() for g in self.grillas]

    def clase(self, lat: float, lon: float) -> str:
        """Nombre de la clase de terreno en (lat, lon), segun la region mas detallada que cubra el punto.
        Fuera de toda grilla: llano."""
        for g in self.grillas:
            i = g.indice(lat, lon)
            if i is not None:
                return NOMBRES.get(g.clases[i], "llano")
        return "llano"

    @property
    def tiene_elevacion(self) -> bool:
        """Si hay alturas cargadas: sin ellas el motor no calcula linea de vista (todo se ve, como antes)."""
        return any(g.elevacion is not None for g in self.grillas)

    def altura(self, lat: float, lon: float) -> float | None:
        """Metros sobre el nivel del mar en (lat, lon) segun la region mas detallada con alturas que lo cubra."""
        for g in self.grillas:
            h = g.altura(lat, lon)
            if h is not None:
                return h
        return None

    def hay_rio_cerca(self, lat: float, lon: float, radio_km: float = 1.0) -> bool:
        """True si hay una celda de rio a <= radio_km (se muestrea el punto y 8 direcciones)."""
        if self.clase(lat, lon) == "rio":
            return True
        d_lat = radio_km / 111.32
        d_lon = radio_km / (111.32 * max(0.05, math.cos(math.radians(lat))))
        for i in range(8):
            a = i * math.pi / 4
            if self.clase(lat + d_lat * math.sin(a), lon + d_lon * math.cos(a)) == "rio":
                return True
        return False


def _cargar_grilla(carpeta: Path) -> Grilla | None:
    meta_path, datos_path = carpeta / "meta.json", carpeta / "clases.bin.z"
    if not (meta_path.exists() and datos_path.exists()):
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.setdefault("id", carpeta.name)
    elevacion = None
    elev_path = carpeta / "elevacion.bin.z"
    if elev_path.exists() and "elev_paso" in meta:
        elevacion = memoryview(zlib.decompress(elev_path.read_bytes())).cast("h")  # int16 little endian (Windows/Linux x86)
    return Grilla(meta, zlib.decompress(datos_path.read_bytes()), elevacion)


@lru_cache(maxsize=1)
def cargar() -> Terreno:
    grillas = []
    if DATA_DIR.is_dir():
        for carpeta in sorted(p for p in DATA_DIR.iterdir() if p.is_dir()):
            g = _cargar_grilla(carpeta)
            if g is not None:
                grillas.append(g)
    return Terreno(grillas=grillas)


def get_terreno() -> Terreno:
    return cargar()
