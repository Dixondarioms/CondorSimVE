"""Transporte de tropas: unidades anfibias (buque de desembarco), helitransportadas (helicoptero de transporte) y
aerotransportadas (avion de transporte, con paracaidistas).

Una unidad terrestre se **embarca** (orden `embarcar`, objetivo = el transporte propio a <= 3 km) y viaja a bordo:
queda oculta (no se la detecta ni ataca por separado), no recibe ordenes, se mueve con el transporte y sufre parte
del daño que este recibe (o se pierde con el). El transporte **desembarca** (orden `desembarcar`: waypoints de su
ruta y, como ultimo punto, el lugar de desembarco en tierra): al llegar a <= RADIO_DESEMBARCO_KM del punto, las
unidades a bordo aparecen alli; si no llega, sigue navegando o volando hacia el punto en los turnos siguientes.

- El buque de desembarco lleva hasta 3 unidades terrestres de cualquier movilidad; el helicoptero de transporte
  artillado, 1 unidad ligera (infanteria, antiaerea portatil, ingenieros...).
- El punto de desembarco debe ser tierra firme; un buque no puede entrar en el, asi que se acerca por el agua.
- El avion de transporte embarca tropas ligeras en tierra (en una base) y las desembarca al aterrizar. En vuelo lanza
  a los PARACAIDISTAS (orden «paracaidistas»): vuela a la zona de lanzamiento y, a RADIO_SALTO_KM o menos, saltan;
  caen dispersos (hasta DISPERSION_KM del punto), pierden PERDIDA_SALTO puntos de fuerza en el salto y tardan
  REAGRUPAR_S en reagruparse antes de poder combatir. Las demas tropas a bordo no saltan. Lleva CAPACIDAD unidades
  por avion del grupo (segun el modelo). Con tormenta en la zona no se salta.
"""

import math

from app.engine import catalogo, geo

RADIO_EMBARQUE_KM = 3.0
RADIO_DESEMBARCO_KM = 5.0
DANO_A_BORDO = 0.5  # fraccion del daño al transporte que sufren las unidades embarcadas
CAPACIDAD = {"buque_desembarco": 3, "helicoptero_artillado": 1, "avion_transporte": 2}
# unidades por avion de transporte (los chicos y medianos, 1; los grandes, 3; el resto, 2)
CAPACIDAD_MODELO = {"c27j": 1, "an26": 1, "an32": 1, "c295": 1, "cn235": 1, "c212": 1, "bt67": 1, "dhc6": 1, "c208": 1,
                    "emb110": 1, "il76md": 3, "a400m": 3}
SOLO_LIGERAS = {"helicoptero_artillado", "avion_transporte"}
SALTAN = ("paracaidistas",)  # clases que se lanzan en paracaidas
RADIO_SALTO_KM = 2.0
DISPERSION_KM = 1.5
PERDIDA_SALTO = 5.0
REAGRUPAR_S = 1200.0


def es_avion_transporte(u) -> bool:
    return getattr(u, "clase", None) == "avion_transporte"


def capacidad(u) -> int:
    clase = getattr(u, "clase", "") or ""
    if clase == "avion_transporte":  # por avion del grupo
        return CAPACIDAD_MODELO.get(getattr(u, "modelo", "") or "", CAPACIDAD[clase]) * max(1, int(getattr(u, "aeronaves", 1) or 1))
    return CAPACIDAD.get(clase, 0)


def punto_de_embarque(transporte, unidades) -> tuple:
    """Donde suben y bajan las tropas: el avion estacionado lo hace en su base (en la plataforma puede quedar a
    varios km del centro); los demas transportes, donde estan."""
    if es_avion_transporte(transporte) and getattr(transporte, "en_tierra", False) and getattr(transporte, "base_id", None):
        base = next((x for x in unidades if x.id == transporte.base_id), None)
        if base is not None:
            return base.lat, base.lon
    return transporte.lat, transporte.lon


def distancia_embarque_km(u, transporte, unidades) -> float:
    d = geo.distancia_km(u.lat, u.lon, transporte.lat, transporte.lon)
    lat, lon = punto_de_embarque(transporte, unidades)
    return min(d, geo.distancia_km(u.lat, u.lon, lat, lon))


def es_transporte(u) -> bool:
    return capacidad(u) > 0


def embarcada(u) -> bool:
    return getattr(u, "transporte_id", None) is not None


def a_bordo(transporte, unidades) -> list:
    return [x for x in unidades if getattr(x, "transporte_id", None) == transporte.id and x.estado == "activa"]


def error_de_embarque(u, transporte, unidades) -> str | None:
    """Motivo por el que `u` no puede embarcarse en `transporte` (None si puede)."""
    if u.tipo != "terrestre" or u.estado != "activa":
        return "Solo una unidad terrestre activa puede embarcarse."
    if embarcada(u):
        return "La unidad ya esta embarcada."
    if transporte is None or transporte.bando != u.bando or transporte.estado != "activa" or not es_transporte(transporte):
        return "Elija un buque de desembarco, un helicoptero o un avion de transporte propio."
    if es_avion_transporte(transporte) and not getattr(transporte, "en_tierra", False):
        return f"{transporte.nombre} embarca tropas en tierra: aterrícelo antes en una base."
    clase_u = catalogo.obtener(u.clase, u.tipo)
    if transporte.clase in SOLO_LIGERAS and clase_u.movilidad != "ligera":
        return f"{transporte.nombre} solo transporta unidades ligeras (infanteria, antiaerea portatil, ingenieros)."
    if len(a_bordo(transporte, unidades)) >= capacidad(transporte):
        return f"{transporte.nombre} ya lleva su carga maxima ({capacidad(transporte)} unidad(es))."
    d = distancia_embarque_km(u, transporte, unidades)
    if d > RADIO_EMBARQUE_KM:
        return f"El transporte esta a {d:.1f} km: acerquese a menos de {RADIO_EMBARQUE_KM:.0f} km para embarcar."
    return None


def embarcar(u, transporte) -> None:
    u.transporte_id = transporte.id
    u.lat, u.lon = transporte.lat, transporte.lon
    u.mision, u.mision_lat, u.mision_lon = "", None, None


def seguir_transporte(unidades) -> None:
    """Las unidades embarcadas viajan con su transporte (tras el movimiento del turno)."""
    por_id = {x.id: x for x in unidades}
    for x in unidades:
        t = por_id.get(getattr(x, "transporte_id", None))
        if t is not None and x.estado == "activa":
            x.lat, x.lon = t.lat, t.lon


def error_de_desembarco(transporte, punto, terreno, unidades) -> str | None:
    if transporte is None or transporte.estado != "activa" or not es_transporte(transporte):
        return "Solo un buque de desembarco, un helicoptero o un avion de transporte puede desembarcar tropas."
    if not a_bordo(transporte, unidades):
        return f"{transporte.nombre} no lleva unidades a bordo."
    if es_avion_transporte(transporte):
        if getattr(transporte, "en_tierra", False):
            return None  # desembarca donde esta, en la base
        return ("En vuelo, un avión de transporte lanza paracaidistas (orden «Lanzar paracaidistas»); para desembarcar "
                "a las demás tropas, aterrícelo en una base.")
    if punto is None:
        return "Indique el punto de desembarco (ultimo punto de la ruta)."
    if terreno.clase(punto[0], punto[1]) == "agua":
        return "El punto de desembarco debe estar en tierra firme."
    return None


def desembarcar(transporte, punto, unidades, terreno) -> list:
    """Si el transporte esta a <= RADIO_DESEMBARCO_KM del punto, deja alli a las unidades a bordo (las devuelve)."""
    if geo.distancia_km(transporte.lat, transporte.lon, punto[0], punto[1]) > RADIO_DESEMBARCO_KM:
        return []
    return bajar(transporte, punto, unidades)


def bajar(transporte, punto, unidades) -> list:
    """Las unidades a bordo bajan en `punto` (las devuelve)."""
    carga = a_bordo(transporte, unidades)
    for i, x in enumerate(carga):
        x.transporte_id = None
        x.lat, x.lon = punto[0] + 0.004 * i, punto[1] + 0.004 * i
        x.despliegue_restante = catalogo.obtener(x.clase, x.tipo).despliegue_turnos
    return carga


def paracaidistas_a_bordo(transporte, unidades) -> list:
    return [x for x in a_bordo(transporte, unidades) if x.clase in SALTAN]


def error_de_salto(transporte, punto, terreno, unidades) -> str | None:
    """Motivo por el que `transporte` no puede lanzar paracaidistas en `punto` (None si puede)."""
    if transporte is None or transporte.estado != "activa" or not es_avion_transporte(transporte):
        return "Solo un avión de transporte lanza paracaidistas."
    if not paracaidistas_a_bordo(transporte, unidades):
        return f"{transporte.nombre} no lleva paracaidistas a bordo (las demás tropas desembarcan al aterrizar)."
    if punto is None:
        return "Marque en el mapa la zona de lanzamiento (el último punto de la ruta)."
    if terreno.clase(punto[0], punto[1]) == "agua":
        return "La zona de lanzamiento debe estar en tierra firme."
    return None


def saltar(transporte, punto, unidades, semilla: int = 0) -> list:
    """Los paracaidistas a bordo saltan sobre `punto`: caen repartidos alrededor (hasta DISPERSION_KM), pierden
    PERDIDA_SALTO de fuerza y quedan en tierra. Los devuelve."""
    saltan = paracaidistas_a_bordo(transporte, unidades)
    n = len(saltan)
    for i, x in enumerate(saltan):
        angulo = 2 * math.pi * (i / max(1, n) + (semilla % 360) / 360.0)
        km = DISPERSION_KM * (0.5 + 0.5 * ((semilla // 7 + i) % 3) / 2)
        x.transporte_id = None
        x.lat = punto[0] + km / 110.57 * math.cos(angulo)
        x.lon = punto[1] + km / (111.32 * max(0.05, math.cos(math.radians(punto[0])))) * math.sin(angulo)
        x.fuerza = max(1.0, x.fuerza - PERDIDA_SALTO)
    return saltan


def repartir_dano(transporte, perdida: float, unidades) -> list:
    """Las unidades a bordo sufren parte del daño del transporte; si se pierde, se pierden con el."""
    afectadas = []
    for x in a_bordo(transporte, unidades):
        if transporte.estado == "destruida":
            x.fuerza, x.estado = 0.0, "destruida"
        else:
            x.fuerza = max(0.0, x.fuerza - perdida * DANO_A_BORDO)
            if x.fuerza <= 0:
                x.estado = "destruida"
        afectadas.append(x)
    return afectadas
