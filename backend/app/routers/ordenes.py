import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas, state
from app.db import get_db
from app.engine import aeronaves as aeronaves_mod
from app.engine import armas as armas_mod
from app.engine import asw as asw_mod
from app.engine import minas as minas_mod
from app.engine import catalogo, geo, infraestructura, movimiento, puestos
from app.engine import clima as clima_mod
from app.engine import doctrina as doctrina_mod
from app.engine import guerra_electronica as ge_mod
from app.engine import interceptacion as intercep_mod
from app.engine import misiles as misiles_mod
from app.engine import transporte as transporte_mod
from app.engine import zonas as zonas_mod
from app.engine import misiones as misiones_mod
from app.engine import rutas as rutas_mod
from app.engine import tiempo_real
from app.engine.orders import COSTO_OBRA, tipo_efectivo
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.obra import Obra
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.models.zona import Zona
from app.terreno import get_terreno
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/ordenes", tags=["ordenes"])


def _en_decision(esc: Escenario) -> Escenario:
    """En tiempo real se dan ordenes en todo momento (tambien con el reloj detenido), salvo al finalizar."""
    if esc.estado == "finalizado":
        raise HTTPException(status_code=400, detail="El escenario ya finalizo")
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
    if payload.tipo not in tiempo_real.TIPOS_DE_ORDEN:
        raise HTTPException(status_code=400, detail=tiempo_real.MOTIVO_ETAPA)
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
    area = None
    if payload.tipo == "patrullar" and payload.zona_id is not None:
        area = db.get(Zona, payload.zona_id)
        if area is None or area.escenario_id != esc.id or not zonas_mod.visible(area, usuario.rol) or area.tipo != "patrulla":
            raise HTTPException(status_code=404, detail="Elija un área de patrulla de su bando o de la dirección")
        if unidad.velocidad_kmh <= 0:
            raise HTTPException(status_code=400, detail="Esta unidad no puede moverse")
    if (payload.tipo == "aterrizar" or (payload.tipo == "patrullar" and area is None)) and unidad.tipo != "aerea":
        raise HTTPException(status_code=400, detail="Solo las aeronaves pueden aterrizar u orbitar sobre un punto: "
                                                    "las demás unidades patrullan un área")
    if unidad.en_tierra and unidad.espera_restante > 0 and payload.tipo in ("mover", "atacar", "patrullar", "interceptar",
                                                                            "sonoboyas", "sonar", "minar"):
        raise HTTPException(
            status_code=400,
            detail=f"En tierra: le falta {_falta_texto(esc, unidad)} para reabastecer y rearmar antes de despegar",
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
        motivo = armas_mod.error_de_carga(payload.modelo, payload.carga, payload.aeronaves or 1, unidad)
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
    elif payload.tipo == "patrullar" and area is not None:
        payload.waypoints = [zonas_mod.centro(zonas_mod.puntos(area))]
        if unidad.tipo == "aerea" and unidad.combustible <= aeronaves_mod.COMBUSTIBLE_CRITICO:
            raise HTTPException(status_code=400, detail="Combustible insuficiente para patrullar: aterrice y reabastezca")
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
        if asw_mod.es_submarino(unidad) and asw_mod.profundidad(unidad) == "profunda":
            raise HTTPException(status_code=400, detail="A profundidad no se lanzan misiles: suba a cota periscópica")
        if unidad.recarga_hasta and unidad.recarga_hasta > (esc.sim_segundos or 0.0):
            minutos = max(1, round((unidad.recarga_hasta - (esc.sim_segundos or 0.0)) / 60))
            raise HTTPException(status_code=400, detail=f"El lanzador está recargando: faltan {minutos} min para otra salva")
    elif payload.tipo == "rumbo":
        if unidad.tipo != "aerea" or unidad.en_tierra:
            raise HTTPException(status_code=400, detail="Solo una aeronave en vuelo recibe un rumbo: en tierra, ordene Mover para despegar")
        if unidad.combustible <= 0:
            raise HTTPException(status_code=400, detail="La aeronave no tiene combustible")
        if payload.rumbo_modo is None or payload.rumbo_grados is None:
            raise HTTPException(status_code=400, detail="Indique si vira unos grados o toma un rumbo, y cuántos grados")
        if payload.rumbo_modo == "virar" and payload.rumbo_sentido not in ("derecha", "izquierda"):
            raise HTTPException(status_code=400, detail="Indique si vira a la derecha o a la izquierda")
        if payload.rumbo_modo == "virar" and not 0 < payload.rumbo_grados < 360:
            raise HTTPException(status_code=400, detail="El viraje va de 1 a 359 grados")
    elif payload.tipo == "torpedo":
        blanco = {u.id: u for u in state.unidades_visibles_para(db, esc, usuario.rol)}.get(payload.objetivo_unidad_id or -1)
        motivo = asw_mod.error_de_torpedo(unidad, blanco) if blanco is not None else "Blanco no detectado por su bando"
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
    elif payload.tipo in ("minar", "barrer"):
        motivo = minas_mod.error_de_siembra(unidad) if payload.tipo == "minar" else (
            None if minas_mod.barre(unidad) else "Barren minas los cazaminas")
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
        if len(payload.waypoints) != 1:
            raise HTTPException(status_code=400, detail="Indique un único punto en el mapa")
        _validar_waypoints(payload.waypoints)
    elif payload.tipo in ("sonoboyas", "sonar"):
        if payload.tipo == "sonoboyas" and not asw_mod.es_avion_asw(unidad):
            raise HTTPException(status_code=400, detail="Siembran sonoboyas los aviones de patrulla marítima (P-3, P-8)")
        if payload.tipo == "sonar" and not asw_mod.es_helo_asw(unidad):
            raise HTTPException(status_code=400, detail="El sonar de inmersión es de los helicópteros antisubmarinos")
        if len(payload.waypoints) != 1:
            raise HTTPException(status_code=400, detail="Indique un único punto en el mapa")
        _validar_waypoints(payload.waypoints)
        if unidad.combustible <= aeronaves_mod.COMBUSTIBLE_CRITICO:
            raise HTTPException(status_code=400, detail="Combustible insuficiente: aterrice y reabastezca")
    elif payload.tipo == "interceptar":
        blanco = _blanco_de_intercepcion(db, esc, usuario, payload.objetivo_unidad_id)
        motivo = intercep_mod.puede_interceptar(unidad, blanco, payload.accion_intercepcion or "")
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
        if unidad.combustible <= aeronaves_mod.COMBUSTIBLE_CRITICO:
            raise HTTPException(status_code=400, detail="Combustible insuficiente para interceptar: aterrice y reabastezca")
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

    # Una aeronave en tierra sale con la carga pedida: devuelve la que tenia y se arma con la nueva desde su base.
    if payload.carga and payload.tipo != "despegar" and unidad.en_tierra and armas_mod.aplica(unidad):
        base = db.get(Unidad, unidad.base_id) if unidad.base_id else None
        motivo = armas_mod.error_de_carga(unidad.modelo, payload.carga, unidad.aeronaves or 1, base)
        if motivo:
            raise HTTPException(status_code=400, detail=motivo)
        if base is not None and armas_mod.tiene_carga(unidad):
            armas_mod.devolver(base, armas_mod.datos(unidad)["quedan"])
        armas_mod.armar(unidad, payload.carga, base)
    # Una orden directa a un grupo aereo reemplaza su mision (redireccionamiento).
    if unidad.tipo == "aerea":
        misiones_mod.cancelar_por_orden(db, unidad, payload.tipo)
    # un dron dentro de una interferencia enemiga pierde el enlace de datos: no recibe ordenes
    if ge_mod.enlace_perdido(unidad, ge_mod.contexto(db, esc)):
        raise HTTPException(status_code=400, detail=ge_mod.MOTIVO_SIN_ENLACE)
    # comunicaciones: la orden puede tardar en llegar (sigue con la que cumplia hasta que llegue la nueva)
    demora = tiempo_real.demora_de_orden(db, esc, unidad, payload.tipo)
    # Una unidad cumple una sola orden a la vez: la nueva reemplaza a la que estaba cumpliendo (al instante). El
    # despegue y el lanzamiento son de la base o del lanzador y no interrumpen lo que hace.
    if payload.tipo not in ("despegar", "lanzar", "torpedo") and not demora:
        tiempo_real.cancelar_ordenes_de(db, unidad, "Reemplazada por una nueva orden.", tiempo_real.hora_del_dia(esc))
    elif demora:  # una orden demorada reemplaza a otra que tambien esperaba llegar
        for previa in db.query(Orden).filter(Orden.unidad_id == unidad.id, Orden.estado == "pendiente"):
            previa.estado, previa.resultado = "cancelada", "Reemplazada por una nueva orden antes de llegar."

    orden = Orden(
        escenario_id=esc.id,
        unidad_id=unidad.id,
        tipo=payload.tipo,
        waypoints_json=json.dumps(payload.waypoints if payload.tipo in ("mover", "construir", "patrullar", "interferir", "desembarcar",
                                                                  "sonoboyas", "sonar", "minar", "barrer") else []),
        objetivo_unidad_id=payload.objetivo_unidad_id if payload.tipo in ("atacar", "apoyar", "aterrizar", "lanzar", "embarcar", "interceptar",
                                                                    "torpedo") else None,
        detalle=(
            aeronaves_mod.codificar(payload.modelo, payload.aeronaves, (payload.indicativo or "").strip(), payload.carga)
            if payload.tipo == "despegar"
            else misiles_mod.codificar(payload.misiles) if payload.tipo == "lanzar"
            else (payload.parte or "") if payload.tipo == "atacar"
            else json.dumps({"modo": payload.rumbo_modo, "grados": payload.rumbo_grados,
                             "sentido": payload.rumbo_sentido or "corto"}) if payload.tipo == "rumbo"
            else intercep_mod.codificar(payload.accion_intercepcion) if payload.tipo == "interceptar"
            else json.dumps({"zona": payload.zona_id}) if payload.tipo == "patrullar" and payload.zona_id is not None
            else payload.detalle or "" if payload.tipo == "construir" else ""
        ),
        turno_emitida=esc.turno_actual,
        **puestos.firma(usuario),
    )
    db.add(orden)
    db.flush()
    if demora:
        orden.emitida_seg, orden.llega_seg = esc.sim_segundos, esc.sim_segundos + demora
        llega = tiempo_real.hora_del_dia(esc, esc.sim_segundos + demora)
        orden.resultado = (f"Comunicaciones: la orden no llegó a tiempo"
                           + (" (interferencia enemiga)" if ge_mod.contexto(db, esc).interferido(unidad) else "")
                           + f"; llegará a {unidad.nombre} a las {llega}.")
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="comunicaciones", bando_destino=unidad.bando,
                      descripcion=f"[{tiempo_real.hora_del_dia(esc)}] {orden.resultado}"))
        return orden
    tiempo_real.aplicar_orden(db, esc, orden, unidad)
    return orden


def _blanco_de_intercepcion(db: Session, esc: Escenario, usuario: Usuario, blanco_id: int | None) -> Unidad:
    if blanco_id is None:
        raise HTTPException(status_code=400, detail="Elija el blanco a interceptar")
    blanco = {u.id: u for u in state.unidades_visibles_para(db, esc, usuario.rol)}.get(blanco_id)
    if blanco is None or blanco.estado != "activa" or blanco.bando == usuario.rol:
        raise HTTPException(status_code=404, detail="Blanco no detectado por su bando")
    return blanco


def _falta_texto(esc: Escenario, unidad: Unidad) -> str:
    """Tiempo simulado que le falta a una aeronave en tierra para quedar lista ("1 h 20 min")."""
    if unidad.espera_hasta is None:
        return f"{unidad.espera_restante} h"
    minutos = max(1, round((unidad.espera_hasta - (esc.sim_segundos or 0.0)) / 60.0))
    return f"{minutos // 60} h {minutos % 60} min" if minutos >= 60 else f"{minutos} min"


@router.post("", response_model=schemas.OrdenOut)
async def emitir_orden(
    payload: schemas.OrdenCreate,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.conductor),
):
    _en_decision(esc)
    orden = _crear_orden(payload, esc, db, usuario)
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
    usuario: Usuario = Depends(auth.conductor),
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
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"resultados": resultados, "emitidas": sum(1 for r in resultados if r["ok"])}


@router.post("/previsualizar")
def previsualizar(
    payload: schemas.PrevisualizarIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.conductor),
):
    """Donde terminaria la unidad este turno con esos waypoints (terreno, clima y
    combustible incluidos), sin emitir la orden."""
    unidad = _unidad_propia(db, esc, payload.unidad_id, usuario)
    _validar_waypoints(payload.waypoints)
    obras = _obras_y_cortes(db, esc)
    clima = clima_mod.contexto(db, esc)
    wps = [list(w) for w in payload.waypoints]
    mov = movimiento.simular(unidad, wps, get_terreno(), clima, obras)
    # tiempo de TODO el recorrido (no solo este turno): horas, turnos y hora simulada de llegada
    tiempo = movimiento.tiempo_recorrido(unidad, wps, get_terreno(), clima, obras)
    if tiempo["horas"] and not tiempo["bloqueo"]:
        ahora = (esc.hora_inicio_min or 0) + int((esc.sim_segundos or 0.0) // 60)
        llegada = ahora + round(tiempo["horas"] * 60)
        tiempo["llegada"] = f"{llegada % 1440 // 60:02d}:{llegada % 60:02d}"
        tiempo["llegada_dias"] = llegada // 1440 - ahora // 1440
    return {
        "tiempo": tiempo,
        "ruta": mov.ruta,
        "destino": [mov.lat, mov.lon],
        "km": round(mov.km_reales, 1),
        "combustible_restante": round(max(0.0, unidad.combustible - mov.combustible_gastado), 1),
        "llega": bool(payload.waypoints) and [round(mov.lat, 5), round(mov.lon, 5)]
        == [round(payload.waypoints[-1][0], 5), round(payload.waypoints[-1][1], 5)],
        "nota": mov.nota,
    }


@router.post("/interceptacion")
def estimar_intercepcion(
    payload: schemas.IntercepcionIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.conductor),
):
    """Antes de emitir la orden: si alcanza al blanco, en cuanto tiempo, donde, con cuanto combustible llega y con
    cuanto le queda para volver a la base; y si la doctrina le exige identificarlo antes de tirar."""
    unidad = _unidad_propia(db, esc, payload.unidad_id, usuario)
    blanco = _blanco_de_intercepcion(db, esc, usuario, payload.objetivo_unidad_id)
    accion = payload.accion_intercepcion or "neutralizar"
    salida = {"motivo_no": intercep_mod.puede_interceptar(unidad, blanco, accion)}
    if salida["motivo_no"] is None:
        propias = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == usuario.rol).all()
        salida.update(intercep_mod.estimar(unidad, blanco, propias))
        estado = doctrina_mod.de_unidad(esc, unidad)[intercep_mod.dominio(blanco)]
        salida["identifica"] = bool(esc.niebla) and intercep_mod.necesita_identificar(accion, estado)
        salida["armas"] = estado
        if salida.get("minutos") is not None:
            salida["hora"] = tiempo_real.hora_del_dia(esc, (esc.sim_segundos or 0.0) + salida["minutos"] * 60.0)
    return salida


@router.post("/ruta")
def trazar_ruta(
    payload: schemas.RutaIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.conductor),
):
    """Waypoints del camino mas rapido de la unidad hasta `destino`, por carreteras y puentes reales y las obras
    vigentes del bando, sin emitir la orden (el alumno la revisa y la emite como un "mover")."""
    unidad = _unidad_propia(db, esc, payload.unidad_id, usuario)
    _validar_waypoints([payload.destino])
    return rutas_mod.ruta(unidad, list(payload.destino), get_terreno(), _obras_y_cortes(db, esc))


def _obras_y_cortes(db: Session, esc: Escenario) -> list:
    """Obras vigentes de los ingenieros y puentes de infraestructura cortados (los conoce todo el mundo)."""
    obras = db.query(Obra).filter(Obra.escenario_id == esc.id, Obra.expira_turno >= esc.turno_actual).all()
    unidades = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.tipo == "base").all()
    return obras + infraestructura.cortes(unidades)


@router.delete("/{orden_id}")
async def cancelar_orden(
    orden_id: int,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.conductor),
):
    _en_decision(esc)
    orden = db.get(Orden, orden_id)
    unidad = db.get(Unidad, orden.unidad_id) if orden else None
    if orden is None or orden.escenario_id != esc.id or unidad.bando != usuario.rol:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    auth.exigir_funcion(usuario, puestos.funcion_de_orden(unidad, orden.tipo, catalogo.perfil(unidad)))
    if orden.estado not in ("pendiente", "en_ejecucion"):
        raise HTTPException(status_code=400, detail="Esa orden ya terminó")
    # detener: la unidad deja de cumplir la orden y se queda donde esta (una aeronave, orbitando alli)
    tiempo_real.detener(db, esc, unidad)
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
