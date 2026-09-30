"""Genera frontend/static/geo/aerodromos.geojson: el plano detallado de cada base aerea (pistas, calles de rodaje,
plataformas, hangares y edificios) para verlo en el mapa al acercarse, sin internet.

Fuente: OpenStreetMap (https://www.openstreetmap.org), via la API publica Overpass. Licencia ODbL 1.0: uso libre,
incluso offline, citando "(c) colaboradores de OpenStreetMap" (el mapa ya lo muestra al activar la capa).
La imagen satelital offline (Sentinel-2, 10 m/pixel) no alcanza para ver una pista (45 m = 4 pixeles) ni los
hangares; los mosaicos de alta resolucion (Google, Bing, Esri) no permiten guardarse para uso sin conexion.

Se ejecuta UNA vez con internet (como preparar_terreno.py). Guarda la respuesta cruda en
tools/cache/osm_aerodromos.json: si ya existe no vuelve a descargar (use --descargar para refrescar).

Procesa:
  - pistas (aeroway=runway): rectangulo con su ancho real (etiqueta width; 45 m si falta), numeracion de cada
    cabecera (etiqueta ref o calculada del rumbo magnetico) y marcas: umbrales, eje, punto de toma de contacto
    y bordes, todo en metros para que escale con el zoom;
  - calles de rodaje (taxiway/taxilane) con su ancho (18 m si falta) y el eje amarillo;
  - plataformas (apron), helipuertos, hangares y edificios dentro del aerodromo, y el limite del aerodromo.

    backend\\venv\\Scripts\\python tools/preparar_aerodromos.py
"""

import argparse
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "frontend" / "static" / "geo" / "aerodromos.geojson"
CACHE = RAIZ / "tools" / "cache" / "osm_aerodromos.json"
# espejos publicos de Overpass, en orden (overpass-api.de a veces corta las consultas grandes)
ESPEJOS = ["https://overpass.kumi.systems/api/interpreter", "https://overpass-api.de/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
UA = {"User-Agent": "SimuladorFenix/1.0 (educational, offline military academy training tool)"}

# (icao, nombre, lat, lon): las bases de geo/bases_aereas.geojson mas las que usan las plantillas de escenario
BASES = [
    ("SVBL", "Base Aérea El Libertador", 10.18056, -67.56111),
    ("SVBS", "Base Aérea Mariscal Sucre", 10.24972, -67.64944),
    ("SVFM", "Base Aérea La Carlota", 10.48500, -66.84361),
    ("SVMC", "Base Aérea Rafael Urdaneta", 10.55833, -71.72778),
    ("SVBC", "Base Aérea Luis del Valle García", 10.10722, -64.68917),
    ("SVBM", "Base Aérea Vicente Landaeta Gil", 10.04667, -69.36889),
    ("SVPR", "Base Aérea Teófilo Luis Méndez", 8.28472, -62.76389),
    ("SVPA", "Base Aérea José Antonio Páez", 5.62000, -67.60611),
    ("SVBI", "Base Aérea Barinas", 8.61958, -70.22083),
    # paises vecinos (ver tools/generar_bases_aereas.py, VECINOS)
    ("SKUA", "Base Aérea Marandúa", 5.5236, -68.6853),
    ("SKYP", "Aeropuerto El Alcaraván (Yopal)", 5.3191, -72.3840),
    ("SKCC", "Aeropuerto Camilo Daza (Cúcuta)", 7.9276, -72.5115),
    ("SKUC", "Aeropuerto de Arauca", 7.0686, -70.7369),
    ("SKPC", "Aeropuerto de Puerto Carreño", 6.1847, -67.4932),
    ("SKRH", "Aeropuerto de Riohacha", 11.5262, -72.9260),
    ("SKVP", "Aeropuerto de Valledupar", 10.4350, -73.2495),
    ("SBBV", "Base Aérea de Boa Vista", 2.8461, -60.6903),
    ("SYLT", "Aeropuerto de Lethem", 3.3728, -59.7894),
    ("TTPP", "Aeropuerto de Piarco", 10.5954, -61.3372),
]
RADIO_PISTAS_M = 4500
RADIO_EDIFICIOS_M = 3000
DECLINACION_OESTE = 12.0  # declinacion magnetica aproximada en Venezuela (2020-2030): rumbo magnetico = verdadero + 12
ANCHO_PISTA = 45.0
ANCHO_RODAJE = 18.0


# ------------------------------------------------------------------ descarga
def consulta(lat: float, lon: float) -> str:
    """Consulta Overpass de una base: todo lo aeronautico y los edificios en un recuadro de ~9 x 9 km alrededor."""
    d = RADIO_PISTAS_M / 111000
    caja = f"({lat - d:.5f},{lon - d:.5f},{lat + d:.5f},{lon + d:.5f})"
    return (f'[out:json][timeout:90];(way["aeroway"]{caja};node["aeroway"="helipad"]{caja};'
            f'relation["aeroway"="aerodrome"]{caja};way["building"]{caja};);out geom;')


def consultar_overpass(texto: str) -> dict | None:
    datos = urllib.parse.urlencode({"data": texto}).encode()
    for url in ESPEJOS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=datos, headers=UA), timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"    {url}: {e}")
    return None


# ---- alternativa: la API de OpenStreetMap (api.openstreetmap.org/api/0.6/map), por celdas pequeñas ----
API_MAPA = "https://api.openstreetmap.org/api/0.6/map?bbox={oeste:.5f},{sur:.5f},{este:.5f},{norte:.5f}"
CELDA_GRADOS = 0.025
RADIO_GRADOS = 0.0375  # ~4 km alrededor del punto de la base


def celda_osm(sur, oeste, norte, este, nodos, vias, relaciones, nivel=0) -> None:
    """Baja una celda; si tiene demasiados nodos (limite de la API: 50 000) la parte en cuatro."""
    url = API_MAPA.format(oeste=oeste, sur=sur, este=este, norte=norte)
    for intento in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                xml = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 400 and nivel < 4:  # demasiados nodos: cuatro celdas mas chicas
                lat_m, lon_m = (sur + norte) / 2, (oeste + este) / 2
                for s, o, n, e_ in ((sur, oeste, lat_m, lon_m), (sur, lon_m, lat_m, este), (lat_m, oeste, norte, lon_m), (lat_m, lon_m, norte, este)):
                    celda_osm(s, o, n, e_, nodos, vias, relaciones, nivel + 1)
                return
            if intento == 2:
                raise
        except Exception:  # noqa: BLE001
            if intento == 2:
                raise
        time.sleep(2 * (intento + 1))
    raiz = ET.fromstring(xml)
    for n in raiz.iter("node"):
        nodos[int(n.get("id"))] = (float(n.get("lat")), float(n.get("lon")), {t.get("k"): t.get("v") for t in n.iter("tag")})
    for w in raiz.iter("way"):
        vias[int(w.get("id"))] = ([int(nd.get("ref")) for nd in w.iter("nd")], {t.get("k"): t.get("v") for t in w.iter("tag")})
    for rel in raiz.iter("relation"):
        relaciones[int(rel.get("id"))] = ([(m.get("type"), int(m.get("ref")), m.get("role")) for m in rel.iter("member")],
                                         {t.get("k"): t.get("v") for t in rel.iter("tag")})
    time.sleep(1.0)  # uso cortes de la API publica


def descargar_api(solo=None) -> dict:
    """Lo mismo que Overpass ("out geom") armado desde la API de OSM, celda por celda. `solo`: ids a bajar."""
    nodos, vias, relaciones = {}, {}, {}
    for icao, nombre, lat, lon in BASES:
        if solo is not None and icao not in solo:
            continue
        print(f"  {icao} {nombre}...", flush=True)
        n = math.ceil(2 * RADIO_GRADOS / CELDA_GRADOS)
        for i in range(n):
            for j in range(n):
                sur = lat - RADIO_GRADOS + i * CELDA_GRADOS
                oeste = lon - RADIO_GRADOS + j * CELDA_GRADOS
                celda_osm(sur, oeste, sur + CELDA_GRADOS, oeste + CELDA_GRADOS, nodos, vias, relaciones)
    geom = lambda refs: [{"lat": nodos[r][0], "lon": nodos[r][1]} for r in refs if r in nodos]  # noqa: E731
    elementos = []
    for vid, (refs, tags) in vias.items():
        if "aeroway" in tags or "building" in tags:
            elementos.append({"type": "way", "id": vid, "tags": tags, "geometry": geom(refs)})
    for nid, (la, lo, tags) in nodos.items():
        if tags.get("aeroway") == "helipad":
            elementos.append({"type": "node", "id": nid, "lat": la, "lon": lo, "tags": tags})
    for rid, (miembros, tags) in relaciones.items():
        if tags.get("aeroway") == "aerodrome":
            elementos.append({"type": "relation", "id": rid, "tags": tags, "members": [
                {"type": t, "ref": ref, "role": rol, "geometry": geom(vias[ref][0])}
                for t, ref, rol in miembros if t == "way" and ref in vias]})
    return {"elements": elementos}


def descargar() -> dict:
    elementos, vistos = [], set()
    for icao, nombre, lat, lon in BASES:
        print(f"  {icao} {nombre}...", flush=True)
        respuesta = consultar_overpass(consulta(lat, lon))
        if respuesta is None:
            print("  Overpass no responde: se usa la API de OpenStreetMap por celdas.", flush=True)
            elementos = descargar_api()["elements"]
            break
        for e in respuesta.get("elements", []):
            clave = (e["type"], e["id"])
            if clave not in vistos:
                vistos.add(clave)
                elementos.append(e)
    crudo = {"elements": elementos}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(crudo), encoding="utf-8")
    return crudo


# ------------------------------------------------------------------ geometria local (metros)
class Local:
    """Proyeccion equirectangular alrededor de un punto: suficiente para unos pocos kilometros."""

    def __init__(self, lat0: float, lon0: float):
        self.lat0, self.lon0 = lat0, lon0
        self.kx = 111320.0 * math.cos(math.radians(lat0))
        self.ky = 110574.0

    def a_m(self, lat: float, lon: float) -> tuple[float, float]:
        return ((lon - self.lon0) * self.kx, (lat - self.lat0) * self.ky)

    def a_geo(self, x: float, y: float) -> list[float]:
        return [round(self.lon0 + x / self.kx, 7), round(self.lat0 + y / self.ky, 7)]


def rect(p, q, ancho, loc: Local, extra=0.0) -> list:
    """Rectangulo (anillo GeoJSON) de ancho `ancho` alrededor del segmento p-q (en metros locales)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    largo = math.hypot(dx, dy) or 1.0
    ux, uy = dx / largo, dy / largo
    nx, ny = -uy * ancho / 2, ux * ancho / 2
    a = (p[0] - ux * extra, p[1] - uy * extra)
    b = (q[0] + ux * extra, q[1] + uy * extra)
    anillo = [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]
    return [loc.a_geo(*v) for v in anillo] + [loc.a_geo(*anillo[0])]


def circulo(c, r, loc: Local, n=10) -> list:
    anillo = [loc.a_geo(c[0] + r * math.cos(2 * math.pi * k / n), c[1] + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return anillo + [anillo[0]]


def poligono(anillo_m, loc: Local) -> list:
    pts = [loc.a_geo(*v) for v in anillo_m]
    return pts + [pts[0]]


def en_poligono(x, y, anillo) -> bool:
    dentro = False
    for i in range(len(anillo)):
        (x1, y1), (x2, y2) = anillo[i], anillo[(i + 1) % len(anillo)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            dentro = not dentro
    return dentro


def numero(v: str | None, defecto: float) -> float:
    m = re.match(r"\s*([\d.]+)", v or "")
    try:
        return float(m.group(1)) if m else defecto
    except ValueError:
        return defecto


def rumbo_verdadero(p, q) -> float:
    return math.degrees(math.atan2(q[0] - p[0], q[1] - p[1])) % 360


def designador(rumbo: float) -> str:
    n = round(((rumbo + DECLINACION_OESTE) % 360) / 10) % 36
    return f"{n or 36:02d}"


def feature(tipo: str, geom: dict, **props) -> dict:
    return {"type": "Feature", "geometry": geom, "properties": {"tipo": tipo, **props}}


def poly(anillo) -> dict:
    return {"type": "Polygon", "coordinates": [anillo]}


# ------------------------------------------------------------------ marcas de pista
def marcas_pista(p, q, ancho, loc: Local, base: str) -> list:
    """Marcas pintadas (en metros): bordes, eje discontinuo, umbrales tipo "piano" y zona de toma de contacto."""
    out = []
    largo = math.hypot(q[0] - p[0], q[1] - p[1])
    ux, uy = (q[0] - p[0]) / largo, (q[1] - p[1]) / largo
    nx, ny = -uy, ux
    en = lambda s, t: (p[0] + ux * s + nx * t, p[1] + uy * s + ny * t)  # noqa: E731  s: a lo largo, t: a traves

    def barra(s0, s1, t, w):
        out.append(feature("marca", poly(rect(en(s0, t), en(s1, t), w, loc)), base=base))

    medio = ancho / 2
    # bordes
    barra(0, largo, medio - 1.5, 1.2)
    barra(0, largo, -medio + 1.5, 1.2)
    # umbrales: franjas longitudinales en ambos extremos
    franjas = max(4, min(16, int(ancho / 5.5)))
    paso = (ancho - 6) / franjas
    for extremo in (0, 1):
        s0 = 6 if extremo == 0 else largo - 36
        for k in range(franjas):
            t = -medio + 3 + paso * (k + 0.5)
            if abs(t) < paso * 0.6:
                continue  # hueco central para la numeracion
            barra(s0, s0 + 30, t, paso * 0.55)
    # eje discontinuo (entre las numeraciones)
    s = 130.0
    while s + 30 < largo - 130:
        barra(s, s + 30, 0, 2.5)
        s += 50
    # punto de visada y zona de toma de contacto a ~300 m de cada cabecera
    if largo > 1200:
        for s0 in (300, largo - 345):
            for lado in (1, -1):
                barra(s0, s0 + 45, lado * (medio - 11), 6)
        for s0 in (150, 450, largo - 180, largo - 480):
            for lado in (1, -1):
                barra(s0, s0 + 22, lado * (medio - 11), 2.5)
    return out


# ------------------------------------------------------------------ proceso
def base_mas_cercana(lat, lon):
    return min(BASES, key=lambda b: (b[2] - lat) ** 2 + ((b[3] - lon) * math.cos(math.radians(lat))) ** 2)


def distancia_m(lat1, lon1, lat2, lon2) -> float:
    return math.hypot((lon2 - lon1) * 111320 * math.cos(math.radians(lat1)), (lat2 - lat1) * 110574)


def procesar(crudo: dict) -> dict:
    feats = []
    por_base: dict[str, dict] = {b[0]: {"limites": [], "edificios": [], "pistas": 0} for b in BASES}
    elementos = crudo.get("elements", [])

    # limites de los aerodromos (ways y relaciones)
    for e in elementos:
        tags = e.get("tags", {})
        if tags.get("aeroway") != "aerodrome":
            continue
        anillos = []
        if e["type"] == "way" and e.get("geometry"):
            anillos.append([(g["lon"], g["lat"]) for g in e["geometry"]])
        elif e["type"] == "relation":
            for m in e.get("members", []):
                if m.get("role") == "outer" and m.get("geometry"):
                    anillos.append([(g["lon"], g["lat"]) for g in m["geometry"]])
        for a in anillos:
            lat = sum(p[1] for p in a) / len(a)
            lon = sum(p[0] for p in a) / len(a)
            icao, nombre, blat, blon = base_mas_cercana(lat, lon)
            if distancia_m(lat, lon, blat, blon) > RADIO_EDIFICIOS_M or len(a) < 4:
                continue
            por_base[icao]["limites"].append(a)
            feats.append(feature("aerodromo", poly([[round(x, 7), round(y, 7)] for x, y in a]), base=icao, nombre=nombre))

    for e in elementos:
        if e["type"] not in ("way", "node"):
            continue
        tags = e.get("tags", {})
        tipo = tags.get("aeroway") or ("edificio" if "building" in tags else None)
        if tipo in (None, "aerodrome"):
            continue
        if e["type"] == "node":
            if tipo == "helipad":
                icao, _, blat, blon = base_mas_cercana(e["lat"], e["lon"])
                if distancia_m(e["lat"], e["lon"], blat, blon) > RADIO_PISTAS_M * 1.5:
                    continue
                loc = Local(blat, blon)
                feats.append(feature("helipuerto", poly(circulo(loc.a_m(e["lat"], e["lon"]), 14, loc, 16)), base=icao))
            continue
        geo = e.get("geometry") or []
        if len(geo) < 2:
            continue
        lat = sum(g["lat"] for g in geo) / len(geo)
        lon = sum(g["lon"] for g in geo) / len(geo)
        icao, nombre, blat, blon = base_mas_cercana(lat, lon)
        if distancia_m(lat, lon, blat, blon) > RADIO_PISTAS_M * 1.5:
            continue  # elemento de otro aerodromo que quedo en la cache
        loc = Local(blat, blon)
        pts = [loc.a_m(g["lat"], g["lon"]) for g in geo]
        cerrado = geo[0] == geo[-1] and len(geo) >= 4

        if tipo == "runway" and not cerrado:
            p, q = pts[0], pts[-1]
            ancho = numero(tags.get("width"), ANCHO_PISTA)
            largo = math.hypot(q[0] - p[0], q[1] - p[1])
            if largo < 300:
                continue
            r = rumbo_verdadero(p, q)
            ref = tags.get("ref", "")
            partes = [x.strip() for x in re.split(r"[/-]", ref)] if ref else []
            if len(partes) != 2 or not all(re.match(r"^\d{1,2}[LRC]?$", x) for x in partes):
                partes = [designador(r), designador((r + 180) % 360)]
            # la cabecera A es la del designador menor en rumbo (el que se lee al aterrizar desde p hacia q)
            etiqueta_a, etiqueta_b = designador(r), designador((r + 180) % 360)
            if partes and partes[0][:2].isdigit() and abs(int(partes[0][:2]) - int(etiqueta_a)) <= 2:
                etiqueta_a, etiqueta_b = partes[0], partes[1]
            elif partes and partes[1][:2].isdigit() and abs(int(partes[1][:2]) - int(etiqueta_a)) <= 2:
                etiqueta_a, etiqueta_b = partes[1], partes[0]
            ux, uy = (q[0] - p[0]) / largo, (q[1] - p[1]) / largo
            num_a = loc.a_geo(p[0] + ux * 85, p[1] + uy * 85)
            num_b = loc.a_geo(q[0] - ux * 85, q[1] - uy * 85)
            feats.append(feature(
                "pista", poly(rect(p, q, ancho, loc)), base=icao, ref=f"{etiqueta_a}/{etiqueta_b}", largo_m=round(largo),
                ancho_m=ancho, rumbo=round(r, 1), superficie=tags.get("surface", ""),
                extremos=[loc.a_geo(*p)[::-1], loc.a_geo(*q)[::-1]],
                numeros=[[etiqueta_a, num_a[1], num_a[0], round(r, 1)], [etiqueta_b, num_b[1], num_b[0], round((r + 180) % 360, 1)]],
            ))
            feats.extend(marcas_pista(p, q, ancho, loc, icao))
            por_base[icao]["pistas"] += 1
        elif tipo in ("taxiway", "taxilane") and not cerrado:
            ancho = numero(tags.get("width"), ANCHO_RODAJE if tipo == "taxiway" else 12.0)
            for i in range(len(pts) - 1):
                feats.append(feature("rodaje", poly(rect(pts[i], pts[i + 1], ancho, loc, extra=ancho * 0.1)), base=icao))
            for i in range(1, len(pts) - 1):  # uniones redondeadas en los quiebres
                feats.append(feature("rodaje", poly(circulo(pts[i], ancho / 2, loc, 10)), base=icao))
            feats.append(feature("eje_rodaje", {"type": "LineString", "coordinates": [loc.a_geo(*v) for v in pts]}, base=icao))
        elif tipo in ("apron", "helipad") and cerrado:
            feats.append(feature("plataforma" if tipo == "apron" else "helipuerto", poly(poligono(pts[:-1], loc)), base=icao))
        elif tipo in ("hangar", "edificio", "terminal", "tower", "control_tower") and cerrado:
            niveles = numero(tags.get("building:levels"), 0.0)
            alto = numero(tags.get("height"), niveles * 3.5 if niveles else 0.0)
            clase = "hangar" if tipo == "hangar" or tags.get("building") == "hangar" else (
                "torre" if tipo in ("tower", "control_tower") or tags.get("man_made") == "tower" else "edificio")
            por_base[icao]["edificios"].append(feature(clase, poly(poligono(pts[:-1], loc)), base=icao, alto_m=alto or None,
                                                       centro=[lon, lat], nombre=tags.get("name", "")))

    # edificios: solo los que estan dentro del limite del aerodromo (o a menos de 1,5 km de la pista si no hay limite)
    for icao, datos in por_base.items():
        for f in datos["edificios"]:
            lon, lat = f["properties"].pop("centro")
            if datos["limites"]:
                if not any(en_poligono(lon, lat, a) for a in datos["limites"]):
                    continue
            else:
                b = next(x for x in BASES if x[0] == icao)
                if distancia_m(lat, lon, b[2], b[3]) > 1500:
                    continue
            feats.append(f)

    orden = {"aerodromo": 0, "plataforma": 1, "rodaje": 2, "helipuerto": 3, "pista": 4, "marca": 5, "eje_rodaje": 6,
             "edificio": 7, "hangar": 8, "torre": 9}
    feats.sort(key=lambda f: orden.get(f["properties"]["tipo"], 10))
    resumen = {icao: {"pistas": d["pistas"], "limite": bool(d["limites"])} for icao, d in por_base.items()}
    return {
        "type": "FeatureCollection",
        "name": "aerodromos",
        "fuente": "© colaboradores de OpenStreetMap (ODbL 1.0), https://www.openstreetmap.org/copyright",
        "bases": [{"icao": i, "nombre": n, "lat": la, "lon": lo, **resumen[i]} for i, n, la, lo in BASES],
        "features": feats,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--descargar", action="store_true", help="vuelve a descargar aunque exista la cache")
    ap.add_argument("--api", action="store_true", help="usa directamente la API de OSM (si Overpass no responde)")
    args = ap.parse_args()
    if args.descargar or not CACHE.exists():
        crudo = descargar_api() if args.api else descargar()
        if args.api:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(crudo), encoding="utf-8")
    else:
        crudo = json.loads(CACHE.read_text(encoding="utf-8"))
        # bases agregadas despues de la ultima descarga: se bajan solo esas y se suman a la cache
        faltan = [b[0] for b in BASES if b[0] not in crudo.get("bases_descargadas", [b[0] for b in BASES[:9]])]
        if faltan:
            print(f"  bases nuevas: {', '.join(faltan)}", flush=True)
            nuevo = descargar_api(solo=set(faltan))
            vistos = {(e["type"], e["id"]) for e in crudo["elements"]}
            crudo["elements"] += [e for e in nuevo["elements"] if (e["type"], e["id"]) not in vistos]
            crudo["bases_descargadas"] = sorted(set(crudo.get("bases_descargadas", [b[0] for b in BASES[:9]])) | set(faltan))
            CACHE.write_text(json.dumps(crudo), encoding="utf-8")
    salida = procesar(crudo)
    DESTINO.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cuenta: dict[str, int] = {}
    for f in salida["features"]:
        cuenta[f["properties"]["tipo"]] = cuenta.get(f["properties"]["tipo"], 0) + 1
    print(f"{len(salida['features'])} elementos en {DESTINO} ({DESTINO.stat().st_size // 1024} KB): {cuenta}")
    for b in salida["bases"]:
        print(f"  {b['icao']} {b['nombre']}: {b['pistas']} pista(s), limite {'si' if b['limite'] else 'no'}")


if __name__ == "__main__":
    main()
