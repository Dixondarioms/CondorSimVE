"""Guerra antisubmarina del Cóndor (como en los simuladores de mando modernos).

Un submarino sumergido no se ve con radar ni a ojo: se lo detecta con sonar.
- Profundidad: a cota periscopica (por defecto) un radar o un vigia lo ven a menos de PERISCOPIO_KM y el sonar a su
  alcance completo; a profundidad no lo ve nadie mas que el sonar, a FACTOR_PROFUNDO de su alcance, y no puede lanzar
  misiles de crucero.
- Sonar de casco de fragatas, destructores y submarinos (SONAR_KM).
- Sonoboyas: los aviones de patrulla maritima (ASW_AVIONES) las siembran (orden «sonoboyas») en un cuadro de 4 boyas
  sobre el punto elegido; cada una escucha BOYA_RADIO_KM durante BOYA_VIDA_S (tabla sonoboyas).
- Sonar de inmersion: un helicoptero antisubmarino (ASW_HELOS) va al punto (orden «sonar»), se queda en vuelo
  estacionario y escucha SONAR_INMERSION_KM mientras mantenga la orden.
- Al atacar (fuego, misiles o torpedos) el submarino se delata: durante EXPUESTO_S se lo ve como a un buque.
- Torpedos (orden «torpedo»): de submarinos, fragatas, destructores y aeronaves antisubmarinas contra buques y
  submarinos que el bando ve, a su alcance (ALCANCE_TORPEDO_KM). Cada torpedo es una unidad que navega hacia su blanco
  a VELOCIDAD_TORPEDO_KMH (tarda lo que tarda) y lo golpea al llegar; si no lo alcanza en su autonomia, se pierde.
"""

from __future__ import annotations

from app.engine import catalogo, geo

PERISCOPIO_KM = 8.0
FACTOR_PROFUNDO = 0.6
SONAR_KM = {"fragata": 25.0, "destructor": 30.0, "submarino": 35.0}
SONAR_INMERSION_KM = 12.0
ESTACIONARIO_KM = 1.5  # el helicoptero escucha con el sonar calado a esta distancia de su punto
BOYA_RADIO_KM = 10.0
BOYA_VIDA_S = 4 * 3600.0
BOYA_SEPARACION_KM = 8.0  # el cuadro cubre su centro aun con el submarino a profundidad
LLEGADA_KM = 3.0
EXPUESTO_S = 600.0
ASW_AVIONES = {"p3c", "p8a"}
ASW_HELOS = {"nh90"}
ALCANCE_TORPEDO_KM = {"submarino": 30.0, "fragata": 10.0, "destructor": 10.0, "aerea": 8.0}
VELOCIDAD_TORPEDO_KMH = 75.0  # unos 40 nudos
AUTONOMIA_TORPEDO_KM = 50.0
MUNICION_TORPEDO = {"submarino": 12.5}  # % de la municion por torpedo (los demas: 25 %)
MUNICION_TORPEDO_POR_DEFECTO = 25.0

# estado en memoria compartido por el motor y la pantalla (mismo proceso): se rehace al correr el reloj
AHORA: dict[int, float] = {}  # escenario_id -> segundo simulado
EXPUESTO: dict[int, float] = {}  # submarino_id -> hasta cuando se lo ve por haber atacado
BOYAS: dict[int, list] = {}  # escenario_id -> [(bando, lat, lon, radio_km, hasta_seg)]


def es_submarino(u) -> bool:
    return getattr(u, "clase", None) == "submarino" and getattr(u, "tipo", "") == "naval"


def profundidad(u) -> str:
    return getattr(u, "profundidad", None) or "periscopica"


def expuesto(u) -> bool:
    return EXPUESTO.get(u.id, -1.0) >= AHORA.get(getattr(u, "escenario_id", None), 0.0)


def exponer(u, hasta: float) -> None:
    if es_submarino(u):
        EXPUESTO[u.id] = max(EXPUESTO.get(u.id, -1.0), hasta)


def es_avion_asw(u) -> bool:
    return getattr(u, "tipo", "") == "aerea" and getattr(u, "modelo", None) in ASW_AVIONES


def es_helo_asw(u) -> bool:
    return getattr(u, "tipo", "") == "aerea" and getattr(u, "modelo", None) in ASW_HELOS


def sonar_km(u) -> float:
    """Alcance del sonar de la unidad ahora (0 sin sonar o sin calar)."""
    if es_helo_asw(u) and not getattr(u, "en_tierra", False) and getattr(u, "mision", "") == "sonar" \
            and u.mision_lat is not None and geo.distancia_km(u.lat, u.lon, u.mision_lat, u.mision_lon) <= ESTACIONARIO_KM:
        return SONAR_INMERSION_KM
    if getattr(u, "tipo", "") != "naval":
        return 0.0
    from app.engine import sistemas  # importacion tardia: el sonar es parte de los sensores

    return SONAR_KM.get(u.clase, 0.0) * sistemas.factor(u, "sensores")


def radio_contra_submarino(detector, objetivo, radio_normal: float) -> float:
    """A que distancia `detector` ve al submarino `objetivo` (`radio_normal`: el de un buque a la vista)."""
    if expuesto(objetivo):
        return radio_normal
    hondo = profundidad(objetivo) == "profunda"
    sonar = sonar_km(detector) * (FACTOR_PROFUNDO if hondo else 1.0)
    vista = 0.0 if hondo or es_submarino(detector) else min(radio_normal, PERISCOPIO_KM)
    return max(sonar, vista)


def lanza_torpedos(u) -> bool:
    if getattr(u, "tipo", "") == "aerea":
        return (es_avion_asw(u) or es_helo_asw(u)) and not getattr(u, "en_tierra", False)
    return getattr(u, "clase", None) in ("submarino", "fragata", "destructor")


def alcance_torpedo(u) -> float:
    return ALCANCE_TORPEDO_KM["aerea" if u.tipo == "aerea" else u.clase] if lanza_torpedos(u) else 0.0


def error_de_torpedo(u, blanco) -> str | None:
    if not lanza_torpedos(u):
        return "Lanzan torpedos los submarinos, las fragatas, los destructores y las aeronaves antisubmarinas en vuelo."
    if blanco is None or blanco.estado != "activa" or blanco.bando == u.bando:
        return "Blanco inválido o ya fuera de combate."
    if blanco.tipo != "naval" or catalogo.es_misil(blanco):
        return "El torpedo solo sirve contra buques y submarinos."
    d = geo.distancia_km(u.lat, u.lon, blanco.lat, blanco.lon)
    if d > alcance_torpedo(u):
        return f"El blanco está a {d:.0f} km: el torpedo llega a {alcance_torpedo(u):.0f} km. Acérquese."
    from app.engine import armas  # importacion tardia

    if armas.tiene_carga(u):
        if (armas.datos(u)["quedan"].get("TOR") or 0) <= 0:
            return "No le quedan torpedos en su carga (elija la carga antisubmarina al despegar)."
    elif u.municion < municion_por_torpedo(u):
        return "Sin munición suficiente para un torpedo."
    return None


def municion_por_torpedo(u) -> float:
    return MUNICION_TORPEDO.get(u.clase, MUNICION_TORPEDO_POR_DEFECTO)


def crear_torpedo(lanzador, blanco, t: float):
    """Unidad torpedo junto al lanzador, guiada hacia el blanco (sin agregarla a la sesion)."""
    from app.models.unidad import Unidad

    clase = catalogo.CLASES["torpedo"]
    return Unidad(escenario_id=lanzador.escenario_id, nombre=f"Torpedo de {lanzador.nombre}"[:120], bando=lanzador.bando,
                  tipo="naval", clase=clase.id, echelon="", lat=lanzador.lat + 0.002, lon=lanzador.lon + 0.002,
                  fuerza=100.0, velocidad_kmh=VELOCIDAD_TORPEDO_KMH, alcance_km=clase.alcance_km, deteccion_km=0.0,
                  combustible=100.0, municion=100.0, autonomia_km=AUTONOMIA_TORPEDO_KM, blanco_id=blanco.id,
                  mision="impacto", mision_lat=blanco.lat, mision_lon=blanco.lon, estado="activa",
                  espera_hasta=t + AUTONOMIA_TORPEDO_KM / VELOCIDAD_TORPEDO_KMH * 3600.0 * 1.2,
                  sidc=catalogo.generar_sidc(lanzador.bando, clase))


def gastar_torpedo(u) -> None:
    from app.engine import armas  # importacion tardia

    if armas.tiene_carga(u):
        d = armas.datos(u)
        d["quedan"]["TOR"] = max(0, d["quedan"].get("TOR", 0) - 1)
        armas._guardar(u, d)
        armas.sincronizar(u)
    else:
        u.municion = max(0.0, u.municion - municion_por_torpedo(u))


# ---------------------------------------------------------------------------------------------------- sonoboyas
def cuadro_de_boyas(lat: float, lon: float) -> list[tuple[float, float]]:
    """4 boyas en cuadro alrededor del punto."""
    m = BOYA_SEPARACION_KM / 2.0
    return [geo.destino(lat, lon, rumbo, m * 1.414) for rumbo in (45.0, 135.0, 225.0, 315.0)]


def cargar_boyas(db, escenario_id: int, t: float) -> list:
    from app.models.sonoboya import Sonoboya

    filas = db.query(Sonoboya).filter(Sonoboya.escenario_id == escenario_id, Sonoboya.hasta_seg > t).all()
    BOYAS[escenario_id] = [(b.bando, b.lat, b.lon, b.radio_km, b.hasta_seg) for b in filas]
    return filas


def por_boyas(unidades, bando: str) -> list:
    """Submarinos enemigos que las sonoboyas activas del bando oyen ahora."""
    salida = []
    for u in unidades:
        if u.bando == bando or u.estado != "activa" or not es_submarino(u):
            continue
        boyas = BOYAS.get(u.escenario_id) or []
        t = AHORA.get(u.escenario_id, 0.0)
        factor = FACTOR_PROFUNDO if profundidad(u) == "profunda" else 1.0
        if any(b[0] == bando and b[4] > t and geo.distancia_km(u.lat, u.lon, b[1], b[2]) <= b[3] * factor for b in boyas):
            salida.append(u)
    return salida


def boyas_para(db, escenario, rol: str) -> list[dict]:
    """Sonoboyas activas que ve el rol (cada bando, las suyas; el director, todas)."""
    from app.models.sonoboya import Sonoboya

    q = db.query(Sonoboya).filter(Sonoboya.escenario_id == escenario.id, Sonoboya.hasta_seg > (escenario.sim_segundos or 0.0))
    if rol in ("azul", "rojo"):
        q = q.filter(Sonoboya.bando == rol)
    return [{"id": b.id, "bando": b.bando, "lat": b.lat, "lon": b.lon, "radio_km": b.radio_km,
             "minutos": max(0, round((b.hasta_seg - (escenario.sim_segundos or 0.0)) / 60))} for b in q]
