"""Infraestructura no militar de Venezuela para la capa del mapa y los ejercicios: centrales electricas, refinerias,
centros de comunicaciones y puentes estrategicos, con su ubicacion real de OpenStreetMap (© colaboradores de
OpenStreetMap, ODbL) y una ficha breve.

Baja de Overpass las centrales (power=plant), refinerias, estaciones terrenas y puentes con nombre de Venezuela (con
cache en tools/cache/osm_infra/), elige las de importancia estrategica y escribe
frontend/static/geo/venezuela/infraestructura.json. Las capacidades son las que trae OpenStreetMap (MW) o las
nominales publicadas (refinerias, en barriles por dia); son orientativas.

    backend\\venv\\Scripts\\python tools/preparar_infraestructura.py            # usa la cache si existe
    backend\\venv\\Scripts\\python tools/preparar_infraestructura.py --bajar    # vuelve a consultar Overpass
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import preparar_aerodromos as osm  # noqa: E402  (cliente de Overpass con espejos)

CACHE = RAIZ / "tools" / "cache" / "osm_infra"
DESTINO = RAIZ / "frontend" / "static" / "geo" / "venezuela" / "infraestructura.json"

CONSULTA_INSTALACIONES = '''[out:json][timeout:240];
area["ISO3166-1"="VE"][admin_level=2]->.ve;
(
 nwr["power"="plant"](area.ve);
 nwr["name"~"Refiner",i](area.ve);
 nwr["name"~"Estaci.n terrena|Antena del VENESAT|Cerro El Volc.n|Sede Central de CANTV",i](area.ve);
);
out center tags;'''
CONSULTA_PUENTES = '''[out:json][timeout:240];
area["ISO3166-1"="VE"][admin_level=2]->.ve;
way["bridge"="yes"]["name"~"^Puente",i]["highway"~"motorway|trunk|primary|secondary"](area.ve);
out geom tags;'''

MW_MINIMO = 100  # centrales termicas que se incluyen (las hidroelectricas, todas las que tienen nombre)
# refinerias: nombre en OpenStreetMap -> (nombre en la capa, capacidad nominal publicada)
REFINERIAS = {
    "Refinería Amuay": ("Refinería de Amuay (Complejo Refinador Paraguaná)", "645 000 barriles por día (nominal)"),
    "Refinería El Palito": ("Refinería El Palito", "140 000 barriles por día (nominal)"),
    "Refinería Puerto La Cruz": ("Refinería de Puerto La Cruz", "187 000 barriles por día (nominal)"),
}
# la refineria de Cardon no tiene nombre en OpenStreetMap: se ubica en Punta Cardon, junto a su planta electrica
REFINERIAS_A_MANO = [
    {"nombre": "Refinería de Cardón (Complejo Refinador Paraguaná)", "lat": 11.629, "lon": -70.225,
     "capacidad": "310 000 barriles por día (nominal)", "aproximada": True},
]
# centros de comunicaciones: nombre en OpenStreetMap -> (nombre en la capa, descripcion)
COMUNICACIONES = {
    "Cerro El Volcán": ("Cerro El Volcán (antenas y enlaces)", "Cumbre al sureste de Caracas con las antenas de radio, "
                        "televisión y enlaces de microondas que sirven a la capital."),
    "Estación terrena de control Baemari": ("Estación Terrena de Control Satelital BAEMARI (El Sombrero)",
                                            "Control de los satélites venezolanos, dentro de la Base Aérea Capitán Manuel Ríos."),
    "Antena del VENESAT-1": ("Estación Terrena Luepa", "Estación secundaria de control satelital en la Gran Sabana."),
    "Sede Central de CANTV": ("Sede central de CANTV (Caracas)", "Centro de la red nacional de telefonía y datos."),
}
# puentes estrategicos: nombre en OpenStreetMap -> descripcion
PUENTES = {
    "Puente General Rafael Urdaneta": "Cruza el lago de Maracaibo y une Maracaibo con la costa oriental del lago.",
    "Puente Orinoquia": "Cruza el Orinoco entre Ciudad Guayana y Soledad (carretera y vía férrea).",
    "Puente Angostura": "Cruza el Orinoco en Ciudad Bolívar: une Guayana con el oriente y el centro del país.",
    "Puente Caroní": "Cruza el río Caroní en Ciudad Guayana.",
    "Puente Angosturita": "Cruza el río Caroní en Ciudad Guayana (autopista).",
    "Puente María Nieves": "Cruza el río Apure en San Fernando de Apure.",
    "Puente Internacional Simón Bolívar": "Paso fronterizo San Antonio del Táchira – Cúcuta (Colombia).",
    "Puente Internacional Francisco de Paula Santander": "Paso fronterizo Ureña – Cúcuta (Colombia).",
    "Puente Internacional José Antonio Páez": "Paso fronterizo El Amparo – Arauca (Colombia).",
    "Puente Internacional Atanasio Girardot": "Paso fronterizo de Táchira con Colombia.",
    "Puente Internacional La Unión": "Paso fronterizo de Táchira con Colombia.",
}


# nombres de OpenStreetMap que se aclaran (nombre en la capa, descripcion)
RENOMBRAR = {
    "Guri": ("Central Hidroeléctrica Simón Bolívar (Guri)", "La mayor central del país, sobre el río Caroní."),
    "Caruachi": ("Central Hidroeléctrica Francisco de Miranda (Caruachi)", "Sobre el río Caroní, aguas abajo de Guri."),
    "Tocoma": ("Central Hidroeléctrica Manuel Piar (Tocoma)", "Sobre el río Caroní, entre Guri y Caruachi; obra de larga "
               "construcción: su capacidad real puede ser menor que la prevista."),
    "Termozulia Rafael Urdaneta Thermoelectric Complex": ("Complejo Termoeléctrico Termozulia (Maracaibo)",
                                                          "Principal generación térmica del occidente del país."),
    "Central Eléctrica Josefa Joaquina Sánchez Bastidas": ("Central Termoeléctrica Josefa Joaquina Sánchez (Tacoa)",
                                                           "Generación térmica del litoral central, en La Guaira."),
    "Planta Centro": ("Planta Centro (Morón)", "La mayor central térmica del país, en la costa de Carabobo."),
}


def km(a, b) -> float:
    r = 6371.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return 2 * r * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))


def bajar(nombre: str, consulta: str, forzar: bool) -> dict:
    ruta = CACHE / nombre
    if ruta.exists() and not forzar:
        return json.loads(ruta.read_text(encoding="utf-8"))
    for _ in range(3):
        datos = osm.consultar_overpass(consulta)
        if datos:
            CACHE.mkdir(parents=True, exist_ok=True)
            ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
            return datos
    raise SystemExit(f"Overpass no respondio ({nombre}); vuelva a intentarlo mas tarde.")


def centro(e) -> tuple[float, float]:
    c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
    return round(c["lat"], 5), round(c["lon"], 5)


def megavatios(texto) -> float | None:
    m = re.match(r"\s*([\d.,]+)\s*(MW|Mw|mw)?", str(texto or ""))
    if not m or not m.group(2):
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def centrales(elementos) -> list[dict]:
    salida = []
    macagua = []
    for e in elementos:
        t = e.get("tags", {})
        if t.get("power") != "plant" or not t.get("name"):
            continue
        nombre, fuente = t["name"], t.get("plant:source", "")
        mw = megavatios(t.get("plant:output:electricity"))
        lat, lon = centro(e)
        if "Macagua" in nombre:  # tres casas de maquinas de la misma central
            macagua.append((lat, lon, mw or 0))
            continue
        hidro = "hydro" in fuente
        if fuente in ("wind", "solar"):
            continue
        if not hidro and (mw or 0) < MW_MINIMO and not re.search(r"Planta Centro|Tacoa|Josefa Joaquina|Termozulia Rafael", nombre):
            continue
        if hidro and "Microcentral" in nombre:
            continue
        salida.append({
            "nombre": nombre, "clase": "hidroelectrica" if hidro else "termoelectrica", "lat": lat, "lon": lon,
            "capacidad": f"{mw:,.0f} MW".replace(",", " ") if mw else "", "operador": t.get("operator", ""),
            "combustible": {"gas": "gas", "oil": "fueloil", "diesel": "diésel", "gas;fuel oil": "gas y fueloil"}.get(fuente, ""),
        })
    if macagua:
        salida.append({
            "nombre": "Central Hidroeléctrica Macagua (Antonio José de Sucre)", "clase": "hidroelectrica",
            "lat": round(sum(m[0] for m in macagua) / len(macagua), 5), "lon": round(sum(m[1] for m in macagua) / len(macagua), 5),
            "capacidad": f"{sum(m[2] for m in macagua):,.0f} MW".replace(",", " "), "operador": "CORPOELEC", "combustible": "",
        })
    for c in salida:
        if c["nombre"] in RENOMBRAR:
            c["nombre"], c["descripcion"] = RENOMBRAR[c["nombre"]]
        elif c["nombre"].endswith(" Power Plant"):
            c["nombre"] = "Planta Termoeléctrica " + c["nombre"][: -len(" Power Plant")]
        if c["nombre"].startswith("Tocoma") or "Tocoma" in c["nombre"]:
            c["capacidad"] = f"{c['capacidad']} previstos" if c["capacidad"] else ""
    return salida


def refinerias(elementos) -> list[dict]:
    salida, vistas = [], set()
    for e in elementos:
        nombre = e.get("tags", {}).get("name")
        if nombre in REFINERIAS and nombre not in vistas:
            vistas.add(nombre)
            lat, lon = centro(e)
            nuevo, capacidad = REFINERIAS[nombre]
            salida.append({"nombre": nuevo, "clase": "refineria", "lat": lat, "lon": lon, "capacidad": capacidad,
                           "operador": "PDVSA"})
    for r in REFINERIAS_A_MANO:
        salida.append({**r, "clase": "refineria", "operador": "PDVSA"})
    return salida


def comunicaciones(elementos) -> list[dict]:
    salida, vistas = [], set()
    for e in elementos:
        nombre = e.get("tags", {}).get("name")
        if nombre in COMUNICACIONES and nombre not in vistas:
            vistas.add(nombre)
            lat, lon = centro(e)
            nuevo, desc = COMUNICACIONES[nombre]
            salida.append({"nombre": nuevo, "clase": "centro_comunicaciones", "lat": lat, "lon": lon, "descripcion": desc})
    return salida


def puentes(elementos) -> list[dict]:
    por_nombre: dict[str, list] = {}
    for e in elementos:
        nombre = e.get("tags", {}).get("name")
        if nombre in PUENTES:
            por_nombre.setdefault(nombre, []).append([(p["lat"], p["lon"]) for p in e["geometry"]])
    salida = []
    for nombre, tramos in por_nombre.items():
        puntos = [p for t in tramos for p in t]
        lat = sum(p[0] for p in puntos) / len(puntos)
        lon = sum(p[1] for p in puntos) / len(puntos)
        # largo: el del tramo mas largo (las dos calzadas de un puente son dos vias paralelas)
        largo = max(sum(km(t[i], t[i + 1]) for i in range(len(t) - 1)) for t in tramos)
        # radio que corta: la punta mas lejana del centro, mas un margen
        radio = max(km((lat, lon), p) for p in puntos) + 0.3
        salida.append({"nombre": nombre, "clase": "puente", "lat": round(lat, 5), "lon": round(lon, 5),
                       "largo_km": round(largo, 2), "radio_km": round(min(radio, 20.0), 2), "descripcion": PUENTES[nombre]})
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bajar", action="store_true", help="volver a consultar Overpass aunque haya cache")
    args = ap.parse_args()
    inst = bajar("instalaciones.json", CONSULTA_INSTALACIONES, args.bajar)["elements"]
    pts = bajar("puentes.json", CONSULTA_PUENTES, args.bajar)["elements"]
    elementos = centrales(inst) + refinerias(inst) + comunicaciones(inst) + puentes(pts)
    for i, e in enumerate(sorted(elementos, key=lambda x: (x["clase"], x["nombre"]))):
        e["id"] = f"inf{i + 1:03d}"
    elementos.sort(key=lambda x: x["id"])
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps({
        "fuente": "© colaboradores de OpenStreetMap (ODbL); capacidades de refinación nominales publicadas por PDVSA",
        "instalaciones": elementos,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    from collections import Counter
    print(DESTINO, Counter(e["clase"] for e in elementos))


if __name__ == "__main__":
    main()
