from types import SimpleNamespace

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


# lo que se mira desde un punto: un avion a cota media, uno rasante y lo que esta en tierra (engine/relieve.py)
BLANCOS_VISIBILIDAD = (("medio", "Avión a cota media (1 500 m)", 1500.0), ("rasante", "Avión rasante (60 m)", 60.0),
                       ("tierra", "Vehículo o tropa en tierra", 3.0))


@router.get("/visibilidad")
def visibilidad_desde(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    alcance_km: float = Query(default=150.0, ge=5, le=400),
    altura_m: float = Query(default=25.0, ge=1, le=3000),
    _: Usuario = Depends(auth.usuario_actual),
):
    """¿Que se ve desde aqui? Para un observador o un radar a `altura_m` sobre el suelo en (lat, lon), hasta donde ve
    segun el relieve y la curvatura de la tierra: un avion a cota media, uno rasante y lo que esta en tierra. Sirve
    para planear donde poner un radar o por donde entrar sin ser visto. Sin grilla de alturas: disponible = False."""
    from app.engine import relieve  # importacion tardia

    t = get_terreno()
    if not t.tiene_elevacion:
        return {"disponible": False, "poligonos": []}
    punto = SimpleNamespace(lat=lat, lon=lon, tipo="terrestre", clase="")
    return {
        "disponible": True, "altura_suelo_m": round(relieve.altura_suelo(t, lat, lon)), "altura_m": altura_m,
        "poligonos": [{"id": i, "nombre": n, "altura_blanco_m": h,
                       "poligono": relieve.cobertura(t, punto, alcance_km, h, altura_sensor_m=altura_m)}
                      for i, n, h in BLANCOS_VISIBILIDAD],
    }


@router.get("/mapas", name="mapas")
def listar_mapas(_: Usuario = Depends(auth.usuario_actual)):
    """Regiones del mapa generadas (tools/preparar_terreno.py), de la mas detallada a la mas general: el frontend
    dibuja las teselas de cada una (/static/tiles/<id>/) y sus limites, y encaja la vista en la principal."""
    return {"mapas": get_terreno().regiones()}
