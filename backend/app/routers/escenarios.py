import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from app import adversario, auth, diapositivas_html, informe_html, schemas, state, turnos
from app.db import get_db
from app.engine import toe
from app.engine import inteligencia
from app.engine import transmisiones
from app.engine import apresto
from app.engine import aar, calendario, clock, naciones, plantillas, timeline
from app.models.aar import Instantanea
from app.models.objetivo import Objetivo
from app.models.problema_militar import ProblemaMilitar
from app.models.documento_tiem import DocumentoTiem
from app.models.asignacion import Asignacion
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios", tags=["escenarios"])
solo_instructor = auth.requiere_roles("instructor")


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


MAX_TURNOS_DE_UNA_VEZ = 24


@router.post("/{escenario_id}/avanzar_turno")
async def avanzar_turno(
    n: int = 1,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(solo_instructor),
):
    """Resuelve el turno; con `n`, varios seguidos (hasta un dia: para recorrer los periodos tranquilos de un
    ejercicio largo). Se detiene si el escenario deja de estar activo."""
    if esc.estado != "activo":
        raise HTTPException(status_code=400, detail="El escenario no esta activo")
    if not 1 <= n <= MAX_TURNOS_DE_UNA_VEZ:
        raise HTTPException(status_code=400, detail=f"Se avanzan entre 1 y {MAX_TURNOS_DE_UNA_VEZ} turnos de una vez")
    for _ in range(n):
        if esc.estado != "activo":
            break
        await turnos.resolver_y_difundir(db, esc)
    return state.estado_para(db, esc, usuario.rol)


@router.post("/{escenario_id}/pcao")
async def ordenar_pcao(
    payload: schemas.PcaoIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    """Ordena la Puesta en Completo Apresto Operacional: el comandante o el JEM del bando, o el instructor. Si el
    bando tiene un Plan de PCAO con los plazos de los 5 eventos, rigen esos plazos."""
    if usuario.rol in ("azul", "rojo"):
        if (usuario.puesto or "comandante") not in ("comandante", "jem"):
            raise HTTPException(status_code=403, detail="La PCAO la ordena el Comandante o el Jefe de Estado Mayor")
        bando = usuario.rol
    elif usuario.rol == "instructor" and payload.bando:
        bando = payload.bando
    else:
        raise HTTPException(status_code=403, detail="Solo el comandante del bando o el instructor ordenan la PCAO")
    c = apresto.config(esc, bando)
    if c["grado"] == "completo":
        raise HTTPException(status_code=400, detail="El bando ya está en Completo Apresto Operacional")
    if c.get("pcao_inicio") is not None:
        raise HTTPException(status_code=400, detail="La PCAO ya está en marcha")
    doc = db.query(DocumentoTiem).filter(DocumentoTiem.escenario_id == esc.id, DocumentoTiem.bando == bando,
                                         DocumentoTiem.tipo == "plan_pcao").one_or_none()
    plazos = apresto.plazos_del_plan(json.loads(doc.contenido_json)) if doc is not None else None
    apresto.iniciar_pcao(esc, bando, esc.turno_actual, plazos)
    p = apresto.progreso(esc, bando, esc.turno_actual)
    db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="direccion", bando_destino=bando,
                  descripcion=f"Se ordenó la Puesta en Completo Apresto Operacional (PCAO): {p['total']} turnos en 5 "
                              f"eventos{' según el Plan de PCAO' if plazos else ''}; termina en el turno "
                              f"{esc.turno_actual + p['total']}."))
    db.commit()
    await manager.difundir_estado(db, esc)
    return apresto.resumen(esc, bando, db.query(Unidad).filter(Unidad.escenario_id == esc.id).all())


@router.put("/{escenario_id}/transmisiones")
async def guardar_transmisiones(
    payload: schemas.PlanTransmisionesIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    """Plan de transmisiones del bando: cada alumno, el de su bando; el instructor, el que indique."""
    if usuario.rol in ("azul", "rojo"):
        bando = usuario.rol
    elif usuario.rol == "instructor" and payload.bando:
        bando = payload.bando
    else:
        raise HTTPException(status_code=403, detail="Solo los alumnos de un bando o el instructor editan el plan")
    transmisiones.guardar(esc, bando, [r.model_dump() for r in payload.redes], esc.turno_actual)
    errores = transmisiones.errores(transmisiones.plan(esc, bando), esc.turno_actual)
    db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="comunicaciones", bando_destino=bando,
                  descripcion=f"Plan de transmisiones actualizado por {usuario.username}"
                              + (f" con {len(errores)} observación(es)." if errores else ": sin observaciones.")))
    db.commit()
    await manager.difundir_estado(db, esc)
    return transmisiones.resumen(esc, bando, esc.turno_actual)


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
                            ("com_perdida_pct", "perdida de mensajes"), ("com_ordenes_pct", "ordenes demoradas")):
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
    for campo, etiqueta in (("niebla", "niebla de guerra"), ("logistica", "consumo y reabastecimiento"),
                            ("efectos_clima", "efectos del clima"), ("fuego_automatico", "fuego automatico (patrullas y antiaerea)")):
        nuevo = getattr(payload, campo)
        if nuevo is not None and nuevo != getattr(esc, campo):
            setattr(esc, campo, nuevo)
            cambios.append(f"{etiqueta} {'activado' if nuevo else 'desactivado'}")
            db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="direccion", bando_destino="todos",
                          descripcion=f"Direccion del ejercicio: {etiqueta} {'activado' if nuevo else 'desactivado'}."))
    if payload.ia_nivel is not None and payload.ia_nivel != esc.ia_nivel:
        esc.ia_nivel = payload.ia_nivel
        cambios.append(f"nivel del adversario automatico: {payload.ia_nivel}")
    if payload.fallas is not None and payload.fallas != esc.fallas:
        esc.fallas = payload.fallas
        cambios.append(f"disponibilidad y fallas de las aeronaves {'activadas' if payload.fallas else 'desactivadas'}")
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="direccion", bando_destino="todos",
                      descripcion="Direccion del ejercicio: disponibilidad y fallas de las aeronaves "
                                  f"{'activadas' if payload.fallas else 'desactivadas'}."))
    if payload.personal is not None:
        actual = {b: toe.config(esc, b) for b in ("azul", "rojo")}
        for bando, datos in payload.personal.items():
            nuevos = {k: v for k, v in datos.model_dump().items() if v is not None}
            if nuevos:
                actual[bando] = {**actual[bando], **nuevos}
                cambios.append(f"personal del bando {bando.capitalize()}: " + ", ".join(f"{k} {v}" for k, v in nuevos.items()))
        esc.personal_json = json.dumps(actual)
    if payload.apresto is not None:
        for bando, datos in payload.apresto.items():
            d = datos.model_dump(exclude_none=True)
            reiniciar = d.pop("reiniciar_pcao", False)
            if reiniciar or d.get("grado") in ("paz", "elevado"):
                d["pcao_inicio"] = None
            c = apresto.guardar(esc, bando, **d)
            cambios.append(f"apresto del bando {bando.capitalize()}: {apresto.NOMBRE_GRADO[c['grado']]}"
                           + (f", fase {apresto.FASES[int(c['fase'])]}" if c["grado"] == "elevado" else ""))
            db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="direccion", bando_destino=bando,
                          descripcion=f"El bando pasa a {apresto.NOMBRE_GRADO[c['grado']]}"
                                      + (f" (fase {apresto.FASES[int(c['fase'])]})." if c["grado"] == "elevado" else ".")))
    if payload.inteligencia is not None:
        for bando, datos in payload.inteligencia.items():
            c = inteligencia.configurar(esc, bando, datos.satelites, datos.tipo)
            cambios.append(f"satélites del bando {bando.capitalize()}: {c['satelites']} ({c['tipo']})")
    if payload.dia_noche is not None and payload.dia_noche != esc.dia_noche:
        esc.dia_noche = payload.dia_noche
        cambios.append(f"ciclo de dia y noche {'activado' if payload.dia_noche else 'desactivado'}")
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="direccion", bando_destino="todos",
                      descripcion=f"Direccion del ejercicio: ciclo de dia y noche {'activado' if payload.dia_noche else 'desactivado'}."))
    for bando in ("azul", "rojo"):
        pedida = getattr(payload, f"conduccion_{bando}")
        if pedida is None or pedida == esc.conduccion(bando):
            continue
        # "ia" enciende el adversario automatico; "alumnos" o "instructor" lo apagan
        setattr(payload, f"ia_{bando}", pedida == "ia")
        if pedida != "ia":
            setattr(esc, f"conduce_{bando}", pedida)
            if not getattr(esc, f"ia_{bando}"):
                cambios.append(f"bando {bando.capitalize()} conducido por {'el instructor' if pedida == 'instructor' else 'los alumnos'}")
                db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="direccion", bando_destino="todos",
                              descripcion=f"Direccion del ejercicio: el bando {bando.capitalize()} lo conduce "
                                          f"{'el instructor' if pedida == 'instructor' else 'el grupo de alumnos'}."))
    _aplicar_calendario(payload, esc, cambios)
    ia_encendida = []
    for campo, etiqueta in (("ia_azul", "adversario automatico del bando Azul"), ("ia_rojo", "adversario automatico del bando Rojo")):
        nuevo = getattr(payload, campo)
        if nuevo is not None and nuevo != getattr(esc, campo):
            setattr(esc, campo, nuevo)
            cambios.append(f"{etiqueta} {'activado' if nuevo else 'desactivado'}")
            db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="direccion", bando_destino="todos",
                          descripcion=f"Direccion del ejercicio: {etiqueta} {'activado' if nuevo else 'desactivado'}."))
            if nuevo:
                ia_encendida.append(campo[3:])
            else:
                setattr(esc, f"listo_{campo[3:]}", False)
    if ia_encendida and esc.estado == "activo" and esc.fase == "decision":
        db.flush()
        adversario.jugar_turno(db, esc, bandos=ia_encendida)  # juega ya el turno en curso
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


def _aplicar_calendario(payload: schemas.EscenarioConfig, esc: Escenario, cambios: list[str]) -> None:
    """Fecha de inicio, hora H, ultimo turno y fases de la operacion (ver engine/calendario.py)."""
    if payload.fecha_inicio is not None and (payload.fecha_inicio or None) != esc.fecha_inicio:
        if payload.fecha_inicio:
            try:
                date.fromisoformat(payload.fecha_inicio)
            except ValueError:
                raise HTTPException(status_code=400, detail="Fecha de inicio invalida")
        esc.fecha_inicio = payload.fecha_inicio or None
        cambios.append(f"fecha del turno 1: {esc.fecha_inicio or 'sin fecha'}")
    if payload.turno_h is not None and (payload.turno_h or None) != esc.turno_h:
        esc.turno_h = payload.turno_h or None
        cambios.append(f"hora H en el turno {esc.turno_h}" if esc.turno_h else "sin hora H")
    if payload.turno_final is not None and (payload.turno_final or None) != esc.turno_final:
        esc.turno_final = payload.turno_final or None
        cambios.append(f"ultimo turno previsto {esc.turno_final}" if esc.turno_final else "sin ultimo turno previsto")
    if esc.turno_h and esc.turno_final and esc.turno_final < esc.turno_h:
        raise HTTPException(status_code=400, detail="El ultimo turno previsto no puede ser anterior a la hora H")
    if payload.fases is not None:
        try:
            fases = calendario.validar_fases([f.model_dump() for f in payload.fases])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        esc.fases_json = json.dumps(fases, ensure_ascii=False) if fases else None
        cambios.append("fases de la operacion " + (", ".join(f["nombre"] for f in fases) if fases else "por defecto"))


@router.post("/{escenario_id}/listo")
async def marcar_listo(
    payload: schemas.ListoIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.conductor),
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
    con_posicion = payload.lat is not None and payload.lon is not None
    evento = Evento(
        escenario_id=esc.id, turno=esc.turno_actual, tipo=payload.tipo,
        descripcion=payload.descripcion, bando_destino=payload.bando_destino,
        lat=payload.lat if con_posicion else None, lon=payload.lon if con_posicion else None,
        hasta_turno=(esc.turno_actual + (payload.turnos or 3)) if con_posicion else None, fuente=payload.fuente.strip(),
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
                      com_jitter_ms=esc.com_jitter_ms, com_perdida_pct=esc.com_perdida_pct, com_ordenes_pct=esc.com_ordenes_pct,
                      dia_noche=esc.dia_noche, ia_nivel=esc.ia_nivel,
                      nacion_azul=esc.nacion_azul, nacion_rojo=esc.nacion_rojo,
                      conduce_azul=esc.conduce_azul, conduce_rojo=esc.conduce_rojo, fecha_inicio=esc.fecha_inicio,
                      turno_h=esc.turno_h, turno_final=esc.turno_final, fases_json=esc.fases_json)
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
    copias: dict[int, Objetivo] = {}
    originales = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).order_by(Objetivo.id).all()
    for o in originales:
        if o.unidad_id is not None and o.unidad_id not in nuevas:
            continue
        copias[o.id] = Objetivo(
            escenario_id=copia.id, bando=o.bando, tipo=o.tipo, nombre=o.nombre, puntos=o.puntos, lat=o.lat, lon=o.lon,
            radio_km=o.radio_km, turnos_requeridos=o.turnos_requeridos, hasta_turno=o.hasta_turno,
            unidad_id=nuevas[o.unidad_id].id if o.unidad_id is not None else None,
            nivel=o.nivel, efecto=o.efecto, indicador=o.indicador, umbral=o.umbral,
        )
        db.add(copias[o.id])
    db.flush()
    for o in originales:  # la cadena de objetivos apunta a las copias
        if o.id in copias and o.padre_id in copias:
            copias[o.id].padre_id = copias[o.padre_id].id
    for pm in db.query(ProblemaMilitar).filter(ProblemaMilitar.escenario_id == esc.id):
        db.add(ProblemaMilitar(escenario_id=copia.id, bando=pm.bando, contenido_json=pm.contenido_json, origen=pm.origen))
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


@router.get("/{escenario_id}/aar/replay")
def informe_replay(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                   usuario: Usuario = Depends(auth.usuario_actual)):
    """Datos para el replay animado del informe: por turno, posiciones de todas las unidades, combates con su
    lugar, novedades publicas y marcador acumulado (mismos permisos que el informe)."""
    _informe_permitido(esc, usuario)
    return aar.construir_replay(db, esc)


@router.get("/{escenario_id}/aar/rubrica")
def informe_rubrica(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                    usuario: Usuario = Depends(auth.usuario_actual)):
    """Rubrica de evaluacion por bando y por puesto responsable (ordenes, turnos pasivos, logistica, perdidas,
    objetivos, misiones y observaciones automaticas)."""
    _informe_permitido(esc, usuario)
    return aar.construir_rubrica(db, esc)


@router.get("/{escenario_id}/aar/rubrica.csv")
def informe_rubrica_csv(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                        usuario: Usuario = Depends(auth.usuario_actual)):
    """Evaluacion por alumno de la rubrica, como CSV (mismos permisos que el informe)."""
    _informe_permitido(esc, usuario)
    contenido = informe_html.render_rubrica_csv(aar.construir_rubrica(db, esc))
    return Response(contenido, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="rubrica_alumnos_{esc.id}.csv"'})


@router.get("/{escenario_id}/aar/diapositivas.html", response_class=HTMLResponse)
def informe_diapositivas(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                         usuario: Usuario = Depends(auth.usuario_actual)):
    """Presentacion automatica para la sesion de analisis posterior (una diapositiva por turno, resumen y rubrica)."""
    _informe_permitido(esc, usuario)
    return HTMLResponse(diapositivas_html.render_diapositivas(aar.construir_informe(db, esc), aar.construir_rubrica(db, esc)))


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
            "conduccion_azul": esc.conduccion_azul, "conduccion_rojo": esc.conduccion_rojo,
            "calendario": esc.calendario,
        },
        "problema_militar": {
            pm.bando: json.loads(pm.contenido_json)
            for pm in db.query(ProblemaMilitar).filter(ProblemaMilitar.escenario_id == esc.id)
        },
        "documentos_tiem": [
            {"bando": d.bando, "tipo": d.tipo, "estado": d.estado, "observaciones": d.observaciones,
             "editado_por": d.editado_por, "presentado_turno": d.presentado_turno, "revisado_turno": d.revisado_turno,
             "contenido": json.loads(d.contenido_json)}
            for d in db.query(DocumentoTiem).filter(DocumentoTiem.escenario_id == esc.id).order_by(DocumentoTiem.id)
        ],
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
