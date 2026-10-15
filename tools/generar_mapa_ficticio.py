"""Mapa FICTICIO para ejercicios que no involucran a ningun pais real: la region "teatro_ficticio", con dos
estados inventados, la Republica de Valdoria (al oeste, bando azul por defecto) y la Republica de Ostrania (al
este, bando rojo), en una masa de tierra del tamaño de un pais con todo lo que el motor usa de un mapa real:

  - relieve: una cordillera alta al oeste, una serrania costera al norte, un macizo con mesetas al sureste, llanos
    en el centro, costas con golfos, penínsulas e islas y una plataforma continental;
  - rios que nacen en las montañas y bajan por el relieve hasta el mar (calculados sobre la elevacion), un lago
    natural y embalses con su represa;
  - cobertura: bosques, sabanas, pantanos en las zonas bajas y los deltas, ciudades;
  - carreteras troncales y secundarias entre las ciudades (por el camino mas barato sobre el terreno, con puentes
    donde cruzan los rios) y pasos de frontera;
  - frontera, provincias, ciudades con poblacion, infraestructura (centrales, refinerias, comunicaciones, puentes)
    y una plantilla de ejercicio lista para usar.

Se ubica en pleno Atlantico (6 a 12,5 grados norte, 27,5 a 20 oeste), donde no hay tierra real ni otra region del
simulador, con la misma resolucion que la region de Venezuela (zoom 9, ~300 m por pixel). No descarga nada: todo
sale de una semilla, asi que el resultado es siempre el mismo. Genera lo mismo que tools/preparar_terreno.py:

  frontend/static/tiles/teatro_ficticio/{z}/{x}/{y}.jpg       relieve coloreado por clase de terreno (zooms 5 a 9)
  frontend/static/tiles_sat/teatro_ficticio/{z}/{x}/{y}.jpg   vista "satelital" sintetica (zooms 5 a 10)
  frontend/static/geo/teatro_ficticio/*.geojson               fronteras, provincias, rios, lagos, ciudades, carreteras
  frontend/static/geo/teatro_ficticio/infraestructura.json    centrales, refinerias, comunicaciones y puentes
  backend/data/terreno/teatro_ficticio/                       grillas del motor (clases, alturas, vias) y meta.json
  backend/data/plantillas_sistema/teatro_ficticio.json        plantilla "Valdoria contra Ostrania"

    backend\\venv\\Scripts\\python tools/generar_mapa_ficticio.py
"""

import argparse
import heapq
import json
import math
import shutil
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import preparar_terreno as pt  # noqa: E402
from preparar_vias import simplificar  # noqa: E402

RAIZ = AQUI.parent
ID = "teatro_ficticio"
REG = pt.Region(ID, "Teatro ficticio (Valdoria y Ostrania)", (-27.5, 6.0, -20.0, 12.5), 9, 5, "10m", 0)
TILES_SAT = RAIZ / "frontend" / "static" / "tiles_sat"
GEO = RAIZ / "frontend" / "static" / "geo" / ID
DATOS = RAIZ / "backend" / "data" / "terreno" / ID
PLANTILLAS = RAIZ / "backend" / "data" / "plantillas_sistema"
SEMILLA = 20261015
F = 4  # factor de la grilla gruesa (hidrologia y caminos): ~1,2 km por celda
FUENTE = "Mapa ficticio generado por S.I.E.T.E. (tools/generar_mapa_ficticio.py): no representa ningún país real"

PAISES = {
    "valdoria": {"nombre": "República de Valdoria", "bando": "azul"},
    "ostrania": {"nombre": "República de Ostrania", "bando": "rojo"},
}
# ciudades: (nombre, pais, peso) — el peso ordena la poblacion; la capital es la primera de cada pais
NOMBRES_CIUDADES = {
    "valdoria": ["Valdora", "Puerto Albán", "San Telmo", "Rocaverde", "Las Moras", "Villa Esmeralda", "Ciudad Arenas",
                 "Montecal", "Río Claro", "El Pinar", "Santa Irene", "Altamesa", "La Candela", "Puerto Sereno"],
    "ostrania": ["Nueva Ostria", "Puerto Varela", "Tierra Roja", "San Fermín", "Las Dunas", "Monteoscuro", "Villa Oriente",
                 "Ciudad Cobre", "Los Álamos", "Santa Brígida", "El Mirador", "Campo Alegre", "Puerto Lince", "Altavista"],
}
NOMBRES_RIOS = ["Río Aldana", "Río Verdal", "Río Caraño", "Río Toroya", "Río Mirana", "Río Saltén", "Río Ostral",
                "Río Barcen", "Río Lumes", "Río Quebrado"]
NOMBRES_EMBALSES = ["Embalse Las Piedras", "Embalse Coroma", "Embalse Alto Tirel"]
NOMBRES_LAGOS = ["Lago Varena", "Laguna de Sierra Negra", "Laguna Clara"]


# ============================================================================ utilidades
def ruido(rng, forma, escala_px, octavas=5, persistencia=0.5):
    """Ruido fractal suave (suma de octavas de valores al azar interpolados), media 0 y desvio 1."""
    h, w = forma
    total = np.zeros(forma, np.float32)
    amp = 1.0
    for o in range(octavas):
        paso = max(3.0, escala_px / 2 ** o)
        gh, gw = int(math.ceil(h / paso)) + 2, int(math.ceil(w / paso)) + 2
        g = rng.standard_normal((gh, gw)).astype(np.float32)
        up = ndimage.zoom(g, (h / gh, w / gw), order=3, mode="reflect")[:h, :w]
        if up.shape != forma:
            up = np.pad(up, ((0, h - up.shape[0]), (0, w - up.shape[1])), mode="edge")
        total += amp * up
        amp *= persistencia
    return (total - total.mean()) / (total.std() + 1e-9)


def agrandar(a, forma, orden=1):
    """Lleva una grilla gruesa a la forma de la fina (interpolada)."""
    up = ndimage.zoom(a, (forma[0] / a.shape[0], forma[1] / a.shape[1]), order=orden)
    out = np.zeros(forma, up.dtype)
    out[:min(forma[0], up.shape[0]), :min(forma[1], up.shape[1])] = up[:forma[0], :forma[1]]
    return out


def reducir(a, f, modo="media"):
    h, w = a.shape[0] // f, a.shape[1] // f
    b = a[:h * f, :w * f].reshape(h, f, w, f)
    return b.mean(axis=(1, 3)) if modo == "media" else (b.max(axis=(1, 3)) if modo == "max" else b.min(axis=(1, 3)))


def chaikin(pts, vueltas=2, cerrada=False):
    for _ in range(vueltas):
        if len(pts) < 3:
            return pts
        nuevos = [] if cerrada else [pts[0]]
        rango = range(len(pts)) if cerrada else range(len(pts) - 1)
        for i in rango:
            a, b = pts[i], pts[(i + 1) % len(pts)]
            nuevos.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
            nuevos.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
        if not cerrada:
            nuevos.append(pts[-1])
        pts = nuevos
    return pts


# segmentos de cada caso de "marching squares" (bits: arriba-izq 8, arriba-der 4, abajo-der 2, abajo-izq 1)
_BORDES = {"t": (1, 0), "r": (2, 1), "b": (1, 2), "l": (0, 1)}  # en medios pixeles desde la esquina de la celda
_CASOS = {1: [("l", "b")], 2: [("b", "r")], 3: [("l", "r")], 4: [("t", "r")], 5: [("l", "t"), ("b", "r")],
          6: [("t", "b")], 7: [("l", "t")], 8: [("l", "t")], 9: [("t", "b")], 10: [("t", "r"), ("l", "b")],
          11: [("t", "r")], 12: [("l", "r")], 13: [("b", "r")], 14: [("l", "b")]}


def contornos(mascara, minimo=8):
    """Polilineas (coordenadas de pixel, x hacia la derecha e y hacia abajo) del borde de una mascara."""
    m = np.pad(mascara.astype(np.uint8), 1)
    caso = m[:-1, :-1] * 8 + m[:-1, 1:] * 4 + m[1:, 1:] * 2 + m[1:, :-1]
    vecinos: dict = {}
    ys, xs = np.nonzero((caso > 0) & (caso < 15))
    for y, x, c in zip(ys.tolist(), xs.tolist(), caso[ys, xs].tolist()):
        for a, b in _CASOS[c]:
            pa = (2 * x + _BORDES[a][0], 2 * y + _BORDES[a][1])
            pb = (2 * x + _BORDES[b][0], 2 * y + _BORDES[b][1])
            vecinos.setdefault(pa, []).append(pb)
            vecinos.setdefault(pb, []).append(pa)
    usados = set()
    lineas = []
    for inicio in list(vecinos):
        if inicio in usados:
            continue
        cadena = [inicio]
        usados.add(inicio)
        actual = inicio
        while True:
            sig = next((p for p in vecinos[actual] if p not in usados), None)
            if sig is None:
                break
            usados.add(sig)
            cadena.append(sig)
            actual = sig
        if len(cadena) >= minimo:
            # medios pixeles del recuadro con borde -> pixeles de la mascara (centro del pixel = entero)
            lineas.append([(px / 2 - 1.0, py / 2 - 1.0) for px, py in cadena])
    return lineas


class Proyeccion:
    """Pixeles de la grilla fina (zoom nativo) <-> longitud y latitud."""

    def __init__(self, xa, ya, z):
        self.xa, self.ya, self.n = xa, ya, 2 ** z * 256

    def lonlat(self, x, y):
        gx, gy = self.xa * 256 + x + 0.5, self.ya * 256 + y + 0.5
        lon = gx / self.n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * gy / self.n))))
        return lon, lat

    def pixel(self, lon, lat):
        x, y = pt.px(lon, lat, self.xa, self.ya, REG.z)
        return x - 0.5, y - 0.5


# ============================================================================ generacion
class Mapa:
    def __init__(self, semilla=SEMILLA):
        self.rng = np.random.default_rng(semilla)
        xa, ya, xb, yb = REG.teselas()
        self.xa, self.ya = xa, ya
        self.W, self.H = (xb - xa + 1) * 256, (yb - ya + 1) * 256
        self.proy = Proyeccion(xa, ya, REG.z)
        lat_fila = pt.lat_de_fila(ya, self.H, REG.z)
        self.m_px = (156543.03392 * np.cos(np.radians(lat_fila)) / 2 ** REG.z).astype(np.float32)  # m por pixel, por fila
        self.km_px = float(self.m_px.mean() / 1000.0)
        print(f"Grilla {self.W} x {self.H} pixeles (~{self.km_px * 1000:.0f} m/pixel), {self.W // 256 * self.H // 256} teselas", flush=True)

    # ---------------------------------------------------------------- tierra, paises y relieve
    def tierra(self):
        h, w = self.H // 2, self.W // 2  # el relieve se arma a media resolucion y se lleva a la fina
        v, u = np.mgrid[0:h, 0:w].astype(np.float32)
        u, v = u / w, v / h
        d = np.sqrt(((u - 0.5) / 0.42) ** 2 + ((v - 0.5) / 0.38) ** 2)
        campo = (1.0 - d) * 1.25 + 0.45 * ruido(self.rng, (h, w), 260, 6, 0.55)
        # mar abierto en todo el contorno del recuadro: la tierra nunca queda cortada por el borde del mapa
        borde = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))
        campo -= 3.0 * np.clip((0.08 - borde) / 0.08, 0, 1)
        umbral = np.quantile(campo, 1 - 0.50)  # la mitad del recuadro es tierra
        tierra = campo > umbral
        etiquetas, n = ndimage.label(tierra)
        tam = ndimage.sum(tierra, etiquetas, range(1, n + 1))
        principal = int(np.argmax(tam)) + 1
        guardar = [i + 1 for i, t in enumerate(tam) if i + 1 == principal or t >= 900]  # islas de mas de ~300 km2
        tierra = np.isin(etiquetas, guardar)
        tierra = ndimage.binary_fill_holes(tierra)
        self.u, self.v, self.h2, self.w2 = u, v, h, w
        self.tierra2 = tierra
        self.principal2 = etiquetas == principal

    def relieve(self):
        h, w, u, v = self.h2, self.w2, self.u, self.v
        tierra = self.tierra2
        km2 = self.km_px * 2  # km por pixel de la media resolucion
        dcosta = ndimage.distance_transform_edt(tierra) * km2
        dmar = ndimage.distance_transform_edt(~tierra) * km2
        rng = self.rng
        n1 = ruido(rng, (h, w), 180, 6)
        rid = 1.0 - np.abs(ruido(rng, (h, w), 70, 5, 0.55))  # ruido "de crestas"
        # tierras bajas que suben siempre tierra adentro (asi todo drena al mar) con ondulaciones suaves
        elev = 8.0 + np.minimum(dcosta, 150) * 2.4 + 45.0 * n1 * np.clip(dcosta / 30.0, 0, 1)
        llanos = np.exp(-(((u - 0.52) / 0.16) ** 2 + ((v - 0.56) / 0.17) ** 2))
        montes = np.zeros_like(elev)

        def cordillera(puntos, alto, ancho_km):
            img = Image.new("L", (w, h), 0)
            ImageDraw.Draw(img).line([(x * w, y * h) for x, y in puntos], fill=1, width=3)
            dist = ndimage.distance_transform_edt(np.asarray(img) == 0) * km2
            return alto * np.exp(-(dist / ancho_km) ** 2) * (0.55 + 0.45 * rid) * (0.85 + 0.25 * n1)

        # cordillera occidental (alta), serrania costera del norte y una sierra interior al este
        montes += cordillera([(0.16, 0.86), (0.20, 0.68), (0.25, 0.52), (0.30, 0.38), (0.38, 0.27)], 3600, 38)
        montes += cordillera([(0.40, 0.22), (0.52, 0.19), (0.63, 0.21), (0.74, 0.25)], 1900, 22)
        montes += cordillera([(0.66, 0.42), (0.74, 0.50), (0.80, 0.58)], 1300, 18)
        # macizo del sureste: mesetas escalonadas con escarpes (como tepuyes)
        dm = np.sqrt(((u - 0.70) / 0.17) ** 2 + ((v - 0.76) / 0.13) ** 2)
        meseta = np.clip((1.0 - dm) * 3.0, 0, 1)
        escalones = np.floor((meseta * 3 + 0.4 * ruido(rng, (h, w), 50, 4)).clip(0, 3)) / 3
        montes += 1250 * escalones * meseta + 250 * meseta
        # los llanos del centro quedan sin montañas y con la pendiente suave hacia la costa
        elev = elev * (1 - 0.45 * llanos) + montes * (1 - llanos)
        # cuenca del lago natural (entre la cordillera y la serrania)
        dl = np.sqrt(((u - 0.39) / 0.035) ** 2 + ((v - 0.36) / 0.022) ** 2)
        elev -= 120 * np.clip(1 - dl, 0, 1) ** 1.5
        # la tierra se adelgaza hacia la costa; el mar baja con la plataforma continental
        elev = np.where(tierra, np.maximum(elev * np.clip(dcosta / 6.0, 0.15, 1.0), 2.0), -12.0 - dmar * 18.0)
        elev = np.where(tierra, elev, np.maximum(elev, -3500.0))
        self.elev2 = elev.astype(np.float32)
        self.dcosta2 = dcosta
        # paises: frontera ondulada de norte a sur
        ondas = ruido(rng, (h, 8), 260, 4, 0.45)[:, :1]  # solo depende de la latitud: una sola linea de norte a sur
        borde = 0.52 + 0.035 * np.sin(v * 6.0 + 1.3) + 0.03 * ondas
        self.pais2 = np.where(u < borde, 0, 1).astype(np.uint8)  # 0 Valdoria (oeste), 1 Ostrania (este)

    # ---------------------------------------------------------------- hidrologia (grilla gruesa)
    def hidrologia(self):
        fino_tierra = agrandar(self.tierra2.astype(np.float32), (self.H, self.W)) > 0.5
        self.elev = agrandar(self.elev2, (self.H, self.W), orden=1)
        self.tierra = fino_tierra
        self.pais = agrandar(self.pais2, (self.H, self.W), orden=0)
        ec = reducir(self.elev, F)
        tc = reducir(self.tierra.astype(np.float32), F) > 0.5
        h, w = ec.shape
        rugosidad = 9.0 * ruido(np.random.default_rng(SEMILLA + 7), (h, w), 9, 3, 0.5)
        plano = (ec + rugosidad * tc).ravel().astype(np.float64).copy()
        rec = np.full(h * w, -1, np.int64)
        visto = (~tc).ravel().copy()
        borde = (~tc) & ndimage.binary_dilation(tc)
        monton = [(0.0, int(i)) for i in np.flatnonzero(borde)]
        heapq.heapify(monton)
        orden = []
        vec = [(-1, -1, 1.414), (-1, 0, 1.0), (-1, 1, 1.414), (0, -1, 1.0), (0, 1, 1.0), (1, -1, 1.414), (1, 0, 1.0), (1, 1, 1.414)]
        while monton:
            e, c = heapq.heappop(monton)
            orden.append(c)
            r, k = divmod(c, w)
            for dr, dk, dd in vec:
                rr, kk = r + dr, k + dk
                if 0 <= rr < h and 0 <= kk < w:
                    n = rr * w + kk
                    if not visto[n]:
                        visto[n] = True
                        plano[n] = max(plano[n], e + 0.001 * dd)
                        rec[n] = c
                        heapq.heappush(monton, (plano[n], n))
        area = (self.km_px * F) ** 2
        acc = np.where(tc.ravel(), area, 0.0)
        for c in reversed(orden):
            r_ = rec[c]
            if r_ >= 0:
                acc[r_] += acc[c]
        self.hc, self.wc = h, w
        self.ec, self.tc = ec, tc
        self.relleno = plano.reshape(h, w)
        self.rec, self.acc, self.orden = rec, acc, np.array(orden, np.int64)
        print(f"Drenaje: {len(orden)} celdas; cuenca mayor {acc.max():,.0f} km2", flush=True)

    def aguas_arriba(self, celda):
        arriba = np.zeros(self.hc * self.wc, bool)
        arriba[celda] = True
        rec = self.rec
        for c in self.orden:  # el orden del relleno pone a cada celda despues de la que la recibe
            r_ = rec[c]
            if r_ >= 0 and arriba[r_]:
                arriba[c] = True
        return arriba.reshape(self.hc, self.wc)

    def lagos_y_embalses(self):
        """Lago natural (la cuenca rellena mas profunda) y embalses detras de represas en rios de montaña."""
        prof = (self.relleno - self.ec) * self.tc
        etiquetas, n = ndimage.label(prof > 4.0)
        tam = ndimage.sum(np.ones_like(prof), etiquetas, range(1, n + 1)) if n else []
        lagos = []
        for i in np.argsort(tam)[::-1]:
            if len(lagos) == 2:
                break
            if 12 <= tam[i] <= 400:  # una cuenca cerrada enorme no es un lago: los rios la atraviesan
                lagos.append(etiquetas == i + 1)
        self.lagos_c = lagos
        # represas: rios grandes entre 250 y 1100 m, lejos entre si
        acc = self.acc.reshape(self.hc, self.wc)
        cand = np.flatnonzero(((acc > 900) & (acc < 9000) & (self.ec > 250) & (self.ec < 1100) & self.tc).ravel())
        self.rng.shuffle(cand)
        represas, embalses = [], []
        yy, xx = np.mgrid[0:self.hc, 0:self.wc]
        probadas = 0
        for c in cand:
            r, k = divmod(int(c), self.wc)
            if any(math.hypot(r - rr, k - kk) < 60 for rr, kk in represas):
                continue
            probadas += 1
            if probadas > 60:
                break
            arriba = self.aguas_arriba(int(c))
            cerca = np.hypot(yy - r, xx - k) <= 28
            vaso = arriba & cerca & (self.relleno <= self.relleno[r, k] + 45)
            etiq, _ = ndimage.label(vaso)
            vaso = etiq == etiq[r, k] if etiq[r, k] else vaso
            if 25 <= vaso.sum() <= 260:
                represas.append((r, k))
                embalses.append(vaso)
            if len(represas) == 3:
                break
        self.represas, self.embalses_c = represas, embalses
        print(f"Lagos naturales: {len(lagos)}; embalses: {len(embalses)}", flush=True)

    def rios(self):
        acc = self.acc
        umbral = 450.0  # km2 de cuenca para que haya un rio visible
        es_rio = (acc >= umbral) & self.tc.ravel()
        tiene_afluente = np.zeros_like(es_rio)
        receptores = self.rec[es_rio]
        tiene_afluente[receptores[receptores >= 0]] = True
        cabeceras = np.flatnonzero(es_rio & ~tiene_afluente)
        visitado = np.zeros_like(es_rio)
        tramos = []
        for c0 in sorted(cabeceras.tolist(), key=lambda c: -acc[c]):
            camino = [c0]
            c = c0
            visitado[c] = True
            while True:
                r_ = self.rec[c]
                if r_ < 0:
                    break
                camino.append(int(r_))
                if visitado[r_] or not self.tc.ravel()[r_]:
                    break
                visitado[r_] = True
                c = int(r_)
            if len(camino) >= 3:
                tramos.append(camino)
        self.tramos = tramos
        # nombre de las cuencas mayores: el tramo principal de cada desembocadura grande
        salidas = {}
        for t in tramos:
            fin = t[-1]
            salidas.setdefault(fin, []).append(t)
        grandes = sorted(salidas, key=lambda s: -acc[s])
        self.nombre_tramo = {}
        for i, s in enumerate(grandes[:len(NOMBRES_RIOS)]):
            principal = max(salidas[s], key=len)
            self.nombre_tramo[id(principal)] = NOMBRES_RIOS[i]
        print(f"Rios: {len(tramos)} tramos", flush=True)

    # ---------------------------------------------------------------- cobertura y clases
    def clases(self):
        H, W = self.H, self.W
        elev = self.elev
        gy, gx = np.gradient(elev)
        pm = self.m_px[:, None]
        self.dzdx, self.dzdy = gx / pm, -gy / pm
        pendiente = np.degrees(np.arctan(np.hypot(self.dzdx, self.dzdy)))
        rng = self.rng
        n_bosque = agrandar(ruido(rng, (H // 4, W // 4), 60, 5), (H, W))
        n_pant = agrandar(ruido(rng, (H // 4, W // 4), 40, 4), (H, W))
        v = np.linspace(0, 1, H)[:, None]
        u = np.linspace(0, 1, W)[None, :]
        humedad = 0.35 * n_bosque + 0.9 * (0.6 * v + 0.4 * u) - 0.25 * np.exp(-(((u - 0.52) / 0.18) ** 2 + ((v - 0.55) / 0.2) ** 2))
        clases = np.full((H, W), pt.LLANO, np.uint8)
        clases[(humedad > 0.62) & (elev < 2800)] = pt.BOSQUE
        dcosta = agrandar(self.dcosta2.astype(np.float32), (H, W))
        bajo = (elev < 30) & (dcosta < 35) & (n_pant > 0.2)
        clases[bajo & self.tierra] = pt.PANTANO
        clases[(elev >= 1500) | (pendiente >= 9.0)] = pt.MONTANA
        # agua: mar, lagos y embalses (de la grilla gruesa a la fina, con el borde suavizado)
        agua_c = ~self.tc
        for m in self.lagos_c + self.embalses_c:
            agua_c = agua_c | m
        interior = np.zeros_like(self.tc)
        for m in self.lagos_c + self.embalses_c:
            interior |= m
        interior_f = agrandar(ndimage.gaussian_filter(interior.astype(np.float32), 0.8), (H, W)) > 0.45
        self.interior_f = interior_f
        agua = ~self.tierra | interior_f
        # rios: lineas sobre la grilla fina, mas anchas cuanto mayor la cuenca; un campo de deformacion suave y continuo
        # los hace serpentear sin separar a los afluentes del rio al que llegan
        rng_d = np.random.default_rng(SEMILLA + 9)
        dx = ruido(rng_d, (self.hc, self.wc), 7, 3, 0.55) * 2.2 * F
        dy = ruido(rng_d, (self.hc, self.wc), 7, 3, 0.55) * 2.2 * F

        def deformar(pts):
            salida = []
            for x, y in pts:
                k = min(self.wc - 1, max(0, int(x / F)))
                r = min(self.hc - 1, max(0, int(y / F)))
                salida.append((x + float(dx[r, k]), y + float(dy[r, k])))
            return salida
        img = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(img)
        self.rios_px = []
        for t in self.tramos:
            pts = [((c % self.wc) * F + F / 2, (c // self.wc) * F + F / 2) for c in t]
            pts = chaikin(deformar(chaikin(pts, 2)), 2)
            a = self.acc[t[-2]] if len(t) > 1 else self.acc[t[0]]
            ancho = 1 if a < 3000 else 2 if a < 15000 else 3
            d.line(pts, fill=1, width=ancho)
            self.rios_px.append((t, pts, a))
        rio = np.asarray(img, bool) & ~agua
        clases[rio] = pt.RIO
        # ciudades: manchas urbanas
        urb = Image.new("L", (W, H), 0)
        du = ImageDraw.Draw(urb)
        for c in self.ciudades:
            x, y = c["px"]
            r = max(4.0, min(28.0, 7.0 * math.sqrt(c["pop"] / 1e6) * 1000 / (self.km_px * 1000) * 1.2))
            du.ellipse([x - r, y - r, x + r, y + r], fill=1)
        clases[np.asarray(urb, bool) & ~agua] = pt.URBANO
        clases[agua] = pt.AGUA
        self.clase = clases
        # el agua interior queda plana (para el relieve y la linea de vista)
        if interior_f.any():
            self.elev = np.where(interior_f, ndimage.grey_erosion(np.where(interior_f, elev, 9999), size=3), self.elev)
            self.elev = np.where(self.elev > 9000, elev, self.elev)
        for nombre, k in (("agua", pt.AGUA), ("llano", pt.LLANO), ("bosque", pt.BOSQUE), ("pantano", pt.PANTANO),
                          ("urbano", pt.URBANO), ("montana", pt.MONTANA), ("rio", pt.RIO)):
            print(f"  {nombre}: {100.0 * (clases == k).mean():.1f} %", flush=True)

    # ---------------------------------------------------------------- ciudades
    def ubicar_ciudades(self):
        """Ciudades donde se asientan las reales: costas, rios y llanos, lejos de las cumbres y separadas."""
        ec, tc = self.ec, self.tc
        acc = self.acc.reshape(self.hc, self.wc)
        dcosta = reducir(agrandar(self.dcosta2.astype(np.float32), (self.H, self.W)), F)
        pais = reducir(self.pais.astype(np.float32), F) > 0.5
        rio = ndimage.binary_dilation(acc > 1500, iterations=2)
        puntaje = (np.where(dcosta < 6, 1.4, 0) + np.where(rio, 1.0, 0) + np.where(ec < 400, 0.8, 0) - ec / 1200.0
                   + 0.3 * self.rng.random(ec.shape))
        puntaje[~tc] = -9
        puntaje[dcosta < 1.0] = -9
        for lago in self.lagos_c + self.embalses_c:
            puntaje[ndimage.binary_dilation(lago, iterations=1)] = -9
        # distancia a la frontera: las capitales quedan lejos de ella
        frontera = tc & (pais != ndimage.binary_dilation(pais))
        dfrontera = ndimage.distance_transform_edt(~frontera) * self.km_px * F
        self.ciudades = []
        for p_i, (clave, nombres) in enumerate(NOMBRES_CIUDADES.items()):
            mascara = (pais == p_i) & tc
            p = np.where(mascara, puntaje, -9).ravel()
            elegidas = []
            for c in np.argsort(p)[::-1]:
                if p[c] < 0 or len(elegidas) == len(nombres):
                    break
                r, k = divmod(int(c), self.wc)
                if any(math.hypot(r - rr, k - kk) < 34 for rr, kk in elegidas):
                    continue
                if not elegidas and dfrontera[r, k] < 90:
                    continue  # la capital, a mas de 90 km de la frontera
                elegidas.append((r, k))
            for i, (r, k) in enumerate(elegidas):
                pop = int(2_400_000 / (1 + i) ** 1.15 * (0.85 + 0.3 * self.rng.random())) if i else 2_600_000 + p_i * 300_000
                x, y = k * F + F / 2, r * F + F / 2
                lon, lat = self.proy.lonlat(x, y)
                self.ciudades.append({"nombre": nombres[i], "pais": clave, "pop": pop, "capital": i == 0,
                                      "px": (x, y), "celda": (r, k), "lon": lon, "lat": lat,
                                      "costa": bool(dcosta[r, k] < 6)})
        print(f"Ciudades: {len(self.ciudades)}", flush=True)

    # ---------------------------------------------------------------- carreteras
    def carreteras(self):
        h, w = self.hc, self.wc
        pantano_c = reducir((self.clase == pt.PANTANO).astype(np.float32), F) > 0.5
        es_rio = reducir((self.clase == pt.RIO).astype(np.float32), F) > 0
        es_agua = reducir((self.clase == pt.AGUA).astype(np.float32), F) > 0.5
        ec = self.ec
        pend = np.hypot(*np.gradient(ec)) / (self.km_px * F * 1000)
        costo = np.ones((h, w), np.float64)
        costo += np.where(ec > 1500, 3.0, 0) + np.clip(pend * 40, 0, 6)
        costo *= np.where(pantano_c, 1.8, 1.0)
        costo += np.where(es_rio, 6.0, 0)  # cruzar un rio cuesta un puente: se cruza poco y por el camino mas corto
        costo[es_agua] = np.inf
        self.costo_c = costo
        idx = np.arange(h * w).reshape(h, w)

        def grafo(c):
            filas, cols, pesos = [], [], []
            for dr, dk, dd in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, 1.414), (1, -1, 1.414)):
                if dk < 0:
                    a = idx[0:h - dr, -dk:w]
                    b = idx[dr:h, 0:w + dk]
                elif dk > 0:
                    a = idx[0:h - dr, 0:w - dk]
                    b = idx[dr:h, dk:w]
                else:
                    a = idx[0:h - dr, :]
                    b = idx[dr:h, :]
                ca, cb = c.ravel()[a.ravel()], c.ravel()[b.ravel()]
                p = dd * (ca + cb) / 2
                ok = np.isfinite(p)
                filas += [a.ravel()[ok], b.ravel()[ok]]
                cols += [b.ravel()[ok], a.ravel()[ok]]
                pesos += [p[ok], p[ok]]
            return csr_matrix((np.concatenate(pesos), (np.concatenate(filas), np.concatenate(cols))), shape=(h * w, h * w))

        nodos = [c["celda"][0] * w + c["celda"][1] for c in self.ciudades]
        g = grafo(costo)
        dist = dijkstra(g, indices=nodos)[:, nodos]
        n = len(nodos)
        # arbol de expansion minima entre las ciudades (troncales) y enlaces extra entre vecinas (secundarias)
        en, aristas = {0}, []
        while len(en) < n:
            mejor = min(((dist[i, j], i, j) for i in en for j in range(n) if j not in en and np.isfinite(dist[i, j])), default=None)
            if mejor is None:
                break
            aristas.append((mejor[1], mejor[2], 2))
            en.add(mejor[2])
        pares = {(min(a, b), max(a, b)) for a, b, _ in aristas}
        for i in range(n):
            for j in np.argsort(dist[i])[1:4]:
                par = (min(i, int(j)), max(i, int(j)))
                if par not in pares and np.isfinite(dist[i, j]):
                    pares.add(par)
                    aristas.append((par[0], par[1], 1))
        # cada camino se traza sobre el costo actual: los tramos ya hechos abaratan los siguientes (la red se junta)
        self.vias = []
        usado = np.zeros(h * w, bool)
        for k, (i, j, nivel) in enumerate(sorted(aristas, key=lambda a: (-a[2], dist[a[0], a[1]]))):
            c = np.where(usado.reshape(h, w), costo * 0.45, costo)
            g = grafo(c) if k % 3 == 0 or k < 4 else g
            _, pred = dijkstra(g, indices=nodos[i], return_predecessors=True)
            camino = []
            x = nodos[j]
            while x != nodos[i] and x >= 0:
                camino.append(int(x))
                x = pred[x]
            if x < 0:
                continue
            camino.append(nodos[i])
            usado[camino] = True
            pts = chaikin([((c_ % w) * F + F / 2, (c_ // w) * F + F / 2) for c_ in reversed(camino)], 2)
            ci, cj = self.ciudades[i], self.ciudades[j]
            nivel = 2 if nivel == 2 and (ci["pop"] > 250_000 or cj["pop"] > 250_000) else 1
            self.vias.append({"nivel": nivel, "pts": pts, "de": ci["nombre"], "a": cj["nombre"]})
        print(f"Carreteras: {len(self.vias)} tramos", flush=True)

    # ---------------------------------------------------------------- infraestructura
    def infraestructura(self):
        inst = []
        acc = self.acc.reshape(self.hc, self.wc)
        for i, (r, k) in enumerate(self.represas):
            # la central queda al pie de la represa, aguas abajo, en tierra firme
            c = r * self.wc + k
            for _ in range(8):
                x, y = k * F + F / 2, r * F + F / 2
                if self.clase[int(y), int(x)] not in (pt.AGUA, pt.RIO) or self.rec[c] < 0:
                    break
                c = int(self.rec[c])
                r, k = divmod(c, self.wc)
            x, y = self._cerca_en_tierra((k * F + F / 2, r * F + F / 2), 3) if self.clase[int(r * F + 2), int(k * F + 2)] in (pt.AGUA, pt.RIO) else (k * F + F / 2, r * F + F / 2)
            lon, lat = self.proy.lonlat(x, y)
            mw = int(round(min(4000, acc[r, k] * 0.35), -1))
            inst.append({"nombre": f"Central Hidroeléctrica {NOMBRES_EMBALSES[i].replace('Embalse ', '')}", "clase": "hidroelectrica",
                         "lat": round(lat, 5), "lon": round(lon, 5), "capacidad": f"{mw:,} MW".replace(",", " "),
                         "descripcion": f"Represa del {NOMBRES_EMBALSES[i].lower()}.", "pais": self._pais_en(r, k)})
        for clave in PAISES:
            costeras = [c for c in self.ciudades if c["pais"] == clave and c["costa"]]
            costeras.sort(key=lambda c: -c["pop"])
            for c, clase, capacidad in ((costeras[0] if costeras else None, "termoelectrica", "1 200 MW"),
                                         (costeras[1] if len(costeras) > 1 else None, "refineria", "180 000 barriles por día")):
                if c is None:
                    continue
                x, y = self._cerca_en_tierra(c["px"], 14)
                lon, lat = self.proy.lonlat(x, y)
                tipo = "Planta Termoeléctrica" if clase == "termoelectrica" else "Refinería"
                inst.append({"nombre": f"{tipo} de {c['nombre']}", "clase": clase, "lat": round(lat, 5), "lon": round(lon, 5),
                             "capacidad": capacidad, "pais": clave})
            capital = next(c for c in self.ciudades if c["pais"] == clave and c["capital"])
            x, y = self._cumbre_cerca(capital["px"], 90)
            lon, lat = self.proy.lonlat(x, y)
            inst.append({"nombre": f"Centro de comunicaciones de {capital['nombre']}", "clase": "centro_comunicaciones",
                         "lat": round(lat, 5), "lon": round(lon, 5), "pais": clave,
                         "descripcion": f"Antenas y enlaces de microondas en la cumbre más alta cerca de {capital['nombre']}."})
        # puentes: donde una troncal cruza un rio grande
        vistos = []
        for v in self.vias:
            if v["nivel"] != 2:
                continue
            for x, y in v["pts"]:
                xi, yi = int(round(x)), int(round(y))
                if not (0 <= xi < self.W and 0 <= yi < self.H) or self.clase[yi, xi] != pt.RIO:
                    continue
                a = acc[min(self.hc - 1, yi // F), min(self.wc - 1, xi // F)]
                if a < 2500 or any(math.hypot(x - a_, y - b_) < 60 for a_, b_ in vistos):
                    continue
                vistos.append((x, y))
                lon, lat = self.proy.lonlat(x, y)
                rio = self._nombre_rio_en(xi, yi)
                inst.append({"nombre": f"Puente sobre el {rio}" if rio else f"Puente de la troncal {v['de']}–{v['a']}",
                             "clase": "puente", "lat": round(lat, 5), "lon": round(lon, 5), "radio_km": 0.8, "largo_km": 0.6,
                             "descripcion": f"Troncal {v['de']} – {v['a']}.", "pais": self._pais_en(yi // F, xi // F)})
        for i, e in enumerate(sorted(inst, key=lambda x: (x["clase"], x["nombre"]))):
            e["id"] = f"fic{i + 1:03d}"
        self.instalaciones = inst
        print(f"Infraestructura: {len(inst)} instalaciones", flush=True)

    def _pais_en(self, r, k):
        return "valdoria" if self.pais[min(self.H - 1, r * F), min(self.W - 1, k * F)] == 0 else "ostrania"

    def _cerca_en_tierra(self, p, radio):
        x0, y0 = p
        for _ in range(200):
            a = self.rng.random() * 2 * math.pi
            x, y = x0 + math.cos(a) * radio, y0 + math.sin(a) * radio
            xi, yi = int(x), int(y)
            if 0 <= xi < self.W and 0 <= yi < self.H and self.clase[yi, xi] in (pt.LLANO, pt.BOSQUE):
                return x, y
        return p

    def _cumbre_cerca(self, p, radio):
        x0, y0 = int(p[0]), int(p[1])
        ya, yb = max(0, y0 - radio), min(self.H, y0 + radio)
        xa, xb = max(0, x0 - radio), min(self.W, x0 + radio)
        sub = np.where(self.tierra[ya:yb, xa:xb], self.elev[ya:yb, xa:xb], -1)
        r, k = np.unravel_index(int(np.argmax(sub)), sub.shape)
        return xa + k, ya + r

    def _nombre_rio_en(self, x, y):
        mejor, dmin = None, 1e9
        for t, pts, _ in self.rios_px:
            nombre = self.nombre_tramo.get(id(t))
            if not nombre:
                continue
            for a, b in pts[::3]:
                d = math.hypot(a - x, b - y)
                if d < dmin:
                    mejor, dmin = nombre, d
        return mejor if dmin < 12 else None

    # ============================================================================ salidas
    def escribir_grillas(self):
        DATOS.mkdir(parents=True, exist_ok=True)
        meta = REG.meta()
        (DATOS / "clases.bin.z").write_bytes(zlib.compress(self.clase.tobytes(), 9))
        elev = np.clip(np.rint(self.elev), -500, 9000).astype("<i2")
        (DATOS / "elevacion.bin.z").write_bytes(zlib.compress(elev.tobytes(), 6))
        img = Image.new("L", (self.W, self.H), 0)
        d = ImageDraw.Draw(img)
        for nivel in (1, 2):
            for v in self.vias:
                if v["nivel"] == nivel:
                    d.line(v["pts"], fill=nivel, width=2)
        (DATOS / "vias.bin.z").write_bytes(zlib.compress(img.tobytes(), 9))
        meta.update(elev_paso=1, elev_ancho=self.W, elev_alto=self.H, vias_fuente=FUENTE, ficticio=True)
        (DATOS / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        print(f"Grillas del motor en {DATOS}", flush=True)

    def escribir_teselas(self):
        for carpeta in (pt.TILES_OUT / ID, TILES_SAT / ID):
            if carpeta.exists():
                shutil.rmtree(carpeta)
        rgb = pt.colorear(self.elev, self.clase, self.dzdx, self.dzdy)
        n = pt.escribir_nativas(REG, rgb, self.xa, self.ya)
        del rgb
        pt.piramide(REG.meta(), [])
        self.mancha = ruido(np.random.default_rng(SEMILLA + 3), (self.H // 4, self.W // 4), 90, 4, 0.5)
        self.detalle = ruido(np.random.default_rng(SEMILLA + 4), (self.H // 2, self.W // 2), 9, 3, 0.55)
        mancha = agrandar(self.mancha, (self.H, self.W), 1)
        detalle = agrandar(self.detalle, (self.H, self.W), 1)
        sat = self.colorear_satelite(self.elev, self.clase, self.dzdx, self.dzdy, np.random.default_rng(SEMILLA + 1), mancha, detalle)
        del mancha, detalle
        m = self._nativas(TILES_SAT / ID / str(REG.z), sat, self.xa, self.ya)
        del sat
        m += self.satelite_detalle()
        self._piramide(TILES_SAT / ID, REG.z, REG.z_min)
        print(f"Teselas: {n} de relieve y {m} satelitales nativas", flush=True)

    @staticmethod
    def colorear_satelite(elev, clase, dzdx, dzdy, rng, mancha, detalle, x0=0):
        """Vista satelital sintetica: colores naturales con variacion de humedad (`mancha`, gran escala) y de
        vegetacion (`detalle`, escala media), ambas calculadas para todo el mapa (sin costuras entre franjas); grano
        fino, parcelas de cultivo, roca en las laderas empinadas, nieve en las cumbres y sombra del relieve."""
        h, w = clase.shape
        z = 3.0
        nx, ny = -z * dzdx, -z * dzdy
        norma = np.sqrt(nx * nx + ny * ny + 1)
        az, alt = math.radians(315), math.radians(48)
        sombra = np.clip((nx * math.sin(az) * math.cos(alt) + ny * math.cos(az) * math.cos(alt) + math.sin(alt)) / norma, 0, 1)
        pendiente = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
        grano = rng.normal(0, 1, (h, w)).astype(np.float32)
        tex = (detalle * 0.7 + grano * 0.3)[..., None]
        col = lambda c: np.array(c, np.float32)  # noqa: E731
        rgb = np.zeros((h, w, 3), np.float32)
        seco = np.clip(0.5 + 0.28 * mancha + 0.12 * detalle, 0, 1)[..., None]
        # sabana y pastizal: del verde al pajizo segun la humedad
        pasto = col((104, 124, 70)) * (1 - seco) + col((158, 148, 100)) * seco + tex * 9
        # bosque: dosel oscuro con claros
        bosque = col((38, 64, 38)) + tex * 11 + np.clip(detalle, 0, None)[..., None] * col((6, 10, 4))
        llano = clase == pt.LLANO
        rgb[llano] = pasto[llano]
        bx = (np.arange(w)[None, :] + x0) // 7
        by = np.arange(h)[:, None] // 6
        parcela = ((bx * 73856093) ^ (by * 19349663)) % 7
        campos = llano & (mancha > 0.15) & (detalle > -0.3) & (parcela < 3)
        tono = np.stack([np.where(parcela == 0, 0.86, 1.08), np.where(parcela == 1, 0.92, 1.1), np.full(parcela.shape, 0.88)], -1)
        rgb[campos] *= np.broadcast_to(tono, (h, w, 3))[campos]
        rgb[clase == pt.BOSQUE] = bosque[clase == pt.BOSQUE]
        pantano = col((66, 88, 66)) + tex * 9
        charcos = (clase == pt.PANTANO) & (detalle > 0.9)
        rgb[clase == pt.PANTANO] = pantano[clase == pt.PANTANO]
        rgb[charcos] = col((44, 70, 78))
        # montaña: vegetacion donde la ladera es suave y la cota baja, roca en las pendientes y nieve arriba
        monta = clase == pt.MONTANA
        roca_t = np.clip((pendiente - 12) / 18, 0, 1) * 0.7 + np.clip((elev - 2200) / 1200, 0, 1) * 0.6
        roca_t = np.clip(roca_t, 0, 1)[..., None]
        alto_t = np.clip((elev - 1500) / 2000, 0, 1)[..., None]
        veg = bosque * (1 - alto_t) + pasto * alto_t
        roca = col((122, 110, 94)) * (1 - alto_t) + col((146, 140, 132)) * alto_t + tex * 12
        m_rgb = veg * (1 - roca_t) + roca * roca_t
        rgb[monta] = m_rgb[monta]
        nieve = monta & (elev > 3250 + 120 * detalle)
        rgb[nieve] = (col((236, 238, 240)) + tex * 4)[nieve]
        urb = clase == pt.URBANO
        manzanas = ((bx // 1) % 3 == 0) | ((by // 1) % 3 == 0)
        rgb[urb] = (col((140, 134, 126)) + tex * 14)[urb]
        rgb[urb & manzanas] *= 0.82
        rgb[clase == pt.RIO] = (col((50, 82, 96)) + tex * 3)[clase == pt.RIO]
        rgb *= (0.55 + 0.7 * sombra)[..., None]
        prof = np.clip(-elev / 900.0, 0, 1)[..., None]
        mar = col((40, 104, 130)) * (1 - prof) + col((14, 42, 78)) * prof + (grano * 2)[..., None]
        agua = clase == pt.AGUA
        rgb[agua] = mar[agua]
        interior = agua & (elev > 0)
        rgb[interior] = (col((30, 66, 88)) + (grano * 2)[..., None])[interior]
        return np.clip(rgb, 0, 255).astype(np.uint8)

    @staticmethod
    def _nativas(carpeta, rgb, x0, y0):
        h, w = rgb.shape[:2]
        im = Image.fromarray(rgb)
        n = 0
        for j in range(h // 256):
            for i in range(w // 256):
                ruta = carpeta / str(x0 + i) / f"{y0 + j}.jpg"
                ruta.parent.mkdir(parents=True, exist_ok=True)
                im.crop((i * 256, j * 256, (i + 1) * 256, (j + 1) * 256)).save(ruta, "JPEG", quality=84, optimize=True)
                n += 1
        return n

    def satelite_detalle(self):
        """Zoom 10 de la vista satelital: el doble de detalle, con textura nueva (no solo la imagen agrandada)."""
        rng = np.random.default_rng(SEMILLA + 2)
        n = 0
        carpeta = TILES_SAT / ID / str(REG.z + 1)
        self._mancha_fina = agrandar(self.mancha, (self.H, self.W), 1)
        self._detalle_fino = agrandar(self.detalle, (self.H, self.W), 1)
        for fila in range(self.H // 256):
            y0, y1 = max(0, fila * 256 - 2), min(self.H, fila * 256 + 258)
            elev = ndimage.zoom(self.elev[y0:y1], 2, order=1)
            clase = ndimage.zoom(self.clase[y0:y1], 2, order=0)
            rec = (fila * 256 - y0) * 2
            elev, clase = elev[rec:rec + 512], clase[rec:rec + 512]
            mancha = ndimage.zoom(self._mancha_fina[y0:y1], 2, order=1)[rec:rec + 512]
            detalle = ndimage.zoom(self._detalle_fino[y0:y1], 2, order=1)[rec:rec + 512]
            gy, gx = np.gradient(elev)
            pm = float(self.m_px[min(self.H - 1, fila * 256)]) / 2
            sat = self.colorear_satelite(elev, clase, gx / pm, -gy / pm, rng, mancha, detalle, self.xa * 512)
            n += self._nativas(carpeta, sat, self.xa * 2, self.ya * 2 + fila * 2)
        return n

    @staticmethod
    def _piramide(carpeta, z, z_min):
        for zz in range(z - 1, z_min - 1, -1):
            hijos = {(int(p.parent.name), int(p.stem)) for p in (carpeta / str(zz + 1)).glob("*/*.jpg")}
            for x, y in sorted({(a // 2, b // 2) for a, b in hijos}):
                im = Image.new("RGB", (256, 256), (14, 42, 78))
                for dx in (0, 1):
                    for dy in (0, 1):
                        hijo = carpeta / str(zz + 1) / str(2 * x + dx) / f"{2 * y + dy}.jpg"
                        if hijo.is_file():
                            im.paste(Image.open(hijo).convert("RGB").resize((128, 128), Image.LANCZOS), (dx * 128, dy * 128))
                ruta = carpeta / str(zz) / str(x) / f"{y}.jpg"
                ruta.parent.mkdir(parents=True, exist_ok=True)
                im.save(ruta, "JPEG", quality=84, optimize=True)

    # ---------------------------------------------------------------- capas vectoriales
    def _a_lonlat(self, pts, tol=0.004, nd=4):
        ll = [self.proy.lonlat(x, y) for x, y in pts]
        ll = simplificar(ll, tol)
        return [[round(a, nd), round(b, nd)] for a, b in ll]

    def escribir_geo(self):
        GEO.mkdir(parents=True, exist_ok=True)

        def guardar(nombre, features):
            (GEO / f"{nombre}.geojson").write_text(json.dumps({"type": "FeatureCollection", "fuente": FUENTE, "features": features},
                                                             ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        def linea(props, coords):
            return {"type": "Feature", "properties": props, "geometry": {"type": "LineString", "coordinates": coords}}

        # fronteras: costas (de la grilla gruesa) y el limite entre los dos paises
        costas = contornos(self.tc, minimo=6)
        fr = [linea({"name": "Costa", "pais": "XV"}, self._a_lonlat(chaikin([(x * F + F / 2, y * F + F / 2) for x, y in c], 2)))
              for c in costas]
        pais_c = reducir(self.pais.astype(np.float32), F) > 0.5
        limite = contornos(pais_c & self.tc, minimo=6)
        for c in limite:
            # solo los tramos del contorno de Ostrania que no son costa
            tramo = []
            for x, y in c:
                xi, yi = int(round(x)), int(round(y))
                interior = all(0 <= yi + dy < self.hc and 0 <= xi + dx < self.wc and self.tc[yi + dy, xi + dx]
                               for dy in (-1, 0, 1) for dx in (-1, 0, 1))
                if interior:
                    tramo.append((x * F + F / 2, y * F + F / 2))
                elif len(tramo) > 3:
                    fr.append(linea({"name": "Frontera Valdoria – Ostrania"}, self._a_lonlat(chaikin(tramo, 2))))
                    tramo = []
                else:
                    tramo = []
            if len(tramo) > 3:
                fr.append(linea({"name": "Frontera Valdoria – Ostrania"}, self._a_lonlat(chaikin(tramo, 2))))
        guardar("fronteras", fr)
        # provincias: limites de un Voronoi entre las ciudades de cada pais (solo por tierra y dentro del pais)
        yy, xx = np.mgrid[0:self.hc, 0:self.wc]
        semillas = [(c["celda"], i) for i, c in enumerate(self.ciudades) if self.rng.random() < 0.6 or c["capital"]]
        prov = np.full((self.hc, self.wc), -1, np.int32)
        dmin = np.full((self.hc, self.wc), np.inf)
        # el espacio se deforma suavemente (domain warping): limites curvos y naturales, no rectas de Voronoi
        rng_p = np.random.default_rng(SEMILLA + 11)
        xw = xx + 14 * ruido(rng_p, (self.hc, self.wc), 45, 3, 0.5)
        yw = yy + 14 * ruido(rng_p, (self.hc, self.wc), 45, 3, 0.5)
        for (r, k), i in semillas:
            d = np.hypot(yw - r, xw - k)
            mismo = pais_c == (self.ciudades[i]["pais"] == "ostrania")
            mejor = (d < dmin) & mismo
            prov[mejor], dmin[mejor] = i, d[mejor]
        estados = []
        for i in {i for _, i in semillas}:
            for c in contornos((prov == i) & self.tc, minimo=6):
                tramo = []
                for x, y in c:
                    xi, yi = int(round(x)), int(round(y))
                    ok = all(0 <= yi + dy < self.hc and 0 <= xi + dx < self.wc and self.tc[yi + dy, xi + dx]
                             and pais_c[yi + dy, xi + dx] == pais_c[yi, xi] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) \
                        if 0 <= yi < self.hc and 0 <= xi < self.wc else False
                    if ok:
                        tramo.append((x * F + F / 2, y * F + F / 2))
                    else:
                        if len(tramo) > 4:
                            estados.append(linea({"name": None, "pais": "XV" if self.ciudades[i]["pais"] == "valdoria" else "XO"},
                                                 self._a_lonlat(chaikin(tramo, 2))))
                        tramo = []
                if len(tramo) > 4:
                    estados.append(linea({"name": None}, self._a_lonlat(chaikin(tramo, 2))))
        guardar("estados", estados)
        # rios
        rios = []
        for t, pts, a in self.rios_px:
            if a < 2500:  # en la capa solo los rios grandes; los menores ya estan dibujados en el fondo del mapa
                continue
            rios.append({"type": "Feature", "properties": {"name": self.nombre_tramo.get(id(t)), "cuenca_km2": int(a)},
                         "geometry": {"type": "MultiLineString", "coordinates": [self._a_lonlat(pts, 0.002)]}})
        guardar("rios", rios)
        # lagos y embalses (poligonos)
        lagos = []
        for nombres, mascaras in ((NOMBRES_LAGOS, self.lagos_c), (NOMBRES_EMBALSES, self.embalses_c)):
            for nombre, m in zip(nombres, mascaras):
                for c in contornos(ndimage.binary_closing(m, iterations=1) | m, minimo=6):
                    anillo = self._a_lonlat(chaikin([(x * F + F / 2, y * F + F / 2) for x, y in c], 2, cerrada=True), 0.002)
                    if len(anillo) >= 4:
                        anillo.append(anillo[0])
                        lagos.append({"type": "Feature", "properties": {"name": nombre},
                                      "geometry": {"type": "Polygon", "coordinates": [anillo]}})
        guardar("lagos", lagos)
        # ciudades
        lugares = [{"type": "Feature", "properties": {"name": c["nombre"], "pop": c["pop"], "capital": c["capital"],
                                                      "pais": PAISES[c["pais"]]["nombre"]},
                    "geometry": {"type": "Point", "coordinates": [round(c["lon"], 4), round(c["lat"], 4)]}} for c in self.ciudades]
        guardar("lugares", lugares)
        # carreteras
        vias = []
        for i, v in enumerate(self.vias):
            vias.append(linea({"nivel": v["nivel"], "nombre": f"{'Troncal' if v['nivel'] == 2 else 'Carretera'} {v['de']} – {v['a']}",
                               "ref": f"{'T' if v['nivel'] == 2 else 'C'}-{i + 1}"}, self._a_lonlat(v["pts"], 0.0008)))
        guardar("carreteras", vias)
        # infraestructura (la capa del mapa la lee y el instructor la coloca en el ejercicio)
        (GEO / "infraestructura.json").write_text(json.dumps({"fuente": FUENTE, "instalaciones": self.instalaciones},
                                                             ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Capas: {len(fr)} costas y fronteras, {len(estados)} limites de provincia, {len(rios)} rios, {len(lagos)} lagos, "
              f"{len(lugares)} ciudades, {len(vias)} carreteras", flush=True)

    # ---------------------------------------------------------------- plantilla de ejercicio
    def escribir_plantilla(self):
        """"Valdoria contra Ostrania": cada bando con su capital, bases, defensa, sensores, infraestructura y una
        fuerza de maniobra cerca de la frontera; objetivos que pesan en la guerra para ambos."""
        unidades, objetivos = [], []
        cap = {p: next(c for c in self.ciudades if c["pais"] == p and c["capital"]) for p in PAISES}
        # el punto de la frontera mas cercano entre las dos capitales (por donde se espera el esfuerzo principal)
        pais_c = reducir(self.pais.astype(np.float32), F) > 0.5
        frontera = (pais_c != ndimage.grey_dilation(pais_c.astype(np.uint8), size=3).astype(bool)) & self.tc
        ys, xs = np.nonzero(frontera)
        cx = (cap["valdoria"]["celda"][1] + cap["ostrania"]["celda"][1]) / 2
        cy = (cap["valdoria"]["celda"][0] + cap["ostrania"]["celda"][0]) / 2
        i0 = int(np.argmin(np.hypot(ys - cy, xs - cx)))
        fr = (ys[i0], xs[i0])

        def punto(desde, hacia_km, rumbo_rad, clases_ok=(pt.LLANO, pt.BOSQUE, pt.URBANO)):
            r, k = desde
            for intento in range(60):
                d = hacia_km / (self.km_px * F) * (1 + 0.15 * intento / 10)
                a = rumbo_rad + (intento % 7 - 3) * 0.25
                rr, kk = int(r + math.sin(a) * d), int(k + math.cos(a) * d)
                if 0 <= rr < self.hc and 0 <= kk < self.wc:
                    xi, yi = kk * F + 2, rr * F + 2
                    if self.clase[yi, xi] in clases_ok:
                        lon, lat = self.proy.lonlat(xi, yi)
                        return round(lat, 5), round(lon, 5)
            lon, lat = self.proy.lonlat(k * F + 2, r * F + 2)
            return round(lat, 5), round(lon, 5)

        def u(nombre, bando, clase, lat, lon, **kw):
            unidades.append({"nombre": nombre, "bando": bando, "clase": clase, "lat": lat, "lon": lon, **kw})

        for p, datos in PAISES.items():
            b = datos["bando"]
            c = cap[p]
            sentido = 0.0 if p == "valdoria" else math.pi  # hacia la frontera: este para Valdoria, oeste para Ostrania
            hacia = math.atan2(fr[0] - c["celda"][0], fr[1] - c["celda"][1])
            gent = "valdoriano" if p == "valdoria" else "ostranio"
            base = punto(c["celda"], 12, sentido + 1.2)
            u(f"Base Aérea de {c['nombre']}", b, "base_aerea", *base)
            u(f"Cazas {gent}s", b, "caza", *base, modelo="f16" if p == "valdoria" else "su30", aeronaves=4,
              en_tierra=True, base=f"Base Aérea de {c['nombre']}")
            u(f"Aviación de ataque {gent}", b, "ataque", *base, modelo="ataque_ligero", aeronaves=2, en_tierra=True,
              base=f"Base Aérea de {c['nombre']}")
            u(f"Helicópteros de ataque {gent}s", b, "helicoptero", *base, modelo="helo_ataque", aeronaves=2, en_tierra=True,
              base=f"Base Aérea de {c['nombre']}")
            u(f"Depósito logístico de {c['nombre']}", b, "deposito", *punto(c["celda"], 10, sentido - 1.0))
            u(f"Defensa antiaérea de {c['nombre']}", b, "antiaerea", *punto(c["celda"], 8, hacia))
            x, y = self._cumbre_cerca(c["px"], 110)
            lon, lat = self.proy.lonlat(x, y)
            u(f"Radar de vigilancia {gent}", b, "radar", round(lat, 5), round(lon, 5))
            # fuerza de maniobra a 40-60 km de la frontera
            frente = (fr[0] - math.sin(hacia) * 0, fr[1])
            for nombre, clase, km, desv in ((f"1.ª Brigada de Infantería {gent}", "infanteria", 45, 0.0),
                                            (f"Brigada Blindada {gent}", "blindado", 55, 0.5),
                                            (f"Grupo de Artillería {gent}", "artilleria", 60, -0.4),
                                            (f"Escuadrón de Reconocimiento {gent}", "reconocimiento", 30, 0.2),
                                            (f"Batallón de Ingenieros {gent}", "ingenieros", 55, -0.7),
                                            (f"Convoy logístico {gent}", "transporte", 65, 0.9)):
                rumbo = math.atan2(c["celda"][0] - frente[0], c["celda"][1] - frente[1]) + desv
                kw = {"escalon": "brigada"} if "Brigada" in nombre else {}
                u(nombre, b, clase, *punto(frente, km, rumbo), **kw)
            # infraestructura del pais
            for inst in self.instalaciones:
                if inst["pais"] == p and inst["clase"] != "puente":
                    extra = {"radio_km": inst["radio_km"]} if inst.get("radio_km") else {}
                    u(inst["nombre"], b, inst["clase"], inst["lat"], inst["lon"], **extra)
        nombres_vistos = {x["nombre"] for x in unidades}
        for inst in self.instalaciones:
            if inst["clase"] == "puente":
                n_ = 2
                while inst["nombre"] in nombres_vistos:
                    inst["nombre"] = f"{inst['nombre'].split(' (')[0]} ({n_})"
                    n_ += 1
                nombres_vistos.add(inst["nombre"])
                u(inst["nombre"], PAISES[inst["pais"]]["bando"], "puente", inst["lat"], inst["lon"], radio_km=inst["radio_km"])
        # objetivos: la capital enemiga cercana a la frontera y la infraestructura que pesa en la guerra
        fr_lon, fr_lat = self.proy.lonlat(fr[1] * F + 2, fr[0] * F + 2)
        for p, datos in PAISES.items():
            b, otro = datos["bando"], "rojo" if datos["bando"] == "azul" else "azul"
            propias = [x for x in unidades if x["bando"] == b]
            for x in propias:
                if x["clase"] in ("hidroelectrica", "termoelectrica"):
                    objetivos.append({"bando": otro, "tipo": "destruir", "nombre": f"Dejar sin energía: {x['nombre']}", "puntos": 20, "unidad": x["nombre"]})
                    objetivos.append({"bando": b, "tipo": "proteger", "nombre": f"Mantener {x['nombre']}", "puntos": 15,
                                      "unidad": x["nombre"], "hasta_turno": 10})
                elif x["clase"] == "refineria":
                    objetivos.append({"bando": otro, "tipo": "destruir", "nombre": f"Cortar el combustible: {x['nombre']}", "puntos": 15, "unidad": x["nombre"]})
                elif x["clase"] == "centro_comunicaciones":
                    objetivos.append({"bando": otro, "tipo": "destruir", "nombre": f"Cortar los enlaces: {x['nombre']}", "puntos": 15, "unidad": x["nombre"]})
            base = next(x for x in propias if x["clase"] == "base_aerea")
            objetivos.append({"bando": otro, "tipo": "destruir", "nombre": f"Neutralizar {base['nombre']}", "puntos": 30, "unidad": base["nombre"]})
        for b in ("azul", "rojo"):
            objetivos.append({"bando": b, "tipo": "ocupar", "nombre": "Controlar el paso de frontera central", "puntos": 30,
                              "lat": round(fr_lat, 5), "lon": round(fr_lon, 5), "radio_km": 8.0, "turnos_requeridos": 3})
        nv, no = cap["valdoria"]["nombre"], cap["ostrania"]["nombre"]
        plantilla = {
            "id": "teatro_ficticio", "nombre": "Valdoria contra Ostrania (mapa ficticio)",
            "descripcion": (
                "Ejercicio sobre el mapa ficticio, sin ningún país real: la República de Valdoria (azul, capital "
                f"{nv}) y la República de Ostrania (rojo, capital {no}) se enfrentan a lo largo de su frontera. Cada bando "
                "tiene su base aérea con cazas, ataque y helicópteros, defensa antiaérea, radar, depósito, una fuerza de "
                "maniobra a 30-65 km de la frontera y su infraestructura: centrales, refinería, centro de comunicaciones "
                "y los puentes de las troncales. Objetivos: el paso de frontera central, la base aérea enemiga y la "
                "infraestructura que sostiene la guerra del otro bando. Para jugar contra el simulador, active el "
                "adversario automático en Consola → Dirección del ejercicio."),
            "clima": "despejado", "hora_inicio_min": 420, "nacion_azul": "valdoria", "nacion_rojo": "ostrania",
            "ia_azul": False, "ia_rojo": False, "dia_noche": True, "con_estado": False,
            "unidades": unidades, "objetivos": objetivos,
        }
        PLANTILLAS.mkdir(parents=True, exist_ok=True)
        (PLANTILLAS / "teatro_ficticio.json").write_text(json.dumps(plantilla, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Plantilla: {len(unidades)} unidades y {len(objetivos)} objetivos", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sin-teselas", action="store_true", help="no rehacer las teselas (solo grillas y capas)")
    args = ap.parse_args()
    m = Mapa()
    m.tierra()
    m.relieve()
    m.hidrologia()
    m.lagos_y_embalses()
    m.rios()
    m.ubicar_ciudades()
    m.clases()
    m.carreteras()
    m.infraestructura()
    m.escribir_grillas()
    m.escribir_geo()
    m.escribir_plantilla()
    if not args.sin_teselas:
        m.escribir_teselas()
    print("Listo.", flush=True)


if __name__ == "__main__":
    main()
