from fastapi import APIRouter, Depends

from app import auth
from app.engine import naciones
from app.models.usuario import Usuario

router = APIRouter(prefix="/api", tags=["naciones"])


@router.get("/naciones")
def listar_naciones(_: Usuario = Depends(auth.usuario_actual)):
    """Paises que se pueden asignar a un bando (identidad nacional del ejercicio; ver engine/naciones.py)."""
    return {"naciones": [naciones.nacion_dict(n) for n in naciones.NACIONES.values()]}
