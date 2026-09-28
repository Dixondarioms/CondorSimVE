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

# (icao, nombre oficial, ciudad, estado, lat, lon, elevacion m)
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


def main() -> None:
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"icao": icao, "nombre": nombre, "ciudad": ciudad, "estado": estado, "elevacion_m": elev},
        }
        for icao, nombre, ciudad, estado, lat, lon, elev in BASES
    ]
    coleccion = {
        "type": "FeatureCollection",
        "name": "bases_aereas_venezuela",
        "fuente": "Wikipedia (CC BY-SA), OurAirports (dominio público)",
        "features": features,
    }
    DESTINO.write_text(json.dumps(coleccion, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(features)} bases en {DESTINO}")


if __name__ == "__main__":
    main()
