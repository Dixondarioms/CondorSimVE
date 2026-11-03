"""Misiles balisticos y defensa antimisil del Cóndor (como en los simuladores de mando modernos).

- Un lanzador de misiles balisticos (clase lanzador_balistico, tipo Iskander) emite «lanzar» contra un blanco de
  superficie que su bando ve, a ALCANCE_KM o menos. Cada misil vuela por separado (como las salvas: engine/misiles.py)
  con una trayectoria balistica: no se lo guia despues del lanzamiento, cae en el punto donde estaba el blanco al
  lanzar (si el blanco se movio mas de RADIO_IMPACTO_KM, no le pega). Es muy rapido (VELOCIDAD_KMH): unos minutos de
  vuelo. Fases: ascenso, medio curso y terminal (el ultimo FASE_TERMINAL del recorrido).
- Al lanzar llega la alerta temprana al bando del blanco con la hora estimada del impacto.
- Ni la antiaerea comun, ni las patrullas, ni la defensa de punto de los buques pueden con el: solo los sistemas
  antimisil (ANTIMISIL: S-300VM, S-400, Patriot, HQ-9 y los destructores con SM-3/SM-6) y solo en la fase terminal,
  a su alcance, con sus canales y su probabilidad por interceptor. Cada interceptor gasta un misil de la bateria (o
  MUNICION_POR_INTERCEPTOR % de un buque).
"""

from __future__ import annotations

import json

from app.engine import catalogo, geo

ALCANCE_KM = 500.0
VELOCIDAD_KMH = 5000.0
MUNICION_POR_MISIL = 25.0
MAX_MISILES = 4
PK = 0.9
RADIO_IMPACTO_KM = 1.5
LLEGADA_KM = 1.0
FASE_TERMINAL = 0.3  # el ultimo 30 % del recorrido
CICLO_ANTIMISIL_S = 20.0
MUNICION_POR_INTERCEPTOR = 3.0
ANTIMISIL = {  # por modelo: alcance contra balisticos (km), canales y probabilidad por interceptor
    "s300vm": {"km": 40.0, "canales": 2, "pk": 0.55},
    "s400": {"km": 60.0, "canales": 2, "pk": 0.6},
    "patriot": {"km": 30.0, "canales": 2, "pk": 0.65},
    "hq9": {"km": 25.0, "canales": 1, "pk": 0.45},
    "arleigh_burke": {"km": 80.0, "canales": 2, "pk": 0.6},
    "ticonderoga": {"km": 80.0, "canales": 2, "pk": 0.6},
}


def es_balistico(u) -> bool:
    return getattr(u, "clase", None) == "misil_balistico"


def lanza(u) -> bool:
    return getattr(u, "clase", None) == "lanzador_balistico"


def antimisil(u) -> dict | None:
    return ANTIMISIL.get(getattr(u, "modelo", None) or "")


def datos(m) -> dict:
    try:
        d = json.loads(getattr(m, "armamento_json", None) or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def recorrido(m) -> float:
    """Fraccion del recorrido ya volada (0 al lanzar, 1 al llegar)."""
    d = datos(m)
    total = float(d.get("total_km") or 0.0)
    if total <= 0 or m.mision_lat is None:
        return 0.0
    falta = geo.distancia_km(m.lat, m.lon, m.mision_lat, m.mision_lon)
    return max(0.0, min(1.0, 1.0 - falta / total))


def fase(m) -> str:
    f = recorrido(m)
    return "ascenso" if f < 0.25 else "medio curso" if f < 1.0 - FASE_TERMINAL else "terminal"


def apogeo_km(total_km: float) -> float:
    return max(30.0, min(150.0, total_km / 4.0))


def minutos_de_vuelo(km: float) -> float:
    return km / VELOCIDAD_KMH * 60.0


def info(m) -> dict | None:
    """Para la pantalla (al bando que lo lanzo): fase, minutos al impacto, origen y punto de impacto."""
    if not es_balistico(m) or m.mision_lat is None:
        return None
    d = datos(m)
    falta = geo.distancia_km(m.lat, m.lon, m.mision_lat, m.mision_lon)
    return {"fase": fase(m), "minutos": round(minutos_de_vuelo(falta), 1), "origen": d.get("origen"),
            "impacto": [m.mision_lat, m.mision_lon], "apogeo_km": round(apogeo_km(float(d.get("total_km") or 0.0)))}


def error_de_lanzamiento(lanzador, blanco, misiles: int | None) -> str | None:
    if not lanza(lanzador) or lanzador.estado != "activa":
        return "Esta unidad no lanza misiles balísticos."
    if not misiles or not 1 <= misiles <= MAX_MISILES:
        return f"Una salva tiene entre 1 y {MAX_MISILES} misiles."
    clase = catalogo.obtener(lanzador.clase, lanzador.tipo)
    if clase.despliegue_turnos and lanzador.despliegue_restante > 0:
        return "Desplegando el lanzador tras moverse."
    if blanco is None or blanco.bando == lanzador.bando or blanco.estado != "activa":
        return "Blanco inválido o ya fuera de combate."
    if blanco.tipo == "aerea" and not getattr(blanco, "en_tierra", False):
        return "Un misil balístico no ataca aeronaves en vuelo."
    d = geo.distancia_km(lanzador.lat, lanzador.lon, blanco.lat, blanco.lon)
    if d > ALCANCE_KM:
        return f"Blanco fuera de alcance ({d:.0f} km > {ALCANCE_KM:.0f} km)."
    if lanzador.municion + 1e-6 < MUNICION_POR_MISIL * misiles:
        return f"Munición insuficiente para {misiles} misil(es)."
    return None


def crear(lanzador, blanco, misiles: int) -> list:
    """Una unidad por misil, sobre el lanzador, con el punto de impacto fijo (sin agregarlas a la sesion)."""
    from app.models.unidad import Unidad

    clase = catalogo.CLASES["misil_balistico"]
    total = geo.distancia_km(lanzador.lat, lanzador.lon, blanco.lat, blanco.lon)
    salida = []
    for i in range(misiles):
        u = Unidad(escenario_id=lanzador.escenario_id, nombre=f"Balístico {i + 1}/{misiles} de {lanzador.nombre}"[:120],
                   bando=lanzador.bando, tipo="aerea", clase=clase.id, aeronaves=1, echelon="",
                   lat=lanzador.lat + 0.003 * i, lon=lanzador.lon, fuerza=100.0, velocidad_kmh=VELOCIDAD_KMH,
                   alcance_km=clase.alcance_km, deteccion_km=0.0, combustible=100.0, municion=100.0,
                   autonomia_km=ALCANCE_KM * 1.5, en_tierra=False, blanco_id=blanco.id, mision="impacto",
                   mision_lat=blanco.lat, mision_lon=blanco.lon, estado="activa",
                   sidc=catalogo.generar_sidc(lanzador.bando, clase))
        u.armamento_json = json.dumps({"salva": misiles, "pk": PK, "balistico": True,
                                       "origen": [round(lanzador.lat, 5), round(lanzador.lon, 5)], "total_km": round(total, 1)})
        salida.append(u)
    return salida
