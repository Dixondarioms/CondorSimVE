"""Imagen comun por enlace de datos del Cóndor (como en los simuladores de mando modernos). La enciende el director
(Escenario.enlace_datos); apagada, todo el bando comparte lo que ve cualquiera de sus unidades, como siempre.

Encendida, lo que detecta una unidad llega a la pantalla de su bando solo si la unidad esta en la red: la red nace en
los centros de mando y control del bando (RAICES: bases, puertos, depositos, centros de comunicaciones, radares, aviones
de alerta temprana, portaaviones y destructores) y se extiende de unidad en unidad mientras esten a ALCANCE_KM o menos
(el alcance mayor de las dos: un avion enlaza desde lejos; una tropa, de cerca). No entra a la red una unidad dentro
de una interferencia enemiga ni una con las comunicaciones fuera de servicio (engine/sistemas.py).

Una unidad sin enlace sigue viendo y defendiendose con sus propios sensores (su antiaerea y su patrulla tiran a lo que
ven ellas), pero su bando no ve lo que detecta y no puede tirarle a eso desde otra unidad.
"""

from __future__ import annotations

from app.engine import catalogo, geo

RAICES = ("base_aerea", "puerto", "deposito", "centro_comunicaciones", "punto_recobre", "radar", "alerta_temprana",
          "portaaviones", "destructor")
ALCANCE_KM = {"aerea": 350.0, "naval": 250.0, "base": 150.0, "terrestre": 60.0}


def _puede(u, ge) -> bool:
    from app.engine import sistemas  # importacion tardia

    if ge is not None and ge.interferido(u):
        return False
    return sistemas.factor(u, "comunicaciones") > 0


def _alcance(u) -> float:
    return ALCANCE_KM.get(u.tipo, ALCANCE_KM["terrestre"])


def enlazadas(unidades, bando: str, ge=None) -> set:
    """Ids de las unidades del bando que estan en la red de enlace de datos."""
    activas = [u for u in unidades if u.bando == bando and u.estado == "activa" and not catalogo.es_misil(u)
               and getattr(u, "transporte_id", None) is None and getattr(u, "clase", None) != "torpedo"]
    red = [u for u in activas if u.clase in RAICES and not (u.tipo == "aerea" and getattr(u, "en_tierra", False))
           and _puede(u, ge)]
    dentro = {u.id for u in red}
    resto = [u for u in activas if u.id not in dentro and _puede(u, ge)]
    i = 0
    while i < len(red):  # de nodo en nodo
        n = red[i]
        i += 1
        quedan = []
        for u in resto:
            if geo.distancia_km(n.lat, n.lon, u.lat, u.lon) <= max(_alcance(n), _alcance(u)):
                dentro.add(u.id)
                red.append(u)
            else:
                quedan.append(u)
        resto = quedan
    return dentro


def para(escenario, unidades, bando: str, ge=None) -> set | None:
    """Las unidades enlazadas si el director encendio el enlace de datos; None si no (todas comparten lo que ven)."""
    return enlazadas(unidades, bando, ge) if getattr(escenario, "enlace_datos", False) else None
