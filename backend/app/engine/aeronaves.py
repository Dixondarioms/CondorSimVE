"""Despegue de grupos aereos desde una base aerea o un portaaviones.

Un portaaviones es una base aerea movil: solo opera aeronaves embarcables (helicopteros, drones y cazas
embarcados), tiene menos plazas y las aeronaves estacionadas a bordo se mueven, sufren y se hunden con el.

Un alumno emite la orden `despegar` sobre una base aerea propia eligiendo el modelo (F-16, Su-30...), el numero
de aeronaves y un indicativo. Al resolverse el turno nace una unidad aerea junto a la base, con el combustible
y la municion llenos; puede recibir ordenes desde el turno siguiente. El instructor puede ubicar grupos
directamente (POST /unidades con `modelo`) sin pasar por este limite.
"""

import json

from sqlalchemy.orm import Session

from app.engine import catalogo, geo, logistica
from app.models.orden import Orden
from app.models.unidad import Unidad

FUERZA_MINIMA_BASE = 25.0  # una base muy danada no puede lanzar grupos (ni reabastecer)
DESPLAZAMIENTO_GRADOS = 0.018  # el grupo aparece ~2 km al noreste de la base para poder seleccionarlo


def codificar(modelo: str, aeronaves: int, indicativo: str) -> str:
    return json.dumps({"modelo": modelo, "aeronaves": aeronaves, "indicativo": indicativo}, ensure_ascii=False)


def decodificar(detalle: str) -> dict:
    try:
        d = json.loads(detalle or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def es_dron_modelo(modelo_id: str | None) -> bool:
    m = catalogo.MODELOS.get(modelo_id or "")
    return bool(m and catalogo.CLASES[m.clase].dron)


def aeronaves_en_servicio(unidades, drones: bool = False) -> int:
    """Aeronaves activas tripuladas (o, con drones=True, drones activos): cada categoria tiene su tope. Los misiles
    de crucero en vuelo no cuentan para ninguno."""
    return sum(
        max(1, u.aeronaves or 1) for u in unidades
        if u.tipo == "aerea" and u.estado == "activa" and catalogo.obtener(u.clase, u.tipo).dron == drones
        and not catalogo.es_misil(u)
    )


def aeronaves_comprometidas(
    db: Session, escenario_id: int, bando: str, excluir_orden_id: int | None = None, drones: bool = False
) -> int:
    """Aeronaves (o drones) activas del bando mas las de los despegues pendientes, para respetar el tope al emitir."""
    unidades = db.query(Unidad).filter(Unidad.escenario_id == escenario_id, Unidad.bando == bando).all()
    total = aeronaves_en_servicio(unidades, drones)
    por_id = {u.id: u for u in unidades}
    pendientes = db.query(Orden).filter(
        Orden.escenario_id == escenario_id, Orden.tipo == "despegar", Orden.estado == "pendiente"
    )
    for o in pendientes:
        datos = decodificar(o.detalle)
        if o.id != excluir_orden_id and o.unidad_id in por_id and es_dron_modelo(datos.get("modelo")) == drones:
            total += int(datos.get("aeronaves", 0) or 0)
    return total


MOTIVO_NO_EMBARCABLE = "solo helicopteros, drones y cazas embarcados operan desde un portaaviones"


def error_de_despegue(base: Unidad, modelo_id: str | None, aeronaves: int | None, en_servicio: int) -> str | None:
    """Motivo por el que la base (aerea o portaaviones) no puede lanzar ese grupo (None si puede)."""
    if not catalogo.opera_aeronaves(base):
        return "Solo una base aerea o un portaaviones puede lanzar grupos de caza."
    if base.estado != "activa":
        return "La base aerea ya no esta activa." if base.tipo == "base" else f"{base.nombre} ya no esta activo."
    if base.fuerza < FUERZA_MINIMA_BASE:
        return f"La base esta muy danada ({base.fuerza:.0f}%): no puede lanzar grupos."
    modelo = catalogo.MODELOS.get(modelo_id or "")
    if modelo is None:
        return "Elija un modelo de aeronave del catalogo."
    if catalogo.CLASES[modelo.clase].misil:
        return "Los misiles de crucero no despegan de una base: se lanzan con la orden lanzar."
    if catalogo.es_portaaviones(base) and not catalogo.modelo_embarcable(modelo):
        return f"{modelo.nombre} no puede despegar de un portaaviones: {MOTIVO_NO_EMBARCABLE}."
    if not aeronaves or not 1 <= aeronaves <= catalogo.MAX_AERONAVES_GRUPO:
        return f"Un grupo tiene entre 1 y {catalogo.MAX_AERONAVES_GRUPO} aeronaves."
    falta = logistica.falta_para_despegue(base, aeronaves)
    if falta:
        return falta
    if es_dron_modelo(modelo.id):
        if en_servicio + aeronaves > catalogo.MAX_DRONES_BANDO:
            return (f"Tope de {catalogo.MAX_DRONES_BANDO} drones por bando "
                    f"({en_servicio} ya en servicio o comprometidos).")
    elif en_servicio + aeronaves > catalogo.MAX_AERONAVES_BANDO:
        return (f"Tope de {catalogo.MAX_AERONAVES_BANDO} aeronaves por bando "
                f"({en_servicio} ya en servicio o comprometidas).")
    return None


def crear_grupo(base: Unidad, modelo_id: str, aeronaves: int, indicativo: str, ya_lanzados_en_base: int = 0) -> Unidad:
    """Unidad aerea nueva junto a la base (sin agregarla a la sesion: lo hace quien llama)."""
    m = catalogo.MODELOS[modelo_id]
    clase = catalogo.CLASES[m.clase]
    escalon = catalogo.escalon_grupo(aeronaves)
    nombre = (indicativo or "").strip() or f"{m.corto} de {base.nombre}"
    return Unidad(
        escenario_id=base.escenario_id, nombre=nombre[:120], bando=base.bando, tipo="aerea", clase=clase.id,
        modelo=m.id, aeronaves=aeronaves, echelon=escalon,
        lat=base.lat + DESPLAZAMIENTO_GRADOS, lon=base.lon + DESPLAZAMIENTO_GRADOS * (1 + ya_lanzados_en_base),
        fuerza=100.0, velocidad_kmh=m.velocidad_kmh, alcance_km=m.alcance_km, deteccion_km=m.deteccion_km,
        combustible=100.0, municion=100.0, autonomia_km=m.autonomia_km,
        sidc=catalogo.generar_sidc(base.bando, clase, escalon), estado="activa",
    )


# ---------------------------------------------------------------------------------------------------------
# Ciclo de vuelo: aterrizar en una base propia, esperar el reabastecimiento, despegar, patrullar
# ---------------------------------------------------------------------------------------------------------
TIEMPO_REARME_TURNOS = 2  # turnos en tierra antes de poder despegar (reabastecer y rearmar)
CAPACIDAD_BASE = 12  # aeronaves que caben estacionadas en una base
RADIO_ATERRIZAJE_KM = 3.0  # distancia a la base para considerar que aterrizo
COMBUSTIBLE_LOITER = 8.0  # puntos de combustible por turno que gasta una patrulla sobre su punto
COMBUSTIBLE_CRITICO = 25.0  # una patrulla con menos regresa sola a la base mas cercana
PERDIDA_EN_TIERRA = 0.6  # fraccion del dano a la base que sufren los aviones estacionados en ella
DESPLAZAMIENTO_ESTACIONADO = 0.006  # grados: los aviones estacionados no se dibujan encima de la base


def en_vuelo(u) -> bool:
    return u.tipo == "aerea" and u.estado == "activa" and not u.en_tierra


def estacionadas(base, unidades) -> list:
    return [u for u in unidades if u.en_tierra and u.base_id == base.id and u.estado == "activa"]


def capacidad(base) -> int:
    """Plazas de estacionamiento de una base aerea (12) o de un portaaviones (10)."""
    return catalogo.plazas_aeronaves(base) or CAPACIDAD_BASE


def plazas_libres(base, unidades) -> int:
    return capacidad(base) - sum(max(1, u.aeronaves or 1) for u in estacionadas(base, unidades))


def puede_operar_en(u, base) -> bool:
    """La aeronave `u` puede aterrizar en (y despegar de) `base`: una base aerea recibe a todas; un portaaviones,
    solo a las embarcables. Los misiles no aterrizan."""
    if catalogo.es_misil(u) or not catalogo.opera_aeronaves(base):
        return False
    return not catalogo.es_portaaviones(base) or catalogo.es_embarcable(u.clase, u.modelo)


def error_de_aterrizaje(u, base, unidades) -> str | None:
    """Motivo por el que `u` no puede aterrizar en `base` (None si puede)."""
    if u.tipo != "aerea" or u.estado != "activa":
        return "Solo una aeronave activa puede aterrizar."
    if catalogo.es_misil(u):
        return "Un misil en vuelo no admite ordenes."
    if u.en_tierra:
        return "La aeronave ya esta en tierra."
    if base is None or base.bando != u.bando or not catalogo.opera_aeronaves(base):
        return "Elija una base aerea propia o un portaaviones propio."
    if not puede_operar_en(u, base):
        return f"{u.nombre} no puede aterrizar en {base.nombre}: {MOTIVO_NO_EMBARCABLE}."
    if base.estado != "activa" or base.fuerza < FUERZA_MINIMA_BASE:
        return f"{base.nombre} esta fuera de servicio o muy danada."
    if plazas_libres(base, unidades) < max(1, u.aeronaves or 1):
        return f"{base.nombre} no tiene plazas libres (capacidad {capacidad(base)} aeronaves)."
    return None


def base_mas_cercana(u, unidades):
    """Base aerea (o portaaviones, si la aeronave es embarcable) propia en servicio y con plazas, la mas cercana
    (None si no hay ninguna)."""
    candidatas = [
        b for b in unidades
        if b.bando == u.bando and b.estado == "activa" and b.fuerza >= FUERZA_MINIMA_BASE and puede_operar_en(u, b)
        and plazas_libres(b, unidades) >= max(1, u.aeronaves or 1)
    ]
    return min(candidatas, key=lambda b: geo.distancia_km(u.lat, u.lon, b.lat, b.lon), default=None)


def aterrizar(u, base, estacionados_antes: int = 0) -> None:
    """La aeronave queda estacionada junto a la base y empieza el reabastecimiento."""
    u.en_tierra = True
    u.base_id = base.id
    u.espera_restante = TIEMPO_REARME_TURNOS
    u.mision, u.mision_lat, u.mision_lon = "", None, None
    u.lat = base.lat + DESPLAZAMIENTO_ESTACIONADO * (1 + estacionados_antes)
    u.lon = base.lon + DESPLAZAMIENTO_ESTACIONADO


def despegar_unidad(u) -> None:
    u.en_tierra = False
    u.base_id = None
    u.espera_restante = 0


def seguir_portaaviones(unidades) -> None:
    """Las aeronaves estacionadas en un portaaviones se mueven con el (despues del movimiento del turno)."""
    for pa in unidades:
        if pa.estado != "activa" or not catalogo.es_portaaviones(pa):
            continue
        for i, x in enumerate(estacionadas(pa, unidades)):
            x.lat = pa.lat + DESPLAZAMIENTO_ESTACIONADO * (1 + i)
            x.lon = pa.lon + DESPLAZAMIENTO_ESTACIONADO
