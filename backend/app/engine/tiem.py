"""Documentos del TIEM que redacta cada bando (Fase I, Paso 1: Apreciacion inicial).

Cuatro documentos, cada uno con los parrafos del formato guia del TIEM y redactado por las reparticiones que el
manual indica:
  analisis_mision  Analisis de la mision (Comandante y JEM): situacion, mision del Teatro, situacion propia y
                   enemiga, Poder Relativo de Combate preliminar, tareas impuestas y deducidas y mision especifica.
  concepto         Concepto del Comandante: mision especifica, centros de gravedad (COG, CC, RC, VC), objetivos
                   priorizados, tareas, nivel de efecto deseado, idea general y suposiciones.
  guia             Guia de Planeamiento (JEM): nombre clave, misiones, COG, capacidades del enemigo (que, donde, con
                   que, desde donde, cuando, como), condiciones de ejecucion, criterios, suposiciones, aspectos
                   administrativos y cronograma.
  formas_accion    Formas de Accion operacionales (A-3, A-3 D/A y A-2): al menos dos, cada una con que, donde,
                   cuando, quien y como, analizada con el criterio APA (adaptabilidad en naturaleza, integridad y
                   oportunidad; practicabilidad; aceptabilidad).

Fase I, Paso 2 (apreciaciones de Estado Mayor), una por reparticion, con los formatos guia del TIEM:
  apreciacion_inteligencia (A-2): situacion del enemigo, capacidades y su analisis (practicabilidad y aceptabilidad
                   para el enemigo) y conclusiones en orden de peligrosidad.
  apreciacion_operaciones (A-3) y apreciacion_defensa_aerea (A-3 D/A): situacion operacional, PRC, fortalezas y
                   debilidades, confrontacion de cada F/A contra cada capacidad del enemigo (matriz), comparacion de
                   las F/A (ventajas, desventajas, principios de la guerra aerea, riesgos) y F/A recomendada.
  apreciacion_personal (A-1), apreciacion_logistica (A-4) y apreciacion_ce (C-E): situacion de su area, analisis de
                   cada F/A operacional (necesidades y formas de accion de apoyo) y la F/A mas favorable.

Fase I, Paso 3 y Fase II (planes y ordenes):
  decision         Decision del Comandante: F/A adoptada, fundamentacion, idea general de la maniobra, acciones
                   inmediatas, limitaciones y organizacion de la fuerza.
  analisis_previo  Analisis previo al plan (JEM y A-3): estudio, suposiciones, objetivos materiales con APA,
                   distribucion del poder combativo, despliegues y planes alternos.
  plan_operaciones Plan de Operaciones: situacion, mision, concepto, TAREAS de las unidades subordinadas (cada una es
                   una orden del simulador para un turno: unidad, accion, objetivo o destino y turno), coordinacion,
                   logistica y comando. Las tareas que vencen se emiten como ordenes desde la Orden de Operaciones
                   (ver routers/tiem.py, emitir).

El simulador ayuda con lo que es transcripcion (`sugerencias`: datos del PMO, de la cadena de objetivos, del
calendario y el Poder Relativo de Combate calculado); el analisis queda a cargo de los alumnos. Cada documento pasa
por los estados borrador -> presentado -> aprobado o devuelto (con las observaciones del instructor).
"""

import json
import random
import re
import secrets
from dataclasses import dataclass

from app.engine import calendario, catalogo, pmo

ESTADOS = ("borrador", "presentado", "aprobado", "devuelto")
MAX_TEXTO = 8000
MAX_FILAS = 40
MAX_FORMAS = 6

LADOS = ("propio", "enemigo")
NIVELES_GUERRA = ("estrategico", "operacional", "tactico")
CATEGORIAS_EFECTO = ("directo", "indirecto", "secuencial", "simultaneo", "sistemico", "acumulativo", "cascada")
EFECTOS_CONFRONTACION = ("no afecta", "degrada", "anula")  # efecto de una capacidad del enemigo sobre una F/A
# acciones del simulador que puede tener una tarea del Plan de Operaciones (ver routers/ordenes.py)
TIPOS_TAREA = {"mover": "Desplazar", "atacar": "Atacar", "patrullar": "Patrullar", "apoyar": "Apoyar",
               "aterrizar": "Aterrizar", "interferir": "Interferir"}
AREAS_ACCION = ("personal", "inteligencia", "logistica", "operaciones", "otros")
PRINCIPIOS_GUERRA_AEREA = ("objetivo", "ofensiva", "seguridad", "sorpresa", "simplicidad", "masa y maniobra",
                           "economía de fuerza", "movimiento", "cooperación")


@dataclass(frozen=True)
class Columna:
    clave: str
    titulo: str
    opciones: tuple = ()  # vacio = texto libre


@dataclass(frozen=True)
class Campo:
    clave: str
    titulo: str
    tipo: str = "texto"  # texto | linea | mision | tabla | formas | matriz (F/A x capacidades) | tareas (del plan)
    ayuda: str = ""
    requerido: bool = True
    columnas: tuple = ()  # tabla
    min_filas: int = 1  # tabla requerida


@dataclass(frozen=True)
class Documento:
    tipo: str
    titulo: str
    paso: str
    redactan: tuple  # ids de reparticion (engine/puestos.py)
    campos: tuple
    descripcion: str = ""


_TAREAS = (Columna("tarea", "Tarea"), Columna("origen", "Origen", ("impuesta", "deducida")), Columna("prioridad", "Prioridad"))
_COG = (Columna("lado", "Lado", LADOS), Columna("nivel", "Nivel", NIVELES_GUERRA), Columna("cog", "Centro de gravedad"),
        Columna("cc", "Capacidades críticas"), Columna("rc", "Requerimientos críticos"),
        Columna("vc", "Vulnerabilidades críticas"))
_SUPOSICIONES = (Columna("suposicion", "Suposición (como hecho, en futuro)"),
                 Columna("probabilidad", "Probabilidad", ("alta", "media", "baja")), Columna("plan_alterno", "Plan alterno"))
_PRC = (Columna("factor", "Factor"), Columna("propio", "Propio"), Columna("enemigo", "Enemigo (estimado)"),
        Columna("relacion", "Relación"), Columna("conclusion", "Conclusión"))

# subcampos de cada Forma de Accion: (clave, titulo, tipo, opciones)
CAMPOS_FA = (
    ("nombre", "Nombre (F/A 1, F/A 2…)", "linea", ()),
    ("que", "¿Qué hacer? (verbo en infinitivo)", "linea", ()),
    ("donde", "¿Dónde?", "linea", ()),
    ("cuando", "¿Cuándo?", "linea", ()),
    ("quien", "¿Quién? (unidades)", "linea", ()),
    ("como", "¿Cómo? (secuencia de acciones y efectos)", "texto", ()),
    ("naturaleza", "Adaptabilidad · naturaleza", "opcion", ("si", "parcial", "no")),
    ("naturaleza_f", "Fundamento (¿contribuye a la tarea?)", "texto", ()),
    ("integridad", "Adaptabilidad · integridad o alcance", "opcion", ("si", "parcial", "no")),
    ("integridad_f", "Fundamento (¿cumple toda la tarea?)", "texto", ()),
    ("oportunidad", "Adaptabilidad · oportunidad", "opcion", ("si", "parcial", "no")),
    ("oportunidad_f", "Fundamento (¿a tiempo?)", "texto", ()),
    ("prac_propia", "Practicabilidad · ¿tenemos capacidad para realizarla?", "texto", ()),
    ("prac_oposicion", "Practicabilidad · ¿podemos vencer las capacidades del enemigo?", "texto", ()),
    ("prac_ambiente", "Practicabilidad · ¿cómo afecta el ambiente operacional?", "texto", ()),
    ("practicabilidad", "Conclusión de practicabilidad", "opcion", ("practicable", "parcialmente practicable", "no practicable")),
    ("acep_beneficio", "Aceptabilidad · resultados que se obtienen", "texto", ()),
    ("acep_costo", "Aceptabilidad · costos (pérdidas, tiempo, medios)", "texto", ()),
    ("aceptabilidad", "Conclusión de aceptabilidad", "opcion", ("alta", "media", "baja")),
)
REQUERIDOS_FA = ("que", "donde", "cuando", "quien", "naturaleza", "integridad", "oportunidad", "practicabilidad")

_CAPACIDADES = (Columna("que", "¿Qué?"), Columna("donde", "¿Dónde?"), Columna("con_que", "¿Con qué?"),
                Columna("desde_donde", "¿Desde dónde?"), Columna("cuando", "¿Cuándo?"), Columna("como", "¿Cómo?"),
                Columna("peligrosidad", "Orden de peligrosidad"))
_CONCLUSION_APOYO = ("apoya", "apoya con limitaciones", "no apoya")
_ORGANIZACION = (Columna("elemento", "Elemento"), Columna("unidades", "Unidades"), Columna("ubicacion", "Ubicación"),
                 Columna("comandante", "Comandante"))

_CAMPOS_OPERACIONES = (
    Campo("mision_resumen", "1.1 Resumen de la situación general y misión del escalón superior"),
    Campo("tareas", "1.2 Tareas impuestas, deducidas y su secuencia", "tabla", columnas=_TAREAS),
    Campo("mision_especifica", "1.3 Misión específica", "mision"),
    Campo("prc", "2.1 Poder relativo de combate", "tabla", columnas=_PRC),
    Campo("factores", "2.1 Factores generales, militares y características del Teatro de Operaciones", requerido=False,
          ayuda="Solo lo que influye en el cumplimiento de la misión, positiva o negativamente."),
    Campo("fortalezas_debilidades", "2.1.4 Fortalezas y debilidades", "tabla", columnas=(
        Columna("lado", "Lado", LADOS), Columna("tipo", "Tipo", ("fortaleza", "debilidad")),
        Columna("descripcion", "Descripción"))),
    Campo("confrontacion", "3. Confrontación de las F/A vs las capacidades del enemigo", "matriz",
          ayuda="Dándolas a ambas como ejecutadas, cómo afecta cada capacidad del enemigo a cada F/A: no la afecta, la "
                "degrada o la anula. El ensayo en el simulador (juego de guerra) ayuda a fundamentarlo."),
    Campo("comparacion", "4. Comparación de nuestras F/A", "tabla", columnas=(
        Columna("fa", "F/A"), Columna("ventajas", "Ventajas"), Columna("desventajas", "Desventajas"),
        Columna("principios", "Principios de la guerra aérea que cumple"), Columna("riesgos", "Riesgos asumidos"))),
    Campo("fa_recomendada", "5.1 Forma de Acción recomendada", "linea"),
    Campo("justificacion", "5.2 Justificación"),
    Campo("factores_limitantes", "5.3 Factores limitantes", requerido=False),
)


def _campos_apoyo(titulo_situacion: str, ayuda_situacion: str) -> tuple:
    """Formato comun de las apreciaciones de personal, logistica y comunicaciones."""
    return (
        Campo("mision_especifica", "1.1 Misión específica", "mision"),
        Campo("situacion_propia", "2.1 Situación operacional propia",
              ayuda="Disposición y dotación de las unidades, naturaleza de las operaciones, terreno y clima, y las "
                    "capacidades del enemigo que afectan al área."),
        Campo("situacion_area", titulo_situacion, ayuda=ayuda_situacion),
        Campo("analisis_fa", "3. Análisis de las F/A operacionales", "tabla", columnas=(
            Columna("fa", "F/A"), Columna("necesidades", "Necesidades y requerimientos"),
            Columna("formas_apoyo", "Formas de acción de apoyo (qué, dónde, cuándo, quién)"),
            Columna("conclusion", "Conclusión parcial", _CONCLUSION_APOYO))),
        Campo("conclusiones", "4. Conclusiones y recomendaciones",
              ayuda="La F/A operacional más favorable desde el punto de vista del área y las providencias a tomar."),
    )


DOCUMENTOS: dict[str, Documento] = {d.tipo: d for d in [
    Documento("analisis_mision", "Análisis de la misión", "Fase I · Paso 1", ("comandante", "jem"), (
        Campo("resumen_situacion", "1. Resumen de la situación (contexto histórico y situación actual)"),
        Campo("mision_to", "2. Misión estratégico-operacional del Teatro de Operaciones"),
        Campo("idea_general_conjunta", "3. Idea general de la operación conjunta", requerido=False),
        Campo("situacion_propia", "4. Situación militar propia"),
        Campo("situacion_enemigo", "5. Situación militar del enemigo"),
        Campo("prc", "6. Poder relativo de combate (preliminar)", "tabla", columnas=_PRC,
              ayuda="Lo calcula el simulador con las fuerzas propias y la estimación de inteligencia; la conclusión es suya."),
        Campo("fortalezas_debilidades", "Fortalezas y debilidades (resumen del PRC)"),
        Campo("tareas", "Tareas impuestas y deducidas", "tabla", columnas=_TAREAS,
              ayuda="Impuestas: las que fija el escalón superior. Deducidas: las que hacen falta para cumplirlas."),
        Campo("mision_especifica", "7. Misión específica del Componente Aéreo", "mision",
              ayuda="TAREA (qué, dónde, cuándo) «a fin de» PROPÓSITO; verbo en infinitivo y sin condiciones."),
    ), "El Comandante con su Estado Mayor interpreta la misión recibida y deduce la misión específica."),
    Documento("concepto", "Concepto del Comandante", "Fase I · Paso 1", ("comandante", "jem"), (
        Campo("mision_especifica", "1. Misión específica", "mision"),
        Campo("cog", "2. Centros de gravedad del enemigo y propios (preliminares)", "tabla", columnas=_COG, min_filas=2,
              ayuda="Al menos uno propio y uno enemigo. Ejemplo: COG Comando de caza · CC respuesta inmediata · "
                    "RC sistema de alerta temprana · VC radares."),
        Campo("objetivos", "3. Objetivos priorizados", "tabla", columnas=(
            Columna("prioridad", "Prioridad"), Columna("objetivo", "Objetivo"), Columna("efecto", "Efecto deseado"),
            Columna("indicador", "Indicador"))),
        Campo("tareas", "4. Tareas a realizar (impuestas y deducidas)", "tabla", columnas=_TAREAS),
        Campo("efecto_deseado", "5. Nivel de efecto deseado", "tabla", columnas=(
            Columna("efecto", "Efecto deseado"), Columna("nivel", "Nivel", NIVELES_GUERRA),
            Columna("categoria", "Categoría", CATEGORIAS_EFECTO), Columna("indicador", "Indicador observable o medible"))),
        Campo("idea_general", "6. Idea general de las operaciones",
              ayuda="Línea gruesa de cómo se cumplirá la misión: neutralizar la defensa aérea, la aviación, la logística…"),
        Campo("suposiciones", "Suposiciones", "tabla", columnas=_SUPOSICIONES, requerido=False),
    ), "El Comandante orienta el trabajo de su Estado Mayor."),
    Documento("guia", "Guía de Planeamiento", "Fase I · Paso 1", ("jem", "comandante"), (
        Campo("nombre_clave", "Nombre clave de la operación", "linea"),
        Campo("mision_to", "1. Misión estratégico-operacional del Teatro de Operaciones"),
        Campo("mision_especifica", "2. Misión específica", "mision"),
        Campo("cog", "3. Centros de gravedad", "tabla", columnas=_COG, min_filas=2),
        Campo("capacidades_enemigo", "4. Capacidades del enemigo", "tabla", columnas=_CAPACIDADES,
              ayuda="Lo que el enemigo realmente está en condiciones de hacer y que interfiere con nuestra misión, "
                    "sin tener en cuenta nuestra oposición; ordenadas de mayor a menor peligrosidad."),
        Campo("condiciones", "5. Condiciones de ejecución (en tiempo y lugar)"),
        Campo("criterios", "6. Criterios",
              ayuda="Fases, actitud (ofensiva o defensiva), tipos de operaciones, duración, organización de la fuerza, "
                    "nivel de daño deseado y otras medidas de coordinación."),
        Campo("suposiciones", "7. Suposiciones", "tabla", columnas=_SUPOSICIONES, requerido=False),
        Campo("administrativos", "8. Aspectos administrativos", requerido=False),
        Campo("cronograma", "9. Cronograma de la planificación", "tabla", columnas=(
            Columna("actividad", "Actividad"), Columna("inicio", "Inicio"), Columna("fin", "Fin"),
            Columna("responsable", "Responsable"))),
    ), "El Jefe de Estado Mayor ordena por escrito el trabajo de las reparticiones."),
    Documento("formas_accion", "Formas de Acción operacionales", "Fase I · Paso 1", ("a3", "a3da", "a2", "jem", "comandante"), (
        Campo("efecto_deseado", "Efecto deseado (tarea de la misión) contra el que se analizan",
              ayuda="Las F/A se comparan con la tarea de la misión específica."),
        Campo("formas", "Formas de Acción y su análisis APA", "formas",
              ayuda="Al menos dos. Cada una responde qué, dónde, cuándo y quién, y se analiza en adaptabilidad "
                    "(naturaleza, integridad, oportunidad), practicabilidad (medios propios, oposición y ambiente) y "
                    "aceptabilidad (costo y beneficio)."),
        Campo("conclusion", "Conclusión: F/A que reúnen el criterio APA", requerido=False),
    ), "Operaciones, Defensa Aérea e Inteligencia elaboran las F/A que luego apreciará todo el Estado Mayor."),
    Documento("apreciacion_inteligencia", "Apreciación de Inteligencia", "Fase I · Paso 2", ("a2", "jem", "comandante"), (
        Campo("mision_especifica", "1. Misión específica", "mision"),
        Campo("situacion_enemigo", "2. Situación del enemigo",
              ayuda="Organización, despliegue, sistemas de armas, defensa aérea, terreno y meteorología: solo lo que "
                    "afecta a nuestra misión y respaldado con hechos."),
        Campo("capacidades_enemigo", "3. Capacidades del enemigo", "tabla", columnas=_CAPACIDADES),
        Campo("analisis_capacidades", "4. Análisis de las capacidades del enemigo", "tabla", columnas=(
            Columna("capacidad", "Capacidad"),
            Columna("practicabilidad", "Practicabilidad (con nuestra oposición)", ("practicable", "parcialmente practicable", "no practicable")),
            Columna("aceptabilidad", "Aceptabilidad para el enemigo", ("alta", "media", "baja")),
            Columna("retenida", "¿Se retiene?", ("si", "no")), Columna("fundamento", "Fundamento")),
              ayuda="Se retienen las capacidades que, practicables y aceptables para el enemigo, pueden interferir "
                    "con nuestra misión."),
        Campo("conclusiones", "5. Conclusiones",
              ayuda="Capacidad global del enemigo para interferir con la misión y las capacidades ordenadas de mayor a "
                    "menor peligrosidad, justificando el orden."),
    ), "La A-2 determina la capacidad del enemigo para interferir con nuestra misión."),
    Documento("apreciacion_operaciones", "Apreciación de Operaciones", "Fase I · Paso 2", ("a3", "jem", "comandante"), (
        *_CAMPOS_OPERACIONES,
    ), "La A-3 confronta las F/A con las capacidades del enemigo, las compara y recomienda la mejor."),
    Documento("apreciacion_defensa_aerea", "Apreciación de Defensa Aérea", "Fase I · Paso 2", ("a3da", "jem", "comandante"), (
        *(Campo("factores", "2.1 Situación de la defensa aérea propia y de la amenaza aérea enemiga",
                ayuda="Radares, artillería y misiles antiaéreos, interceptores, alerta temprana y sus coberturas; líneas "
                      "de defensa (LDM, LID, LIMP, LLB); la aviación enemiga que puede atacarnos.")
          if c.clave == "factores" else c for c in _CAMPOS_OPERACIONES),
    ), "La A-3 D/A aprecia las F/A desde las operaciones defensivas."),
    Documento("apreciacion_personal", "Apreciación de Personal", "Fase I · Paso 2", ("a1", "jem", "comandante"), (
        *_campos_apoyo("2.2 Situación de personal",
                       "Efectivos y su ubicación, reemplazos, entrenamiento, moral, prisioneros de guerra, asuntos civiles."),
    ), "La A-1 determina las necesidades de personal de cada F/A operacional."),
    Documento("apreciacion_logistica", "Apreciación de Logística", "Fase I · Paso 2", ("a4", "jem", "comandante"), (
        *_campos_apoyo("2.2 Situación logística",
                       "Abastecimiento de combustible y munición, existencias de las bases y depósitos, mantenimiento, "
                       "transporte, instalaciones, sanidad y evacuación."),
    ), "La A-4 determina si la logística puede sostener cada F/A operacional."),
    Documento("apreciacion_ce", "Apreciación de Comunicaciones y Electrónica", "Fase I · Paso 2", ("ce", "jem", "comandante"), (
        *_campos_apoyo("2.2 Situación de comunicaciones y electrónica",
                       "Redes y enlaces, centros de comunicaciones, guerra electrónica propia y enemiga, emisiones."),
    ), "La C-E determina cómo apoyar con comunicaciones y guerra electrónica cada F/A operacional."),
    Documento("decision", "Decisión del Comandante", "Fase I · Paso 3", ("comandante",), (
        Campo("fa_adoptada", "1. Forma de Acción adoptada", "linea",
              ayuda="La F/A elegida después de oír a todo el Estado Mayor (puede ser una combinación de varias)."),
        Campo("fundamentacion", "2. Fundamentación",
              ayuda="Por qué esa F/A, según la misión, la situación y las apreciaciones (sobre todo la de Operaciones)."),
        Campo("idea_maniobra", "3. Idea general de la maniobra",
              ayuda="Fases según los objetivos intermedios, acciones en cada fase, tareas a las unidades y tácticas."),
        Campo("acciones_inmediatas", "4. Acciones inmediatas", "tabla", columnas=(
            Columna("area", "Área", AREAS_ACCION), Columna("accion", "Acción"), Columna("responsable", "Responsable"))),
        Campo("limitaciones", "5. Limitaciones", requerido=False),
        Campo("organizacion_fuerza", "6. Organización de la fuerza", "tabla", columnas=_ORGANIZACION),
    ), "El Comandante decide la Forma de Acción que cumplirá la misión."),
    Documento("analisis_previo", "Análisis previo al plan", "Fase II · Paso 1", ("jem", "a3", "comandante"), (
        Campo("estudio", "1. Estudio de la información disponible",
              ayuda="La misión, la decisión del Comandante y lo sobresaliente de las apreciaciones (fortalezas, "
                    "debilidades y limitaciones de personal, logística y comunicaciones)."),
        Campo("suposiciones", "2. Suposiciones", "tabla", columnas=_SUPOSICIONES, requerido=False),
        Campo("objetivos_materiales", "3. Objetivos materiales correctos", "tabla", columnas=(
            Columna("prioridad", "Prioridad"), Columna("objetivo", "Objetivo material"), Columna("efecto", "Efecto a lograr"),
            Columna("adaptabilidad", "Adaptable", ("si", "parcial", "no")),
            Columna("practicabilidad", "Practicable", ("si", "parcial", "no")),
            Columna("aceptabilidad", "Aceptable", ("si", "parcial", "no")))),
        Campo("distribucion", "4. Distribución del poder combativo", "tabla", columnas=(
            Columna("esfuerzo", "Esfuerzo"), Columna("medios", "Medios asignados"), Columna("porcentaje", "% de los medios"))),
        Campo("despliegues", "5. Despliegues", ayuda="Desde dónde se proyecta la acción y por qué (bases, redespliegues)."),
        Campo("planes_alternos", "6. Formas de acción alternas o planes alternos", requerido=False),
    ), "El Estado Mayor concreta cómo materializar la decisión: objetivos, fuerzas y despliegues."),
    Documento("plan_operaciones", "Plan de Operaciones", "Fase II · Paso 2", ("jem", "a3", "a3da", "comandante"), (
        Campo("nombre_clave", "Nombre clave de la operación", "linea"),
        Campo("organizacion_fuerzas", "Organización de las fuerzas", "tabla", columnas=_ORGANIZACION),
        Campo("resumen_situacion", "1.1 Resumen de la situación"),
        Campo("fuerzas_enemigas", "1.2 Fuerzas enemigas"),
        Campo("fuerzas_amigas", "1.3 Fuerzas amigas", requerido=False),
        Campo("suposiciones", "1.4 Suposiciones", "tabla", columnas=_SUPOSICIONES, requerido=False),
        Campo("mision", "2. Misión", "mision"),
        Campo("concepto", "3.1 Concepto de la operación"),
        Campo("tareas", "3.2 Tareas de las unidades subordinadas", "tareas",
              ayuda="Una actividad por tarea, en infinitivo: qué unidad, qué acción, contra qué o hacia dónde y en qué "
                    "turno (H+n). Cada tarea se emite como orden del simulador desde la Orden de Operaciones."),
        Campo("coordinacion", "3.4 Instrucciones de coordinación"),
        Campo("logistica", "4. Asuntos logísticos", requerido=False),
        Campo("comando", "5. Asuntos de comando y comunicaciones", requerido=False),
    ), "El plan convierte la decisión en tareas para cada unidad, en tiempo y espacio."),
]}
ORDEN = tuple(DOCUMENTOS)


def definicion(d: Documento) -> dict:
    """Formato de un documento para la interfaz (campos, columnas, opciones y quien lo redacta)."""
    return {
        "tipo": d.tipo, "titulo": d.titulo, "paso": d.paso, "descripcion": d.descripcion, "redactan": list(d.redactan),
        "campos": [{
            "clave": c.clave, "titulo": c.titulo, "tipo": c.tipo, "ayuda": c.ayuda, "requerido": c.requerido,
            "columnas": [{"clave": x.clave, "titulo": x.titulo, "opciones": list(x.opciones)} for x in c.columnas],
            "min_filas": c.min_filas,
        } for c in d.campos],
        "campos_fa": [{"clave": k, "titulo": t, "tipo": tp, "opciones": list(o)} for k, t, tp, o in CAMPOS_FA],
        "efectos": list(EFECTOS_CONFRONTACION),
        "tipos_tarea": TIPOS_TAREA,
    }


# ---------------------------------------------------------------- normalizacion y validacion
def _txt(v, maximo=MAX_TEXTO) -> str:
    return str(v or "").strip()[:maximo]


def normalizar(tipo: str, contenido: dict | None) -> dict:
    """Contenido limpio del documento: todos los campos, filas sin columnas desconocidas y opciones validas."""
    d = DOCUMENTOS[tipo]
    c = contenido if isinstance(contenido, dict) else {}
    out = {}
    for campo in d.campos:
        v = c.get(campo.clave)
        if campo.tipo == "mision":
            v = v if isinstance(v, dict) else {}
            out[campo.clave] = {p: _txt(v.get(p), 600) for p in pmo.PARTES_MISION}
        elif campo.tipo == "tabla":
            filas = []
            for f in (v if isinstance(v, list) else [])[:MAX_FILAS]:
                if not isinstance(f, dict):
                    continue
                fila = {}
                for col in campo.columnas:
                    x = _txt(f.get(col.clave), 600)
                    fila[col.clave] = x if not col.opciones or x in col.opciones else ""
                if any(fila.values()):
                    filas.append(fila)
            out[campo.clave] = filas
        elif campo.tipo == "formas":
            formas = []
            for f in (v if isinstance(v, list) else [])[:MAX_FORMAS]:
                if not isinstance(f, dict):
                    continue
                fa = {}
                for k, _, tp, ops in CAMPOS_FA:
                    x = _txt(f.get(k), 3000)
                    fa[k] = x if tp != "opcion" or x in ops else ""
                if any(fa.values()):
                    formas.append(fa)
            out[campo.clave] = formas
        elif campo.tipo == "tareas":
            out[campo.clave] = [t for t in (normalizar_tarea(f) for f in (v if isinstance(v, list) else [])[:MAX_TAREAS])
                                if t is not None]
        elif campo.tipo == "matriz":
            celdas, vistas = [], set()
            for f in (v if isinstance(v, list) else [])[:MAX_FILAS * 4]:
                if not isinstance(f, dict):
                    continue
                fa, cap = _txt(f.get("fa"), 300), _txt(f.get("capacidad"), 300)
                efecto = _txt(f.get("efecto"), 20)
                celda = {"fa": fa, "capacidad": cap, "efecto": efecto if efecto in EFECTOS_CONFRONTACION else "",
                         "analisis": _txt(f.get("analisis"), 2000)}
                if fa and cap and (fa, cap) not in vistas and (celda["efecto"] or celda["analisis"]):
                    vistas.add((fa, cap))
                    celdas.append(celda)
            out[campo.clave] = celdas
        else:
            out[campo.clave] = _txt(v, 200 if campo.tipo == "linea" else MAX_TEXTO)
    return out


MAX_TAREAS = 80
_ID_TAREA = re.compile(r"^[a-z0-9]{4,16}$")
_OBJETIVO_TAREA = re.compile(r"^[uo]:\d+$")


def normalizar_tarea(f) -> dict | None:
    """Tarea del plan: {id, unidad_id, unidad_nombre, tipo, turno, objetivo ("u:<id>" unidad | "o:<id>" objetivo),
    objetivo_nombre, detalle}. Las vacias se descartan; el id se conserva (enlaza con su ejecucion)."""
    if not isinstance(f, dict):
        return None
    def entero(x, minimo=1, maximo=9999):
        try:
            n = int(x)
        except (TypeError, ValueError):
            return None
        return n if minimo <= n <= maximo else None
    t = {
        "id": f.get("id") if isinstance(f.get("id"), str) and _ID_TAREA.match(f.get("id")) else secrets.token_hex(4),
        "unidad_id": entero(f.get("unidad_id"), 1, 10 ** 9), "unidad_nombre": _txt(f.get("unidad_nombre"), 120),
        "tipo": f.get("tipo") if f.get("tipo") in TIPOS_TAREA else "",
        "turno": entero(f.get("turno")),
        "objetivo": f.get("objetivo") if isinstance(f.get("objetivo"), str) and _OBJETIVO_TAREA.match(f.get("objetivo")) else "",
        "objetivo_nombre": _txt(f.get("objetivo_nombre"), 160), "detalle": _txt(f.get("detalle"), 600),
    }
    if not (t["unidad_id"] or t["tipo"] or t["detalle"] or t["objetivo"]):
        return None
    return t


def texto_tarea(t: dict, ref_turno: str = "") -> str:
    """"Atacar con Escuadrón 1 a Radar enemigo (turno 5, H+2)"."""
    verbo = TIPOS_TAREA.get(t["tipo"], "Cumplir")
    unidad = t["unidad_nombre"] or f"la unidad {t['unidad_id']}"
    nexo = {"mover": "hacia", "patrullar": "sobre", "interferir": "sobre", "aterrizar": "en"}.get(t["tipo"], "a")
    destino = f" {nexo} {t['objetivo_nombre']}" if t["objetivo_nombre"] else ""
    cuando = f" (turno {t['turno']}{', ' + ref_turno if ref_turno else ''})" if t["turno"] else ""
    return f"{verbo} con {unidad}{destino}{cuando}"


def _vacio(campo: Campo, valor) -> bool:
    if campo.tipo == "mision":
        return not any(valor.values())
    if campo.tipo in ("tabla", "formas"):
        return len(valor) < (campo.min_filas if campo.tipo == "tabla" else 2)
    if campo.tipo == "matriz":
        return not any(c["efecto"] for c in valor)
    if campo.tipo == "tareas":
        return not valor
    return not valor


def revisar(tipo: str, contenido: dict) -> dict:
    """{"faltan": [...], "avisos": [...]}. Lo que falta impide presentar el documento; los avisos son de forma."""
    d = DOCUMENTOS[tipo]
    c = normalizar(tipo, contenido)
    faltan, avisos = [], []
    for campo in d.campos:
        v = c[campo.clave]
        if campo.requerido and _vacio(campo, v):
            if campo.tipo == "formas":
                faltan.append(f"{campo.titulo}: se necesitan al menos dos Formas de Acción.")
            elif campo.tipo == "tabla" and campo.min_filas > 1:
                faltan.append(f"{campo.titulo}: complete al menos {campo.min_filas} filas.")
            else:
                faltan.append(f"Falta «{campo.titulo}».")
            continue
        if campo.tipo == "mision" and any(v.values()):
            avisos += [f"{campo.titulo}: {a}" for a in pmo.avisos_mision(v)]
        if campo.clave == "cog" and v:
            lados = {f["lado"] for f in v}
            if not set(LADOS) <= lados:
                faltan.append(f"{campo.titulo}: identifique al menos un centro de gravedad propio y uno enemigo.")
        if campo.tipo == "tareas":
            for i, t in enumerate(v, 1):
                vacios = [n for k, n in (("unidad_id", "unidad"), ("tipo", "acción"), ("turno", "turno"),
                                         ("objetivo", "objetivo o destino")) if not t[k]]
                if vacios:
                    faltan.append(f"Tarea {i}: falta {', '.join(vacios)}.")
        if campo.tipo == "formas":
            for i, fa in enumerate(v, 1):
                nombre = fa["nombre"] or f"F/A {i}"
                vacios = [t for k, t, _, _ in CAMPOS_FA if k in REQUERIDOS_FA and not fa[k]]
                if vacios:
                    faltan.append(f"{nombre}: falta {', '.join(vacios)}.")
                primera = fa["que"].split(" ")[0].lower() if fa["que"] else ""
                if primera and not primera.endswith(("ar", "er", "ir", "ár", "ér", "ír")):
                    avisos.append(f"{nombre}: el «qué» debe empezar con un verbo en infinitivo.")
    return {"faltan": faltan, "avisos": avisos}


# ---------------------------------------------------------------- Poder Relativo de Combate
FACTORES_PRC = (
    ("aviacion", "Aviación de combate"),
    ("defensa_aerea", "Defensa aérea"),
    ("superficie", "Fuerzas de superficie"),
    ("guerra_electronica", "Guerra electrónica y reconocimiento"),
)


def _factor(u) -> str | None:
    c = catalogo.obtener(u.clase, u.tipo)
    if c.misil or c.infraestructura or u.tipo == "base":
        return None
    if c.id in ("antiaerea", "antiaerea_portatil", "radar", "alerta_temprana") or c.defensa_aerea:
        return "defensa_aerea"
    if c.id in ("guerra_electronica", "avion_ge", "reconocimiento", "dron_reconocimiento"):
        return "guerra_electronica"
    if u.tipo == "aerea":
        return "aviacion" if max(c.ataque_vs.values()) > 0 else None
    if c.carga_max > 0 or c.construye:
        return None
    return "superficie"


def poder_unidad(u) -> float:
    """Poder de combate didactico de una unidad: fuerza x aeronaves x (mejor ataque + defensa) / 2.

    Los sensores sin armas (radares, reconocimiento, guerra electronica) valen 1 por unidad: suman a su factor por
    lo que aportan, no por su fuego."""
    p = catalogo.perfil(u)
    n = max(1, int(getattr(u, "aeronaves", 1) or 1)) if u.tipo == "aerea" else 1
    ataque = max(p.ataque_vs.values()) if p.ataque_vs else 0.0
    base = (ataque + p.defensa) / 2 if ataque > 0 else 1.0
    return max(0.0, u.fuerza) / 100.0 * n * base


def _calificar(r: float | None) -> str:
    if r is None:
        return "sin oposición"
    if r >= 3:
        return "muy favorable"
    if r >= 1.5:
        return "favorable"
    if r >= 0.67:
        return "equilibrado"
    if r >= 0.33:
        return "desfavorable"
    return "muy desfavorable"


def poder_relativo(esc, unidades, bando: str) -> dict:
    """PRC preliminar del bando por factor. Lo propio es exacto; lo del enemigo es la estimacion de inteligencia:
    el valor real con un error fijo de hasta +-15 % por factor (siempre el mismo en el escenario)."""
    enemigo = "rojo" if bando == "azul" else "azul"
    rnd = random.Random(f"{esc.semilla}-prc-{bando}")
    tot = {b: {k: 0.0 for k, _ in FACTORES_PRC} for b in (bando, enemigo)}
    for u in unidades:
        if u.bando not in tot or u.estado != "activa":
            continue
        f = _factor(u)
        if f:
            tot[u.bando][f] += poder_unidad(u)
    filas = []
    for k, titulo in FACTORES_PRC:
        propio = round(tot[bando][k], 1)
        estimado = round(tot[enemigo][k] * rnd.uniform(0.85, 1.15), 1)
        r = round(propio / estimado, 2) if estimado > 0 else None
        filas.append({"clave": k, "factor": titulo, "propio": propio, "enemigo": estimado,
                      "relacion": f"{r:.2f} : 1".replace(".", ",") if r is not None else "—", "valor": r,
                      "conclusion": _calificar(r) if propio or estimado else "sin medios"})
    total_p = sum(f["propio"] for f in filas)
    total_e = sum(f["enemigo"] for f in filas)
    rt = round(total_p / total_e, 2) if total_e > 0 else None
    return {"filas": filas, "total": {"propio": round(total_p, 1), "enemigo": round(total_e, 1),
                                     "relacion": f"{rt:.2f} : 1".replace(".", ",") if rt is not None else "—",
                                     "conclusion": _calificar(rt)},
            "nota": "Poder de cada unidad = fuerza × aeronaves × (mejor ataque + defensa) / 2 según el catálogo; los "
                    "sensores sin armas valen 1. Lo enemigo es una estimación de inteligencia (±15 %)."}


def fortalezas_debilidades(prc: dict) -> str:
    fuertes = [f["factor"].lower() for f in prc["filas"] if f["valor"] is not None and f["valor"] >= 1.5]
    debiles = [f["factor"].lower() for f in prc["filas"] if f["valor"] is not None and f["valor"] < 0.67]
    lineas = []
    if fuertes:
        lineas.append("- Fortalezas: superioridad propia en " + ", ".join(fuertes) + ".")
    if debiles:
        lineas.append("- Debilidades: inferioridad propia en " + ", ".join(debiles) + ".")
    lineas.append(f"- Relación global estimada: {prc['total']['relacion']} ({prc['total']['conclusion']}).")
    return "\n".join(lineas)


# ---------------------------------------------------------------- ayudas: lo que se transcribe
def sugerencias(tipo: str, esc, unidades, objetivos, bando: str, pm_contenido: dict | None,
                documentos: dict[str, dict]) -> dict:
    """Contenido sugerido para los campos que son transcripcion de otros documentos o calculo (no el analisis).
    Solo se usan para completar campos vacios (lo decide la interfaz)."""
    p = pmo.normalizar(pm_contenido)
    s: dict = {}
    prc = poder_relativo(esc, unidades, bando)
    analisis = documentos.get("analisis_mision") or {}
    concepto = documentos.get("concepto") or {}
    mision_especifica = next((d.get("mision_especifica") for d in (concepto, analisis)
                              if any((d.get("mision_especifica") or {}).values())), None) or p["mision"]
    if tipo == "analisis_mision":
        s["resumen_situacion"] = p["situacion_general"]
        s["mision_to"] = p["mision_superior"]
        s["idea_general_conjunta"] = p["idea_general"]
        s["situacion_propia"] = "\n".join(x for x in (p["fuerzas_propias"], p["medios"]) if x)
        s["situacion_enemigo"] = p["fuerzas_enemigas"]
        s["prc"] = [{"factor": f["factor"], "propio": str(f["propio"]).replace(".", ","),
                     "enemigo": str(f["enemigo"]).replace(".", ","), "relacion": f["relacion"],
                     "conclusion": f["conclusion"]} for f in prc["filas"]]
        s["fortalezas_debilidades"] = fortalezas_debilidades(prc)
        s["tareas"] = [{"tarea": o.nombre, "origen": "impuesta", "prioridad": str(i)}
                       for i, o in enumerate(sorted((o for o in objetivos if o.bando == bando and o.nivel == "asignado"),
                                                    key=lambda o: -o.puntos), 1)]
        s["mision_especifica"] = p["mision"]
    elif tipo == "concepto":
        s["mision_especifica"] = mision_especifica
        mios = [o for o in objetivos if o.bando == bando and o.nivel in ("asignado", "material")]
        orden = sorted(mios, key=lambda o: (0 if o.nivel == "asignado" else 1, -o.puntos, o.id))
        s["objetivos"] = [{"prioridad": str(i), "objetivo": o.nombre, "efecto": o.efecto or "", "indicador": o.indicador or ""}
                          for i, o in enumerate(orden[:MAX_FILAS], 1)]
        s["tareas"] = analisis.get("tareas") or []
    elif tipo == "guia":
        s["mision_to"] = analisis.get("mision_to") or p["mision_superior"]
        s["mision_especifica"] = mision_especifica
        s["cog"] = concepto.get("cog") or []
        s["suposiciones"] = concepto.get("suposiciones") or []
        lineas = []
        cal = calendario.resumen(esc)
        if cal:
            if cal["turno_h"]:
                lineas.append(f"- Tiempo: día D {cal['dia_d'] or '(a determinar)'}, hora H {cal['hora_h']} (turno {cal['turno_h']})"
                              + (f"; hasta el turno {cal['turno_final']}." if cal["turno_final"] else "."))
            for f in cal["fases"]:
                lineas.append(f"- Fase {f['nombre']}: turnos {f['desde']} a {f['hasta'] or '…'}.")
        if p["area_operaciones"]:
            lineas.append(f"- Lugar: {p['area_operaciones']}")
        s["condiciones"] = "\n".join(lineas)
        fases = ", ".join(f["nombre"] for f in calendario.fases(esc))
        s["criterios"] = (f"- Fases de la operación: {fases}.\n" if fases else "") + \
            "- Actitud: (ofensiva o defensiva)\n- Tipos de operaciones: \n- Organización de la fuerza: \n- Nivel de daño deseado: "
    elif tipo == "formas_accion":
        s["efecto_deseado"] = pmo.texto_mision(mision_especifica)
    elif tipo.startswith("apreciacion_"):
        guia = documentos.get("guia") or {}
        ctx = contexto(documentos)
        mision = next((d.get("mision_especifica") for d in (guia, concepto, analisis)
                       if any((d.get("mision_especifica") or {}).values())), None) or p["mision"]
        s["mision_especifica"] = mision
        if tipo == "apreciacion_inteligencia":
            s["situacion_enemigo"] = analisis.get("situacion_enemigo") or p["fuerzas_enemigas"]
            s["capacidades_enemigo"] = guia.get("capacidades_enemigo") or []
            s["analisis_capacidades"] = [{"capacidad": c} for c in ctx["capacidades"]]
        elif tipo in ("apreciacion_operaciones", "apreciacion_defensa_aerea"):
            s["mision_resumen"] = "\n".join(x for x in (analisis.get("resumen_situacion") or p["situacion_general"],
                                                         analisis.get("mision_to") or p["mision_superior"]) if x)
            s["tareas"] = concepto.get("tareas") or analisis.get("tareas") or []
            s["prc"] = [{"factor": f["factor"], "propio": str(f["propio"]).replace(".", ","),
                         "enemigo": str(f["enemigo"]).replace(".", ","), "relacion": f["relacion"],
                         "conclusion": f["conclusion"]} for f in prc["filas"]]
            s["fortalezas_debilidades"] = filas_fortalezas(prc)
            s["confrontacion"] = [{"fa": fa, "capacidad": c, "efecto": "", "analisis": ""}
                                  for fa in ctx["formas"] for c in ctx["capacidades"]]
            s["comparacion"] = [{"fa": fa} for fa in ctx["formas"]]
            if tipo == "apreciacion_defensa_aerea":
                s["factores"] = situacion_defensa_aerea(unidades, bando)
        else:
            s["situacion_propia"] = "\n".join(x for x in (p["fuerzas_propias"], p["medios"]) if x)
            s["situacion_area"] = {"apreciacion_personal": situacion_personal, "apreciacion_logistica": situacion_logistica,
                                   "apreciacion_ce": situacion_ce}[tipo](esc, unidades, bando)
            s["analisis_fa"] = [{"fa": fa} for fa in ctx["formas"]]
    elif tipo in ("decision", "analisis_previo", "plan_operaciones"):
        ops = documentos.get("apreciacion_operaciones") or {}
        decision = documentos.get("decision") or {}
        previo = documentos.get("analisis_previo") or {}
        guia = documentos.get("guia") or {}
        if tipo == "decision":
            s["fa_adoptada"] = ops.get("fa_recomendada") or ""
            s["fundamentacion"] = ops.get("justificacion") or ""
            s["limitaciones"] = "\n".join(x for x in (ops.get("factores_limitantes"), p["limitaciones"]) if x)
            s["organizacion_fuerza"] = organizacion_fuerza(unidades, bando)
        elif tipo == "analisis_previo":
            partes = [f"- Misión: {pmo.texto_mision(mision_especifica)}"]
            if decision.get("fa_adoptada"):
                partes.append(f"- Decisión del Comandante: {decision['fa_adoptada']}.")
            for f in ops.get("fortalezas_debilidades") or []:
                partes.append(f"- {f['tipo'].capitalize() if f.get('tipo') else 'Factor'} {f.get('lado', '')}: {f.get('descripcion', '')}")
            s["estudio"] = "\n".join(partes)
            s["suposiciones"] = concepto.get("suposiciones") or guia.get("suposiciones") or []
            materiales = sorted((o for o in objetivos if o.bando == bando and o.nivel == "material"), key=lambda o: -o.puntos)
            s["objetivos_materiales"] = [{"prioridad": str(i), "objetivo": o.nombre, "efecto": o.efecto or ""}
                                         for i, o in enumerate(materiales[:MAX_FILAS], 1)]
            s["distribucion"] = distribucion_poder(unidades, bando)
        else:
            s["nombre_clave"] = guia.get("nombre_clave") or ""
            s["organizacion_fuerzas"] = decision.get("organizacion_fuerza") or organizacion_fuerza(unidades, bando)
            s["resumen_situacion"] = analisis.get("resumen_situacion") or p["situacion_general"]
            intel = documentos.get("apreciacion_inteligencia") or {}
            s["fuerzas_enemigas"] = intel.get("conclusiones") or analisis.get("situacion_enemigo") or p["fuerzas_enemigas"]
            s["suposiciones"] = previo.get("suposiciones") or []
            s["mision"] = mision_especifica
            s["concepto"] = decision.get("idea_maniobra") or ""
            s["coordinacion"] = p["instrucciones"]
    return _completar_matriz(tipo, normalizar(tipo, s), s)


def organizacion_fuerza(unidades, bando: str) -> list[dict]:
    """Elementos de la fuerza propia por categoria, con sus unidades y donde estan."""
    from app.engine import lugares

    grupos: dict[str, list] = {}
    nombres = {"aviacion": "Aviación de combate", "defensa_aerea": "Defensa aérea", "superficie": "Fuerzas de superficie",
               "guerra_electronica": "Guerra electrónica y reconocimiento"}
    for u in unidades:
        if u.bando != bando or u.estado != "activa" or getattr(u, "transporte_id", None):
            continue
        f = _factor(u) or ("logistica" if u.tipo != "base" else None)
        if u.tipo == "base" and not catalogo.obtener(u.clase, u.tipo).infraestructura:
            f = "bases"
        if f:
            grupos.setdefault(f, []).append(u)
    filas = []
    for clave, titulo in (("aviacion", "Aviación de combate"), ("defensa_aerea", "Defensa aérea"),
                          ("superficie", "Fuerzas de superficie"), ("guerra_electronica", "Guerra electrónica y reconocimiento"),
                          ("logistica", "Logística"), ("bases", "Bases y apoyo")):
        us = grupos.get(clave)
        if us:
            filas.append({"elemento": nombres.get(clave, titulo), "unidades": ", ".join(u.nombre for u in us)[:600],
                          "ubicacion": lugares.describir(us[0].lat, us[0].lon), "comandante": ""})
    return filas


def distribucion_poder(unidades, bando: str) -> list[dict]:
    """Aeronaves propias por esfuerzo (ofensivo, defensivo, apoyo), como punto de partida de la distribucion."""
    esfuerzos = {"Ofensivo (ataque, helicópteros, drones armados)": [], "Defensivo (caza y alerta temprana)": [],
                 "Apoyo (reconocimiento, guerra electrónica, cisternas)": []}
    claves = list(esfuerzos)
    for u in unidades:
        if u.bando != bando or u.estado != "activa" or u.tipo != "aerea" or catalogo.es_misil(u):
            continue
        c = catalogo.obtener(u.clase, u.tipo)
        if c.id in ("caza", "alerta_temprana"):
            esfuerzos[claves[1]].append(u)
        elif max(c.ataque_vs.values()) > 0:
            esfuerzos[claves[0]].append(u)
        else:
            esfuerzos[claves[2]].append(u)
    total = sum(max(1, u.aeronaves or 1) for us in esfuerzos.values() for u in us)
    filas = []
    for nombre, us in esfuerzos.items():
        n = sum(max(1, u.aeronaves or 1) for u in us)
        if n:
            filas.append({"esfuerzo": nombre, "medios": f"{n} aeronaves: " + ", ".join(u.nombre for u in us)[:500],
                          "porcentaje": f"{round(100 * n / total)} %"})
    return filas


def _completar_matriz(tipo: str, normal: dict, crudo: dict) -> dict:
    """La matriz sugerida va con las celdas vacias (normalizar las descarta): son el esqueleto F/A x capacidad."""
    for campo in DOCUMENTOS[tipo].campos:
        if campo.tipo == "matriz" and crudo.get(campo.clave):
            normal[campo.clave] = crudo[campo.clave]
    return normal


def contexto(documentos: dict[str, dict]) -> dict:
    """Las F/A operacionales y las capacidades del enemigo del bando, como se nombran en la confrontacion."""
    formas = [f"{fa.get('nombre') or f'F/A {i}'}: {fa.get('que', '')}".strip()
              for i, fa in enumerate((documentos.get("formas_accion") or {}).get("formas") or [], 1)]
    fuente = ((documentos.get("apreciacion_inteligencia") or {}).get("capacidades_enemigo")
              or (documentos.get("guia") or {}).get("capacidades_enemigo") or [])
    capacidades = [f"C{i}: {c.get('que', '')}".strip() for i, c in enumerate(fuente, 1) if c.get("que")]
    return {"formas": formas, "capacidades": capacidades}


def filas_fortalezas(prc: dict) -> list[dict]:
    filas = []
    for f in prc["filas"]:
        if f["valor"] is None:
            continue
        if f["valor"] >= 1.5:
            filas += [{"lado": "propio", "tipo": "fortaleza", "descripcion": f"Superioridad en {f['factor'].lower()} ({f['relacion']})"},
                      {"lado": "enemigo", "tipo": "debilidad", "descripcion": f"Inferioridad en {f['factor'].lower()}"}]
        elif f["valor"] < 0.67:
            filas += [{"lado": "enemigo", "tipo": "fortaleza", "descripcion": f"Superioridad en {f['factor'].lower()} ({f['relacion']})"},
                      {"lado": "propio", "tipo": "debilidad", "descripcion": f"Inferioridad en {f['factor'].lower()}"}]
    return filas


def _nombre_clase(u) -> str:
    return catalogo.obtener(u.clase, u.tipo).nombre


def situacion_defensa_aerea(unidades, bando: str) -> str:
    enemigo = "rojo" if bando == "azul" else "azul"
    propias = [u for u in unidades if u.bando == bando and u.estado == "activa" and _factor(u) == "defensa_aerea"]
    lineas = ["Defensa aérea propia:"]
    for u in propias:
        lineas.append(f"- {u.nombre} ({_nombre_clase(u).lower()}): alcance {u.alcance_km:.0f} km, detección "
                      f"{u.deteccion_km:.0f} km, fuerza {u.fuerza:.0f} %.")
    if not propias:
        lineas.append("- Sin medios de defensa aérea asignados.")
    cazas = [u for u in unidades if u.bando == bando and u.estado == "activa" and u.clase == "caza"]
    if cazas:
        lineas.append(f"- Caza de intercepción: {sum(max(1, u.aeronaves or 1) for u in cazas)} aeronaves.")
    amenaza = [u for u in unidades if u.bando == enemigo and u.estado == "activa" and _factor(u) == "aviacion"]
    lineas.append(f"Amenaza aérea estimada: unas {sum(max(1, u.aeronaves or 1) for u in amenaza)} aeronaves de combate "
                  "enemigas (ver la Apreciación de Inteligencia).")
    return "\n".join(lineas)


def situacion_personal(esc, unidades, bando: str) -> str:
    from app.engine import personal  # importacion tardia: personal importa el catalogo

    r = personal.resumen(unidades, bando)
    lineas = [f"- Efectivos del bando: {r['actual']} de {r['inicial']} ({r['operativo_pct'] or 0} % operativo), "
              f"bajas {r['bajas']}."]
    lineas += [f"- {x['nombre']}: {x['actual']} de {x['inicial']} en {x['unidades']} unidad(es)." for x in r["ramas"]]
    return "\n".join(lineas)


def situacion_logistica(esc, unidades, bando: str) -> str:
    from app.engine import infraestructura

    lineas = []
    for u in unidades:
        if u.bando != bando or u.estado != "activa" or u.tipo != "base" or catalogo.obtener(u.clase, u.tipo).infraestructura:
            continue
        lineas.append(f"- {u.nombre}: combustible {u.stock_combustible:.0f}, munición {u.stock_municion:.0f} (existencias).")
    convoyes = [u for u in unidades if u.bando == bando and u.estado == "activa" and u.clase == "transporte"]
    if convoyes:
        lineas.append(f"- Convoyes de abastecimiento: {len(convoyes)}.")
    for f in infraestructura.resumen(unidades, bando):
        if f["categoria"] in ("combustible", "puente"):
            lineas.append(f"- {f['nombre']}: {f['capacidad_pct']:.0f} % ({f['efecto']}).")
    return "\n".join(lineas) or "- Sin datos logísticos en el escenario."


def situacion_ce(esc, unidades, bando: str) -> str:
    from app.engine import infraestructura

    lineas = []
    for f in infraestructura.resumen(unidades, bando):
        if f["categoria"] in ("comunicaciones", "energia"):
            lineas.append(f"- {f['nombre']}: {f['capacidad_pct']:.0f} % ({f['efecto']}).")
    ge = [u for u in unidades if u.bando == bando and u.estado == "activa" and _factor(u) == "guerra_electronica"]
    if ge:
        lineas.append("- Medios de guerra electrónica y reconocimiento: " + ", ".join(u.nombre for u in ge) + ".")
    if getattr(esc, "com_perdida_pct", 0) or getattr(esc, "com_latencia_ms", 0):
        lineas.append(f"- Red del bando degradada: demora de {esc.com_latencia_ms / 1000:.0f} s y "
                      f"{esc.com_perdida_pct} % de mensajes perdidos.")
    return "\n".join(lineas) or "- Sin datos de comunicaciones en el escenario."

