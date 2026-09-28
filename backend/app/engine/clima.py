"""Efectos del clima. Lo fija el instructor por escenario."""

CLIMAS = ("despejado", "nublado", "lluvia", "tormenta")

# Multiplicador del radio de deteccion de todas las unidades.
DETECCION = {"despejado": 1.0, "nublado": 0.9, "lluvia": 0.7, "tormenta": 0.5}
# Multiplicador de velocidad segun el tipo de unidad.
MOVIMIENTO = {
    "terrestre": {"despejado": 1.0, "nublado": 1.0, "lluvia": 0.8, "tormenta": 0.6},
    "naval": {"despejado": 1.0, "nublado": 1.0, "lluvia": 0.9, "tormenta": 0.5},
    "aerea": {"despejado": 1.0, "nublado": 1.0, "lluvia": 0.9, "tormenta": 0.6},
}
# Multiplicador de la efectividad de los ataques realizados por unidades aereas.
ATAQUE_AEREO = {"despejado": 1.0, "nublado": 0.95, "lluvia": 0.8, "tormenta": 0.5}


def factor_deteccion(clima: str) -> float:
    return DETECCION.get(clima, 1.0)


def factor_movimiento(clima: str, tipo: str) -> float:
    return MOVIMIENTO.get(tipo, {}).get(clima, 1.0)


def factor_ataque_aereo(clima: str) -> float:
    return ATAQUE_AEREO.get(clima, 1.0)
