"""Reparticiones del Estado Mayor de cada bando, segun el TIEM (Trabajo Integral de Estado Mayor).

Cada alumno de un bando ocupa una reparticion: el Comandante y el Jefe de Estado Mayor reunen todas las
funciones; las demas conducen solo las unidades de su area, como en un Estado Mayor de componente aereo:
A-1 Personal, A-2 Inteligencia, A-3 Operaciones, A-3 D/A Defensa Aerea, A-4 Logistica y C-E Comunicaciones y
Electronica. Todas comparten la vista del bando (misma niebla de guerra, misma red de mensajes, mismos graficos);
lo que cambia es que ordenes puede emitir cada una, asi varios alumnos trabajan a la vez sobre el mismo bando sin
pisarse y deben coordinar entre si.
"""

from dataclasses import dataclass

BANDOS = ("azul", "rojo")
FUNCIONES = ("superficie", "aereo", "caza", "despegar", "defensa_aerea", "reconocimiento", "logistica",
             "guerra_electronica", "listo")
POR_DEFECTO = "comandante"
GENERALES = ("comandante", "jem")  # reunen todas las funciones: no son "responsables" de una en particular

# Ids de los puestos anteriores al TIEM y la reparticion que los reemplaza (usuarios y ordenes viejas).
EQUIVALENCIAS = {"mando": "comandante", "inteligencia": "a2", "operaciones": "a3", "logistica": "a4",
                 "planificacion": "a3"}

# Clases que conduce cada area (ademas de las que se reconocen por sus atributos, ver funcion_de_orden).
_DEFENSA_AEREA = {"antiaerea", "antiaerea_portatil", "radar", "alerta_temprana"}
_GUERRA_ELECTRONICA = {"guerra_electronica", "avion_ge"}
_RECONOCIMIENTO = {"reconocimiento", "dron_reconocimiento"}


@dataclass(frozen=True)
class Puesto:
    id: str
    sigla: str
    nombre: str
    descripcion: str
    funciones: frozenset


PUESTOS: dict[str, Puesto] = {p.id: p for p in [
    Puesto("comandante", "CMDTE", "Comandante",
           "Decide y conduce el bando: reune las funciones de todas las reparticiones y confirma las ordenes (LISTO).",
           frozenset(FUNCIONES)),
    Puesto("jem", "JEM", "Jefe de Estado Mayor",
           "Coordina el trabajo de las reparticiones; reune sus funciones y confirma las ordenes (LISTO) por el "
           "comandante.", frozenset(FUNCIONES)),
    Puesto("a1", "A-1", "Personal",
           "Sigue los efectivos propios (dotacion, bajas, reemplazos y moral) y prepara la apreciacion de personal. "
           "No ordena unidades.", frozenset()),
    Puesto("a2", "A-2", "Inteligencia",
           "Sigue al enemigo (contactos, cuadro de radares, capacidades del ENO) y conduce el reconocimiento: "
           "unidades y drones de reconocimiento.", frozenset({"reconocimiento"})),
    Puesto("a3", "A-3", "Operaciones",
           "Conduce la maniobra: despegues, caza, ataque, helicopteros, drones armados, cisternas, fuerzas de "
           "superficie y lanzadores de misiles.", frozenset({"superficie", "aereo", "caza", "despegar"})),
    Puesto("a3da", "A-3 D/A", "Defensa Aerea",
           "Conduce la defensa aerea: radares, artilleria y misiles antiaereos, alerta temprana y la caza de "
           "intercepcion con sus despegues.", frozenset({"defensa_aerea", "caza", "despegar"})),
    Puesto("a4", "A-4", "Logistica",
           "Conduce el abastecimiento: convoyes y depositos, e ingenieros (puentes y vados).",
           frozenset({"logistica"})),
    Puesto("ce", "C-E", "Comunicaciones y Electronica",
           "Conduce la guerra electronica: escucha e interferencia desde tierra y aviones de guerra electronica.",
           frozenset({"guerra_electronica"})),
]}


def normalizar(puesto: str | None) -> str:
    """Id vigente de un puesto: traduce los ids anteriores al TIEM; vacio o desconocido = Comandante."""
    p = EQUIVALENCIAS.get(puesto or "", puesto or "")
    return p if p in PUESTOS else POR_DEFECTO


def obtener(puesto: str | None) -> Puesto:
    """Reparticion por id; vacio o desconocido equivale al Comandante (compatibilidad con usuarios previos)."""
    return PUESTOS[normalizar(puesto)]


def funcion_de_orden(unidad, tipo_orden: str | None, clase) -> str:
    """Funcion (y por lo tanto reparticion responsable) de una orden sobre una unidad.

    Sin tipo de orden devuelve la funcion de la unidad en general. Los despegues desde las bases son de A-3 o
    A-3 D/A; radares y antiaereas, de A-3 D/A; guerra electronica, de C-E; reconocimiento, de A-2; convoyes e
    ingenieros, de A-4; la caza, de A-3 o A-3 D/A; el resto del aire, tierra y mar, de A-3."""
    if tipo_orden == "despegar" or unidad.tipo == "base":
        return "despegar"
    cid = getattr(clase, "id", "") or getattr(unidad, "clase", "") or ""
    if cid in _DEFENSA_AEREA or getattr(clase, "defensa_aerea", False) or (clase.emisor and clase.solo_aereo):
        return "defensa_aerea"
    if cid in _GUERRA_ELECTRONICA or clase.interferencia_km > 0:
        return "guerra_electronica"
    if cid in _RECONOCIMIENTO:
        return "reconocimiento"
    if tipo_orden == "construir" or clase.construye or (clase.carga_max > 0 and unidad.tipo != "aerea"):
        return "logistica"
    if cid == "caza":
        return "caza"
    if unidad.tipo == "aerea":
        return "aereo"
    return "superficie"


def puede(puesto: str | None, funcion: str) -> bool:
    return funcion in obtener(puesto).funciones


def responsables(funcion: str) -> list[Puesto]:
    """Reparticiones especializadas (sin Comandante ni JEM) que tienen esa funcion."""
    return [p for p in PUESTOS.values() if p.id not in GENERALES and funcion in p.funciones]


def especializados() -> list[Puesto]:
    """Reparticiones que conducen unidades por su cuenta (para el desglose del AAR)."""
    return [p for p in PUESTOS.values() if p.id not in GENERALES and p.funciones]


def como_dict(p: Puesto) -> dict:
    return {"id": p.id, "sigla": p.sigla, "nombre": p.nombre, "descripcion": p.descripcion,
            "funciones": sorted(p.funciones)}


def firma(usuario) -> dict:
    """Autor de una orden o mision: id del usuario y reparticion que ocupa al emitirla (los instructores no tienen
    puesto dentro de un bando). Se pasa tal cual al constructor de Orden / Mision."""
    return {"autor_id": usuario.id, "autor_puesto": normalizar(usuario.puesto) if usuario.rol in BANDOS else None}
