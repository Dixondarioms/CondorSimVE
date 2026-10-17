"""Tramos de carretera aptos como pista de un Punto de Recobre Operacional (PRO) de una region del mapa:
frontend/static/geo/<region>/tramos_pro.geojson. Lo usa el motor (backend/app/engine/tramos_pro.py) para no dejar poner
un PRO con pista en cualquier sitio, y el mapa (capa Tramos aptos para PRO).

No toda carretera sirve. Un tramo es apto si cumple TODOS estos minimos (se pueden cambiar abajo):
  - carretera principal (autopista, troncal o principal) pavimentada (OSM `surface`; sin dato se asume pavimento);
  - recta: ningun punto del eje se aparta mas de RECTA_TOL_M de la linea entre los extremos, en al menos LARGO_MINIMO_M;
  - ancho de calzada estimado >= ANCHO_MINIMO_M: `width` de OSM, o `lanes` x 3,5 m mas hombrillos (2,5 m por lado en
    autopistas y troncales, 1 m en las demas; 2 canales si no hay dato);
  - sin puentes ni tuneles (OSM `bridge`/`tunnel`), ni agua o rio debajo, y a lo sumo URBANO_MAX de su largo en zona
    urbana (postes, pasarelas y edificios);
  - pendiente longitudinal (desnivel entre el punto mas alto y el mas bajo / largo) <= PENDIENTE_MAX (relieve SRTM de
    ~600 m: es una aproximacion).

Fuentes: Venezuela, el cache de OpenStreetMap de tools/preparar_vias.py (tools/cache/osm_vias, geometria completa y
etiquetas); el teatro ficticio, su carreteras.geojson (sin etiquetas: troncal de 2 canales pavimentada).

    python tools/preparar_tramos_pro.py                 # venezuela y teatro_ficticio
    python tools/preparar_tramos_pro.py --region venezuela
"""

import argparse
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
from app import terreno as terreno_mod  # noqa: E402

GEO = RAIZ / "frontend" / "static" / "geo"
CACHE_OSM = RAIZ / "tools" / "cache" / "osm_vias"

LARGO_MINIMO_M = 800.0  # la pista de emergencia mas corta (aviones de entrenamiento, transporte liviano)
ANCHO_MINIMO_M = 12.0
RECTA_TOL_M = 15.0
PENDIENTE_MAX = 0.02
URBANO_MAX = 0.2
MUESTRA_M = 150.0  # paso del muestreo de relieve y terreno
ANCHO_CANAL_M = 3.5
PRINCIPALES = {"motorway", "trunk", "primary"}
PAVIMENTO = {"", "asphalt", "concrete", "paved", "concrete:plates", "concrete:lanes", "chipseal"}
R_TIERRA = 6371000.0


def _ancho(t: dict) -> float:
    try:
        return float(str(t.get("width", "")).replace(",", ".").split()[0])
    except (ValueError, IndexError):
        pass
    try:
        canales = int(str(t.get("lanes", "2")).split(";")[0])
    except ValueError:
        canales = 2
    hombrillo = 2.5 if t.get("highway") in ("motorway", "trunk") else 1.0
    return canales * ANCHO_CANAL_M + 2 * hombrillo


def _apta(t: dict) -> bool:
    return (t.get("highway") in PRINCIPALES and t.get("surface", "") in PAVIMENTO
            and t.get("bridge", "no") == "no" and t.get("tunnel", "no") == "no" and t.get("ford", "no") == "no")


def vias_osm():
    """(nombre, ref, ancho, [(lon, lat)...]) de las vias aptas del cache de OSM (sin repetir las de dos celdas)."""
    vistas = set()
    for archivo in sorted(CACHE_OSM.glob("*.json")):
        for e in json.loads(archivo.read_text(encoding="utf-8")).get("elements", []):
            t = e.get("tags", {})
            if e.get("id") in vistas or not e.get("geometry") or not _apta(t):
                continue
            vistas.add(e.get("id"))
            yield t.get("name", ""), t.get("ref", ""), _ancho(t), [(g["lon"], g["lat"]) for g in e["geometry"]]


def vias_geojson(region: str):
    datos = json.loads((GEO / region / "carreteras.geojson").read_text(encoding="utf-8"))
    for f in datos["features"]:
        p = f["properties"]
        if p.get("nivel") == 2 and f["geometry"]["type"] == "LineString":
            yield p.get("nombre", ""), p.get("ref", ""), _ancho({"highway": "trunk"}), [tuple(c) for c in f["geometry"]["coordinates"]]


def _clave(p):
    return round(p[0], 6), round(p[1], 6)


def cadenas(vias):
    """Une las vias que comparten extremo (sin pasar por cruces de tres o mas): cada cadena es una calzada continua."""
    vias = [v for v in vias if len(v[3]) >= 2]
    extremos = {}
    for i, v in enumerate(vias):
        for p in (v[3][0], v[3][-1]):
            extremos.setdefault(_clave(p), []).append(i)
    usadas = set()
    for i, v in enumerate(vias):
        if i in usadas:
            continue
        usadas.add(i)
        puntos, ancho = list(v[3]), v[2]
        for hacia_adelante in (True, False):
            while True:
                fin = puntos[-1] if hacia_adelante else puntos[0]
                otras = [j for j in extremos.get(_clave(fin), []) if j not in usadas]
                if len(extremos.get(_clave(fin), [])) != 2 or len(otras) != 1:
                    break
                j = otras[0]
                usadas.add(j)
                w = vias[j][3]
                if _clave(w[-1]) == _clave(fin):
                    w = w[::-1]
                ancho = min(ancho, vias[j][2])
                puntos = puntos + w[1:] if hacia_adelante else w[::-1][:-1] + puntos
        yield v[0], v[1], ancho, puntos


def _xy(puntos):
    lat0 = math.radians(sum(p[1] for p in puntos) / len(puntos))
    return [(math.radians(lon) * R_TIERRA * math.cos(lat0), math.radians(lat) * R_TIERRA) for lon, lat in puntos]


def _desvio(xy, i, j) -> float:
    (x1, y1), (x2, y2) = xy[i], xy[j]
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy) or 1e-9
    return max((abs(dy * (x - x1) - dx * (y - y1)) / largo for x, y in xy[i + 1:j]), default=0.0)


def rectas(puntos):
    """Tramos rectos (i, j) de una cadena: el mas largo posible desde cada inicio, sin solaparse."""
    xy = _xy(puntos)
    i = 0
    while i < len(xy) - 1:
        j = i + 1
        while j + 1 < len(xy) and _desvio(xy, i, j + 1) <= RECTA_TOL_M:
            j += 1
        largo = math.dist(xy[i], xy[j])
        if largo >= LARGO_MINIMO_M:
            yield i, j, largo
        i = j


def evaluar(a, b, largo, ter):
    """(pendiente, fraccion urbana) del tramo a-b, o None si pasa por agua o un rio."""
    n = max(2, int(largo / MUESTRA_M) + 1)
    alturas, urbano = [], 0
    for k in range(n):
        f = k / (n - 1)
        lat, lon = a[1] + (b[1] - a[1]) * f, a[0] + (b[0] - a[0]) * f
        clase = ter.clase(lat, lon)
        if clase in ("agua", "rio"):
            return None
        urbano += clase == "urbano"
        h = ter.altura(lat, lon)
        if h is not None:
            alturas.append(h)
    pendiente = (max(alturas) - min(alturas)) / largo if alturas else 0.0
    return pendiente, urbano / n


def generar(region: str) -> None:
    ter = terreno_mod.cargar()
    if region == "venezuela" and CACHE_OSM.is_dir():
        fuente, vias = "© colaboradores de OpenStreetMap (ODbL 1.0)", list(vias_osm())
    else:
        fuente, vias = "carreteras de la región (sin etiquetas)", list(vias_geojson(region))
    print(f"{region}: {len(vias)} vías principales pavimentadas sin puentes ni túneles", flush=True)
    features, descartes = [], {"angosta": 0, "pendiente": 0, "urbana": 0, "agua": 0}
    for nombre, ref, ancho, puntos in cadenas(vias):
        for i, j, largo in rectas(puntos):
            a, b = puntos[i], puntos[j]
            if ancho < ANCHO_MINIMO_M:
                descartes["angosta"] += 1
                continue
            ev = evaluar(a, b, largo, ter)
            if ev is None:
                descartes["agua"] += 1
                continue
            pendiente, urbano = ev
            if pendiente > PENDIENTE_MAX:
                descartes["pendiente"] += 1
                continue
            if urbano > URBANO_MAX:
                descartes["urbana"] += 1
                continue
            rumbo = math.degrees(math.atan2((b[0] - a[0]) * math.cos(math.radians(a[1])), b[1] - a[1])) % 180
            features.append({"type": "Feature", "properties": {
                "nombre": nombre, "ref": ref, "largo_m": round(largo), "ancho_m": round(ancho, 1),
                "pendiente_pct": round(pendiente * 100, 1), "rumbo": round(rumbo)},
                "geometry": {"type": "LineString", "coordinates": [[round(a[0], 5), round(a[1], 5)],
                                                                   [round(b[0], 5), round(b[1], 5)]]}})
    features.sort(key=lambda f: -f["properties"]["largo_m"])
    for k, f in enumerate(features, 1):
        f["properties"]["id"] = f"Tramo {k:03d}"
    criterios = {"largo_minimo_m": LARGO_MINIMO_M, "ancho_minimo_m": ANCHO_MINIMO_M, "recta_tol_m": RECTA_TOL_M,
                 "pendiente_max_pct": PENDIENTE_MAX * 100, "urbano_max": URBANO_MAX}
    destino = GEO / region / "tramos_pro.geojson"
    destino.write_text(json.dumps({"type": "FeatureCollection", "fuente": fuente, "criterios": criterios,
                                   "features": features}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    largos = [f["properties"]["largo_m"] for f in features]
    print(f"  {len(features)} tramos aptos ({sum(x >= 2000 for x in largos)} de 2 km o más); descartados: {descartes}; "
          f"{destino.stat().st_size // 1024} KB", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--region", choices=["venezuela", "teatro_ficticio"], action="append")
    for region in ap.parse_args().region or ["venezuela", "teatro_ficticio"]:
        generar(region)


if __name__ == "__main__":
    main()
