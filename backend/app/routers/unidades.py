from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas, state
from app.db import get_db
from app.engine import aar, catalogo, defensa_aerea, puestos, relieve, vision
from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.models.aar import Combate, RegistroLogistico
from app.models.contacto import Contacto
from app.models.obra import Obra
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.escenario import Escenario
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.terreno import get_terreno
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/unidades", tags=["unidades"])
solo_instructor = auth.requiere_roles("instructor")


def validar_ubicacion(tipo: str, lat: float, lon: float, clase_unidad: str = "") -> None:
    terreno = get_terreno()
    if not terreno.disponible or clase_unidad == "puente":  # un puente puede estar sobre el agua
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
            raise HTTPException(status_code=400, detail="Modelo o tipo de unidad desconocido")
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
    escalon = payload.echelon or (catalogo.escalon_grupo(aeronaves) if modelo and clase.tipo == "aerea" else clase.escalon)

    validar_ubicacion(clase.tipo, payload.lat, payload.lon, clase.id)

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
        personal=payload.personal,
        radio_km=payload.radio_km if clase.infraestructura == "puente" else None,
    )
    db.add(unidad)
    db.commit()
    db.refresh(unidad)

    await manager.difundir_estado(db, esc)
    return unidad


@router.delete("/{unidad_id}")
async def eliminar_unidad(
    unidad_id: int,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_instructor),
):
    """Quita una unidad del escenario (editor). Si ya combatio no se puede borrar sin falsear el informe:
    en ese caso hay que marcarla como destruida."""
    unidad = db.get(Unidad, unidad_id)
    if unidad is None or unidad.escenario_id != esc.id:
        raise HTTPException(status_code=404, detail="Unidad no encontrada")
    if db.query(Combate).filter((Combate.atacante_id == unidad.id) | (Combate.defensor_id == unidad.id)).count():
        raise HTTPException(
            status_code=409,
            detail="Esta unidad ya participo en combates y consta en el informe: marquela como destruida en lugar de borrarla",
        )
    db.query(Orden).filter((Orden.unidad_id == unidad.id) | (Orden.objetivo_unidad_id == unidad.id)).delete(synchronize_session=False)
    db.query(Contacto).filter(Contacto.unidad_id == unidad.id).delete(synchronize_session=False)
    db.query(Objetivo).filter(Objetivo.unidad_id == unidad.id).delete(synchronize_session=False)
    db.query(RegistroLogistico).filter(RegistroLogistico.unidad_id == unidad.id).delete(synchronize_session=False)
    db.query(Obra).filter(Obra.unidad_id == unidad.id).update({Obra.unidad_id: None}, synchronize_session=False)
    # las aeronaves estacionadas en una base que se borra quedan en el aire junto a ella
    db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.base_id == unidad.id).update(
        {Unidad.en_tierra: False, Unidad.base_id: None, Unidad.espera_restante: 0}, synchronize_session=False)
    aar.registrar_ajuste(db, esc, f"Unidad eliminada del escenario: {unidad.nombre} ({unidad.bando})")
    db.delete(unidad)
    db.commit()
    await manager.difundir_estado(db, esc)
    return {"ok": True}


@router.get("")
def listar_unidades(
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    # Mismo filtro de niebla de guerra que el estado en vivo.
    return state.estado_para(db, esc, usuario.rol)["unidades"]


@router.post("/{unidad_id}/defensa", response_model=schemas.UnidadOut)
async def configurar_defensa(
    unidad_id: int,
    payload: schemas.DefensaIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.requiere_roles("azul", "rojo", "instructor")),
):
    """Encender o apagar el radar (control de emisiones) y liberar o retener el fuego automatico de la antiaerea.
    Rige de inmediato: un radar que se enciende empieza a ver (y a ser escuchado) ya en esta planificacion."""
    unidad = db.get(Unidad, unidad_id)
    if unidad is None or unidad.escenario_id != esc.id or (usuario.rol != "instructor" and unidad.bando != usuario.rol):
        raise HTTPException(status_code=404, detail="Unidad no encontrada")
    clase = catalogo.obtener(unidad.clase, unidad.tipo)
    if payload.emitiendo is not None and not clase.emisor:
        raise HTTPException(status_code=400, detail="Esta unidad no tiene radar")
    if payload.fuego_libre is not None and not clase.defensa_aerea:
        raise HTTPException(status_code=400, detail="Solo la defensa antiaerea tiene fuego automatico")
    sistema = defensa_aerea.sistema(unidad)
    if payload.arma is not None:
        if sistema is None:
            raise HTTPException(status_code=400, detail="Esta unidad no tiene un sistema de armas antiaereo")
        if payload.arma and sistema.arma(payload.arma) is None:
            raise HTTPException(status_code=400, detail="Ese arma no es de este sistema")
    if unidad.estado != "activa":
        raise HTTPException(status_code=400, detail="La unidad ya no esta activa")
    if usuario.rol != "instructor":
        if esc.estado != "activo":
            raise HTTPException(status_code=400, detail=f"El escenario esta {esc.estado}")
        auth.exigir_funcion(usuario, puestos.funcion_de_orden(unidad, "defensa", clase))
    if payload.emitiendo is not None:
        unidad.emitiendo = payload.emitiendo
    if payload.fuego_libre is not None:
        unidad.fuego_libre = payload.fuego_libre
    if payload.arma is not None:
        unidad.arma_elegida = payload.arma or None
    db.commit()
    db.refresh(unidad)
    await manager.difundir_estado(db, esc)
    return unidad


@router.post("/{unidad_id}/perfil", response_model=schemas.UnidadOut)
async def cambiar_perfil(
    unidad_id: int,
    payload: schemas.PerfilVueloIn,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.requiere_roles("azul", "rojo", "instructor")),
):
    """Perfil de vuelo de una aeronave propia (alto, medio o rasante). Rige de inmediato: cambia lo que la ve y la
    puede atacar desde ya (engine/relieve.py); el combustible se descuenta segun el perfil al resolverse el turno."""
    unidad = db.get(Unidad, unidad_id)
    if unidad is None or unidad.escenario_id != esc.id or (usuario.rol != "instructor" and unidad.bando != usuario.rol):
        raise HTTPException(status_code=404, detail="Unidad no encontrada")
    permitidos = relieve.perfiles_permitidos(unidad)
    if not permitidos:
        raise HTTPException(status_code=400, detail="Solo las aeronaves eligen perfil de vuelo (los misiles van siempre rasantes)")
    if payload.perfil_vuelo not in permitidos:
        raise HTTPException(status_code=400, detail=f"Esta aeronave no puede volar en perfil {payload.perfil_vuelo}")
    if unidad.estado != "activa":
        raise HTTPException(status_code=400, detail="La unidad ya no esta activa")
    if usuario.rol != "instructor":
        if esc.estado != "activo":
            raise HTTPException(status_code=400, detail=f"El escenario esta {esc.estado}")
        auth.exigir_funcion(usuario, puestos.funcion_de_orden(unidad, None, catalogo.obtener(unidad.clase, unidad.tipo)))
    unidad.perfil_vuelo = payload.perfil_vuelo
    db.commit()
    db.refresh(unidad)
    await manager.difundir_estado(db, esc)
    return unidad


@router.get("/{unidad_id}/cobertura")
def cobertura_sensor(
    unidad_id: int,
    esc: Escenario = Depends(auth.escenario_dep),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    """Lo que ve un sensor propio segun el relieve: por perfil de vuelo, el poligono hasta donde detecta una
    aeronave a esa cota (sombras de las montañas y horizonte). Sin grilla de alturas: disponible = False."""
    unidad = db.get(Unidad, unidad_id)
    if unidad is None or unidad.escenario_id != esc.id or (state.es_bando(usuario.rol) and unidad.bando != usuario.rol):
        raise HTTPException(status_code=404, detail="Unidad no encontrada")
    terreno = get_terreno()
    if not terreno.tiene_elevacion or unidad.estado != "activa" or unidad.tipo == "aerea" or not unidad.deteccion_km:
        return {"disponible": False, "perfiles": {}}
    clima = clima_mod.contexto(db, esc)
    ge = ge_mod.contexto(db, esc)
    perfiles = {}
    for perfil in relieve.PERFILES:
        alcance = vision.radio_efectivo(unidad, relieve.blanco_de_prueba(unidad.lat, unidad.lon, perfil), terreno, clima, ge)
        perfiles[perfil] = {"alcance_km": round(alcance, 1), "altura_m": relieve.ALTURA_PERFIL_M[perfil],
                            "poligono": relieve.cobertura(terreno, unidad, alcance, relieve.ALTURA_PERFIL_M[perfil])}
    return {"disponible": True, "altura_sensor_m": round(relieve.altura_msl(unidad, terreno)), "perfiles": perfiles}


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
