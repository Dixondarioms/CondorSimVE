"""Fase III del TIEM: supervision de la ejecucion.

El TIEM la define como un ciclo: OBJETIVO (lo establecido en el plan) -> RESULTADO verdadero de lo ejecutado ->
DIFERENCIA entre ambos -> CAUSA -> ACCION CORRECTIVA, que retroalimenta la ejecucion. El simulador arma
automaticamente las tres primeras columnas para el bando con lo que el bando sabe (sus tareas, sus ordenes, sus
objetivos y sus unidades; nunca el estado real del enemigo) y sugiere la causa cuando la conoce (el motivo por el que
se rechazo una orden). La causa y la accion correctiva las escribe el Estado Mayor en el documento de Supervision,
cuyas ordenes fragmentarias (tareas nuevas) se emiten como ordenes igual que las del Plan de Operaciones.
"""

from sqlalchemy.orm import Session

from app.engine import calendario, tiem
from app.models.documento_tiem import EjecucionTarea
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.unidad import Unidad

ESTADOS = ("conforme", "en curso", "desvio", "fallido")  # del renglon del cuadro
FUERZA_CRITICA = 50.0  # % de fuerza por debajo del cual una unidad propia se informa
AVISO_PLAZO = 2  # turnos antes del plazo de un objetivo pendiente en que se lo marca


def tareas_del_bando(documentos: dict[str, dict]) -> list[tuple[dict, str]]:
    """Tareas del Plan de Operaciones y ordenes fragmentarias de la Supervision: [(tarea, origen)]."""
    plan = (documentos.get("plan_operaciones") or {}).get("tareas") or []
    frago = (documentos.get("supervision") or {}).get("ordenes_fragmentarias") or []
    return [(t, "plan") for t in plan] + [(t, "frago") for t in frago]


def _ref(esc: Escenario, turno: int) -> str:
    r = calendario.referencia(esc, turno)
    return r["hora_h"] or f"turno {turno}"


def cuadro(db: Session, esc: Escenario, bando: str, documentos: dict[str, dict]) -> list[dict]:
    """Renglones {clave, origen, objetivo, resultado, diferencia, estado, causa_sugerida, turno} del bando."""
    turno = esc.turno_actual
    filas = []
    ejec = {e.tarea_id: e for e in db.query(EjecucionTarea).filter(EjecucionTarea.escenario_id == esc.id,
                                                                  EjecucionTarea.bando == bando)}
    ordenes = {o.id: o for o in db.query(Orden).filter(Orden.escenario_id == esc.id)}
    # 1. tareas del plan y ordenes fragmentarias ya vencidas
    for t, origen in tareas_del_bando(documentos):
        if not t.get("turno") or t["turno"] > turno:
            continue
        objetivo = f"{tiem.texto_tarea(t)} ({_ref(esc, t['turno'])})"
        e = ejec.get(t["id"])
        fila = {"clave": f"t:{t['id']}", "origen": "Orden fragmentaria" if origen == "frago" else "Plan de Operaciones",
                "turno": t["turno"], "objetivo": objetivo, "resultado": "", "diferencia": "", "estado": "conforme",
                "causa_sugerida": ""}
        if e is None:
            fila.update(resultado="No se emitió la orden.", diferencia="La tarea no se ejecutó en su turno.",
                        estado="desvio", causa_sugerida="La tarea no se emitió desde la Orden de Operaciones.")
        elif e.estado == "rechazada":
            fila.update(resultado=f"Orden rechazada al emitirla: {e.motivo}", diferencia="La tarea no se ejecutó.",
                        estado="desvio", causa_sugerida=e.motivo)
        else:
            o = ordenes.get(e.orden_id)
            if o is None:
                fila.update(resultado="La orden fue reemplazada o cancelada.", diferencia="La unidad no cumplió la tarea "
                            "prevista.", estado="desvio", causa_sugerida="Se le dio otra orden a la unidad.")
            elif o.estado == "pendiente":
                fila.update(resultado=f"Orden emitida en el turno {e.turno}; se cumple al resolverse el turno.",
                            estado="en curso")
            elif o.estado == "rechazada":
                fila.update(resultado=f"Orden rechazada al resolverse: {o.resultado}", diferencia="La tarea no se cumplió.",
                            estado="desvio", causa_sugerida=o.resultado)
            else:
                fila.update(resultado=o.resultado or "Orden cumplida.", estado="conforme")
        filas.append(fila)
    # 2. objetivos del bando (cadena del TIEM): su estado y los plazos que vencen
    for o in db.query(Objetivo).filter(Objetivo.escenario_id == esc.id, Objetivo.bando == bando).order_by(Objetivo.id):
        nivel = {"ulterior": "Objetivo ulterior", "asignado": "Objetivo asignado"}.get(o.nivel, "Objetivo")
        fila = {"clave": f"o:{o.id}", "origen": nivel, "turno": o.turno_resuelto or turno,
                "objetivo": o.nombre + (f" (efecto: {o.efecto})" if o.efecto else ""), "resultado": "",
                "diferencia": "", "estado": "en curso", "causa_sugerida": ""}
        if o.estado == "cumplido":
            fila.update(resultado=f"Cumplido en el turno {o.turno_resuelto}.", estado="conforme")
        elif o.estado == "fallido":
            fila.update(resultado=f"Fallido en el turno {o.turno_resuelto}.", diferencia="No se logró el efecto deseado.",
                        estado="fallido")
        else:
            if o.tipo == "ocupar":
                fila["resultado"] = f"Zona mantenida {o.progreso} de {o.turnos_requeridos} turno(s) seguidos."
            else:
                fila["resultado"] = "Pendiente."
            if o.hasta_turno and o.tipo != "proteger" and o.hasta_turno - turno <= AVISO_PLAZO:
                fila.update(diferencia=f"Vence en el turno {o.hasta_turno} y todavía no se cumplió.", estado="desvio",
                            causa_sugerida="El ritmo de la operación no alcanza para el plazo.")
        filas.append(fila)
    # 3. unidades propias muy dañadas o perdidas
    for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == bando).order_by(Unidad.id):
        if u.estado == "destruida":
            filas.append({"clave": f"u:{u.id}", "origen": "Fuerzas propias", "turno": turno, "objetivo": u.nombre,
                          "resultado": "Destruida.", "diferencia": "Pérdida de medios: revisar la distribución del poder "
                          "combativo.", "estado": "fallido", "causa_sugerida": ""})
        elif u.estado == "activa" and u.fuerza < FUERZA_CRITICA and u.tipo != "base":
            filas.append({"clave": f"u:{u.id}", "origen": "Fuerzas propias", "turno": turno, "objetivo": u.nombre,
                          "resultado": f"Fuerza {u.fuerza:.0f} %.", "diferencia": "Por debajo del 50 %: capacidad "
                          "reducida.", "estado": "desvio", "causa_sugerida": ""})
    orden_estado = {"fallido": 0, "desvio": 1, "en curso": 2, "conforme": 3}
    filas.sort(key=lambda f: (orden_estado[f["estado"]], -f["turno"]))
    return filas


def parte(db: Session, esc: Escenario, bando: str) -> dict | None:
    """Parte del ultimo turno resuelto para el bando: ordenes cumplidas y rechazadas, objetivos y perdidas."""
    t = esc.turno_actual - 1
    if t < 1:
        return None
    propias = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == bando)}
    ordenes = [o for o in db.query(Orden).filter(Orden.escenario_id == esc.id, Orden.turno_emitida == t)
               if o.unidad_id in propias]
    eventos = db.query(Evento).filter(Evento.escenario_id == esc.id, Evento.turno == t, Evento.tipo == "objetivo",
                                      Evento.bando_destino == bando).all()
    perdidas = [u.nombre for u in propias.values() if u.estado == "destruida"]
    lineas = [f"Órdenes del turno {t}: {sum(1 for o in ordenes if o.estado == 'resuelta')} cumplida(s), "
              f"{sum(1 for o in ordenes if o.estado == 'rechazada')} rechazada(s)."]
    lineas += [e.descripcion for e in eventos]
    if perdidas:
        lineas.append(f"Unidades propias perdidas hasta ahora: {', '.join(perdidas)}.")
    return {"turno": t, "referencia": calendario.texto(calendario.referencia(esc, t)), "lineas": lineas}


def contar(filas: list[dict]) -> dict:
    return {e: sum(1 for f in filas if f["estado"] == e) for e in ESTADOS}

