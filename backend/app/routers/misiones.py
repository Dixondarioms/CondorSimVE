"""Misiones aereas: planificar (rol + ruta), previsualizar la estimacion, listar y cancelar/abortar."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas, state
from app.db import get_db
from app.engine import aeronaves as aeronaves_mod
from app.engine import catalogo, puestos
from app.engine import misiones as misiones_mod
from app.models.escenario import Escenario
from app.models.mision import Mision
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.routers.ordenes import _en_decision
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/misiones", tags=["misiones"])
solo_alumnos = auth.requiere_roles("azul", "rojo")


def _preparar(payload: schemas.MisionIn, esc: Escenario, db: Session, usuario: Usuario) -> dict:
    """Valida el origen (grupo o base), normaliza los puntos y estima la ruta. No escribe nada."""
    if (payload.unidad_id is None) == (payload.base_id is None):
        raise HTTPException(status_code=400, detail="Indique un grupo aereo propio o una base de despegue (uno de los dos)")
    if payload.unidad_id is not None:
        u = db.get(Unidad, payload.unidad_id)
        if u is None or u.escenario_id != esc.id or u.bando != usuario.rol:
            raise HTTPException(status_code=404, detail="Grupo aereo no encontrado")
        if u.tipo != "aerea" or u.estado != "activa":
            raise HTTPException(status_code=400, detail="Solo un grupo aereo activo puede recibir una mision")
        clase = catalogo.perfil(u)
        auth.exigir_funcion(usuario, puestos.funcion_de_orden(u, "mision", clase))
        origen = (u.lat, u.lon, misiones_mod.velocidad_efectiva(u.velocidad_kmh, clase, esc.clima), u.autonomia_km, u.combustible)
        turno, modelo, n = esc.turno_actual, u.modelo, u.aeronaves
    else:
        base = db.get(Unidad, payload.base_id)
        if base is None or base.escenario_id != esc.id or base.bando != usuario.rol:
            raise HTTPException(status_code=404, detail="Base no encontrada")
        auth.exigir_funcion(usuario, "despegar")
        if base.clase != "base_aerea" or base.estado != "activa":
            raise HTTPException(status_code=400, detail="Solo una base aerea en servicio puede lanzar misiones")
        m = catalogo.MODELOS.get(payload.modelo or "")
        if m is None:
            raise HTTPException(status_code=400, detail="Elija un modelo de aeronave del catalogo")
        n = payload.aeronaves or 2
        if n > catalogo.MAX_AERONAVES_GRUPO:
            raise HTTPException(status_code=400, detail=f"Un grupo tiene entre 1 y {catalogo.MAX_AERONAVES_GRUPO} aeronaves")
        turno = esc.turno_actual if payload.turno_despegue is None else payload.turno_despegue
        if not esc.turno_actual <= turno <= esc.turno_actual + misiones_mod.MAX_ANTICIPACION_TURNOS:
            raise HTTPException(status_code=400, detail=(
                f"El despegue se programa entre este turno y {misiones_mod.MAX_ANTICIPACION_TURNOS} turnos despues"))
        dron = aeronaves_mod.es_dron_modelo(m.id)
        tope = catalogo.MAX_DRONES_BANDO if dron else catalogo.MAX_AERONAVES_BANDO
        comprometidas = (aeronaves_mod.aeronaves_comprometidas(db, esc.id, usuario.rol, None, dron)
                         + misiones_mod.aeronaves_programadas(db, esc.id, usuario.rol, dron))
        if comprometidas + n > tope:
            que = "drones" if dron else "aeronaves"
            raise HTTPException(status_code=400, detail=f"Tope de {tope} {que} por bando ({comprometidas} ya en servicio o comprometidas)")
        clase = misiones_mod.clase_de_modelo(m.id)
        origen = (base.lat, base.lon, misiones_mod.velocidad_efectiva(m.velocidad_kmh, clase, esc.clima), m.autonomia_km, 100.0)
        modelo = m.id

    puntos, visibles = [], None
    for p in payload.puntos:
        d = {"tipo": p.tipo, "lat": round(p.lat, 5), "lon": round(p.lon, 5)}
        if p.tipo == "orbita":
            d["turnos"] = p.turnos
            if p.centro is not None:
                d["centro"] = [round(p.centro[0], 5), round(p.centro[1], 5)]
        elif p.tipo == "aterrizaje":
            b = db.get(Unidad, p.base_id) if p.base_id else None
            if (b is None or b.escenario_id != esc.id or b.bando != usuario.rol or b.clase != "base_aerea"
                    or b.estado != "activa"):
                raise HTTPException(status_code=400, detail="El aterrizaje debe ser en una base aerea propia en servicio")
            d.update(lat=b.lat, lon=b.lon, base_id=b.id)
        elif p.tipo == "blanco" and p.objetivo_unidad_id:
            if visibles is None:
                visibles = {x.id: x for x in state.unidades_visibles_para(db, esc, usuario.rol)}
            x = visibles.get(p.objetivo_unidad_id)
            if x is None or x.bando == usuario.rol or x.estado != "activa":
                raise HTTPException(status_code=400, detail="El blanco elegido no es un enemigo detectado por su bando")
            d["objetivo_unidad_id"] = x.id
        puntos.append(d)
    return {
        "puntos": puntos, "turno": turno, "modelo": modelo, "aeronaves": n,
        "errores": misiones_mod.validar(payload.rol, puntos, clase),
        "plan": misiones_mod.estimar(*origen, puntos),
    }


@router.post("/previsualizar")
def previsualizar(payload: schemas.MisionIn, esc: Escenario = Depends(auth.escenario_dep),
                  db: Session = Depends(get_db), usuario: Usuario = Depends(solo_alumnos)):
    """Estimacion (hora y combustible en cada punto) y errores de la mision, sin crearla."""
    r = _preparar(payload, esc, db, usuario)
    return {"plan": r["plan"], "errores": r["errores"], "turno_despegue": r["turno"], "puntos": r["puntos"]}


@router.post("")
async def crear(payload: schemas.MisionIn, esc: Escenario = Depends(auth.escenario_dep),
                db: Session = Depends(get_db), usuario: Usuario = Depends(solo_alumnos)):
    _en_decision(esc)
    r = _preparar(payload, esc, db, usuario)
    if r["errores"]:
        raise HTTPException(status_code=400, detail=" ".join(r["errores"]))
    if payload.unidad_id is not None:
        # la nueva mision reemplaza a la anterior del grupo y a su orden pendiente
        for previa in db.query(Mision).filter(Mision.escenario_id == esc.id, Mision.unidad_id == payload.unidad_id,
                                              Mision.estado.in_(misiones_mod.ACTIVAS)):
            previa.estado = "abortada" if previa.estado == "en_curso" else "cancelada"
            previa.resultado = "Reemplazada por una nueva mision."
        db.query(Orden).filter(Orden.escenario_id == esc.id, Orden.unidad_id == payload.unidad_id,
                               Orden.estado == "pendiente").delete()
    m = Mision(
        escenario_id=esc.id, bando=usuario.rol, rol=payload.rol, nombre=payload.nombre.strip(), estado="programada",
        unidad_id=payload.unidad_id, base_id=payload.base_id, modelo=r["modelo"] or "", aeronaves=r["aeronaves"] or 0,
        turno_despegue=r["turno"], creada_turno=esc.turno_actual, puntos_json=json.dumps(r["puntos"]),
        plan_json=json.dumps(r["plan"]), autor=usuario.username,
        resultado="Programada." if r["turno"] > esc.turno_actual else "Se inicia al resolverse este turno.",
    )
    db.add(m)
    setattr(esc, f"listo_{usuario.rol}", False)  # como una orden nueva: el bando debe confirmar otra vez
    db.commit()
    db.refresh(m)
    await manager.difundir_estado(db, esc)
    return misiones_mod.serializar(m)


@router.get("")
def listar(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
           usuario: Usuario = Depends(auth.usuario_actual)):
    return [misiones_mod.serializar(m) for m in misiones_mod.visibles_para(db, esc, usuario.rol)]


@router.delete("/{mision_id}")
async def cancelar(mision_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                   usuario: Usuario = Depends(solo_alumnos)):
    """Cancela una mision programada; una en curso se aborta y el grupo regresa a la base mas cercana."""
    _en_decision(esc)
    m = db.get(Mision, mision_id)
    if m is None or m.escenario_id != esc.id or m.bando != usuario.rol:
        raise HTTPException(status_code=404, detail="Mision no encontrada")
    if m.estado not in misiones_mod.ACTIVAS:
        raise HTTPException(status_code=400, detail="La mision ya termino")
    u = db.get(Unidad, m.unidad_id) if m.unidad_id else None
    auth.exigir_funcion(usuario, puestos.funcion_de_orden(u, "mision", catalogo.perfil(u)) if u else "despegar")
    misiones_mod.abortar(m, db.query(Unidad).filter(Unidad.escenario_id == esc.id).all())
    setattr(esc, f"listo_{usuario.rol}", False)
    db.commit()
    await manager.difundir_estado(db, esc)
    return misiones_mod.serializar(m)
