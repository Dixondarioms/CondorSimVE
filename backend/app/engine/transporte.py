"""Transporte de tropas: unidades anfibias (buque de desembarco) y helitransportadas (helicoptero de transporte).

Una unidad terrestre se **embarca** (orden `embarcar`, objetivo = el transporte propio a <= 3 km) y viaja a bordo:
queda oculta (no se la detecta ni ataca por separado), no recibe ordenes, se mueve con el transporte y sufre parte
del daño que este recibe (o se pierde con el). El transporte **desembarca** (orden `desembarcar`: waypoints de su
ruta y, como ultimo punto, el lugar de desembarco en tierra): al llegar a <= RADIO_DESEMBARCO_KM del punto, las
unidades a bordo aparecen alli; si no llega, sigue navegando o volando hacia el punto en los turnos siguientes.

- El buque de desembarco lleva hasta 3 unidades terrestres de cualquier movilidad; el helicoptero de transporte
  artillado, 1 unidad ligera (infanteria, antiaerea portatil, ingenieros...).
- El punto de desembarco debe ser tierra firme; un buque no puede entrar en el, asi que se acerca por el agua.
"""

from app.engine import catalogo, geo

RADIO_EMBARQUE_KM = 3.0
RADIO_DESEMBARCO_KM = 5.0
DANO_A_BORDO = 0.5  # fraccion del daño al transporte que sufren las unidades embarcadas
CAPACIDAD = {"buque_desembarco": 3, "helicoptero_artillado": 1}
SOLO_LIGERAS = {"helicoptero_artillado"}


def capacidad(u) -> int:
    return CAPACIDAD.get(getattr(u, "clase", "") or "", 0)


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
        return "Elija un buque de desembarco o un helicoptero de transporte propio."
    if getattr(transporte, "en_tierra", False) and transporte.tipo == "aerea":
        pass  # un helicoptero en pista tambien embarca
    clase_u = catalogo.obtener(u.clase, u.tipo)
    if transporte.clase in SOLO_LIGERAS and clase_u.movilidad != "ligera":
        return f"{transporte.nombre} solo transporta unidades ligeras (infanteria, antiaerea portatil, ingenieros)."
    if len(a_bordo(transporte, unidades)) >= capacidad(transporte):
        return f"{transporte.nombre} ya lleva su carga maxima ({capacidad(transporte)} unidad(es))."
    d = geo.distancia_km(u.lat, u.lon, transporte.lat, transporte.lon)
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
        return "Solo un buque de desembarco o un helicoptero de transporte puede desembarcar tropas."
    if not a_bordo(transporte, unidades):
        return f"{transporte.nombre} no lleva unidades a bordo."
    if punto is None:
        return "Indique el punto de desembarco (ultimo punto de la ruta)."
    if terreno.clase(punto[0], punto[1]) == "agua":
        return "El punto de desembarco debe estar en tierra firme."
    return None


def desembarcar(transporte, punto, unidades, terreno) -> list:
    """Si el transporte esta a <= RADIO_DESEMBARCO_KM del punto, deja alli a las unidades a bordo (las devuelve)."""
    if geo.distancia_km(transporte.lat, transporte.lon, punto[0], punto[1]) > RADIO_DESEMBARCO_KM:
        return []
    carga = a_bordo(transporte, unidades)
    for i, x in enumerate(carga):
        x.transporte_id = None
        x.lat, x.lon = punto[0] + 0.004 * i, punto[1] + 0.004 * i
        x.despliegue_restante = catalogo.obtener(x.clase, x.tipo).despliegue_turnos
    return carga


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
