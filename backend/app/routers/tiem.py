"""Documentos del TIEM de cada bando: Fase I, Paso 1 (apreciacion inicial). Ver engine/tiem.py.

Cada bando lee y redacta los suyos (segun la reparticion de cada alumno); el instructor y el observador ven los de
los dos bandos, y el instructor los revisa: los aprueba o los devuelve con observaciones. A cada documento se le
pueden adjuntar archivos (Word o PDF), que se guardan en la base de datos."""

import base64
import binascii
import json
from pathlib import PurePath

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import auth, ensayos, schemas, state
from app.db import get_db
from app.engine import aar, catalogo, pmo, puestos, tiem
from app.models.contacto import Contacto
from app.models.documento_tiem import ArchivoTiem, DocumentoTiem, EjecucionTarea
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/tiem", tags=["tiem"])
solo_instructor = auth.requiere_roles("instructor")
MAX_ARCHIVO = 10 * 1024 * 1024
MAX_ARCHIVOS = 5
EXTENSIONES = {".doc": "application/msword",
               ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               ".odt": "application/vnd.oasis.opendocument.text", ".rtf": "application/rtf", ".pdf": "application/pdf"}


class ContenidoIn(BaseModel):
    contenido: dict


class RevisionIn(BaseModel):
    estado: str = Field(pattern="^(aprobado|devuelto|borrador)$")
    observaciones: str = Field(default="", max_length=4000)


class ArchivoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    datos: str  # base64


# ---------------------------------------------------------------- permisos
def autor(escenario_id: int, request: Request, db: Session = Depends(get_db),
          usuario: Usuario = Depends(auth.usuario_actual)):
    """Quien escribe: el instructor (sin cabecera de conduccion, puede todo) o quien conduce un bando (alumno o
    instructor con X-Conduce-Bando, ver auth.conductor)."""
    if usuario.rol == "instructor" and not request.headers.get(auth.CABECERA_CONDUCE):
        return usuario
    return auth.conductor(escenario_id, request, db, usuario)


def _es_instructor(u) -> bool:
    return getattr(u, "rol", "") == "instructor"


def _puede_redactar(u, bando: str, tipo: str) -> bool:
    if _es_instructor(u):
        return True
    return u.rol == bando and puestos.normalizar(u.puesto) in tiem.DOCUMENTOS[tipo].redactan


def _validar(bando: str, tipo: str) -> None:
    if bando not in pmo.BANDOS:
        raise HTTPException(status_code=404, detail="Bando desconocido")
    if tipo not in tiem.DOCUMENTOS:
        raise HTTPException(status_code=404, detail="Documento desconocido")


def _exigir_redactar(u, bando: str, tipo: str) -> None:
    _validar(bando, tipo)
    if not _puede_redactar(u, bando, tipo):
        quienes = " o ".join(puestos.obtener(p).sigla for p in tiem.DOCUMENTOS[tipo].redactan)
        raise HTTPException(status_code=403, detail=f"La {tiem.DOCUMENTOS[tipo].titulo} la redactan {quienes} de su bando")


def _bandos_visibles(rol: str) -> list[str]:
    return [rol] if rol in pmo.BANDOS else list(pmo.BANDOS)


# ---------------------------------------------------------------- datos
def _doc(db: Session, esc: Escenario, bando: str, tipo: str, crear: bool = False) -> DocumentoTiem | None:
    d = db.query(DocumentoTiem).filter(DocumentoTiem.escenario_id == esc.id, DocumentoTiem.bando == bando,
                                       DocumentoTiem.tipo == tipo).first()
    if d is None and crear:
        d = DocumentoTiem(escenario_id=esc.id, bando=bando, tipo=tipo, contenido_json="{}", estado="borrador",
                          observaciones="", editado_por="", editado_puesto="")
        db.add(d)
        db.flush()
    return d


def _contenido(d: DocumentoTiem | None, tipo: str) -> dict:
    return tiem.normalizar(tipo, json.loads(d.contenido_json) if d is not None else {})


def _serializar(db: Session, d: DocumentoTiem | None, bando: str, tipo: str, u) -> dict:
    contenido = _contenido(d, tipo)
    archivos = db.query(ArchivoTiem).filter(ArchivoTiem.documento_id == d.id).order_by(ArchivoTiem.id).all() if d else []
    return {
        "tipo": tipo, "bando": bando, "existe": d is not None, "estado": d.estado if d else "borrador",
        "observaciones": d.observaciones if d else "", "editado_por": d.editado_por if d else "",
        "editado_puesto": d.editado_puesto if d else "",
        "actualizado_en": d.actualizado_en.isoformat() if d and d.actualizado_en else None,
        "presentado_turno": d.presentado_turno if d else None, "revisado_turno": d.revisado_turno if d else None,
        "contenido": contenido, "revision": tiem.revisar(tipo, contenido),
        "puede_redactar": _puede_redactar(u, bando, tipo) and u.rol != "observador",
        "archivos": [{"id": a.id, "nombre": a.nombre, "tamano": a.tamano, "subido_por": a.subido_por,
                      "subido_en": a.subido_en.isoformat()} for a in archivos],
    }


def _respuesta(db: Session, esc: Escenario, u) -> dict:
    documentos = {b: {t: _serializar(db, _doc(db, esc, b, t), b, t, u) for t in tiem.ORDEN}
                  for b in _bandos_visibles(u.rol)}
    return {
        "orden": list(tiem.ORDEN),
        "definiciones": {t: tiem.definicion(d) for t, d in tiem.DOCUMENTOS.items()},
        "documentos": documentos,
        # nombres de las F/A y de las capacidades del enemigo de cada bando (filas y columnas de la confrontacion)
        "contexto": {b: tiem.contexto({t: d["contenido"] for t, d in docs.items()}) for b, docs in documentos.items()},
        "ensayos": {b: [ensayos.resumen(db, e) for e in ensayos.ensayos_de(db, esc, b)] for b in documentos},
        # tareas del Plan de Operaciones: que paso con cada una y con que se pueden armar
        "ejecuciones": {b: {e.tarea_id: {"estado": e.estado, "turno": e.turno, "orden_id": e.orden_id, "motivo": e.motivo,
                                         "emitida_por": e.emitida_por}
                            for e in db.query(EjecucionTarea).filter(EjecucionTarea.escenario_id == esc.id,
                                                                    EjecucionTarea.bando == b)}
                        for b in documentos},
        "opciones_tarea": {b: _opciones_tarea(db, esc, b) for b in documentos},
        "turno_actual": esc.turno_actual,
        "puede_ensayar": {b: _puede_ensayar(u, b) for b in documentos},
    }


ENSAYAN = ("comandante", "jem", "a3", "a3da", "a2")


def _puede_ensayar(u, bando: str) -> bool:
    if _es_instructor(u):
        return True
    return u.rol == bando and puestos.normalizar(u.puesto) in ENSAYAN


def _avisar(db: Session, esc: Escenario, bando: str, texto: str) -> None:
    db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, tipo="tiem", bando_destino=bando, descripcion=texto))


# ---------------------------------------------------------------- rutas
def lector(escenario_id: int, request: Request, db: Session = Depends(get_db),
           usuario: Usuario = Depends(auth.usuario_actual)):
    """Quien lee: cualquier usuario; el instructor que conduce un bando lo ve como ese bando."""
    if usuario.rol == "instructor" and request.headers.get(auth.CABECERA_CONDUCE):
        return auth.conductor(escenario_id, request, db, usuario)
    return usuario


@router.get("")
def leer(esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db), u=Depends(lector)):
    return _respuesta(db, esc, u)


@router.get("/{bando}/prc")
def prc(bando: str, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db), u=Depends(lector)):
    """Poder Relativo de Combate preliminar del bando (lo propio exacto; lo enemigo, estimado)."""
    if bando not in _bandos_visibles(u.rol):
        raise HTTPException(status_code=404, detail="Bando no disponible")
    unidades = db.query(Unidad).filter(Unidad.escenario_id == esc.id).all()
    return tiem.poder_relativo(esc, unidades, bando)


@router.get("/{bando}/{tipo}/sugerencias")
def sugerencias(bando: str, tipo: str, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                u=Depends(lector)):
    """Lo que el simulador puede transcribir o calcular para ese documento (no se guarda)."""
    _validar(bando, tipo)
    if bando not in _bandos_visibles(u.rol):
        raise HTTPException(status_code=404, detail="Bando no disponible")
    unidades = db.query(Unidad).filter(Unidad.escenario_id == esc.id).all()
    objetivos = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).all()
    pm = pmo.obtener(db, esc, bando)
    docs = {t: _contenido(_doc(db, esc, bando, t), t) for t in tiem.ORDEN}
    return {"contenido": tiem.sugerencias(tipo, esc, unidades, objetivos, bando,
                                           json.loads(pm.contenido_json) if pm else None, docs)}


@router.put("/{bando}/{tipo}")
async def guardar(bando: str, tipo: str, payload: ContenidoIn, esc: Escenario = Depends(auth.escenario_dep),
                  db: Session = Depends(get_db), u=Depends(autor)):
    _exigir_redactar(u, bando, tipo)
    d = _doc(db, esc, bando, tipo, crear=True)
    if not _es_instructor(u) and d.estado in ("presentado", "aprobado"):
        raise HTTPException(status_code=400, detail="El documento ya fue presentado al instructor: espere su revisión"
                            if d.estado == "presentado" else "El documento ya está aprobado")
    d.contenido_json = json.dumps(tiem.normalizar(tipo, payload.contenido), ensure_ascii=False)
    d.editado_por = u.username
    d.editado_puesto = "instructor" if _es_instructor(u) else puestos.normalizar(u.puesto)
    db.commit()
    return _serializar(db, d, bando, tipo, u)


@router.post("/{bando}/{tipo}/presentar")
async def presentar(bando: str, tipo: str, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                    u=Depends(autor)):
    _exigir_redactar(u, bando, tipo)
    d = _doc(db, esc, bando, tipo)
    if d is None:
        raise HTTPException(status_code=400, detail="El documento está vacío")
    if d.estado in ("presentado", "aprobado"):
        raise HTTPException(status_code=400, detail=f"El documento ya está {d.estado}")
    faltan = tiem.revisar(tipo, json.loads(d.contenido_json))["faltan"]
    if faltan:
        raise HTTPException(status_code=400, detail="No se puede presentar todavía: " + " ".join(faltan))
    d.estado, d.presentado_turno = "presentado", esc.turno_actual
    _avisar(db, esc, bando, f"{tiem.DOCUMENTOS[tipo].titulo}: presentada al instructor por {u.username}.")
    db.commit()
    await manager.difundir_estado(db, esc)
    return _serializar(db, d, bando, tipo, u)


@router.post("/{bando}/{tipo}/revisar")
async def revisar(bando: str, tipo: str, payload: RevisionIn, esc: Escenario = Depends(auth.escenario_dep),
                  db: Session = Depends(get_db), u: Usuario = Depends(solo_instructor)):
    """El instructor aprueba el documento, lo devuelve con observaciones o lo reabre como borrador."""
    _validar(bando, tipo)
    d = _doc(db, esc, bando, tipo, crear=True)
    d.estado, d.observaciones, d.revisado_turno = payload.estado, payload.observaciones.strip(), esc.turno_actual
    titulo = tiem.DOCUMENTOS[tipo].titulo
    texto = {"aprobado": f"{titulo}: aprobada por el instructor.",
             "devuelto": f"{titulo}: devuelta por el instructor con observaciones.",
             "borrador": f"{titulo}: reabierta por el instructor para seguir trabajándola."}[payload.estado]
    _avisar(db, esc, bando, texto)
    aar.registrar_ajuste(db, esc, f"TIEM: {titulo} del bando {bando} {payload.estado}")
    db.commit()
    await manager.difundir_estado(db, esc)
    return _serializar(db, d, bando, tipo, u)


@router.post("/{bando}/{tipo}/archivos")
async def adjuntar(bando: str, tipo: str, payload: ArchivoIn, esc: Escenario = Depends(auth.escenario_dep),
                   db: Session = Depends(get_db), u=Depends(autor)):
    """Adjunta un Word, ODT, RTF o PDF (hasta 10 MB) al documento."""
    _exigir_redactar(u, bando, tipo)
    nombre = PurePath(payload.nombre.replace("\\", "/")).name.strip()[:200]
    ext = PurePath(nombre).suffix.lower()
    if ext not in EXTENSIONES:
        raise HTTPException(status_code=400, detail="Solo se adjuntan documentos Word (.doc, .docx), .odt, .rtf o .pdf")
    try:
        datos = base64.b64decode(payload.datos, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Archivo dañado")
    if not datos or len(datos) > MAX_ARCHIVO:
        raise HTTPException(status_code=400, detail="El archivo debe pesar menos de 10 MB")
    d = _doc(db, esc, bando, tipo, crear=True)
    if db.query(ArchivoTiem).filter(ArchivoTiem.documento_id == d.id).count() >= MAX_ARCHIVOS:
        raise HTTPException(status_code=400, detail=f"Cada documento admite hasta {MAX_ARCHIVOS} archivos")
    db.add(ArchivoTiem(documento_id=d.id, nombre=nombre, tipo_mime=EXTENSIONES[ext], tamano=len(datos), datos=datos,
                       subido_por=u.username))
    _avisar(db, esc, bando, f"{tiem.DOCUMENTOS[tipo].titulo}: {u.username} adjuntó «{nombre}».")
    db.commit()
    await manager.difundir_estado(db, esc)
    return _serializar(db, d, bando, tipo, u)


def _archivo(db: Session, esc: Escenario, archivo_id: int) -> tuple[ArchivoTiem, DocumentoTiem]:
    a = db.get(ArchivoTiem, archivo_id)
    d = db.get(DocumentoTiem, a.documento_id) if a else None
    if a is None or d is None or d.escenario_id != esc.id:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return a, d


@router.get("/archivos/{archivo_id}")
def descargar(archivo_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
              u=Depends(lector)):
    a, d = _archivo(db, esc, archivo_id)
    if d.bando not in _bandos_visibles(u.rol):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    nombre = a.nombre.encode("ascii", "ignore").decode() or "documento"
    return Response(a.datos, media_type=a.tipo_mime,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.delete("/archivos/{archivo_id}")
async def quitar(archivo_id: int, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                 u=Depends(autor)):
    a, d = _archivo(db, esc, archivo_id)
    _exigir_redactar(u, d.bando, d.tipo)
    db.delete(a)
    db.commit()
    await manager.difundir_estado(db, esc)
    return _serializar(db, d, d.bando, d.tipo, u)


class EnsayoIn(BaseModel):
    fa: str = Field(min_length=1, max_length=300)


@router.post("/{bando}/ensayos")
async def ensayar(bando: str, payload: EnsayoIn, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                  u=Depends(autor)):
    """Juego de guerra: crea una copia del escenario en su estado actual para ensayar una F/A contra la IA."""
    if bando not in pmo.BANDOS:
        raise HTTPException(status_code=404, detail="Bando desconocido")
    if not _puede_ensayar(u, bando):
        raise HTTPException(status_code=403, detail="Los ensayos los crean el Comandante, el JEM, la A-3, la A-3 D/A o la A-2")
    if esc.ensayo_de is not None:
        raise HTTPException(status_code=400, detail="Esto ya es un ensayo: créelo desde el ejercicio original")
    if esc.estado == "finalizado":
        raise HTTPException(status_code=400, detail="El ejercicio está finalizado")
    if len(ensayos.ensayos_de(db, esc, bando)) >= ensayos.MAX_ENSAYOS:
        raise HTTPException(status_code=400, detail=f"Cada bando puede tener hasta {ensayos.MAX_ENSAYOS} ensayos por ejercicio")
    copia = ensayos.crear(db, esc, bando, payload.fa.strip())
    _avisar(db, esc, bando, f"Juego de guerra: {u.username} creó «{copia.nombre}».")
    db.commit()
    await manager.difundir_estado(db, esc)
    return ensayos.resumen(db, copia)


# ---------------------------------------------------------------- tareas del Plan de Operaciones -> ordenes
def _conocidas(db: Session, esc: Escenario, bando: str) -> dict[int, tuple]:
    """Unidades enemigas que el bando conoce: {id: (nombre, lat, lon, visible)} (las vistas ahora y los contactos)."""
    out = {}
    for c in db.query(Contacto).filter(Contacto.escenario_id == esc.id, Contacto.bando == bando):
        u = db.get(Unidad, c.unidad_id)
        if u is not None and u.estado == "activa":
            out[u.id] = (u.nombre, c.lat, c.lon, False)
    for u in state.unidades_visibles_para(db, esc, bando):
        if u.bando != bando and u.estado == "activa":
            out[u.id] = (u.nombre, u.lat, u.lon, True)
    return out


def _opciones_tarea(db: Session, esc: Escenario, bando: str) -> dict:
    propias = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == bando, Unidad.estado == "activa")
    objetivos = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id, Objetivo.bando == bando, Objetivo.tipo != "efecto")
    propias = [u for u in propias.order_by(Unidad.nombre) if not catalogo.es_misil(u)]
    return {
        "unidades": [{"id": u.id, "nombre": u.nombre, "tipo": u.tipo, "clase": u.clase} for u in propias],
        "objetivos": ([{"clave": f"o:{o.id}", "nombre": o.nombre, "grupo": "Objetivos del bando"} for o in objetivos.order_by(Objetivo.id)]
                      + [{"clave": f"u:{i}", "nombre": n, "grupo": "Unidades enemigas conocidas"}
                         for i, (n, *_r) in sorted(_conocidas(db, esc, bando).items(), key=lambda x: x[1][0])]
                      + [{"clave": f"u:{u.id}", "nombre": u.nombre, "grupo": "Unidades y bases propias"} for u in propias]),
    }


def _orden_de_tarea(db: Session, esc: Escenario, bando: str, t: dict, conocidas: dict) -> schemas.OrdenCreate:
    """Traduce una tarea a la orden del simulador; ValueError con el motivo si no se puede armar."""
    tipo, (clase_obj, num) = t["tipo"], t["objetivo"].split(":")
    num = int(num)
    unidad_obj, punto = None, None
    if clase_obj == "o":
        o = db.get(Objetivo, num)
        if o is None or o.escenario_id != esc.id:
            raise ValueError("El objetivo ya no existe")
        if o.unidad_id:
            num, clase_obj = o.unidad_id, "u"
        else:
            punto = (o.lat, o.lon)
    if clase_obj == "u":
        u = db.get(Unidad, num)
        if u is None or u.escenario_id != esc.id or u.estado != "activa":
            raise ValueError("El objetivo o destino ya no está activo")
        if u.bando == bando:
            unidad_obj, punto = u, (u.lat, u.lon)
        elif num in conocidas:
            unidad_obj, punto = u, conocidas[num][1:3]
        else:
            raise ValueError("No se conoce la posición del objetivo: hay que localizarlo primero")
    if tipo in ("atacar", "apoyar", "aterrizar"):
        if unidad_obj is None:
            raise ValueError(f"Para {tiem.TIPOS_TAREA[tipo].lower()} hace falta una unidad, no una zona")
        return schemas.OrdenCreate(unidad_id=t["unidad_id"], tipo=tipo, objetivo_unidad_id=unidad_obj.id)
    return schemas.OrdenCreate(unidad_id=t["unidad_id"], tipo=tipo, waypoints=[punto])


class EmitirIn(BaseModel):
    ids: list[str] | None = None  # tareas a emitir; sin ids, todas las que vencen hasta este turno


@router.post("/{bando}/emitir")
async def emitir(bando: str, payload: EmitirIn, esc: Escenario = Depends(auth.escenario_dep), db: Session = Depends(get_db),
                 u=Depends(autor)):
    """Orden de Operaciones: emite como ordenes del simulador las tareas del plan que vencen en el turno en curso (o
    antes y aun no emitidas). Cada orden pasa por la misma validacion que una orden manual, con la reparticion de
    quien la emite; las que no se pueden cumplir quedan rechazadas con el motivo y se pueden reintentar."""
    from app.routers.ordenes import _crear_orden, _en_decision  # importacion tardia: evita ciclos entre routers

    if bando not in pmo.BANDOS:
        raise HTTPException(status_code=404, detail="Bando desconocido")
    if _es_instructor(u):
        u = auth.InstructorConductor(id=u.id, username=u.username, rol=bando)
    elif u.rol != bando:
        raise HTTPException(status_code=403, detail="Solo puede emitir las tareas de su bando")
    _en_decision(esc)
    plan = _contenido(_doc(db, esc, bando, "plan_operaciones"), "plan_operaciones")
    hechas = {e.tarea_id: e for e in db.query(EjecucionTarea).filter(EjecucionTarea.escenario_id == esc.id,
                                                                   EjecucionTarea.bando == bando)}
    elegidas = [t for t in plan["tareas"] if t["turno"] and t["turno"] <= esc.turno_actual
                and (t["id"] not in hechas or hechas[t["id"]].estado != "emitida")
                and (payload.ids is None or t["id"] in payload.ids)]
    conocidas = _conocidas(db, esc, bando)
    resultados = []
    for t in elegidas:
        ok, motivo, orden_id = False, "", None
        try:
            if not (t["unidad_id"] and t["tipo"] and t["objetivo"]):
                raise ValueError("La tarea está incompleta")
            orden = _crear_orden(_orden_de_tarea(db, esc, bando, t, conocidas), esc, db, u)
            db.flush()
            ok, orden_id = True, orden.id
        except HTTPException as e:
            motivo = str(e.detail)
        except ValueError as e:
            motivo = str(e)
        ej = hechas.get(t["id"]) or EjecucionTarea(escenario_id=esc.id, bando=bando, tarea_id=t["id"])
        ej.estado = "emitida" if ok else "rechazada"
        ej.turno, ej.orden_id, ej.motivo, ej.emitida_por = esc.turno_actual, orden_id, motivo[:300], u.username
        db.add(ej)
        resultados.append({"id": t["id"], "texto": tiem.texto_tarea(t), "ok": ok, "motivo": motivo, "orden_id": orden_id})
    if any(r["ok"] for r in resultados):
        setattr(esc, f"listo_{bando}", False)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"resultados": resultados, "emitidas": sum(1 for r in resultados if r["ok"])}
