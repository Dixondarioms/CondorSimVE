"""Informe posterior al ejercicio (AAR): instantaneas por turno, combates y resumen."""

import json
from sqlalchemy.orm import Session

from app import state
from app.engine import objetivos as objetivos_mod
from app.models.aar import Combate, Instantanea
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.unidad import Unidad

CAMPOS_UNIDAD = (
    "id", "nombre", "bando", "tipo", "clase", "sidc", "lat", "lon", "fuerza", "estado",
    "combustible", "municion",
)


def _datos_unidades(db: Session, escenario_id: int) -> list[dict]:
    return [
        {c: getattr(u, c) for c in CAMPOS_UNIDAD}
        for u in db.query(Unidad).filter(Unidad.escenario_id == escenario_id).order_by(Unidad.id)
    ]


def guardar_instantanea(db: Session, escenario: Escenario, turno: int) -> None:
    """Guarda (o reemplaza) el estado del escenario al terminar `turno`."""
    datos = json.dumps({"unidades": _datos_unidades(db, escenario.id)})
    inst = (
        db.query(Instantanea)
        .filter(Instantanea.escenario_id == escenario.id, Instantanea.turno == turno)
        .first()
    )
    if inst is None:
        db.add(Instantanea(escenario_id=escenario.id, turno=turno, clima=escenario.clima, datos_json=datos))
    else:
        inst.datos_json, inst.clima = datos, escenario.clima


def asegurar_linea_base(db: Session, escenario: Escenario) -> None:
    """Antes del primer turno resuelto, guarda el despliegue inicial (turno 0)."""
    hay = db.query(Instantanea.id).filter(Instantanea.escenario_id == escenario.id).first()
    if hay is None:
        guardar_instantanea(db, escenario, escenario.turno_actual - 1)


def registrar_ajuste(db: Session, escenario: Escenario, descripcion: str) -> None:
    """Deja constancia de una intervencion manual del instructor (solo visible en el informe)."""
    db.add(Evento(
        escenario_id=escenario.id, turno=escenario.turno_actual, tipo="ajuste",
        bando_destino="instructor", descripcion=descripcion,
    ))


def _orden_dict(o: Orden, nombres: dict) -> dict:
    return {
        "id": o.id, "turno": o.turno_emitida, "unidad_id": o.unidad_id,
        "unidad": nombres.get(o.unidad_id, f"#{o.unidad_id}"), "tipo": o.tipo,
        "objetivo": nombres.get(o.objetivo_unidad_id) if o.objetivo_unidad_id else None,
        "waypoints": json.loads(o.waypoints_json or "[]"), "estado": o.estado, "resultado": o.resultado,
    }


def _combate_dict(c: Combate) -> dict:
    return {
        "id": c.id, "turno": c.turno, "atacante_id": c.atacante_id, "defensor_id": c.defensor_id,
        "atacante": c.atacante_nombre, "defensor": c.defensor_nombre,
        "atacante_bando": c.atacante_bando, "defensor_bando": c.defensor_bando,
        "ratio": round(c.ratio, 3), "perdida_atacante": round(c.perdida_atacante, 1),
        "perdida_defensor": round(c.perdida_defensor, 1), "terreno": c.terreno,
        "efectos": c.efectos, "lat": c.lat, "lon": c.lon,
    }


def construir_informe(db: Session, escenario: Escenario) -> dict:
    """Vista completa (sin niebla de guerra) de todo lo ocurrido en el escenario."""
    unidades = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id)}
    nombres = {uid: u.nombre for uid, u in unidades.items()}
    instantaneas = (
        db.query(Instantanea).filter(Instantanea.escenario_id == escenario.id).order_by(Instantanea.turno).all()
    )
    combates = db.query(Combate).filter(Combate.escenario_id == escenario.id).order_by(Combate.id).all()
    ordenes = db.query(Orden).filter(Orden.escenario_id == escenario.id).order_by(Orden.id).all()
    eventos = db.query(Evento).filter(Evento.escenario_id == escenario.id).order_by(Evento.id).all()

    # Fuerza de cada unidad en la primera y ultima instantanea, para contar bajas.
    turnos: dict[int, dict] = {}
    for inst in instantaneas:
        turnos[inst.turno] = {
            "turno": inst.turno, "clima": inst.clima, "unidades": json.loads(inst.datos_json)["unidades"],
            "combates": [], "ordenes": [], "eventos": [], "en_curso": False,
        }
    for c in combates:
        turnos[c.turno]["combates"].append(_combate_dict(c))

    def entrada_en_curso() -> dict:
        # Ordenes y eventos del turno que aun no se resolvio (no tiene instantanea).
        return turnos.setdefault(escenario.turno_actual, {
            "turno": escenario.turno_actual, "clima": escenario.clima, "unidades": [],
            "combates": [], "ordenes": [], "eventos": [], "en_curso": True,
        })

    for o in ordenes:
        if o.turno_emitida in turnos or o.turno_emitida == escenario.turno_actual:
            turnos.get(o.turno_emitida, None) or entrada_en_curso()
            turnos[o.turno_emitida]["ordenes"].append(_orden_dict(o, nombres))
    for e in eventos:
        if e.turno in turnos or e.turno == escenario.turno_actual:
            turnos.get(e.turno, None) or entrada_en_curso()
            turnos[e.turno]["eventos"].append(
                {"id": e.id, "turno": e.turno, "tipo": e.tipo, "bando_destino": e.bando_destino, "descripcion": e.descripcion}
            )

    resumen = {b: {
        "unidades": 0, "destruidas": 0, "fuerza_perdida": 0.0, "combates_iniciados": 0,
        "combates_recibidos": 0, "ordenes_emitidas": 0, "ordenes_rechazadas": 0,
        "dano_infligido": 0.0,
    } for b in ("azul", "rojo")}
    for u in unidades.values():
        r = resumen.get(u.bando)
        if r is None:
            continue
        r["unidades"] += 1
        r["destruidas"] += 1 if u.estado == "destruida" else 0
    for c in combates:
        resumen[c.atacante_bando]["combates_iniciados"] += 1
        resumen[c.defensor_bando]["combates_recibidos"] += 1
        resumen[c.atacante_bando]["fuerza_perdida"] += c.perdida_atacante
        resumen[c.defensor_bando]["fuerza_perdida"] += c.perdida_defensor
        resumen[c.atacante_bando]["dano_infligido"] += c.perdida_defensor
        resumen[c.defensor_bando]["dano_infligido"] += c.perdida_atacante
    for o in ordenes:
        u = unidades.get(o.unidad_id)
        if u is not None and u.bando in resumen:
            resumen[u.bando]["ordenes_emitidas"] += 1
            resumen[u.bando]["ordenes_rechazadas"] += 1 if o.estado == "rechazada" else 0
    for r in resumen.values():
        r["fuerza_perdida"] = round(r["fuerza_perdida"], 1)
        r["dano_infligido"] = round(r["dano_infligido"], 1)

    return {
        "escenario": {
            "id": escenario.id, "nombre": escenario.nombre, "estado": escenario.estado,
            "turno_actual": escenario.turno_actual, "clima": escenario.clima, "azar": escenario.azar,
            "creado_en": escenario.creado_en.isoformat(),
        },
        "turnos": [turnos[k] for k in sorted(turnos)],
        "resumen": resumen,
        "marcador": objetivos_mod.marcador(db, escenario),
        "objetivos": [
            state.serializar_objetivo(o, unidades)
            for o in db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id).order_by(Objetivo.id)
        ],
    }
