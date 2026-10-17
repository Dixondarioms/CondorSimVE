"""Objetivos del ejercicio (ocupar una zona; destruir, neutralizar o proteger una unidad; efectos que agrupan a otros
objetivos en la cadena del TIEM) y marcador.

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
    elif payload.tipo != "efecto":
        unidad = db.get(Unidad, payload.unidad_id) if payload.unidad_id else None
        if unidad is None or unidad.escenario_id != esc.id:
            raise HTTPException(status_code=400, detail="Elija una unidad del escenario")
        if payload.tipo in ("destruir", "neutralizar") and unidad.bando == payload.bando:
            raise HTTPException(status_code=400, detail=f"Solo se puede {payload.tipo} una unidad del bando contrario")
        if payload.tipo == "proteger":
            if unidad.bando != payload.bando:
                raise HTTPException(status_code=400, detail="Solo se puede proteger una unidad del propio bando")
            if payload.hasta_turno is None or payload.hasta_turno < esc.turno_actual:
                raise HTTPException(status_code=400, detail="Indique hasta que turno hay que proteger la unidad (no anterior al actual)")
    if payload.tipo == "efecto" and payload.nivel == "material":
        raise HTTPException(status_code=400, detail="Un objetivo de efecto es ulterior o asignado: agrupa a otros objetivos")
    if payload.tipo != "efecto" and payload.nivel != "material":
        raise HTTPException(status_code=400, detail="Los objetivos ulteriores y asignados son de tipo efecto")
    padre = None
    if payload.padre_id is not None:
        padre = db.get(Objetivo, payload.padre_id)
        if padre is None or padre.escenario_id != esc.id or padre.bando != payload.bando or padre.tipo != "efecto":
            raise HTTPException(status_code=400, detail="El objetivo superior debe ser un objetivo de efecto del mismo bando")
        if motor.NIVELES.index(padre.nivel) >= motor.NIVELES.index(payload.nivel):
            raise HTTPException(status_code=400, detail="El objetivo superior debe ser de un nivel mas alto (ulterior > asignado > material)")
    o = Objetivo(
        escenario_id=esc.id, bando=payload.bando, tipo=payload.tipo, nombre=payload.nombre.strip(), puntos=payload.puntos,
        lat=payload.lat if payload.tipo == "ocupar" else None, lon=payload.lon if payload.tipo == "ocupar" else None,
        radio_km=payload.radio_km, turnos_requeridos=payload.turnos_requeridos if payload.tipo == "ocupar" else 1,
        unidad_id=unidad.id if unidad else None, hasta_turno=payload.hasta_turno,
        nivel=payload.nivel, padre_id=padre.id if padre else None, efecto=payload.efecto.strip(),
        indicador=payload.indicador.strip(), umbral=payload.umbral if payload.tipo in ("neutralizar", "efecto") else None,
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
    # los que dependian de el quedan sueltos (no se borran)
    db.query(Objetivo).filter(Objetivo.padre_id == o.id).update({Objetivo.padre_id: None})
    db.delete(o)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}


@router.patch("/{objetivo_id}", response_model=schemas.ObjetivoOut)
async def editar(objetivo_id: int, payload: schemas.ObjetivoEdicion, esc: Escenario = Depends(auth.escenario_dep),
                 db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    """Corrige un objetivo: nombre, puntos, plazo, efecto deseado, indicador, umbral u objetivo superior."""
    o = db.get(Objetivo, objetivo_id)
    if o is None or o.escenario_id != esc.id:
        raise HTTPException(status_code=404, detail="Objetivo no encontrado")
    datos = payload.model_dump(exclude_unset=True)
    if "padre_id" in datos and datos["padre_id"] is not None:
        padre = db.get(Objetivo, datos["padre_id"])
        if (padre is None or padre.escenario_id != esc.id or padre.bando != o.bando or padre.tipo != "efecto"
                or padre.id == o.id or motor.NIVELES.index(padre.nivel) >= motor.NIVELES.index(o.nivel)):
            raise HTTPException(status_code=400, detail="El objetivo superior debe ser un efecto de nivel mas alto del mismo bando")
    for campo, valor in datos.items():
        setattr(o, campo, valor.strip() if isinstance(valor, str) else valor)
    db.commit()
    await manager.difundir_estado(db, esc)
    por_id = {o.unidad_id: db.get(Unidad, o.unidad_id)} if o.unidad_id else {}
    hijos = db.query(Objetivo).filter(Objetivo.padre_id == o.id).all()
    return state.serializar_objetivo(o, por_id, hijos)
