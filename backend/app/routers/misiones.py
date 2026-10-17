"""Misiones aereas: planificar (rol + ruta), previsualizar la estimacion, listar y cancelar/abortar."""

import json
import math

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app import auth, legajo, schemas, state
from app.db import get_db
from app.engine import aeronaves as aeronaves_mod
from app.engine import apoyo_aereo, catalogo, ota, plataformas, puestos, relieve, weaponeering
from app.engine import clima as clima_mod
from app.engine import misiones as misiones_mod
from app.models.escenario import Escenario
from app.models.mision import Mision
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.routers.ordenes import _en_decision
from app.ws_manager import manager

router = APIRouter(prefix="/api/escenarios/{escenario_id}/misiones", tags=["misiones"])


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
        if catalogo.es_misil(u):
            raise HTTPException(status_code=400, detail="Un misil en vuelo no admite ordenes.")
        clase = catalogo.perfil(u)
        auth.exigir_funcion(usuario, puestos.funcion_de_orden(u, "mision", clase))
        origen = (u.lat, u.lon, misiones_mod.velocidad_efectiva(u.velocidad_kmh, clase, clima_mod.contexto(db, esc), u.lat, u.lon), u.autonomia_km, u.combustible)
        turno, modelo, n = esc.turno_actual, u.modelo, u.aeronaves
        factor = relieve.FACTOR_CONSUMO.get(relieve.perfil_de(u), 1.0)
        base, volador = None, u
    else:
        base = db.get(Unidad, payload.base_id)
        if base is None or base.escenario_id != esc.id or base.bando != usuario.rol:
            raise HTTPException(status_code=404, detail="Base no encontrada")
        auth.exigir_funcion(usuario, "despegar")
        if not catalogo.opera_aeronaves(base) or base.estado != "activa":
            raise HTTPException(status_code=400, detail="Solo una base aerea en servicio puede lanzar misiones")
        m = catalogo.MODELOS.get(payload.modelo or "")
        if m is None:
            raise HTTPException(status_code=400, detail="Elija un modelo de aeronave del catalogo")
        if catalogo.CLASES[m.clase].misil:
            raise HTTPException(status_code=400, detail="Los misiles de crucero se lanzan con la orden lanzar, no en una mision")
        if catalogo.es_portaaviones(base) and not catalogo.modelo_embarcable(m):
            raise HTTPException(status_code=400, detail=f"{m.nombre} no puede operar desde un portaaviones: {aeronaves_mod.MOTIVO_NO_EMBARCABLE}")
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
        origen = (base.lat, base.lon, misiones_mod.velocidad_efectiva(m.velocidad_kmh, clase, clima_mod.contexto(db, esc), base.lat, base.lon), m.autonomia_km, 100.0)
        modelo = m.id
        volador = Unidad(tipo="aerea", clase=m.clase, modelo=m.id)
        factor = relieve.FACTOR_CONSUMO.get(relieve.perfil_de(volador), 1.0)

    puntos, visibles, errores_ruta = [], None, []
    permitidos = relieve.perfiles_permitidos(volador)
    for i, p in enumerate(payload.puntos):
        d = {"tipo": p.tipo, "lat": round(p.lat, 5), "lon": round(p.lon, 5)}
        if p.perfil:
            if p.perfil not in permitidos:
                errores_ruta.append(f"Punto {i + 1}: esta aeronave no vuela en perfil {p.perfil}.")
            d["perfil"] = p.perfil
        if p.reunion:
            if p.tipo != "paso":
                errores_ruta.append(f"Punto {i + 1}: el punto de reunión debe ser un punto de paso.")
            d["reunion"] = True
        if p.corte:
            if p.tipo != "blanco" or p.objetivo_unidad_id:
                errores_ruta.append(f"Punto {i + 1}: el corte de carretera es un punto de blanco sin unidad.")
            d["corte"] = True
        if p.reabastecimiento:
            if p.tipo != "paso":
                errores_ruta.append(f"Punto {i + 1}: el punto de reabastecimiento en vuelo debe ser un punto de paso.")
            d["reabastecimiento"] = True
        if p.tipo == "orbita":
            d["turnos"] = p.turnos
            if p.centro is not None:
                d["centro"] = [round(p.centro[0], 5), round(p.centro[1], 5)]
        elif p.tipo == "aterrizaje":
            b = db.get(Unidad, p.base_id) if p.base_id else None
            if (b is None or b.escenario_id != esc.id or b.bando != usuario.rol or not catalogo.opera_aeronaves(b)
                    or b.estado != "activa"):
                raise HTTPException(status_code=400, detail="El aterrizaje debe ser en una base aerea propia (o un portaaviones propio) en servicio")
            if catalogo.es_portaaviones(b) and not catalogo.es_embarcable(clase.id if clase else None, modelo):
                raise HTTPException(status_code=400, detail=f"No puede aterrizar en un portaaviones: {aeronaves_mod.MOTIVO_NO_EMBARCABLE}")
            corta = plataformas.error_de_pista(catalogo.MODELOS.get(modelo or ""), b, aterrizar=True)
            if corta:
                raise HTTPException(status_code=400, detail=corta)
            d.update(lat=b.lat, lon=b.lon, base_id=b.id)
        elif p.tipo == "blanco" and p.objetivo_unidad_id:
            if visibles is None:
                visibles = {x.id: x for x in state.unidades_visibles_para(db, esc, usuario.rol)}
            x = visibles.get(p.objetivo_unidad_id)
            if x is None or x.bando == usuario.rol or x.estado != "activa":
                raise HTTPException(status_code=400, detail="El blanco elegido no es un enemigo detectado por su bando")
            d["objetivo_unidad_id"] = x.id
        puntos.append(d)
    errores = misiones_mod.validar(payload.rol, puntos, clase) + errores_ruta
    if sum(1 for p in puntos if p.get("reunion")) > 1:
        errores.append("La ruta admite un solo punto de reunión.")
    datos_ota = None
    if payload.ota is not None:
        datos_ota = payload.ota.model_dump()
        datos_ota["paquete"] = datos_ota["paquete"].strip().upper()
        if datos_ota["codigo"] and datos_ota["codigo"] not in ota.NOMBRE_CODIGO:
            errores.append(f"Código de misión desconocido: {datos_ota['codigo']}.")
        errores += ota.validar(payload.rol, modelo, clase, datos_ota)
        errores += ota.errores_del_paquete(db, esc.id, usuario.rol, datos_ota)
        if any(p.get("reunion") for p in puntos) and not datos_ota["paquete"]:
            errores.append("El punto de reunión es para los grupos de un paquete: indique el paquete.")
    elif any(p.get("reunion") for p in puntos):
        errores.append("El punto de reunión es para los grupos de un paquete: indique el paquete.")
    if base is not None:
        corta = plataformas.error_de_pista(catalogo.MODELOS.get(modelo or ""), base)
        if corta:
            errores.append(corta)
    plan = misiones_mod.estimar(*origen, puntos, factor)
    plan["tramos"] = ota.tramos(origen[0], origen[1], puntos, relieve.perfil_de(volador))
    # TOT: turno en que el grupo esta sobre el (primer) blanco; con un TOT pedido y despegue desde una base, el
    # turno de despegue se calcula hacia atras desde el
    k = next((i for i, p in enumerate(puntos) if p["tipo"] == "blanco"), None)
    tot_pedido = datos_ota.get("tot_turno") if datos_ota else None
    if k is not None:
        llegada = plan["puntos"][k]["llegada_h"]
        if tot_pedido is not None and base is not None:
            t = ota.turno_de_despegue_para_tot(int(tot_pedido), llegada)
            if not esc.turno_actual <= t <= esc.turno_actual + misiones_mod.MAX_ANTICIPACION_TURNOS:
                errores.append(f"Para estar sobre el blanco en T{tot_pedido} debería despegar en T{t}: el despegue se "
                               f"programa entre T{esc.turno_actual} y T{esc.turno_actual + misiones_mod.MAX_ANTICIPACION_TURNOS}.")
            else:
                turno = t
        plan["tot_turno"] = turno + int(math.floor(llegada + 1e-9))
        if tot_pedido is not None and plan["tot_turno"] != int(tot_pedido) and base is None:
            plan["advertencias"].append(f"Llegaría al blanco en T{plan['tot_turno']}, no en el TOT pedido (T{tot_pedido}).")
    elif tot_pedido is not None:
        errores.append("El TOT (hora sobre el blanco) solo se fija en misiones con un punto de blanco.")
    k_aer = next((i for i, p in enumerate(puntos) if p.get("reabastecimiento")), None)
    if k_aer is not None:
        plan["aar"] = apoyo_aereo.estimar_aar(catalogo.MODELOS.get(modelo or ""), n, plan["puntos"][k_aer]["combustible_llegada"])
        plan["aar"]["turno"] = turno + int(math.floor(plan["puntos"][k_aer]["llegada_h"] + 1e-9))
    if payload.rol in ("AAR", "AEW"):
        n_esc = 0
        if payload.escolta is not None:
            g = db.get(Unidad, payload.escolta.unidad_id) if payload.escolta.unidad_id else None
            n_esc = (g.aeronaves or 0) if g is not None else (payload.escolta.aeronaves or 2)
        if n_esc < apoyo_aereo.ESCOLTAS_MINIMAS:
            errores.append(f"{misiones_mod.ROLES[payload.rol].nombre}: es un activo de alto valor y va con "
                           f"{apoyo_aereo.ESCOLTAS_MINIMAS} cazas de escolta (agregue la escolta del paquete).")
    # calculo de armamento contra el primer blanco con unidad, con el armamento primario elegido
    arma = (datos_ota or {}).get("armamento_primario")
    pb = next((p for p in puntos if p["tipo"] == "blanco" and p.get("objetivo_unidad_id")), None)
    if arma and pb is not None:
        x = db.get(Unidad, pb["objetivo_unidad_id"])
        tipo_b = weaponeering.tipo_de_blanco(x)
        w = weaponeering.calcular(arma, tipo_b, dmpi=weaponeering.dmpi_de(x, tipo_b), aeronaves=n)
        if w is not None:
            plan["weaponeering"] = w
            if not w["suficiente"]:
                plan["advertencias"].append(
                    f"Cálculo de armamento: para «{w['criterio_nombre'].lower()}» sobre {x.nombre} hacen falta unas "
                    f"{w['lanzar']} {arma} ({w['aeronaves_necesarias']} aeronaves); {n} aeronave(s) llevan {w['lleva']}.")
            todas = db.query(Unidad).filter(Unidad.escenario_id == esc.id).all()
            colat = weaponeering.colaterales(x.lat, x.lon, w["radio_escombros_m"], todas, usuario.rol, x.id)
            if colat:
                plan["advertencias"].append("Riesgo de daño colateral (radio de escombros de "
                                            f"{w['radio_escombros_m']} m): " + ", ".join(f"{u.nombre} a {d} m" for u, d in colat) + ".")
    reunion = next((i for i, p in enumerate(puntos) if p.get("reunion")), None)
    if reunion is not None:
        plan["reunion_turno"] = turno + int(math.floor(plan["puntos"][reunion]["llegada_h"] + 1e-9))
    # logistica de la mision: combustible (kg) y oxigeno liquido (l) para toda la ruta, con la reserva
    plan["logistica"] = plataformas.requerimientos(catalogo.MODELOS.get(modelo or ""), n, plan["duracion_h"], factor)
    if plan["logistica"] and plan["logistica"]["excede_lox"]:
        plan["advertencias"].append(
            f"El oxigeno liquido de a bordo ({plan['logistica']['lox_a_bordo_l']:g} l) no alcanza para "
            f"{plan['duracion_h']:.1f} h de vuelo con la reserva.")
    if payload.rol == "ESCOLTA":
        e = db.get(Mision, payload.escolta_de) if payload.escolta_de else None
        if e is None or e.escenario_id != esc.id or e.bando != usuario.rol or e.estado not in misiones_mod.ACTIVAS:
            errores.append("Indique la mision propia (programada o en curso) que va a escoltar.")
        elif e.rol == "ESCOLTA":
            errores.append("Una escolta no puede escoltar a otra escolta.")
        else:
            plan["escolta_de"] = e.id
    return {
        "puntos": puntos, "turno": turno, "modelo": modelo, "aeronaves": n, "errores": errores, "plan": plan,
        "ota": datos_ota,
    }


def _ota_escolta(datos_ota: dict | None, modelo: str | None, unidad_id: int | None, db: Session) -> dict:
    """La escolta va en el paquete de la mision escoltada, con un misil aire-aire como armamento primario."""
    if unidad_id:
        g = db.get(Unidad, unidad_id)
        modelo = g.modelo if g is not None else modelo
    aa = [a for a in ota.armas_de(modelo, misiones_mod.clase_de_modelo(modelo or "")) if ota.ARMAMENTO[a][1] == "aa"]
    return {"paquete": (datos_ota or {}).get("paquete", ""), "funcion": "-", "alerta": (datos_ota or {}).get("alerta", 1),
            "armamento_primario": aa[0] if aa else "", "armamento_secundario": aa[-1] if len(aa) > 1 else "",
            "iff": "", "codigo": "3EA", "pdi": "", "tot_turno": None}


@router.post("/previsualizar")
def previsualizar(payload: schemas.MisionIn, esc: Escenario = Depends(auth.escenario_dep),
                  db: Session = Depends(get_db), usuario: Usuario = Depends(auth.conductor)):
    """Estimacion (hora y combustible en cada punto) y errores de la mision, sin crearla."""
    r = _preparar(payload, esc, db, usuario)
    return {"plan": r["plan"], "errores": r["errores"], "turno_despegue": r["turno"], "puntos": r["puntos"]}


# ---------------------------------------------------------------- Orden de Tareas Aereas (AV/D 5-47)
def _ota(esc: Escenario, db: Session, usuario: Usuario, bando: str | None, tipo: str) -> tuple[str, list, dict]:
    if usuario.rol in ("azul", "rojo"):
        bando = usuario.rol  # cada bando ve solo su OTA
    elif bando not in ("azul", "rojo"):
        bando = "azul"
    tipo = tipo.upper() if tipo and tipo.upper() in ota.TIPOS_OPERACION else "ENT"
    docs, _ = legajo._contexto(db, esc, bando)
    info = legajo.informacion(db, esc, bando, docs)
    nombre = info["nombre_clave"] if not info["nombre_clave"].startswith("(") else esc.nombre
    misiones = db.query(Mision).filter(Mision.escenario_id == esc.id, Mision.bando == bando,
                                       Mision.estado.in_(misiones_mod.ACTIVAS)).all()
    unidades = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id)}
    lineas = ota.lineas_ota(db, esc, bando, misiones, unidades, nombre, "CAO", tipo)
    titulo = "Orden de Tareas Aéreas (OTA)"
    bloques = legajo._encabezado(info, titulo) + ota.bloques(lineas) + legajo._final(info)
    return f"{titulo} · {bando.capitalize()}", bloques, {**lineas, "bando": bando}


@router.get("/ota")
def ota_lineas(bando: str | None = None, tipo: str = "ENT", esc: Escenario = Depends(auth.escenario_dep),
               db: Session = Depends(get_db), usuario: Usuario = Depends(auth.usuario_actual)):
    """Lineas de la OTA del bando (misiones programadas y en curso) en el formato de la AV/D 5-47."""
    return _ota(esc, db, usuario, bando, tipo)[2]


@router.get("/ota.docx")
def ota_word(bando: str | None = None, tipo: str = "ENT", esc: Escenario = Depends(auth.escenario_dep),
             db: Session = Depends(get_db), usuario: Usuario = Depends(auth.usuario_actual)):
    titulo, bloques, d = _ota(esc, db, usuario, bando, tipo)
    return Response(legajo.word(titulo, bloques),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="ota_{d["bando"]}_esc{esc.id}_t{esc.turno_actual}.docx"'})


@router.get("/ota.html", response_class=HTMLResponse)
def ota_html(bando: str | None = None, tipo: str = "ENT", esc: Escenario = Depends(auth.escenario_dep),
             db: Session = Depends(get_db), usuario: Usuario = Depends(auth.usuario_actual)):
    """La misma OTA como pagina imprimible (el navegador la guarda como PDF)."""
    titulo, bloques, _ = _ota(esc, db, usuario, bando, tipo)
    return HTMLResponse(legajo.pagina(titulo, bloques))


@router.post("")
async def crear(payload: schemas.MisionIn, esc: Escenario = Depends(auth.escenario_dep),
                db: Session = Depends(get_db), usuario: Usuario = Depends(auth.conductor)):
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
        plan_json=json.dumps(r["plan"]), autor=usuario.username, **puestos.firma(usuario),
        resultado="Programada." if r["turno"] > esc.turno_actual else "Se inicia al resolverse este turno.",
        ota_json=json.dumps(r["ota"]) if r["ota"] else None,
    )
    db.add(m)
    db.flush()
    # paquete: la escolta se crea junto con la mision, con el mismo turno de despegue y aterrizaje en la misma base
    if payload.escolta is not None and payload.rol != "ESCOLTA":
        aterrizaje = next((p for p in reversed(r["puntos"]) if p["tipo"] == "aterrizaje"), None)
        if aterrizaje is None:
            raise HTTPException(status_code=400, detail="Para agregar escolta la mision debe terminar en un aterrizaje")
        esc_payload = schemas.MisionIn(
            rol="ESCOLTA", nombre=(payload.escolta.nombre or f"Escolta {m.nombre or m.rol}")[:40],
            puntos=[schemas.PuntoMisionIn(tipo="aterrizaje", lat=aterrizaje["lat"], lon=aterrizaje["lon"], base_id=aterrizaje["base_id"])],
            unidad_id=payload.escolta.unidad_id, base_id=payload.escolta.base_id, modelo=payload.escolta.modelo,
            aeronaves=payload.escolta.aeronaves, turno_despegue=None if payload.escolta.unidad_id else r["turno"],
            escolta_de=m.id,
        )
        re = _preparar(esc_payload, esc, db, usuario)
        if re["errores"]:
            raise HTTPException(status_code=400, detail="Escolta: " + " ".join(re["errores"]))
        db.add(Mision(
            escenario_id=esc.id, bando=usuario.rol, rol="ESCOLTA", nombre=esc_payload.nombre, estado="programada",
            unidad_id=esc_payload.unidad_id, base_id=esc_payload.base_id, modelo=re["modelo"] or "", aeronaves=re["aeronaves"] or 0,
            turno_despegue=re["turno"], creada_turno=esc.turno_actual, puntos_json=json.dumps(re["puntos"]),
            plan_json=json.dumps(re["plan"]), autor=usuario.username, resultado="Escolta programada.",
            ota_json=json.dumps(_ota_escolta(r["ota"], re["modelo"], esc_payload.unidad_id, db)),
            **puestos.firma(usuario),
        ))
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
                   usuario: Usuario = Depends(auth.conductor)):
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
