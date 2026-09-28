"""Azar reproducible: el mismo escenario (semilla), turno y par de unidades dan
siempre el mismo factor, de modo que un ejercicio puede repetirse y auditarse."""

import hashlib
import math
import random

SIGMA = 0.25  # dispersion log-normal del ratio (~ +-28 % en el 68 % de los casos)
LIMITE_Z = 2.0  # se recortan los extremos


def factor_azar(semilla: int, turno: int, atacante_id: int, defensor_id: int) -> float:
    h = hashlib.sha256(f"{semilla}:{turno}:{atacante_id}:{defensor_id}".encode()).digest()
    rng = random.Random(int.from_bytes(h[:8], "big"))
    z = max(-LIMITE_Z, min(LIMITE_Z, rng.gauss(0.0, 1.0)))
    return math.exp(SIGMA * z)
