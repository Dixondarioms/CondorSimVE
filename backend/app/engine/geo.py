from math import asin, cos, radians, sin, sqrt

RADIO_TIERRA_KM = 6371.0


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia entre dos puntos (formula de Haversine), en kilometros."""
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def avanzar_hacia(
    lat1: float, lon1: float, lat2: float, lon2: float, distancia_maxima_km: float
) -> tuple[float, float]:
    """Devuelve el punto intermedio entre (lat1,lon1) y (lat2,lon2) que resulta
    de avanzar como maximo distancia_maxima_km en linea recta. Si el destino
    esta mas cerca que distancia_maxima_km, devuelve el destino."""
    total = distancia_km(lat1, lon1, lat2, lon2)
    if total <= distancia_maxima_km or total == 0:
        return lat2, lon2
    fraccion = distancia_maxima_km / total
    return lat1 + (lat2 - lat1) * fraccion, lon1 + (lon2 - lon1) * fraccion
