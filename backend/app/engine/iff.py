"""Fuego amigo e IFF del Cóndor (interruptor del director, Escenario.fuego_amigo). Apagado, nada cambia.

Encendido, cada aeronave tiene su IFF (identificacion amigo-enemigo, Unidad.iff):
- con el IFF encendido, la escucha electronica enemiga la localiza de lejos (el transpondedor responde);
- con el IFF apagado no la escucha, pero la defensa aerea propia con las armas aire «libres» no la distingue de un
  enemigo y le tira (fuego amigo). Con las armas «restringidas» (solo identificados) no le tira.
El fuego amigo queda en las alertas, en los eventos y en el informe.
"""

from __future__ import annotations

from app.engine import catalogo

_POR_ESCENARIO: dict[int, bool] = {}


def fijar(esc) -> None:
    _POR_ESCENARIO[esc.id] = bool(getattr(esc, "fuego_amigo", False))


def activo(u) -> bool:
    return _POR_ESCENARIO.get(getattr(u, "escenario_id", None), False)


def _aeronave_en_vuelo(u) -> bool:
    return (getattr(u, "tipo", "") == "aerea" and not getattr(u, "en_tierra", False) and u.estado == "activa"
            and not catalogo.es_misil(u) and not catalogo.obtener(u.clase, u.tipo).civil)


def emite(u) -> bool:
    """El transpondedor IFF encendido de una aeronave en vuelo: la escucha enemiga lo oye (solo con el interruptor)."""
    return activo(u) and _aeronave_en_vuelo(u) and getattr(u, "iff", True) is not False


def sin_iff(u) -> bool:
    """Aeronave propia en vuelo con el IFF apagado: la defensa aerea propia no la distingue de un enemigo."""
    return activo(u) and _aeronave_en_vuelo(u) and getattr(u, "iff", True) is False
