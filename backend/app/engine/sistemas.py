"""Daño por sistemas de buques y unidades de tierra (Cóndor, como en los simuladores de mando modernos).

Ademas de la fuerza, cada buque y cada unidad de tierra tiene cuatro sistemas que se dañan por separado:
- sensores (radar, sonar, optronicos): la deteccion se reduce en proporcion al daño;
- armas: su potencia de fuego (y la probabilidad de los misiles de su defensa aerea) se reduce igual;
- propulsion (o tren de rodaje): su velocidad se reduce; con el 100 % de daño queda inmovil;
- comunicaciones: sus ordenes tardan en llegar (se suma a la demora de las comunicaciones del ejercicio).
Cada punto de fuerza perdido tiene IMPACTO_POR_PUNTO de probabilidad de un impacto critico en un sistema al azar,
que le hace entre DANO_IMPACTO % (reproducible con la semilla del escenario): perder 25 puntos de fuerza daña un
sistema en promedio. Un sistema con FUERA_DE_SERVICIO % o mas queda fuera de servicio (alerta al bando). El control de averias repara con el tiempo
REPARACION_POR_HORA puntos por hora; en el mar o en campaña solo hasta AVERIA_GRAVE %: el resto se repara junto a un
puerto, deposito o base propia (a PUERTO_KM o menos).
Las aeronaves, las bases (tienen sus partes: engine/bases.py), los misiles y la infraestructura no tienen sistemas.
"""

from __future__ import annotations

import hashlib
import json
import random

from app.engine import catalogo, geo

SISTEMAS = ("sensores", "armas", "propulsion", "comunicaciones")
NOMBRES = {"sensores": "Sensores (radar y sonar)", "armas": "Armas", "propulsion": "Propulsión",
           "comunicaciones": "Comunicaciones"}
NOMBRES_TIERRA = {"propulsion": "Movilidad", "sensores": "Sensores (radar y ópticos)"}
IMPACTO_POR_PUNTO = 0.04  # impactos criticos esperados por punto de fuerza perdido
DANO_IMPACTO = (30.0, 70.0)  # % de daño de un impacto critico en un sistema
FUERA_DE_SERVICIO = 75.0
REPARACION_POR_HORA = 10.0
AVERIA_GRAVE = 40.0
PUERTO_KM = 5.0
DEMORA_COMUNICACIONES_PCT = 60.0  # con las comunicaciones destruidas, 60 % mas de ordenes demoradas


def aplica(u) -> bool:
    if getattr(u, "tipo", "") not in ("naval", "terrestre"):
        return False
    clase = catalogo.obtener(getattr(u, "clase", None), u.tipo)
    return not clase.infraestructura and not clase.civil


def datos(u) -> dict[str, float]:
    try:
        d = json.loads(getattr(u, "sistemas_json", None) or "{}")
    except ValueError:
        d = {}
    return {s: float(d.get(s, 0.0)) for s in SISTEMAS} if isinstance(d, dict) else {s: 0.0 for s in SISTEMAS}


def _guardar(u, d: dict) -> None:
    limpio = {s: round(v, 1) for s, v in d.items() if v > 0.05}
    u.sistemas_json = json.dumps(limpio, sort_keys=True) if limpio else None


def dano(u, sistema: str) -> float:
    if not getattr(u, "sistemas_json", None):  # lo mas comun: sano (se llama muchas veces por paso)
        return 0.0
    return datos(u)[sistema] if aplica(u) else 0.0


def factor(u, sistema: str) -> float:
    """Fraccion que conserva el sistema (1 = sano)."""
    return max(0.0, 1.0 - dano(u, sistema) / 100.0)


def nombre(u, sistema: str) -> str:
    if getattr(u, "tipo", "") == "terrestre" and sistema in NOMBRES_TIERRA:
        return NOMBRES_TIERRA[sistema]
    return NOMBRES[sistema]


def recibir(u, perdida: float, semilla: int, t: float) -> list[str]:
    """Impactos criticos en los sistemas por una perdida de fuerza. Devuelve los sistemas que quedaron fuera de
    servicio con este impacto."""
    if not aplica(u) or perdida <= 0:
        return []
    clave = f"{semilla}:sistemas:{u.id}:{t:.0f}:{perdida:.2f}"
    rng = random.Random(int.from_bytes(hashlib.sha256(clave.encode()).digest()[:8], "big"))
    esperados = perdida * IMPACTO_POR_PUNTO
    impactos = int(esperados) + (1 if rng.random() < esperados - int(esperados) else 0)
    if not impactos:
        return []
    d = datos(u)
    caidos = []
    for _ in range(impactos):
        s = rng.choice(SISTEMAS)
        antes = d[s]
        d[s] = min(100.0, antes + rng.uniform(*DANO_IMPACTO))
        if antes < FUERA_DE_SERVICIO <= d[s] and s not in caidos:
            caidos.append(s)
    _guardar(u, d)
    return caidos


def reparar(u, horas: float, unidades) -> list[str]:
    """Control de averias durante `horas`. Devuelve los sistemas que volvieron a servicio."""
    if not aplica(u):
        return []
    d = datos(u)
    if not any(v > 0 for v in d.values()):
        return []
    en_puerto = any(x.bando == u.bando and x.estado == "activa" and x.id != u.id
                    and (x.tipo == "base" or catalogo.obtener(x.clase, x.tipo).stock_max)
                    and geo.distancia_km(u.lat, u.lon, x.lat, x.lon) <= PUERTO_KM for x in unidades)
    vuelven = []
    for s, v in d.items():
        if v <= 0:
            continue
        minimo = 0.0 if en_puerto or v <= AVERIA_GRAVE else AVERIA_GRAVE
        nuevo = max(minimo, v - REPARACION_POR_HORA * horas)
        if v >= FUERA_DE_SERVICIO > nuevo:
            vuelven.append(s)
        d[s] = nuevo
    _guardar(u, d)
    return vuelven


def publico(u) -> dict | None:
    """Para la pantalla: % de daño de cada sistema con su nombre, y si se repara."""
    if not aplica(u):
        return None
    d = datos(u)
    return {s: {"nombre": nombre(u, s), "dano": round(d[s]), "fuera": d[s] >= FUERA_DE_SERVICIO} for s in SISTEMAS}
