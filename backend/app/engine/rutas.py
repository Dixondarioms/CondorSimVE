"""Ruta mas rapida de una unidad terrestre hasta un destino, siguiendo carreteras y evitando lo intransitable.

Busqueda A* sobre una grilla local (pasos de ~0,6 km, mas gruesos en distancias largas) en la que cada celda cuesta
su largo dividido por el factor de velocidad que la unidad conserva alli (movimiento.factor_terreno: terreno,
carreteras, puentes reales y obras de ingenieros). Devuelve los waypoints simplificados (a lo sumo 30, el maximo de
una orden), listos para una orden "mover".
"""

import heapq
import math

from app.engine import geo, movimiento

MAX_WAYPOINTS = 30
PASO_MIN_KM = 0.6
CELDAS_POR_LADO = 260  # la grilla se hace mas gruesa en distancias largas para no pasar de ~70 000 celdas utiles
MARGEN = 0.4  # se busca en el rectangulo de origen y destino ampliado en esta fraccion de la distancia
MARGEN_MIN_KM = 25.0
INTENTOS = 3  # sin camino, se repite con un rectangulo el doble de amplio (y una grilla mas gruesa)
FACTOR_MAXIMO = 1.5  # el mejor factor posible (autopista): mantiene admisible la heuristica


def _simplificar(puntos, tol):
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
    if d_max <= tol:
        return [puntos[0], puntos[-1]]
    return _simplificar(puntos[:i_max + 1], tol)[:-1] + _simplificar(puntos[i_max:], tol)


def ruta(unidad, destino, terreno, obras=()) -> dict:
    """{"waypoints": [[lat, lon], ...], "km": float, "nota": str}. Sin camino: ruta directa con una nota."""
    resultado = None
    for intento in range(INTENTOS):
        resultado = _buscar(unidad, destino, terreno, obras, 2 ** intento)
        if resultado.get("encontrada", True):
            break
    resultado.pop("encontrada", None)
    return resultado


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
            lat, lon = centro(c)
            f = movimiento.factor_terreno(unidad, terreno.clase(lat, lon), obras, lat, lon, terreno.via(lat, lon))
            factores[c] = f
        return f

    inicio, fin = celda(lat0, lon0), celda(lat1, lon1)
    if factor(fin) <= 0:
        directa["nota"] = "El destino es intransitable para esta unidad: ruta directa."
        return directa

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
    if fin not in previo:
        directa["nota"] = "No hay camino transitable (rios sin puente, agua o montaña): ruta directa."
        directa["encontrada"] = False
        return directa

    camino = [fin]
    while camino[-1] != inicio:
        camino.append(previo[camino[-1]])
    puntos = [centro(c) for c in reversed(camino)]
    puntos[0], puntos[-1] = (lat0, lon0), (lat1, lon1)
    tol = paso / 111.32 * 0.5
    simple = _simplificar(puntos, tol)
    while len(simple) - 1 > MAX_WAYPOINTS:
        tol *= 1.6
        simple = _simplificar(puntos, tol)
    km = sum(geo.distancia_km(*a, *b) for a, b in zip(puntos, puntos[1:]))
    return {"waypoints": [[round(a, 5), round(b, 5)] for a, b in simple[1:]], "km": round(km, 1),
            "nota": f"Ruta por el camino más rápido ({km:.0f} km, {len(simple) - 1} tramos)."}
