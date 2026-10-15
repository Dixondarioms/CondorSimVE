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

El simulador ayuda con lo que es transcripcion (`sugerencias`: datos del PMO, de la cadena de objetivos, del
calendario y el Poder Relativo de Combate calculado); el analisis queda a cargo de los alumnos. Cada documento pasa
por los estados borrador -> presentado -> aprobado o devuelto (con las observaciones del instructor).
"""

import json
import random
from dataclasses import dataclass

from app.engine import calendario, catalogo, pmo

ESTADOS = ("borrador", "presentado", "aprobado", "devuelto")
MAX_TEXTO = 8000
MAX_FILAS = 40
MAX_FORMAS = 6

LADOS = ("propio", "enemigo")
NIVELES_GUERRA = ("estrategico", "operacional", "tactico")
CATEGORIAS_EFECTO = ("directo", "indirecto", "secuencial", "simultaneo", "sistemico", "acumulativo", "cascada")


@dataclass(frozen=True)
class Columna:
    clave: str
    titulo: str
    opciones: tuple = ()  # vacio = texto libre


@dataclass(frozen=True)
class Campo:
    clave: str
    titulo: str
    tipo: str = "texto"  # texto | linea | mision | tabla | formas
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
        Campo("capacidades_enemigo", "4. Capacidades del enemigo", "tabla", columnas=(
            Columna("que", "¿Qué?"), Columna("donde", "¿Dónde?"), Columna("con_que", "¿Con qué?"),
            Columna("desde_donde", "¿Desde dónde?"), Columna("cuando", "¿Cuándo?"), Columna("como", "¿Cómo?"),
            Columna("peligrosidad", "Orden de peligrosidad")),
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
        else:
            out[campo.clave] = _txt(v, 200 if campo.tipo == "linea" else MAX_TEXTO)
    return out


def _vacio(campo: Campo, valor) -> bool:
    if campo.tipo == "mision":
        return not any(valor.values())
    if campo.tipo in ("tabla", "formas"):
        return len(valor) < (campo.min_filas if campo.tipo == "tabla" else 2)
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
    return normalizar(tipo, s)

