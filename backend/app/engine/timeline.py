"""Linea de tiempo del informe posterior: cruza la logistica (caidas abruptas de combustible y
municion) con los eventos cineticos (combates) en una estructura pensada para dibujar un
diagrama interactivo: ejes, una serie compacta por unidad, eventos ordenados y correlaciones.

Forma de la respuesta:
{
  "escenario": {...}, "ejes": {"turnos": [0..N], "hora_inicio_min": 360, "umbrales": {...}},
  "series":   [{"unidad_id", "nombre", "bando", "clase", "turnos": [...], "combustible": [...],
                "municion": [...], "fuerza": [...], "estado": [...]}],
  "eventos":  [{"id", "tipo": "combate" | "logistico" | "evento", "subtipo", "turno", "orden", ...}],
  "correlaciones": [{"tipo", "turno", "unidad_id", "logistico": id, "combate": id, "detalle": ...}],
  "resumen":  {...}
}
"""

import json
from collections import OrderedDict

from sqlalchemy.orm import Session

from app.models.aar import Combate, Instantanea, RegistroLogistico
from app.models.escenario import Escenario
from app.models.evento import Evento

UMBRAL_CAIDA = 30.0  # puntos porcentuales perdidos en un turno = caida abrupta
UMBRAL_CRITICO = 25.0  # nivel por debajo del cual la unidad esta al limite


def _series(instantaneas: list) -> list[dict]:
    por_unidad: "OrderedDict[int, dict]" = OrderedDict()
    for inst in instantaneas:
        for u in json.loads(inst.datos_json)["unidades"]:
            s = por_unidad.setdefault(u["id"], {
                "unidad_id": u["id"], "nombre": u["nombre"], "bando": u["bando"], "clase": u.get("clase") or u["tipo"],
                "turnos": [], "combustible": [], "municion": [], "fuerza": [], "estado": [],
            })
            s["turnos"].append(inst.turno)
            s["combustible"].append(round(u["combustible"], 1))
            s["municion"].append(round(u["municion"], 1))
            s["fuerza"].append(round(u["fuerza"], 1))
            s["estado"].append(u["estado"])
    return list(por_unidad.values())


def _eventos_logisticos(filas: list[RegistroLogistico]) -> list[dict]:
    """Agrupa por (turno, unidad, variable) y conserva solo lo relevante: caidas abruptas, niveles
    criticos y reabastecimientos grandes. Los ajustes manuales del instructor van aparte: son una
    intervencion, no una consecuencia del ejercicio, y no deben mezclarse con el gasto real."""
    grupos: "OrderedDict[tuple, list]" = OrderedDict()
    for f in filas:
        grupos.setdefault((f.turno, f.unidad_id, f.variable, f.causa == "ajuste"), []).append(f)
    eventos = []
    for (turno, unidad_id, variable, es_ajuste), fs in grupos.items():
        inicial, final = fs[0].antes, fs[-1].despues
        neto = round(final - inicial, 2)
        if es_ajuste:
            subtipo = "ajuste_manual"
        elif neto <= -UMBRAL_CAIDA:
            subtipo = "caida_abrupta"
        elif final < UMBRAL_CRITICO <= inicial:
            subtipo = "nivel_critico"
        elif neto >= UMBRAL_CAIDA:
            subtipo = "reabastecimiento"
        else:
            continue
        eventos.append({
            "id": f"l{turno}-{unidad_id}-{variable}" + ("-aj" if es_ajuste else ""), "tipo": "logistico",
            "subtipo": subtipo, "turno": turno,
            "unidad_id": unidad_id, "unidad": fs[0].unidad_nombre, "bando": fs[0].bando, "variable": variable,
            "antes": round(inicial, 1), "despues": round(final, 1), "delta": neto,
            "causas": list(OrderedDict.fromkeys(f.causa for f in fs)),
            "orden_ids": [f.orden_id for f in fs if f.orden_id is not None],
        })
    return eventos


def construir_timeline(db: Session, escenario: Escenario) -> dict:
    instantaneas = (
        db.query(Instantanea).filter(Instantanea.escenario_id == escenario.id).order_by(Instantanea.turno).all()
    )
    combates = db.query(Combate).filter(Combate.escenario_id == escenario.id).order_by(Combate.id).all()
    filas = (
        db.query(RegistroLogistico).filter(RegistroLogistico.escenario_id == escenario.id)
        .order_by(RegistroLogistico.id).all()
    )
    sucesos = db.query(Evento).filter(Evento.escenario_id == escenario.id).order_by(Evento.id).all()

    series = _series(instantaneas)
    por_turno_unidad = {(t, s["unidad_id"]): i for s in series for i, t in enumerate(s["turnos"])}
    serie_de = {s["unidad_id"]: s for s in series}

    eventos: list[dict] = []
    combate_de_orden: dict[int, str] = {}
    for c in combates:
        cid = f"c{c.id}"
        if c.orden_id is not None:
            combate_de_orden[c.orden_id] = cid
        eventos.append({
            "id": cid, "tipo": "combate", "subtipo": "ataque", "turno": c.turno, "orden_id": c.orden_id,
            "atacante_id": c.atacante_id, "defensor_id": c.defensor_id, "atacante": c.atacante_nombre,
            "defensor": c.defensor_nombre, "atacante_bando": c.atacante_bando, "defensor_bando": c.defensor_bando,
            "ratio": round(c.ratio, 3), "perdida_atacante": round(c.perdida_atacante, 1),
            "perdida_defensor": round(c.perdida_defensor, 1), "terreno": c.terreno,
            "efectos": [e for e in c.efectos.split("; ") if e], "lat": c.lat, "lon": c.lon,
        })
    logisticos = _eventos_logisticos(filas)
    eventos.extend(logisticos)
    for e in sucesos:
        if e.tipo in ("clima", "logistica", "ajuste", "general"):
            eventos.append({
                "id": f"e{e.id}", "tipo": "evento", "subtipo": "perdida" if e.tipo == "logistica" else e.tipo,
                "turno": e.turno, "texto": e.descripcion, "bando_destino": e.bando_destino,
            })
    prioridad = {"evento": 0, "logistico": 1, "combate": 2}
    eventos.sort(key=lambda x: (x["turno"], prioridad[x["tipo"]], x["id"]))

    # ---- correlaciones logistica <-> combate ----
    combates_por_turno_unidad: dict[tuple, list[str]] = {}
    for c in combates:
        for uid in (c.atacante_id, c.defensor_id):
            combates_por_turno_unidad.setdefault((c.turno, uid), []).append(f"c{c.id}")
    correlaciones = []
    for l in logisticos:
        # 1) el gasto de municion sale directamente de un ataque
        vinculados = [combate_de_orden[o] for o in l["orden_ids"] if o in combate_de_orden]
        for cid in vinculados:
            correlaciones.append({
                "tipo": "consumo_en_combate", "turno": l["turno"], "unidad_id": l["unidad_id"],
                "logistico": l["id"], "combate": cid,
                "detalle": f"{l['variable']} {l['antes']:.0f}% -> {l['despues']:.0f}%",
            })
        # 2) la caida ocurre en un turno en que la unidad estuvo en combate, aunque la causa sea otra
        if not vinculados and l["subtipo"] not in ("reabastecimiento", "ajuste_manual"):
            for cid in combates_por_turno_unidad.get((l["turno"], l["unidad_id"]), []):
                correlaciones.append({
                    "tipo": "coincide_con_combate", "turno": l["turno"], "unidad_id": l["unidad_id"],
                    "logistico": l["id"], "combate": cid,
                    "detalle": f"{l['variable']} {l['antes']:.0f}% -> {l['despues']:.0f}% ({', '.join(l['causas'])})",
                })
    # 3) la unidad llego a combatir con la logistica ya al limite (estado al cierre del turno anterior)
    for c in combates:
        for uid, papel in ((c.atacante_id, "atacante"), (c.defensor_id, "defensor")):
            i = por_turno_unidad.get((c.turno - 1, uid))
            if i is None:
                continue
            s = serie_de[uid]
            bajo = [v for v in ("combustible", "municion") if s[v][i] < UMBRAL_CRITICO]
            if bajo:
                correlaciones.append({
                    "tipo": "combate_con_logistica_baja", "turno": c.turno, "unidad_id": uid, "combate": f"c{c.id}",
                    "logistico": None,
                    "detalle": f"{papel} con " + ", ".join(f"{v} {s[v][i]:.0f}%" for v in bajo) + " al iniciar el turno",
                })

    resumen = {
        "combates": len(combates),
        "caidas_abruptas": sum(1 for l in logisticos if l["subtipo"] == "caida_abrupta"),
        "niveles_criticos": sum(1 for l in logisticos if l["subtipo"] == "nivel_critico"),
        "reabastecimientos": sum(1 for l in logisticos if l["subtipo"] == "reabastecimiento"),
        "ajustes_manuales": sum(1 for l in logisticos if l["subtipo"] == "ajuste_manual"),
        "correlaciones": len(correlaciones),
        "por_bando": {
            b: {
                "combates_iniciados": sum(1 for c in combates if c.atacante_bando == b),
                "caidas_abruptas": sum(1 for l in logisticos if l["subtipo"] == "caida_abrupta" and l["bando"] == b),
            }
            for b in ("azul", "rojo")
        },
    }
    return {
        "escenario": {
            "id": escenario.id, "nombre": escenario.nombre, "estado": escenario.estado,
            "turno_actual": escenario.turno_actual, "hora_inicio_min": escenario.hora_inicio_min,
        },
        "ejes": {
            "turnos": [i.turno for i in instantaneas], "hora_inicio_min": escenario.hora_inicio_min,
            "umbrales": {"caida_abrupta": UMBRAL_CAIDA, "nivel_critico": UMBRAL_CRITICO},
        },
        "series": series,
        "eventos": eventos,
        "correlaciones": correlaciones,
        "resumen": resumen,
    }
