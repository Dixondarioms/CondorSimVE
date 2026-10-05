import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas, state
from app.db import get_db
from app.engine import aeronaves as aeronaves_mod
from app.engine import catalogo, geo, movimiento, puestos
from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.engine import misiles as misiles_mod
from app.engine import transporte as transporte_mod
from app.engine import misiones as misiones_mod
from app.engine.orders import COSTO_OBRA, tipo_efectivo
from app.models.escenario import Escenario
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.terreno import get_terreno
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/ordenes", tags=["ordenes"])
solo_alumnos = auth.requiere_roles("azul", "rojo")


def _en_decision(esc: Escenario) -> Escenario:
    if esc.estado != "activo":
        raise HTTPException(status_code=400, detail=f"El escenario esta {esc.estado}")
    if esc.fase != "decision":
        raise HTTPException(status_code=400, detail="El escenario no esta en fase de decision")
    return esc


def _unidad_propia(db: Session, esc: Escenario, unidad_id: int, usuario: Usuario) -> Unidad:
    unidad = db.get(Unidad, unidad_id)
    if unidad is None or unidad.escenario_id != esc.id or unidad.bando != usuario.rol:
        # Mismo mensaje para "no existe" y "es del otro bando": no revela unidades ocultas.
        raise HTTPException(status_code=404, detail="Unidad no encontrada")
    if unidad.estado != "activa":
        raise HTTPException(status_code=400, detail="La unidad ya no esta activa")
    return unidad


def _validar_waypoints(waypoints) -> None:
    if not waypoints:
        raise HTTPException(status_code=400, detail="Indique al menos un waypoint")
    for lat, lon in waypoints:
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise HTTPException(status_code=400, detail="Waypoint fuera de rango")


def _crear_orden(payload: schemas.OrdenCreate, esc: Escenario, db: Session, usuario: Usuario) -> Orden:
    """Valida y agrega (sin confirmar) la orden de una unidad; lanza HTTPException con el motivo si no procede."""
    if payload.unidad_id is None:
        raise HTTPException(status_code=400, detail="Indique la unidad")
    unidad = _unidad_propia(db, esc, payload.unidad_id, usuario)
    if unidad.tipo == "base" and payload.tipo not in ("mover", "despegar"):
        raise HTTPException(status_code=400, detail="Una base no puede combatir ni apoyar")
    if catalogo.es_misil(unidad):
        raise HTTPException(status_code=400, detail=misiles_mod.MOTIVO_SIN_ORDENES)
    if transporte_mod.embarcada(unidad):
        raise HTTPException(status_code=400, detail="La unidad viaja a bordo de un transporte: primero debe desembarcar")
    if payload.tipo == "despegar" and not catalogo.opera_aeronaves(unidad):
        raise HTTPException(status_code=400, detail="Solo una base aerea o un portaaviones puede lanzar grupos")

    clase = catalogo.perfil(unidad)
    auth.exigir_funcion(usuario, puestos.funcion_de_orden(unidad, payload.tipo, clase))
    if payload.tipo in ("patrullar", "aterrizar") and unidad.tipo != "aerea":
        raise HTTPException(status_code=400, detail="Solo las aeronaves pueden patrullar o aterrizar")
    if unidad.en_tierra and unidad.espera_restante > 0 and payload.tipo in ("mover", "atacar", "patrullar"):
        raise HTTPException(
            status_code=400,
            detail=f"En tierra: faltan {unidad.espera_restante} turno(s) para reabastecer y rearmar antes de despegar",
        )
    if unidad.en_tierra and payload.tipo == "apoyar":
        raise HTTPException(status_code=400, detail="Una aeronave en tierra no puede apoyar: debe despegar primero")
    if payload.tipo == "despegar":
        # el despegue pendiente de esta misma base sera reemplazado: no cuenta para el tope
        previa = db.query(Orden).filter(
            Orden.escenario_id == esc.id, Orden.unidad_id == unidad.id, Orden.estado == "pendiente"
        ).first()
        motivo = aeronaves_mod.error_de_despegue(
            unidad, payload.modelo, payload.aeronaves,
            aeronaves_mod.aeronaves_comprometidas(db, esc.id, usuario.rol, previa.id if previa else None,
                                                  aeronaves_mod.es_dron_modelo(payload.modelo)),
        )
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
    elif payload.tipo == "aterrizar":
        base = db.get(Unidad, payload.objetivo_unidad_id) if payload.objetivo_unidad_id else None
        if base is None or base.escenario_id != esc.id or base.bando != usuario.rol:
            raise HTTPException(status_code=404, detail="Elija una base aerea propia")
        todas = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == usuario.rol).all()
        motivo = aeronaves_mod.error_de_aterrizaje(unidad, base, todas)
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
    elif payload.tipo == "patrullar":
        if len(payload.waypoints) != 1:
            raise HTTPException(status_code=400, detail="Indique un unico punto de patrulla")
        _validar_waypoints(payload.waypoints)
        if unidad.combustible <= aeronaves_mod.COMBUSTIBLE_CRITICO:
            raise HTTPException(status_code=400, detail="Combustible insuficiente para patrullar: aterrice y reabastezca")
    elif payload.tipo == "construir":
        if not clase.construye:
            raise HTTPException(status_code=400, detail="Solo los ingenieros pueden construir puentes y vados")
        if payload.detalle is None:
            raise HTTPException(status_code=400, detail="Indique si construye un puente o un vado")
        if len(payload.waypoints) != 1:
            raise HTTPException(status_code=400, detail="Indique un unico punto de construccion")
        _validar_waypoints(payload.waypoints)
        lat, lon = payload.waypoints[0]
        if geo.distancia_km(unidad.lat, unidad.lon, lat, lon) > unidad.alcance_km:
            raise HTTPException(
                status_code=400,
                detail=f"El punto esta fuera del alcance de trabajo ({unidad.alcance_km:.0f} km): acerque primero a los ingenieros",
            )
        if not get_terreno().hay_rio_cerca(lat, lon, 1.0):
            raise HTTPException(status_code=400, detail="El punto no esta sobre un rio")
        if unidad.municion < COSTO_OBRA[payload.detalle]:
            raise HTTPException(status_code=400, detail="Material insuficiente para esa obra")
    elif payload.tipo == "interferir":
        if len(payload.waypoints) != 1:
            raise HTTPException(status_code=400, detail="Indique un unico punto: el centro de la zona a interferir")
        _validar_waypoints(payload.waypoints)
        motivo = ge_mod.error_de_interferencia(unidad, payload.waypoints[0])
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
    elif payload.tipo == "embarcar":
        t = db.get(Unidad, payload.objetivo_unidad_id) if payload.objetivo_unidad_id else None
        if t is None or t.escenario_id != esc.id or t.bando != usuario.rol:
            raise HTTPException(status_code=404, detail="Elija un transporte propio")
        todas = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == usuario.rol).all()
        motivo = transporte_mod.error_de_embarque(unidad, t, todas)
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
    elif payload.tipo == "desembarcar":
        _validar_waypoints(payload.waypoints)
        todas = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == usuario.rol).all()
        motivo = transporte_mod.error_de_desembarco(unidad, list(payload.waypoints[-1]), get_terreno(), todas)
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
    elif payload.tipo == "lanzar":
        if payload.objetivo_unidad_id is None:
            raise HTTPException(status_code=400, detail="Indique la unidad blanco de los misiles")
        visibles = {u.id: u for u in state.unidades_visibles_para(db, esc, usuario.rol)}
        blanco = visibles.get(payload.objetivo_unidad_id)
        if blanco is None or blanco.estado != "activa":
            raise HTTPException(status_code=404, detail="Blanco no visible o inexistente")
        motivo = misiles_mod.error_de_lanzamiento(unidad, blanco, payload.misiles)
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
    elif payload.tipo == "mover":
        if unidad.tipo == "base" or unidad.velocidad_kmh <= 0:
            raise HTTPException(status_code=400, detail="Esta unidad no puede moverse")
        if unidad.combustible <= 0:
            raise HTTPException(status_code=400, detail="La unidad no tiene combustible")
        _validar_waypoints(payload.waypoints)
    else:  # atacar / apoyar
        if payload.objetivo_unidad_id is None:
            raise HTTPException(status_code=400, detail="Indique la unidad objetivo")
        if unidad.municion <= 0:
            raise HTTPException(status_code=400, detail="La unidad no tiene municion")
        visibles = {u.id: u for u in state.unidades_visibles_para(db, esc, usuario.rol)}
        objetivo = visibles.get(payload.objetivo_unidad_id)
        if objetivo is None or objetivo.estado != "activa":
            raise HTTPException(status_code=404, detail="Objetivo no visible o inexistente")
        if payload.tipo == "atacar" and objetivo.bando == usuario.rol:
            raise HTTPException(status_code=400, detail="No puede atacar una unidad propia")
        if payload.tipo == "atacar" and clase.ataque_vs.get(tipo_efectivo(objetivo), 0.0) <= 0:
            raise HTTPException(
                status_code=400, detail=f"{clase.nombre} no puede atacar objetivos de tipo {tipo_efectivo(objetivo)}"
            )
        if payload.tipo == "apoyar" and (objetivo.bando != usuario.rol or objetivo.id == unidad.id):
            raise HTTPException(status_code=400, detail="Solo puede apoyar a otra unidad propia")
        if payload.tipo == "atacar" and payload.parte and not catalogo.opera_aeronaves(objetivo):
            raise HTTPException(status_code=400, detail="Solo una base aerea o un portaaviones tiene partes (pista, plataforma, combustible)")

    # Una orden directa a un grupo aereo reemplaza su mision (redireccionamiento).
    if unidad.tipo == "aerea":
        misiones_mod.cancelar_por_orden(db, unidad, payload.tipo)
    # Una unidad tiene una sola orden por turno: la nueva reemplaza a la pendiente.
    db.query(Orden).filter(
        Orden.escenario_id == esc.id, Orden.unidad_id == unidad.id, Orden.estado == "pendiente",
    ).delete()

    orden = Orden(
        escenario_id=esc.id,
        unidad_id=unidad.id,
        tipo=payload.tipo,
        waypoints_json=json.dumps(payload.waypoints if payload.tipo in ("mover", "construir", "patrullar", "interferir", "desembarcar") else []),
        objetivo_unidad_id=payload.objetivo_unidad_id if payload.tipo in ("atacar", "apoyar", "aterrizar", "lanzar", "embarcar") else None,
        detalle=(
            aeronaves_mod.codificar(payload.modelo, payload.aeronaves, (payload.indicativo or "").strip())
            if payload.tipo == "despegar"
            else misiles_mod.codificar(payload.misiles) if payload.tipo == "lanzar"
            else (payload.parte or "") if payload.tipo == "atacar"
            else payload.detalle or "" if payload.tipo == "construir" else ""
        ),
        turno_emitida=esc.turno_actual,
        **puestos.firma(usuario),
    )
    db.add(orden)
    return orden


@router.post("", response_model=schemas.OrdenOut)
async def emitir_orden(
    payload: schemas.OrdenCreate,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_alumnos),
):
    _en_decision(esc)
    orden = _crear_orden(payload, esc, db, usuario)
    # Emitir una orden nueva invalida el "listo" del bando: debe confirmarlo otra vez.
    setattr(esc, f"listo_{usuario.rol}", False)
    db.commit()
    db.refresh(orden)

    await manager.difundir_estado(db, esc)
    return orden


def _desplazar(waypoints, dlat: float, dlon: float):
    return [(w[0] + dlat, w[1] + dlon) for w in waypoints]


@router.post("/lote")
async def emitir_lote(
    payload: schemas.OrdenLote,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_alumnos),
):
    """La misma orden para varias unidades (seleccion multiple). Con `formacion`, los waypoints de cada unidad se
    desplazan segun su posicion relativa al lider (la primera), de modo que el conjunto conserva su formacion.
    Devuelve el resultado por unidad; las que fallan no impiden a las demas."""
    _en_decision(esc)
    lider = db.get(Unidad, payload.unidad_ids[0])
    resultados = []
    for uid in payload.unidad_ids:
        datos = payload.orden.model_dump()
        datos["unidad_id"] = uid
        u = db.get(Unidad, uid)
        if payload.formacion and payload.orden.tipo in ("mover", "desembarcar") and lider is not None and u is not None and datos.get("waypoints"):
            datos["waypoints"] = _desplazar(datos["waypoints"], u.lat - lider.lat, u.lon - lider.lon)
        try:
            orden = _crear_orden(schemas.OrdenCreate(**datos), esc, db, usuario)
            db.flush()
            resultados.append({"unidad_id": uid, "ok": True, "orden_id": orden.id})
        except HTTPException as e:
            resultados.append({"unidad_id": uid, "ok": False, "detalle": e.detail})
    if any(r["ok"] for r in resultados):
        setattr(esc, f"listo_{usuario.rol}", False)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"resultados": resultados, "emitidas": sum(1 for r in resultados if r["ok"])}


@router.post("/previsualizar")
def previsualizar(
    payload: schemas.PrevisualizarIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_alumnos),
):
    """Donde terminaria la unidad este turno con esos waypoints (terreno, clima y
    combustible incluidos), sin emitir la orden."""
    unidad = _unidad_propia(db, esc, payload.unidad_id, usuario)
    _validar_waypoints(payload.waypoints)
    mov = movimiento.simular(unidad, [list(w) for w in payload.waypoints], get_terreno(), clima_mod.contexto(db, esc))
    return {
        "ruta": mov.ruta,
        "destino": [mov.lat, mov.lon],
        "km": round(mov.km_reales, 1),
        "combustible_restante": round(max(0.0, unidad.combustible - mov.combustible_gastado), 1),
        "llega": bool(payload.waypoints) and [round(mov.lat, 5), round(mov.lon, 5)]
        == [round(payload.waypoints[-1][0], 5), round(payload.waypoints[-1][1], 5)],
        "nota": mov.nota,
    }


@router.delete("/{orden_id}")
async def cancelar_orden(
    orden_id: int,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_alumnos),
):
    _en_decision(esc)
    orden = db.get(Orden, orden_id)
    unidad = db.get(Unidad, orden.unidad_id) if orden else None
    if orden is None or orden.escenario_id != esc.id or unidad.bando != usuario.rol:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    auth.exigir_funcion(usuario, puestos.funcion_de_orden(unidad, orden.tipo, catalogo.perfil(unidad)))
    if orden.estado != "pendiente":
        raise HTTPException(status_code=400, detail="Solo se pueden cancelar ordenes pendientes")
    db.delete(orden)
    setattr(esc, f"listo_{usuario.rol}", False)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}


@router.get("", response_model=list[schemas.OrdenOut])
def listar_ordenes(
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    q = db.query(Orden).filter(Orden.escenario_id == esc.id)
    if state.es_bando(usuario.rol):
        propias = [
            u.id
            for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == usuario.rol)
        ]
        q = q.filter(Orden.unidad_id.in_(propias))
    return q.order_by(Orden.id).all()
