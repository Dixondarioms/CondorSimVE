"""Motor de resolucion de combate.

La relacion de fuerzas (poder atacante / poder defensor), ajustada por tipo de
arma, terreno, cobertura aerea, apoyo, clima y municion, se convierte en
perdidas con una curva continua (interpolacion en log2 del ratio entre puntos
de anclaje, sin saltos bruscos). Es determinista; el azar es opcional y
reproducible (ver engine/azar.py) y entra como un multiplicador del ratio.
"""

import math
from dataclasses import dataclass, field

from app.terreno import FACTOR_DEFENSA

# Efectividad generica del atacante segun (tipo_atacante, tipo_objetivo), usada
# solo cuando no se indica un factor por clase de unidad.
FACTOR_TIPO_ARMA = {
    ("terrestre", "terrestre"): 1.0,
    ("aerea", "terrestre"): 0.8,
    ("aerea", "aerea"): 1.0,
    ("terrestre", "aerea"): 0.3,
    ("naval", "naval"): 1.0,
    ("naval", "terrestre"): 0.6,
    ("terrestre", "naval"): 0.5,
    ("aerea", "naval"): 0.9,
    ("naval", "aerea"): 0.4,
}

# Defensa terrestre atacada desde el aire sin cobertura aerea propia.
PENALIZACION_SIN_COBERTURA_AEREA = 0.7
# Atacante terrestre con cobertura aerea propia frente a un defensor sin ella.
BONO_SUPERIORIDAD_AEREA = 1.15

# (ratio, perdida % del defensor, perdida % del atacante). En los anclajes el
# resultado coincide con la tabla clasica; entre ellos se interpola.
ANCLAJES = [
    (0.25, 3.0, 30.0),
    (0.5, 8.0, 20.0),
    (1.0, 15.0, 15.0),
    (2.0, 25.0, 10.0),
    (3.0, 40.0, 5.0),
    (4.0, 50.0, 3.0),
]


@dataclass
class CombatResult:
    ratio: float
    perdida_atacante_pct: float
    perdida_defensor_pct: float
    fuerza_atacante_resultante: float
    fuerza_defensor_resultante: float
    resumen: str
    efectos: list[str] = field(default_factory=list)


def perdidas_por_ratio(ratio: float) -> tuple[float, float]:
    """(perdida del defensor, perdida del atacante) en puntos porcentuales."""
    if ratio <= ANCLAJES[0][0]:
        return ANCLAJES[0][1], ANCLAJES[0][2]
    if ratio >= ANCLAJES[-1][0]:
        return ANCLAJES[-1][1], ANCLAJES[-1][2]
    x = math.log2(ratio)
    for (r0, d0, a0), (r1, d1, a1) in zip(ANCLAJES, ANCLAJES[1:]):
        if r0 <= ratio <= r1:
            t = (x - math.log2(r0)) / (math.log2(r1) - math.log2(r0))
            return d0 + (d1 - d0) * t, a0 + (a1 - a0) * t
    raise AssertionError("ratio fuera de los anclajes")  # inalcanzable


def resolver_combate(
    fuerza_atacante: float,
    tipo_atacante: str,
    fuerza_defensor: float,
    tipo_defensor: str,
    terreno_defensor: str = "llano",
    cobertura_aerea_defensor: bool = True,
    cobertura_aerea_atacante: bool = False,
    bono_atacante: float = 1.0,
    bono_defensor: float = 1.0,
    factor_ataque: float | None = None,
    factor_defensa: float = 1.0,
    factor_clima: float = 1.0,
    factor_municion: float = 1.0,
    azar: float = 1.0,
    sorpresa: float = 1.0,
    cadencia: float = 1.0,
) -> CombatResult:
    """Resuelve un enfrentamiento. Fuerzas en escala 0-100 (% de la nominal);
    devuelve las fuerzas resultantes recortadas a [0, 100]. Los tipos son
    "terrestre", "aerea" o "naval" (las bases cuentan como terrestres)."""
    if fuerza_atacante <= 0 or fuerza_defensor <= 0:
        raise ValueError("ambas unidades deben tener fuerza > 0 para combatir")

    efectos: list[str] = []
    base_tipo = FACTOR_TIPO_ARMA.get((tipo_atacante, tipo_defensor), 0.5) if factor_ataque is None else factor_ataque
    factor_cadencia = math.sqrt(max(cadencia, 0.0)) if cadencia > 0 else 1.0
    poder_atacante = (
        fuerza_atacante * base_tipo * bono_atacante * factor_clima * factor_municion * sorpresa * factor_cadencia
    )
    poder_defensor = fuerza_defensor * factor_defensa * bono_defensor

    def anotar(cond, texto):
        if cond:
            efectos.append(texto)

    anotar(bono_atacante != 1.0, f"apoyo al atacante x{bono_atacante:.2f}")
    anotar(bono_defensor != 1.0, f"apoyo al defensor x{bono_defensor:.2f}")
    anotar(factor_clima != 1.0, f"clima x{factor_clima:.2f} al ataque")
    anotar(factor_municion < 1.0, f"municion escasa x{factor_municion:.2f}")
    anotar(sorpresa != 1.0, f"sorpresa (atacante no detectado) x{sorpresa:.2f}")
    anotar(cadencia != 1.0, f"cadencia de fuego x{factor_cadencia:.2f}")

    if tipo_defensor == "terrestre":
        factor_terreno = FACTOR_DEFENSA.get(terreno_defensor, 1.0)
        poder_defensor *= factor_terreno
        anotar(factor_terreno != 1.0, f"terreno {terreno_defensor} x{factor_terreno:.2f} a la defensa")

    if tipo_atacante == "aerea" and tipo_defensor == "terrestre" and not cobertura_aerea_defensor:
        poder_defensor *= PENALIZACION_SIN_COBERTURA_AEREA
        anotar(True, f"defensor sin cobertura aerea x{PENALIZACION_SIN_COBERTURA_AEREA:.2f}")

    if (
        tipo_atacante == "terrestre"
        and tipo_defensor == "terrestre"
        and cobertura_aerea_atacante
        and not cobertura_aerea_defensor
    ):
        poder_atacante *= BONO_SUPERIORIDAD_AEREA
        anotar(True, f"superioridad aerea del atacante x{BONO_SUPERIORIDAD_AEREA:.2f}")

    ratio = poder_atacante / poder_defensor if poder_defensor > 0 else float("inf")
    if azar != 1.0:
        ratio *= azar
        efectos.append(f"azar x{azar:.2f}")
    perdida_defensor_pct, perdida_atacante_pct = perdidas_por_ratio(ratio)

    fuerza_defensor_resultante = max(0.0, min(100.0, fuerza_defensor - perdida_defensor_pct))
    fuerza_atacante_resultante = max(0.0, min(100.0, fuerza_atacante - perdida_atacante_pct))

    resumen = (
        f"Ratio {ratio:.2f}: defensor pierde {perdida_defensor_pct:.1f}%, "
        f"atacante pierde {perdida_atacante_pct:.1f}%."
    )
    if efectos:
        resumen += " Efectos: " + "; ".join(efectos) + "."

    return CombatResult(
        ratio=ratio,
        perdida_atacante_pct=perdida_atacante_pct,
        perdida_defensor_pct=perdida_defensor_pct,
        fuerza_atacante_resultante=fuerza_atacante_resultante,
        fuerza_defensor_resultante=fuerza_defensor_resultante,
        resumen=resumen,
        efectos=efectos,
    )
