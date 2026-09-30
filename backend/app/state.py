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
from app.engine import clima as clima_mod
from app.engine import guerra_electronica as ge_mod
from app.engine import misiones as misiones_mod
from app.engine import objetivos as objetivos_mod
from app.engine.vision import unidades_visibles
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
    "carga", "recarga_restante", "despliegue_restante", "modelo", "aeronaves",
    "base_id", "espera_restante", "mision", "mision_lat", "mision_lon", "blanco_id",
    "emitiendo", "fuego_libre", "stock_combustible", "stock_municion", "dano_pista", "dano_plataforma", "dano_combustible", "refugios",
    "transporte_id",
)
CAMPOS_SOLO_INSTRUCTOR = ("com_latencia_ms", "com_jitter_ms", "com_perdida_pct")


def es_bando(rol: str) -> bool:
    return rol in BANDOS


def unidades_visibles_para(
    db: Session, escenario: Escenario, rol: str, terreno: Terreno | None = None
) -> list[Unidad]:
    unidades = db.query(Unidad).filter(Unidad.escenario_id == escenario.id).all()
    if not es_bando(rol) or not getattr(escenario, "niebla", True):
        return [u for u in unidades if not es_bando(rol) or getattr(u, "transporte_id", None) is None or u.bando == rol]
    return unidades_visibles(unidades, rol, terreno or get_terreno(), clima_mod.contexto(db, escenario), ge_mod.contexto(db, escenario))


def grafico_visible(bando_grafico: str, rol: str) -> bool:
    """Los graficos son del bando que los traza; los "todos" (neutrales) los ve cualquiera y
    quien no es de un bando (instructor, observador) ve todos."""
    return bando_grafico == "todos" or not es_bando(rol) or bando_grafico == rol


def serializar_grafico(g: Grafico) -> dict:
    return GraficoOut(
        id=g.id, bando=g.bando, tipo=g.tipo, etiqueta=g.etiqueta, geometria=json.loads(g.geojson),
        autor=g.autor_nombre, turno=g.turno,
    ).model_dump()


def serializar_objetivo(o: Objetivo, unidades: dict) -> dict:
    u = unidades.get(o.unidad_id) if o.unidad_id else None
    return ObjetivoOut(
        id=o.id, bando=o.bando, tipo=o.tipo, nombre=o.nombre, puntos=o.puntos, lat=o.lat, lon=o.lon,
        radio_km=o.radio_km, turnos_requeridos=o.turnos_requeridos, progreso=o.progreso, unidad_id=o.unidad_id,
        unidad_nombre=u.nombre if u else "", hasta_turno=o.hasta_turno, estado=o.estado, turno_resuelto=o.turno_resuelto,
    ).model_dump()


def objetivos_para(db: Session, escenario: Escenario, rol: str) -> list[dict]:
    """Cada bando ve solo sus objetivos; instructor y observador, todos."""
    por_id = {u.id: u for u in db.query(Unidad).filter(Unidad.escenario_id == escenario.id)}
    lista = db.query(Objetivo).filter(Objetivo.escenario_id == escenario.id).order_by(Objetivo.id)
    return [serializar_objetivo(o, por_id) for o in lista if not es_bando(rol) or o.bando == rol]


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


def estado_para(
    db: Session, escenario: Escenario, rol: str, terreno: Terreno | None = None
) -> dict:
    terreno = terreno or get_terreno()
    unidades = unidades_visibles_para(db, escenario, rol, terreno)

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
            contactos.append({
                "unidad_id": u.id, "nombre": u.nombre, "tipo": u.tipo, "clase": u.clase,
                "sidc": u.sidc, "lat": c.lat, "lon": c.lon, "turno_visto": c.turno_visto,
            })
    ordenes = q_ordenes.order_by(Orden.id).all()
    eventos = q_eventos.order_by(Evento.id.desc()).limit(20).all()
    obras = _obras_visibles(db, escenario, rol, unidades)
    graficos = [
        g for g in db.query(Grafico).filter(Grafico.escenario_id == escenario.id).order_by(Grafico.id)
        if grafico_visible(g.bando, rol)
    ]

    unidades_out = []
    for u in unidades:
        d = UnidadOut.model_validate(u).model_dump()
        d["terreno"] = terreno.clase(u.lat, u.lon)
        if es_bando(rol) and u.bando != rol:
            for oculto in CAMPOS_OCULTOS:
                d[oculto] = None
        unidades_out.append(d)

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
        "marcador": objetivos_mod.marcador(db, escenario),
        "ordenes": [OrdenOut.model_validate(o).model_dump() for o in ordenes],
        "eventos": [EventoOut.model_validate(e).model_dump() for e in eventos],
    }


def catalogo_publico() -> list[dict]:
    return [catalogo.como_dict(c) for c in catalogo.CLASES.values()]


def modelos_publicos() -> list[dict]:
    return [catalogo.modelo_dict(m) for m in catalogo.MODELOS.values()]
