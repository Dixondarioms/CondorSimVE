"""Tramos de carretera aptos como pista de aterrizaje de un PRO. Un Punto de Recobre Operacional (PRO) con pista solo puede
estar en uno de ellos (o en un aerodromo con pista suficiente); sin pista (helicopteros) puede ir en cualquier sitio.

Los tramos los calcula tools/preparar_tramos_pro.py a partir de las carreteras reales (OpenStreetMap) con los minimos de una
pista en carretera: carretera principal pavimentada, recta, con ancho suficiente, sin puentes ni tuneles, casi plana y fuera de zona
urbana. Se guardan en frontend/static/geo/<region>/tramos_pro.geojson (tambien los dibuja el mapa, capa Tramos aptos para PRO). Donde no hay
datos de carreteras (regiones sin ese archivo) no se puede verificar y el PRO queda con el aviso.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from app.engine import plataformas

GEO = Path(__file__).resolve().parents[3] / "frontend" / "static" / "geo"
DATOS_TERRENO = Path(__file__).resolve().parents[2] / "data" / "terreno"
RADIO_M = 1000.0  # el PRO (su zona de apoyo) a esta distancia o menos del eje del tramo
CELDA = 0.05  # grados del indice espacial
BUSQUEDA_KM = 60.0  # para sugerir el tramo apto mas cercano


@lru_cache(maxsize=1)
def _datos() -> tuple[list[dict], dict, list[tuple[float, float, float, float]], dict]:
    """(tramos, indice por celda, bbox de las regiones con datos, criterios)."""
    tramos, indice, cajas, criterios = [], {}, [], {}
    for archivo in sorted(GEO.glob("*/tramos_pro.geojson")):
        try:
            d = json.loads(archivo.read_text(encoding="utf-8"))
            meta = json.loads((DATOS_TERRENO / archivo.parent.name / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cajas.append(tuple(meta["bbox"]))  # oeste, sur, este, norte
        criterios = d.get("criterios") or criterios
        for f in d.get("features", []):
            (lon1, lat1), (lon2, lat2) = f["geometry"]["coordinates"][:2]
            t = {**f["properties"], "a": (lat1, lon1), "b": (lat2, lon2)}
            tramos.append(t)
            pad = RADIO_M / 100_000  # con margen para la longitud (cos de la latitud)
            for i in range(math.floor((min(lat1, lat2) - pad) / CELDA), math.floor((max(lat1, lat2) + pad) / CELDA) + 1):
                for j in range(math.floor((min(lon1, lon2) - pad) / CELDA), math.floor((max(lon1, lon2) + pad) / CELDA) + 1):
                    indice.setdefault((i, j), []).append(t)
    return tramos, indice, cajas, criterios


def cubierto(lat: float, lon: float) -> bool:
    """Si hay datos de carreteras para verificar un tramo apto en el punto."""
    return any(o <= lon <= e and s <= lat <= n for o, s, e, n in _datos()[2])


def distancia_m(lat: float, lon: float, t: dict) -> float:
    """Distancia del punto al eje del tramo."""
    k = 111_195.0
    c = math.cos(math.radians(lat))
    ax, ay = (t["a"][1] - lon) * k * c, (t["a"][0] - lat) * k
    bx, by = (t["b"][1] - lon) * k * c, (t["b"][0] - lat) * k
    dx, dy = bx - ax, by - ay
    f = max(0.0, min(1.0, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1e-9)))
    return math.hypot(ax + f * dx, ay + f * dy)


def cercanos(lat: float, lon: float, radio_m: float = RADIO_M) -> list[tuple[float, dict]]:
    """Tramos a <= radio_m (con su distancia), del mas cercano al mas lejano."""
    _, indice, _, _ = _datos()
    if radio_m <= RADIO_M:
        candidatos = indice.get((math.floor(lat / CELDA), math.floor(lon / CELDA)), [])
    else:
        candidatos = _datos()[0]
    out = [(distancia_m(lat, lon, t), t) for t in candidatos]
    return sorted((x for x in out if x[0] <= radio_m), key=lambda x: x[0])


def resumen(t: dict) -> str:
    nombre = " ".join(x for x in (t.get("ref"), t.get("nombre")) if x) or "carretera"
    return f"{t['id']} {nombre} ({t['largo_m']:,} m)".replace(",", ".")


@lru_cache(maxsize=4096)
def _sitio(lat: float, lon: float, pista_m: float) -> tuple[str, dict | None, str]:
    plano = plataformas.pista_del_plano(lat, lon)
    if plano and plano[0] >= pista_m:
        return "aerodromo", {"nombre": plano[1], "largo_m": round(plano[0])}, ""
    if not cubierto(lat, lon):
        return "sin_datos", None, ""
    cerca = cercanos(lat, lon)
    aptos = [t for _, t in cerca if t["largo_m"] >= pista_m]
    if aptos:
        return "tramo", aptos[0], ""
    crit = _datos()[3]
    pista = f"{pista_m:,.0f}".replace(",", ".")
    texto = (f"Un PRO con pista de {pista} m solo puede ir en un tramo de carretera apto (recto, pavimentado, "
             f"de {crit.get('ancho_minimo_m', 12):.0f} m de ancho o más, pendiente de {crit.get('pendiente_max_pct', 2):.0f} % "
             f"o menos, sin puentes ni túneles, fuera de zona urbana) a {RADIO_M / 1000:.0f} km o menos, o en un aeródromo "
             "con esa pista.")
    if cerca:
        t = max((t for _, t in cerca), key=lambda t: t["largo_m"])
        texto += f" El tramo de aquí, {resumen(t)}, es más corto: baje la pista a {t['largo_m']:,} m o busque otro.".replace(",", ".")
    else:
        lejos = [(d, t) for d, t in cercanos(lat, lon, BUSQUEDA_KM * 1000) if t["largo_m"] >= pista_m]
        texto += (f" El más cercano: {resumen(lejos[0][1])}, a {lejos[0][0] / 1000:.0f} km (capa «Tramos aptos para PRO» del mapa)."
                  if lejos else " Vea la capa «Tramos aptos para PRO» del mapa.")
    return "no_apto", None, texto


def sitio(lat: float, lon: float, pista_m: float) -> tuple[str, dict | None, str]:
    """(tipo, tramo o aerodromo, motivo): tipo "tramo", "aerodromo", "sin_datos" (no se puede verificar) o "no_apto"
    (con el motivo y una sugerencia). Sin pista siempre es apto ("sin_pista")."""
    if not pista_m or pista_m <= 0:
        return "sin_pista", None, ""
    return _sitio(round(lat, 5), round(lon, 5), float(pista_m))


def error_de_ubicacion(lat: float, lon: float, pista_m: float | None) -> str | None:
    """El motivo por el que un PRO con esa pista no puede estar en el punto, o None."""
    tipo, _, motivo = sitio(lat, lon, pista_m or 0)
    return motivo if tipo == "no_apto" else None

