"""Genera el plano detallado de cada aerodromo de la capa de bases (pistas, calles de rodaje, plataformas, hangares y
edificios) para verlo en el mapa al acercarse, sin internet: un archivo por aerodromo en
frontend/static/geo/aerodromos/<OACI>.json y el indice frontend/static/geo/aerodromos/indice.json. El navegador
solo descarga el plano de los aerodromos que quedan a la vista al acercarse (ver frontend/static/js/aerodromos.js).

Fuente: OpenStreetMap (https://www.openstreetmap.org), via la API publica Overpass. Licencia ODbL 1.0: uso libre,
incluso offline, citando "(c) colaboradores de OpenStreetMap" (el mapa ya lo muestra al activar la capa).
La imagen satelital offline (Sentinel-2, 10 m/pixel) no alcanza para ver una pista (45 m = 4 pixeles) ni los
hangares; los mosaicos de alta resolucion (Google, Bing, Esri) no permiten guardarse para uso sin conexion.

Aerodromos: todos los de frontend/static/geo/bases_aereas.geojson (las bases de Venezuela, sus vecinos y los ~1 260
de toda America; ver tools/generar_bases_aereas.py). Se ejecuta con internet y es reanudable: la respuesta de cada
aerodromo se guarda en tools/cache/osm_aerodromos/<OACI>.json y no se vuelve a pedir (--descargar la refresca).
Con varios miles de consultas tarda; se respeta a la API publica con una pausa entre consulta y consulta.

Procesa:
  - pistas (aeroway=runway): rectangulo con su ancho real (etiqueta width; 45 m si falta), extremos y numeracion de
    cada cabecera (etiqueta ref o calculada del rumbo magnetico); las marcas pintadas (umbrales, eje, toma de
    contacto, bordes) las dibuja el navegador a partir de los extremos y el ancho;
  - calles de rodaje (taxiway/taxilane): su eje con el ancho (18 m si falta); el navegador lo dibuja a escala;
  - plataformas (apron), helipuertos, hangares y edificios dentro del limite del aerodromo, y el limite.

    backend\\venv\\Scripts\\python tools/preparar_aerodromos.py                 # todos (reanuda donde quedo)
    backend\\venv\\Scripts\\python tools/preparar_aerodromos.py --solo SVBL SKBO # algunos
    backend\\venv\\Scripts\\python tools/preparar_aerodromos.py --sin-descargar  # solo reprocesa la cache
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
BASES_GEOJSON = RAIZ / "frontend" / "static" / "geo" / "bases_aereas.geojson"
DESTINO = RAIZ / "frontend" / "static" / "geo" / "aerodromos"
INDICE = DESTINO / "indice.json"
ANTIGUO = RAIZ / "frontend" / "static" / "geo" / "aerodromos.geojson"  # formato anterior (un solo archivo)
CACHE = RAIZ / "tools" / "cache" / "osm_aerodromos"
CACHE_ANTIGUA = RAIZ / "tools" / "cache" / "osm_aerodromos.json"  # descarga anterior de las 18 bases curadas
# espejos publicos de Overpass, en orden (overpass-api.de a veces corta las consultas grandes)
ESPEJOS = ["https://overpass.kumi.systems/api/interpreter", "https://overpass-api.de/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
LOTE = 15  # aerodromos por consulta: muchas menos consultas que uno por uno
UA = {"User-Agent": "SimuladorFenix/1.0 (educational, offline military academy training tool)"}
PAUSA_S = 1.0
FUENTE = "© colaboradores de OpenStreetMap (ODbL 1.0), https://www.openstreetmap.org/copyright"

RADIO_PISTAS_M = 4500
RADIO_EDIFICIOS_M = 3000
VECINDAD_M = 25000  # aerodromos cercanos entre los que se reparten los elementos descargados
DECLINACION_OESTE = 12.0  # declinacion magnetica aproximada en Venezuela: solo para pistas sin etiqueta ref
ANCHO_PISTA = 45.0
ANCHO_RODAJE = 18.0


def nombre_archivo(icao: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", icao)


CURADAS: set[str] = set()  # bases verificadas a mano (origen "curado"): las unicas de la descarga anterior
# aerodromos que usan las plantillas de escenario aunque no esten en la capa de referencia
EXTRAS = [("SVBI", "Aeropuerto de Barinas", 8.61958, -70.22083)]  # aeropuerto civil (no es base de la AMB)


def cargar_bases() -> list[tuple[str, str, float, float]]:
    """(icao, nombre, lat, lon) de cada aerodromo de la capa de referencia, sin repetir el identificador."""
    datos = json.loads(BASES_GEOJSON.read_text(encoding="utf-8"))
    bases, vistos = [], set()
    for f in datos["features"]:
        p = f["properties"]
        icao = (p.get("icao") or "").strip()
        if not icao or icao in vistos or f["geometry"]["type"] != "Point":
            continue
        vistos.add(icao)
        if p.get("origen") == "curado":
            CURADAS.add(icao)
        lon, lat = f["geometry"]["coordinates"][:2]
        bases.append((icao, p.get("nombre") or icao, float(lat), float(lon)))
    for extra in EXTRAS:
        CURADAS.add(extra[0])  # su plano ya estaba en la descarga anterior
        if extra[0] not in vistos:
            bases.append(extra)
    return bases


# ------------------------------------------------------------------ descarga
def caja_de(lat: float, lon: float) -> str:
    d = RADIO_PISTAS_M / 111000
    dl = d / max(0.2, math.cos(math.radians(lat)))
    return f"({lat - d:.5f},{lon - dl:.5f},{lat + d:.5f},{lon + dl:.5f})"


def consulta(puntos: list[tuple[float, float]]) -> str:
    """Consulta Overpass de uno o varios aerodromos: lo aeronautico en un recuadro de ~9 x 9 km alrededor de cada uno
    y los edificios que caen dentro del limite de algun aerodromo de esos recuadros (no los de la ciudad vecina)."""
    cajas = [caja_de(lat, lon) for lat, lon in puntos]
    limites = "".join(f'way["aeroway"="aerodrome"]{c};relation["aeroway"="aerodrome"]{c};' for c in cajas)
    resto = "".join(f'way["aeroway"]{c};node["aeroway"="helipad"]{c};' for c in cajas)
    return (f'[out:json][timeout:{min(900, 120 + 30 * len(cajas))}];({limites})->.ad;.ad map_to_area->.zona;'
            f'(.ad;{resto}way["building"](area.zona););out geom;')


def espejos_disponibles() -> list[str]:
    """Espejos de Overpass que contestan una consulta minima en 30 s (si estan caidos, no se espera por cada lote)."""
    prueba = urllib.parse.urlencode({"data": "[out:json][timeout:20];node(1);out ids;"}).encode()
    vivos = []
    for url in ESPEJOS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=prueba, headers=UA), timeout=30) as r:
                json.loads(r.read().decode("utf-8"))
            vivos.append(url)
        except Exception as e:  # noqa: BLE001
            print(f"  {url} no responde ({type(e).__name__})", flush=True)
    return vivos


def consultar_overpass(texto: str, espejos: list[str] | None = None) -> dict | None:
    datos = urllib.parse.urlencode({"data": texto}).encode()
    limite = int(re.search(r"\[timeout:(\d+)\]", texto).group(1)) + 60  # lo que el servidor puede tardar, y un margen
    for url in ESPEJOS if espejos is None else espejos:
        for intento in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, data=datos, headers=UA), timeout=limite) as r:
                    respuesta = json.loads(r.read().decode("utf-8"))
                # Overpass responde 200 con un "remark" de error (y datos parciales) si la consulta se corta
                if "error" in (respuesta.get("remark") or "").lower():
                    print(f"    {url}: {respuesta['remark'][:120]}", flush=True)
                    break
                return respuesta
            except urllib.error.HTTPError as e:
                if e.code in (429, 504):  # saturado: se espera y se reintenta
                    time.sleep(20 * (intento + 1))
                    continue
                print(f"    {url}: {e}", flush=True)
                break
            except Exception as e:  # noqa: BLE001
                print(f"    {url}: {e}", flush=True)
                break
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


def descargar_api(lat: float, lon: float) -> dict:
    """Lo mismo que Overpass ("out geom") armado desde la API de OSM, celda por celda, para un aerodromo."""
    nodos, vias, relaciones = {}, {}, {}
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


def elementos_antiguos(lat: float, lon: float) -> list | None:
    """Elementos de la descarga anterior (un solo archivo para las bases curadas) cercanos a ese punto, o None."""
    if not CACHE_ANTIGUA.exists():
        return None
    if not hasattr(elementos_antiguos, "datos"):
        elementos_antiguos.datos = json.loads(CACHE_ANTIGUA.read_text(encoding="utf-8")).get("elements", [])
    cerca = []
    for e in elementos_antiguos.datos:
        c = centro_elemento(e)
        if c and distancia_m(lat, lon, c[0], c[1]) <= RADIO_PISTAS_M * 1.6:
            cerca.append(e)
    return cerca or None


def leer_cache(icao: str) -> dict | None:
    """Respuesta cruda guardada de un aerodromo; las bases curadas toman la de la descarga anterior si no tienen."""
    ruta = CACHE / f"{nombre_archivo(icao)}.json"
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except ValueError:  # quedo a medio escribir (proceso interrumpido): se vuelve a bajar
            ruta.unlink()
    return None


def guardar_cache(icao: str, crudo: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    temporal = CACHE / f"{nombre_archivo(icao)}.json.tmp"
    temporal.write_text(json.dumps({"elements": crudo.get("elements", [])}), encoding="utf-8")
    temporal.replace(CACHE / f"{nombre_archivo(icao)}.json")  # nunca queda un archivo a medias


def repartir(lote: list[tuple], elementos: list) -> None:
    """Guarda en la cache de cada aerodromo del lote los elementos de la respuesta que caen en su recuadro."""
    centros = [(e, centro_elemento(e)) for e in elementos]
    for icao, _, lat, lon in lote:
        guardar_cache(icao, {"elements": [e for e, c in centros if c and distancia_m(lat, lon, c[0], c[1]) <= RADIO_PISTAS_M * 1.6]})


MAX_API_OSM = 10  # la API de OSM no admite descargas masivas: solo se usa para unos pocos aerodromos sueltos


def descargar_lote(lote: list[tuple], espejos: list[str], usar_api: bool) -> int:
    """Baja de una vez el lote; si la consulta falla, la parte en dos (y un aerodromo solo, si se permite, prueba la
    API de OSM). Devuelve cuantos aerodromos quedaron sin descargar (se reintentan en la proxima ejecucion)."""
    respuesta = consultar_overpass(consulta([(b[2], b[3]) for b in lote]), espejos) if espejos else None
    if respuesta is not None:
        repartir(lote, respuesta.get("elements", []))
        time.sleep(PAUSA_S)
        return 0
    if len(lote) > 1 and espejos:
        medio = len(lote) // 2
        return descargar_lote(lote[:medio], espejos, usar_api) + descargar_lote(lote[medio:], espejos, usar_api)
    if not usar_api:
        return len(lote)
    fallidos = 0
    for icao, _, lat, lon in lote:
        try:
            guardar_cache(icao, descargar_api(lat, lon))
        except Exception as e:  # noqa: BLE001
            print(f"    {icao}: sin respuesta de la API de OSM ({e})", flush=True)
            fallidos += 1
    return fallidos


def descargar(pendientes: list[tuple], api: bool) -> int:
    """Descarga por lotes de aerodromos cercanos entre si (consultas mas chicas que si se mezclaran continentes).
    Si Overpass esta caido no espera por cada lote: avisa y deja todo para la proxima ejecucion."""
    usar_api = api or len(pendientes) <= MAX_API_OSM
    espejos = [] if api else espejos_disponibles()
    if not espejos and not usar_api:
        print(f"Ningun servidor Overpass responde ahora: no se descargo nada. Vuelva a intentarlo mas tarde "
              f"(quedan {len(pendientes)} aerodromos; el script retoma donde quedo).", flush=True)
        return len(pendientes)
    pendientes = sorted(pendientes, key=lambda b: (int((b[2] + 90) // 4), b[3] if int((b[2] + 90) // 4) % 2 else -b[3]))
    lotes = [pendientes[i:i + LOTE] for i in range(0, len(pendientes), LOTE)]
    fallidos = 0
    for k, lote in enumerate(lotes, 1):
        inicio = time.time()
        fallo = descargar_lote(lote, espejos, usar_api)
        fallidos += fallo
        print(f"  lote {k}/{len(lotes)}: {', '.join(b[0] for b in lote)} ({time.time() - inicio:.0f} s"
              + (f", {fallo} sin descargar)" if fallo else ")"), flush=True)
        if fallo == len(lote) and espejos:  # el lote entero fallo: puede que Overpass se haya caido a mitad
            espejos = espejos_disponibles()
            if not espejos and not usar_api:
                restantes = sum(len(x) for x in lotes[k:])
                print(f"Overpass dejo de responder: quedan {restantes + fallidos} aerodromos para la proxima ejecucion.", flush=True)
                return fallidos + restantes
    return fallidos


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


def distancia_m(lat1, lon1, lat2, lon2) -> float:
    return math.hypot((lon2 - lon1) * 111320 * math.cos(math.radians(lat1)), (lat2 - lat1) * 110574)


def centro_elemento(e) -> tuple[float, float] | None:
    if e["type"] == "node":
        return e["lat"], e["lon"]
    pts = e.get("geometry") or [g for m in e.get("members", []) for g in (m.get("geometry") or [])]
    if not pts:
        return None
    return sum(g["lat"] for g in pts) / len(pts), sum(g["lon"] for g in pts) / len(pts)


# ------------------------------------------------------------------ proceso de un aerodromo
def procesar(base: tuple, vecinos: list[tuple], crudo: dict) -> dict:
    """Plano de `base` con los elementos de su descarga que le son mas cercanos que a cualquier `vecino` (los de un
    aerodromo vecino que caen en el mismo recuadro van al archivo de ese otro aerodromo)."""
    icao, nombre, blat, blon = base
    candidatas = [base] + [v for v in vecinos if v[0] != icao]

    def es_mio(lat, lon, radio):
        mas_cerca = min(candidatas, key=lambda b: (b[2] - lat) ** 2 + ((b[3] - lon) * math.cos(math.radians(lat))) ** 2)
        return mas_cerca[0] == icao and distancia_m(lat, lon, blat, blon) <= radio

    loc = Local(blat, blon)
    feats, limites, edificios, pistas = [], [], [], 0
    elementos = crudo.get("elements", [])

    # limites del aerodromo (ways y relaciones)
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
            if len(a) < 4 or not es_mio(lat, lon, RADIO_EDIFICIOS_M):
                continue
            limites.append(a)
            feats.append(feature("aerodromo", poly([[round(x, 7), round(y, 7)] for x, y in a]), base=icao, nombre=nombre))

    for e in elementos:
        if e["type"] not in ("way", "node"):
            continue
        tags = e.get("tags", {})
        tipo = tags.get("aeroway") or ("edificio" if "building" in tags else None)
        if tipo in (None, "aerodrome"):
            continue
        if e["type"] == "node":
            if tipo == "helipad" and es_mio(e["lat"], e["lon"], RADIO_PISTAS_M * 1.5):
                feats.append(feature("helipuerto", poly(circulo(loc.a_m(e["lat"], e["lon"]), 14, loc, 16)), base=icao))
            continue
        geo = e.get("geometry") or []
        if len(geo) < 2:
            continue
        lat = sum(g["lat"] for g in geo) / len(geo)
        lon = sum(g["lon"] for g in geo) / len(geo)
        if not es_mio(lat, lon, RADIO_PISTAS_M * 1.5):
            continue
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
            pistas += 1
        elif tipo in ("taxiway", "taxilane") and not cerrado:
            ancho = numero(tags.get("width"), ANCHO_RODAJE if tipo == "taxiway" else 12.0)
            feats.append(feature("rodaje", {"type": "LineString", "coordinates": [loc.a_geo(*v) for v in pts]},
                                 base=icao, ancho_m=ancho))
        elif tipo in ("apron", "helipad") and cerrado:
            feats.append(feature("plataforma" if tipo == "apron" else "helipuerto", poly(poligono(pts[:-1], loc)), base=icao))
        elif tipo in ("hangar", "edificio", "terminal", "tower", "control_tower") and cerrado:
            niveles = numero(tags.get("building:levels"), 0.0)
            alto = numero(tags.get("height"), niveles * 3.5 if niveles else 0.0)
            clase = "hangar" if tipo == "hangar" or tags.get("building") == "hangar" else (
                "torre" if tipo in ("tower", "control_tower") or tags.get("man_made") == "tower" else "edificio")
            edificios.append((lon, lat, feature(clase, poly(poligono(pts[:-1], loc)), base=icao, alto_m=alto or None,
                                                nombre=tags.get("name", ""))))

    # edificios: solo los que estan dentro del limite del aerodromo (o a menos de 1,5 km del punto si no hay limite)
    for lon, lat, f in edificios:
        if limites:
            if not any(en_poligono(lon, lat, a) for a in limites):
                continue
        elif distancia_m(lat, lon, blat, blon) > 1500:
            continue
        feats.append(f)

    orden = {"aerodromo": 0, "plataforma": 1, "rodaje": 2, "helipuerto": 3, "pista": 4, "edificio": 7, "hangar": 8, "torre": 9}
    feats.sort(key=lambda f: orden.get(f["properties"]["tipo"], 10))
    return {
        "type": "FeatureCollection",
        "name": f"aerodromo {icao}",
        "fuente": FUENTE,
        "bases": [{"icao": icao, "nombre": nombre, "lat": blat, "lon": blon, "pistas": pistas, "limite": bool(limites)}],
        "features": feats,
    }


def vecinos_de(bases: list[tuple]) -> dict[str, list[tuple]]:
    """Aerodromos a menos de VECINDAD_M de cada uno (rejilla de 0,5 grados para no comparar todos con todos)."""
    celdas: dict[tuple[int, int], list[tuple]] = {}
    for b in bases:
        celdas.setdefault((int(b[2] // 0.5), int(b[3] // 0.5)), []).append(b)
    vecinos = {}
    for b in bases:
        ci, cj = int(b[2] // 0.5), int(b[3] // 0.5)
        cerca = [o for di in (-1, 0, 1) for dj in (-1, 0, 1) for o in celdas.get((ci + di, cj + dj), [])]
        vecinos[b[0]] = [o for o in cerca if o[0] != b[0] and distancia_m(b[2], b[3], o[2], o[3]) <= VECINDAD_M]
    return vecinos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--solo", nargs="+", metavar="OACI", help="solo estos aerodromos")
    ap.add_argument("--descargar", action="store_true", help="vuelve a descargar aunque exista la cache")
    ap.add_argument("--sin-descargar", action="store_true", help="no pide nada a internet: procesa solo lo que hay en cache")
    ap.add_argument("--api", action="store_true", help="usa directamente la API de OSM (si Overpass no responde)")
    args = ap.parse_args()

    bases = cargar_bases()
    vecinos = vecinos_de(bases)
    elegidas = [b for b in bases if not args.solo or b[0] in set(args.solo)]
    DESTINO.mkdir(parents=True, exist_ok=True)
    indice_previo = {b["icao"]: b for b in json.loads(INDICE.read_text(encoding="utf-8"))["bases"]} if INDICE.exists() else {}

    # las bases curadas reusan la descarga anterior (un solo archivo) si todavia no tienen la suya
    for icao, _, lat, lon in elegidas:
        if icao in CURADAS and not args.descargar and leer_cache(icao) is None:
            viejos = elementos_antiguos(lat, lon)
            if viejos is not None:
                guardar_cache(icao, {"elements": viejos})
    sin_datos = 0
    if not args.sin_descargar:
        pendientes = [b for b in elegidas if args.descargar or leer_cache(b[0]) is None]
        if pendientes:
            print(f"Descargando {len(pendientes)} aerodromos de OpenStreetMap en lotes de {LOTE}...", flush=True)
            sin_datos = descargar(pendientes, args.api)

    for base in elegidas:
        icao = base[0]
        crudo = leer_cache(icao)
        if crudo is None:
            continue
        plano = procesar(base, vecinos[icao], crudo)
        resumen = plano["bases"][0]
        ruta = DESTINO / f"{nombre_archivo(icao)}.json"
        if resumen["pistas"] or resumen["limite"]:
            ruta.write_text(json.dumps(plano, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            indice_previo[icao] = {**resumen, "archivo": ruta.name, "kb": max(1, ruta.stat().st_size // 1024)}
        else:  # OSM no tiene pistas ni limite de este aerodromo: queda sin plano (solo el icono)
            ruta.unlink(missing_ok=True)
            indice_previo.pop(icao, None)

    INDICE.write_text(json.dumps({"fuente": FUENTE, "bases": sorted(indice_previo.values(), key=lambda b: b["icao"])},
                                 ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ANTIGUO.unlink(missing_ok=True)
    total = sum(p.stat().st_size for p in DESTINO.glob("*.json"))
    print(f"{len(indice_previo)} aerodromos con plano en {DESTINO} ({total // 1024} KB)"
          + (f"; {sin_datos} sin respuesta (se reintentan en la proxima ejecucion)" if sin_datos else ""))


if __name__ == "__main__":
    main()
