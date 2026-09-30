import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from app import auth, informe_html, schemas, state, turnos
from app.db import get_db
from app.engine import aar, clock, naciones, plantillas, timeline
from app.models.aar import Instantanea
from app.models.objetivo import Objetivo
from app.models.asignacion import Asignacion
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios", tags=["escenarios"])
solo_instructor = auth.requiere_roles("instructor")
solo_alumnos = auth.requiere_roles("azul", "rojo")


async def _difundir_y_estado(db: Session, esc: Escenario, usuario: Usuario, vista: str | None = None):
    await manager.difundir_estado(db, esc)
    return state.estado_para(db, esc, _rol_vista(usuario, vista))


def _rol_vista(usuario: Usuario, vista: str | None) -> str:
    """Solo un instructor puede pedir la vista de un bando ("ver como")."""
    return vista if usuario.rol == "instructor" and vista in state.BANDOS else usuario.rol


@router.post("", response_model=schemas.EscenarioOut)
def crear_escenario(
    payload: schemas.EscenarioCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_instructor),
):
    escenario = Escenario(nombre=payload.nombre)
    db.add(escenario)
    db.commit()
    db.refresh(escenario)
    return escenario


@router.get("", response_model=list[schemas.EscenarioOut])
def listar_escenarios(
    archivados: bool = False,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    q = db.query(Escenario)
    if usuario.rol != "instructor":
        q = q.join(Asignacion, Asignacion.escenario_id == Escenario.id).filter(
            Asignacion.usuario_id == usuario.id
        )
    if not (archivados and usuario.rol == "instructor"):
        q = q.filter(Escenario.archivado.is_(False))
    return q.order_by(Escenario.id.desc()).all()


@router.get("/{escenario_id}")
def obtener_escenario(
    vista: str | None = None,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    return state.estado_para(db, esc, _rol_vista(usuario, vista))


@router.post("/{escenario_id}/avanzar_turno")
async def avanzar_turno(
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_instructor),
):
    if esc.estado != "activo":
        raise HTTPException(status_code=400, detail="El escenario no esta activo")
    await turnos.resolver_y_difundir(db, esc)
    return state.estado_para(db, esc, usuario.rol)


@router.post("/{escenario_id}/pausar")
async def pausar(
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_instructor),
):
    clock.pausar(db, esc)
    return await _difundir_y_estado(db, esc, usuario)


@router.post("/{escenario_id}/reanudar")
async def reanudar(
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_instructor),
):
    if esc.estado == "finalizado":
        raise HTTPException(status_code=400, detail="El escenario ya finalizo")
    clock.reanudar(db, esc)
    return await _difundir_y_estado(db, esc, usuario)


@router.post("/{escenario_id}/finalizar")
async def finalizar(
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_instructor),
):
    clock.finalizar(db, esc)
    return await _difundir_y_estado(db, esc, usuario)


@router.patch("/{escenario_id}/config")
async def configurar(
    payload: schemas.EscenarioConfig,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_instructor),
):
    cambios = []
    if payload.clima is not None and payload.clima != esc.clima:
        esc.clima = payload.clima
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="clima", bando_destino="todos",
                      descripcion=f"El clima cambia a {payload.clima}."))
    if payload.azar is not None and payload.azar != esc.azar:
        esc.azar = payload.azar
        cambios.append(f"azar {'activado' if payload.azar else 'desactivado'}")
    if payload.auto_resolver is not None and payload.auto_resolver != esc.auto_resolver:
        esc.auto_resolver = payload.auto_resolver
        cambios.append(f"resolucion automatica {'activada' if payload.auto_resolver else 'desactivada'}")
    if payload.limite_decision_seg is not None:
        esc.limite_decision_seg = payload.limite_decision_seg or None
        clock.programar_limite(esc)
        cambios.append(f"limite de decision {esc.limite_decision_seg or 'sin limite'} s")
    for campo, etiqueta in (("com_latencia_ms", "latencia de radio"), ("com_jitter_ms", "variacion de latencia"),
                            ("com_perdida_pct", "perdida de mensajes")):
        nuevo = getattr(payload, campo)
        if nuevo is not None and nuevo != getattr(esc, campo):
            setattr(esc, campo, nuevo)
            cambios.append(f"{etiqueta} {nuevo}" + (" %" if campo.endswith("pct") else " ms"))
    if payload.hora_inicio is not None:
        h, m = payload.hora_inicio.split(":")
        nueva = int(h) * 60 + int(m)
        if nueva != esc.hora_inicio_min:
            esc.hora_inicio_min = nueva
            cambios.append(f"hora simulada inicial {payload.hora_inicio}")
    for campo, etiqueta in (("nacion_azul", "Azul"), ("nacion_rojo", "Rojo")):
        nueva_nacion = getattr(payload, campo)
        if nueva_nacion is None or nueva_nacion == getattr(esc, campo):
            continue
        if nueva_nacion and naciones.obtener(nueva_nacion) is None:
            raise HTTPException(status_code=400, detail=f"Nacion desconocida: {nueva_nacion}")
        setattr(esc, campo, nueva_nacion)
        cambios.append(f"bando {etiqueta} representa a {naciones.obtener(nueva_nacion).nombre}" if nueva_nacion else f"bando {etiqueta} sin identidad nacional")
    if cambios:
        aar.registrar_ajuste(db, esc, "Configuracion: " + ", ".join(cambios))
    db.commit()
    return await _difundir_y_estado(db, esc, usuario)


@router.post("/{escenario_id}/listo")
async def marcar_listo(
    payload: schemas.ListoIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_alumnos),
):
    auth.exigir_funcion(usuario, "listo")
    if esc.estado != "activo" or esc.fase != "decision":
        raise HTTPException(status_code=400, detail="El escenario no esta en fase de decision")
    ambos = clock.marcar_listo(db, esc, usuario.rol, payload.listo)
    if ambos and esc.auto_resolver:
        await turnos.resolver_y_difundir(db, esc)
    else:
        await manager.difundir_estado(db, esc)
    return state.estado_para(db, esc, usuario.rol)


@router.post("/{escenario_id}/eventos", response_model=schemas.EventoOut)
async def inyectar_evento(
    payload: schemas.EventoCreate,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_instructor),
):
    evento = Evento(
        escenario_id=esc.id, turno=esc.turno_actual, tipo=payload.tipo,
        descripcion=payload.descripcion, bando_destino=payload.bando_destino,
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    await manager.difundir_estado(db, esc)
    return evento


# ---------- administracion de escenarios ----------
@router.post("/{escenario_id}/archivar")
def archivar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
             _: Usuario = Depends(solo_instructor)):
    esc.archivado = True
    db.commit()
    return {"ok": True}


@router.post("/{escenario_id}/desarchivar")
def desarchivar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                _: Usuario = Depends(solo_instructor)):
    esc.archivado = False
    db.commit()
    return {"ok": True}


@router.post("/{escenario_id}/duplicar", response_model=schemas.EscenarioOut)
def duplicar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
             _: Usuario = Depends(solo_instructor)):
    """Copia el despliegue inicial (posiciones de la primera instantanea, o las actuales
    si aun no se resolvio ningun turno) con toda la fuerza, combustible y municion."""
    base = db.query(Instantanea).filter(Instantanea.escenario_id == esc.id).order_by(Instantanea.turno).first()
    posiciones = {u["id"]: (u["lat"], u["lon"]) for u in json.loads(base.datos_json)["unidades"]} if base else {}

    copia = Escenario(nombre=f"{esc.nombre} (copia)", clima=esc.clima, azar=esc.azar,
                      auto_resolver=esc.auto_resolver, limite_decision_seg=esc.limite_decision_seg,
                      hora_inicio_min=esc.hora_inicio_min, com_latencia_ms=esc.com_latencia_ms,
                      com_jitter_ms=esc.com_jitter_ms, com_perdida_pct=esc.com_perdida_pct,
                      nacion_azul=esc.nacion_azul, nacion_rojo=esc.nacion_rojo)
    db.add(copia)
    db.flush()
    campos = ("nombre", "bando", "tipo", "clase", "echelon", "modelo", "aeronaves", "velocidad_kmh", "alcance_km",
              "deteccion_km", "autonomia_km", "sidc")
    nuevas: dict[int, Unidad] = {}
    for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id).order_by(Unidad.id):
        lat, lon = posiciones.get(u.id, (u.lat, u.lon))
        nuevas[u.id] = Unidad(escenario_id=copia.id, lat=lat, lon=lon, **{c: getattr(u, c) for c in campos})
        db.add(nuevas[u.id])
    db.flush()
    for o in db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).order_by(Objetivo.id):
        if o.unidad_id is not None and o.unidad_id not in nuevas:
            continue
        db.add(Objetivo(
            escenario_id=copia.id, bando=o.bando, tipo=o.tipo, nombre=o.nombre, puntos=o.puntos, lat=o.lat, lon=o.lon,
            radio_km=o.radio_km, turnos_requeridos=o.turnos_requeridos, hasta_turno=o.hasta_turno,
            unidad_id=nuevas[o.unidad_id].id if o.unidad_id is not None else None,
        ))
    for a in db.query(Asignacion).filter(Asignacion.escenario_id == esc.id):
        db.add(Asignacion(usuario_id=a.usuario_id, escenario_id=copia.id))
    db.commit()
    db.refresh(copia)
    return copia


@router.post("/{escenario_id}/guardar_plantilla")
def guardar_plantilla(payload: schemas.PlantillaGuardarIn, esc: Escenario = Depends(auth.escenario_dep),
                      db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    """Guarda las unidades ACTUALES del escenario (con sus objetivos, clima e identidad nacional) como una
    plantilla del instructor, en backend/data/plantillas_usuario/<id>.json; queda en GET /api/plantillas."""
    try:
        p = plantillas.guardar_desde_escenario(db, esc, payload.nombre, payload.descripcion,
                                               payload.con_estado, payload.reemplazar)
    except plantillas.PlantillaInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=f"Ya existe una plantilla con el identificador '{exc}': "
                                                    "cambie el nombre o marque 'reemplazar'")
    return plantillas.plantilla_dict(p)


@router.get("/{escenario_id}/usuarios")
def usuarios_asignados(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                       _: Usuario = Depends(solo_instructor)):
    return {"usuario_ids": [a.usuario_id for a in db.query(Asignacion).filter(Asignacion.escenario_id == esc.id)]}


@router.put("/{escenario_id}/usuarios")
def asignar_usuarios(payload: schemas.AsignacionIn, esc: Escenario = Depends(auth.escenario_dep),
                     db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    ids = set(payload.usuario_ids)
    validos = {
        u.id for u in db.query(Usuario).filter(Usuario.id.in_(ids), Usuario.rol != "instructor")
    } if ids else set()
    db.query(Asignacion).filter(Asignacion.escenario_id == esc.id).delete()
    for uid in validos:
        db.add(Asignacion(usuario_id=uid, escenario_id=esc.id))
    db.commit()
    return {"usuario_ids": sorted(validos)}


# ---------- informe posterior (AAR) ----------
def _informe_permitido(esc: Escenario, usuario: Usuario) -> None:
    """Instructores y observadores ven el informe siempre; los alumnos, solo al finalizar
    (el informe muestra ambos bandos sin niebla de guerra)."""
    if usuario.rol in ("azul", "rojo") and esc.estado != "finalizado":
        raise HTTPException(status_code=403, detail="El informe estara disponible al finalizar el escenario")


@router.get("/{escenario_id}/aar")
def informe_json(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                 usuario: Usuario = Depends(auth.usuario_actual)):
    _informe_permitido(esc, usuario)
    return aar.construir_informe(db, esc)


@router.get("/{escenario_id}/aar/timeline")
def informe_timeline(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                     usuario: Usuario = Depends(auth.usuario_actual)):
    """Linea de tiempo que cruza la logistica (caidas de combustible/municion) con los combates."""
    _informe_permitido(esc, usuario)
    return timeline.construir_timeline(db, esc)


@router.get("/{escenario_id}/aar/rubrica")
def informe_rubrica(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                    usuario: Usuario = Depends(auth.usuario_actual)):
    """Rubrica de evaluacion por bando y por puesto responsable (ordenes, turnos pasivos, logistica, perdidas,
    objetivos, misiones y observaciones automaticas)."""
    _informe_permitido(esc, usuario)
    return aar.construir_rubrica(db, esc)


@router.get("/{escenario_id}/aar.html", response_class=HTMLResponse)
def informe_html_(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                  usuario: Usuario = Depends(auth.usuario_actual)):
    _informe_permitido(esc, usuario)
    return HTMLResponse(informe_html.render_html(aar.construir_informe(db, esc), aar.construir_rubrica(db, esc)))


@router.get("/{escenario_id}/aar.csv")
def informe_csv(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                usuario: Usuario = Depends(auth.usuario_actual)):
    _informe_permitido(esc, usuario)
    contenido = informe_html.render_csv(aar.construir_informe(db, esc))
    return Response(contenido, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="combates_{esc.id}.csv"'})


@router.get("/{escenario_id}/exportar")
def exportar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
             _: Usuario = Depends(solo_instructor)):
    """Definicion del escenario (unidades y configuracion) mas su informe, como JSON."""
    unidades = [
        {c.name: getattr(u, c.name) for c in Unidad.__table__.columns if c.name not in ("id", "escenario_id")}
        for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id).order_by(Unidad.id)
    ]
    cuerpo = {
        "version": 1,
        "exportado_en": datetime.now(timezone.utc).isoformat(),
        "escenario": {
            "nombre": esc.nombre, "clima": esc.clima, "azar": esc.azar, "semilla": esc.semilla,
            "auto_resolver": esc.auto_resolver, "limite_decision_seg": esc.limite_decision_seg,
            "nacion_azul": esc.nacion_azul, "nacion_rojo": esc.nacion_rojo,
        },
        "unidades": unidades,
        "objetivos": [
            {c.name: getattr(o, c.name) for c in Objetivo.__table__.columns if c.name not in ("id", "escenario_id")}
            for o in db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).order_by(Objetivo.id)
        ],
        "informe": aar.construir_informe(db, esc),
        "timeline": timeline.construir_timeline(db, esc),
        "rubrica": aar.construir_rubrica(db, esc),
    }
    return JSONResponse(cuerpo, headers={"Content-Disposition": f'attachment; filename="escenario_{esc.id}.json"'})
