"""Niebla de guerra: cada bando solo ve sus unidades y las enemigas detectadas.

Una unidad enemiga es detectada si esta dentro del radio de deteccion de alguna
unidad propia activa. El clima reduce ese radio para todos; ademas, sobre
objetivos terrestres y bases, el terreno (bosque, urbano, montana...) lo reduce
mas. Las unidades aereas y navales no se ocultan en el terreno.
"""

from app.engine import clima as clima_mod
from app.engine import geo
from app.terreno import OCULTAMIENTO, Terreno

DETECCION_POR_DEFECTO = {"terrestre": 8.0, "aerea": 40.0, "naval": 30.0, "base": 6.0}


def deteccion_por_defecto(tipo: str) -> float:
    return DETECCION_POR_DEFECTO.get(tipo, 8.0)


def radio_efectivo(detector, objetivo, terreno: Terreno, clima: str = "despejado") -> float:
    ocultamiento = (
        OCULTAMIENTO.get(terreno.clase(objetivo.lat, objetivo.lon), 1.0)
        if objetivo.tipo in ("terrestre", "base")
        else 1.0
    )
    return detector.deteccion_km * ocultamiento * clima_mod.factor_deteccion(clima)


def detecta(detector, objetivo, terreno: Terreno, clima: str = "despejado") -> bool:
    return (
        geo.distancia_km(detector.lat, detector.lon, objetivo.lat, objetivo.lon)
        <= radio_efectivo(detector, objetivo, terreno, clima)
    )


def unidades_visibles(unidades, bando: str, terreno: Terreno, clima: str = "despejado") -> list:
    """Unidades que el bando indicado puede ver (propias + enemigas detectadas)."""
    propias = [u for u in unidades if u.bando == bando]
    detectores = [u for u in propias if u.estado == "activa"]
    visibles = list(propias)

    for enemiga in unidades:
        if enemiga.bando == bando or enemiga.estado == "destruida":
            continue
        if any(detecta(d, enemiga, terreno, clima) for d in detectores):
            visibles.append(enemiga)
    return visibles
