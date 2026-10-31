"""Puntos medios de impacto (PMI) sobre las pistas enemigas: Operaciones (A-3) los pide, Inteligencia (A-2) recibe una
propuesta calculada sobre la pista (engine/pmi.py), la ajusta si quiere y la entrega. Con los PMI entregados, el
ataque a la pista de esa base hace todo su daño."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import auth
from app.db import get_db
from app.engine import pmi as pmi_mod
from app.engine import puestos, tiempo_real
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.pmi import PedidoPmi
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/pmi", tags=["pmi"])


class PedidoIn(BaseModel):
    base_id: int
    nota: str = Field(default="", max_length=300)


class PuntoIn(BaseModel):
    id: str = Field(default="", max_length=12)
    lat: float
    lon: float
    nota: str = Field(default="", max_length=120)


class EntregaIn(BaseModel):
    puntos: list[PuntoIn] = Field(min_length=1, max_length=pmi_mod.MAX_PUNTOS)


def _quien(usuario) -> str:
    return f"{puestos.obtener(usuario.puesto).sigla} ({usuario.username})"


def _pedido(db: Session, esc: Escenario, pedido_id: int, usuario) -> PedidoPmi:
    p = db.get(PedidoPmi, pedido_id)
    # mismo mensaje si no existe o es del otro bando
    if p is None or p.escenario_id != esc.id or p.bando != usuario.rol or p.estado == "cancelado":
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return p


def _evento(db: Session, esc: Escenario, bando: str, texto: str, base: Unidad | None = None) -> None:
    db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, sim_segundos=esc.sim_segundos, tipo="inteligencia",
                  bando_destino=bando, descripcion=f"[{tiempo_real.hora_del_dia(esc)}] {texto}"))


@router.get("")
def listar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
           usuario: Usuario = Depends(auth.usuario_actual)):
    return pmi_mod.visibles_para(db, esc, usuario.rol)


@router.post("")
async def pedir(payload: PedidoIn, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                usuario=Depends(auth.conductor)):
    """A-3 (o el Comandante o el JEM) pide a Inteligencia los PMI de la pista de una base aerea enemiga."""
    auth.exigir_funcion(usuario, "aereo")
    base = db.get(Unidad, payload.base_id)
    if base is None or base.escenario_id != esc.id or base.bando == usuario.rol or not pmi_mod.es_base_con_pista(base) \
            or base.estado == "destruida":
        raise HTTPException(status_code=400, detail="Elija una base aérea enemiga con pista")
    previo = db.query(PedidoPmi).filter(PedidoPmi.escenario_id == esc.id, PedidoPmi.bando == usuario.rol,
                                        PedidoPmi.base_id == base.id, PedidoPmi.estado != "cancelado").first()
    if previo is not None:
        estado = "ya los entregó" if previo.estado == "entregado" else "ya tiene el pedido"
        raise HTTPException(status_code=400, detail=f"Inteligencia {estado} para la pista de {base.nombre}")
    p = PedidoPmi(escenario_id=esc.id, bando=usuario.rol, base_id=base.id, pedido_por=_quien(usuario),
                  nota=payload.nota.strip(), turno=esc.turno_actual, pedido_seg=esc.sim_segundos)
    db.add(p)
    _evento(db, esc, usuario.rol, f"{p.pedido_por} pidió a Inteligencia (A-2) los puntos medios de impacto de la pista de {base.nombre}.")
    db.commit()
    db.refresh(p)
    await manager.difundir_estado(db, esc)
    return pmi_mod.serializar(p, base)


@router.post("/{pedido_id}/propuesta")
def propuesta(pedido_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
              usuario=Depends(auth.conductor)):
    """A-2: los PMI que propone el sistema sobre la pista (cortes en partes iguales), para revisarlos antes de entregar."""
    auth.exigir_funcion(usuario, "reconocimiento")
    p = _pedido(db, esc, pedido_id, usuario)
    base = db.get(Unidad, p.base_id)
    puntos, pista = pmi_mod.proponer(base)
    return {"puntos": puntos, "pista": pista, "mos_m": pmi_mod.MOS_M}


@router.post("/{pedido_id}/entregar")
async def entregar(pedido_id: int, payload: EntregaIn, esc: Escenario = Depends(auth.escenario_dep),
                   db: Session = Depends(get_db), usuario=Depends(auth.conductor)):
    """A-2 entrega los PMI a Operaciones: desde ahora el ataque a esa pista hace todo su daño."""
    auth.exigir_funcion(usuario, "reconocimiento")
    p = _pedido(db, esc, pedido_id, usuario)
    base = db.get(Unidad, p.base_id)
    puntos = [x.model_dump() for x in payload.puntos]
    motivo = pmi_mod.validar(puntos, base)
    if motivo:
        raise HTTPException(status_code=400, detail=motivo)
    p.puntos_json = json.dumps(pmi_mod.normalizar(puntos))
    p.pista_json = json.dumps(pmi_mod.pista_de(base))
    p.estado, p.entregado_por, p.entregado_seg = "entregado", _quien(usuario), esc.sim_segundos
    _evento(db, esc, usuario.rol, f"{p.entregado_por} entregó a Operaciones {len(puntos)} puntos medios de impacto de la pista "
                                  f"de {base.nombre}: el ataque a esa pista hace ahora todo su daño.")
    db.commit()
    await manager.difundir_estado(db, esc)
    return pmi_mod.serializar(p, base)


@router.post("/{pedido_id}/cancelar")
async def cancelar(pedido_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                   usuario=Depends(auth.conductor)):
    """Quien pide (A-3) o quien entrega (A-2) da de baja el pedido; los PMI entregados dejan de valer."""
    if not (puestos.puede(usuario.puesto, "aereo") or puestos.puede(usuario.puesto, "reconocimiento")):
        auth.exigir_funcion(usuario, "aereo")
    p = _pedido(db, esc, pedido_id, usuario)
    p.estado = "cancelado"
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}
