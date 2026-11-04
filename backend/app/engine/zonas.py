"""Areas de referencia y zonas del Cóndor (como en los simuladores de mando modernos).

El director y cada bando dibujan poligonos con nombre:
- area de patrulla: una unidad con la orden «patrullar» sobre el area la recorre de vertice en vertice y reacciona a
  lo que entra en ella segun la doctrina (lo ataca si sus armas lo autorizan; si no, lo deja pasar);
- zona de exclusion: nadie ajeno debe entrar (aeronaves en vuelo, buques ni tropas);
- zona de no vuelo: ninguna aeronave ajena debe volar sobre ella.
Quien cruza una zona de exclusion o de no vuelo dispara una alerta (y la pausa automatica, si el director la eligio):
al bando dueno de la zona, si ve al intruso; en las del director, al bando del intruso. Con «armas» marcado, las armas
propias tiran contra quien este dentro aunque la doctrina las tenga restringidas o retenidas (solo zonas de un bando).
Una zona puede acompañar a una unidad (un circulo de N km alrededor de una fragata, un area de patrulla sobre un grupo
naval): se corre lo que la unidad se mueve; si la unidad se pierde, la zona queda donde estaba.
"""

import json
import math

from app.engine import catalogo, geo
from app.models.zona import Zona

TIPOS = {"patrulla": "área de patrulla", "exclusion": "zona de exclusión", "no_vuelo": "zona de no vuelo"}
MAX_VERTICES = 60
MAX_POR_BANDO = 40
LLEGADA_VERTICE_KM = 2.0
VERTICES_CIRCULO = 24
SEGUIR_DESDE_KM = 0.3  # una zona que acompaña a una unidad se mueve cuando la unidad se corrio al menos esto


def puntos(z) -> list:
    try:
        p = json.loads(z.puntos_json or "[]")
    except ValueError:
        return []
    return [(float(a), float(b)) for a, b in p] if isinstance(p, list) else []


def dentro(lat: float, lon: float, poligono: list) -> bool:
    """Punto dentro del poligono [(lat, lon), ...] (rayo horizontal; sirve para zonas de cientos de km)."""
    adentro = False
    n = len(poligono)
    for i in range(n):
        (y1, x1), (y2, x2) = poligono[i], poligono[(i + 1) % n]
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / ((y2 - y1) or 1e-12):
            adentro = not adentro
    return adentro


def centro(poligono: list) -> tuple[float, float]:
    return sum(p[0] for p in poligono) / len(poligono), sum(p[1] for p in poligono) / len(poligono)


def visible(z, rol: str) -> bool:
    """Cada bando ve las suyas y las del director; el director y el observador, todas."""
    return z.bando == "todos" or rol not in ("azul", "rojo") or z.bando == rol


def de_escenario(db, escenario_id: int) -> list:
    return db.query(Zona).filter(Zona.escenario_id == escenario_id).order_by(Zona.id).all()


def serializar(z) -> dict:
    return {"id": z.id, "bando": z.bando, "tipo": z.tipo, "nombre": z.nombre, "puntos": [list(p) for p in puntos(z)],
            "armas": bool(z.armas), "autor": z.autor, "unidad_id": getattr(z, "unidad_id", None)}


def circulo(lat: float, lon: float, radio_km: float, n: int = VERTICES_CIRCULO) -> list:
    """Poligono de n vertices que aproxima un circulo de radio_km alrededor del punto."""
    dlat = radio_km / 110.57
    dlon = radio_km / (111.32 * max(0.05, math.cos(math.radians(lat))))
    return [(round(lat + dlat * math.cos(2 * math.pi * i / n), 5), round(lon + dlon * math.sin(2 * math.pi * i / n), 5))
            for i in range(n)]


def anclar(z, u) -> None:
    """La zona acompaña desde ahora a la unidad u (se mueve con ella)."""
    z.unidad_id, z.ancla_lat, z.ancla_lon = u.id, u.lat, u.lon


def seguir(z, u) -> bool:
    """Corre la zona lo que se movio su unidad desde la ultima vez. True si la movio."""
    if z.ancla_lat is None or z.ancla_lon is None:
        anclar(z, u)
        return False
    if geo.distancia_km(z.ancla_lat, z.ancla_lon, u.lat, u.lon) < SEGUIR_DESDE_KM:
        return False
    dlat, dlon = u.lat - z.ancla_lat, u.lon - z.ancla_lon
    z.puntos_json = json.dumps([[round(a + dlat, 5), round(b + dlon, 5)] for a, b in puntos(z)])
    z.ancla_lat, z.ancla_lon = u.lat, u.lon
    return True


def visibles_para(db, escenario, rol: str) -> list[dict]:
    return [serializar(z) for z in de_escenario(db, escenario.id) if visible(z, rol)]


def afecta(z, u) -> bool:
    """La zona controla a esa unidad: la de no vuelo, a las aeronaves en vuelo; la de exclusion, a todo lo que se
    mueve (no las bases ni lo embarcado). Los misiles no cuentan: no se los puede desviar."""
    if u.estado != "activa" or u.tipo == "base" or getattr(u, "transporte_id", None) or catalogo.es_misil(u):
        return False
    en_vuelo = u.tipo == "aerea" and not u.en_tierra
    if z.tipo == "no_vuelo":
        return en_vuelo
    return z.tipo == "exclusion" and (en_vuelo or u.tipo in ("naval", "terrestre"))


def ajena(z, u) -> bool:
    """Las zonas de un bando son contra los demas; las del director, contra todos."""
    return z.bando == "todos" or u.bando != z.bando


def zona_de_orden(orden) -> int | None:
    """Area de patrulla de una orden «patrullar» (None si es la orbita sobre un punto)."""
    if orden is None or orden.tipo != "patrullar" or not orden.detalle:
        return None
    try:
        return int(json.loads(orden.detalle).get("zona")) or None
    except (ValueError, TypeError, AttributeError):
        return None


def nombre(z) -> str:
    return f"{TIPOS.get(z.tipo, z.tipo)} «{z.nombre}»" if z.nombre else TIPOS.get(z.tipo, z.tipo)


def error_de_poligono(vertices: list) -> str | None:
    if not 3 <= len(vertices) <= MAX_VERTICES:
        return f"Una zona necesita entre 3 y {MAX_VERTICES} vértices."
    if any(not (-90 <= a <= 90 and -180 <= b <= 180) for a, b in vertices):
        return "Vértice fuera de rango."
    return None
