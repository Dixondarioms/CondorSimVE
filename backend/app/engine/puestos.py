"""Puestos por funcion dentro de cada bando (estado mayor de aula).

Cada alumno de un bando ocupa un puesto: el Estado Mayor completo (todas las funciones) o una
celula especializada, como en un centro de operaciones: Inteligencia (A2), Operaciones en curso
(A3), Logistica (A4) y Planificacion (A5). Todos los puestos comparten la vista del bando (misma
niebla de guerra, misma red de mensajes, mismos graficos); lo que cambia es que ordenes puede
emitir cada uno, asi varios alumnos trabajan a la vez sobre el mismo bando sin pisarse.
"""

from dataclasses import dataclass

BANDOS = ("azul", "rojo")
FUNCIONES = ("superficie", "aereo", "despegar", "logistica", "listo")
POR_DEFECTO = "mando"


@dataclass(frozen=True)
class Puesto:
    id: str
    sigla: str
    nombre: str
    descripcion: str
    funciones: frozenset


PUESTOS: dict[str, Puesto] = {p.id: p for p in [
    Puesto("mando", "EM", "Estado Mayor",
           "Conduce todo el bando: reune las funciones de los demas puestos.", frozenset(FUNCIONES)),
    Puesto("inteligencia", "A2", "Inteligencia",
           "Sigue la situacion enemiga: contactos, graficos de blancos y mensajes. No emite ordenes.",
           frozenset()),
    Puesto("operaciones", "A3", "Operaciones en curso",
           "Conduce las aeronaves: despegue desde la pista, rutas, patrullas, ataques y aterrizajes.",
           frozenset({"aereo"})),
    Puesto("logistica", "A4", "Logistica",
           "Conduce los convoyes de abastecimiento y a los ingenieros (puentes y vados).",
           frozenset({"logistica"})),
    Puesto("planificacion", "A5", "Planificacion",
           "Ordena a las unidades terrestres y navales, envia los grupos de caza desde las bases y "
           "confirma las ordenes del bando (LISTO).",
           frozenset({"superficie", "despegar", "listo"})),
]}


def obtener(puesto: str | None) -> Puesto:
    """Puesto por id; vacio o desconocido equivale al Estado Mayor (compatibilidad con usuarios previos)."""
    return PUESTOS.get(puesto or "", PUESTOS[POR_DEFECTO])


def funcion_de_orden(unidad, tipo_orden: str | None, clase) -> str:
    """Funcion (y por lo tanto puesto responsable) de una orden sobre una unidad.

    Sin tipo de orden devuelve la funcion de la unidad en general. Las bases (despegues) y los
    grupos de caza que se envian desde ellas son de Planificacion; las aeronaves ya creadas, de
    Operaciones; ingenieros y convoyes, de Logistica; el resto de tierra y mar, de Planificacion."""
    if tipo_orden == "despegar" or unidad.tipo == "base":
        return "despegar"
    if tipo_orden == "construir" or clase.construye or clase.carga_max > 0:
        return "logistica"
    if unidad.tipo == "aerea":
        return "aereo"
    return "superficie"


def puede(puesto: str | None, funcion: str) -> bool:
    return funcion in obtener(puesto).funciones


def responsables(funcion: str) -> list[Puesto]:
    """Puestos especializados (sin el Estado Mayor) que tienen esa funcion."""
    return [p for p in PUESTOS.values() if p.id != POR_DEFECTO and funcion in p.funciones]


def como_dict(p: Puesto) -> dict:
    return {"id": p.id, "sigla": p.sigla, "nombre": p.nombre, "descripcion": p.descripcion,
            "funciones": sorted(p.funciones)}
