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

Cóndor (tiempo real): cada misil vuela por separado (`crear_misiles`: una unidad por misil, con el tamaño de su salva y
su probabilidad de impacto en `armamento_json`). Al llegar impacta con su probabilidad (PK_MISIL) y hace su parte del
daño que la tabla de combate le asigna a la salva completa (decision del usuario: si todos impactan, como antes). La
defensa de punto de los buques (DEFENSA_PUNTO: canales, alcance y probabilidad) los derriba de a uno: una salva grande
satura los canales y pasan mas. Los misiles antibuque que tiran las aeronaves (Harpoon, Exocet, Kh-35) tambien vuelan.
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
    "fremm": "exocet", "scorpene": "exocet", "tamandare": "exocet", "type21": "exocet",
    "type052d": "yj18", "type054a": "yj83", "sovremenny": "moskit", "molniya": "moskit", "lupo": "otomat",
    "kuznetsov": "granit",
}
# modelos de una clase que lanza misiles pero que en la realidad no los tienen (solo cañones, antiaereos o torpedos)
SIN_MISILES = frozenset({"type42", "rothesay", "u209", "type212"})


def lanza(u) -> bool:
    """La unidad puede lanzar misiles de crucero o antibuque: los de su modelo (aunque su clase no los lance, como las
    corbetas lanzamisiles o el Kuznetsov) o los de su clase, salvo los modelos que no los tienen."""
    modelo = getattr(u, "modelo", "") or ""
    if modelo in SIN_MISILES:
        return False
    if modelo in MISIL_DEL_LANZADOR:
        return True
    return bool(catalogo.obtener(getattr(u, "clase", None), getattr(u, "tipo", "")).lanza_misiles)


PK_MISIL = {"crucero": 0.85, "kalibr": 0.85, "brahmos": 0.85, "exocet": 0.8, "harpoon": 0.8, "oniks": 0.8, "kh35": 0.8,
            "nsm": 0.85, "yj18": 0.85, "yj83": 0.8, "moskit": 0.8, "otomat": 0.8, "granit": 0.8}
PK_POR_DEFECTO = 0.8
MISIL_DEL_ARMA = {"HPN": "harpoon", "EXO": "exocet", "MA6": "kh35"}  # antibuque de las aeronaves (engine/armas.py)
# defensa de punto de los buques: canales de tiro simultaneos, alcance (km), probabilidad por disparo y ciclo (s)
DEFENSA_PUNTO = {
    "destructor": {"canales": 4, "km": 12.0, "pk": 0.5},
    "fragata": {"canales": 2, "km": 8.0, "pk": 0.45},
    "portaaviones": {"canales": 2, "km": 6.0, "pk": 0.4},
    "patrullero": {"canales": 1, "km": 4.0, "pk": 0.3},
    "buque_desembarco": {"canales": 1, "km": 4.0, "pk": 0.3},
}
# buques de las operaciones historicas sin defensa de punto moderna (1982: sin cañones de tiro rapido; el Sea Dart y
# el Sea Cat casi no podian con misiles rozaolas)
DEFENSA_PUNTO_MODELO = {
    "type42": {"canales": 1, "km": 6.0, "pk": 0.15}, "invincible": {"canales": 1, "km": 6.0, "pk": 0.15},
    "type21": {"canales": 1, "km": 4.0, "pk": 0.1}, "rothesay": {"canales": 1, "km": 4.0, "pk": 0.1},
    "hermes": {"canales": 1, "km": 4.0, "pk": 0.1},
}
CICLO_PUNTO_S = 10.0  # cada canal tira una vez por este tiempo


def defensa_punto(buque) -> dict | None:
    """Canales, alcance y probabilidad de la defensa de punto de ese buque (por su modelo o por su clase)."""
    return DEFENSA_PUNTO_MODELO.get(getattr(buque, "modelo", "") or "") or DEFENSA_PUNTO.get(getattr(buque, "clase", "") or "")


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
    if not lanza(lanzador):
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


def salva_de(m) -> dict:
    """{"salva": n, "pk": p} de un misil del Cóndor ({} en las salvas de un solo bloque, anteriores)."""
    try:
        d = json.loads(getattr(m, "armamento_json", None) or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) and "salva" in d else {}


def crear_misiles(lanzador, blanco, misiles: int, modelo_id: str | None = None) -> list:
    """Una unidad por misil, en abanico sobre el lanzador (sin agregarlas a la sesion)."""
    m = catalogo.MODELOS[modelo_id] if modelo_id else modelo_misil(lanzador)
    clase = catalogo.CLASES[m.clase]
    pk = PK_MISIL.get(m.id, PK_POR_DEFECTO)
    salida = []
    for i in range(misiles):
        u = Unidad(
            escenario_id=lanzador.escenario_id, nombre=f"{m.corto} {i + 1}/{misiles} de {lanzador.nombre}"[:120],
            bando=lanzador.bando, tipo="aerea", clase=clase.id, modelo=m.id, aeronaves=1, echelon="",
            lat=lanzador.lat + DESPLAZAMIENTO_GRADOS * (i % 3), lon=lanzador.lon + DESPLAZAMIENTO_GRADOS * (i // 3),
            fuerza=100.0, velocidad_kmh=m.velocidad_kmh, alcance_km=m.alcance_km, deteccion_km=m.deteccion_km,
            combustible=100.0, municion=100.0, autonomia_km=m.autonomia_km, en_tierra=False,
            blanco_id=blanco.id, mision="impacto", mision_lat=blanco.lat, mision_lon=blanco.lon,
            sidc=catalogo.generar_sidc(lanzador.bando, clase), estado="activa",
        )
        u.armamento_json = json.dumps({"salva": misiles, "pk": pk})
        salida.append(u)
    return salida


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
