"""Evaluacion del trabajo de Estado Mayor (TIEM) de cada bando.

Indicadores de 0 a 100, con el mismo formato que los indicadores doctrinales del informe (engine/aar.py):
  documentos   documentos del TIEM aprobados (1) o presentados (0,5), sobre los 13 de las fases I y II;
  forma        documentos redactados sin faltantes ni observaciones de forma del TIEM (mision en infinitivo y sin
               condiciones, dos F/A con su APA, COG propio y enemigo...);
  oportunidad  documentos de la Fase I presentados a mas tardar a la hora H;
  ejecucion    tareas del plan y ordenes fragmentarias vencidas que se emitieron como ordenes;
  supervision  desvios y fallidos del cuadro de supervision con su causa y su accion correctiva en el registro.
Un indicador sin datos no aplica y no cuenta. La nota automatica (1 a 20) es el promedio de los que aplican; si el
instructor califico documentos al revisarlos, su promedio es la nota del instructor y la nota final promedia ambas.
"""

import json

from sqlalchemy.orm import Session

from app.engine import supervision, tiem
from app.models.documento_tiem import DocumentoTiem, EjecucionTarea

FASE_1 = ("analisis_mision", "concepto", "guia", "formas_accion", "apreciacion_inteligencia", "apreciacion_operaciones",
          "apreciacion_defensa_aerea", "apreciacion_personal", "apreciacion_logistica", "apreciacion_ce", "decision")
EVALUABLES = FASE_1 + ("analisis_previo", "plan_operaciones")  # la supervision se lleva todo el ejercicio


def _ind(id_, nombre, valor, puntaje, criterio) -> dict:
    return {"id": id_, "nombre": nombre, "valor": valor,
            "puntaje": None if puntaje is None else max(0, min(100, round(puntaje))), "criterio": criterio}


def _nota(puntajes: list) -> float | None:
    return None if not puntajes else round(1 + 19 * (sum(puntajes) / len(puntajes)) / 100, 1)


def evaluar(db: Session, esc, bando: str) -> dict:
    docs = {d.tipo: d for d in db.query(DocumentoTiem).filter(DocumentoTiem.escenario_id == esc.id,
                                                             DocumentoTiem.bando == bando)}
    contenidos = {t: tiem.normalizar(t, json.loads(d.contenido_json)) for t, d in docs.items()}
    filas_doc = []
    for t in tiem.ORDEN:
        d = docs.get(t)
        rev = tiem.revisar(t, contenidos[t]) if d else {"faltan": [], "avisos": []}
        filas_doc.append({"tipo": t, "titulo": tiem.DOCUMENTOS[t].titulo, "paso": tiem.DOCUMENTOS[t].paso,
                          "estado": d.estado if d else "sin empezar", "presentado_turno": d.presentado_turno if d else None,
                          "revisado_turno": d.revisado_turno if d else None, "nota": d.nota if d else None,
                          "faltan": len(rev["faltan"]), "avisos": len(rev["avisos"]),
                          "observaciones": d.observaciones if d else ""})
    inds = []
    # 1. documentos
    aprobados = sum(1 for t in EVALUABLES if t in docs and docs[t].estado == "aprobado")
    presentados = sum(1 for t in EVALUABLES if t in docs and docs[t].estado == "presentado")
    inds.append(_ind("documentos", "Documentos del TIEM", f"{aprobados} aprobado(s) y {presentados} presentado(s) de "
                     f"{len(EVALUABLES)}", 100 * (aprobados + 0.5 * presentados) / len(EVALUABLES) if docs else None,
                     "Aprobados (1) y presentados sin revisar (0,5) sobre los 13 documentos de las fases I y II."))
    # 2. forma
    redactados = [t for t in EVALUABLES if t in docs]
    limpios = [t for t in redactados if not any(f["tipo"] == t and (f["faltan"] or f["avisos"]) for f in filas_doc)]
    inds.append(_ind("forma", "Forma según el TIEM", f"{len(limpios)} de {len(redactados)} documento(s) sin observaciones",
                     100 * len(limpios) / len(redactados) if redactados else None,
                     "Documentos sin faltantes ni observaciones de forma (misión en infinitivo y sin condiciones, F/A "
                     "con su APA, centros de gravedad propio y enemigo...)."))
    # 3. oportunidad
    fase1 = [docs[t] for t in FASE_1 if t in docs and docs[t].presentado_turno]
    if esc.turno_h and fase1:
        a_tiempo = sum(1 for d in fase1 if d.presentado_turno <= esc.turno_h)
        inds.append(_ind("oportunidad", "Oportunidad de la apreciación", f"{a_tiempo} de {len(fase1)} presentado(s) "
                         f"hasta la hora H (hora {esc.turno_h} del ejercicio)", 100 * a_tiempo / len(fase1),
                         "Documentos de la Fase I presentados a más tardar a la hora H."))
    else:
        inds.append(_ind("oportunidad", "Oportunidad de la apreciación", "sin hora H o sin documentos presentados", None,
                         "Documentos de la Fase I presentados a más tardar a la hora H."))
    # 4. ejecucion del plan
    tareas = [t for t, _ in supervision.tareas_del_bando(contenidos) if t.get("turno") and t["turno"] <= esc.turno_actual]
    ejec = {e.tarea_id: e for e in db.query(EjecucionTarea).filter(EjecucionTarea.escenario_id == esc.id,
                                                                  EjecucionTarea.bando == bando)}
    emitidas = sum(1 for t in tareas if t["id"] in ejec and ejec[t["id"]].estado == "emitida")
    inds.append(_ind("ejecucion", "Ejecución del plan", f"{emitidas} de {len(tareas)} tarea(s) vencida(s) emitida(s)",
                     100 * emitidas / len(tareas) if tareas else None,
                     "Tareas del Plan de Operaciones y órdenes fragmentarias vencidas que se emitieron como órdenes."))
    # 5. supervision
    cuadro = supervision.cuadro(db, esc, bando, contenidos)
    desvios = sum(1 for f in cuadro if f["estado"] in ("desvio", "fallido"))
    registro = (contenidos.get("supervision") or {}).get("registro") or []
    analizados = sum(1 for r in registro if r.get("causa") and r.get("accion"))
    inds.append(_ind("supervision", "Supervisión de la ejecución",
                     f"{desvios} desvío(s) o fallido(s); {analizados} con causa y acción correctiva",
                     100 * min(1.0, analizados / desvios) if desvios else (100 if analizados else None),
                     "Desvíos y fallidos del cuadro de supervisión registrados con su causa y su acción correctiva."))
    puntajes = [i["puntaje"] for i in inds if i["puntaje"] is not None]
    notas_instructor = [d.nota for d in docs.values() if d.nota]
    nota_auto = _nota(puntajes) if docs else None
    nota_instr = round(sum(notas_instructor) / len(notas_instructor), 1) if notas_instructor else None
    finales = [n for n in (nota_auto, nota_instr) if n is not None]
    return {"aplica": bool(docs), "indicadores": inds, "documentos": filas_doc,
            "nota_automatica": nota_auto, "nota_instructor": nota_instr,
            "nota": round(sum(finales) / len(finales), 1) if finales else None,
            "escala": "1 a 20: promedio de los indicadores que aplican y, si las hay, de las notas del instructor"}
