from fastapi import APIRouter, Depends, Query

from app import auth
from app.models.usuario import Usuario
from app.terreno import get_terreno

router = APIRouter(prefix="/api/terreno", tags=["terreno"])


@router.get("/clase")
def clase_de_terreno(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    _: Usuario = Depends(auth.usuario_actual),
):
    return {"clase": get_terreno().clase(lat, lon)}
