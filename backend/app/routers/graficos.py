"""Graficos tacticos (lineas de fase, ejes de avance, zonas de reunion, puntos de control).

Se guardan como GeoJSON y se difunden por WebSocket a todo el bando (los del instructor pueden ser
"todos"). Los alumnos solo ven, crean y borran los de su bando."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas, state
from app.db import get_db
from app.models.escenario import Escenario
from app.models.grafico import Grafico
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/graficos", tags=["graficos"])
puede_dibujar = auth.requiere_roles("azul", "rojo", "instructor")

MAX_VERTICES = 200
MAX_POR_BANDO = 150
TIPO_GEOMETRIA = {
    "linea_fase": "LineString", "eje_avance": "LineString", "zona_reunion": "Polygon", "punto_control": "Point",
}


def _coordenada(c) -> None:
    if (
        not isinstance(c, (list, tuple)) or len(c) < 2
        or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in c[:2])
        or not (-180 <= c[0] <= 180 and -90 <= c[1] <= 90)
    ):
        raise HTTPException(status_code=422, detail="Coordenada GeoJSON invalida (se espera [lon, lat])")


def validar_geometria(tipo: str, geometria: dict) -> dict:
    """Devuelve la geometria normalizada (solo tipo y coordenadas) o lanza 422."""
    esperado = TIPO_GEOMETRIA[tipo]
    if geometria.get("type") != esperado:
        raise HTTPException(status_code=422, detail=f"Un grafico '{tipo}' debe ser de tipo {esperado}")
    coords = geometria.get("coordinates")
    if esperado == "Point":
        _coordenada(coords)
    elif esperado == "LineString":
        if not isinstance(coords, list) or not (2 <= len(coords) <= MAX_VERTICES):
            raise HTTPException(status_code=422, detail=f"Una linea necesita entre 2 y {MAX_VERTICES} puntos")
        for c in coords:
            _coordenada(c)
    else:  # Polygon: un unico anillo cerrado
        if (
            not isinstance(coords, list) or len(coords) != 1 or not isinstance(coords[0], list)
            or not (4 <= len(coords[0]) <= MAX_VERTICES + 1)
        ):
            raise HTTPException(status_code=422, detail="Un poligono necesita un anillo de 3 a 200 vertices")
        for c in coords[0]:
            _coordenada(c)
        if coords[0][0][:2] != coords[0][-1][:2]:
            raise HTTPException(status_code=422, detail="El anillo del poligono debe estar cerrado")
    return {"type": esperado, "coordinates": coords}


def _bando_destino(payload: schemas.GraficoIn, usuario: Usuario) -> str:
    if usuario.rol == "instructor":
        return payload.bando or "todos"
    return usuario.rol  # los alumnos solo dibujan para su bando


@router.get("")
def listar(
    esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    gs = db.query(Grafico).filter(Grafico.escenario_id == esc.id).order_by(Grafico.id).all()
    return [state.serializar_grafico(g) for g in gs if state.grafico_visible(g.bando, usuario.rol)]


@router.post("", response_model=schemas.GraficoOut)
async def crear(
    payload: schemas.GraficoIn, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
    usuario: Usuario = Depends(puede_dibujar),
):
    if esc.estado == "finalizado":
        raise HTTPException(status_code=400, detail="El escenario ya finalizo")
    geometria = validar_geometria(payload.tipo, payload.geometria)
    bando = _bando_destino(payload, usuario)
    if db.query(Grafico).filter(Grafico.escenario_id == esc.id, Grafico.bando == bando).count() >= MAX_POR_BANDO:
        raise HTTPException(status_code=400, detail="Se alcanzo el maximo de graficos; borre alguno")
    g = Grafico(
        escenario_id=esc.id, bando=bando, tipo=payload.tipo, etiqueta=payload.etiqueta.strip(),
        geojson=json.dumps(geometria), autor_id=usuario.id, autor_nombre=usuario.username, turno=esc.turno_actual,
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    salida = state.serializar_grafico(g)
    await manager.difundir_grafico(esc.id, {"tipo": "grafico", "accion": "crear", "grafico": salida}, bando)
    return salida


@router.delete("/{grafico_id}")
async def borrar(
    grafico_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
    usuario: Usuario = Depends(puede_dibujar),
):
    g = db.get(Grafico, grafico_id)
    # Mismo mensaje si no existe o es del otro bando: no revela graficos ajenos.
    if g is None or g.escenario_id != esc.id or (usuario.rol != "instructor" and g.bando != usuario.rol):
        raise HTTPException(status_code=404, detail="Grafico no encontrado")
    bando = g.bando
    db.delete(g)
    db.commit()
    await manager.difundir_grafico(esc.id, {"tipo": "grafico", "accion": "borrar", "id": grafico_id}, bando)
    return {"ok": True}
