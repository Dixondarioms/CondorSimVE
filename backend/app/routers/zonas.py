"""Areas de referencia y zonas (engine/zonas.py): areas de patrulla, zonas de exclusion y zonas de no vuelo.

El director las dibuja para todos (o para un bando) y cada bando, las suyas. Se difunden con el estado."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas
from app.db import get_db
from app.engine import tiempo_real
from app.engine import zonas as zonas_mod
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.usuario import Usuario
from app.models.zona import Zona
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/zonas", tags=["zonas"])
puede_dibujar = auth.requiere_roles("azul", "rojo", "instructor")


def _propia(db: Session, esc: Escenario, zona_id: int, usuario: Usuario) -> Zona:
    z = db.get(Zona, zona_id)
    # mismo mensaje si no existe o es del otro bando: no revela zonas ajenas
    if z is None or z.escenario_id != esc.id or (usuario.rol != "instructor" and z.bando != usuario.rol):
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return z


@router.get("")
def listar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
           usuario: Usuario = Depends(auth.usuario_actual)):
    return zonas_mod.visibles_para(db, esc, usuario.rol)


@router.post("")
async def crear(payload: schemas.ZonaIn, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                usuario: Usuario = Depends(puede_dibujar)):
    if esc.estado == "finalizado":
        raise HTTPException(status_code=400, detail="El escenario ya finalizó")
    vertices = [(float(a), float(b)) for a, b in payload.puntos]
    if len(vertices) > 3 and vertices[0] == vertices[-1]:
        vertices = vertices[:-1]  # anillo cerrado: el ultimo repite el primero
    motivo = zonas_mod.error_de_poligono(vertices)
    if motivo:
        raise HTTPException(status_code=400, detail=motivo)
    bando = (payload.bando or "todos") if usuario.rol == "instructor" else usuario.rol
    if db.query(Zona).filter(Zona.escenario_id == esc.id, Zona.bando == bando).count() >= zonas_mod.MAX_POR_BANDO:
        raise HTTPException(status_code=400, detail="Se alcanzó el máximo de zonas: borre alguna")
    z = Zona(escenario_id=esc.id, bando=bando, tipo=payload.tipo, nombre=payload.nombre.strip(),
             puntos_json=json.dumps([[round(a, 5), round(b, 5)] for a, b in vertices]),
             armas=bool(payload.armas) and payload.tipo != "patrulla" and bando != "todos",
             autor=usuario.username, creada_seg=esc.sim_segundos)
    db.add(z)
    db.flush()
    texto = f"[{tiempo_real.hora_del_dia(esc)}] Nueva {zonas_mod.nombre(z)}" + (
        " (fijada por la dirección del ejercicio)." if bando == "todos" else f" (por {usuario.username}).")
    db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="zona", bando_destino=bando, descripcion=texto,
                  sim_segundos=esc.sim_segundos))
    db.commit()
    await manager.difundir_estado(db, esc)
    return zonas_mod.serializar(z)


@router.patch("/{zona_id}")
async def cambiar(zona_id: int, payload: schemas.ZonaCambio, esc: Escenario = Depends(auth.escenario_dep),
                  db: Session = Depends(get_db), usuario: Usuario = Depends(puede_dibujar)):
    z = _propia(db, esc, zona_id, usuario)
    if payload.nombre is not None:
        z.nombre = payload.nombre.strip()
    if payload.armas is not None:
        if payload.armas and (z.tipo == "patrulla" or z.bando == "todos"):
            raise HTTPException(status_code=400, detail="Solo las zonas de exclusión o de no vuelo de un bando tienen armas")
        z.armas = payload.armas
    db.commit()
    await manager.difundir_estado(db, esc)
    return zonas_mod.serializar(z)


@router.delete("/{zona_id}")
async def borrar(zona_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                 usuario: Usuario = Depends(puede_dibujar)):
    z = _propia(db, esc, zona_id, usuario)
    db.delete(z)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}
