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
# Velocidad elegida de aeronaves y buques (como el acelerador de los simuladores de mando modernos): cuanto mas rapido,
# mas combustible por kilometro. Con «maxima» una aeronave usa la postcombustion; un buque, toda su maquina.
VELOCIDADES = {
    "economica": {"nombre": "Económica", "velocidad": 0.75, "consumo": 0.85},
    "crucero": {"nombre": "Crucero", "velocidad": 1.0, "consumo": 1.0},
    "maxima": {"nombre": "Máxima", "velocidad": 1.3, "consumo": 2.2},
}
PASO_KM = 1.0
OBRA_RADIO_KM = 0.8
# Velocidad relativa al cruzar un rio por una obra: el puente casi no frena; el vado, si.
FACTOR_OBRA = {"puente": 0.9, "vado": 0.5}


def elige_velocidad(u) -> bool:
    """Aeronaves y buques eligen su velocidad (no los misiles ni los torpedos, que van a la suya)."""
    return (getattr(u, "tipo", "") in ("aerea", "naval") and not catalogo.es_misil(u)
            and getattr(u, "clase", None) != "torpedo" and not catalogo.obtener(u.clase, u.tipo).civil)


def modo_velocidad(u) -> str | None:
    if not elige_velocidad(u):
        return None
    m = getattr(u, "velocidad_modo", None)
    return m if m in VELOCIDADES else "crucero"


def factor_velocidad(u) -> float:
    m = modo_velocidad(u)
    return VELOCIDADES[m]["velocidad"] if m else 1.0


def factor_consumo_velocidad(u) -> float:
    m = modo_velocidad(u)
    return VELOCIDADES[m]["consumo"] if m else 1.0


def aplicar_tramo(u, tramo: dict | None) -> None:
    """La velocidad y la altura que la orden fijo para el tramo que empieza (lo que no fija, sigue como esta)."""
    if not tramo:
        return
    if tramo.get("velocidad") in VELOCIDADES and elige_velocidad(u):
        u.velocidad_modo = tramo["velocidad"]
    if tramo.get("perfil") in relieve.perfiles_permitidos(u):
        u.perfil_vuelo = tramo["perfil"]


def tramos_de(orden) -> list:
    try:
        d = json.loads(getattr(orden, "detalle", None) or "{}")
    except ValueError:
        return []
    t = d.get("tramos") if isinstance(d, dict) else None
    return t if isinstance(t, list) else []


@dataclass
class Movimiento:
    lat: float
    lon: float
    km_reales: float = 0.0
    ruta: list = field(default_factory=list)  # [[lat, lon], ...] desde el origen
    nota: str = ""
    combustible_gastado: float = 0.0  # puntos porcentuales
    alcanzados: int = 0  # waypoints a los que llego (tiempo real: los que ya no le faltan)


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


PUENTE_CERCA_KM = (0.15, 0.3)  # radios en que se busca el puente de la carretera junto a un punto de rio


def puente_cercano(terreno: Terreno, lat: float, lon: float, obras=()) -> bool:
    """Hay un puente de carretera (rio o agua con via, no cortado) a pocos cientos de metros: la ruta de la unidad pasa
    junto al puente y lo usa (las grillas de terreno y de carreteras no coinciden al metro con la ruta trazada)."""
    for radio in PUENTE_CERCA_KM:
        d_lat = radio / 111.32
        d_lon = radio / (111.32 * max(0.05, math.cos(math.radians(lat))))
        for i in range(8):
            a = i * math.pi / 4
            p_lat, p_lon = lat + d_lat * math.sin(a), lon + d_lon * math.cos(a)
            if terreno.via(p_lat, p_lon) and terreno.clase(p_lat, p_lon) in ("rio", "agua") \
                    and not puente_cortado(obras, p_lat, p_lon):
                return True
    return False


def factor_en(unidad, terreno: Terreno, obras, lat: float, lon: float) -> float:
    """factor_terreno en un punto del mapa; un rio intransitable junto a un puente de carretera se cruza por el puente."""
    clase_terreno = terreno.clase(lat, lon)
    f = factor_terreno(unidad, clase_terreno, obras, lat, lon, terreno.via(lat, lon))
    if f <= 0 and clase_terreno == "rio" and unidad.tipo == "terrestre" and puente_cercano(terreno, lat, lon, obras):
        return FACTOR_PUENTE
    return f


def simular(unidad, waypoints: list, terreno: Terreno, clima: str = "despejado", obras=(),
            horas: float = TURNO_DURACION_HORAS) -> Movimiento:
    """Devuelve donde termina `unidad` al seguir `waypoints` durante `horas` (un turno si no se indica)."""
    lat, lon = unidad.lat, unidad.lon
    mov = Movimiento(lat, lon, ruta=[[lat, lon]])
    if unidad.tipo == "base" or unidad.velocidad_kmh <= 0:
        mov.nota = "La unidad no puede moverse."
        return mov

    clase = catalogo.obtener(unidad.clase, unidad.tipo)
    from app.engine import sistemas  # importacion tardia: propulsion dañada (engine/sistemas.py)

    propulsion = sistemas.factor(unidad, "propulsion")
    if propulsion <= 0:
        mov.nota = f"{sistemas.nombre(unidad, 'propulsion')} fuera de servicio: la unidad no puede moverse."
        return mov
    presupuesto = (
        unidad.velocidad_kmh * horas * clima_mod.factor_movimiento(clima, unidad.tipo, unidad.lat, unidad.lon)
        * (1.0 - clase.penalizacion_movilidad) * propulsion * factor_velocidad(unidad)
    )
    # las aeronaves gastan segun su perfil de vuelo (a baja cota rinden menos kilometros por punto de combustible) y,
    # con los buques, segun la velocidad elegida
    autonomia = max(unidad.autonomia_km, 1e-9) / (relieve.factor_consumo(unidad) * factor_consumo_velocidad(unidad))
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
                factor = factor_en(unidad, terreno, obras, sig_lat, sig_lon)
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
        if geo.distancia_km(lat, lon, wp_lat, wp_lon) < 1e-6:
            mov.alcanzados += 1
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
    from app.engine import sistemas  # importacion tardia

    velocidad = (unidad.velocidad_kmh * clima_mod.factor_movimiento(clima, unidad.tipo, unidad.lat, unidad.lon)
                 * (1.0 - clase.penalizacion_movilidad) * sistemas.factor(unidad, "propulsion") * factor_velocidad(unidad))
    if velocidad <= 0:
        salida["bloqueo"] = "Propulsión fuera de servicio: la unidad no puede moverse."
        return salida
    autonomia = max(unidad.autonomia_km, 1e-9) / (relieve.factor_consumo(unidad) * factor_consumo_velocidad(unidad))
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
            factor = 1.0 if aerea else factor_en(unidad, terreno, obras, sig_lat, sig_lon)
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
