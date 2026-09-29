"""Catalogo de clases de unidad: valores por defecto, efectividad por tipo de
objetivo, fidelidad de plataforma (movilidad, cadencia, despliegue, recarga) y
codigo de simbolo (APP-6 / MIL-STD-2525B, validados con milsymbol).

Los valores son parametros de juego (abstracciones didacticas ajustables), no datos
tecnicos de sistemas reales."""

from dataclasses import dataclass, replace

TIPOS = ("terrestre", "aerea", "naval", "base")

# Escalon (tamano de la unidad) -> letra en la posicion 12 del SIDC.
ESCALONES = {
    "": "-", "equipo": "A", "escuadra": "B", "seccion": "C", "peloton": "D",
    "compania": "E", "batallon": "F", "regimiento": "G", "brigada": "H", "division": "I",
}

# Movilidad en tierra: las unidades "ligeras" vadean los rios (a media velocidad); las "pesadas"
# (vehiculos) solo los cruzan sobre un puente o vado tendido por ingenieros.
MOVILIDADES = ("ligera", "pesada", "aerea", "naval", "fija")


@dataclass(frozen=True)
class Clase:
    id: str
    nombre: str
    tipo: str
    dimension: str  # G terrestre/instalacion, A aire, S superficie
    funcion: str  # 6 caracteres del SIDC
    velocidad_kmh: float
    alcance_km: float
    deteccion_km: float
    autonomia_km: float  # distancia con el tanque lleno
    ataque_vs: dict  # multiplicador de ataque segun el tipo del objetivo (0 = no puede atacarlo)
    defensa: float
    escalon: str = ""
    suministra: tuple = ()  # tipos de unidad a los que reabastece (solo bases)
    # ---- fidelidad de plataforma ----
    movilidad: str = "pesada"
    penalizacion_movilidad: float = 0.0  # fraccion de velocidad que se pierde (peso, carga, armamento)
    cadencia_fuego: float = 1.0  # 1.0 = normal; consume mas municion y aporta potencia (raiz cuadrada)
    municion_por_ataque: float | None = None  # % de municion por ataque (None = valor del tipo)
    despliegue_turnos: int = 0  # turnos quieta para poder disparar tras moverse
    recarga_turnos: int = 0  # turnos sin poder disparar despues de un ataque
    armamento: str = ""
    vulnerable_emboscada: bool = False  # sufre mucho mas si el atacante no fue detectado
    nodo_movil_km: float = 0.0  # radio de reabastecimiento de un convoy (0 = no es nodo movil)
    carga_max: float = 0.0  # suministros que transporta un convoy (%)
    construye: bool = False  # puede tender puentes y vados
    # ---- sensores, guerra electronica y drones (ver engine/guerra_electronica.py) ----
    firma: float = 1.0  # multiplica la distancia a la que se la detecta (drones: firma radar pequena)
    solo_aereo: bool = False  # sensor que ve aeronaves en vuelo muy lejos, pero lo que esta en tierra solo de cerca
    emisor: bool = False  # emite (radar): la escucha electronica enemiga lo localiza a gran distancia
    escucha_km: float = 0.0  # radio en que localiza emisores enemigos (0 = no escucha)
    interferencia_km: float = 0.0  # radio de la zona que puede interferir (0 = no interfiere)
    dron: bool = False  # aeronave no tripulada: pierde el enlace dentro de una interferencia enemiga
    se_consume: bool = False  # municion merodeadora: se destruye al atacar
    celula: str = ""  # "ge": radares y guerra electronica, que conduce el puesto A2
    defensa_aerea: bool = False  # dispara sola contra aeronaves enemigas detectadas a su alcance (si su fuego esta libre)
    # ---- bases: existencias (ver engine/logistica.py) ----
    stock_max: float = 0.0  # existencias maximas de combustible y de municion (puntos; 100 = llenar una unidad)
    reposicion_turno: float = 0.0  # puntos que repone cada turno (depositos: la linea de abastecimiento)


def _atk(t=1.0, a=1.0, n=1.0):
    return {"terrestre": t, "aerea": a, "naval": n}


CLASES: dict[str, Clase] = {c.id: c for c in [
    # ---- terrestres ----
    Clase("infanteria", "Infanteria", "terrestre", "G", "UCI---", 30, 10, 8, 300, _atk(1.0, 0.3, 0.4), 1.0,
          "compania", movilidad="ligera"),
    Clase("blindado", "Blindados", "terrestre", "G", "UCA---", 45, 15, 8, 250, _atk(1.25, 0.3, 0.9), 1.15,
          "compania"),
    Clase("artilleria", "Artilleria", "terrestre", "G", "UCFH--", 25, 30, 6, 200, _atk(1.3, 0.1, 1.0), 0.7,
          "batallon"),
    Clase("reconocimiento", "Reconocimiento", "terrestre", "G", "UCR---", 60, 6, 16, 350, _atk(0.6, 0.2, 0.3), 0.8,
          "seccion", movilidad="ligera"),
    Clase("antiaerea", "Defensa antiaerea", "terrestre", "G", "UCD---", 30, 20, 20, 250, _atk(0.4, 2.0, 0.2), 0.9,
          "batallon", emisor=True, defensa_aerea=True,
          armamento="Misiles y canones guiados por radar: dispara sola contra aviones enemigos a su alcance si su radar "
                    "emite; la guerra electronica enemiga la localiza y la degrada"),
    Clase("antiaerea_portatil", "Antiaerea portatil (tipo IGLA-S)", "terrestre", "G", "UCDM--", 20, 5, 10, 200,
          _atk(0.0, 2.6, 0.0), 0.6, "equipo", movilidad="ligera", municion_por_ataque=50.0,
          despliegue_turnos=1, recarga_turnos=1, defensa_aerea=True,
          armamento="Sistema portatil antiaereo: debe desplegarse (1 turno quieto) y recargar (1 turno) entre disparos"),
    Clase("ingenieros", "Ingenieros", "terrestre", "G", "UCEC--", 25, 5, 8, 250, _atk(0.5, 0.1, 0.2), 0.9,
          "compania", movilidad="ligera", construye=True,
          armamento="Tiende vados (rapidos, precarios) y puentes (mas lentos, permiten pasar a los vehiculos)"),
    Clase("transporte", "Transporte logistico (convoy)", "terrestre", "G", "USTM--", 40, 0, 6, 400,
          _atk(0.0, 0.0, 0.0), 0.5, "compania", suministra=("terrestre",), vulnerable_emboscada=True,
          nodo_movil_km=3.0, carga_max=100.0,
          armamento="Convoy: reabastece en marcha a las unidades terrestres a <= 3 km; muy vulnerable a emboscadas"),
    # ---- sensores y guerra electronica terrestres (los conduce el puesto A2) ----
    Clase("radar", "Radar de vigilancia aerea", "terrestre", "G", "ESR---", 15, 0, 150, 150, _atk(0.0, 0.0, 0.0), 0.5,
          "", movilidad="pesada", solo_aereo=True, emisor=True, celula="ge",
          armamento="Radar 3D: ve aeronaves en vuelo hasta 150 km, pero lo que esta en tierra solo a pocos km. "
                    "Emite: la escucha enemiga lo localiza"),
    Clase("guerra_electronica", "Guerra electronica (escucha e interferencia)", "terrestre", "G", "UUMSE-", 35, 40, 10,
          300, _atk(0.0, 0.0, 0.0), 0.6, "compania", movilidad="pesada", escucha_km=120.0, interferencia_km=25.0,
          celula="ge",
          armamento="Escucha: localiza radares e interferidores enemigos hasta 120 km. Interferencia: degrada "
                    "sensores, antiaerea y enlaces de drones enemigos en 25 km a hasta 40 km de la unidad; al emitir se delata"),
    # ---- aereas ----
    Clase("caza", "Caza", "aerea", "A", "MFF---", 900, 80, 60, 1800, _atk(0.7, 1.25, 0.7), 1.0, movilidad="aerea"),
    Clase("ataque", "Ataque a tierra", "aerea", "A", "MFA---", 700, 100, 30, 2000, _atk(1.3, 0.4, 1.2), 0.8,
          movilidad="aerea"),
    Clase("helicoptero", "Helicoptero", "aerea", "A", "MH----", 250, 25, 20, 500, _atk(1.1, 0.3, 0.9), 0.8,
          movilidad="aerea"),
    Clase("helicoptero_artillado", "Helicoptero de transporte artillado", "aerea", "A", "MHU---", 220, 6, 15, 450,
          _atk(0.45, 0.15, 0.3), 0.7, movilidad="aerea", penalizacion_movilidad=0.15, cadencia_fuego=1.6,
          armamento="Ametralladora de 12,7 mm en afuste: alta cadencia (mas municion), -15 % de velocidad por peso"),
    Clase("avion_ge", "Avion de guerra electronica", "aerea", "A", "MFJ---", 750, 60, 60, 2500, _atk(0.0, 0.0, 0.0),
          0.6, movilidad="aerea", escucha_km=200.0, interferencia_km=40.0,
          armamento="Interferidor en orbita: degrada sensores, antiaerea y enlaces de drones enemigos en 40 km a hasta "
                    "60 km de su posicion; escucha emisores hasta 200 km. Sin armas"),
    Clase("dron_reconocimiento", "Dron de reconocimiento", "aerea", "A", "MFQR--", 150, 0, 45, 1500,
          _atk(0.0, 0.0, 0.0), 0.35, movilidad="aerea", firma=0.5, dron=True,
          armamento="Camaras electroopticas e infrarrojas, sin armas. Firma radar pequena: se lo detecta a la mitad de distancia"),
    Clase("dron_ataque", "Dron armado", "aerea", "A", "MFQA--", 200, 15, 30, 1200, _atk(0.9, 0.0, 0.6), 0.35,
          movilidad="aerea", firma=0.6, dron=True, municion_por_ataque=50.0,
          armamento="Misiles guiados ligeros contra vehiculos y buques (2 ataques por carga); firma radar pequena"),
    Clase("municion_merodeadora", "Municion merodeadora (dron kamikaze)", "aerea", "A", "MFQA--", 180, 5, 15, 300,
          _atk(1.4, 0.0, 1.0), 0.2, movilidad="aerea", firma=0.4, dron=True, se_consume=True,
          armamento="Merodea sobre la zona y se estrella contra el blanco: un solo ataque, se destruye al impactar"),
    # ---- navales ----
    Clase("fragata", "Fragata", "naval", "S", "CLFF--", 40, 40, 30, 4000, _atk(0.6, 0.5, 1.2), 1.0, movilidad="naval"),
    Clase("patrullero", "Patrullero", "naval", "S", "CPSB--", 55, 20, 20, 1500, _atk(0.4, 0.3, 0.9), 0.7,
          movilidad="naval"),
    # ---- bases ----
    Clase("base_aerea", "Base aerea", "base", "G", "IBA---", 0, 25, 6, 0, _atk(0.0, 0.0, 0.0), 1.0, "",
          ("aerea",), movilidad="fija", stock_max=2000.0),
    Clase("deposito", "Deposito logistico", "base", "G", "UUS---", 0, 20, 5, 0, _atk(0.0, 0.0, 0.0), 1.0, "",
          ("terrestre",), movilidad="fija", stock_max=3000.0, reposicion_turno=150.0),
    Clase("puerto", "Puerto / base naval", "base", "G", "IBN---", 0, 25, 6, 0, _atk(0.0, 0.0, 0.0), 1.0, "",
          ("naval",), movilidad="fija", stock_max=2000.0),
]}

# Clase por defecto de cada tipo (compatibilidad con unidades creadas sin clase).
CLASE_POR_TIPO = {"terrestre": "infanteria", "aerea": "caza", "naval": "fragata", "base": "deposito"}


def obtener(clase: str | None, tipo: str) -> Clase:
    """Clase indicada o, si no existe o no corresponde al tipo, la clase por defecto del tipo."""
    c = CLASES.get(clase or "")
    if c is None or c.tipo != tipo:
        c = CLASES[CLASE_POR_TIPO[tipo]]
    return c


# ---------------------------------------------------------------------------------------------------------
# Modelos de aeronave: variantes de una clase (p. ej. "caza") con su foto y sus propios valores de juego.
# Las cifras son parametros didacticos relativos entre modelos, no datos tecnicos oficiales.
# ---------------------------------------------------------------------------------------------------------
TAMANO_GRUPO_REFERENCIA = 4  # un grupo de 4 aeronaves rinde "1.0"
MAX_AERONAVES_GRUPO = 8
MAX_AERONAVES_BANDO = 24  # tope de aeronaves de combate en vuelo o en pista por bando (despegues de los alumnos)
MAX_DRONES_BANDO = 16  # los drones tienen su propio tope y no cuentan para el de aeronaves tripuladas


@dataclass(frozen=True)
class Modelo:
    id: str
    clase: str  # clase del catalogo a la que pertenece (define el simbolo APP-6)
    nombre: str
    corto: str  # para rotulos en el mapa
    fabricante: str
    pais: str
    funcion: str
    descripcion: str
    armamento: str
    velocidad_kmh: float
    alcance_km: float
    deteccion_km: float
    autonomia_km: float
    ataque_vs: dict
    defensa: float
    foto: str
    credito: dict  # autor, licencia, url_licencia, pagina


_CREDITO_PROPIO = {"autor": "Simulador Fenix (ilustracion propia)", "licencia": "CC0",
                   "url_licencia": "https://creativecommons.org/publicdomain/zero/1.0/",
                   "pagina": "/static/fotos/CREDITOS.md"}

MODELOS: dict[str, Modelo] = {m.id: m for m in [
    Modelo(
        "f16", "caza", "F-16A/B Fighting Falcon", "F-16", "General Dynamics (hoy Lockheed Martin)", "Estados Unidos",
        "Caza multirol monomotor",
        "Caza ligero y muy maniobrable, adquirido por la Aviacion Militar Bolivariana en los anos 80. "
        "Mejor en combate aereo que contra tierra o buques.",
        "Canon M61 de 20 mm, misiles aire-aire de corto y medio alcance, bombas y cohetes.",
        950, 80, 65, 1900, _atk(0.85, 1.3, 0.75), 1.0,
        "/static/fotos/f16.jpg",
        {"autor": "Veronidae", "licencia": "CC BY-SA 3.0", "url_licencia": "https://creativecommons.org/licenses/by-sa/3.0",
         "pagina": "https://commons.wikimedia.org/wiki/File:F-16_venezolano.jpg"},
    ),
    Modelo(
        "su30", "caza", "Su-30MK2 Flanker-G", "Su-30", "Sukhoi", "Rusia",
        "Caza multirol biplaza de largo alcance",
        "Caza pesado de dos motores y dos tripulantes, adquirido por la Aviacion Militar Bolivariana a partir de 2006. "
        "Mayor autonomia y radar que el F-16; buena capacidad contra buques y tierra.",
        "Canon de 30 mm, misiles aire-aire de corto y largo alcance, misiles aire-superficie y antibuque.",
        1000, 100, 90, 3000, _atk(0.9, 1.35, 1.1), 1.05,
        "/static/fotos/su30.jpg",
        {"autor": "Carlos E. Perez S.L", "licencia": "CC BY-SA 4.0", "url_licencia": "https://creativecommons.org/licenses/by-sa/4.0",
         "pagina": "https://commons.wikimedia.org/wiki/File:Sukhoi_Su-30MK2_de_Venezuela.jpg"},
    ),
    # ---- no tripulados y guerra electronica: modelos genericos (parametros didacticos, sin fabricante real) ----
    Modelo(
        "uav_reco", "dron_reconocimiento", "Dron de reconocimiento (UAV tactico)", "UAV-R", "Generico", "-",
        "Vigilancia y reconocimiento no tripulado",
        "Aeronave no tripulada de largo aliento: ve lejos y se la detecta tarde, pero no lleva armas y dentro de una "
        "interferencia enemiga pierde el enlace y no acepta ordenes.",
        "Sin armas: camaras electroopticas e infrarrojas.",
        150, 0, 45, 1500, _atk(0.0, 0.0, 0.0), 0.35,
        "/static/fotos/dron_reconocimiento.svg", _CREDITO_PROPIO,
    ),
    Modelo(
        "uav_armado", "dron_ataque", "Dron armado (UAV de media altitud)", "UAV-A", "Generico", "-",
        "Ataque de precision no tripulado",
        "Dron con misiles ligeros para atacar vehiculos y buques a distancia. Lento y fragil si lo detectan; "
        "vulnerable a la interferencia de su enlace.",
        "Dos misiles guiados ligeros (2 ataques por carga).",
        200, 15, 30, 1200, _atk(0.9, 0.0, 0.6), 0.35,
        "/static/fotos/dron_armado.svg", _CREDITO_PROPIO,
    ),
    Modelo(
        "merodeadora", "municion_merodeadora", "Municion merodeadora (dron kamikaze)", "Kamikaze", "Generico", "-",
        "Ataque de un solo uso",
        "Pequeno dron que merodea sobre la zona y se estrella contra el blanco. Muy dificil de detectar, "
        "corto alcance; se pierde al atacar.",
        "Carga explosiva (un solo ataque).",
        180, 5, 15, 300, _atk(1.4, 0.0, 1.0), 0.2,
        "/static/fotos/municion_merodeadora.svg", _CREDITO_PROPIO,
    ),
    Modelo(
        "ge_aereo", "avion_ge", "Avion de guerra electronica (interferidor)", "GE", "Generico", "-",
        "Interferencia y escucha desde el aire",
        "Avion con interferidores y receptores: en orbita, fuera del alcance de la defensa enemiga, interfiere sus "
        "sensores, antiaerea y drones, y localiza sus radares. Sin armas: necesita escolta.",
        "Interferidores y receptores de escucha; sin armas.",
        750, 60, 60, 2500, _atk(0.0, 0.0, 0.0), 0.6,
        "/static/fotos/avion_ge.svg", _CREDITO_PROPIO,
    ),
]}


def perfil(unidad) -> Clase:
    """Clase de la unidad con los valores de combate de su modelo (si tiene y corresponde a la clase)."""
    base = obtener(getattr(unidad, "clase", None), unidad.tipo)
    m = MODELOS.get(getattr(unidad, "modelo", "") or "")
    if m is None or m.clase != base.id:
        return base
    return replace(base, nombre=m.nombre, ataque_vs=m.ataque_vs, defensa=m.defensa, armamento=m.armamento)


def factor_grupo(unidad) -> float:
    """Un grupo de aeronaves rinde con la raiz de su tamano frente al grupo de referencia (4)."""
    if unidad.tipo != "aerea":
        return 1.0
    n = max(1, int(getattr(unidad, "aeronaves", 1) or 1))
    return max(0.5, min(2.0, (n / TAMANO_GRUPO_REFERENCIA) ** 0.5))


def escalon_grupo(aeronaves: int) -> str:
    """Escalon APP-6 segun el tamano del grupo aereo: pareja, escuadrilla o seccion."""
    return "equipo" if aeronaves <= 2 else "escuadra" if aeronaves <= 4 else "seccion"


def modelo_dict(m: Modelo) -> dict:
    return {
        "id": m.id, "clase": m.clase, "nombre": m.nombre, "corto": m.corto, "fabricante": m.fabricante,
        "pais": m.pais, "funcion": m.funcion, "descripcion": m.descripcion, "armamento": m.armamento,
        "velocidad_kmh": m.velocidad_kmh, "alcance_km": m.alcance_km, "deteccion_km": m.deteccion_km,
        "autonomia_km": m.autonomia_km, "ataque_vs": m.ataque_vs, "defensa": m.defensa, "foto": m.foto,
        "credito": m.credito,
    }


def generar_sidc(bando: str, clase: Clase, escalon: str = "") -> str:
    afiliacion = {"azul": "F", "rojo": "H"}.get(bando, "U")
    esc = ESCALONES.get(escalon or clase.escalon, "-")
    return f"S{afiliacion}{clase.dimension}P{clase.funcion}-{esc}---"


def como_dict(c: Clase) -> dict:
    return {
        "id": c.id, "nombre": c.nombre, "tipo": c.tipo, "velocidad_kmh": c.velocidad_kmh,
        "alcance_km": c.alcance_km, "deteccion_km": c.deteccion_km, "autonomia_km": c.autonomia_km,
        "escalon": c.escalon, "suministra": list(c.suministra), "movilidad": c.movilidad,
        "penalizacion_movilidad": c.penalizacion_movilidad, "cadencia_fuego": c.cadencia_fuego,
        "despliegue_turnos": c.despliegue_turnos, "recarga_turnos": c.recarga_turnos, "armamento": c.armamento,
        "vulnerable_emboscada": c.vulnerable_emboscada, "nodo_movil_km": c.nodo_movil_km,
        "carga_max": c.carga_max, "construye": c.construye, "firma": c.firma, "solo_aereo": c.solo_aereo,
        "emisor": c.emisor, "escucha_km": c.escucha_km, "interferencia_km": c.interferencia_km, "dron": c.dron,
        "se_consume": c.se_consume, "celula": c.celula, "defensa_aerea": c.defensa_aerea, "stock_max": c.stock_max,
        "reposicion_turno": c.reposicion_turno,
    }
