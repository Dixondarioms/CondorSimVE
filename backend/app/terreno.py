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

    def __init__(self, meta: dict, clases: bytes):
        self.meta = meta
        self.clases = clases

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
        """Lo que necesita el frontend para dibujar la region (GET /api/mapas)."""
        m = self.meta
        return {"id": self.id, "nombre": m.get("nombre", self.id), "bbox": m.get("bbox"), "z": self.z,
                "z_min": int(m.get("z_min", max(2, self.z - 4))), "metros_por_pixel": m.get("metros_por_pixel")}


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
    return Grilla(meta, zlib.decompress(datos_path.read_bytes()))


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
