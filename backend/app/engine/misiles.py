"""Misiles de crucero: la orden `lanzar` y el vuelo guiado de cada salva.

Un buque (fragata, destructor, submarino) o una bateria costera con `lanza_misiles` emite `lanzar` contra una
unidad enemiga que su bando ve, con 1 a 4 misiles (cada uno cuesta el 25 % de la municion del lanzador). Al
resolverse el turno (fase 0, junto a los despegues) nace una unidad aerea de clase `misil_crucero` sobre el
lanzador: la salva (`aeronaves` = misiles, rinde como un grupo aereo), con el combustible lleno, su blanco en
`blanco_id` y la mision "impacto".

La salva es autonoma: no admite ordenes. En la fase 1 vuela hacia la posicion ACTUAL de su blanco (guiada) y, si
lo tiene a su alcance, se registra un ataque "impacto". Si el blanco desaparecio, vuela al ultimo punto conocido
(mision_lat/lon) y se pierde alli. Sin combustible, se pierde. Antes del impacto (fase 3) la antiaerea y las
patrullas enemigas pueden derribarla: sus perdidas se aplican primero y, si llega a 0, no impacta. No aterriza, no se
reabastece y no cuenta para los topes de aeronaves del bando.
"""

import json

from app.engine import catalogo, geo, movimiento
from app.models.unidad import Unidad

MODELO = "crucero"
MUNICION_POR_MISIL = 25.0  # % de la municion del lanzador por cada misil
MAX_MISILES = 4
LLEGADA_KM = 1.0
DESPLAZAMIENTO_GRADOS = 0.004  # las salvas del mismo lanzador no nacen encima unas de otras
MOTIVO_SIN_ORDENES = "Un misil en vuelo no admite ordenes."
# misil que lanza cada modelo de lanzador (catalogo_ampliado.py); los demas lanzan el de siempre (MODELO: Tomahawk)
MISIL_DEL_LANZADOR = {
    "grigorovich": "kalibr", "buyan_m": "kalibr", "kilo636": "kalibr",
    "bastion_p": "oniks", "bal_e": "kh35", "nsm_cds": "nsm",
    "fremm": "exocet", "scorpene": "exocet", "tamandare": "exocet",
}


def codificar(misiles: int) -> str:
    return json.dumps({"misiles": misiles})


def decodificar(detalle: str) -> dict:
    try:
        d = json.loads(detalle or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def modelo_misil(lanzador) -> catalogo.Modelo:
    """El misil de crucero o antibuque que dispara ese lanzador."""
    return catalogo.MODELOS[MISIL_DEL_LANZADOR.get(getattr(lanzador, "modelo", "") or "", MODELO)]


def clase_misil() -> catalogo.Clase:
    return catalogo.CLASES[catalogo.MODELOS[MODELO].clase]


def _tipo_efectivo(x) -> str:
    return "terrestre" if x.tipo == "base" or getattr(x, "en_tierra", False) else x.tipo


def blanco_valido(blanco) -> bool:
    """El misil puede seguir y golpear a ese blanco (activo y no una aeronave en vuelo)."""
    return (blanco is not None and blanco.estado == "activa"
            and catalogo.MODELOS[MODELO].ataque_vs.get(_tipo_efectivo(blanco), 0.0) > 0)


def error_de_lanzamiento(lanzador, blanco, misiles: int | None) -> str | None:
    """Motivo por el que `lanzador` no puede lanzar esa salva contra `blanco` (None si puede)."""
    clase = catalogo.obtener(lanzador.clase, lanzador.tipo)
    if not clase.lanza_misiles:
        return "Esta unidad no puede lanzar misiles de crucero."
    if lanzador.estado != "activa":
        return "El lanzador no esta activo."
    if not misiles or not 1 <= misiles <= MAX_MISILES:
        return f"Una salva tiene entre 1 y {MAX_MISILES} misiles."
    if clase.despliegue_turnos and lanzador.despliegue_restante > 0:
        return f"Desplegando el sistema tras moverse ({lanzador.despliegue_restante} turno(s) quieto)."
    if blanco is None or blanco.bando == lanzador.bando or blanco.estado != "activa":
        return "Blanco invalido o ya fuera de combate."
    if not blanco_valido(blanco):
        return f"Un misil de crucero no puede atacar objetivos de tipo {_tipo_efectivo(blanco)} (aeronaves en vuelo)."
    modelo = modelo_misil(lanzador)
    d = geo.distancia_km(lanzador.lat, lanzador.lon, blanco.lat, blanco.lon)
    if d > modelo.autonomia_km:
        return f"Blanco fuera del alcance del misil ({d:.0f} km > {modelo.autonomia_km:.0f} km)."
    costo = MUNICION_POR_MISIL * misiles
    if lanzador.municion + 1e-6 < costo:
        return f"Municion insuficiente para {misiles} misil(es) ({lanzador.municion:.0f}% < {costo:.0f}%)."
    return None


def crear_salva(lanzador, blanco, misiles: int, ya_lanzadas: int = 0) -> Unidad:
    """Unidad aerea nueva (la salva) sobre el lanzador (sin agregarla a la sesion: lo hace quien llama)."""
    m = modelo_misil(lanzador)
    clase = catalogo.CLASES[m.clase]
    return Unidad(
        escenario_id=lanzador.escenario_id, nombre=f"{m.corto} x{misiles} de {lanzador.nombre}"[:120],
        bando=lanzador.bando, tipo="aerea", clase=clase.id, modelo=m.id, aeronaves=misiles, echelon="",
        lat=lanzador.lat + DESPLAZAMIENTO_GRADOS * ya_lanzadas, lon=lanzador.lon + DESPLAZAMIENTO_GRADOS * ya_lanzadas,
        fuerza=100.0, velocidad_kmh=m.velocidad_kmh, alcance_km=m.alcance_km, deteccion_km=m.deteccion_km,
        combustible=100.0, municion=100.0, autonomia_km=m.autonomia_km, en_tierra=False,
        blanco_id=blanco.id, mision="impacto", mision_lat=blanco.lat, mision_lon=blanco.lon,
        sidc=catalogo.generar_sidc(lanzador.bando, clase), estado="activa",
    )


def guiar(misil, unidades: dict, terreno, clima: str, obras=()) -> tuple:
    """Vuela la salva un turno hacia su blanco. Devuelve (blanco a impactar o None, combustible gastado, perdida):
    `perdida` es True si llego al ultimo punto conocido sin encontrar el blanco."""
    blanco = unidades.get(misil.blanco_id) if misil.blanco_id else None
    guiado = blanco_valido(blanco) and blanco.bando != misil.bando
    if guiado:
        misil.mision_lat, misil.mision_lon = blanco.lat, blanco.lon
    if misil.mision_lat is None or misil.mision_lon is None:
        return None, 0.0, True
    mov = movimiento.simular(misil, [[misil.mision_lat, misil.mision_lon]], terreno, clima, obras)
    misil.lat, misil.lon = mov.lat, mov.lon
    if guiado and geo.distancia_km(misil.lat, misil.lon, blanco.lat, blanco.lon) <= misil.alcance_km:
        return blanco, mov.combustible_gastado, False
    perdida = not guiado and geo.distancia_km(misil.lat, misil.lon, misil.mision_lat, misil.mision_lon) <= LLEGADA_KM
    return None, mov.combustible_gastado, perdida
