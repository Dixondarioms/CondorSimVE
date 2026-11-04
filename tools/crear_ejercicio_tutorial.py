"""Plantilla «Tutorial del Cóndor» (tutorial_condor): un ejercicio para que UN alumno solo aprenda a usar todo el
simulador paso a paso (acompaña al recorrido guiado de frontend/static/js/recorrido.js).

Toma de la plantilla teatro_ficticio (mapa ficticio) las fuerzas de tierra y aire de cada bando y les suma lo necesario
para practicar todo: una fragata, un submarino, un cazaminas, un helicóptero antisubmarino NH90, un avión de patrulla
marítima P-8A, cazas en alerta en tierra y un lanzador de misiles balísticos frente a la costa oeste de Capital Azul;
del lado Rojo, lo mínimo: sus fuerzas de tierra, un submarino y una corbeta en ese mar y un campo de minas en la entrada
de Puerto Albán; sin aviación (un dron y un lanzador de misiles balísticos los hacen aparecer los eventos automáticos).
Para que un alumno solo no pierda todo antes de aprender: el adversario automático es «prudente» y la doctrina azul
empieza con las armas contra aeronaves restringidas (solo identificados), porque hay vuelos civiles. El alumno
conduce el Azul y el adversario automático el Rojo.

Los EVENTOS AUTOMÁTICOS hacen de instructor: a cada hora le mandan al Azul la práctica que sigue y, a medida que avanza
(al entrar a un área, al derribar o hundir una unidad, al cumplir un objetivo), lo felicitan, le dan puntos o le
inyectan una situación nueva (un dron que entra, refuerzos rojos).

    backend\\venv\\Scripts\\python tools\\crear_ejercicio_tutorial.py           # escribe la plantilla
    backend\\venv\\Scripts\\python tools\\crear_ejercicio_tutorial.py --crear   # y crea el escenario en la base local
"""

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
CARPETA = RAIZ / "backend" / "data" / "plantillas_sistema"
SALIDA = CARPETA / "tutorial_condor.json"

AZUL = ["Base Aérea de Capital Azul", "Cazas azules", "Aviación de ataque azul", "Depósito logístico de Capital Azul",
        "Defensa antiaérea de Capital Azul", "Radar de vigilancia azul", "1.ª Brigada de Infantería azul",
        "Brigada Blindada azul", "Grupo de Artillería azul", "Escuadrón de Reconocimiento azul",
        "Batallón de Ingenieros azul", "Convoy logístico azul"]
# el Rojo, lo mínimo: sin aviación propia (la amenaza aérea la inyectan los eventos automáticos)
ROJO = ["Defensa antiaérea de Capital Roja", "Radar de vigilancia rojo",
        "1.ª Brigada de Infantería rojo", "Brigada Blindada rojo", "Grupo de Artillería rojo",
        "Escuadrón de Reconocimiento rojo"]
BASE_AZUL = "Base Aérea de Capital Azul"
# cambios a unidades de teatro_ficticio: la antiaérea de Capital Azul, con un sistema antimisil (S-300VM)
CAMBIOS = {"Defensa antiaérea de Capital Azul": {"modelo": "s300vm"}}
# lo que se suma: mar al oeste de Capital Azul (la costa queda a unos 8 km de la base aérea)
NUEVAS = [
    {"nombre": "Cazas de alerta azules", "bando": "azul", "clase": "caza", "modelo": "f16", "aeronaves": 2,
     "en_tierra": True, "base": BASE_AZUL},
    {"nombre": "Helicóptero antisubmarino NH90", "bando": "azul", "clase": "helicoptero_artillado", "modelo": "nh90",
     "aeronaves": 1, "en_tierra": True, "base": BASE_AZUL},
    {"nombre": "Patrulla marítima P-8A", "bando": "azul", "clase": "ataque", "modelo": "p8a", "aeronaves": 1,
     "en_tierra": True, "base": BASE_AZUL},
    {"nombre": "Fragata Independencia", "bando": "azul", "clase": "fragata", "modelo": "lupo", "lat": 10.62, "lon": -26.62},
    {"nombre": "Submarino Tiburón", "bando": "azul", "clase": "submarino", "modelo": "u209", "lat": 10.50, "lon": -26.80},
    {"nombre": "Cazaminas Centinela", "bando": "azul", "clase": "cazaminas", "lat": 10.95, "lon": -26.90},
    {"nombre": "Lanzador balístico azul", "bando": "azul", "clase": "lanzador_balistico", "lat": 9.65, "lon": -24.90},
    # rojo: con qué practicar la guerra antisubmarina y la salva de misiles (algo gastados: es un tutorial)
    {"nombre": "Submarino rojo", "bando": "rojo", "clase": "submarino", "modelo": "kilo636", "lat": 10.42, "lon": -27.10,
     "fuerza": 70, "municion": 50},
    {"nombre": "Corbeta roja", "bando": "rojo", "clase": "patrullero", "modelo": "molniya", "lat": 10.05, "lon": -27.30,
     "fuerza": 80, "municion": 50},
]
LANZADOR_ROJO = (9.75, -23.70)  # al norte del Cruce: a la vista de los cazas que patrullan el Área de patrulla Norte
CRUCE = (9.43, -23.86)  # entre las dos fuerzas de tierra, a medio camino
MINAS = (10.85, -26.72)  # campo rojo frente a Puerto Albán (el Azul no lo conoce: lo descubre el cazaminas)


def _rect(lat1, lon1, lat2, lon2):
    return [[lat1, lon1], [lat1, lon2], [lat2, lon2], [lat2, lon1]]


AREA_NORTE = _rect(10.05, -24.70, 9.70, -23.60)  # sobre el flanco norte de las fuerzas azules y el lanzador rojo
AREA_OESTE = _rect(10.55, -27.30, 10.30, -26.90)  # donde un pesquero vio un periscopio
NO_VUELO = _rect(10.85, -26.65, 10.25, -25.95)  # Capital Azul y su base
CANAL = _rect(10.90, -26.82, 10.80, -26.62)  # entrada de Puerto Albán (alrededor del campo de minas)
CRUCE_AREA = _rect(CRUCE[0] + 0.08, CRUCE[1] - 0.08, CRUCE[0] - 0.08, CRUCE[1] + 0.08)

# las prácticas, en orden (la descripción del ejercicio y el último paso del recorrido guiado dicen lo mismo)
PRACTICAS = [
    "Comunicaciones: lea los mensajes del director automático (le dicen qué hacer en cada momento) y conteste «Recibido».",
    "Doctrina: contra aeronaves, las armas están «restringidas» (solo identificados) porque hay vuelos civiles; déjelas así.",
    "Mover: lleve la 1.ª Brigada de Infantería azul al Cruce central (marque 2 puntos en el mapa) y mire su estela.",
    "Aviación: los Cazas azules están en tierra; ordéneles Patrullar el «Área de patrulla Norte» con la carga Aire-aire.",
    "Interceptar: cuando entre el dron enemigo, mírelo en SITUACIÓN → Cuadro radar y lance los Cazas de alerta azules con Interceptar.",
    "Atacar: con la artillería o los blindados, a la Brigada Blindada roja; siga el combate en Alertas y el daño por sistemas abajo.",
    "Guerra antisubmarina: el NH90 con Sonar de inmersión o el P-8A con Sonoboyas sobre el «Área de búsqueda Oeste»; después, Torpedo.",
    "Minas: lleve el Cazaminas Centinela a la entrada de Puerto Albán y, cuando aparezca el campo rojo, ordene Barrer minas.",
    "Salva de misiles: Lanzar misiles desde la Fragata Independencia contra la Corbeta roja; mire la defensa de punto.",
    "Misil balístico: mire su defensa antimisil ante los balísticos rojos; ubique el lanzador rojo con un avión y láncele el suyo.",
    "Áreas y zonas: mire la «Zona de no vuelo de Capital Azul» y dibuje un área propia.",
    "Ocupe el Cruce central y siga el puntaje en Objetivos; mire la pestaña TIEM.",
    "Al terminar, abra el Informe y mire la repetición.",
]

DESCRIPCION = (
    "Ejercicio para aprender a usar TODO el Cóndor, solo y paso a paso. Usted conduce el bando Azul; el Rojo lo conduce "
    "el adversario automático. El director crea el ejercicio, pone el reloj en marcha (10×; 1× si quiere ir con calma) y "
    "lo deja correr: los mensajes automáticos (Comunicaciones y Alertas) le van diciendo qué practicar. Antes, haga el "
    "recorrido guiado (Ayuda → Recorrido guiado paso a paso). Prácticas, en orden: "
    + " ".join(f"{i}) {p}" for i, p in enumerate(PRACTICAS, 1))
)


def _mensaje(texto):
    return {"tipo": "mensaje", "para": "azul", "texto": texto}


def _regla(rid, nombre, disparador, *acciones):
    return {"id": rid, "nombre": nombre, "activo": True, "repetir": False, "disparador": disparador,
            "acciones": list(acciones)}


def eventos() -> list:
    """El instructor automático: a cada hora la práctica que sigue y, según lo que pase, felicitaciones e inyecciones."""
    return [
        _regla("bienvenida", "Bienvenida", {"tipo": "hora", "hora": "08:00"}, _mensaje(
            "Director: bienvenido al Tutorial del Cóndor. Estos mensajes le dirán qué practicar. 1) Mire la Doctrina "
            "(FUERZAS): contra aeronaves, «restringido»: hay vuelos civiles y tirarles resta puntos. 2) Mueva la 1.ª Brigada de Infantería al Cruce "
            "central. 3) Ordene a los Cazas azules Patrullar el «Área de patrulla Norte» con la carga Aire-aire.")),
        _regla("dron", "Entra un dron enemigo", {"tipo": "entra_area", "area": AREA_NORTE, "bando": "azul"},
               {"tipo": "aparecer", "bando": "rojo", "clase": "dron_reconocimiento", "cantidad": 1,
                "nombre": "Dron de reconocimiento rojo", "lat": 10.60, "lon": -23.80},
               _mensaje("Director: su patrulla llegó al área. Inteligencia avisa que un dron enemigo entra desde el mar, "
                        "al norte, hacia sus fuerzas. Cuando aparezca (desconocido), mírelo en SITUACIÓN → Cuadro radar. "
                        "Seleccione los Cazas de alerta azules (en tierra), orden Interceptar, elija el contacto y "
                        "«Identificar y neutralizar».")),
        _regla("dron_caido", "Dron derribado", {"tipo": "destruida", "unidad": "Dron de reconocimiento rojo"},
               {"tipo": "puntos", "bando": "azul", "puntos": 5},
               _mensaje("Director: dron derribado, +5 puntos. Ahora ataque a la Brigada Blindada roja con la artillería "
                        "o los blindados (orden Atacar) y siga el combate en Alertas.")),
        _regla("cruce_llegada", "Llegada al Cruce", {"tipo": "entra_area", "area": CRUCE_AREA, "bando": "azul"},
               _mensaje("Director: llegó al Cruce central. Manténgase allí para ocuparlo; en Objetivos y puntaje verá el "
                        "avance. Seleccione una unidad que haya combatido y mire abajo el daño por sistemas.")),
        _regla("mar", "Guerra antisubmarina", {"tipo": "hora", "hora": "09:30"}, _mensaje(
            "Director: un pesquero vio un periscopio en el «Área de búsqueda Oeste» (en el mar, frente a Capital Azul). "
            "Seleccione el Helicóptero NH90 (en tierra), orden Sonar de inmersión, carga Antisubmarina, y marque un punto "
            "del área. O el P-8A con Sonoboyas. Al detectar el submarino rojo, ordene Torpedo.")),
        _regla("sub_hundido", "Submarino hundido", {"tipo": "destruida", "unidad": "Submarino rojo"},
               _mensaje("Director: submarino rojo hundido. Pruebe en su Submarino Tiburón la profundidad (abajo, en el "
                        "panel de la unidad): a profundidad solo lo oye el sonar.")),
        _regla("minas", "Minas en Puerto Albán", {"tipo": "hora", "hora": "10:30"}, _mensaje(
            "Director: se sospecha un campo de minas rojo en la entrada de Puerto Albán. No meta buques allí. Lleve el "
            "Cazaminas Centinela (orden Mover) hacia la entrada del puerto; cuando su sonar descubra el campo, ordene "
            "Barrer minas sobre él.")),
        _regla("canal", "Cazaminas en el canal", {"tipo": "entra_area", "area": CANAL, "unidad": "Cazaminas Centinela"},
               {"tipo": "puntos", "bando": "azul", "puntos": 5},
               _mensaje("Director: el cazaminas llegó a la entrada de Puerto Albán (+5). Si ya ve el campo en el mapa, "
                        "ordene Barrer minas con un clic sobre él; tarda unas horas en limpiarlo.")),
        _regla("misiles", "Salva de misiles", {"tipo": "hora", "hora": "11:30"}, _mensaje(
            "Director: hora de los misiles. Seleccione la Fragata Independencia, orden Lanzar misiles, blanco la Corbeta "
            "roja, 2 misiles. Si la corbeta responde, mire en Alertas cómo la defensa de punto de la fragata derriba los "
            "misiles que llegan.")),
        _regla("balistico", "Ataque balístico rojo", {"tipo": "hora", "hora": "12:00"},
               {"tipo": "aparecer", "bando": "rojo", "clase": "lanzador_balistico", "cantidad": 1,
                "nombre": "Lanzador balístico rojo", "lat": LANZADOR_ROJO[0], "lon": LANZADOR_ROJO[1]},
               {"tipo": "lanzar", "unidad": "Lanzador balístico rojo", "blanco": BASE_AZUL, "misiles": 2},
               _mensaje("Director: ¡alerta temprana! Dos misiles balísticos rojos van hacia la Base Aérea de Capital Azul. "
                        "Mire en Alertas cómo su S-300VM (Defensa antiaérea de Capital Azul) intenta derribarlos. Salieron "
                        "del este del Área de patrulla Norte: mande a patrullarla a sus cazas (si volvieron a cargar "
                        "combustible, otra vez) y, cuando el lanzador aparezca en el mapa, láncele su Lanzador balístico "
                        "azul (orden Lanzar misiles; puede hacer falta una segunda salva).")),
        _regla("contrabateria", "Lanzador rojo destruido", {"tipo": "destruida", "unidad": "Lanzador balístico rojo"},
               {"tipo": "puntos", "bando": "azul", "puntos": 15},
               _mensaje("Director: lanzador balístico rojo destruido (+15). Excelente contrabatería.")),
        _regla("corbeta", "Corbeta hundida", {"tipo": "destruida", "unidad": "Corbeta roja"},
               _mensaje("Director: Corbeta roja hundida. Muy bien.")),
        _regla("refuerzos", "Refuerzos rojos", {"tipo": "destruida", "unidad": "Brigada Blindada rojo"},
               {"tipo": "aparecer", "bando": "rojo", "clase": "blindado", "cantidad": 1, "nombre": "Reserva blindada roja",
                "lat": 9.45, "lon": -23.05},
               _mensaje("Director: cayó la Brigada Blindada roja. Inteligencia informa una reserva blindada roja que sale "
                        "de Puerto Varela hacia el Cruce: prepárese a recibirla.")),
        _regla("cruce", "Cruce ocupado", {"tipo": "objetivo", "objetivo": "Ocupar el Cruce central", "estado": "cumplido"},
               _mensaje("Director: Cruce central ocupado. Ahora mire la pestaña TIEM (el trabajo de Estado Mayor) y dibuje "
                        "en «Áreas y zonas» un área propia.")),
        _regla("fragata", "Fragata perdida", {"tipo": "destruida", "unidad": "Fragata Independencia"},
               _mensaje("Director: perdió la Fragata Independencia. Al terminar, mire en el Informe y en la repetición qué "
                        "pasó.")),
        _regla("cierre", "Cierre", {"tipo": "hora", "hora": "14:00"}, _mensaje(
            "Director: complete lo que le falte. Para terminar, abra el Informe: resumen, línea de tiempo y la repetición "
            "sobre el mapa. ¡Buen trabajo!")),
    ]


def zonas() -> list:
    return [
        {"bando": "azul", "tipo": "patrulla", "nombre": "Área de patrulla Norte", "puntos": AREA_NORTE, "armas": False},
        {"bando": "azul", "tipo": "patrulla", "nombre": "Área de búsqueda Oeste", "puntos": AREA_OESTE, "armas": False},
        # solo alerta: con «armas», las propias tirarían también a los vuelos civiles que la cruzan
        {"bando": "azul", "tipo": "no_vuelo", "nombre": "Zona de no vuelo de Capital Azul", "puntos": NO_VUELO,
         "armas": False},
    ]


def trafico() -> dict:
    """Pocos vuelos civiles, mercantes y pesqueros sobre el Azul y su mar (las aerovías, fijas, salen de la semilla)."""
    from app.engine import trafico as trafico_mod

    esc = SimpleNamespace(semilla=20261103, trafico_json=None)
    return trafico_mod.configurar(esc, aviones=3, mercantes=1, pesqueros=3, zona=[9.6, -27.5, 11.4, -24.6])


def plantilla() -> dict:
    base = json.loads((CARPETA / "teatro_ficticio.json").read_text(encoding="utf-8"))
    por_nombre = {u["nombre"]: u for u in base["unidades"]}
    unidades = [dict(por_nombre[n], **CAMBIOS.get(n, {})) for n in AZUL + ROJO]
    base_azul = por_nombre[BASE_AZUL]
    for u in NUEVAS:
        unidades.append({"lat": base_azul["lat"], "lon": base_azul["lon"], **u})
    objetivos = [
        {"bando": "azul", "tipo": "ocupar", "nombre": "Ocupar el Cruce central", "puntos": 30, "lat": CRUCE[0],
         "lon": CRUCE[1], "radio_km": 8.0, "turnos_requeridos": 1},
        {"bando": "azul", "tipo": "destruir", "nombre": "Batir la Brigada Blindada roja", "puntos": 20,
         "unidad": "Brigada Blindada rojo"},
        {"bando": "azul", "tipo": "destruir", "nombre": "Hundir el submarino rojo", "puntos": 20, "unidad": "Submarino rojo"},
        {"bando": "azul", "tipo": "destruir", "nombre": "Hundir la corbeta roja", "puntos": 15, "unidad": "Corbeta roja"},
        {"bando": "azul", "tipo": "proteger", "nombre": "Conservar la Base Aérea de Capital Azul", "puntos": 10,
         "unidad": BASE_AZUL, "hasta_turno": 8},
        {"bando": "azul", "tipo": "proteger", "nombre": "Conservar la Fragata Independencia", "puntos": 10,
         "unidad": "Fragata Independencia", "hasta_turno": 8},
        {"bando": "rojo", "tipo": "ocupar", "nombre": "Ocupar el Cruce central", "puntos": 40, "lat": CRUCE[0],
         "lon": CRUCE[1], "radio_km": 8.0, "turnos_requeridos": 1},
        {"bando": "rojo", "tipo": "destruir", "nombre": "Batir la 1.ª Brigada de Infantería azul", "puntos": 30,
         "unidad": "1.ª Brigada de Infantería azul"},
        {"bando": "rojo", "tipo": "destruir", "nombre": "Hundir la Fragata Independencia", "puntos": 20,
         "unidad": "Fragata Independencia"},
    ]
    return {
        "id": "tutorial_condor", "nombre": "Tutorial del Cóndor", "descripcion": DESCRIPCION,
        "clima": "despejado", "hora_inicio_min": 480, "nacion_azul": base.get("nacion_azul", "valdoria"),
        "nacion_rojo": base.get("nacion_rojo", "ostrania"), "ia_azul": False, "ia_rojo": True, "dia_noche": False,
        "ia_nivel": "prudente", "doctrina": {"azul": {"armas_aire": "restringido"}},
        "con_estado": False, "conduce_azul": "alumnos", "conduce_rojo": "alumnos", "turno_final": 8,
        "unidades": unidades, "objetivos": objetivos, "eventos_auto": eventos(), "zonas": zonas(),
        "trafico": trafico(), "minas": [{"bando": "rojo", "lat": MINAS[0], "lon": MINAS[1], "radio_km": 3.0}],
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
    from app.engine import plantillas

    plantillas.desde_dict(p)  # valida (eventos, zonas, minas) antes de escribir
    SALIDA.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(p['unidades'])} unidades, {len(p['objetivos'])} objetivos, {len(p['eventos_auto'])} eventos -> {SALIDA}")
    if args.crear:
        crear_escenario()


if __name__ == "__main__":
    main()
