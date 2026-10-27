"""Ruta mas rapida de una unidad terrestre hasta un destino, siguiendo carreteras y evitando lo intransitable.

Busqueda A* sobre una grilla local (pasos de ~0,6 km, mas gruesos en distancias largas) en la que cada celda cuesta
su largo dividido por el factor de velocidad que la unidad conserva alli (movimiento.factor_terreno: terreno,
carreteras, puentes reales y obras de ingenieros). Devuelve los waypoints simplificados (a lo sumo 30, el maximo de
una orden), listos para una orden "mover".
"""

import heapq
import math

from app.engine import geo, movimiento

MAX_WAYPOINTS = 30  # se busca no pasar de esto; si recortar cruzaria un rio o el agua, se conservan mas puntos
MAX_WAYPOINTS_RUTA = 120  # tope absoluto (el de una orden "mover")
MUESTRA_KM = 0.2  # cada cuanto se revisa que un tramo recto sea transitable
MARGENES_REFINO_KM = (3.0, 10.0, 25.0)  # alrededor de un tramo que pisa un rio, se busca de cerca en estas franjas...
PASO_REFINO_KM = 0.25  # ...con celdas de este tamaño
RADIO_DESTINO = 3  # celdas alrededor de un destino intransitable en que se busca el lugar transitable mas cercano
PASO_MIN_KM = 0.6
CELDAS_POR_LADO = 260  # la grilla se hace mas gruesa en distancias largas para no pasar de ~70 000 celdas utiles
MARGEN = 0.4  # se busca en el rectangulo de origen y destino ampliado en esta fraccion de la distancia
MARGEN_MIN_KM = 25.0
INTENTOS = 3  # sin camino, se repite con un rectangulo el doble de amplio (y una grilla mas gruesa)
FACTOR_MAXIMO = 1.5  # el mejor factor posible (autopista): mantiene admisible la heuristica


def _simplificar(puntos, tol, transitable=None):
    """Douglas-Peucker; con `transitable(a, b)`, un tramo recto que cruzaria algo intransitable no se recorta."""
    if len(puntos) < 3:
        return puntos
    (y1, x1), (y2, x2) = puntos[0], puntos[-1]
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy) or 1e-12
    i_max, d_max = 0, 0.0
    for i in range(1, len(puntos) - 1):
        y, x = puntos[i]
        d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / largo
        if d > d_max:
            i_max, d_max = i, d
    if d_max <= tol and (transitable is None or transitable(puntos[0], puntos[-1])):
        return [puntos[0], puntos[-1]]
    if d_max <= tol:
        i_max = len(puntos) // 2
    return _simplificar(puntos[:i_max + 1], tol, transitable)[:-1] + _simplificar(puntos[i_max:], tol, transitable)


def ruta(unidad, destino, terreno, obras=()) -> dict:
    """{"waypoints": [[lat, lon], ...], "km": float, "nota": str}. Sin camino: ruta directa con una nota."""
    resultado = None
    for intento in range(INTENTOS):
        resultado = _buscar(unidad, destino, terreno, obras, 2 ** intento)
        if resultado.get("encontrada", True):
            break
    resultado.pop("encontrada", None)
    return resultado


def _transitable(unidad, terreno, obras, a, b) -> bool:
    """El tramo recto de a a b no pisa nada intransitable (como lo recorre el movimiento, en pasos cortos)."""
    n = max(1, int(geo.distancia_km(a[0], a[1], b[0], b[1]) / MUESTRA_KM))
    return all(movimiento.factor_en(unidad, terreno, obras, a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) > 0
               for k in range(1, n + 1))


def _camino(unidad, origen, destino, terreno, obras, margen_km, paso_min) -> tuple[list | None, bool]:
    """A* de origen a destino en una grilla de pasos >= paso_min: (puntos del camino o None, destino_ajustado). Si el
    destino cae en algo intransitable (un rio, el agua), se va a la celda transitable mas cercana."""
    (lat0, lon0), (lat1, lon1) = origen, destino
    dist = geo.distancia_km(lat0, lon0, lat1, lon1)
    paso = max(paso_min, (dist + 2 * margen_km) / CELDAS_POR_LADO)
    cos = max(0.05, math.cos(math.radians((lat0 + lat1) / 2)))
    dlat, dlon = paso / 111.32, paso / (111.32 * cos)
    sur = min(lat0, lat1) - margen_km / 111.32
    oeste = min(lon0, lon1) - margen_km / (111.32 * cos)
    filas = int((max(lat0, lat1) + margen_km / 111.32 - sur) / dlat) + 1
    cols = int((max(lon0, lon1) + margen_km / (111.32 * cos) - oeste) / dlon) + 1

    def celda(lat, lon):
        return (min(filas - 1, max(0, round((lat - sur) / dlat))), min(cols - 1, max(0, round((lon - oeste) / dlon))))

    def centro(c):
        return (sur + c[0] * dlat, oeste + c[1] * dlon)

    factores: dict = {}

    def factor(c):
        f = factores.get(c)
        if f is None:
            f = factores[c] = movimiento.factor_en(unidad, terreno, obras, *centro(c))
        return f

    inicio, fin = celda(lat0, lon0), celda(lat1, lon1)
    ajustado = False
    if factor(fin) <= 0:
        cercanas = [(fin[0] + i, fin[1] + j) for i in range(-RADIO_DESTINO, RADIO_DESTINO + 1)
                    for j in range(-RADIO_DESTINO, RADIO_DESTINO + 1)
                    if 0 <= fin[0] + i < filas and 0 <= fin[1] + j < cols]
        cercanas = [c for c in cercanas if factor(c) > 0]
        if not cercanas:
            return None, False
        fin = min(cercanas, key=lambda c: math.hypot(c[0] - fin[0], c[1] - fin[1]))
        ajustado = True

    def h(c):
        return math.hypot(c[0] - fin[0], c[1] - fin[1]) * paso / FACTOR_MAXIMO

    vecinos = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    abiertos = [(h(inicio), 0.0, inicio)]
    costo = {inicio: 0.0}
    previo = {}
    while abiertos:
        _, g, c = heapq.heappop(abiertos)
        if c == fin:
            break
        if g > costo.get(c, math.inf):
            continue
        for df, dc in vecinos:
            n = (c[0] + df, c[1] + dc)
            if not (0 <= n[0] < filas and 0 <= n[1] < cols):
                continue
            f = factor(n)
            if f <= 0:
                continue
            ng = g + paso * (1.4142 if df and dc else 1.0) / f
            if ng < costo.get(n, math.inf):
                costo[n] = ng
                previo[n] = c
                heapq.heappush(abiertos, (ng + h(n), ng, n))
    if fin != inicio and fin not in previo:
        return None, ajustado
    camino = [fin]
    while camino[-1] != inicio:
        camino.append(previo[camino[-1]])
    puntos = [centro(c) for c in reversed(camino)]
    puntos[0] = (lat0, lon0)
    if not ajustado:
        puntos[-1] = (lat1, lon1)
    return puntos, ajustado


def _refinar(unidad, terreno, obras, puntos) -> list:
    """En una grilla gruesa el camino puede "saltar" un rio angosto entre dos celdas: cada tramo que pisa algo
    intransitable se vuelve a trazar de cerca, con una grilla fina alrededor de ese tramo. Si no se encuentra otro paso
    el tramo queda como estaba (en marcha, la unidad que se tope con el rio busca otro camino)."""
    salida = [puntos[0]]
    for a, b in zip(puntos, puntos[1:]):
        if not _transitable(unidad, terreno, obras, a, b):
            for margen in MARGENES_REFINO_KM:  # el puente puede estar lejos: se busca cada vez en una franja mas ancha
                local, _ = _camino(unidad, a, b, terreno, obras, margen, PASO_REFINO_KM)
                if local:
                    salida.extend(local[1:])
                    break
            else:
                salida.append(b)
            continue
        salida.append(b)
    return salida


def _buscar(unidad, destino, terreno, obras, ampliacion) -> dict:
    lat0, lon0 = unidad.lat, unidad.lon
    lat1, lon1 = destino
    directa = {"waypoints": [[lat1, lon1]], "km": geo.distancia_km(lat0, lon0, lat1, lon1), "nota": ""}
    if unidad.tipo != "terrestre":
        directa["nota"] = "Solo las unidades terrestres siguen carreteras: ruta directa."
        return directa
    dist = directa["km"]
    if dist < 1.0:
        return directa
    margen_km = max(MARGEN_MIN_KM, dist * MARGEN) * ampliacion
    paso = max(PASO_MIN_KM, (dist + 2 * margen_km) / CELDAS_POR_LADO)
    puntos, ajustado = _camino(unidad, (lat0, lon0), (lat1, lon1), terreno, obras, margen_km, PASO_MIN_KM)
    if puntos is None:
        if ajustado is False and movimiento.factor_en(unidad, terreno, obras, lat1, lon1) <= 0:
            directa["nota"] = "El destino es intransitable para esta unidad: ruta directa."
            return directa
        directa["nota"] = "No hay camino transitable (rios sin puente, agua o montaña): ruta directa."
        directa["encontrada"] = False
        return directa
    if paso > PASO_REFINO_KM * 2:
        puntos = _refinar(unidad, terreno, obras, puntos)

    def transitable(a, b) -> bool:
        return _transitable(unidad, terreno, obras, a, b)

    tol = paso / 111.32 * 0.5
    simple = _simplificar(puntos, tol, transitable)
    while len(simple) - 1 > MAX_WAYPOINTS and tol < paso / 111.32 * 20:
        tol *= 1.6
        simple = _simplificar(puntos, tol, transitable)
    while len(simple) - 1 > MAX_WAYPOINTS_RUTA:  # caso extremo: se recorta sin revisar
        tol *= 1.6
        simple = _simplificar(puntos, tol)
    km = sum(geo.distancia_km(*a, *b) for a, b in zip(puntos, puntos[1:]))
    nota = f"Ruta por el camino más rápido ({km:.0f} km, {len(simple) - 1} tramos)."
    if ajustado:
        nota += " El punto elegido es intransitable para la unidad: llega al lugar transitable más cercano."
    return {"waypoints": [[round(a, 5), round(b, 5)] for a, b in simple[1:]], "km": round(km, 1), "nota": nota}
