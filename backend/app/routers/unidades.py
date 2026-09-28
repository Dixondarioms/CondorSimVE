from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas, state
from app.db import get_db
from app.engine import aar, catalogo
from app.models.aar import RegistroLogistico
from app.models.escenario import Escenario
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.terreno import get_terreno
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/unidades", tags=["unidades"])
solo_instructor = auth.requiere_roles("instructor")


def validar_ubicacion(tipo: str, lat: float, lon: float) -> None:
    terreno = get_terreno()
    if not terreno.disponible:
        return
    clase = terreno.clase(lat, lon)
    if tipo in ("terrestre", "base") and clase == "agua":
        raise HTTPException(status_code=400, detail="Esta unidad no puede ubicarse en el agua")
    if tipo == "naval" and clase != "agua":
        raise HTTPException(status_code=400, detail="Una unidad naval solo puede ubicarse en el agua")


@router.post("", response_model=schemas.UnidadOut)
async def crear_unidad(
    payload: schemas.UnidadCreate,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_instructor),
):
    modelo = None
    if payload.modelo:
        modelo = catalogo.MODELOS.get(payload.modelo)
        if modelo is None:
            raise HTTPException(status_code=400, detail="Modelo de aeronave desconocido")
        if payload.clase is not None and payload.clase != modelo.clase:
            raise HTTPException(status_code=400, detail="El modelo no corresponde a la clase")
        payload.clase = modelo.clase
    if payload.aeronaves > catalogo.MAX_AERONAVES_GRUPO and modelo is not None:
        raise HTTPException(status_code=400, detail=f"Un grupo tiene como maximo {catalogo.MAX_AERONAVES_GRUPO} aeronaves")
    if payload.clase is not None:
        clase = catalogo.CLASES.get(payload.clase)
        if clase is None:
            raise HTTPException(status_code=400, detail="Clase de unidad desconocida")
        if payload.tipo is not None and payload.tipo != clase.tipo:
            raise HTTPException(status_code=400, detail="El tipo no corresponde a la clase")
    elif payload.tipo is not None:
        clase = catalogo.obtener(None, payload.tipo)
    else:
        raise HTTPException(status_code=400, detail="Indique la clase o el tipo de unidad")
    if payload.echelon not in catalogo.ESCALONES:
        raise HTTPException(status_code=400, detail="Escalon desconocido")
    aeronaves = payload.aeronaves if clase.tipo == "aerea" else 1
    escalon = payload.echelon or (catalogo.escalon_grupo(aeronaves) if modelo else clase.escalon)

    validar_ubicacion(clase.tipo, payload.lat, payload.lon)

    def valor(indicado, defecto):
        return defecto if indicado is None else indicado

    # los valores del modelo (si lo hay) reemplazan a los de la clase como predeterminados
    ref = modelo or clase

    unidad = Unidad(
        escenario_id=esc.id,
        nombre=payload.nombre,
        bando=payload.bando,
        tipo=clase.tipo,
        clase=clase.id,
        echelon=escalon,
        modelo=modelo.id if modelo else "",
        aeronaves=aeronaves,
        lat=payload.lat,
        lon=payload.lon,
        fuerza=payload.fuerza,
        velocidad_kmh=valor(payload.velocidad_kmh, ref.velocidad_kmh),
        alcance_km=valor(payload.alcance_km, ref.alcance_km),
        deteccion_km=valor(payload.deteccion_km, ref.deteccion_km),
        autonomia_km=valor(payload.autonomia_km, ref.autonomia_km),
        carga=clase.carga_max,
        sidc=catalogo.generar_sidc(payload.bando, clase, escalon),
    )
    db.add(unidad)
    db.commit()
    db.refresh(unidad)

    await manager.difundir_estado(db, esc)
    return unidad


@router.get("")
def listar_unidades(
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    # Mismo filtro de niebla de guerra que el estado en vivo.
    return state.estado_para(db, esc, usuario.rol)["unidades"]


@router.patch("/{unidad_id}", response_model=schemas.UnidadOut)
async def ajustar_unidad(
    unidad_id: int,
    payload: schemas.UnidadAjuste,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_instructor),
):
    """Ajuste manual del instructor/umpire (adjudicacion); queda registrado en el informe."""
    unidad = db.get(Unidad, unidad_id)
    if unidad is None or unidad.escenario_id != esc.id:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")

    cambios = payload.model_dump(exclude_none=True)
    if "lat" in cambios or "lon" in cambios:
        validar_ubicacion(unidad.tipo, cambios.get("lat", unidad.lat), cambios.get("lon", unidad.lon))
    detalle = []
    for campo, valor in cambios.items():
        anterior = getattr(unidad, campo)
        if anterior != valor:
            setattr(unidad, campo, valor)
            if campo in ("combustible", "municion"):
                db.add(RegistroLogistico(
                    escenario_id=esc.id, turno=esc.turno_actual, unidad_id=unidad.id, unidad_nombre=unidad.nombre,
                    bando=unidad.bando, variable=campo, antes=round(anterior, 2), despues=round(valor, 2),
                    causa="ajuste",
                ))
            detalle.append(f"{campo} {anterior if not isinstance(anterior, float) else round(anterior, 2)} -> "
                           f"{valor if not isinstance(valor, float) else round(valor, 2)}")
    if unidad.fuerza <= 0:
        unidad.estado = "destruida"
    if detalle:
        aar.registrar_ajuste(db, esc, f"Ajuste manual de {unidad.nombre}: " + "; ".join(detalle))

    db.commit()
    db.refresh(unidad)
    await manager.difundir_estado(db, esc)
    return unidad
