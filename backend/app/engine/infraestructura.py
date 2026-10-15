"""Infraestructura no militar y su peso en la conduccion de la guerra.

Centrales termoelectricas e hidroelectricas, refinerias, centros de comunicaciones y puentes son unidades fijas de
un bando (clases con `infraestructura` en engine/catalogo.py): no se mueven ni combaten, pero se las puede atacar,
proteger o fijar como objetivo, y su estado cambia lo que el bando puede hacer:

- energia (centrales): sin electricidad, los radares fijos del bando trabajan con generadores de respaldo y pierden
  alcance (al 50 % con toda la generacion perdida).
- combustible (refinerias): los depositos del bando reponen menos combustible cada turno (al 25 % sin refinacion: lo
  que queda son las reservas estrategicas).
- comunicaciones (centros de comunicaciones): mas ordenes del bando no llegan a tiempo (hasta 30 puntos mas, aunque el
  instructor no haya activado la demora).
- puentes: con menos del 50 % de fuerza el puente queda cortado y ninguna unidad terrestre cruza por el (los
  ingenieros pueden tender un vado o un puente al lado).

La capacidad de una categoria es la fuerza media de las instalaciones de ese bando (una destruida cuenta 0). Si el
bando no tiene instalaciones de una categoria, esa categoria no le afecta: el ejercicio decide que infraestructura
importa poniendola en el mapa.
"""

from types import SimpleNamespace

from app.engine import catalogo

CATEGORIAS = ("energia", "combustible", "comunicaciones", "puente")
NOMBRE = {"energia": "Energía eléctrica", "combustible": "Refinación de combustible",
          "comunicaciones": "Comunicaciones", "puente": "Puentes"}
RADAR_CON_RESPALDO = 0.5  # alcance de los radares fijos sin ninguna generacion
COMBUSTIBLE_RESERVA = 0.25  # reposicion de combustible de los depositos sin ninguna refinacion
DEMORA_SIN_COMUNICACIONES_PCT = 30  # puntos de demora de ordenes con todos los centros de comunicaciones caidos
PUENTE_OPERATIVO = 50.0  # fuerza minima para que un puente siga transitable
RADIO_PUENTE_KM = 1.0  # tramo que corta un puente sin largo indicado
CAMBIO_NOTABLE = 5.0  # puntos de capacidad que justifican avisar al bando


def categoria(u) -> str:
    return catalogo.obtener(getattr(u, "clase", None), u.tipo).infraestructura


def es_infraestructura(u) -> bool:
    return bool(categoria(u))


def _fuerza(u) -> float:
    return 0.0 if getattr(u, "estado", "activa") == "destruida" else max(0.0, min(100.0, u.fuerza or 0.0))


def capacidad(unidades, bando: str, cat: str) -> float | None:
    """Capacidad (0 a 1) de esa categoria para el bando; None si el bando no tiene instalaciones de esa categoria."""
    propias = [u for u in unidades if u.bando == bando and categoria(u) == cat]
    if not propias:
        return None
    return sum(_fuerza(u) for u in propias) / (100.0 * len(propias))


def factor_radar(unidades, bando: str) -> float:
    cap = capacidad(unidades, bando, "energia")
    return 1.0 if cap is None else RADAR_CON_RESPALDO + (1 - RADAR_CON_RESPALDO) * cap


def factor_combustible(unidades, bando: str) -> float:
    cap = capacidad(unidades, bando, "combustible")
    return 1.0 if cap is None else COMBUSTIBLE_RESERVA + (1 - COMBUSTIBLE_RESERVA) * cap


def demora_extra_pct(unidades, bando: str) -> float:
    cap = capacidad(unidades, bando, "comunicaciones")
    return 0.0 if cap is None else DEMORA_SIN_COMUNICACIONES_PCT * (1 - cap)


def cortado(u) -> bool:
    return categoria(u) == "puente" and _fuerza(u) < PUENTE_OPERATIVO


def cortes(unidades) -> list:
    """Puentes cortados, como obras de tipo "corte" para engine/movimiento.py (anulan el puente de la carretera)."""
    return [SimpleNamespace(tipo="corte", lat=u.lat, lon=u.lon, radio_km=u.radio_km or RADIO_PUENTE_KM, nombre=u.nombre)
            for u in unidades if cortado(u)]


def efecto(cat: str, cap: float) -> str:
    """Lo que significa para el bando esa capacidad, en una frase."""
    if cat == "energia":
        return f"radares fijos al {100 * (RADAR_CON_RESPALDO + (1 - RADAR_CON_RESPALDO) * cap):.0f} % de su alcance"
    if cat == "combustible":
        return f"los depósitos reponen el {100 * (COMBUSTIBLE_RESERVA + (1 - COMBUSTIBLE_RESERVA) * cap):.0f} % del combustible"
    if cat == "comunicaciones":
        extra = DEMORA_SIN_COMUNICACIONES_PCT * (1 - cap)
        return "sin demoras por esta causa" if extra < 0.5 else f"+{extra:.0f} % de órdenes que no llegan a tiempo"
    return ""


def resumen(unidades, bando: str) -> list[dict]:
    """Estado de cada categoria que el bando tiene en el ejercicio, con sus instalaciones."""
    filas = []
    for cat in CATEGORIAS:
        propias = [u for u in unidades if u.bando == bando and categoria(u) == cat]
        if not propias:
            continue
        cap = capacidad(unidades, bando, cat)
        cortados = [u.nombre for u in propias if cortado(u)]
        filas.append({
            "categoria": cat, "nombre": NOMBRE[cat], "capacidad_pct": round(100 * cap, 1),
            "efecto": (f"{len(cortados)} cortado(s): {', '.join(cortados)}" if cortados else "todos transitables")
            if cat == "puente" else efecto(cat, cap),
            "instalaciones": [{"id": u.id, "nombre": u.nombre, "clase": u.clase, "fuerza": round(_fuerza(u), 1),
                               "estado": "cortado" if cortado(u) else u.estado} for u in propias],
        })
    return filas


def estado(unidades) -> dict:
    """{(bando, categoria): capacidad} y los puentes cortados, para comparar antes y despues de un turno."""
    caps = {}
    for bando in ("azul", "rojo"):
        for cat in CATEGORIAS:
            cap = capacidad(unidades, bando, cat)
            if cap is not None:
                caps[(bando, cat)] = cap
    return {"capacidades": caps, "cortados": {u.id for u in unidades if cortado(u)}}


def avisos(antes: dict, despues: dict, unidades) -> list[tuple[str, str]]:
    """(bando, texto) de los cambios notables de la infraestructura en el turno."""
    por_id = {u.id: u for u in unidades}
    salida = []
    for (bando, cat), cap in despues["capacidades"].items():
        if cat == "puente":
            continue
        previa = antes["capacidades"].get((bando, cat))
        if previa is None or abs(cap - previa) * 100 < CAMBIO_NOTABLE:
            continue
        verbo = "cae" if cap < previa else "se recupera"
        salida.append((bando, f"{NOMBRE[cat]}: la capacidad {verbo} al {100 * cap:.0f} %: {efecto(cat, cap)}."))
    for uid in despues["cortados"] - antes["cortados"]:
        u = por_id[uid]
        salida.append((u.bando, f"{u.nombre} quedó cortado: ninguna unidad terrestre puede cruzar por él."))
    return salida
