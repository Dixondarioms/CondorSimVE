"""Ejercicio simulado de radares y relieve: los dos bandos los conduce el simulador y los turnos se resuelven solos.

Crea en la base del servidor el escenario "Radares y relieve: País Azul contra País Rojo (ejercicio simulado)"
sobre el mapa ficticio (con su relieve real de cordilleras y sierras), a partir de la plantilla del mapa ficticio
mas tres radares por bando ubicados para que se vea como el relieve recorta su alcance:

  Azul: llano occidental (308 m, la cordillera le tapa el este), en un valle (2 178 m, encerrado) y en la cumbre
        mas alta (5 150 m: ve lejos a cota media pero casi nada a baja cota bajo sus laderas).
  Rojo: en la llanura (115 m, casi un circulo completo), detras de la sierra oriental (197 m) y en el macizo (926 m).

mas drones armados que vuelan rasantes (para esconderse detras de las montanas), drones de reconocimiento, un
avion de alerta temprana del Rojo (radar en el aire: ve por encima del relieve) y guerra electronica del Azul.
El adversario automatico conduce ambos bandos y cada turno se resuelve solo al vencer el plazo de decision
(--segundos, 30 por omision). El escenario se asigna a las cuentas azules (azul.*) y rojas (rojo.*) que existan.

    backend\\venv\\Scripts\\python tools/crear_ejercicio_radares.py [--segundos 30] [--nivel normal]
"""

import argparse
import dataclasses
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ / "backend")
sys.path.insert(0, str(RAIZ / "backend"))

from app.db import SessionLocal, init_db  # noqa: E402
from app.engine import clock, plantillas, pmo  # noqa: E402
from app.models.asignacion import Asignacion  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

PLANTILLA = "teatro_ficticio"
NOMBRE = "Radares y relieve: País Azul contra País Rojo (ejercicio simulado)"
BASE_AZUL = "Base Aérea de Capital Azul"
BASE_ROJA = "Base Aérea de Capital Roja"
RENOMBRAR = {  # los radares de la plantilla, con un nombre que diga donde estan
    "Radar de vigilancia azul": "Radar azul del llano occidental",
    "Radar de vigilancia rojo": "Radar rojo del macizo",
}
EXTRA = [
    dict(nombre="Radar azul del valle", bando="azul", clase="radar", lat=9.30, lon=-25.90),
    dict(nombre="Radar azul de la cumbre", bando="azul", clase="radar", lat=10.24, lon=-25.26),
    dict(nombre="Radar rojo de la llanura", bando="rojo", clase="radar", lat=8.70, lon=-23.20),
    dict(nombre="Radar rojo tras la sierra", bando="rojo", clase="radar", lat=9.30, lon=-21.50),
    dict(nombre="Compañía de Guerra Electrónica azul", bando="azul", clase="guerra_electronica", lat=9.47, lon=-24.18),
    dict(nombre="Drones armados azules", bando="azul", clase="dron_ataque", modelo="uav_armado", aeronaves=2,
         en_tierra=True, base=BASE_AZUL, perfil_vuelo="rasante"),
    dict(nombre="Drones de reconocimiento azules", bando="azul", clase="dron_reconocimiento", modelo="uav_reco",
         aeronaves=2, en_tierra=True, base=BASE_AZUL),
    dict(nombre="Drones armados rojos", bando="rojo", clase="dron_ataque", modelo="uav_armado", aeronaves=2,
         en_tierra=True, base=BASE_ROJA, perfil_vuelo="rasante"),
    dict(nombre="Alerta temprana roja", bando="rojo", clase="alerta_temprana", modelo="e2d", aeronaves=1,
         en_tierra=True, base=BASE_ROJA),
]


def crear(segundos: int, nivel: str):
    base = plantillas.obtener(PLANTILLA)
    pos = {u.nombre: u for u in base.unidades}
    unidades = [dataclasses.replace(u, nombre=RENOMBRAR.get(u.nombre, u.nombre)) for u in base.unidades]
    for e in EXTRA:
        b = pos.get(e.get("base", ""))
        lugar = {"lat": b.lat, "lon": b.lon} if b else {}
        unidades.append(plantillas.UnidadPlantilla(**{**lugar, **e}))
    objetivos = [dataclasses.replace(o, unidad=RENOMBRAR.get(o.unidad, o.unidad)) for o in base.objetivos]
    sim = dataclasses.replace(base, id="ejercicio_radares", nombre=NOMBRE, unidades=tuple(unidades),
                              objetivos=tuple(objetivos), ia_azul=True, ia_rojo=True)
    plantillas.PLANTILLAS[sim.id] = sim  # solo en este proceso: no queda como plantilla del simulador
    init_db()
    with SessionLocal() as db:
        try:
            esc = plantillas.crear_desde_plantilla(db, sim.id)
        finally:
            plantillas.PLANTILLAS.pop(sim.id, None)
        esc.ia_nivel = nivel
        pmo.generar(db, esc, ("azul", "rojo"), sobrescribir=True, calendario_auto=True, cadena=True)
        esc.limite_decision_seg = segundos
        clock.programar_limite(esc)  # desde ahora, cada turno se resuelve solo al vencer el plazo
        asignados = []
        for u in db.query(Usuario).filter(Usuario.username.like("azul.%") | Usuario.username.like("rojo.%")):
            if u.rol in ("azul", "rojo"):
                db.add(Asignacion(usuario_id=u.id, escenario_id=esc.id))
                asignados.append(u.username)
        db.commit()
        print(f"Escenario {esc.id}: {esc.nombre}")
        print(f"  {len(unidades)} unidades; los dos bandos los conduce el simulador (nivel {nivel}); un turno cada {segundos} s")
        print(f"  asignado a: {', '.join(sorted(asignados)) or 'ninguna cuenta de alumno'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segundos", type=int, default=30, help="plazo de decision de cada turno (se resuelve solo)")
    ap.add_argument("--nivel", choices=("prudente", "normal", "agresivo"), default="normal")
    args = ap.parse_args()
    crear(max(10, args.segundos), args.nivel)


if __name__ == "__main__":
    main()
