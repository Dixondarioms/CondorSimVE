"""Niebla de guerra: cada bando solo ve sus unidades y las enemigas detectadas.

Una unidad enemiga es detectada si esta dentro del radio de deteccion de alguna unidad propia activa. El clima
reduce ese radio para todos; sobre objetivos terrestres y bases, el terreno (bosque, urbano, montana...) lo reduce
mas; los drones, por su firma radar pequena, se detectan mas cerca. Los radares de vigilancia ven aeronaves en vuelo
muy lejos pero lo que esta en tierra solo de cerca. La guerra electronica (engine/guerra_electronica.py) reduce la
deteccion de los sensores interferidos, permite a las unidades de escucha localizar emisores enemigos lejanos y
delata a los interferidores mientras emiten.
"""

from app.engine import catalogo, geo
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
    radio *= ocultamiento * clima_mod.factor_deteccion(clima) * _clase(objetivo).firma
    if ge is not None and ge.interferido(detector):
        factor = ge_mod.FACTOR_RADAR if clase_d.solo_aereo else ge_mod.FACTOR_SENSOR
        radio = max(min(radio, ge_mod.RADIO_VISUAL_KM), radio * factor)
    return radio


def escucha(detector, objetivo, ge=None) -> bool:
    """La escucha electronica localiza emisores enemigos (radares, interferidores activos) a gran distancia."""
    alcance = _clase(detector).escucha_km
    if not alcance or getattr(objetivo, "estado", "activa") != "activa":
        return False
    emite = _clase(objetivo).emisor or (ge is not None and ge.emite(objetivo))
    return emite and geo.distancia_km(detector.lat, detector.lon, objetivo.lat, objetivo.lon) <= alcance


def detecta(detector, objetivo, terreno: Terreno, clima: str = "despejado", ge=None) -> bool:
    return (
        geo.distancia_km(detector.lat, detector.lon, objetivo.lat, objetivo.lon)
        <= radio_efectivo(detector, objetivo, terreno, clima, ge)
        or escucha(detector, objetivo, ge)
    )


def unidades_visibles(unidades, bando: str, terreno: Terreno, clima: str = "despejado", ge=None) -> list:
    """Unidades que el bando indicado puede ver (propias + enemigas detectadas + interferidores enemigos activos)."""
    propias = [u for u in unidades if u.bando == bando]
    detectores = [u for u in propias if u.estado == "activa"]
    visibles = list(propias)

    for enemiga in unidades:
        if enemiga.bando == bando or enemiga.estado == "destruida":
            continue
        if (ge is not None and ge.emite(enemiga)) or any(detecta(d, enemiga, terreno, clima, ge) for d in detectores):
            visibles.append(enemiga)
    return visibles
