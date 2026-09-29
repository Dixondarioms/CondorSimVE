"""Objetivos del ejercicio (ocupar una zona, destruir o proteger una unidad) y marcador.

El instructor los crea y borra; cada bando ve solo los suyos (el instructor y el observador ven todos)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas, state
from app.db import get_db
from app.engine import objetivos as motor
from app.models.escenario import Escenario
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/objetivos", tags=["objetivos"])
solo_instructor = auth.requiere_roles("instructor")
MAX_OBJETIVOS = 60


@router.get("")
def listar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
           usuario: Usuario = Depends(auth.usuario_actual)):
    return {"objetivos": state.objetivos_para(db, esc, usuario.rol), "marcador": motor.marcador(db, esc)}


@router.post("", response_model=schemas.ObjetivoOut)
async def crear(payload: schemas.ObjetivoIn, esc: Escenario = Depends(auth.escenario_dep),
                db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    if db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).count() >= MAX_OBJETIVOS:
        raise HTTPException(status_code=400, detail=f"Un escenario admite como maximo {MAX_OBJETIVOS} objetivos")
    unidad = None
    if payload.tipo == "ocupar":
        if payload.lat is None or payload.lon is None:
            raise HTTPException(status_code=400, detail="Indique el centro de la zona a ocupar")
    else:
        unidad = db.get(Unidad, payload.unidad_id) if payload.unidad_id else None
        if unidad is None or unidad.escenario_id != esc.id:
            raise HTTPException(status_code=400, detail="Elija una unidad del escenario")
        if payload.tipo == "destruir" and unidad.bando == payload.bando:
            raise HTTPException(status_code=400, detail="Solo se puede destruir una unidad del bando contrario")
        if payload.tipo == "proteger":
            if unidad.bando != payload.bando:
                raise HTTPException(status_code=400, detail="Solo se puede proteger una unidad del propio bando")
            if payload.hasta_turno is None or payload.hasta_turno < esc.turno_actual:
                raise HTTPException(status_code=400, detail="Indique hasta que turno hay que proteger la unidad (no anterior al actual)")
    o = Objetivo(
        escenario_id=esc.id, bando=payload.bando, tipo=payload.tipo, nombre=payload.nombre.strip(), puntos=payload.puntos,
        lat=payload.lat if payload.tipo == "ocupar" else None, lon=payload.lon if payload.tipo == "ocupar" else None,
        radio_km=payload.radio_km, turnos_requeridos=payload.turnos_requeridos if payload.tipo == "ocupar" else 1,
        unidad_id=unidad.id if unidad else None, hasta_turno=payload.hasta_turno if payload.tipo == "proteger" else None,
    )
    db.add(o)
    db.commit()
    await manager.difundir_estado(db, esc)
    return state.serializar_objetivo(o, {unidad.id: unidad} if unidad else {})


@router.delete("/{objetivo_id}")
async def borrar(objetivo_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                 _: Usuario = Depends(solo_instructor)):
    o = db.get(Objetivo, objetivo_id)
    if o is None or o.escenario_id != esc.id:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    db.delete(o)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}
