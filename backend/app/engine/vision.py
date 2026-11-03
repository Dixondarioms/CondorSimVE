"""Niebla de guerra: cada bando solo ve sus unidades y las enemigas detectadas.

Una unidad enemiga es detectada si esta dentro del radio de deteccion de alguna unidad propia activa. El clima
reduce ese radio para todos; sobre objetivos terrestres y bases, el terreno (bosque, urbano, montana...) lo reduce
mas; los drones, por su firma radar pequena, se detectan mas cerca. Los radares de vigilancia ven aeronaves en vuelo
muy lejos pero lo que esta en tierra solo de cerca. La guerra electronica (engine/guerra_electronica.py) reduce la
deteccion de los sensores interferidos, permite a las unidades de escucha localizar emisores enemigos lejanos y
delata a los interferidores mientras emiten.

Ademas, con la grilla de alturas, nada se detecta sin linea de vista: el relieve y la curvatura de la Tierra
ocultan (sombra de radar, horizonte), y las aeronaves se ven segun su perfil de vuelo (engine/relieve.py).
"""

from app.engine import catalogo, geo, relieve
from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.terreno import OCULTAMIENTO, Terreno

DETECCION_POR_DEFECTO = {"terrestre": 8.0, "aerea": 40.0, "naval": 30.0, "base": 6.0}
RADIO_LOCAL_SENSOR_KM = 8.0  # lo que un radar de vigilancia aerea ve en tierra


def deteccion_por_defecto(tipo: str) -> float:
    return DETECCION_POR_DEFECTO.get(tipo, 8.0)


def _clase(u):
    return catalogo.obtener(getattr(u, "clase", None), u.tipo)


def _en_vuelo(u) -> bool:
    return u.tipo == "aerea" and not getattr(u, "en_tierra", False)


def radio_efectivo(detector, objetivo, terreno: Terreno, clima: str = "despejado", ge=None) -> float:
    clase_d = _clase(detector)
    ocultamiento = (
        OCULTAMIENTO.get(terreno.clase(objetivo.lat, objetivo.lon), 1.0)
        if objetivo.tipo in ("terrestre", "base") or getattr(objetivo, "en_tierra", False)
        else 1.0
    )
    radio = detector.deteccion_km
    if clase_d.solo_aereo and not _en_vuelo(objetivo):
        radio = min(radio, RADIO_LOCAL_SENSOR_KM)
    from app.engine import asw  # importacion tardia: submarinos (engine/asw.py)

    submarino = asw.es_submarino(objetivo)
    radio *= ocultamiento * clima_mod.factor_deteccion(clima, objetivo.lat, objetivo.lon) * (1.0 if submarino else catalogo.firma(objetivo))
    radio *= clima_mod.factor_nocturno(clase_d, getattr(clima, "periodo", "dia"))
    if ge is not None and clase_d.id == "radar":  # radar fijo: sin energia trabaja con generadores (menos alcance)
        radio *= ge.factor_energia(detector.bando)
    if clase_d.emisor and getattr(detector, "emitiendo", True) is False:  # radar apagado: solo a ojo
        radio = min(radio, ge_mod.RADIO_SIN_EMISION_KM)
    if ge is not None and ge.interferido(detector):
        factor = ge_mod.FACTOR_RADAR if clase_d.solo_aereo else ge_mod.FACTOR_SENSOR
        radio = max(min(radio, ge_mod.RADIO_VISUAL_KM), radio * factor)
    from app.engine import sistemas  # importacion tardia: sensores dañados (engine/sistemas.py)

    sanos = sistemas.factor(detector, "sensores")
    if sanos < 1.0:  # con los sensores dañados ve menos; sin ellos, a ojo
        radio = max(min(radio, ge_mod.RADIO_VISUAL_KM), radio * sanos)
    if submarino:  # sumergido: solo el sonar (o a cota periscopica, de cerca); al atacar se delata
        radio = asw.radio_contra_submarino(detector, objetivo, radio)
    return radio


def escucha(detector, objetivo, ge=None, terreno: Terreno | None = None) -> bool:
    """La escucha electronica localiza emisores enemigos (radares, interferidores activos) a gran distancia, si la
    señal le llega (linea de vista: el relieve tambien la tapa)."""
    alcance = _clase(detector).escucha_km
    if not alcance or getattr(objetivo, "estado", "activa") != "activa":
        return False
    emite = ge_mod.emite_radar(objetivo) or (ge is not None and ge.emite(objetivo))  # un radar apagado no se oye
    return (emite and geo.distancia_km(detector.lat, detector.lon, objetivo.lat, objetivo.lon) <= alcance
            and relieve.linea_de_vista(terreno, detector, objetivo))


def detecta(detector, objetivo, terreno: Terreno, clima: str = "despejado", ge=None) -> bool:
    if (geo.distancia_km(detector.lat, detector.lon, objetivo.lat, objetivo.lon)
            <= radio_efectivo(detector, objetivo, terreno, clima, ge)
            and relieve.linea_de_vista(terreno, detector, objetivo)):
        return True
    return escucha(detector, objetivo, ge, terreno)


def es_sensor(u) -> bool:
    """Radares, antiaerea guiada, destructores, alerta temprana y escucha electronica: lo que muestra el cuadro radar."""
    c = _clase(u)
    return bool(c.emisor or c.solo_aereo or c.escucha_km)


def _rumbo(lat1, lon1, lat2, lon2) -> float:
    import math

    r = math.radians
    y = math.sin(r(lon2 - lon1)) * math.cos(r(lat2))
    x = math.cos(r(lat1)) * math.sin(r(lat2)) - math.sin(r(lat1)) * math.cos(r(lat2)) * math.cos(r(lon2 - lon1))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def cuadro_sensores(unidades, bando: str, terreno: Terreno, clima="despejado", ge=None) -> list[dict]:
    """Cada sensor activo del bando con lo que detecta ahora: distancia, rumbo (desde el sensor) y perfil de vuelo.
    Lo usa el panel de radares de la interfaz y el aviso de contactos nuevos al cerrar el turno."""
    enemigas = [e for e in unidades if e.bando != bando and e.estado != "destruida"
                and getattr(e, "transporte_id", None) is None]
    cuadro = []
    for s in unidades:
        if s.bando != bando or s.estado != "activa" or getattr(s, "transporte_id", None) is not None or not es_sensor(s):
            continue
        if s.tipo == "aerea" and getattr(s, "en_tierra", False):
            continue  # un avion de alerta temprana en tierra no vigila
        contactos = []
        for e in enemigas:
            if detecta(s, e, terreno, clima, ge):
                contactos.append({
                    "unidad_id": e.id, "nombre": e.nombre, "tipo": e.tipo, "clase": e.clase,
                    "distancia_km": round(geo.distancia_km(s.lat, s.lon, e.lat, e.lon), 1),
                    "rumbo": round(_rumbo(s.lat, s.lon, e.lat, e.lon)), "en_vuelo": _en_vuelo(e),
                    "perfil": relieve.perfil_de(e) if _en_vuelo(e) else None,
                    "por_escucha": not (geo.distancia_km(s.lat, s.lon, e.lat, e.lon) <= radio_efectivo(s, e, terreno, clima, ge)),
                })
        contactos.sort(key=lambda c: c["distancia_km"])
        cuadro.append({
            "unidad_id": s.id, "nombre": s.nombre, "clase": s.clase, "lat": s.lat, "lon": s.lon,
            "emisor": bool(_clase(s).emisor), "emitiendo": getattr(s, "emitiendo", True) is not False,
            "interferido": bool(ge and ge.interferido(s)),
            "energia_pct": round(100 * ge.factor_energia(bando)) if ge is not None and s.clase == "radar" else None,
            "contactos": contactos,
        })
    return cuadro


def unidades_visibles(unidades, bando: str, terreno: Terreno, clima: str = "despejado", ge=None) -> list:
    """Unidades que el bando indicado puede ver (propias + enemigas detectadas + interferidores enemigos activos)."""
    propias = [u for u in unidades if u.bando == bando]
    detectores = [u for u in propias if u.estado == "activa" and getattr(u, "transporte_id", None) is None]
    visibles = list(propias)

    for enemiga in unidades:
        if enemiga.bando == bando or enemiga.estado == "destruida" or getattr(enemiga, "transporte_id", None) is not None:
            continue  # lo que viaja a bordo de un transporte no se ve por separado
        if (ge is not None and ge.emite(enemiga)) or any(detecta(d, enemiga, terreno, clima, ge) for d in detectores):
            visibles.append(enemiga)
    from app.engine import asw  # importacion tardia: lo que oyen las sonoboyas del bando

    ya = {u.id for u in visibles}
    visibles += [u for u in asw.por_boyas(unidades, bando) if u.id not in ya]
    return visibles
