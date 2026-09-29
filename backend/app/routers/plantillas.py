"""Escenarios precargados: listarlos y crear un escenario nuevo a partir de uno (ver engine/plantillas.py)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas
from app.db import get_db
from app.engine import plantillas
from app.models.usuario import Usuario

router = APIRouter(prefix="/api/plantillas", tags=["plantillas"])
solo_instructor = auth.requiere_roles("instructor")


@router.get("")
def listar(_: Usuario = Depends(auth.usuario_actual)):
    return {"plantillas": [plantillas.plantilla_dict(p) for p in plantillas.PLANTILLAS.values()]}


@router.post("/{plantilla_id}", response_model=schemas.EscenarioOut)
def crear(plantilla_id: str, db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    if plantilla_id not in plantillas.PLANTILLAS:
        raise HTTPException(status_code=404, detail="Plantilla desconocida")
    return plantillas.crear_desde_plantilla(db, plantilla_id)
