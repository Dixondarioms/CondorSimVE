"""Ciudades de referencia para describir posiciones en texto ("a 35 km al NE de Capital Azul").

Lee las capas `lugares.geojson` de cada region (frontend/static/geo/<region>/), las mismas que dibuja el mapa.
"""

import json
from functools import lru_cache
from math import atan2, cos, degrees, radians, sin
from pathlib import Path

from app.engine import geo

GEO = Path(__file__).resolve().parents[3] / "frontend" / "static" / "geo"
RUMBOS = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")


@lru_cache(maxsize=1)
def todos() -> tuple[dict, ...]:
    """[{nombre, lat, lon, pop, capital}] de todas las regiones (sin repetir nombres en el mismo lugar)."""
    vistos, lista = set(), []
    for archivo in sorted(GEO.glob("*/lugares.geojson")):
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for f in datos.get("features", []):
            p, g = f.get("properties") or {}, f.get("geometry") or {}
            if g.get("type") != "Point" or not p.get("name"):
                continue
            lon, lat = g["coordinates"][:2]
            clave = (p["name"], round(lat, 2), round(lon, 2))
            if clave in vistos:
                continue
            vistos.add(clave)
            lista.append({"nombre": p["name"], "lat": lat, "lon": lon, "pop": p.get("pop") or 0,
                          "capital": bool(p.get("capital"))})
    return tuple(lista)


def rumbo(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Rumbo aproximado (8 puntos) desde el punto 1 hacia el punto 2."""
    f1, f2, dl = radians(lat1), radians(lat2), radians(lon2 - lon1)
    ang = (degrees(atan2(sin(dl) * cos(f2), cos(f1) * sin(f2) - sin(f1) * cos(f2) * cos(dl))) + 360) % 360
    return RUMBOS[int((ang + 22.5) // 45) % 8]


def cercano(lat: float, lon: float, max_km: float = 250.0) -> dict | None:
    """Ciudad mas cercana (las grandes pesan un poco mas), con distancia y rumbo desde ella; None si no hay."""
    mejor, puntaje = None, None
    for c in todos():
        d = geo.distancia_km(c["lat"], c["lon"], lat, lon)
        if d > max_km:
            continue
        p = d / (1.0 + min(c["pop"], 3_000_000) / 3_000_000)
        if puntaje is None or p < puntaje:
            mejor, puntaje = dict(c, km=d), p
    if mejor:
        mejor["rumbo"] = rumbo(mejor["lat"], mejor["lon"], lat, lon)
    return mejor


def describir(lat: float, lon: float) -> str:
    """"en Capital Azul", "a 35 km al NE de Capital Azul" o, lejos de toda ciudad, la posicion en grados."""
    c = cercano(lat, lon)
    if c is None:
        return f"en {abs(lat):.1f}° {'N' if lat >= 0 else 'S'} {abs(lon):.1f}° {'O' if lon < 0 else 'E'}"
    if c["km"] < 8:
        return f"en {c['nombre']}"
    return f"a {round(c['km'] / 5) * 5:.0f} km al {c['rumbo']} de {c['nombre']}"
