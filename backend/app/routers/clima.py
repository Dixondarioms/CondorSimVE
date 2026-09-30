"""Zonas meteorologicas del escenario (instructor): frentes de nubes, lluvia o tormenta con deriva y duracion."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas
from app.db import get_db
from app.engine import clima as clima_mod
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.usuario import Usuario
from app.models.zona_clima import ZonaClima
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/clima", tags=["clima"])
solo_instructor = auth.requiere_roles("instructor")


@router.get("/zonas")
def listar_zonas(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                 _: Usuario = Depends(auth.usuario_actual)):
    return [clima_mod.serializar(z) for z in clima_mod.zonas_de(db, esc)]


@router.get("/en")
def clima_en(lat: float, lon: float, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
             _: Usuario = Depends(auth.usuario_actual)):
    """Clima efectivo en un punto (general + zonas)."""
    return {"clima": clima_mod.contexto(db, esc).en(lat, lon), "general": esc.clima}


@router.post("/zonas")
async def crear_zona(payload: schemas.ZonaClimaIn, esc: Escenario = Depends(auth.escenario_dep),
                     db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    motivo = clima_mod.error_de_zona(payload.tipo, payload.radio_km, payload.deriva_kmh)
    if motivo:
        raise HTTPException(status_code=400, detail=motivo)
    hasta = esc.turno_actual + payload.turnos if payload.turnos else None
    z = ZonaClima(escenario_id=esc.id, nombre=(payload.nombre or "").strip()[:60], tipo=payload.tipo, lat=payload.lat,
                  lon=payload.lon, radio_km=payload.radio_km, deriva_rumbo=payload.deriva_rumbo % 360,
                  deriva_kmh=payload.deriva_kmh, hasta_turno=hasta, creada_turno=esc.turno_actual)
    db.add(z)
    db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="clima", bando_destino="todos",
                  descripcion=(f"Zona de {payload.tipo}{' ' + z.nombre if z.nombre else ''} de {payload.radio_km:.0f} km sobre "
                               f"({payload.lat:.2f}, {payload.lon:.2f})"
                               + (f", deriva {payload.deriva_kmh:.0f} km/h al {payload.deriva_rumbo:.0f}" if payload.deriva_kmh else "")
                               + (f", hasta el turno {hasta}." if hasta else "."))))
    db.commit()
    db.refresh(z)
    await manager.difundir_estado(db, esc)
    return clima_mod.serializar(z)


@router.delete("/zonas/{zona_id}")
async def borrar_zona(zona_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                      _: Usuario = Depends(solo_instructor)):
    z = db.get(ZonaClima, zona_id)
    if z is None or z.escenario_id != esc.id:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    db.delete(z)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}
