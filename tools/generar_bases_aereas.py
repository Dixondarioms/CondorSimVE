"""Genera frontend/static/geo/bases_aereas.geojson: bases aereas y aeropuertos de toda America.

Es una capa de referencia para el mapa (no depende de ningun escenario): el instructor puede colocar cualquiera
de ellas como unidad `base_aerea` desde su ventana emergente. Tiene dos partes:

  1. Curadas a mano (`origen: "curado"`): las 8 bases de la Aviacion Militar Bolivariana y 10 aerodromos de los
     vecinos dentro del area de detalle. Datos verificados y embebidos aqui, que se conservan tal cual:
       - Lista de bases, nombres oficiales y codigos OACI: Wikipedia (en), "Venezuelan Air Force", seccion de bases.
       - Coordenadas: las de cada articulo de Wikipedia (coinciden con OurAirports a menos de 1 km).
       - Elevaciones: OurAirports (dominio publico).
  2. El resto del continente (`origen: "ourairports"`), tomado de OurAirports (dominio publico,
     https://ourairports.com/data/): los aeropuertos grandes con codigo OACI, los medianos con codigo OACI y
     servicio regular, y cualquier aerodromo cuyo nombre indique uso militar (base aerea, AFB, NAS, etc.),
     aunque sea pequeno. Sin helipuertos, hidroaeropuertos, cerrados ni globos. Recuadro de la region `america`
     del mapa (ver tools/preparar_terreno.py). El CSV se descarga una vez a tools/cache/ (en .gitignore).

    backend\\venv\\Scripts\\python tools/generar_bases_aereas.py
"""

import csv
import json
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))
from app.engine.naciones import PAISES_AMERICA  # noqa: E402

DESTINO = RAIZ / "frontend" / "static" / "geo" / "bases_aereas.geojson"
URL_OURAIRPORTS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
CSV_OURAIRPORTS = RAIZ / "tools" / "cache" / "ourairports_airports.csv"

# recuadro de la region "america" del mapa (lon_min, lat_min, lon_max, lat_max), como en preparar_terreno.py
RECUADRO_AMERICA = (-170.0, -56.0, -30.0, 72.0)
TIPOS_EXCLUIDOS = {"heliport", "seaplane_base", "closed", "balloonport"}
# el nombre delata el uso militar (en ingles, espanol, portugues y frances); solo el nombre actual: las palabras
# clave de OurAirports guardan nombres historicos ("Bergstrom AFB" en un aeropuerto hoy civil) y no cuentan
MILITAR = re.compile(
    r"(Air Base|Air Force Base|\bAFB\b|Base A[ée]rea|Base A[ée]rienne|Base Aeronaval|Aeronaval|Naval Air|\bNAS\b|"
    r"Military|Militar|Fuerza A[ée]rea|For[çc]a A[ée]rea|\bAla \d|Grupo A[ée]reo|Escuadr[óo]n|Air National Guard|"
    r"Air Guard|\bANGB\b|Army Airfield|\bAAF\b|Marine Corps Air Station|\bMCAS\b|Air Station|Joint Base|"
    r"Air Reserve|Space Force Base|Aer[oó]dromo Militar)", re.I)

# (icao, nombre oficial, ciudad, estado, lat, lon, elevacion m)  -- Venezuela (Aviacion Militar Bolivariana)
BASES = [
    ("SVBL", "Base Aérea El Libertador", "Maracay (Palo Negro)", "Aragua", 10.18056, -67.56111, 442),
    ("SVBS", "Base Aérea Mariscal Sucre", "Maracay (Boca del Río)", "Aragua", 10.24972, -67.64944, 408),
    ("SVFM", "Base Aérea Generalísimo Francisco de Miranda (La Carlota)", "Caracas", "Distrito Capital", 10.48500, -66.84361, 835),
    ("SVMC", "Base Aérea General en Jefe Rafael Urdaneta", "Maracaibo", "Zulia", 10.55833, -71.72778, 73),
    ("SVBC", "Base Aérea Teniente Luis del Valle García", "Barcelona", "Anzoátegui", 10.10722, -64.68917, 9),
    ("SVBM", "Base Aérea Teniente Vicente Landaeta Gil", "Barquisimeto", "Lara", 10.04667, -69.36889, 622),
    ("SVPR", "Base Aérea Teniente Coronel Teófilo Luis Méndez", "Ciudad Guayana", "Bolívar", 8.28472, -62.76389, 144),
    ("SVPA", "Base Aérea General en Jefe José Antonio Páez", "Puerto Ayacucho", "Amazonas", 5.62000, -67.60611, 75),
]

# Paises vecinos dentro del area de detalle (lon -73,5..-59,5, lat 0,5..12,5): bases aereas militares y los
# aeropuertos principales cercanos a la frontera, como referencia para ejercicios con o contra los vecinos.
# (icao, nombre, ciudad, departamento/estado, pais, tipo, lat, lon). Coordenadas de los aerodromos (OurAirports /
# Wikipedia; el plano de OpenStreetMap se centra luego en la pista real). Sin elevacion (no verificada).
VECINOS = [
    ("SKUA", "Base Aérea Marandúa (Grupo Aéreo del Oriente)", "Marandúa", "Vichada", "Colombia", "base aérea", 5.5236, -68.6853),
    ("SKYP", "Aeropuerto El Alcaraván (Grupo Aéreo del Casanare)", "Yopal", "Casanare", "Colombia", "base aérea", 5.3191, -72.3840),
    ("SKCC", "Aeropuerto Internacional Camilo Daza", "Cúcuta", "Norte de Santander", "Colombia", "aeropuerto", 7.9276, -72.5115),
    ("SKUC", "Aeropuerto Santiago Pérez Quiroz", "Arauca", "Arauca", "Colombia", "aeropuerto", 7.0686, -70.7369),
    ("SKPC", "Aeropuerto Germán Olano", "Puerto Carreño", "Vichada", "Colombia", "aeropuerto", 6.1847, -67.4932),
    ("SKRH", "Aeropuerto Almirante Padilla", "Riohacha", "La Guajira", "Colombia", "aeropuerto", 11.5262, -72.9260),
    ("SKVP", "Aeropuerto Alfonso López Pumarejo", "Valledupar", "Cesar", "Colombia", "aeropuerto", 10.4350, -73.2495),
    ("SBBV", "Base Aérea de Boa Vista (Ala 7, FAB)", "Boa Vista", "Roraima", "Brasil", "base aérea", 2.8461, -60.6903),
    ("SYLT", "Aeropuerto de Lethem", "Lethem", "Upper Takutu-Upper Essequibo", "Guyana", "aeropuerto", 3.3728, -59.7894),
    ("TTPP", "Aeropuerto Internacional de Piarco (Air Guard)", "Piarco", "Trinidad", "Trinidad y Tobago", "base aérea", 10.5954, -61.3372),
]


def punto(lat, lon, propiedades):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": propiedades}


def curadas():
    """Las 18 curadas a mano, sin cambios respecto a la version anterior de la capa (origen "curado")."""
    return [
        punto(lat, lon, {"icao": icao, "nombre": nombre, "ciudad": ciudad, "estado": estado, "elevacion_m": elev,
                         "pais": "Venezuela", "tipo": "base aérea", "origen": "curado"})
        for icao, nombre, ciudad, estado, lat, lon, elev in BASES
    ] + [
        punto(lat, lon, {"icao": icao, "nombre": nombre, "ciudad": ciudad, "estado": estado, "elevacion_m": None,
                         "pais": pais, "tipo": tipo, "origen": "curado"})
        for icao, nombre, ciudad, estado, pais, tipo, lat, lon in VECINOS
    ]


def csv_ourairports(ruta=CSV_OURAIRPORTS):
    if not ruta.exists():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        print(f"descargando {URL_OURAIRPORTS} -> {ruta}")
        with urllib.request.urlopen(URL_OURAIRPORTS, timeout=120) as r:
            ruta.write_bytes(r.read())
    return ruta


def es_militar(nombre: str) -> bool:
    return bool(MILITAR.search(nombre))


def incluir(fila: dict) -> bool:
    """Criterio de inclusion de un aerodromo de OurAirports (ver la cabecera del modulo)."""
    if fila["continent"] not in ("NA", "SA") or fila["type"] in TIPOS_EXCLUIDOS:
        return False
    if fila["name"].startswith("[Duplicate]"):
        return False
    lon, lat = float(fila["longitude_deg"]), float(fila["latitude_deg"])
    lon_min, lat_min, lon_max, lat_max = RECUADRO_AMERICA
    if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
        return False
    if es_militar(fila["name"]):
        return True
    if not fila["icao_code"]:
        return False
    return fila["type"] == "large_airport" or (fila["type"] == "medium_airport" and fila["scheduled_service"] == "yes")


def identificador(fila: dict) -> str:
    """Codigo OACI; si no tiene, el codigo GPS de 4 letras (bases militares de EE. UU.) o el identificador local."""
    return fila["icao_code"] or (fila["gps_code"] if re.fullmatch(r"[A-Z0-9]{4}", fila["gps_code"] or "") else "") or fila["ident"]


def desde_ourairports(ruta, icaos_ocupados):
    features = []
    vistos = set(icaos_ocupados)
    with open(ruta, encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            if not incluir(fila):
                continue
            icao = identificador(fila)
            if icao in vistos:
                continue
            vistos.add(icao)
            pais = PAISES_AMERICA.get(fila["iso_country"], fila["iso_country"])
            elev = fila["elevation_ft"]
            features.append(punto(float(fila["latitude_deg"]), float(fila["longitude_deg"]), {
                "icao": icao, "nombre": fila["name"], "ciudad": fila["municipality"] or "", "estado": fila["iso_region"],
                "elevacion_m": round(int(elev) * 0.3048) if elev else None, "pais": pais,
                "tipo": "base aérea" if es_militar(fila["name"]) else "aeropuerto", "origen": "ourairports",
            }))
    return features


def main() -> None:
    fijas = curadas()
    nuevas = desde_ourairports(csv_ourairports(), {f["properties"]["icao"] for f in fijas})
    features = fijas + sorted(nuevas, key=lambda f: (f["properties"]["pais"], f["properties"]["icao"]))
    coleccion = {
        "type": "FeatureCollection",
        "name": "bases_aereas_america",
        "fuente": "Wikipedia (CC BY-SA), OurAirports (dominio público)",
        "features": features,
    }
    # un rasgo por linea: legible en los diffs y la mitad de tamano que con sangria completa
    cabecera = json.dumps({k: v for k, v in coleccion.items() if k != "features"}, ensure_ascii=False)[:-1]
    lineas = ",\n".join(json.dumps(f, ensure_ascii=False, separators=(",", ":")) for f in features)
    DESTINO.write_text(f'{cabecera}, "features": [\n{lineas}\n]}}\n', encoding="utf-8", newline="\n")
    militares = sum(1 for f in nuevas if f["properties"]["tipo"] == "base aérea")
    print(f"{len(features)} bases y aeródromos en {DESTINO}: {len(BASES)} de Venezuela y {len(VECINOS)} de vecinos (curadas), "
          f"{len(nuevas)} de OurAirports ({militares} militares) en {len({f['properties']['pais'] for f in nuevas})} países")


if __name__ == "__main__":
    main()
