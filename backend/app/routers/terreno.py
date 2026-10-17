from fastapi import APIRouter, Depends, Query

from app import auth
from app.models.usuario import Usuario
from app.terreno import NOMBRES_VIA, get_terreno

router = APIRouter(prefix="/api/terreno", tags=["terreno"])


@router.get("/clase")
def clase_de_terreno(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    _: Usuario = Depends(auth.usuario_actual),
):
    t = get_terreno()
    via = t.via(lat, lon)
    return {"clase": t.clase(lat, lon), "via": via, "via_nombre": NOMBRES_VIA.get(via, "")}


@router.get("/mapas", name="mapas")
def listar_mapas(_: Usuario = Depends(auth.usuario_actual)):
    """Regiones del mapa generadas (tools/preparar_terreno.py), de la mas detallada a la mas general: el frontend
    dibuja las teselas de cada una (/static/tiles/<id>/) y sus limites, y encaja la vista en la principal."""
    return {"mapas": get_terreno().regiones()}
