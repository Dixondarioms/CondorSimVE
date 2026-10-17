"""Puntos de Recobre Operacional (PRO): aerodromos avanzados o tramos de carretera donde las aeronaves aterrizan para
reabastecerse y rearmarse cerca del frente (en la OTA, el campo "punto de recobre" de la linea ABA: PR01, PR02...).

Un PRO es una base liviana: pocas plazas (4), existencias chicas que solo reponen los convoyes y una pista corta (la
que fije el instructor; sin pista, solo helicopteros y aeronaves de despegue vertical). Requisitos minimos para operar
bien: PERSONAL_MINIMO efectivos (seguridad, combustible, armamento, comunicaciones y sanidad), existencias de
combustible y municion, y una unidad propia de seguridad o defensa aerea a <= RADIO_SEGURIDAD_KM. Con su personal
completo, una aeronave queda lista en REARME_TURNOS (1 turno, frente a los 2 de una base aerea).
"""

from __future__ import annotations

from app.engine import catalogo, geo, logistica, personal

CLASE = "punto_recobre"
PERSONAL_MINIMO = 20
COMBUSTIBLE_MINIMO = 50.0  # puntos de existencias (100 = llenar una unidad)
MUNICION_MINIMA = 25.0
RADIO_SEGURIDAD_KM = 10.0
REARME_TURNOS = 1
PERSONAL_POR_FUNCION = {"seguridad": 8, "combustible": 6, "armamento": 6, "comunicaciones": 3, "sanidad": 2,
                        "control de vuelo": 3, "mando": 2}  # 30 de dotacion completa


def es_pro(u) -> bool:
    return (getattr(u, "clase", "") or "") == CLASE


def deficiencias(pro, unidades=()) -> list[str]:
    """Lo que le falta al PRO para cumplir los requisitos minimos (lista vacia si los cumple)."""
    out = []
    efectivos = personal.actual(pro)
    if efectivos < PERSONAL_MINIMO:
        out.append(f"Personal: {efectivos} de {PERSONAL_MINIMO} como mínimo (el rearme tarda 2 turnos).")
    if logistica.stock(pro, "combustible") < COMBUSTIBLE_MINIMO:
        out.append(f"Combustible: {logistica.stock(pro, 'combustible'):.0f} de {COMBUSTIBLE_MINIMO:.0f} puntos como mínimo.")
    if logistica.stock(pro, "municion") < MUNICION_MINIMA:
        out.append(f"Munición: {logistica.stock(pro, 'municion'):.0f} de {MUNICION_MINIMA:.0f} puntos como mínimo.")
    if unidades and not any(
            x.bando == pro.bando and x.estado == "activa" and x.tipo == "terrestre"
            and geo.distancia_km(x.lat, x.lon, pro.lat, pro.lon) <= RADIO_SEGURIDAD_KM for x in unidades):
        out.append(f"Seguridad: ninguna unidad propia a {RADIO_SEGURIDAD_KM:.0f} km o menos.")
    if not (getattr(pro, "pista_m", None) or 0):
        out.append("Sin pista: solo helicópteros y aeronaves de despegue vertical.")
    return out


def turnos_rearme(base, por_defecto: int) -> int:
    if es_pro(base) and personal.actual(base) >= PERSONAL_MINIMO:
        return REARME_TURNOS
    return por_defecto


def estado(unidades, bando: str) -> list[dict]:
    """PRO del bando con sus plazas, existencias y deficiencias (para la pestaña Situación)."""
    out = []
    for p in sorted((u for u in unidades if es_pro(u) and u.bando == bando and u.estado != "destruida"), key=lambda u: u.id):
        out.append({"id": p.id, "nombre": p.nombre, "pista_m": getattr(p, "pista_m", None) or 0,
                    "plazas": catalogo.plazas_aeronaves(p), "personal": personal.actual(p),
                    "combustible": round(logistica.stock(p, "combustible")), "municion": round(logistica.stock(p, "municion")),
                    "deficiencias": deficiencias(p, unidades)})
    return out
