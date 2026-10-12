"""Informe posterior al ejercicio (AAR): instantaneas por turno, combates, resumen y rubrica de evaluacion
por bando, por puesto y por alumno (`construir_rubrica`)."""

import json
import re
from collections import Counter, OrderedDict

from sqlalchemy.orm import Session

from app import state
from app.engine import catalogo, puestos
from app.engine import objetivos as objetivos_mod
from app.engine import orders as orders_mod
from app.models.aar import Combate, Instantanea, RegistroLogistico
from app.models.asignacion import Asignacion
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.mision import Mision
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.models.usuario import Usuario

CAMPOS_UNIDAD = (
    "id", "nombre", "bando", "tipo", "clase", "sidc", "lat", "lon", "fuerza", "estado",
    "combustible", "municion",
)


def _datos_unidades(db: Session, escenario_id: int) -> list[dict]:
    return [
        {c: getattr(u, c) for c in CAMPOS_UNIDAD}
        for u in db.query(Unidad).filter(Unidad.escenario_id == escenario_id).order_by(Unidad.id)
    ]


def guardar_instantanea(db: Session, escenario: Escenario, turno: int) -> None:
    """Guarda (o reemplaza) el estado del escenario al terminar `turno`."""
    datos = json.dumps({"unidades": _datos_unidades(db, escenario.id)})
    inst = (
        db.query(Instantanea)
        .filter(Instantanea.escenario_id == escenario.id, Instantanea.turno == turno)
        .first()
    )
    if inst is None:
        db.add(Instantanea(escenario_id=escenario.id, turno=turno, clima=escenario.clima, datos_json=datos))
    else:
        inst.datos_json, inst.clima = datos, escenario.clima


def asegurar_linea_base(db: Session, escenario: Escenario) -> None:
    """Antes del primer turno resuelto, guarda el despliegue inicial (turno 0)."""
    hay = db.query(Instantanea.id).filter(Instantanea.escenario_id == escenario.id).first()
    if hay is None:
        guardar_instantanea(db, escenario, escenario.turno_actual - 1)


def registrar_ajuste(db: Session, escenario: Escenario, descripcion: str) -> None:
    """Deja constancia de una intervencion manual del instructor (solo visible en el informe)."""
    db.add(Evento(
        escenario_id=escenario.id, turno=escenario.turno_actual, tipo="ajuste",
        bando_destino="instructor", descripcion=descripcion,
    ))


def _orden_dict(o: Orden, nombres: dict) -> dict:
    return {
        "id": o.id, "turno": o.turno_emitida, "unidad_id": o.unidad_id,
        "unidad": nombres.get(o.unidad_id, f"#{o.unidad_id}"), "tipo": o.tipo,
        "objetivo": nombres.get(o.objetivo_unidad_id) if o.objetivo_unidad_id else None,
        "waypoints": json.loads(o.waypoints_json or "[]"), "estado": o.estado, "resultado": o.resultado,
        "autor": o.autor, "autor_puesto": o.autor_puesto,
    }


def _combate_dict(c: Combate) -> dict:
    return {
        "id": c.id, "turno": c.turno, "atacante_id": c.atacante_id, "defensor_id": c.defensor_id,
        "atacante": c.atacante_nombre, "defensor": c.defensor_nombre,
        "atacante_bando": c.atacante_bando, "defensor_bando": c.defensor_bando,
        "ratio": round(c.ratio, 3), "perdida_atacante": round(c.perdida_atacante, 1),
        "perdida_defensor": round(c.perdida_defensor, 1), "terreno": c.terreno,
        "efectos": c.efectos, "lat": c.lat, "lon": c.lon,
    }


def construir_informe(db: Session, escenario: Escenario) -> dict:
    """Vista completa (sin niebla de guerra) de todo lo ocurrido en el escenario."""
    unidades = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id)}
    nombres = {uid: u.nombre for uid, u in unidades.items()}
    instantaneas = (
        db.query(Instantanea).filter(Instantanea.escenario_id == escenario.id).order_by(Instantanea.turno).all()
    )
    combates = db.query(Combate).filter(Combate.escenario_id == escenario.id).order_by(Combate.id).all()
    ordenes = db.query(Orden).filter(Orden.escenario_id == escenario.id).order_by(Orden.id).all()
    eventos = db.query(Evento).filter(Evento.escenario_id == escenario.id).order_by(Evento.id).all()

    # Fuerza de cada unidad en la primera y ultima instantanea, para contar bajas.
    turnos: dict[int, dict] = {}
    for inst in instantaneas:
        turnos[inst.turno] = {
            "turno": inst.turno, "clima": inst.clima, "unidades": json.loads(inst.datos_json)["unidades"],
            "combates": [], "ordenes": [], "eventos": [], "en_curso": False,
        }
    for c in combates:
        turnos[c.turno]["combates"].append(_combate_dict(c))

    def entrada_en_curso() -> dict:
        # Ordenes y eventos del turno que aun no se resolvio (no tiene instantanea).
        return turnos.setdefault(escenario.turno_actual, {
            "turno": escenario.turno_actual, "clima": escenario.clima, "unidades": [],
            "combates": [], "ordenes": [], "eventos": [], "en_curso": True,
        })

    for o in ordenes:
        if o.turno_emitida in turnos or o.turno_emitida == escenario.turno_actual:
            turnos.get(o.turno_emitida, None) or entrada_en_curso()
            turnos[o.turno_emitida]["ordenes"].append(_orden_dict(o, nombres))
    for e in eventos:
        if e.turno in turnos or e.turno == escenario.turno_actual:
            turnos.get(e.turno, None) or entrada_en_curso()
            turnos[e.turno]["eventos"].append(
                {"id": e.id, "turno": e.turno, "tipo": e.tipo, "bando_destino": e.bando_destino, "descripcion": e.descripcion}
            )

    resumen = {b: {
        "unidades": 0, "destruidas": 0, "fuerza_perdida": 0.0, "combates_iniciados": 0,
        "combates_recibidos": 0, "ordenes_emitidas": 0, "ordenes_rechazadas": 0,
        "dano_infligido": 0.0,
    } for b in ("azul", "rojo")}
    for u in unidades.values():
        r = resumen.get(u.bando)
        if r is None:
            continue
        r["unidades"] += 1
        r["destruidas"] += 1 if u.estado == "destruida" else 0
    for c in combates:
        resumen[c.atacante_bando]["combates_iniciados"] += 1
        resumen[c.defensor_bando]["combates_recibidos"] += 1
        resumen[c.atacante_bando]["fuerza_perdida"] += c.perdida_atacante
        resumen[c.defensor_bando]["fuerza_perdida"] += c.perdida_defensor
        resumen[c.atacante_bando]["dano_infligido"] += c.perdida_defensor
        resumen[c.defensor_bando]["dano_infligido"] += c.perdida_atacante
    for o in ordenes:
        u = unidades.get(o.unidad_id)
        if u is not None and u.bando in resumen:
            resumen[u.bando]["ordenes_emitidas"] += 1
            resumen[u.bando]["ordenes_rechazadas"] += 1 if o.estado == "rechazada" else 0
    for r in resumen.values():
        r["fuerza_perdida"] = round(r["fuerza_perdida"], 1)
        r["dano_infligido"] = round(r["dano_infligido"], 1)

    return {
        "escenario": {
            "id": escenario.id, "nombre": escenario.nombre, "estado": escenario.estado,
            "turno_actual": escenario.turno_actual, "clima": escenario.clima, "azar": escenario.azar,
            "creado_en": escenario.creado_en.isoformat(),
        },
        "turnos": [turnos[k] for k in sorted(turnos)],
        "resumen": resumen,
        "marcador": objetivos_mod.marcador(db, escenario),
        "objetivos": [
            state.serializar_objetivo(o, unidades)
            for o in db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id).order_by(Objetivo.id)
        ],
    }


# ---------------------------------------------------------------------------------------------------------
# Replay animado: lo justo para animar el mapa turno a turno (posiciones, combates con su lugar, novedades y
# marcador acumulado). Es un subconjunto de `construir_informe`, sin ordenes ni combustible/municion.
CAMPOS_REPLAY = ("id", "nombre", "bando", "tipo", "clase", "sidc", "lat", "lon", "fuerza", "estado")
# novedades que ven ambos bandos en la repeticion (las dirigidas a un solo bando no se muestran)
TIPOS_NOVEDAD_PUBLICA = ("ajuste", "clima", "logistica")


def _marcador_hasta(objetivos: list[Objetivo], combates: list[Combate], turno: int) -> dict:
    """Marcador acumulado al terminar `turno`: puntos de objetivos cumplidos hasta ese turno mas un punto por
    cada FUERZA_POR_PUNTO de fuerza infligida al enemigo (misma regla que engine/objetivos.marcador)."""
    puntos = {b: 0 for b in objetivos_mod.BANDOS}
    infligido = {b: 0.0 for b in objetivos_mod.BANDOS}
    for o in objetivos:
        if o.estado == "cumplido" and o.bando in puntos and (o.turno_resuelto is None or o.turno_resuelto <= turno):
            puntos[o.bando] += o.puntos
    for c in combates:
        if c.turno > turno or c.atacante_bando == c.defensor_bando:
            continue
        if c.atacante_bando in infligido:
            infligido[c.atacante_bando] += c.perdida_defensor
        if c.defensor_bando in infligido:
            infligido[c.defensor_bando] += c.perdida_atacante
    return {
        b: {"objetivos": puntos[b], "bajas": int(infligido[b] // objetivos_mod.FUERZA_POR_PUNTO),
            "total": puntos[b] + int(infligido[b] // objetivos_mod.FUERZA_POR_PUNTO)}
        for b in objetivos_mod.BANDOS
    }


def construir_replay(db: Session, escenario: Escenario) -> dict:
    """Turnos con instantanea (el turno en curso no), cada uno con todas las unidades (id, nombre, bando, tipo,
    clase, sidc, lat, lon, fuerza, estado), los combates del turno con su lugar y sus participantes, las novedades
    publicas y el marcador acumulado. Mismos permisos que el informe: lo decide el router."""
    instantaneas = (
        db.query(Instantanea).filter(Instantanea.escenario_id == escenario.id).order_by(Instantanea.turno).all()
    )
    combates = db.query(Combate).filter(Combate.escenario_id == escenario.id).order_by(Combate.id).all()
    eventos = db.query(Evento).filter(Evento.escenario_id == escenario.id).order_by(Evento.id).all()
    objetivos = db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id).order_by(Objetivo.id).all()

    turnos = []
    for inst in instantaneas:
        filas = json.loads(inst.datos_json)["unidades"]
        turnos.append({
            "turno": inst.turno, "clima": inst.clima,
            "unidades": [{c: u.get(c) for c in CAMPOS_REPLAY} for u in filas],
            "combates": [_combate_dict(c) for c in combates if c.turno == inst.turno],
            "eventos": [
                {"id": e.id, "tipo": e.tipo, "descripcion": e.descripcion}
                for e in eventos
                if e.turno == inst.turno and (e.tipo in TIPOS_NOVEDAD_PUBLICA or e.bando_destino == "todos")
            ],
            "marcador": _marcador_hasta(objetivos, combates, inst.turno),
        })
    return {
        "escenario": {
            "id": escenario.id, "nombre": escenario.nombre, "estado": escenario.estado,
            "turno_actual": escenario.turno_actual, "hora_inicio_min": escenario.hora_inicio_min,
        },
        "turnos": turnos,
    }


# ---------------------------------------------------------------------------------------------------------
# Rubrica de evaluacion por bando y por puesto
UMBRAL_CRITICO = 25.0  # % de combustible o municion por debajo del cual la unidad esta al limite
TOP_MOTIVOS = 3

# El desglose por puesto se deriva de la FUNCION de cada orden (el puesto responsable segun engine/puestos.py),
# no del alumno que la firmo; la evaluacion por alumno (seccion `alumnos`) si usa el autor registrado.
NOTA_PUESTOS = (
    "El desglose por puesto se deriva de la funcion de cada orden (puesto responsable: A2, A3, A4 o A5), "
    "no del alumno que la firmo; la evaluacion por alumno usa el autor registrado en cada orden y mision."
)
SIN_AUTOR = "sin autor registrado"
NOTA_ALUMNOS = (
    "Las ordenes y misiones anteriores a la version que registra su autor figuran como 'sin autor registrado'; "
    "las ordenes automaticas del motor (intercepciones, defensa antiaerea, ataques de mision) no se atribuyen a nadie."
)

_SUGERENCIAS = (
    (re.compile(r"fuera de(l)? alcance", re.I), "revisar la apreciacion de distancias antes de emitir la orden"),
    (re.compile(r"sin municion|material insuficiente", re.I), "planificar el reabastecimiento antes de empenar la unidad"),
    (re.compile(r"recargando|desplegando", re.I), "tener en cuenta los tiempos de recarga y despliegue del sistema"),
    (re.compile(r"en tierra", re.I), "respetar los turnos de reabastecimiento y rearme en pista antes de ordenar el despegue"),
    (re.compile(r"no esta activa|invalido|fuera de combate", re.I), "actualizar la situacion propia y enemiga antes de emitir"),
    (re.compile(r"no puede atacar objetivos", re.I), "emplear el medio adecuado contra cada tipo de objetivo"),
    (re.compile(r"sin waypoints|indique", re.I), "completar los datos de la orden antes de enviarla"),
)


def motivo_generico(texto: str) -> str:
    """Agrupa motivos de rechazo que solo difieren en cifras: 'Objetivo fuera de alcance (12.3 km > 10 km).'
    y '... (40 km > 10 km).' son el mismo motivo."""
    t = texto or ""
    while True:  # parentesis anidados: "Recargando (2 turno(s) restante(s))."
        nuevo = re.sub(r"\s*\([^()]*\)", "", t)
        if nuevo == t:
            break
        t = nuevo
    t = re.sub(r"\d+(?:[.,]\d+)?", "N", t)
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return t or "(sin motivo)"


def _sugerencia(motivo: str) -> str:
    for patron, consejo in _SUGERENCIAS:
        if patron.search(motivo):
            return consejo
    return "revisar las condiciones de la orden"


def _puesto_de(unidad: Unidad | None, tipo_orden: str) -> str:
    """Puesto especializado responsable de una orden (mando queda fuera: reune a todos)."""
    if unidad is None:
        funcion = "despegar" if tipo_orden in ("despegar", "mision") else "superficie"
    else:
        funcion = puestos.funcion_de_orden(unidad, tipo_orden, catalogo.perfil(unidad))
    resp = puestos.responsables(funcion)
    return resp[0].id if resp else puestos.POR_DEFECTO


def _bloque_ordenes() -> dict:
    return {"emitidas": 0, "resueltas": 0, "rechazadas": 0, "pendientes": 0, "_motivos": Counter()}


def _cerrar_ordenes(b: dict) -> dict:
    motivos = b.pop("_motivos")
    b["motivos_rechazo"] = [{"motivo": m, "veces": n} for m, n in motivos.most_common(TOP_MOTIVOS)]
    b["tasa_rechazo"] = round(100.0 * b["rechazadas"] / b["emitidas"], 1) if b["emitidas"] else 0.0
    return b


def _observaciones_ordenes(o: dict, quien: str = "") -> list[str]:
    obs = []
    for m in o["motivos_rechazo"]:
        if m["veces"] >= 2:
            obs.append(f"{m['veces']} orden(es) rechazada(s){quien} por '{m['motivo']}': {_sugerencia(m['motivo'])}.")
    if o["emitidas"] >= 3 and o["tasa_rechazo"] >= 30:
        obs.append(f"Alta proporcion de ordenes rechazadas{quien} ({o['tasa_rechazo']:.0f} % de {o['emitidas']}): "
                   "verificar alcance, municion y estado de la unidad antes de emitir.")
    return obs


def _bloque_misiones() -> dict:
    return {"planificadas": 0, "cumplidas": 0, "abortadas": 0, "fallidas": 0, "canceladas": 0, "en_curso": 0}


def _contar_mision(mm: dict, m: Mision) -> None:
    mm["planificadas"] += 1
    clave = {"cumplida": "cumplidas", "abortada": "abortadas", "fallida": "fallidas", "cancelada": "canceladas",
             "en_curso": "en_curso"}.get(m.estado)
    if clave:
        mm[clave] += 1


def _contar_orden(bl: dict, o: Orden) -> None:
    bl["emitidas"] += 1
    if o.estado == "rechazada":
        bl["rechazadas"] += 1
        bl["_motivos"][motivo_generico(o.resultado)] += 1
    elif o.estado == "resuelta":
        bl["resueltas"] += 1
    else:
        bl["pendientes"] += 1


def _observacion_pasivos(tp: dict) -> str:
    lista = ", ".join(str(t) for t in tp["turnos"][:8]) + ("..." if len(tp["turnos"]) > 8 else "")
    return (f"{tp['cantidad']} turno(s) sin emitir ninguna orden (turno(s) {lista}): "
            "mantener la iniciativa o dejar constancia de la decision de esperar.")


def _observacion_misiones(mi: dict) -> str | None:
    malas = mi["abortadas"] + mi["fallidas"]
    if malas and malas >= mi["cumplidas"]:
        return (f"Misiones aereas abortadas o fallidas ({malas}) igualan o superan a las cumplidas "
                f"({mi['cumplidas']}): revisar el combustible, las rutas y la ventana de aterrizaje (A3).")
    return None


def _alumnos(db: Session, escenario: Escenario, unidades: dict, ordenes: list, misiones: list,
             turnos_resueltos: list[int]) -> tuple[list[dict], dict]:
    """Evaluacion por alumno: cada usuario de un bando asignado al escenario y cada autor registrado de una orden o
    mision. Devuelve la lista (por bando y nombre) y, por bando, cuantas ordenes y misiones de alumnos quedaron sin
    autor registrado (anteriores a la migracion 0018); las ordenes automaticas del motor no cuentan."""
    asignados = {a.usuario_id for a in db.query(Asignacion).filter(Asignacion.escenario_id == escenario.id)}
    autores = {o.autor_id for o in ordenes if o.autor_id} | {m.autor_id for m in misiones if m.autor_id}
    # misiones previas a la migracion: solo guardan el nombre de usuario
    nombres = {m.autor for m in misiones if not m.autor_id and m.autor}
    usuarios: dict[int, Usuario] = {}
    if asignados | autores:
        usuarios.update((u.id, u) for u in db.query(Usuario).filter(Usuario.id.in_(asignados | autores)))
    if nombres:
        usuarios.update((u.id, u) for u in db.query(Usuario).filter(Usuario.username.in_(nombres)))
    por_nombre = {u.username: u.id for u in usuarios.values()}

    fichas: dict[int, dict] = {}
    for uid, u in usuarios.items():
        if uid not in autores and u.username not in nombres and u.rol not in puestos.BANDOS:
            continue  # observadores e instructores asignados que no emitieron nada no se evaluan
        fichas[uid] = {
            "usuario_id": uid, "username": u.username, "bando": u.rol, "asignado": uid in asignados,
            "ordenes": _bloque_ordenes(), "misiones": _bloque_misiones(), "observaciones": [],
            "_turnos": set(), "_puestos": Counter(),
        }
    sin_autor = {b: {"ordenes": 0, "misiones": 0} for b in puestos.BANDOS}

    for o in ordenes:
        f = fichas.get(o.autor_id)
        if f is not None:
            _contar_orden(f["ordenes"], o)
            f["_turnos"].add(o.turno_emitida)
            if o.autor_puesto:
                f["_puestos"][o.autor_puesto] += 1
        elif not orders_mod.es_automatica(o):
            u = unidades.get(o.unidad_id)
            if u is not None and u.bando in sin_autor:
                sin_autor[u.bando]["ordenes"] += 1
    for m in misiones:
        f = fichas.get(m.autor_id or por_nombre.get(m.autor))
        if f is not None:
            _contar_mision(f["misiones"], m)
            f["_turnos"].add(m.creada_turno)
            if m.autor_puesto:
                f["_puestos"][m.autor_puesto] += 1
        elif m.bando in sin_autor:
            sin_autor[m.bando]["misiones"] += 1

    lista = []
    for f in fichas.values():
        usados = f.pop("_puestos")
        # puesto que ocupaba al emitir (el mas frecuente); si no quedo registrado, el que tiene ahora
        p = puestos.obtener(usados.most_common(1)[0][0] if usados else usuarios[f["usuario_id"]].puesto)
        f["puesto"], f["sigla"], f["puesto_nombre"] = p.id, p.sigla, p.nombre
        activos = sorted(f.pop("_turnos"))
        pasivos = [t for t in turnos_resueltos if t not in activos]
        f["turnos_activos"] = {"cantidad": len(activos), "turnos": activos}
        f["turnos_pasivos"] = {"cantidad": len(pasivos), "turnos": pasivos}
        f["ordenes"] = _cerrar_ordenes(f["ordenes"])
        obs = f["observaciones"]
        o, mi = f["ordenes"], f["misiones"]
        if turnos_resueltos and o["emitidas"] == 0 and mi["planificadas"] == 0:
            obs.append("No emitio ninguna orden ni planifico misiones durante el ejercicio.")
        obs.extend(_observaciones_ordenes(o, f" de {f['username']}"))
        if pasivos and o["emitidas"] + mi["planificadas"] > 0:
            obs.append(_observacion_pasivos(f["turnos_pasivos"]))
        aviso = _observacion_misiones(mi)
        if aviso:
            obs.append(aviso)
        if not obs:
            obs.append("Sin observaciones destacables.")
        lista.append(f)
    orden_bando = {b: i for i, b in enumerate(puestos.BANDOS)}
    lista.sort(key=lambda f: (orden_bando.get(f["bando"], len(orden_bando)), f["username"]))
    return lista, sin_autor


def construir_rubrica(db: Session, escenario: Escenario) -> dict:
    """Indicadores de conduccion por bando (y por puesto responsable) a partir de ordenes, unidades, combates,
    registro logistico, objetivos y misiones, con observaciones automaticas en espanol."""
    unidades = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id).order_by(Unidad.id)}
    ordenes = db.query(Orden).filter(Orden.escenario_id == escenario.id).order_by(Orden.id).all()
    combates = db.query(Combate).filter(Combate.escenario_id == escenario.id).order_by(Combate.id).all()
    misiones = db.query(Mision).filter(Mision.escenario_id == escenario.id).order_by(Mision.id).all()
    objetivos = db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id).order_by(Objetivo.id).all()
    registros = (
        db.query(RegistroLogistico).filter(RegistroLogistico.escenario_id == escenario.id)
        .order_by(RegistroLogistico.id).all()
    )
    instantaneas = (
        db.query(Instantanea).filter(Instantanea.escenario_id == escenario.id).order_by(Instantanea.turno).all()
    )
    turnos_resueltos = list(range(1, max(escenario.turno_actual, 1)))
    bandos = ("azul", "rojo")

    r: dict[str, dict] = {}
    for b in bandos:
        r[b] = {
            "ordenes": _bloque_ordenes(),
            "turnos_pasivos": {"cantidad": 0, "turnos": []},
            "logistica": {"unidades_criticas": [], "unidades_en_nivel_critico": 0, "reabastecimientos": 0},
            "perdidas": {"infligidas": 0.0, "sufridas": 0.0, "unidades_destruidas": 0, "enemigas_destruidas": 0},
            "objetivos": {"cumplidos": 0, "fallidos": 0, "pendientes": 0, "puntos": 0},
            "misiones": _bloque_misiones(),
            "puestos": OrderedDict(),
            "observaciones": [],
        }
        for p in puestos.PUESTOS.values():
            if p.id != puestos.POR_DEFECTO:
                r[b]["puestos"][p.id] = {"sigla": p.sigla, "nombre": p.nombre, "ordenes": _bloque_ordenes(),
                                         "misiones": 0, "observaciones": []}

    # ---- ordenes (por bando y por puesto responsable) ----
    actividad: dict[str, set[int]] = {b: set() for b in bandos}
    for o in ordenes:
        u = unidades.get(o.unidad_id)
        if u is None or u.bando not in r:
            continue
        actividad[u.bando].add(o.turno_emitida)
        for bl in (r[u.bando]["ordenes"], r[u.bando]["puestos"][_puesto_de(u, o.tipo)]["ordenes"]):
            _contar_orden(bl, o)

    # ---- misiones aereas ----
    for m in misiones:
        if m.bando not in r:
            continue
        actividad[m.bando].add(m.creada_turno)
        _contar_mision(r[m.bando]["misiones"], m)
        r[m.bando]["puestos"][_puesto_de(unidades.get(m.unidad_id), "mision")]["misiones"] += 1

    # ---- turnos pasivos ----
    for b in bandos:
        if not any(u.bando == b for u in unidades.values()):
            continue
        pasivos = [t for t in turnos_resueltos if t not in actividad[b]]
        r[b]["turnos_pasivos"] = {"cantidad": len(pasivos), "turnos": pasivos}

    # ---- logistica: unidades que llegaron a menos del 25 % y reabastecimientos ----
    criticas: dict[int, dict] = {}
    series = [(inst.turno, json.loads(inst.datos_json)["unidades"]) for inst in instantaneas]
    series.append((escenario.turno_actual, [
        {"id": u.id, "nombre": u.nombre, "bando": u.bando, "combustible": u.combustible, "municion": u.municion}
        for u in unidades.values()]))
    for turno, filas in series:
        for f in filas:
            for variable in ("combustible", "municion"):
                nivel = f.get(variable)
                if nivel is None or nivel >= UMBRAL_CRITICO:
                    continue
                c = criticas.setdefault(f["id"], {"unidad_id": f["id"], "unidad": f["nombre"], "bando": f["bando"],
                                                  "variables": [], "turno": turno, "minimo": nivel})
                if variable not in c["variables"]:
                    c["variables"].append(variable)
                c["minimo"] = min(c["minimo"], nivel)
    for c in criticas.values():
        if c["bando"] in r:
            c["minimo"] = round(c["minimo"], 1)
            r[c["bando"]]["logistica"]["unidades_criticas"].append(c)
    reabastecidos: dict[str, set] = {b: set() for b in bandos}
    for f in registros:
        if (f.bando in r and f.causa in ("reabastecimiento", "convoy", "reabastecimiento en vuelo") and f.variable in ("combustible", "municion")
                and f.despues > f.antes):
            reabastecidos[f.bando].add((f.turno, f.unidad_id))
    for b in bandos:
        r[b]["logistica"]["reabastecimientos"] = len(reabastecidos[b])
        r[b]["logistica"]["unidades_en_nivel_critico"] = len(r[b]["logistica"]["unidades_criticas"])

    # ---- perdidas ----
    for c in combates:
        if c.atacante_bando == c.defensor_bando:
            continue
        if c.atacante_bando in r:
            r[c.atacante_bando]["perdidas"]["infligidas"] += c.perdida_defensor
            r[c.atacante_bando]["perdidas"]["sufridas"] += c.perdida_atacante
        if c.defensor_bando in r:
            r[c.defensor_bando]["perdidas"]["infligidas"] += c.perdida_atacante
            r[c.defensor_bando]["perdidas"]["sufridas"] += c.perdida_defensor
    for u in unidades.values():
        if u.estado != "destruida" or u.bando not in r:
            continue
        r[u.bando]["perdidas"]["unidades_destruidas"] += 1
        r["rojo" if u.bando == "azul" else "azul"]["perdidas"]["enemigas_destruidas"] += 1
    for b in bandos:
        p = r[b]["perdidas"]
        p["infligidas"], p["sufridas"] = round(p["infligidas"], 1), round(p["sufridas"], 1)

    # ---- objetivos ----
    for o in objetivos:
        if o.bando not in r:
            continue
        ob = r[o.bando]["objetivos"]
        ob[{"cumplido": "cumplidos", "fallido": "fallidos"}.get(o.estado, "pendientes")] += 1
        if o.estado == "cumplido":
            ob["puntos"] += o.puntos

    # ---- cierre y observaciones ----
    for b in bandos:
        x = r[b]
        x["ordenes"] = _cerrar_ordenes(x["ordenes"])
        obs = x["observaciones"]
        tiene_unidades = any(u.bando == b for u in unidades.values())
        if turnos_resueltos and tiene_unidades and x["ordenes"]["emitidas"] == 0 and x["misiones"]["planificadas"] == 0:
            obs.append("El bando no emitio ninguna orden durante el ejercicio.")
        obs.extend(_observaciones_ordenes(x["ordenes"]))
        tp = x["turnos_pasivos"]
        if tp["cantidad"] and x["ordenes"]["emitidas"] + x["misiones"]["planificadas"] > 0:
            obs.append(_observacion_pasivos(tp))
        lg = x["logistica"]
        if lg["unidades_criticas"]:
            nombres = ", ".join(c["unidad"] for c in lg["unidades_criticas"][:5])
            extra = "" if len(lg["unidades_criticas"]) <= 5 else f" y {len(lg['unidades_criticas']) - 5} mas"
            cabeza = (f"{len(lg['unidades_criticas'])} unidad(es) llegaron a menos del {UMBRAL_CRITICO:.0f} % de "
                      f"combustible o municion ({nombres}{extra})")
            if lg["reabastecimientos"] == 0:
                obs.append(cabeza + " y no hubo ningun reabastecimiento: coordinar los convoyes y las bases (A4) "
                           "antes de que la unidad quede inmovil.")
            else:
                obs.append(cabeza + f"; se hicieron {lg['reabastecimientos']} reabastecimiento(s): anticipar el "
                           "apoyo logistico antes del nivel critico.")
        pd = x["perdidas"]
        if pd["sufridas"] > 0 and pd["sufridas"] >= 1.5 * pd["infligidas"]:
            obs.append(f"Las perdidas sufridas ({pd['sufridas']:.0f} pts) superan ampliamente a las infligidas "
                       f"({pd['infligidas']:.0f} pts): revisar la relacion de fuerzas y el terreno antes de empenar.")
        elif pd["infligidas"] > 0 and pd["infligidas"] >= 1.5 * pd["sufridas"]:
            obs.append(f"Relacion de intercambio favorable: {pd['infligidas']:.0f} pts infligidos frente a "
                       f"{pd['sufridas']:.0f} sufridos.")
        ob = x["objetivos"]
        if ob["fallidos"]:
            obs.append(f"{ob['fallidos']} objetivo(s) fallido(s): contrastar el plan con los objetivos asignados.")
        if ob["cumplidos"] and not ob["fallidos"] and not ob["pendientes"]:
            obs.append("Todos los objetivos asignados se cumplieron.")
        aviso = _observacion_misiones(x["misiones"])
        if aviso:
            obs.append(aviso)
        for pu in x["puestos"].values():
            pu["ordenes"] = _cerrar_ordenes(pu["ordenes"])
            pu["observaciones"] = _observaciones_ordenes(pu["ordenes"], f" en {pu['sigla']}")
        if not obs:
            obs.append("Sin observaciones destacables.")

    alumnos, sin_autor = _alumnos(db, escenario, unidades, ordenes, misiones, turnos_resueltos)
    return {
        "escenario": {"id": escenario.id, "nombre": escenario.nombre, "estado": escenario.estado,
                      "turno_actual": escenario.turno_actual, "turnos_resueltos": len(turnos_resueltos)},
        "umbral_critico": UMBRAL_CRITICO,
        "nota_puestos": NOTA_PUESTOS,
        "bandos": r,
        # evaluacion por alumno (autor registrado en cada orden y mision) y lo que quedo sin autor, por bando
        "alumnos": alumnos,
        "sin_autor": sin_autor,
        "nota_alumnos": NOTA_ALUMNOS,
    }
