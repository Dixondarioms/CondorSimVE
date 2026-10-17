"""Juego de guerra del TIEM: ensayar una Forma de Accion en una copia del escenario.

El Estado Mayor de un bando crea un ensayo de una de sus F/A: una copia del escenario en su estado ACTUAL (unidades con
su fuerza, combustible, municion y posicion; objetivos; calendario; Problema Militar y los ultimos contactos del bando)
en la que el adversario automatico conduce al enemigo y la resolucion es automatica cuando el bando confirma su turno.
Solo se asignan a la copia los alumnos de ese bando, asi el enemigo no ve el ensayo. Al terminar, el resumen del
ensayo (turnos jugados, objetivos, perdidas) sirve para fundamentar la confrontacion de las F/A con las capacidades del
enemigo en las apreciaciones de Operaciones y de Defensa Aerea.
"""

from sqlalchemy.orm import Session

from app import adversario
from app.engine import objetivos as objetivos_mod
from app.models.asignacion import Asignacion
from app.models.contacto import Contacto
from app.models.escenario import Escenario
from app.models.objetivo import Objetivo
from app.models.problema_militar import ProblemaMilitar
from app.models.unidad import Unidad
from app.models.usuario import Usuario

MAX_ENSAYOS = 3  # por bando y escenario
_CAMPOS_ESCENARIO = ("clima", "azar", "semilla", "hora_inicio_min", "turno_actual", "nacion_azul", "nacion_rojo", "niebla",
                     "logistica", "efectos_clima", "fuego_automatico", "ia_nivel", "dia_noche", "fecha_inicio", "turno_h",
                     "turno_final", "fases_json", "com_latencia_ms", "com_jitter_ms", "com_perdida_pct", "com_ordenes_pct")
_REFERENCIAS = ("base_id", "blanco_id", "transporte_id")  # columnas de Unidad que apuntan a otra unidad


def ensayos_de(db: Session, esc: Escenario, bando: str) -> list[Escenario]:
    return (db.query(Escenario).filter(Escenario.ensayo_de == esc.id, Escenario.ensayo_bando == bando)
            .order_by(Escenario.id).all())


def crear(db: Session, esc: Escenario, bando: str, fa: str) -> Escenario:
    """Crea y deja lista la copia de ensayo (la IA ya dio las ordenes enemigas del primer turno)."""
    enemigo = "rojo" if bando == "azul" else "azul"
    n = len(ensayos_de(db, esc, bando)) + 1
    corto = (fa.split(":")[0] or f"F/A {n}").strip()
    copia = Escenario(nombre=f"Ensayo {n} · {corto} · {bando.capitalize()} · {esc.nombre}"[:200],
                      ensayo_de=esc.id, ensayo_bando=bando, ensayo_fa=fa[:300], ensayo_desde=esc.turno_actual,
                      auto_resolver=True, **{c: getattr(esc, c) for c in _CAMPOS_ESCENARIO})
    setattr(copia, f"ia_{enemigo}", True)
    setattr(copia, f"conduce_{bando}", "alumnos")
    db.add(copia)
    db.flush()

    columnas = [c.name for c in Unidad.__table__.columns if c.name not in ("id", "escenario_id")]
    nuevas: dict[int, Unidad] = {}
    originales = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.estado != "destruida").order_by(Unidad.id).all()
    for u in originales:
        nuevas[u.id] = Unidad(escenario_id=copia.id, **{c: getattr(u, c) for c in columnas})
        db.add(nuevas[u.id])
    db.flush()
    for u in nuevas.values():
        for ref in _REFERENCIAS:
            viejo = getattr(u, ref)
            if viejo is not None:
                setattr(u, ref, nuevas[viejo].id if viejo in nuevas else None)

    columnas_obj = [c.name for c in Objetivo.__table__.columns if c.name not in ("id", "escenario_id", "unidad_id", "padre_id")]
    obj_nuevos: dict[int, Objetivo] = {}
    objs = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).order_by(Objetivo.id).all()
    for o in objs:
        if o.unidad_id is not None and o.unidad_id not in nuevas:
            continue  # su unidad ya fue destruida: no se ensaya
        obj_nuevos[o.id] = Objetivo(escenario_id=copia.id, unidad_id=nuevas[o.unidad_id].id if o.unidad_id else None,
                                    **{c: getattr(o, c) for c in columnas_obj})
        db.add(obj_nuevos[o.id])
    db.flush()
    for o in objs:
        if o.id in obj_nuevos and o.padre_id in obj_nuevos:
            obj_nuevos[o.id].padre_id = obj_nuevos[o.padre_id].id

    for pm in db.query(ProblemaMilitar).filter(ProblemaMilitar.escenario_id == esc.id, ProblemaMilitar.bando == bando):
        db.add(ProblemaMilitar(escenario_id=copia.id, bando=bando, contenido_json=pm.contenido_json, origen=pm.origen))
    for c in db.query(Contacto).filter(Contacto.escenario_id == esc.id, Contacto.bando == bando):
        if c.unidad_id in nuevas:
            db.add(Contacto(escenario_id=copia.id, bando=bando, unidad_id=nuevas[c.unidad_id].id, lat=c.lat, lon=c.lon,
                            turno_visto=c.turno_visto))
    alumnos = (db.query(Usuario).join(Asignacion, Asignacion.usuario_id == Usuario.id)
               .filter(Asignacion.escenario_id == esc.id, Usuario.rol == bando).all())
    for a in alumnos:
        db.add(Asignacion(usuario_id=a.id, escenario_id=copia.id))
    db.flush()
    adversario.jugar_turno(db, copia, bandos=[enemigo])
    return copia


def resumen(db: Session, copia: Escenario) -> dict:
    """Resultado del ensayo hasta ahora: turnos jugados, objetivos del bando, puntos y unidades perdidas."""
    bando = copia.ensayo_bando
    enemigo = "rojo" if bando == "azul" else "azul"
    m = objetivos_mod.marcador(db, copia)
    unidades = db.query(Unidad).filter(Unidad.escenario_id == copia.id).all()
    perdidas = {b: sum(1 for u in unidades if u.bando == b and u.estado == "destruida") for b in (bando, enemigo)}
    turnos = max(0, copia.turno_actual - (copia.ensayo_desde or copia.turno_actual))
    mio = m[bando]
    texto = (f"Ensayo de {copia.ensayo_fa or 'la F/A'}: {turnos} turno(s) jugado(s); objetivos {mio['cumplidos']} "
             f"cumplido(s) y {mio['fallidos']} fallido(s) de {mio['asignados']}; puntos por bajas infligidas "
             f"{mio['bajas']} contra {m[enemigo]['bajas']} sufridos; unidades perdidas: propias {perdidas[bando]}, "
             f"enemigas {perdidas[enemigo]}.")
    return {"id": copia.id, "nombre": copia.nombre, "fa": copia.ensayo_fa, "estado": copia.estado,
            "turnos_jugados": turnos, "turno_actual": copia.turno_actual, "marcador": m,
            "perdidas": perdidas, "texto": texto}
