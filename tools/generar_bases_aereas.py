"""Genera frontend/static/geo/bases_aereas.geojson: las bases aereas de la Aviacion Militar Bolivariana.

Es una capa de referencia para el mapa (no depende de ningun escenario): el instructor puede colocar cualquiera
de ellas como unidad `base_aerea` desde su ventana emergente. Datos ya verificados y embebidos, asi que no
necesita internet:

  - Lista de bases, nombres oficiales y codigos OACI: Wikipedia (en), "Venezuelan Air Force", seccion de bases.
  - Coordenadas: las de cada articulo de Wikipedia (coinciden con OurAirports a menos de 1 km).
  - Elevaciones: OurAirports (dominio publico).

    backend\\venv\\Scripts\\python tools/generar_bases_aereas.py
"""

import json
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "frontend" / "static" / "geo" / "bases_aereas.geojson"

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

# Paises vecinos dentro del area del mapa (lon -73,5..-59,5, lat 0,5..12,5): bases aereas militares y los
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


def main() -> None:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"icao": icao, "nombre": nombre, "ciudad": ciudad, "estado": estado, "elevacion_m": elev,
                           "pais": "Venezuela", "tipo": "base aérea"},
        }
        for icao, nombre, ciudad, estado, lat, lon, elev in BASES
    ] + [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"icao": icao, "nombre": nombre, "ciudad": ciudad, "estado": estado, "elevacion_m": None,
                           "pais": pais, "tipo": tipo},
        }
        for icao, nombre, ciudad, estado, pais, tipo, lat, lon in VECINOS
    ]
    coleccion = {
        "type": "FeatureCollection",
        "name": "bases_aereas_venezuela",
        "fuente": "Wikipedia (CC BY-SA), OurAirports (dominio público)",
        "features": features,
    }
    DESTINO.write_text(json.dumps(coleccion, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(features)} bases y aeródromos en {DESTINO} ({len(BASES)} de Venezuela, {len(VECINOS)} de países vecinos)")


if __name__ == "__main__":
    main()
