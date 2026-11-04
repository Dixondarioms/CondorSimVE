"""Estado del mar del Cóndor (lo fija el director, como el clima): con mar gruesa los helicopteros no calan el sonar,
las sonoboyas y los sonares oyen menos, los buques chicos van mas lentos y el reabastecimiento en el mar se suspende.

El motor anota el estado de cada escenario en cada paso (fijar); las funciones lo leen por el escenario de la unidad.
"""

from __future__ import annotations

ESTADOS = {"calmo": "Calmo", "moderado": "Moderado", "grueso": "Grueso", "muy_grueso": "Muy grueso"}
SONAR = {"calmo": 1.0, "moderado": 0.9, "grueso": 0.75, "muy_grueso": 0.6}  # sonar de casco
BOYAS = {"calmo": 1.0, "moderado": 0.85, "grueso": 0.6, "muy_grueso": 0.4}  # radio de las sonoboyas que se siembran
CHICOS = ("patrullero", "cazaminas", "pesquero")  # lanchas y buques chicos: los frena el oleaje
VELOCIDAD_CHICOS = {"calmo": 1.0, "moderado": 1.0, "grueso": 0.7, "muy_grueso": 0.5}
VELOCIDAD_GRANDES = {"calmo": 1.0, "moderado": 1.0, "grueso": 1.0, "muy_grueso": 0.85}
CON_HELO_Y_REABASTECIMIENTO = ("calmo", "moderado")  # con mar gruesa no se cala el sonar ni se reabastece en el mar

_POR_ESCENARIO: dict[int, str] = {}


def fijar(esc) -> None:
    _POR_ESCENARIO[esc.id] = getattr(esc, "estado_mar", None) or "calmo"


def de(u) -> str:
    e = _POR_ESCENARIO.get(getattr(u, "escenario_id", None), "calmo")
    return e if e in ESTADOS else "calmo"


def factor_sonar(u) -> float:
    return SONAR[de(u)]


def factor_boyas(u) -> float:
    return BOYAS[de(u)]


def sonar_helo(u) -> bool:
    return de(u) in CON_HELO_Y_REABASTECIMIENTO


def reabastecer_en_el_mar(u) -> bool:
    return de(u) in CON_HELO_Y_REABASTECIMIENTO


def factor_velocidad(u) -> float:
    if getattr(u, "tipo", "") != "naval" or getattr(u, "clase", None) == "torpedo":
        return 1.0
    return (VELOCIDAD_CHICOS if u.clase in CHICOS else VELOCIDAD_GRANDES)[de(u)]
