"""Problema Militar Operativo (TIEM) de cada bando: el documento con que empieza el trabajo de Estado Mayor.

Contiene la situacion general, las fuerzas enemigas y propias, la mision del Comando del Teatro de Operaciones
(escalon superior), la idea general de la operacion conjunta, la mision del Componente Aereo (el bando), los medios
asignados, el area de operaciones, las limitaciones y las instrucciones de coordinacion. La mision se guarda por
partes, como la enseña el TIEM: TAREA (que, donde, cuando) "a fin de" PROPOSITO.

El instructor lo redacta o lo genera el simulador a partir del escenario (`generar`): nombres de los paises,
unidades de cada bando, objetivos, terreno y calendario. Las fuerzas enemigas se describen de forma aproximada (lo
que sabria la inteligencia antes de la operacion), nunca con la posicion exacta de cada unidad.
"""

import json
import random
from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.engine import calendario, catalogo, lugares, naciones
from app.models.escenario import Escenario
from app.models.objetivo import Objetivo
from app.models.problema_militar import ProblemaMilitar
from app.models.unidad import Unidad

BANDOS = ("azul", "rojo")

# (clave, titulo) en el orden del documento
CAMPOS = (
    ("situacion_general", "1. Situación general"),
    ("fuerzas_enemigas", "2. a. Fuerzas enemigas"),
    ("fuerzas_propias", "2. b. Fuerzas propias"),
    ("mision_superior", "3. Misión del Comando del Teatro de Operaciones"),
    ("idea_general", "4. Idea general de la operación conjunta"),
    ("mision", "5. Misión del Componente Aéreo"),
    ("medios", "6. Medios asignados"),
    ("area_operaciones", "7. Área de operaciones"),
    ("limitaciones", "8. Limitaciones"),
    ("instrucciones", "9. Instrucciones de coordinación"),
)
PARTES_MISION = ("tarea", "que", "donde", "cuando", "proposito")
MAX_TEXTO = 6000

_CAUSAS = (
    "una disputa por la delimitación de la frontera común",
    "el control de los recursos hídricos y energéticos de la cuenca fronteriza",
    "una serie de incidentes armados en la zona limítrofe",
    "el apoyo que {e} presta a grupos armados irregulares que operan desde su territorio",
)
# como se nombran las unidades en el texto: (singular, plural)
_NOMBRES = {
    "infanteria": ("unidad de infantería", "unidades de infantería"),
    "blindado": ("unidad blindada", "unidades blindadas"),
    "artilleria": ("grupo de artillería", "grupos de artillería"),
    "reconocimiento": ("unidad de reconocimiento", "unidades de reconocimiento"),
    "antiaerea": ("sistema de misiles antiaéreos", "sistemas de misiles antiaéreos"),
    "antiaerea_portatil": ("sección de misiles antiaéreos portátiles", "secciones de misiles antiaéreos portátiles"),
    "ingenieros": ("unidad de ingenieros", "unidades de ingenieros"),
    "transporte": ("convoy logístico", "convoyes logísticos"),
    "lanzador_misiles": ("batería de misiles de crucero", "baterías de misiles de crucero"),
    "radar": ("radar de vigilancia aérea", "radares de vigilancia aérea"),
    "guerra_electronica": ("unidad de guerra electrónica", "unidades de guerra electrónica"),
    "avion_ge": ("avión de guerra electrónica", "aviones de guerra electrónica"),
    "dron_reconocimiento": ("dron de reconocimiento", "drones de reconocimiento"),
    "alerta_temprana": ("avión de alerta temprana", "aviones de alerta temprana"),
    "fragata": ("fragata", "fragatas"), "patrullero": ("patrullero", "patrulleros"),
    "destructor": ("destructor", "destructores"), "portaaviones": ("portaaviones", "portaaviones"),
    "submarino": ("submarino", "submarinos"), "buque_desembarco": ("buque anfibio", "buques anfibios"),
    "deposito": ("depósito logístico", "depósitos logísticos"), "puerto": ("base naval", "bases navales"),
}
_TEATROS = {"N": "Norte", "NE": "Nororiental", "E": "Oriental", "SE": "Suroriental", "S": "Sur", "SO": "Suroccidental",
            "O": "Occidental", "NO": "Noroccidental"}
_CATEGORIAS = (
    ("aviacion", "Medios aéreos"),
    ("defensa_aerea", "Defensa aérea"),
    ("terrestre", "Fuerzas terrestres"),
    ("naval", "Fuerzas navales"),
    ("ge", "Guerra electrónica y reconocimiento"),
    ("logistica", "Logística"),
    ("infraestructura", "Infraestructura de interés"),
)


# ---------------------------------------------------------------- documento
def vacio() -> dict:
    d = {k: "" for k, _ in CAMPOS}
    d["mision"] = {p: "" for p in PARTES_MISION}
    return d


def normalizar(contenido: dict | None) -> dict:
    """Documento con todos los campos (texto recortado); ignora claves desconocidas."""
    d = vacio()
    for k, _ in CAMPOS:
        v = (contenido or {}).get(k)
        if k == "mision":
            v = v if isinstance(v, dict) else {}
            d["mision"] = {p: str(v.get(p) or "").strip()[:600] for p in PARTES_MISION}
        elif v is not None:
            d[k] = str(v).strip()[:MAX_TEXTO]
    return d


def texto_mision(m: dict) -> str:
    """"TAREA que donde cuando, a fin de PROPOSITO." a partir de sus partes."""
    cuerpo = " ".join(m.get(p, "").strip() for p in ("tarea", "que", "donde", "cuando") if m.get(p, "").strip())
    if not cuerpo:
        return ""
    prop = m.get("proposito", "").strip()
    return f"{cuerpo}, a fin de {prop}." if prop else f"{cuerpo}."


def avisos_mision(m: dict) -> list[str]:
    """Reglas del TIEM para enunciar una mision: verbo en infinitivo, que/donde/cuando, proposito y sin condiciones."""
    avisos = []
    tarea = (m.get("tarea") or "").strip()
    primera = tarea.split(" ")[0].lower() if tarea else ""
    if not tarea:
        avisos.append("Falta la tarea.")
    elif not primera.endswith(("ar", "er", "ir", "ár", "ér", "ír")):
        avisos.append("La tarea debe empezar con un verbo en infinitivo (conducir, neutralizar, defender...).")
    for parte, nombre in (("que", "qué"), ("donde", "dónde"), ("cuando", "cuándo")):
        if not (m.get(parte) or "").strip():
            avisos.append(f"Falta el {nombre} de la tarea.")
    if not (m.get("proposito") or "").strip():
        avisos.append("Falta el propósito (\"a fin de...\").")
    todo = " " + " ".join((m.get(p) or "") for p in PARTES_MISION).lower() + " "
    if any(c in todo for c in (" si ", " en caso de ", " de ser posible", " siempre que ")):
        avisos.append("La misión no debe contener condiciones (si, en caso de, de ser posible).")
    return avisos


def como_dict(pm: ProblemaMilitar | None, bando: str) -> dict:
    contenido = normalizar(json.loads(pm.contenido_json) if pm else {})
    return {
        "bando": bando, "existe": pm is not None, "origen": pm.origen if pm else None,
        "actualizado_en": pm.actualizado_en.isoformat() if pm and pm.actualizado_en else None,
        "contenido": contenido, "mision_texto": texto_mision(contenido["mision"]),
        "avisos_mision": avisos_mision(contenido["mision"]) if pm else [],
        "titulos": dict(CAMPOS),
    }


def obtener(db: Session, esc: Escenario, bando: str) -> ProblemaMilitar | None:
    return db.query(ProblemaMilitar).filter(ProblemaMilitar.escenario_id == esc.id, ProblemaMilitar.bando == bando).first()


def guardar(db: Session, esc: Escenario, bando: str, contenido: dict, origen: str) -> ProblemaMilitar:
    pm = obtener(db, esc, bando)
    if pm is None:
        pm = ProblemaMilitar(escenario_id=esc.id, bando=bando)
        db.add(pm)
    pm.contenido_json = json.dumps(normalizar(contenido), ensure_ascii=False)
    pm.origen = origen
    return pm


# ---------------------------------------------------------------- generacion automatica
def _pais(esc: Escenario, bando: str) -> str:
    """Nombre del pais del bando como va en una oracion ("la República de Valdoria", "Venezuela")."""
    n = naciones.obtener(getattr(esc, f"nacion_{bando}"))
    if n is None:
        return f"el País {bando.capitalize()}"
    nombre = n.nombre.replace(" (ficticia)", "")
    return f"la {nombre}" if nombre.startswith("República") else nombre


def _mayuscula(t: str) -> str:
    return t[:1].upper() + t[1:]


def _nombre_clase(clase_id: str, n: int, nombre_catalogo: str) -> str:
    singular, plural = _NOMBRES.get(clase_id, (nombre_catalogo.lower(), nombre_catalogo.lower()))
    return f"{_aprox(n)} {singular if n == 1 else plural}"


def _categoria(u: Unidad) -> str | None:
    c = catalogo.obtener(u.clase, u.tipo)
    if c.misil:
        return None
    if c.infraestructura:
        return "infraestructura"
    if c.id in ("antiaerea", "antiaerea_portatil", "radar", "alerta_temprana") or c.defensa_aerea:
        return "defensa_aerea"
    if c.id in ("guerra_electronica", "avion_ge", "reconocimiento", "dron_reconocimiento"):
        return "ge"
    if c.id in ("deposito", "transporte", "ingenieros", "puerto"):
        return "logistica"
    if u.tipo == "aerea" or c.id == "base_aerea":
        return "aviacion"
    if u.tipo == "naval":
        return "naval"
    return "terrestre"


def _lugares_de(unidades: list[Unidad], maximo: int = 3) -> str:
    cuenta = Counter()
    for u in unidades:
        c = lugares.cercano(u.lat, u.lon)
        cuenta[c["nombre"] if c else lugares.describir(u.lat, u.lon)] += 1
    nombres = [n for n, _ in cuenta.most_common(maximo)]
    if not nombres:
        return ""
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _aprox(n: int) -> str:
    if n <= 2:
        return str(n)
    if n <= 5:
        return "unas " + str(n)
    return f"entre {max(1, n - 2)} y {n + 2}"


def _plural(n: int, uno: str, varios: str) -> str:
    return uno if n == 1 else varios


def _fuerzas_enemigas(enemigas: list[Unidad], pais_e: str) -> str:
    por_cat = defaultdict(list)
    for u in enemigas:
        if (cat := _categoria(u)) is not None:
            por_cat[cat].append(u)
    lineas = [f"La inteligencia estima que {pais_e} dispone en el área de operaciones de:"]
    for cat, titulo in _CATEGORIAS:
        us = por_cat.get(cat)
        if not us:
            continue
        clases = Counter((u.clase, catalogo.obtener(u.clase, u.tipo).nombre) for u in us)
        if cat == "aviacion":
            aviones = sum(max(1, u.aeronaves or 1) for u in us if u.tipo == "aerea")
            bases = [u for u in us if u.tipo == "base"]
            detalle = f"{_aprox(aviones)} aeronaves de combate" if aviones else "sin aeronaves identificadas"
            if bases:
                detalle += f", operando desde {len(bases)} {_plural(len(bases), 'base aérea', 'bases aéreas')} ({_lugares_de(bases)})"
        elif cat == "infraestructura":
            detalle = ", ".join(sorted({u.nombre for u in us})[:6])
        else:
            detalle = "; ".join(_nombre_clase(cid, n, nombre) for (cid, nombre), n in clases.most_common(4))
            if lug := _lugares_de(us):
                detalle += f", en la zona de {lug}"
        lineas.append(f"- {titulo}: {detalle}.")
    if len(lineas) == 1:
        lineas.append("- Sin información sobre fuerzas enemigas en el área.")
    return "\n".join(lineas)


def _fuerzas_propias(propias: list[Unidad], pais: str) -> str:
    terrestres = [u for u in propias if _categoria(u) == "terrestre"]
    navales = [u for u in propias if _categoria(u) == "naval"]
    lineas = [f"Las fuerzas armadas de {pais} conducen la operación con los componentes del Teatro de Operaciones:"]
    lineas.append(f"- Componente Terrestre: {len(terrestres)} {_plural(len(terrestres), 'unidad', 'unidades')}"
                  + (f" desplegadas en la zona de {_lugares_de(terrestres)}." if terrestres else " (fuera del ejercicio)."))
    lineas.append(f"- Componente Naval: {len(navales)} {_plural(len(navales), 'unidad', 'unidades')}"
                  + (f" en la zona de {_lugares_de(navales)}." if navales else " (fuera del ejercicio)."))
    lineas.append("- Componente Aéreo: los medios del párrafo 6 (el bando que conducen ustedes).")
    return "\n".join(lineas)


def _medios(propias: list[Unidad]) -> str:
    lineas = []
    bases = [u for u in propias if u.tipo == "base" and not catalogo.obtener(u.clase, u.tipo).infraestructura]
    aereas = [u for u in propias if u.tipo == "aerea" and not catalogo.es_misil(u)]
    if aereas:
        por_modelo = Counter()
        for u in aereas:
            m = catalogo.MODELOS.get(u.modelo or "")
            por_modelo[m.nombre if m else catalogo.obtener(u.clase, u.tipo).nombre] += max(1, u.aeronaves or 1)
        lineas.append("- Aeronaves: " + "; ".join(f"{n} {nombre}" for nombre, n in por_modelo.most_common()) + ".")
    if bases:
        lineas.append("- Bases y apoyo: " + "; ".join(u.nombre for u in bases) + ".")
    for cat, titulo in (("defensa_aerea", "Defensa aérea"), ("ge", "Guerra electrónica y reconocimiento"),
                        ("logistica", "Logística")):
        us = [u for u in propias if _categoria(u) == cat and u.tipo != "aerea" and u.tipo != "base"]
        if us:
            lineas.append(f"- {titulo}: " + "; ".join(u.nombre for u in us) + ".")
    return "\n".join(lineas) or "- Sin medios asignados."


def _grados(v: float, pos: str, neg: str) -> str:
    g = abs(v)
    return f"{int(g)}°{round((g - int(g)) * 60):02d}' {pos if v >= 0 else neg}"


def _area(unidades: list[Unidad]) -> str:
    if not unidades:
        return "A definir por el instructor."
    lats, lons = [u.lat for u in unidades], [u.lon for u in unidades]
    s, n, o, e = min(lats) - 0.5, max(lats) + 0.5, min(lons) - 0.5, max(lons) + 0.5
    ciudades = sorted((c for c in lugares.todos() if s <= c["lat"] <= n and o <= c["lon"] <= e),
                      key=lambda c: -c["pop"])[:6]
    texto = (f"Comprendida entre los paralelos {_grados(s, 'N', 'S')} y {_grados(n, 'N', 'S')} y los meridianos "
             f"{_grados(o, 'E', 'O')} y {_grados(e, 'E', 'O')}")
    if ciudades:
        texto += ", que incluye " + ", ".join(c["nombre"] for c in ciudades)
    return texto + ". El espacio aéreo correspondiente forma parte del área."


def _postura(objetivos: list[Objetivo]) -> str:
    ofensivos = sum(1 for o in objetivos if o.tipo in ("destruir", "neutralizar", "ocupar"))
    defensivos = sum(1 for o in objetivos if o.tipo == "proteger")
    return "ofensiva" if ofensivos > defensivos else "defensiva"


def _nombres(objs: list[Objetivo], maximo: int = 4) -> str:
    nombres = [o.nombre[0].lower() + o.nombre[1:] for o in objs[:maximo]]
    if not nombres:
        return ""
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _cuando(esc: Escenario) -> str:
    if esc.turno_h:
        ref = calendario.referencia(esc, esc.turno_h)
        if ref["fecha"]:
            return f"a partir del día D ({ref['fecha']}) a la hora H ({ref['hora']})"
        return "a partir del día D a la hora H"
    return "a partir de la recepción de la presente"


def _idea_general(esc: Escenario, postura: str, pais: str, pais_e: str) -> str:
    fases = calendario.fases(esc)
    lineas = []
    if postura == "ofensiva":
        lineas.append(f"El Teatro de Operaciones conducirá una operación ofensiva contra las fuerzas de {pais_e}, con el "
                      "esfuerzo principal inicial en el Componente Aéreo, que debe obtener la superioridad aérea local antes "
                      "de que el Componente Terrestre avance sobre sus objetivos.")
    else:
        lineas.append(f"El Teatro de Operaciones conducirá una operación defensiva para impedir que {pais_e} logre sus "
                      f"objetivos en territorio de {pais}, con el esfuerzo principal en la defensa aérea y en la "
                      "preservación de las bases y de la infraestructura propia, para pasar luego a la contraofensiva.")
    if fases:
        lineas.append("La operación se desarrollará en las siguientes fases:")
        for f in fases:
            desde = calendario.referencia(esc, f["desde"])
            rango = f"desde {desde['hora_h'] or 'el turno ' + str(f['desde'])}"
            if f["hasta"]:
                hasta = calendario.referencia(esc, f["hasta"])
                rango += f" hasta {hasta['hora_h'] or 'el turno ' + str(f['hasta'])}"
            lineas.append(f"- {f['nombre']} ({rango}).")
    return "\n".join(lineas)


def _limitaciones(propios_obj: list[Objetivo], enemigas: list[Unidad], por_id: dict) -> str:
    lineas = ["Restricciones (lo que no se debe hacer):",
              "- No atacar a la población civil ni bienes protegidos por el Derecho Internacional Humanitario.",
              "- No violar el espacio aéreo ni el territorio de terceros países."]
    infra = [u for u in enemigas if _categoria(u) == "infraestructura"]
    if infra:
        lineas.append("- La infraestructura no militar del enemigo (centrales, refinerías, puentes, comunicaciones) solo "
                      "puede atacarse si figura entre los objetivos asignados.")
    lineas.append("Coacciones (lo que se debe hacer):")
    proteger = [por_id[o.unidad_id].nombre for o in propios_obj if o.tipo == "proteger" and o.unidad_id in por_id]
    if proteger:
        lineas.append("- Mantener operativas durante toda la operación: " + ", ".join(proteger) + ".")
    lineas.append("- Mantener en todo momento una reserva de caza para la defensa aérea del territorio propio.")
    return "\n".join(lineas)


def _instrucciones(esc: Escenario) -> str:
    lineas = []
    if esc.turno_h:
        ref = calendario.referencia(esc, esc.turno_h)
        lineas.append(f"- Día D: {ref['fecha'] or 'a determinar'}; hora H: {ref['hora']} (turno {esc.turno_h}).")
    if esc.turno_final:
        lineas.append(f"- Duración prevista del ejercicio: hasta el turno {esc.turno_final}.")
    lineas.append("- El Estado Mayor presentará al comandante la apreciación inicial y las formas de acción antes de "
                  "iniciar la conducción (Fase I del TIEM).")
    lineas.append("- Las comunicaciones se realizan por la red del bando; las consultas al escalón superior, por la red "
                  "de mando (instructor).")
    return "\n".join(lineas)


def generar_contenido(esc: Escenario, unidades: list[Unidad], objetivos: list[Objetivo], bando: str) -> dict:
    """Redacta el Problema Militar Operativo del bando a partir del escenario (no guarda nada)."""
    enemigo = "rojo" if bando == "azul" else "azul"
    rnd = random.Random(f"{esc.semilla}-pmo")
    pais, pais_e = _pais(esc, bando), _pais(esc, enemigo)
    causa = rnd.choice(_CAUSAS).format(e=pais_e)
    por_id = {u.id: u for u in unidades}
    propias = [u for u in unidades if u.bando == bando and u.estado == "activa"]
    enemigas = [u for u in unidades if u.bando == enemigo and u.estado == "activa"]
    mios = [o for o in objetivos if o.bando == bando and o.nivel == "material"]
    postura = _postura(mios)
    # el teatro se nombra por su direccion desde las fuerzas propias hacia las enemigas
    if propias and enemigas:
        centro = lambda us: (sum(u.lat for u in us) / len(us), sum(u.lon for u in us) / len(us))  # noqa: E731
        (la, lo), (le, loe) = centro(propias), centro(enemigas)
        to = f"Teatro de Operaciones {_TEATROS[lugares.rumbo(la, lo, le, loe)]}"
    else:
        to = "Teatro de Operaciones N.º 1"

    if postura == "ofensiva":
        sit = (f"Desde hace varios meses las relaciones entre {pais} y {pais_e} se han deteriorado por {causa}. "
               f"Agotadas las gestiones diplomáticas, y ante la concentración de fuerzas de {pais_e} cerca de la frontera, "
               f"el gobierno de {pais} activó el {to} y ordenó conducir operaciones militares para neutralizar la amenaza "
               "antes de que se materialice.")
        sup_tarea = (f"Conducir operaciones militares conjuntas ofensivas en el {to} {_cuando(esc)}, a fin de neutralizar "
                     f"la capacidad militar de {pais_e} en la zona fronteriza y restablecer la seguridad de {pais}.")
    else:
        sit = (f"Desde hace varios meses las relaciones entre {pais} y {pais_e} se han deteriorado por {causa}. "
               f"{_mayuscula(pais_e)} ha concentrado fuerzas aéreas y terrestres cerca de la frontera y todo indica que "
               f"atacará en los próximos días. El gobierno de {pais} activó el {to} para defender la soberanía nacional.")
        sup_tarea = (f"Conducir operaciones militares conjuntas defensivas en el {to} {_cuando(esc)}, a fin de preservar la "
                     f"soberanía y la integridad territorial de {pais} y crear las condiciones para restablecer la paz.")

    # el "que" de la mision son los objetivos asignados al componente (los efectos que debe lograr)
    asignados = [o for o in objetivos if o.bando == bando and o.nivel == "asignado"
                 and not o.nombre.startswith("Preservar")]
    atacar = [o for o in mios if o.tipo in ("destruir", "neutralizar")]
    if postura == "ofensiva":
        que = _nombres(asignados) or "obtener la superioridad aérea local" + (f" y {_nombres(atacar, 2)}" if atacar else "")
        mision = {
            "tarea": "Conducir operaciones aéreas ofensivas y defensivas",
            "que": "para " + que,
            "donde": f"en el área de operaciones del {to}",
            "cuando": _cuando(esc),
            "proposito": "contribuir a que el Teatro de Operaciones neutralice la capacidad militar de "
                         f"{pais_e} en la zona fronteriza",
        }
    else:
        mision = {
            "tarea": "Conducir operaciones aéreas defensivas y contraofensivas",
            "que": "para impedir que el enemigo obtenga la superioridad aérea" + (f" y {_nombres(asignados)}" if asignados else ""),
            "donde": f"en el área de operaciones del {to}",
            "cuando": _cuando(esc),
            "proposito": f"preservar la libertad de acción de las fuerzas propias y la integridad territorial de {pais}",
        }
    return normalizar({
        "situacion_general": sit,
        "fuerzas_enemigas": _fuerzas_enemigas(enemigas, pais_e),
        "fuerzas_propias": _fuerzas_propias(propias, pais),
        "mision_superior": sup_tarea,
        "idea_general": _idea_general(esc, postura, pais, pais_e),
        "mision": mision,
        "medios": _medios(propias),
        "area_operaciones": _area(unidades),
        "limitaciones": _limitaciones(mios, enemigas, por_id),
        "instrucciones": _instrucciones(esc),
    })


def preparar_calendario(esc: Escenario, hoy: date | None = None) -> None:
    """Si el escenario no tiene calendario: fecha de inicio (la de creacion), H tres turnos despues del actual y
    24 turnos de duracion; las fases salen solas de esos datos."""
    if not esc.fecha_inicio:
        base = hoy or (esc.creado_en.date() if esc.creado_en else date.today())
        esc.fecha_inicio = (base + timedelta(days=1)).isoformat()
    if not esc.turno_h:
        esc.turno_h = max(1, esc.turno_actual) + 2
    if not esc.turno_final:
        esc.turno_final = max(esc.turno_h + 12, 24)


# cadena de objetivos: (clave, nombre, efecto deseado, indicador, umbral %) por categoria del objetivo material
_ASIGNADOS = {
    "aire": ("Obtener la superioridad aérea local",
             "Degradar la capacidad aérea y de defensa aérea del enemigo hasta que no pueda oponerse a las operaciones propias",
             "Bases, radares, antiaéreas y aeronaves enemigas destruidos o neutralizados"),
    "sostenimiento": ("Neutralizar el sostenimiento del enemigo",
                      "Reducir la capacidad del enemigo de abastecer, mover y comunicar a sus fuerzas",
                      "Infraestructura, depósitos y puentes enemigos fuera de servicio"),
    "superficie": ("Neutralizar las fuerzas de superficie enemigas",
                   "Impedir que las fuerzas terrestres y navales enemigas cumplan su misión",
                   "Unidades enemigas de superficie destruidas o neutralizadas"),
    "terreno": ("Apoyar la conquista de los objetivos terrestres",
                "Permitir que las fuerzas propias ocupen y mantengan los puntos clave del terreno",
                "Zonas ocupadas y mantenidas por fuerzas propias"),
    "propio": ("Preservar la capacidad de combate propia",
               "Mantener operativas las bases, los sistemas de defensa aérea y la infraestructura propios",
               "Instalaciones y unidades propias protegidas que siguen operativas"),
}


def _efecto_material(o: Objetivo, por_id: dict) -> str:
    u = por_id.get(o.unidad_id)
    blanco = u.nombre if u is not None else o.nombre
    if o.tipo == "destruir":
        return f"Destrucción o puesta fuera de servicio de {blanco}"
    if o.tipo == "neutralizar":
        return f"{blanco} con {o.umbral if o.umbral is not None else 50:.0f} % de su fuerza o menos"
    if o.tipo == "proteger":
        return f"{blanco} en servicio al final del plazo"
    return f"{o.nombre}: zona ocupada y mantenida por fuerzas propias"


def _clave_asignado(o: Objetivo, unidades: dict) -> str:
    if o.tipo == "proteger":
        return "propio"
    if o.tipo == "ocupar":
        return "terreno"
    u = unidades.get(o.unidad_id)
    cat = _categoria(u) if u is not None else None
    if cat in ("aviacion", "defensa_aerea", "ge"):
        return "aire"
    if cat in ("infraestructura", "logistica"):
        return "sostenimiento"
    return "superficie"


def generar_cadena(db: Session, esc: Escenario, bando: str, unidades: list[Unidad]) -> list[Objetivo]:
    """Agrupa los objetivos materiales del bando bajo objetivos asignados (por efecto) y un objetivo ulterior.

    No toca un bando que ya tiene objetivos asignados o ulteriores. Devuelve los objetivos creados."""
    objs = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id, Objetivo.bando == bando).all()
    if any(o.nivel != "material" for o in objs):
        return []
    materiales = [o for o in objs if o.nivel == "material"]
    if not materiales:
        return []
    por_id = {u.id: u for u in unidades}
    grupos = defaultdict(list)
    for o in materiales:
        grupos[_clave_asignado(o, por_id)].append(o)
    enemigo = "rojo" if bando == "azul" else "azul"
    postura = _postura(materiales)
    pais, pais_e = _pais(esc, bando), _pais(esc, enemigo)
    ulterior = Objetivo(
        escenario_id=esc.id, bando=bando, tipo="efecto", nivel="ulterior", puntos=0, umbral=60.0,
        nombre=(f"Neutralizar la capacidad militar de {pais_e} en la zona fronteriza" if postura == "ofensiva"
                else f"Preservar la integridad territorial de {pais}"),
        efecto="Objetivo del Teatro de Operaciones al que contribuye el Componente Aéreo",
        indicador="Objetivos asignados al Componente Aéreo cumplidos (60 % o más)",
    )
    db.add(ulterior)
    db.flush()
    creados = [ulterior]
    for clave in ("aire", "sostenimiento", "superficie", "terreno", "propio"):
        hijos = grupos.get(clave)
        if not hijos:
            continue
        nombre, efecto, indicador = _ASIGNADOS[clave]
        umbral = 100.0 if len(hijos) == 1 else 75.0
        asignado = Objetivo(escenario_id=esc.id, bando=bando, tipo="efecto", nivel="asignado", padre_id=ulterior.id,
                            nombre=nombre, efecto=efecto, puntos=20, umbral=umbral,
                            indicador=f"{indicador} ({umbral:.0f} % de {len(hijos)})")
        db.add(asignado)
        db.flush()
        creados.append(asignado)
        for o in hijos:
            o.padre_id = asignado.id
            if not o.efecto:
                o.efecto = _efecto_material(o, por_id)
    return creados


def generar(db: Session, esc: Escenario, bandos=BANDOS, sobrescribir: bool = False, calendario_auto: bool = True,
            cadena: bool = True, hoy: date | None = None) -> dict:
    """Crea la situacion automaticamente: calendario (si falta), cadena de objetivos y PMO de cada bando.

    Un PMO redactado por el instructor no se reemplaza salvo con `sobrescribir`. Devuelve lo que hizo."""
    hecho = {"calendario": False, "objetivos": 0, "pmo": []}
    if calendario_auto and not (esc.turno_h and esc.fecha_inicio and esc.turno_final):
        preparar_calendario(esc, hoy)
        hecho["calendario"] = True
    unidades = db.query(Unidad).filter(Unidad.escenario_id == esc.id).order_by(Unidad.id).all()
    if cadena:
        for b in bandos:
            hecho["objetivos"] += len(generar_cadena(db, esc, b, unidades))
    objetivos = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).order_by(Objetivo.id).all()
    for b in bandos:
        pm = obtener(db, esc, b)
        if pm is not None and pm.origen == "instructor" and not sobrescribir:
            continue
        guardar(db, esc, b, generar_contenido(esc, unidades, objetivos, b), "automatico")
        hecho["pmo"].append(b)
    return hecho
