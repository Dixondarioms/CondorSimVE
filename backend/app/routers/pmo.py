"""Problema Militar Operativo de cada bando (TIEM, ver engine/pmo.py).

Cada bando lee el suyo; el instructor y el observador, los dos. El instructor lo redacta o lo genera el simulador a
partir del escenario (que tambien arma el calendario D/H y la cadena de objetivos si faltan)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import auth, state
from app.db import get_db
from app.engine import aar, pmo
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/pmo", tags=["pmo"])
solo_instructor = auth.requiere_roles("instructor")


class PmoIn(BaseModel):
    contenido: dict


class GenerarIn(BaseModel):
    bandos: list[str] = Field(default_factory=lambda: list(pmo.BANDOS))
    sobrescribir: bool = False  # reemplazar tambien los redactados por el instructor
    calendario: bool = True  # fijar dia D, hora H y duracion si faltan
    cadena: bool = True  # agrupar los objetivos en asignados y ulterior si el bando no tiene


def _respuesta(db: Session, esc: Escenario, rol: str) -> dict:
    bandos = [rol] if rol in pmo.BANDOS else list(pmo.BANDOS)
    return {
        "bandos": {b: pmo.como_dict(pmo.obtener(db, esc, b), b) for b in bandos},
        "campos": [{"clave": k, "titulo": t} for k, t in pmo.CAMPOS],
        "calendario": esc.calendario,
    }


def _avisar(db: Session, esc: Escenario, bando: str, texto: str) -> None:
    db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="pmo", bando_destino=bando, descripcion=texto))


@router.get("")
def leer(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
         usuario: Usuario = Depends(auth.usuario_actual)):
    return _respuesta(db, esc, usuario.rol)


@router.put("/{bando}")
async def guardar(bando: str, payload: PmoIn, esc: Escenario = Depends(auth.escenario_dep),
                  db: Session = Depends(get_db), usuario: Usuario = Depends(solo_instructor)):
    if bando not in pmo.BANDOS:
        raise HTTPException(status_code=404, detail="Bando desconocido")
    pmo.guardar(db, esc, bando, payload.contenido, "instructor")
    _avisar(db, esc, bando, "El escalon superior actualizo el Problema Militar Operativo (pestaña PMO).")
    aar.registrar_ajuste(db, esc, f"Problema Militar Operativo del bando {bando} redactado por el instructor")
    db.commit()
    await manager.difundir_estado(db, esc)
    return _respuesta(db, esc, usuario.rol)


@router.delete("/{bando}")
async def borrar(bando: str, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                 usuario: Usuario = Depends(solo_instructor)):
    pm = pmo.obtener(db, esc, bando)
    if pm is None:
        raise HTTPException(status_code=404, detail="Ese bando no tiene Problema Militar")
    db.delete(pm)
    db.commit()
    await manager.difundir_estado(db, esc)
    return _respuesta(db, esc, usuario.rol)


@router.post("/generar")
async def generar(payload: GenerarIn, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                  usuario: Usuario = Depends(solo_instructor)):
    """Crea la situacion automaticamente a partir del escenario."""
    bandos = [b for b in payload.bandos if b in pmo.BANDOS]
    if not bandos:
        raise HTTPException(status_code=400, detail="Indique al menos un bando")
    hecho = pmo.generar(db, esc, bandos, sobrescribir=payload.sobrescribir, calendario_auto=payload.calendario,
                        cadena=payload.cadena)
    for b in hecho["pmo"]:
        _avisar(db, esc, b, "El escalon superior emitio el Problema Militar Operativo (pestaña PMO).")
    partes = [f"PMO generado para {', '.join(hecho['pmo'])}" if hecho["pmo"] else "ningun PMO reemplazado"]
    if hecho["calendario"]:
        partes.append("calendario D/H preparado")
    if hecho["objetivos"]:
        partes.append(f"{hecho['objetivos']} objetivo(s) de la cadena creados")
    aar.registrar_ajuste(db, esc, "Situacion automatica: " + ", ".join(partes))
    db.commit()
    await manager.difundir_estado(db, esc)
    return {**_respuesta(db, esc, usuario.rol), "hecho": hecho}
