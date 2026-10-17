"""Simulacion del movimiento de una unidad durante un turno (1 h), compartida por
la resolucion de ordenes y la previsualizacion.

- Terrestres: el terreno frena (bosque, montana...), el agua bloquea y los rios se vadean a pie;
  los vehiculos pesados solo cruzan un rio sobre un puente o vado (obra) tendido por ingenieros.
- Navales: solo navegan sobre agua.
- Aereas: vuelan en linea recta ignorando el terreno.
- El clima y la penalizacion de peso de la plataforma modifican la velocidad, y el combustible
  limita la distancia real.
"""

import json
import math
from dataclasses import dataclass, field

from app.engine import catalogo, geo, relieve
from app.engine import clima as clima_mod
from app.terreno import FACTOR_MOVIMIENTO, FACTOR_PUENTE, FACTOR_VIA, Terreno

TURNO_DURACION_HORAS = 1.0
PASO_KM = 1.0
OBRA_RADIO_KM = 0.8
# Velocidad relativa al cruzar un rio por una obra: el puente casi no frena; el vado, si.
FACTOR_OBRA = {"puente": 0.9, "vado": 0.5}


@dataclass
class Movimiento:
    lat: float
    lon: float
    km_reales: float = 0.0
    ruta: list = field(default_factory=list)  # [[lat, lon], ...] desde el origen
    nota: str = ""
    combustible_gastado: float = 0.0  # puntos porcentuales


MAX_PUNTOS_RECORRIDO = 150


def recorrido_json(mov: "Movimiento") -> str | None:
    """El camino del turno para guardarlo en la unidad (None si no se movio); a lo sumo MAX_PUNTOS_RECORRIDO puntos."""
    if mov.km_reales <= 0 or len(mov.ruta) < 2:
        return None
    ruta = mov.ruta
    if len(ruta) > MAX_PUNTOS_RECORRIDO:
        paso = (len(ruta) - 1) / (MAX_PUNTOS_RECORRIDO - 1)
        ruta = [ruta[round(i * paso)] for i in range(MAX_PUNTOS_RECORRIDO)]
    return json.dumps([[round(a, 5), round(b, 5)] for a, b in ruta])


def obra_en(obras, lat: float, lon: float):
    """La mejor obra (la de mayor factor de velocidad) que cubre el punto, o None."""
    mejor = None
    for o in obras:
        if o.tipo not in FACTOR_OBRA:
            continue  # puente de infraestructura cortado (ver engine/infraestructura.py)
        if geo.distancia_km(o.lat, o.lon, lat, lon) <= o.radio_km:
            if mejor is None or FACTOR_OBRA[o.tipo] > FACTOR_OBRA[mejor.tipo]:
                mejor = o
    return mejor


FACTOR_CRATER = 0.6  # un crater en la carretera: se pierde la carretera y se rodea por el terreno


def carretera_cortada(obras, lat: float, lon: float) -> bool:
    return any(o.tipo == "crater" and geo.distancia_km(o.lat, o.lon, lat, lon) <= o.radio_km for o in obras)


def puente_cortado(obras, lat: float, lon: float) -> bool:
    return any(o.tipo == "corte" and geo.distancia_km(o.lat, o.lon, lat, lon) <= o.radio_km for o in obras)


def factor_terreno(unidad, clase_terreno: str, obras, lat: float, lon: float, via: int = 0) -> float:
    """Fraccion de la velocidad que conserva `unidad` sobre ese terreno (0 = no puede pasar). Una carretera (`via`)
    la acelera y, donde cruza un rio o el agua, tiene un puente."""
    if unidad.tipo == "aerea":
        return 1.0
    if unidad.tipo == "naval":
        return 1.0 if clase_terreno == "agua" else 0.0
    base = FACTOR_MOVIMIENTO.get(clase_terreno, 1.0)
    if via and carretera_cortada(obras, lat, lon):
        return base * FACTOR_CRATER  # el corte obliga a dejar la carretera y rodearlo
    if via and clase_terreno in ("rio", "agua"):
        if not puente_cortado(obras, lat, lon):
            return FACTOR_PUENTE
        via = 0  # el puente de la carretera esta cortado: se cruza como si no hubiera carretera
    if via:
        return max(base, FACTOR_VIA.get(via, 1.0))
    if clase_terreno != "rio":
        return base
    ligera = catalogo.obtener(unidad.clase, unidad.tipo).movilidad == "ligera"
    obra = obra_en(obras, lat, lon)
    if obra is not None:
        return max(base, FACTOR_OBRA[obra.tipo]) if ligera else FACTOR_OBRA[obra.tipo]
    return base if ligera else 0.0


def simular(unidad, waypoints: list, terreno: Terreno, clima: str = "despejado", obras=()) -> Movimiento:
    """Devuelve donde termina `unidad` al seguir `waypoints` durante un turno."""
    lat, lon = unidad.lat, unidad.lon
    mov = Movimiento(lat, lon, ruta=[[lat, lon]])
    if unidad.tipo == "base" or unidad.velocidad_kmh <= 0:
        mov.nota = "La unidad no puede moverse."
        return mov

    clase = catalogo.obtener(unidad.clase, unidad.tipo)
    presupuesto = (
        unidad.velocidad_kmh * TURNO_DURACION_HORAS * clima_mod.factor_movimiento(clima, unidad.tipo, unidad.lat, unidad.lon)
        * (1.0 - clase.penalizacion_movilidad)
    )
    # las aeronaves gastan segun su perfil de vuelo: a baja cota rinden menos kilometros por punto de combustible
    autonomia = max(unidad.autonomia_km, 1e-9) / relieve.factor_consumo(unidad)
    km_max_combustible = max(0.0, unidad.combustible) / 100.0 * autonomia
    aerea = unidad.tipo == "aerea"

    for wp_lat, wp_lon in waypoints:
        while presupuesto > 1e-9:
            restante = geo.distancia_km(lat, lon, wp_lat, wp_lon)
            if restante < 1e-6:
                break
            if km_max_combustible - mov.km_reales <= 1e-9:
                mov.nota = "Avance detenido: sin combustible."
                return _cerrar(mov, lat, lon, autonomia)
            paso = min(max(PASO_KM, presupuesto) if aerea else PASO_KM, restante,
                       km_max_combustible - mov.km_reales)
            sig_lat, sig_lon = geo.avanzar_hacia(lat, lon, wp_lat, wp_lon, paso)

            if aerea:
                factor = 1.0
            else:
                clase_terreno = terreno.clase(sig_lat, sig_lon)
                factor = factor_terreno(unidad, clase_terreno, obras, sig_lat, sig_lon, terreno.via(sig_lat, sig_lon))
            if factor <= 0:
                mov.nota = (
                    "Avance detenido: rio sin puente ni vado (se necesitan ingenieros)."
                    if not aerea and clase_terreno == "rio" else "Avance detenido: terreno intransitable."
                )
                return _cerrar(mov, lat, lon, autonomia)
            costo = paso / factor

            if costo > presupuesto:
                fraccion = presupuesto / costo
                real = paso * fraccion
                lat, lon = geo.avanzar_hacia(lat, lon, sig_lat, sig_lon, real)
                mov.km_reales += real
                presupuesto = 0.0
                break
            presupuesto -= costo
            mov.km_reales += paso
            lat, lon = sig_lat, sig_lon
        mov.ruta.append([lat, lon])
        if presupuesto <= 1e-9:
            break

    return _cerrar(mov, lat, lon, autonomia)


def tiempo_recorrido(unidad, waypoints: list, terreno: Terreno, clima: str = "despejado", obras=(),
                     maximo_km: float = 2500.0) -> dict:
    """Cuanto tarda `unidad` en recorrer TODA la ruta (no solo un turno), con el mismo terreno, carreteras, rios,
    clima y peso que el movimiento: {"km", "horas", "turnos", "bloqueo", "km_combustible"}. Si algo intransitable la
    detiene, "bloqueo" lo explica y las horas son las del tramo que si puede hacer."""
    salida = {"km": 0.0, "horas": 0.0, "turnos": 0, "bloqueo": "", "km_combustible": None}
    if unidad.tipo == "base" or unidad.velocidad_kmh <= 0 or not waypoints:
        salida["bloqueo"] = "La unidad no puede moverse." if waypoints else ""
        return salida
    clase = catalogo.obtener(unidad.clase, unidad.tipo)
    velocidad = (unidad.velocidad_kmh * clima_mod.factor_movimiento(clima, unidad.tipo, unidad.lat, unidad.lon)
                 * (1.0 - clase.penalizacion_movilidad))
    autonomia = max(unidad.autonomia_km, 1e-9) / relieve.factor_consumo(unidad)
    salida["km_combustible"] = round(max(0.0, unidad.combustible) / 100.0 * autonomia, 1)
    aerea = unidad.tipo == "aerea"
    lat, lon = unidad.lat, unidad.lon
    costo = km = 0.0
    for wp_lat, wp_lon in waypoints:
        while km < maximo_km:
            restante = geo.distancia_km(lat, lon, wp_lat, wp_lon)
            if restante < 1e-6:
                break
            paso = restante if aerea else min(PASO_KM, restante)
            sig_lat, sig_lon = geo.avanzar_hacia(lat, lon, wp_lat, wp_lon, paso)
            factor = 1.0 if aerea else factor_terreno(unidad, terreno.clase(sig_lat, sig_lon), obras, sig_lat, sig_lon,
                                                      terreno.via(sig_lat, sig_lon))
            if factor <= 0:
                salida["bloqueo"] = ("Río sin puente ni vado en la ruta: los vehículos pesados no pasan (se necesitan "
                                     "ingenieros o seguir carreteras)." if terreno.clase(sig_lat, sig_lon) == "rio"
                                     else "Terreno intransitable en la ruta.")
                break
            costo += paso / factor
            km += paso
            lat, lon = sig_lat, sig_lon
        if salida["bloqueo"]:
            break
    horas = costo / max(velocidad, 1e-9)
    salida.update(km=round(km, 1), horas=round(horas, 2), turnos=max(1, math.ceil(horas / TURNO_DURACION_HORAS - 1e-9)))
    return salida


def _cerrar(mov: Movimiento, lat: float, lon: float, autonomia: float) -> Movimiento:
    mov.lat, mov.lon = lat, lon
    if mov.ruta[-1] != [lat, lon]:
        mov.ruta.append([lat, lon])
    mov.combustible_gastado = mov.km_reales / autonomia * 100.0
    return mov
