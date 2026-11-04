"""Contramedidas del Cóndor (como en los simuladores de mando modernos): bengalas y chaff de las aeronaves tripuladas y
señuelos de los buques.

Cuando a una aeronave le tiran un misil (antiaereo o aire-aire) o a un buque le llega un misil, suelta una contramedida
si le quedan: la probabilidad de que ese misil le pegue baja a FACTOR. Cada aeronave del grupo lleva POR_AERONAVE; cada
buque, SEÑUELOS segun su clase. Las aeronaves las reponen al rearmar en tierra; los buques, al reabastecerse (en el
mar, de un buque logistico, o en puerto). Lo que no se gasto queda; lo gastado va al informe de perdidas y gastos.
"""

from __future__ import annotations

from app.engine import catalogo

FACTOR = 0.7  # la probabilidad de impacto del misil que la contramedida engaña
POR_AERONAVE = 4
SENUELOS = {"portaaviones": 12, "destructor": 12, "fragata": 8, "patrullero": 4, "buque_desembarco": 4,
            "buque_logistico": 4, "cazaminas": 2}


def maximo(u) -> int:
    clase = catalogo.obtener(getattr(u, "clase", None), getattr(u, "tipo", ""))
    if getattr(u, "tipo", "") == "aerea":
        if clase.dron or clase.se_consume or clase.civil or catalogo.es_misil(u):
            return 0
        return POR_AERONAVE * max(1, int(getattr(u, "aeronaves", 1) or 1))
    if getattr(u, "tipo", "") == "naval":
        return SENUELOS.get(clase.id, 0)
    return 0


def quedan(u) -> int:
    m = maximo(u)
    v = getattr(u, "contramedidas", None)
    return m if v is None else max(0, min(int(v), m))


def usar(u) -> bool:
    """Suelta una contramedida si le queda. True si la uso."""
    n = quedan(u)
    if n <= 0:
        return False
    u.contramedidas = n - 1
    return True


def reponer(u) -> None:
    u.contramedidas = None  # llena


def nombre(u) -> str:
    return "Bengalas y chaff" if getattr(u, "tipo", "") == "aerea" else "Señuelos"


def publico(u) -> dict | None:
    m = maximo(u)
    return {"nombre": nombre(u), "quedan": quedan(u), "maximo": m} if m else None
