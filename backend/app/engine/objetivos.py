"""Objetivos del ejercicio y marcador.

Se evaluan al terminar de resolver cada turno:
  ocupar    el bando tiene al menos una unidad terrestre activa dentro de la zona y ninguna enemiga; hay que
            mantenerla `turnos_requeridos` turnos seguidos (si se pierde, el conteo vuelve a cero).
  destruir  se cumple cuando la unidad indicada queda destruida.
  proteger  falla si la unidad indicada es destruida; se cumple al llegar `hasta_turno` con la unidad viva.
El marcador de cada bando suma los puntos de sus objetivos cumplidos y un punto por cada 10 de fuerza que
infligio al enemigo en combate.
"""

from sqlalchemy.orm import Session

from app.engine import geo
from app.models.aar import Combate
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad

BANDOS = ("azul", "rojo")
FUERZA_POR_PUNTO = 10.0  # fuerza enemiga infligida que vale un punto


def _en_zona(o: Objetivo, u: Unidad) -> bool:
    return u.estado == "activa" and u.tipo == "terrestre" and geo.distancia_km(u.lat, u.lon, o.lat, o.lon) <= o.radio_km


def evaluar(db: Session, escenario: Escenario) -> list[Objetivo]:
    """Actualiza los objetivos pendientes tras el turno `escenario.turno_actual`; devuelve los que cambiaron."""
    turno = escenario.turno_actual
    unidades = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id)}
    cambiados: list[Objetivo] = []

    def resolver(o: Objetivo, estado: str) -> None:
        o.estado, o.turno_resuelto = estado, turno
        cambiados.append(o)
        palabra = "cumplido" if estado == "cumplido" else "fallido"
        db.add(Evento(
            escenario_id=escenario.id, turno=turno, tipo="objetivo", bando_destino=o.bando,
            descripcion=f"Objetivo {palabra}: {o.nombre}" + (f" (+{o.puntos} puntos)" if estado == "cumplido" and o.puntos else ""),
        ))

    for o in db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id, Objetivo.estado == "pendiente"):
        if o.tipo == "ocupar":
            propias = [u for u in unidades.values() if u.bando == o.bando and _en_zona(o, u)]
            enemigas = [u for u in unidades.values() if u.bando != o.bando and _en_zona(o, u)]
            o.progreso = o.progreso + 1 if propias and not enemigas else 0
            if o.progreso >= o.turnos_requeridos:
                resolver(o, "cumplido")
        else:
            u = unidades.get(o.unidad_id)
            destruida = u is None or u.estado == "destruida"
            if o.tipo == "destruir" and destruida:
                resolver(o, "cumplido")
            elif o.tipo == "proteger":
                if destruida:
                    resolver(o, "fallido")
                elif o.hasta_turno is not None and turno >= o.hasta_turno:
                    resolver(o, "cumplido")
    return cambiados


def marcador(db: Session, escenario: Escenario) -> dict:
    """{"azul": {"objetivos", "bajas", "total"}, "rojo": {...}}"""
    objetivos = {b: 0 for b in BANDOS}
    infligido = {b: 0.0 for b in BANDOS}
    for o in db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id, Objetivo.estado == "cumplido"):
        if o.bando in objetivos:
            objetivos[o.bando] += o.puntos
    for c in db.query(Combate).filter(Combate.escenario_id == escenario.id):
        if c.atacante_bando in infligido and c.defensor_bando != c.atacante_bando:
            infligido[c.atacante_bando] += c.perdida_defensor
        if c.defensor_bando in infligido and c.defensor_bando != c.atacante_bando:
            infligido[c.defensor_bando] += c.perdida_atacante
    return {
        b: {
            "objetivos": objetivos[b], "bajas": int(infligido[b] // FUERZA_POR_PUNTO),
            "total": objetivos[b] + int(infligido[b] // FUERZA_POR_PUNTO),
        }
        for b in BANDOS
    }
