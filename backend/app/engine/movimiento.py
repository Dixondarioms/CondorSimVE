"""Simulacion del movimiento de una unidad durante un turno (1 h), compartida por
la resolucion de ordenes y la previsualizacion.

- Terrestres: el terreno frena (bosque, montana...), el agua bloquea y los rios se vadean a pie;
  los vehiculos pesados solo cruzan un rio sobre un puente o vado (obra) tendido por ingenieros.
- Navales: solo navegan sobre agua.
- Aereas: vuelan en linea recta ignorando el terreno.
- El clima y la penalizacion de peso de la plataforma modifican la velocidad, y el combustible
  limita la distancia real.
"""

from dataclasses import dataclass, field

from app.engine import catalogo, geo, relieve
from app.engine import clima as clima_mod
from app.terreno import FACTOR_MOVIMIENTO, Terreno

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


def obra_en(obras, lat: float, lon: float):
    """La mejor obra (la de mayor factor de velocidad) que cubre el punto, o None."""
    mejor = None
    for o in obras:
        if geo.distancia_km(o.lat, o.lon, lat, lon) <= o.radio_km:
            if mejor is None or FACTOR_OBRA[o.tipo] > FACTOR_OBRA[mejor.tipo]:
                mejor = o
    return mejor


def factor_terreno(unidad, clase_terreno: str, obras, lat: float, lon: float) -> float:
    """Fraccion de la velocidad que conserva `unidad` sobre ese terreno (0 = no puede pasar)."""
    if unidad.tipo == "aerea":
        return 1.0
    if unidad.tipo == "naval":
        return 1.0 if clase_terreno == "agua" else 0.0
    base = FACTOR_MOVIMIENTO.get(clase_terreno, 1.0)
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
                factor = factor_terreno(unidad, clase_terreno, obras, sig_lat, sig_lon)
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


def _cerrar(mov: Movimiento, lat: float, lon: float, autonomia: float) -> Movimiento:
    mov.lat, mov.lon = lat, lon
    if mov.ruta[-1] != [lat, lon]:
        mov.ruta.append([lat, lon])
    mov.combustible_gastado = mov.km_reales / autonomia * 100.0
    return mov
