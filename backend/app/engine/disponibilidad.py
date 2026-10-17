"""Disponibilidad de las aeronaves, fallas en vuelo, esfuerzo aereo y atricion.

Con la opcion "Disponibilidad y fallas" del escenario (Escenario.fallas):
  - al despegar, cada aeronave del grupo esta lista con la probabilidad de disponibilidad de su modelo (o de su
    clase), rebajada por la falta de tecnicos del bando (sin tecnicos, la mitad); y no salen mas aeronaves que las
    tripulaciones con que cuenta el bando (cobertura de pilotos, engine/toe.py);
  - en vuelo, cada aeronave puede tener una falla (probabilidad por hora de vuelo de su clase): vuelve a su base y
    deja el grupo; si fallan todas, el grupo aborta y regresa.
Siempre (con o sin fallas) se lleva el esfuerzo de cada bando: salidas (aeronaves que despegaron), horas de vuelo,
aeronaves perdidas en vuelo, abortos por falla y no disponibles al despegar; de ahi, la tasa de atricion (perdidas
por cada 100 salidas) y las salidas por aeronave y por dia. Valores didacticos, ajustables.
"""

from __future__ import annotations

import hashlib
import json
import random

from app.engine import catalogo, plataformas

DISPONIBILIDAD_CLASE = {
    "caza": 0.75, "ataque": 0.8, "helicoptero": 0.7, "helicoptero_artillado": 0.7, "avion_ge": 0.8,
    "alerta_temprana": 0.8, "cisterna": 0.8, "dron_reconocimiento": 0.85, "dron_ataque": 0.85,
    "municion_merodeadora": 0.95,
}
FALLA_HORA_CLASE = {  # probabilidad de falla de una aeronave por hora de vuelo
    "caza": 0.015, "ataque": 0.012, "helicoptero": 0.02, "helicoptero_artillado": 0.02, "avion_ge": 0.01,
    "alerta_temprana": 0.01, "cisterna": 0.008, "dron_reconocimiento": 0.025, "dron_ataque": 0.025,
}
CAMPOS = ("salidas", "horas", "perdidas", "abortos", "no_disponibles")


def _rng(escenario, *claves) -> random.Random:
    h = hashlib.sha256(":".join(str(c) for c in (getattr(escenario, "semilla", 0), *claves)).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def tasa_disponibilidad(modelo_id: str | None) -> float:
    m = catalogo.MODELOS.get(modelo_id or "")
    if m is None:
        return 0.75
    f = plataformas.ficha_de_modelo(m)
    if f is not None and getattr(f, "disponibilidad", 0):
        return f.disponibilidad
    return DISPONIBILIDAD_CLASE.get(m.clase, 0.75)


def falla_por_hora(u) -> float:
    f = plataformas.ficha(u)
    if f is not None and getattr(f, "falla_h", 0):
        return f.falla_h
    return FALLA_HORA_CLASE.get(getattr(u, "clase", ""), 0.0)


def listas_para_despegar(escenario, base, modelo_id: str, pedidas: int, cobertura_tecnicos: float,
                         cobertura_pilotos: float, tripulaciones: int, clave) -> tuple[int, str]:
    """Aeronaves que estan listas de las `pedidas` y por que faltan las otras (vacio si salen todas)."""
    p = tasa_disponibilidad(modelo_id) * (0.5 + 0.5 * max(0.0, min(1.0, cobertura_tecnicos)))
    rng = _rng(escenario, "despegue", escenario.turno_actual, base.id, clave)
    listas = sum(1 for _ in range(pedidas) if rng.random() < p)
    motivo = []
    if listas < pedidas:
        motivo.append(f"{pedidas - listas} en mantenimiento (disponibilidad {p * 100:.0f} %)")
    tripulaciones_listas = int(pedidas * tripulaciones * max(0.0, cobertura_pilotos))
    if tripulaciones_listas < listas:
        motivo.append(f"solo hay tripulaciones para {tripulaciones_listas}")
        listas = tripulaciones_listas
    return listas, "; ".join(motivo)


def fallas_en_vuelo(escenario, u, turno: int) -> int:
    """Aeronaves del grupo que tienen una falla en esta hora de vuelo."""
    lam = falla_por_hora(u)
    if lam <= 0:
        return 0
    rng = _rng(escenario, "falla", turno, u.id)
    operativas = max(1, round((u.aeronaves or 1) * max(0.0, u.fuerza) / 100.0))
    return sum(1 for _ in range(operativas) if rng.random() < lam)


# ---------------------------------------------------------------------------------------------- esfuerzo
def esfuerzo(escenario) -> dict:
    try:
        datos = json.loads(getattr(escenario, "esfuerzo_json", None) or "{}")
    except ValueError:
        datos = {}
    return {b: {c: float((datos.get(b) or {}).get(c, 0)) for c in CAMPOS} for b in ("azul", "rojo")}


def sumar(escenario, bando: str, **valores) -> None:
    datos = esfuerzo(escenario)
    for k, v in valores.items():
        datos[bando][k] = round(datos[bando][k] + float(v), 2)
    escenario.esfuerzo_json = json.dumps(datos)


def resumen(escenario, bando: str, unidades) -> dict:
    """Indicadores del esfuerzo aereo del bando hasta ahora."""
    e = esfuerzo(escenario)[bando]
    dias = max(1.0, (escenario.turno_actual or 1) / 24.0)
    aeronaves = sum(max(1, x.aeronaves or 1) for x in unidades
                    if x.bando == bando and x.tipo == "aerea" and x.estado == "activa" and not catalogo.es_misil(x))
    return {
        **{k: round(v, 1) for k, v in e.items()},
        "atricion_pct": round(100.0 * e["perdidas"] / e["salidas"], 1) if e["salidas"] else 0.0,
        "salidas_por_aeronave_dia": round(e["salidas"] / max(1, aeronaves) / dias, 2) if aeronaves else 0.0,
        "aeronaves_en_servicio": aeronaves,
        "fallas": bool(getattr(escenario, "fallas", False)),
    }
