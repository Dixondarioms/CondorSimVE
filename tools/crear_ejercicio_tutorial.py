"""Plantilla «Tutorial del Cóndor» (tutorial_condor): un ejercicio corto y chico sobre el mapa ficticio para aprender a
usar la pantalla paso a paso (acompaña al recorrido guiado de frontend/static/js/recorrido.js).

Toma de la plantilla teatro_ficticio unas pocas unidades por bando: el alumno conduce el Azul y el adversario automático
el Rojo, así una sola persona puede practicar. Las fuerzas de tierra están a unos 90 km: hay tiempo para mover, despegar
una patrulla y ver aparecer al enemigo (desconocido → clasificado → identificado) antes del combate.

    backend\\venv\\Scripts\\python tools\\crear_ejercicio_tutorial.py           # escribe la plantilla
    backend\\venv\\Scripts\\python tools\\crear_ejercicio_tutorial.py --crear   # y crea el escenario en la base local
"""

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
CARPETA = RAIZ / "backend" / "data" / "plantillas_sistema"
SALIDA = CARPETA / "tutorial_condor.json"

AZUL = ["Base Aérea de Capital Azul", "Cazas azules", "Aviación de ataque azul", "Depósito logístico de Capital Azul",
        "Defensa antiaérea de Capital Azul", "Radar de vigilancia azul", "1.ª Brigada de Infantería azul",
        "Brigada Blindada azul", "Grupo de Artillería azul", "Escuadrón de Reconocimiento azul",
        "Batallón de Ingenieros azul", "Convoy logístico azul"]
ROJO = ["Base Aérea de Capital Roja", "Cazas rojos", "Defensa antiaérea de Capital Roja", "Radar de vigilancia rojo",
        "1.ª Brigada de Infantería rojo", "Brigada Blindada rojo", "Grupo de Artillería rojo",
        "Escuadrón de Reconocimiento rojo"]
CRUCE = (9.43, -23.86)  # entre las dos fuerzas de tierra, a medio camino

DESCRIPCION = (
    "Ejercicio corto para aprender a usar el Cóndor, paso a paso. Usted conduce el bando Azul; el Rojo lo conduce el "
    "adversario automático, así puede practicar solo. Antes de empezar haga el recorrido guiado (botón Ayuda → Recorrido "
    "guiado). Práctica sugerida: 1) seleccione la 1.ª Brigada de Infantería azul y ordénele Mover hacia el Cruce central "
    "(marque 2 puntos en el mapa); 2) despegue los Cazas azules (Aviación) y ordéneles Patrullar sobre la brigada; "
    "3) adelante el Escuadrón de Reconocimiento y mire en SITUACIÓN → Cuadro radar cómo el enemigo pasa de desconocido "
    "a identificado (círculo amarillo en el mapa); 4) ordene Atacar con la artillería o los blindados y siga el combate "
    "en Alertas; 5) ocupe el Cruce central; 6) al terminar, abra el Informe y mire la repetición."
)


def plantilla() -> dict:
    base = json.loads((CARPETA / "teatro_ficticio.json").read_text(encoding="utf-8"))
    por_nombre = {u["nombre"]: u for u in base["unidades"]}
    unidades = [dict(por_nombre[n]) for n in AZUL + ROJO]
    objetivos = [
        {"bando": "azul", "tipo": "ocupar", "nombre": "Ocupar el Cruce central", "puntos": 40, "lat": CRUCE[0],
         "lon": CRUCE[1], "radio_km": 8.0, "turnos_requeridos": 1},
        {"bando": "azul", "tipo": "destruir", "nombre": "Batir la Brigada Blindada roja", "puntos": 30,
         "unidad": "Brigada Blindada rojo"},
        {"bando": "azul", "tipo": "proteger", "nombre": "Conservar la Base Aérea de Capital Azul", "puntos": 15,
         "unidad": "Base Aérea de Capital Azul", "hasta_turno": 6},
        {"bando": "rojo", "tipo": "ocupar", "nombre": "Ocupar el Cruce central", "puntos": 40, "lat": CRUCE[0],
         "lon": CRUCE[1], "radio_km": 8.0, "turnos_requeridos": 1},
        {"bando": "rojo", "tipo": "destruir", "nombre": "Batir la 1.ª Brigada de Infantería azul", "puntos": 30,
         "unidad": "1.ª Brigada de Infantería azul"},
    ]
    return {
        "id": "tutorial_condor", "nombre": "Tutorial del Cóndor", "descripcion": DESCRIPCION,
        "clima": "despejado", "hora_inicio_min": 480, "nacion_azul": base.get("nacion_azul", "valdoria"),
        "nacion_rojo": base.get("nacion_rojo", "ostrania"), "ia_azul": False, "ia_rojo": True, "dia_noche": False,
        "con_estado": False, "conduce_azul": "alumnos", "conduce_rojo": "alumnos", "turno_final": 6,
        "unidades": unidades, "objetivos": objetivos,
    }


def crear_escenario():
    from app.db import SessionLocal, init_db
    from app.engine import plantillas

    init_db()
    plantillas.PLANTILLAS.pop("tutorial_condor", None)
    plantillas._cargar_sistema()
    with SessionLocal() as db:
        esc = plantillas.crear_desde_plantilla(db, "tutorial_condor")
        db.commit()
        print(f"Escenario {esc.id} creado: {esc.nombre}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--crear", action="store_true", help="crear el escenario en la base de datos local")
    args = ap.parse_args()
    p = plantilla()
    SALIDA.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(p['unidades'])} unidades, {len(p['objetivos'])} objetivos -> {SALIDA}")
    if args.crear:
        crear_escenario()


if __name__ == "__main__":
    main()
