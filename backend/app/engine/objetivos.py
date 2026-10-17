"""Objetivos del ejercicio y marcador.

Se evaluan al terminar de resolver cada turno:
  ocupar    el bando tiene al menos una unidad terrestre activa dentro de la zona y ninguna enemiga; hay que
            mantenerla `turnos_requeridos` turnos seguidos (si se pierde, el conteo vuelve a cero).
  destruir  se cumple cuando la unidad indicada queda destruida.
  neutralizar  se cumple cuando la fuerza de la unidad baja hasta `umbral` % (50 si no se indica) o es destruida.
  proteger  falla si la unidad indicada es destruida; se cumple al llegar `hasta_turno` con la unidad viva.
  efecto    objetivo ulterior o asignado de la cadena del TIEM: se cumple cuando se cumple el `umbral` % (100 si no
            se indica) de los objetivos que dependen de el (`padre_id`), y falla cuando ya no puede alcanzarlo.
En ocupar, destruir, neutralizar y efecto, `hasta_turno` es un plazo: si llega sin cumplirse, el objetivo falla.
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
UMBRAL_NEUTRALIZAR = 50.0  # fuerza (%) a la que queda neutralizada una unidad si el objetivo no indica otra
TIPOS = ("ocupar", "destruir", "neutralizar", "proteger", "efecto")
NIVELES = ("ulterior", "asignado", "material")


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

    todos = db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id).all()
    vencido = lambda o: o.hasta_turno is not None and turno >= o.hasta_turno  # noqa: E731
    for o in [o for o in todos if o.estado == "pendiente" and o.tipo != "efecto"]:
        if o.tipo == "ocupar":
            propias = [u for u in unidades.values() if u.bando == o.bando and _en_zona(o, u)]
            enemigas = [u for u in unidades.values() if u.bando != o.bando and _en_zona(o, u)]
            o.progreso = o.progreso + 1 if propias and not enemigas else 0
            if o.progreso >= o.turnos_requeridos:
                resolver(o, "cumplido")
            elif vencido(o):
                resolver(o, "fallido")
        else:
            u = unidades.get(o.unidad_id)
            destruida = u is None or u.estado == "destruida"
            if o.tipo == "destruir" and destruida:
                resolver(o, "cumplido")
            elif o.tipo == "neutralizar" and (destruida or u.fuerza <= (o.umbral if o.umbral is not None else UMBRAL_NEUTRALIZAR)):
                resolver(o, "cumplido")
            elif o.tipo == "proteger":
                if destruida:
                    resolver(o, "fallido")
                elif vencido(o):
                    resolver(o, "cumplido")
            elif vencido(o):
                resolver(o, "fallido")
    # efectos: primero los asignados (dependen de objetivos materiales) y despues los ulteriores
    hijos: dict[int, list[Objetivo]] = {}
    for o in todos:
        if o.padre_id is not None:
            hijos.setdefault(o.padre_id, []).append(o)
    for o in sorted((o for o in todos if o.tipo == "efecto"), key=lambda o: NIVELES.index(o.nivel) if o.nivel in NIVELES else 0,
                    reverse=True):
        if o.estado != "pendiente":
            continue
        estado = estado_efecto(o, hijos.get(o.id, []))
        if estado == "pendiente" and vencido(o):
            estado = "fallido"
        if estado != "pendiente":
            resolver(o, estado)
    return cambiados


def estado_efecto(o: Objetivo, hijos: list[Objetivo]) -> str:
    """cumplido / fallido / pendiente de un objetivo de efecto segun el estado de los que dependen de el."""
    if not hijos:
        return "pendiente"
    umbral = (o.umbral if o.umbral is not None else 100.0) / 100.0
    cumplidos = sum(1 for h in hijos if h.estado == "cumplido")
    posibles = sum(1 for h in hijos if h.estado != "fallido")
    if cumplidos >= umbral * len(hijos) - 1e-9:
        return "cumplido"
    if posibles < umbral * len(hijos) - 1e-9:
        return "fallido"
    return "pendiente"


def avance_efecto(o: Objetivo, hijos: list[Objetivo]) -> dict:
    """Cuantos de los objetivos dependientes se cumplieron, sobre el total, y el porcentaje requerido."""
    return {"cumplidos": sum(1 for h in hijos if h.estado == "cumplido"), "total": len(hijos),
            "requerido_pct": o.umbral if o.umbral is not None else 100.0}


def marcador(db: Session, escenario: Escenario) -> dict:
    """{"azul": {"objetivos", "bajas", "total", "cumplidos", "fallidos", "asignados", "cumplidos_pct"}, "rojo": {...}}

    "objetivos" son los puntos de los objetivos cumplidos; "cumplidos_pct", el porcentaje de los objetivos asignados
    al bando que ya cumplio (None si no tiene objetivos)."""
    objetivos = {b: 0 for b in BANDOS}
    cuenta = {b: {"cumplidos": 0, "fallidos": 0, "asignados": 0} for b in BANDOS}
    infligido = {b: 0.0 for b in BANDOS}
    for o in db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id):
        if o.bando not in objetivos:
            continue
        cuenta[o.bando]["asignados"] += 1
        if o.estado == "cumplido":
            objetivos[o.bando] += o.puntos
            cuenta[o.bando]["cumplidos"] += 1
        elif o.estado == "fallido":
            cuenta[o.bando]["fallidos"] += 1
    for c in db.query(Combate).filter(Combate.escenario_id == escenario.id):
        if c.atacante_bando in infligido and c.defensor_bando != c.atacante_bando:
            infligido[c.atacante_bando] += c.perdida_defensor
        if c.defensor_bando in infligido and c.defensor_bando != c.atacante_bando:
            infligido[c.defensor_bando] += c.perdida_atacante
    return {
        b: {
            "objetivos": objetivos[b], "bajas": int(infligido[b] // FUERZA_POR_PUNTO),
            "total": objetivos[b] + int(infligido[b] // FUERZA_POR_PUNTO),
            **cuenta[b],
            "cumplidos_pct": round(100 * cuenta[b]["cumplidos"] / cuenta[b]["asignados"], 1) if cuenta[b]["asignados"] else None,
        }
        for b in BANDOS
    }
