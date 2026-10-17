"""Comparar ejercicios: calificacion e indicadores doctrinales de cada bando y evolucion de cada alumno a lo largo de
varios escenarios (para seguir el progreso de una seccion entre un ejercicio y otro)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import auth
from app.db import get_db
from app.engine import aar
from app.models.usuario import Usuario

router = APIRouter(prefix="/api/evaluacion", tags=["evaluacion"])
MAX_ESCENARIOS = 12


@router.get("/comparar")
def comparar(
    ids: str = Query(description="ids de escenario separados por comas, en el orden en que se quieren ver"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.requiere_roles("instructor", "observador")),
):
    try:
        lista = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids debe ser una lista de numeros separados por comas") from None
    if not 1 <= len(lista) <= MAX_ESCENARIOS:
        raise HTTPException(status_code=400, detail=f"Elija entre 1 y {MAX_ESCENARIOS} ejercicios")
    ejercicios = []
    alumnos: dict[str, list] = {}
    nombres: dict[str, str] = {}
    for escenario_id in dict.fromkeys(lista):
        esc = auth.escenario_accesible(db, escenario_id, usuario)
        r = aar.construir_rubrica(db, esc)
        bandos = {}
        for b, x in r["bandos"].items():
            d = x.get("doctrina") or {}
            for i in d.get("indicadores", []):
                nombres.setdefault(i["id"], i["nombre"])
            bandos[b] = {
                "nota": d.get("nota"), "promedio": d.get("promedio"),
                "indicadores": {i["id"]: i["puntaje"] for i in d.get("indicadores", [])},
                "ordenes": x["ordenes"]["emitidas"], "tasa_rechazo": x["ordenes"]["tasa_rechazo"],
            }
        ejercicios.append({"id": esc.id, "nombre": esc.nombre, "estado": esc.estado,
                           "turnos": r["escenario"]["turnos_resueltos"], "bandos": bandos})
        for a in r["alumnos"]:
            alumnos.setdefault(a["username"], []).append({
                "escenario_id": esc.id, "escenario": esc.nombre, "bando": a["bando"], "puesto": a["sigla"],
                "ordenes": a["ordenes"]["emitidas"], "rechazadas": a["ordenes"]["rechazadas"],
                "turnos_activos": a["turnos_activos"]["cantidad"], "turnos_pasivos": a["turnos_pasivos"]["cantidad"],
                "misiones": a["misiones"]["planificadas"],
                "nota_bando": bandos.get(a["bando"], {}).get("nota"),
            })
    return {"ejercicios": ejercicios, "indicadores": nombres,
            "alumnos": [{"username": u, "ejercicios": filas} for u, filas in sorted(alumnos.items())]}
