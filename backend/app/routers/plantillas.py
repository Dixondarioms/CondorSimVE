"""Escenarios precargados: listarlos, crear un escenario nuevo a partir de uno y eliminar los que guardo el
instructor (ver engine/plantillas.py; guardar una desde un escenario esta en routers/escenarios.py)."""

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
    return {"plantillas": [plantillas.plantilla_dict(p) for p in plantillas.todas().values()]}


@router.post("/{plantilla_id}", response_model=schemas.EscenarioOut)
def crear(plantilla_id: str, db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    if plantillas.obtener(plantilla_id) is None:
        raise HTTPException(status_code=404, detail="Plantilla desconocida")
    return plantillas.crear_desde_plantilla(db, plantilla_id)


@router.delete("/{plantilla_id}")
def eliminar(plantilla_id: str, _: Usuario = Depends(solo_instructor)):
    """Solo las plantillas guardadas por el instructor (origen "usuario"); las del codigo no se tocan."""
    try:
        borrada = plantillas.eliminar_usuario(plantilla_id)
    except plantillas.PlantillaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not borrada:
        raise HTTPException(status_code=404, detail="Plantilla desconocida")
    return {"ok": True, "id": plantilla_id}
