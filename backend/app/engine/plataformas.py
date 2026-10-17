"""Plataformas aereas: ficha tecnica de cada modelo, largo de las pistas y conversion de unidades.

Ficha tecnica (`FICHAS`, por modelo; los tipos del catalogo propio la traen del instructor o la heredan de su clase):
roles que puede cumplir, velocidad en ruta y maxima (nudos), radio de accion o distancia eficaz (millas nauticas),
techo (pies), combustible interno y consumo en ruta (kg y kg/h), oxigeno liquido (LOX, litros y litros por hora de
la tripulacion; 0 = genera su oxigeno a bordo, OBOGS), carrera de despegue y de aterrizaje a peso de combate (m) y
tripulacion por aeronave. Son valores de referencia aproximados (fuentes abiertas), didacticos y ajustables.

Pistas: el largo de la pista de una base aerea sale del plano del aerodromo (frontend/static/geo/aerodromos, la pista
mas larga a <= 4 km de la base), o lo fija el instructor (Unidad.pista_m); si no hay plano, PISTA_POR_DEFECTO_M. La
pista util se acorta con el dano de la pista. Una aeronave no despega ni aterriza donde su carrera no entra (los
helicopteros y el F-35B no necesitan pista; los portaaviones tienen catapulta y cable: alli rige lo embarcable).

Unidades: el motor trabaja en km, km/h y metros; la interfaz muestra en nudos, millas nauticas y pies a la aviacion,
la defensa aerea y la armada (ver logica.js, `medida`), y en km a las fuerzas terrestres.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path

from app.engine import catalogo, geo

KM_POR_NM = 1.852
M_POR_FT = 0.3048
KMH_POR_KT = 1.852
PISTA_POR_DEFECTO_M = 3000.0
RADIO_AERODROMO_KM = 4.0  # una base aerea usa el plano del aerodromo a esta distancia o menos
AERODROMOS = Path(__file__).resolve().parents[3] / "frontend" / "static" / "geo" / "aerodromos"
ROLES = {"CAP": "Patrulla aérea de combate", "INTERDICCION": "Interdicción", "CAS": "Apoyo aéreo cercano",
         "SEAD": "Supresión de defensas", "RECO": "Reconocimiento", "GE": "Guerra electrónica", "ESCOLTA": "Escolta",
         "TRASLADO": "Traslado", "AAR": "Reabastecimiento en vuelo", "AEW": "Alerta temprana y control",
         "SAR": "Búsqueda y salvamento", "TRANSPORTE": "Transporte y asalto"}


@dataclass(frozen=True)
class Ficha:
    roles: tuple[str, ...]
    crucero_kt: float  # velocidad en ruta
    max_kt: float
    radio_nm: float  # radio de accion (ida, accion y vuelta con reserva) o distancia eficaz
    techo_ft: float
    combustible_kg: float  # interno
    consumo_kg_h: float  # en ruta
    lox_l: float  # oxigeno liquido a bordo (0 = OBOGS: lo genera a bordo)
    lox_l_h: float  # consumo de la tripulacion
    despegue_m: float  # carrera de despegue a peso de combate (0 = vertical)
    aterrizaje_m: float
    tripulacion: int  # por aeronave (0 = no tripulada)
    transferible_kg: float = 0.0  # cisternas: combustible que puede entregar
    nota: str = ""
    disponibilidad: float = 0.0  # fraccion de la flota lista para volar (0 = la de su clase; engine/disponibilidad.py)
    falla_h: float = 0.0  # probabilidad de falla de una aeronave por hora de vuelo (0 = la de su clase)


def _f(roles, crucero, maxima, radio, techo, comb, consumo, lox, lox_h, desp, aterr, trip, **kw) -> Ficha:
    return Ficha(tuple(roles.split()), crucero, maxima, radio, techo, comb, consumo, lox, lox_h, desp, aterr, trip, **kw)


FICHAS: dict[str, Ficha] = {
    # aviacion venezolana
    "f16": _f("CAP INTERDICCION CAS ESCOLTA", 460, 1150, 300, 50000, 3160, 1500, 5, 0.5, 800, 900, 1),
    "su30": _f("CAP INTERDICCION CAS SEAD ESCOLTA", 480, 1150, 800, 56800, 9640, 2900, 10, 1.0, 750, 750, 2),
    "ataque_ligero": _f("CAS INTERDICCION RECO", 350, 430, 250, 42000, 1200, 300, 3, 0.6, 440, 530, 2),
    "helo_ataque": _f("CAS ESCOLTA RECO", 140, 162, 160, 18000, 1500, 650, 0, 0, 0, 0, 2),
    "helo_transporte": _f("TRANSPORTE SAR TRASLADO", 130, 135, 250, 19700, 2600, 750, 0, 0, 0, 0, 3),
    "uav_reco": _f("RECO", 60, 80, 50, 15000, 20, 4, 0, 0, 150, 150, 0),
    "uav_armado": _f("RECO CAS INTERDICCION", 90, 110, 110, 18000, 80, 12, 0, 0, 400, 400, 0),
    "merodeadora": _f("INTERDICCION SEAD", 95, 100, 80, 10000, 10, 6, 0, 0, 0, 0, 0, nota="Se lanza desde un riel"),
    "ge_aereo": _f("GE", 300, 330, 900, 28000, 20000, 2500, 25, 2.5, 1100, 1000, 8),
    "caza_embarcado": _f("CAP INTERDICCION ESCOLTA", 480, 1000, 390, 50000, 6000, 3200, 10, 0.5, 900, 900, 1,
                         nota="En el portaaviones despega con catapulta y aterriza con cable"),
    # aeronaves de EE. UU. de la plantilla del 3 de enero de 2026
    "f22": _f("CAP ESCOLTA", 520, 1300, 590, 65000, 8200, 3500, 0, 0, 450, 900, 1),
    "f35a": _f("CAP INTERDICCION SEAD ESCOLTA", 480, 920, 590, 50000, 8280, 3000, 0, 0, 900, 1000, 1),
    "f35b": _f("CAP INTERDICCION CAS SEAD ESCOLTA", 480, 920, 450, 50000, 6125, 3000, 0, 0, 150, 0, 1,
               nota="STOVL: despega en carrera corta y aterriza en vertical"),
    "fa18ef": _f("CAP INTERDICCION CAS ESCOLTA AAR", 490, 1030, 390, 50000, 6530, 3300, 0, 0, 1000, 1000, 1),
    "ea18g": _f("GE SEAD ESCOLTA", 470, 1030, 390, 50000, 6530, 3500, 0, 0, 1000, 1000, 2),
    "b1b": _f("INTERDICCION", 490, 720, 2500, 60000, 120000, 9000, 25, 4.0, 2000, 1400, 4),
    "p8a": _f("RECO INTERDICCION", 440, 490, 1200, 41000, 34000, 3000, 0, 0, 2200, 1500, 9),
    "e2d": _f("AEW", 300, 350, 750, 34700, 5600, 800, 0, 0, 600, 600, 5),
    "e3g": _f("AEW", 420, 460, 870, 41000, 70000, 6000, 0, 0, 3000, 2000, 20),
    "rc135": _f("RECO GE", 430, 500, 2000, 42000, 60000, 5000, 0, 0, 3000, 2000, 27),
    "ec130h": _f("GE", 300, 320, 1000, 25000, 20000, 2300, 30, 3.0, 1100, 900, 13),
    "kc135": _f("AAR", 460, 500, 1300, 50000, 90000, 6000, 0, 0, 2700, 1800, 3, transferible_kg=68000),
    "rq170": _f("RECO", 380, 450, 1000, 50000, 4000, 600, 0, 0, 1500, 1500, 0),
    "mq9": _f("RECO CAS INTERDICCION", 170, 240, 1000, 50000, 1800, 120, 0, 0, 700, 700, 0),
    "lucas": _f("INTERDICCION", 95, 100, 430, 10000, 30, 8, 0, 0, 0, 0, 0, nota="Se lanza desde un riel o una catapulta"),
    "mh47g": _f("TRANSPORTE SAR TRASLADO", 140, 170, 370, 18000, 3640, 1300, 0, 0, 0, 0, 4),
    "mh60m": _f("TRANSPORTE SAR TRASLADO", 150, 175, 275, 19000, 2420, 600, 0, 0, 0, 0, 4),
    "mh60dap": _f("CAS ESCOLTA", 150, 175, 250, 19000, 2420, 650, 0, 0, 0, 0, 4),
    "ah6m": _f("CAS ESCOLTA", 120, 160, 100, 18000, 230, 110, 0, 0, 0, 0, 2),
    "mh6m": _f("TRANSPORTE TRASLADO", 120, 160, 100, 18000, 230, 110, 0, 0, 0, 0, 2),
}

# para los tipos del catalogo propio sin ficha: lo propio de su clase
_POR_CLASE = {
    "caza": dict(roles="CAP INTERDICCION ESCOLTA", despegue=800, aterrizaje=900, techo=50000, tripulacion=1, lox=5),
    "ataque": dict(roles="INTERDICCION CAS", despegue=900, aterrizaje=900, techo=40000, tripulacion=2, lox=5),
    "helicoptero": dict(roles="CAS ESCOLTA", despegue=0, aterrizaje=0, techo=18000, tripulacion=2, lox=0),
    "helicoptero_artillado": dict(roles="TRANSPORTE SAR", despegue=0, aterrizaje=0, techo=18000, tripulacion=3, lox=0),
    "avion_ge": dict(roles="GE", despegue=1100, aterrizaje=1000, techo=30000, tripulacion=6, lox=20),
    "alerta_temprana": dict(roles="AEW", despegue=1500, aterrizaje=1200, techo=35000, tripulacion=10, lox=0),
    "cisterna": dict(roles="AAR", despegue=2500, aterrizaje=1800, techo=45000, tripulacion=3, lox=0),
    "dron_reconocimiento": dict(roles="RECO", despegue=300, aterrizaje=300, techo=15000, tripulacion=0, lox=0),
    "dron_ataque": dict(roles="RECO CAS", despegue=500, aterrizaje=500, techo=20000, tripulacion=0, lox=0),
    "municion_merodeadora": dict(roles="INTERDICCION", despegue=0, aterrizaje=0, techo=10000, tripulacion=0, lox=0),
}


def ficha_de_modelo(modelo) -> Ficha | None:
    """La ficha del modelo (FICHAS, o la que cargo el instructor para un tipo propio) o una derivada de su clase y
    de sus valores de juego (velocidad, autonomia)."""
    if modelo is None or catalogo.CLASES[modelo.clase].tipo != "aerea" or catalogo.CLASES[modelo.clase].misil:
        return None
    if modelo.id in FICHAS:
        return FICHAS[modelo.id]
    propia = FICHAS_PROPIAS.get(modelo.id)
    if propia is not None:
        return propia
    c = _POR_CLASE.get(modelo.clase, _POR_CLASE["caza"])
    crucero = modelo.velocidad_kmh * 0.85 / KMH_POR_KT
    horas = modelo.autonomia_km / max(1.0, modelo.velocidad_kmh * 0.85)
    combustible = 3000.0 if c["tripulacion"] else 100.0
    return Ficha(tuple(c["roles"].split()), round(crucero), round(modelo.velocidad_kmh / KMH_POR_KT),
                 round(modelo.autonomia_km * 0.35 / KM_POR_NM), c["techo"], combustible, round(combustible / max(0.5, horas)),
                 c["lox"], 0.5 * c["tripulacion"] if c["lox"] else 0.0, c["despegue"], c["aterrizaje"], c["tripulacion"],
                 nota="Valores estimados a partir de su clase")


# Fuentes: valores de referencia de fuentes abiertas; F-22, F-35, F/A-18, MH-47G, MH-60M y AH/MH-6M revisados con
# los documentos de capacidades que aporto el usuario (radio de accion, velocidad maxima, combustible interno, techo).
# fichas cargadas por el instructor para sus tipos propios (engine/modelos_usuario.py las llena)
FICHAS_PROPIAS: dict[str, Ficha] = {}
CAMPOS_FICHA = ("roles", "crucero_kt", "max_kt", "radio_nm", "techo_ft", "combustible_kg", "consumo_kg_h", "lox_l",
                "lox_l_h", "despegue_m", "aterrizaje_m", "tripulacion", "disponibilidad", "falla_h")


def ficha_desde_dict(datos: dict, base: Ficha) -> Ficha:
    """Ficha a partir de lo que cargo el instructor; lo que falta, de `base`."""
    cambios = {}
    for campo in CAMPOS_FICHA:
        if campo not in datos or datos[campo] in (None, ""):
            continue
        if campo == "roles":
            roles = datos[campo].split() if isinstance(datos[campo], str) else list(datos[campo])
            cambios["roles"] = tuple(r for r in (x.upper() for x in roles) if r in ROLES)
        elif campo == "tripulacion":
            cambios[campo] = max(0, min(60, int(datos[campo])))
        elif campo in ("disponibilidad", "falla_h"):
            cambios[campo] = max(0.0, min(1.0, float(datos[campo])))
        else:
            cambios[campo] = max(0.0, min(200000.0, float(datos[campo])))
    return replace(base, **cambios)


def ficha(unidad) -> Ficha | None:
    return ficha_de_modelo(catalogo.MODELOS.get(getattr(unidad, "modelo", "") or ""))


def ficha_dict(f: Ficha | None) -> dict | None:
    if f is None:
        return None
    d = asdict(f)
    d["roles"] = list(f.roles)
    d["roles_nombres"] = [ROLES[r] for r in f.roles if r in ROLES]
    d["autonomia_h"] = round(f.combustible_kg / f.consumo_kg_h, 1) if f.consumo_kg_h else None
    d["lox_horas"] = round(f.lox_l / f.lox_l_h, 1) if f.lox_l_h else None
    return d


# ---------------------------------------------------------------------------------------------- pistas
@lru_cache(maxsize=1)
def _indice_aerodromos() -> tuple[tuple[float, float, float, str], ...]:
    """(lat, lon, pista mas larga en m, nombre) de cada aerodromo con plano."""
    filas = []
    for archivo in sorted(AERODROMOS.glob("*.json")) if AERODROMOS.is_dir() else []:
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        largo = max((f.get("properties", {}).get("largo_m") or 0 for f in datos.get("features", [])
                     if f.get("properties", {}).get("tipo") == "pista"), default=0)
        for b in datos.get("bases", []):
            if largo and b.get("lat") is not None:
                filas.append((b["lat"], b["lon"], float(largo), b.get("nombre") or b.get("icao") or archivo.stem))
    return tuple(filas)


def pista_del_plano(lat: float, lon: float) -> tuple[float, str] | None:
    """Largo de la pista mas larga del aerodromo a <= RADIO_AERODROMO_KM, y su nombre."""
    cerca = [(geo.distancia_km(lat, lon, a, b), largo, n) for a, b, largo, n in _indice_aerodromos()
             if abs(a - lat) < 0.1 and abs(b - lon) < 0.1]
    cerca = [c for c in cerca if c[0] <= RADIO_AERODROMO_KM]
    if not cerca:
        return None
    _, largo, nombre = min(cerca)
    return largo, nombre


def largo_pista(base) -> float | None:
    """Largo de la pista de una base aerea (None si no es una base aerea: el portaaviones tiene catapulta)."""
    if getattr(base, "clase", "") == "punto_recobre":  # PRO: la pista que tenga (sin ella, solo helicopteros)
        pista = float(getattr(base, "pista_m", None) or 0.0)
        if pista and getattr(base, "lat", None) is not None and getattr(base, "lon", None) is not None:
            from app.engine import ori  # fuera de un tramo apto (ORI) o de un aerodromo la pista no sirve
            if ori.error_de_ubicacion(base.lat, base.lon, pista):
                return 0.0
        return pista
    if getattr(base, "clase", "") != "base_aerea":
        return None
    if getattr(base, "pista_m", None):
        return float(base.pista_m)
    if getattr(base, "lat", None) is None or getattr(base, "lon", None) is None:
        return PISTA_POR_DEFECTO_M
    plano = pista_del_plano(base.lat, base.lon)
    return plano[0] if plano else PISTA_POR_DEFECTO_M


def pista_util(base) -> float | None:
    """La pista que queda usable con su dano (los craters y escombros acortan la carrera disponible)."""
    largo = largo_pista(base)
    if largo is None:
        return None
    return round(largo * max(0.0, 1.0 - (getattr(base, "dano_pista", 0.0) or 0.0) / 100.0))


def error_de_pista(modelo, base, aterrizar: bool = False) -> str | None:
    """Motivo por el que el modelo no puede despegar de (o aterrizar en) la pista de esa base (None si puede)."""
    f = ficha_de_modelo(modelo)
    util = pista_util(base)
    if f is None or util is None:
        return None
    necesita = f.aterrizaje_m if aterrizar else f.despegue_m
    if necesita and util <= 0:
        return f"{base.nombre} no tiene pista: solo operan helicópteros y aeronaves de despegue vertical."
    if necesita and util < necesita:
        accion = "aterrizar" if aterrizar else "despegar"
        return (f"La pista útil de {base.nombre} ({util:.0f} m) es más corta que la carrera para {accion} de "
                f"{modelo.corto} ({necesita:.0f} m).")
    return None


# ---------------------------------------------------------------------------------------------- logistica de mision
def requerimientos(modelo, aeronaves: int, horas: float, factor_consumo: float = 1.0, reserva: float = 0.2) -> dict | None:
    """Combustible (kg) y oxigeno liquido (l) para volar `horas` con `aeronaves`, con la reserva reglamentaria."""
    f = ficha_de_modelo(modelo)
    if f is None:
        return None
    n = max(1, int(aeronaves or 1))
    comb_ac = f.consumo_kg_h * horas * factor_consumo * (1 + reserva)
    lox_ac = f.lox_l_h * horas * (1 + reserva)
    return {
        "combustible_kg": round(comb_ac * n), "combustible_por_aeronave_kg": round(comb_ac),
        "combustible_interno_kg": f.combustible_kg, "excede_interno": comb_ac > f.combustible_kg,
        "lox_l": round(lox_ac * n, 1), "lox_por_aeronave_l": round(lox_ac, 1), "lox_a_bordo_l": f.lox_l,
        "excede_lox": bool(f.lox_l_h) and lox_ac > f.lox_l, "reserva_pct": round(reserva * 100),
        "tripulantes": f.tripulacion * n,
    }
