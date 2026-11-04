"""Grupos de tarea: cada bando junta unidades propias bajo un nombre (por ejemplo «Grupo Naval 1»). En el orden de
batalla aparecen como una linea; con un clic quedan elegidas juntas y la orden se da a todas en formacion
(POST /ordenes/lote). El grupo no cambia como combate cada unidad."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import auth
from app.db import get_db
from app.models.escenario import Escenario
from app.models.grupo import GrupoTarea
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/grupos", tags=["grupos"])
MAX_UNIDADES = 30
MAX_GRUPOS = 20


class GrupoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    unidad_ids: list[int] = Field(min_length=2, max_length=MAX_UNIDADES)


def serializar(g: GrupoTarea, vivas: set | None = None) -> dict:
    ids = json.loads(g.unidades_json or "[]")
    return {"id": g.id, "bando": g.bando, "nombre": g.nombre,
            "unidad_ids": [i for i in ids if vivas is None or i in vivas]}


def para(db: Session, escenario: Escenario, rol: str, vivas: set) -> list[dict]:
    """Los grupos que ve el rol (su bando; el director y el observador, todos), sin las unidades perdidas."""
    q = db.query(GrupoTarea).filter(GrupoTarea.escenario_id == escenario.id)
    if rol in ("azul", "rojo"):
        q = q.filter(GrupoTarea.bando == rol)
    return [serializar(g, vivas) for g in q.order_by(GrupoTarea.id)]


@router.post("")
async def crear(payload: GrupoIn, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                usuario: Usuario = Depends(auth.requiere_roles("azul", "rojo", "instructor"))):
    unidades = [db.get(Unidad, i) for i in dict.fromkeys(payload.unidad_ids)]
    if any(u is None or u.escenario_id != esc.id or u.estado != "activa" or u.tipo == "base" for u in unidades):
        raise HTTPException(status_code=400, detail="Elija unidades activas del ejercicio (no bases)")
    bandos = {u.bando for u in unidades}
    if len(bandos) != 1 or (usuario.rol != "instructor" and bandos != {usuario.rol}):
        raise HTTPException(status_code=400, detail="Un grupo de tarea es de unidades propias de un solo bando")
    bando = bandos.pop()
    if db.query(GrupoTarea).filter(GrupoTarea.escenario_id == esc.id, GrupoTarea.bando == bando).count() >= MAX_GRUPOS:
        raise HTTPException(status_code=400, detail="Se alcanzó el máximo de grupos de tarea: disuelva alguno")
    g = GrupoTarea(escenario_id=esc.id, bando=bando, nombre=payload.nombre.strip(),
                   unidades_json=json.dumps([u.id for u in unidades]))
    db.add(g)
    db.commit()
    await manager.difundir_estado(db, esc)
    return serializar(g)


@router.delete("/{grupo_id}")
async def disolver(grupo_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                   usuario: Usuario = Depends(auth.requiere_roles("azul", "rojo", "instructor"))):
    g = db.get(GrupoTarea, grupo_id)
    if g is None or g.escenario_id != esc.id or (usuario.rol != "instructor" and g.bando != usuario.rol):
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    db.delete(g)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}
