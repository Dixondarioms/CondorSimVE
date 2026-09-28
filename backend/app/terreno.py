"""Consulta de clases de terreno a partir de la grilla generada por
tools/preparar_terreno.py (elevacion SRTM + cobertura WorldCover + ciudades)."""

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


class Terreno:
    def __init__(self, meta: dict | None = None, clases: bytes | None = None):
        self.meta = meta
        self.clases = clases

    @property
    def disponible(self) -> bool:
        return self.clases is not None

    def clase(self, lat: float, lon: float) -> str:
        """Nombre de la clase de terreno en (lat, lon). Fuera de la grilla: llano."""
        if not self.disponible:
            return "llano"
        lat = max(-85.0, min(85.0, lat))
        z, n = self.meta["z"], 2 ** self.meta["z"] * 256
        x = (lon + 180.0) / 360.0 * n - self.meta["x0"] * 256
        s = math.sin(math.radians(lat))
        y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n - self.meta["y0"] * 256
        xi, yi = int(x), int(y)
        if not (0 <= xi < self.meta["ancho"] and 0 <= yi < self.meta["alto"]):
            return "llano"
        return NOMBRES.get(self.clases[yi * self.meta["ancho"] + xi], "llano")

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


@lru_cache(maxsize=1)
def cargar() -> Terreno:
    meta_path, datos_path = DATA_DIR / "meta.json", DATA_DIR / "clases.bin.z"
    if not (meta_path.exists() and datos_path.exists()):
        return Terreno()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return Terreno(meta, zlib.decompress(datos_path.read_bytes()))


def get_terreno() -> Terreno:
    return cargar()
