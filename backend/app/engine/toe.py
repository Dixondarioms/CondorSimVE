"""Plantilla de personal (TOE) y partes de personal por unidad, con reservas activas y milicianos.

Plantilla (lo autorizado) de cada unidad:
  - grupos aereos: por aeronave, `tripulaciones` tripulaciones de pilotos (3 en operaciones normales, 4 en
    operaciones intensas; cada tripulacion son los pilotos de su ficha tecnica: 1 en el F-16, 2 en el Su-30) y 7
    tecnicos de mantenimiento repartidos por especialidad, mas 3 de apoyo (seguridad, abastecimiento, servicios);
    las no tripuladas, operadores en lugar de pilotos;
  - el resto: su dotacion (engine/personal.py) repartida en oficiales, tecnicos (suboficiales y tropa profesional
    especializada) y tropa, segun el tipo de unidad.
Existencia: lo autorizado por la cobertura del bando (el % de la plantilla que tiene; lo fija el instructor) y por
la fuerza que le queda a la unidad (las bajas). El deficit se cubre, en orden de prioridad (aviacion, defensa aerea,
el resto), con las **reservas activas** del bando (pueden cubrir oficiales, pilotos y tecnicos) y con los
**milicianos** (solo apoyo y tropa). La cobertura de pilotos y tecnicos que queda pesa en la disponibilidad de las
aeronaves (engine/disponibilidad.py). Cifras didacticas, ajustables; no son plantillas oficiales.
"""

from __future__ import annotations

import json
import math

from app.engine import catalogo, defensa_aerea, personal, plataformas

TECNICOS_POR_AERONAVE = (("motores", 2), ("celula", 1), ("avionica", 1), ("armamento", 1), ("electricidad", 1),
                         ("equipo_de_vuelo", 1))  # 7 por aeronave
NOMBRE_ESPECIALIDAD = {"motores": "Motores", "celula": "Célula y estructuras", "avionica": "Aviónica",
                       "armamento": "Armamento", "electricidad": "Electricidad e instrumentos",
                       "equipo_de_vuelo": "Equipo de vuelo y supervivencia"}
APOYO_POR_AERONAVE = 3
CATEGORIAS = ("pilotos", "tecnicos", "oficiales", "tropa")  # tambien el orden en que se cubre el deficit
NOMBRE_CATEGORIA = {"oficiales": "Oficiales", "pilotos": "Pilotos / operadores", "tecnicos": "Técnicos",
                    "tropa": "Tropa y apoyo"}
# reparto de la dotacion por tipo de unidad: (oficiales, tecnicos, tropa)
REPARTO = {"defensa_aerea": (0.15, 0.45, 0.40), "sensor": (0.2, 0.6, 0.2), "naval": (0.12, 0.38, 0.5),
           "base": (0.1, 0.4, 0.5), "terrestre": (0.06, 0.2, 0.74)}
CUBREN_RESERVAS = ("oficiales", "pilotos", "tecnicos", "tropa")
CUBREN_MILICIAS = ("tropa",)
POR_DEFECTO = {"cobertura": 100, "reserva": 0, "milicia": 0, "tripulaciones": 3}


def config(escenario, bando: str) -> dict:
    """Configuracion de personal del bando: cobertura (% de la plantilla), reservas activas y milicianos
    disponibles, y tripulaciones por aeronave (3 o 4)."""
    try:
        datos = json.loads(getattr(escenario, "personal_json", None) or "{}")
    except ValueError:
        datos = {}
    return {**POR_DEFECTO, **(datos.get(bando) or {})}


def _aereo(u) -> bool:
    return u.tipo == "aerea" and not catalogo.es_misil(u)


def plantilla(u, tripulaciones: int = 3) -> dict:
    """Lo autorizado: {oficiales, pilotos, tecnicos, tropa} y el desglose de tecnicos por especialidad."""
    if _aereo(u):
        n = max(1, int(getattr(u, "aeronaves", 1) or 1))
        f = plataformas.ficha(u)
        tripulacion = f.tripulacion if f is not None else 1
        pilotos = max(1, tripulacion) * n * tripulaciones  # no tripuladas: operadores en tierra
        espec = {e: k * n for e, k in TECNICOS_POR_AERONAVE}
        return {"oficiales": 1 + n // 4, "pilotos": pilotos, "tecnicos": sum(espec.values()),
                "tropa": APOYO_POR_AERONAVE * n, "especialidades": espec}
    total = personal.inicial(u)
    if not total:
        return {c: 0 for c in CATEGORIAS} | {"especialidades": {}}
    clase = catalogo.obtener(getattr(u, "clase", None), u.tipo)
    clave = ("defensa_aerea" if (clase.defensa_aerea or defensa_aerea.sistema(u)) else
             "sensor" if clase.solo_aereo or clase.celula == "ge" else
             "naval" if u.tipo == "naval" else "base" if u.tipo == "base" else "terrestre")
    of, tec, _ = REPARTO[clave]
    oficiales, tecnicos = max(1, round(total * of)), round(total * tec)
    return {"oficiales": oficiales, "pilotos": 0, "tecnicos": tecnicos, "tropa": max(0, total - oficiales - tecnicos),
            "especialidades": {}}


def _prioridad(u) -> int:
    if _aereo(u):
        return 0
    clase = catalogo.obtener(getattr(u, "clase", None), u.tipo)
    return 1 if clase.defensa_aerea or clase.solo_aereo else 2


def partes(unidades, escenario, bando: str) -> dict:
    """Parte de personal de cada unidad del bando y del bando entero, con lo que cubren las reservas y la milicia."""
    cfg = config(escenario, bando)
    cobertura = max(0.0, min(100.0, float(cfg["cobertura"]))) / 100.0
    tripulaciones = 4 if int(cfg.get("tripulaciones") or 3) >= 4 else 3
    reserva, milicia = max(0, int(cfg["reserva"] or 0)), max(0, int(cfg["milicia"] or 0))
    propias = [u for u in unidades if u.bando == bando and u.estado != "destruida"
               and (personal.inicial(u) or _aereo(u))]
    filas = []
    for u in sorted(propias, key=lambda x: (_prioridad(x), x.id)):
        aut = plantilla(u, tripulaciones)
        fuerza = max(0.0, min(100.0, u.fuerza or 0.0)) / 100.0
        fila = {"unidad_id": u.id, "nombre": u.nombre, "clase": u.clase or u.tipo, "categorias": {}}
        for c in CATEGORIAS:
            a = aut[c]
            existe = math.floor(a * cobertura * fuerza + 1e-9)
            falta = max(0, a - existe)
            por_reserva = min(falta, reserva) if c in CUBREN_RESERVAS else 0
            reserva -= por_reserva
            por_milicia = min(falta - por_reserva, milicia) if c in CUBREN_MILICIAS else 0
            milicia -= por_milicia
            fila["categorias"][c] = {"autorizado": a, "existente": existe, "reserva": por_reserva, "milicia": por_milicia,
                                     "deficit": falta - por_reserva - por_milicia}
        fila["especialidades"] = {e: {"autorizado": n, "existente": math.floor(n * cobertura * fuerza + 1e-9)}
                                  for e, n in aut["especialidades"].items()}
        fila["cobertura_pilotos"] = _cobertura(fila["categorias"]["pilotos"])
        fila["cobertura_tecnicos"] = _cobertura(fila["categorias"]["tecnicos"])
        filas.append(fila)
    total = {c: {k: sum(f["categorias"][c][k] for f in filas) for k in ("autorizado", "existente", "reserva", "milicia", "deficit")}
             for c in CATEGORIAS}
    return {"bando": bando, "config": {**cfg, "tripulaciones": tripulaciones}, "unidades": filas, "total": total,
            "reserva_restante": reserva, "milicia_restante": milicia}


def _cobertura(cat: dict) -> float:
    """Fraccion cubierta (existentes + reservas + milicia) de una categoria; 1 si no hay plantilla."""
    if not cat["autorizado"]:
        return 1.0
    return round(min(1.0, (cat["existente"] + cat["reserva"] + cat["milicia"]) / cat["autorizado"]), 3)


def cobertura_aerea(unidades, escenario, bando: str) -> tuple[float, float, int]:
    """(cobertura de pilotos, cobertura de tecnicos, tripulaciones por aeronave) de la aviacion del bando; sin grupos
    aereos todavia, la cobertura de la plantilla del bando."""
    p = partes(unidades, escenario, bando)
    aereas = [f for f in p["unidades"] if f["categorias"]["pilotos"]["autorizado"]]
    if not aereas:
        c = max(0.0, min(100.0, float(p["config"]["cobertura"]))) / 100.0
        return c, c, p["config"]["tripulaciones"]

    def cob(cat):
        aut = sum(f["categorias"][cat]["autorizado"] for f in aereas)
        ok = sum(f["categorias"][cat]["existente"] + f["categorias"][cat]["reserva"] + f["categorias"][cat]["milicia"] for f in aereas)
        return min(1.0, ok / aut) if aut else 1.0

    return cob("pilotos"), cob("tecnicos"), p["config"]["tripulaciones"]


def coberturas(unidades, escenario, bando: str) -> dict[int, tuple[float, float]]:
    """{unidad_id: (cobertura de pilotos, cobertura de tecnicos)} del bando."""
    return {f["unidad_id"]: (f["cobertura_pilotos"], f["cobertura_tecnicos"]) for f in partes(unidades, escenario, bando)["unidades"]}
