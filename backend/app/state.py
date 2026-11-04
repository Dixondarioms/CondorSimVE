"""Construye el estado del escenario tal como lo debe ver cada rol.

- instructor / observador: vista completa (sin niebla de guerra). El instructor
  puede ademas "ver como" un bando para mostrar en clase lo que ese bando ve.
- azul / rojo: solo sus unidades y las enemigas detectadas (de estas, solo lo
  observable), sus ordenes, los eventos dirigidos a todos o a su bando, los
  ultimos contactos conocidos de unidades enemigas que perdieron de vista, sus
  graficos tacticos y las obras (puentes y vados) propias o enemigas al alcance de su deteccion.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.engine import catalogo, geo
from app.engine import contactos_vivo
from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.engine import misiones as misiones_mod
from app.engine import pmi as pmi_mod
from app.engine import zonas as zonas_mod
from app.engine import aeronaves as aeronaves_mod
from app.engine import armas as armas_mod
from app.engine import contramedidas as contramedidas_mod
from app.engine import enlace as enlace_mod
from app.engine import iff as iff_mod
from app.engine import mar as mar_mod
from app.routers import grupos as grupos_mod
from app.engine import sistemas as sistemas_mod
from app.engine import asw as asw_mod
from app.engine import balisticos as balisticos_mod
from app.engine import minas as minas_mod
from app.engine import objetivos as objetivos_mod
from app.engine import infraestructura as infra_mod
from app.engine import personal as personal_mod
from app.engine import disponibilidad as disp_mod
from app.engine import toe as toe_mod
from app.engine import recobre as recobre_mod
from app.engine import rescate as rescate_mod
from app.engine import inteligencia as intel_mod
from app.engine import warden as warden_mod
from app.engine import transmisiones as trans_mod
from app.engine import apresto as apresto_mod
from app.engine import doctrina as doctrina_mod
from app.engine.vision import cuadro_sensores, unidades_visibles
from app.models.contacto import Contacto
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.grafico import Grafico
from app.models.obra import Obra
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.schemas import EscenarioOut, EventoOut, GraficoOut, ObjetivoOut, ObraOut, OrdenOut, UnidadOut
from app.terreno import Terreno, get_terreno

BANDOS = ("azul", "rojo")
# De una unidad enemiga detectada solo se conoce lo que se ve desde afuera.
CAMPOS_OCULTOS = (
    "fuerza", "velocidad_kmh", "alcance_km", "deteccion_km", "combustible", "municion", "autonomia_km",
    "carga", "armamento", "armamento_texto", "existencias_armas", "sistemas", "profundidad", "balistico", "recarga_restante", "despliegue_restante", "modelo", "aeronaves",
    "base_id", "espera_restante", "mision", "mision_lat", "mision_lon", "blanco_id",
    "emitiendo", "fuego_libre", "stock_combustible", "stock_municion", "dano_pista", "dano_plataforma", "dano_combustible", "refugios",
    "transporte_id", "personal_inicial", "personal_actual", "sistema_da", "pista_largo_m", "pista_util_m", "recorrido",
    "ruta", "orden_id", "doctrina", "apresto", "velocidad_actual", "contramedidas", "enlace", "iff",
)
TURNOS_ORDENES = 3  # ordenes ya resueltas que viajan con el estado (el historial completo esta en el AAR)
CAMPOS_SOLO_INSTRUCTOR = ("com_latencia_ms", "com_jitter_ms", "com_perdida_pct", "com_ordenes_pct", "inteligencia", "apresto")


def es_bando(rol: str) -> bool:
    return rol in BANDOS


def unidades_visibles_para(
    db: Session, escenario: Escenario, rol: str, terreno: Terreno | None = None
) -> list[Unidad]:
    unidades = db.query(Unidad).filter(Unidad.escenario_id == escenario.id).all()
    if not es_bando(rol) or not getattr(escenario, "niebla", True):
        return [u for u in unidades if not es_bando(rol) or getattr(u, "transporte_id", None) is None or u.bando == rol]
    ge = ge_mod.contexto(db, escenario)
    return unidades_visibles(unidades, rol, terreno or get_terreno(), clima_mod.contexto(db, escenario), ge,
                             enlace_mod.para(escenario, unidades, rol, ge))


def grafico_visible(bando_grafico: str, rol: str) -> bool:
    """Los graficos son del bando que los traza; los "todos" (neutrales) los ve cualquiera y
    quien no es de un bando (instructor, observador) ve todos."""
    return bando_grafico == "todos" or not es_bando(rol) or bando_grafico == rol


def serializar_grafico(g: Grafico) -> dict:
    return GraficoOut(
        id=g.id, bando=g.bando, tipo=g.tipo, etiqueta=g.etiqueta, geometria=json.loads(g.geojson),
        autor=g.autor_nombre, turno=g.turno,
    ).model_dump()


def serializar_objetivo(o: Objetivo, unidades: dict, hijos: list[Objetivo] | None = None) -> dict:
    u = unidades.get(o.unidad_id) if o.unidad_id else None
    return ObjetivoOut(
        id=o.id, bando=o.bando, tipo=o.tipo, nombre=o.nombre, puntos=o.puntos, lat=o.lat, lon=o.lon,
        radio_km=o.radio_km, turnos_requeridos=o.turnos_requeridos, progreso=o.progreso, unidad_id=o.unidad_id,
        unidad_nombre=u.nombre if u else "", hasta_turno=o.hasta_turno, estado=o.estado, turno_resuelto=o.turno_resuelto,
        nivel=o.nivel or "material", padre_id=o.padre_id, efecto=o.efecto or "", indicador=o.indicador or "",
        umbral=o.umbral, avance=objetivos_mod.avance_efecto(o, hijos or []) if o.tipo == "efecto" else None,
    ).model_dump()


def objetivos_para(db: Session, escenario: Escenario, rol: str) -> list[dict]:
    """Cada bando ve solo sus objetivos; instructor y observador, todos."""
    por_id = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id)}
    lista = db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id).order_by(Objetivo.id).all()
    hijos: dict[int, list[Objetivo]] = {}
    for o in lista:
        if o.padre_id is not None:
            hijos.setdefault(o.padre_id, []).append(o)
    return [serializar_objetivo(o, por_id, hijos.get(o.id)) for o in lista if not es_bando(rol) or o.bando == rol]


def _obras_visibles(db: Session, escenario: Escenario, rol: str, unidades: list[Unidad]) -> list[Obra]:
    obras = db.query(Obra).filter(
        Obra.escenario_id == escenario.id, Obra.expira_turno >= escenario.turno_actual
    ).all()
    if not es_bando(rol):
        return obras
    detectores = [u for u in unidades if u.bando == rol and u.estado == "activa" and u.deteccion_km]
    return [
        o for o in obras
        if o.bando == rol or any(geo.distancia_km(u.lat, u.lon, o.lat, o.lon) <= u.deteccion_km for u in detectores)
    ]


def _contacto_para(d: dict, db: Session, escenario: Escenario, rol: str, u: Unidad, unidades: list, terreno) -> None:
    """Lo que el bando sabe de un enemigo que ve: etapa, nombre y simbolo, y su posicion aproximada (sin pista todavia,
    porque el reloj no corrio desde que aparecio: desconocido, salvo que se lo vea a ojo)."""
    if contactos_vivo.fija(u) or (contactos_vivo.pista(db, escenario, rol, u.id) is None
                                  and contactos_vivo.a_ojo(unidades, rol, u, terreno)):
        d["etapa"], d["incertidumbre_km"] = "identificado", 0.0
        return
    p = contactos_vivo.pista(db, escenario, rol, u.id)
    t = escenario.sim_segundos or 0.0
    inc = contactos_vivo.incertidumbre(p, u, t)
    d["lat"], d["lon"] = contactos_vivo.aproximar(escenario.semilla, rol, u.id, u.lat, u.lon, inc, t)
    d["incertidumbre_km"] = inc
    contactos_vivo.enmascarar(d, u, p["etapa"] if p else "desconocido")


def _etiqueta_sensor(c: dict, x: Unidad, p: dict | None) -> None:
    etapa = p["etapa"] if p else "desconocido"
    c["etapa"] = etapa
    if etapa == "desconocido":
        c["nombre"], c["clase"] = contactos_vivo.generico(x), None
    elif etapa == "clasificado":
        c["nombre"] = f"{catalogo.obtener(x.clase, x.tipo).nombre} (sin identificar)"


def estado_para(
    db: Session, escenario: Escenario, rol: str, terreno: Terreno | None = None
) -> dict:
    terreno = terreno or get_terreno()
    mar_mod.fijar(escenario)  # estado del mar (engine/mar.py): lo usan los sonares al calcular lo que se ve
    iff_mod.fijar(escenario)  # fuego amigo e IFF (engine/iff.py): el transpondedor se oye
    # el trafico civil que ya salio de la zona (engine/trafico.py) no se muestra
    unidades = [u for u in unidades_visibles_para(db, escenario, rol, terreno) if u.estado != "retirada"]

    q_ordenes = db.query(Orden).filter(Orden.escenario_id == escenario.id)
    q_eventos = db.query(Evento).filter(Evento.escenario_id == escenario.id)
    contactos = []
    if es_bando(rol):
        propias = [u.id for u in unidades if u.bando == rol]
        q_ordenes = q_ordenes.filter(Orden.unidad_id.in_(propias))
        q_eventos = q_eventos.filter(or_(Evento.bando_destino == "todos", Evento.bando_destino == rol))
        visibles = {u.id for u in unidades}
        por_id = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id)}
        for c in db.query(Contacto).filter(Contacto.escenario_id == escenario.id, Contacto.bando == rol):
            u = por_id.get(c.unidad_id)
            if u is None or u.estado == "destruida" or c.unidad_id in visibles:
                continue
            fila = {
                "unidad_id": u.id, "nombre": u.nombre, "tipo": u.tipo, "clase": u.clase,
                "sidc": u.sidc, "lat": c.lat, "lon": c.lon, "turno_visto": c.turno_visto,
            }
            if escenario.niebla:  # lo que el bando sabe de el y cuanto pudo moverse desde que lo vio
                p = contactos_vivo.pista(db, escenario, rol, u.id)
                inc = contactos_vivo.incertidumbre(p, u, escenario.sim_segundos or 0.0, perdido=True)
                visto = (p or {}).get("visto") or 0.0
                fila["lat"], fila["lon"] = contactos_vivo.aproximar(escenario.semilla, rol, u.id, c.lat, c.lon,
                                                                    min(inc, (p or {}).get("inc") or 0.0), visto)
                fila["incertidumbre_km"] = inc
                contactos_vivo.enmascarar(fila, u, p["etapa"] if p else (c.etapa or "desconocido"))
            contactos.append(fila)
    ordenes = (q_ordenes.filter(or_(Orden.estado.in_(("pendiente", "en_ejecucion")), Orden.turno_emitida >= escenario.turno_actual - TURNOS_ORDENES))
               .order_by(Orden.id).all())
    eventos = q_eventos.order_by(Evento.id.desc()).limit(20).all()
    obras = _obras_visibles(db, escenario, rol, unidades)
    graficos = [
        g for g in db.query(Grafico).filter(Grafico.escenario_id == escenario.id).order_by(Grafico.id)
        if grafico_visible(g.bando, rol)
    ]

    unidades_out = []
    red = {b: enlace_mod.para(escenario, unidades, b, ge_mod.contexto(db, escenario)) for b in BANDOS} \
        if getattr(escenario, "enlace_datos", False) else {}
    for u in unidades:
        d = UnidadOut.model_validate(u).model_dump()
        d["terreno"] = terreno.clase(u.lat, u.lon)
        # carga de armamento de las aeronaves y existencias de armas de bases y buques (engine/armas.py)
        d["armamento"] = armas_mod.datos(u) if u.tipo == "aerea" else None
        d["armamento_texto"] = armas_mod.texto(u) if d["armamento"] else ""
        d["existencias_armas"] = armas_mod.resumen_existencias(u, unidades) if armas_mod.deposito_de(u) else None
        d["sistemas"] = sistemas_mod.publico(u)  # daño por sistemas de buques y unidades de tierra
        d["profundidad"] = asw_mod.profundidad(u) if asw_mod.es_submarino(u) else None
        d["balistico"] = balisticos_mod.info(u)  # trayectoria de un misil balistico (engine/balisticos.py)
        d["antimisil"] = balisticos_mod.antimisil(u)
        d["contramedidas"] = contramedidas_mod.publico(u)  # bengalas y chaff o señuelos (engine/contramedidas.py)
        # IFF de la aeronave, solo con el fuego amigo encendido (engine/iff.py)
        d["iff"] = bool(u.iff) if escenario.fuego_amigo and u.tipo == "aerea" and armas_mod.aplica(u) else None
        # en la red de enlace de datos (None: el director no la encendio; engine/enlace.py)
        d["enlace"] = (u.id in red[u.bando]) if red.get(u.bando) is not None and u.estado == "activa" else None
        if u.tipo == "aerea" and armas_mod.aplica(u):  # apresto de la aeronave (engine/aeronaves.py)
            falta = (u.despega_hasta - (escenario.sim_segundos or 0.0)) if u.despega_hasta is not None else None
            d["apresto"] = {"minutos": aeronaves_mod.apresto(u), "nombre": aeronaves_mod.APRESTOS[aeronaves_mod.apresto(u)],
                            "despega_en_min": max(0, round(falta / 60)) if falta is not None and u.en_tierra else None}
        else:
            d["apresto"] = None
        if es_bando(rol) and u.bando != rol:
            for oculto in CAMPOS_OCULTOS:
                d[oculto] = None
            if escenario.niebla:  # clasificacion e incertidumbre del contacto (engine/contactos_vivo.py)
                _contacto_para(d, db, escenario, rol, u, unidades, terreno)
        unidades_out.append(d)

    # personal, infraestructura y cuadro radar: cada bando ve los suyos; instructor y observador, los de ambos
    todas = db.query(Unidad).filter(Unidad.escenario_id == escenario.id).all()
    bandos_propios = [rol] if es_bando(rol) else list(BANDOS)
    clima_ctx = clima_mod.contexto(db, escenario)
    ge_ctx = ge_mod.contexto(db, escenario)
    sensores = []
    for b in bandos_propios:
        for fila in cuadro_sensores(todas, b, terreno, clima_ctx, ge_ctx):
            fila["bando"] = b
            if escenario.niebla:
                for c in fila.get("contactos", []):
                    x = next((u for u in todas if u.id == c["unidad_id"]), None)
                    if x is not None and not contactos_vivo.fija(x):
                        _etiqueta_sensor(c, x, contactos_vivo.pista(db, escenario, b, x.id))
            sensores.append(fila)

    esc = EscenarioOut.model_validate(escenario).model_dump(mode="json")
    if rol != "instructor":
        for k in CAMPOS_SOLO_INSTRUCTOR:
            esc.pop(k, None)
    return {
        "tipo": "estado",
        # Hora del servidor (UTC): el cliente calcula la cuenta regresiva sin fiarse de su reloj.
        "ahora": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "vista": rol if es_bando(rol) else "completa",
        "escenario": esc,
        "unidades": unidades_out,
        "contactos": contactos,
        "obras": [ObraOut.model_validate(o).model_dump() for o in obras],
        # la interferencia no es secreta: el interferido la sufre y el emisor queda localizado
        "interferencias": [ge_mod.serializar(z) for z in ge_mod.contexto(db, escenario).zonas],
        "clima_zonas": [clima_mod.serializar(z) for z in clima_mod.zonas_de(db, escenario)],
        # informes inyectados con posicion todavia vigentes (se dibujan en el mapa del bando destinatario)
        "informes": [
            {"id": e.id, "turno": e.turno, "tipo": e.tipo, "descripcion": e.descripcion, "lat": e.lat, "lon": e.lon,
             "hasta_turno": e.hasta_turno, "fuente": e.fuente or ""}
            for e in q_eventos.filter(Evento.lat.isnot(None), or_(Evento.hasta_turno.is_(None), Evento.hasta_turno >= escenario.turno_actual))
        ],
        # misiones aereas: cada bando solo las suyas (el instructor y el observador, todas)
        "misiones": [misiones_mod.serializar(m) for m in misiones_mod.visibles_para(db, escenario, rol)],
        "graficos": [serializar_grafico(g) for g in graficos],
        "objetivos": objetivos_para(db, escenario, rol),
        # puntos medios de impacto de Inteligencia sobre las pistas enemigas (engine/pmi.py): cada bando, los suyos
        "pmi": pmi_mod.visibles_para(db, escenario, rol),
        "pmi_bases": pmi_mod.bases_conocidas(db, escenario, rol),
        # areas de patrulla y zonas de exclusion y de no vuelo (engine/zonas.py): las propias y las del director
        "zonas": zonas_mod.visibles_para(db, escenario, rol),
        # grupos de tarea del bando (app/routers/grupos.py), sin las unidades perdidas
        "grupos": grupos_mod.para(db, escenario, rol, {u.id for u in unidades if u.estado == "activa"}),
        "sonoboyas": asw_mod.boyas_para(db, escenario, rol),  # guerra antisubmarina (engine/asw.py)
        "minas": minas_mod.campos_para(db, escenario, rol),  # campos de minas que el rol conoce (engine/minas.py)
        "personal": {b: personal_mod.resumen(todas, b) for b in bandos_propios},
        # plantilla de personal por unidad con reservas y milicia, y esfuerzo aereo (engine/toe.py, disponibilidad.py)
        "personal_toe": (partes := {b: toe_mod.partes(todas, escenario, b) for b in bandos_propios}),
        # apresto operacional: grado, PCAO y calificacion de cada unidad (engine/apresto.py)
        "apresto": {b: apresto_mod.resumen(escenario, b, todas, partes[b]) for b in bandos_propios},
        "esfuerzo": {b: disp_mod.resumen(escenario, b, todas) for b in bandos_propios},
        # recuperacion de personal (tripulaciones derribadas) y puntos de recobre operacional
        "derribados": rescate_mod.visibles(escenario, rol, todas),
        "recuperacion": {b: rescate_mod.resumen(escenario, b) for b in bandos_propios},
        "recobre": {b: recobre_mod.estado(todas, b) for b in bandos_propios},
        # inteligencia: satelites e imagenes en proceso, y los objetivos enemigos conocidos por anillo de Warden
        "inteligencia": {b: intel_mod.resumen(escenario, b) for b in bandos_propios},
        "transmisiones": {b: trans_mod.resumen(escenario, b, escenario.turno_actual) for b in bandos_propios},
        "warden": {b: warden_mod.resumen(_conocidos(db, escenario, todas, b, terreno, clima_ctx, ge_ctx), b)
                   for b in bandos_propios},
        "infraestructura": {b: infra_mod.resumen(todas, b) for b in bandos_propios},
        "sensores": sensores,
        # doctrina y reglas de enfrentamiento de cada bando (Cóndor, engine/doctrina.py)
        "doctrina": {b: {"valores": doctrina_mod.de_bando(escenario, b), "texto": doctrina_mod.texto(doctrina_mod.de_bando(escenario, b))}
                     for b in bandos_propios},
        "marcador": objetivos_mod.marcador(db, escenario),
        "ordenes": [OrdenOut.model_validate(o).model_dump() for o in ordenes],
        "eventos": [EventoOut.model_validate(e).model_dump() for e in eventos],
    }


def _conocidos(db: Session, escenario: Escenario, todas: list, bando: str, terreno, clima_ctx, ge_ctx) -> list:
    """[(unidad enemiga, se ve ahora)]: las que el bando ve y las que solo conoce por un contacto anterior."""
    ve = {u.id for u in unidades_visibles(todas, bando, terreno, clima_ctx, ge_ctx, enlace_mod.para(escenario, todas, bando, ge_ctx))
          if u.bando != bando}
    por_id = {u.id: u for u in todas}
    contactos = {c.unidad_id for c in db.query(Contacto).filter(Contacto.escenario_id == escenario.id, Contacto.bando == bando)}
    return [(por_id[i], i in ve) for i in sorted(ve | contactos) if i in por_id]


def catalogo_publico() -> list[dict]:
    return [catalogo.como_dict(c) for c in catalogo.CLASES.values()]


def modelos_publicos() -> list[dict]:
    from app.engine import plataformas

    return [{**catalogo.modelo_dict(m), "ficha": plataformas.ficha_dict(plataformas.ficha_de_modelo(m))}
            for m in catalogo.MODELOS.values()]
