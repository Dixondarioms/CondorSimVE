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
    dimension: str  # G terrestre/instalacion, A aire, S superficie, U submarino
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
    # ---- buques, portaaviones y misiles de crucero (ver engine/misiles.py y engine/aeronaves.py) ----
    misil: bool = False  # misil de crucero en vuelo: autonomo, guiado hacia su blanco, no admite ordenes
    lanza_misiles: bool = False  # puede lanzar salvas de misiles de crucero (orden "lanzar")
    plazas_aeronaves: int = 0  # aeronaves que opera y estaciona (base aerea, portaaviones); 0 = ninguna
    embarcable: bool = False  # la aeronave puede operar desde un portaaviones (helicopteros, drones)
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
    Clase("lanzador_misiles", "Lanzador de misiles de crucero (bateria costera)", "terrestre", "G", "UCMT--", 40, 0,
          10, 400, _atk(0.0, 0.0, 0.0), 0.7, "compania", despliegue_turnos=1, lanza_misiles=True,
          armamento="Sin fuego directo: lanza salvas de misiles de crucero contra blancos terrestres y navales; debe "
                    "desplegarse (1 turno quieto) tras moverse"),
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
          movilidad="aerea", embarcable=True),
    Clase("helicoptero_artillado", "Helicoptero de transporte artillado", "aerea", "A", "MHU---", 220, 6, 15, 450,
          _atk(0.45, 0.15, 0.3), 0.7, movilidad="aerea", penalizacion_movilidad=0.15, cadencia_fuego=1.6, embarcable=True,
          armamento="Ametralladora de 12,7 mm en afuste: alta cadencia (mas municion), -15 % de velocidad por peso"),
    Clase("avion_ge", "Avion de guerra electronica", "aerea", "A", "MFJ---", 750, 60, 60, 2500, _atk(0.0, 0.0, 0.0),
          0.6, movilidad="aerea", escucha_km=200.0, interferencia_km=40.0,
          armamento="Interferidor en orbita: degrada sensores, antiaerea y enlaces de drones enemigos en 40 km a hasta "
                    "60 km de su posicion; escucha emisores hasta 200 km. Sin armas"),
    Clase("dron_reconocimiento", "Dron de reconocimiento", "aerea", "A", "MFQR--", 150, 0, 45, 1500,
          _atk(0.0, 0.0, 0.0), 0.35, movilidad="aerea", firma=0.5, dron=True, embarcable=True,
          armamento="Camaras electroopticas e infrarrojas, sin armas. Firma radar pequena: se lo detecta a la mitad de distancia"),
    Clase("dron_ataque", "Dron armado", "aerea", "A", "MFQA--", 200, 15, 30, 1200, _atk(0.9, 0.0, 0.6), 0.35,
          movilidad="aerea", firma=0.6, dron=True, municion_por_ataque=50.0, embarcable=True,
          armamento="Misiles guiados ligeros contra vehiculos y buques (2 ataques por carga); firma radar pequena"),
    Clase("municion_merodeadora", "Municion merodeadora (dron kamikaze)", "aerea", "A", "MFQA--", 180, 5, 15, 300,
          _atk(1.4, 0.0, 1.0), 0.2, movilidad="aerea", firma=0.4, dron=True, se_consume=True, embarcable=True,
          armamento="Merodea sobre la zona y se estrella contra el blanco: un solo ataque, se destruye al impactar"),
    Clase("misil_crucero", "Misil de crucero", "aerea", "A", "WMCM--", 850, 5, 0, 1000, _atk(1.5, 0.0, 1.6), 0.3,
          movilidad="aerea", firma=0.3, se_consume=True, misil=True,
          armamento="Salva de misiles guiados hacia su blanco: vuela sola, se estrella contra el blanco (un solo "
                    "ataque) y puede ser derribada antes del impacto por la antiaerea o las patrullas enemigas"),
    # ---- navales ----
    Clase("fragata", "Fragata", "naval", "S", "CLFF--", 40, 40, 30, 4000, _atk(0.6, 0.5, 1.2), 1.0, movilidad="naval",
          lanza_misiles=True,
          armamento="Canon y misiles antibuque y antiaereos de corto alcance; lanza misiles de crucero (orden lanzar)"),
    Clase("patrullero", "Patrullero", "naval", "S", "CPSB--", 55, 20, 20, 1500, _atk(0.4, 0.3, 0.9), 0.7,
          movilidad="naval"),
    Clase("destructor", "Destructor", "naval", "S", "CLDD--", 55, 60, 60, 5000, _atk(0.8, 1.6, 1.4), 1.2,
          movilidad="naval", emisor=True, defensa_aerea=True, lanza_misiles=True,
          armamento="Radar de busqueda aerea y misiles antiaereos: derriba solo aeronaves y misiles enemigos a su "
                    "alcance si su radar emite (la escucha enemiga lo localiza). Misiles antibuque y de crucero"),
    Clase("portaaviones", "Portaaviones", "naval", "S", "CLCV--", 45, 15, 50, 8000, _atk(0.2, 0.5, 0.3), 1.5,
          "", ("aerea",), movilidad="naval", plazas_aeronaves=10, stock_max=1500.0,
          armamento="Base aerea movil: lanza y recibe helicopteros, drones y cazas embarcados (10 plazas). Repone "
                    "sus existencias junto a un puerto propio. Armas propias debiles: necesita escolta"),
    Clase("submarino", "Submarino", "naval", "U", "SC----", 35, 30, 25, 6000, _atk(0.0, 0.0, 1.6), 1.0,
          movilidad="naval", firma=0.25, lanza_misiles=True,
          armamento="Torpedos contra buques y misiles de crucero. Sumergido, se lo detecta a un cuarto de la "
                    "distancia. No puede atacar aeronaves"),
    Clase("buque_desembarco", "Buque de desembarco anfibio", "naval", "S", "CALS--", 35, 10, 25, 5000,
          _atk(0.4, 0.2, 0.2), 0.9, movilidad="naval",
          armamento="Transporte anfibio de tropas y vehiculos con armas de autodefensa debiles: necesita escolta"),
    # ---- bases ----
    Clase("base_aerea", "Base aerea", "base", "G", "IBA---", 0, 25, 6, 0, _atk(0.0, 0.0, 0.0), 1.0, "",
          ("aerea",), movilidad="fija", stock_max=2000.0, plazas_aeronaves=12),
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


def plazas_aeronaves(unidad) -> int:
    """Aeronaves que la unidad puede estacionar y lanzar (base aerea, portaaviones); 0 si no opera aeronaves."""
    return obtener(getattr(unidad, "clase", None), unidad.tipo).plazas_aeronaves


def opera_aeronaves(unidad) -> bool:
    return plazas_aeronaves(unidad) > 0


def es_portaaviones(unidad) -> bool:
    """Opera aeronaves y no es una base fija (se mueve con ellas a bordo)."""
    return unidad.tipo != "base" and opera_aeronaves(unidad)


def es_misil(unidad) -> bool:
    return unidad.tipo == "aerea" and obtener(getattr(unidad, "clase", None), unidad.tipo).misil


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
    embarcable: bool | None = None  # opera desde un portaaviones (None = lo que diga su clase)


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
    # ---- aviacion embarcada y de apoyo, y misil de crucero: modelos genericos (ilustraciones propias) ----
    Modelo(
        "caza_embarcado", "caza", "Caza embarcado (generico)", "Caza emb.", "Generico", "-",
        "Caza multirol naval",
        "Caza reforzado con gancho de apontaje: despega y aterriza en un portaaviones. Algo menos de autonomia que "
        "un caza de base terrestre y buena capacidad antibuque.",
        "Canon, misiles aire-aire y misiles antibuque.",
        900, 70, 60, 1500, _atk(0.8, 1.2, 1.0), 0.95,
        "/static/fotos/caza_embarcado.svg", _CREDITO_PROPIO, embarcable=True,
    ),
    Modelo(
        "helo_ataque", "helicoptero", "Helicoptero de ataque (generico)", "Helo At.", "Generico", "-",
        "Ataque a blindados y embarcaciones",
        "Helicoptero con misiles guiados: lento pero muy eficaz contra blindados y embarcaciones. Opera desde bases "
        "y portaaviones.",
        "Canon de 30 mm, cohetes y misiles antitanque guiados.",
        280, 25, 20, 550, _atk(1.2, 0.3, 1.0), 0.85,
        "/static/fotos/helo_ataque.svg", _CREDITO_PROPIO,
    ),
    Modelo(
        "helo_transporte", "helicoptero_artillado", "Helicoptero de transporte artillado (generico)", "Helo Tr.",
        "Generico", "-",
        "Transporte de tropas con autodefensa",
        "Helicoptero de transporte con ametralladoras en las puertas: apoyo ligero y autodefensa. Opera desde bases "
        "y portaaviones.",
        "Ametralladoras de 12,7 mm en afuste (alta cadencia).",
        230, 6, 15, 500, _atk(0.45, 0.15, 0.3), 0.7,
        "/static/fotos/helo_transporte.svg", _CREDITO_PROPIO,
    ),
    Modelo(
        "ataque_ligero", "ataque", "Avion de ataque ligero (generico)", "At. ligero", "Generico", "-",
        "Apoyo aereo cercano",
        "Avion ligero y economico para apoyo cercano contra blancos terrestres poco defendidos. Vulnerable a la "
        "antiaerea y a los cazas. Solo opera desde bases terrestres.",
        "Canon, cohetes y bombas ligeras.",
        650, 90, 30, 1800, _atk(1.2, 0.3, 1.0), 0.75,
        "/static/fotos/ataque_ligero.svg", _CREDITO_PROPIO,
    ),
    Modelo(
        "crucero", "misil_crucero", "Misil de crucero (generico)", "Crucero", "Generico", "-",
        "Ataque de precision a larga distancia",
        "Misil subsonico de vuelo rasante lanzado en salvas desde buques, submarinos o baterias costeras. Vuela solo "
        "hacia su blanco; la antiaerea enemiga puede derribarlo antes del impacto.",
        "Cabeza explosiva (un solo impacto).",
        850, 5, 0, 1000, _atk(1.5, 0.0, 1.6), 0.3,
        "/static/fotos/crucero.svg", _CREDITO_PROPIO,
    ),
]}


def modelo_embarcable(m: Modelo) -> bool:
    return CLASES[m.clase].embarcable if m.embarcable is None else m.embarcable


def es_embarcable(clase_id: str | None, modelo_id: str | None = None) -> bool:
    """La aeronave (su clase y, si lo tiene, su modelo) puede operar desde un portaaviones."""
    m = MODELOS.get(modelo_id or "")
    if m is not None and m.clase == clase_id:
        return modelo_embarcable(m)
    c = CLASES.get(clase_id or "")
    return bool(c and c.embarcable)


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
        "credito": m.credito, "embarcable": modelo_embarcable(m), "misil": CLASES[m.clase].misil,
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
        "reposicion_turno": c.reposicion_turno, "misil": c.misil, "lanza_misiles": c.lanza_misiles,
        "plazas_aeronaves": c.plazas_aeronaves, "embarcable": c.embarcable,
    }


# ---------------------------------------------------------------------------------------------------------
# Ajustes del instructor sin tocar el codigo: backend/data/ajustes_catalogo.json (opcional).
# Sobrescribe campos numericos de clases y modelos y los topes de aeronaves. Formato:
#   {"clases": {"caza": {"velocidad_kmh": 950, "ataque_vs": {"aerea": 1.4}}},
#    "modelos": {"f16": {"alcance_km": 90}},
#    "topes": {"MAX_AERONAVES_BANDO": 32}}
# Las claves que empiezan por "_" (p. ej. "_comentario") se ignoran. Ver data/ajustes_catalogo.ejemplo.json.
# ---------------------------------------------------------------------------------------------------------
import json as _json
import logging as _logging
import os as _os
import sys as _sys
from pathlib import Path as _Path

_log = _logging.getLogger("simulador.catalogo")

RUTA_AJUSTES = _Path(__file__).resolve().parent.parent.parent / "data" / "ajustes_catalogo.json"
VAR_AJUSTES = "SIMULADOR_AJUSTES_CATALOGO"

# Campos que se pueden ajustar (nombre -> tipo esperado). Los enteros no admiten decimales; los flotantes
# aceptan enteros. "ataque_vs" es un dict que se fusiona clave a clave (terrestre / aerea / naval).
_CAMPOS_CLASE = {
    "velocidad_kmh": float, "alcance_km": float, "deteccion_km": float, "autonomia_km": float,
    "defensa": float, "ataque_vs": dict, "stock_max": float, "reposicion_turno": float, "firma": float,
    "escucha_km": float, "interferencia_km": float, "cadencia_fuego": float, "municion_por_ataque": float,
    "despliegue_turnos": int, "recarga_turnos": int, "plazas_aeronaves": int,
}
_CAMPOS_MODELO = {
    "velocidad_kmh": float, "alcance_km": float, "deteccion_km": float, "autonomia_km": float,
    "defensa": float, "ataque_vs": dict,
}
_TOPES = ("MAX_AERONAVES_GRUPO", "MAX_AERONAVES_BANDO", "MAX_DRONES_BANDO")


def _es_numero(valor, tipo) -> bool:
    if isinstance(valor, bool):
        return False
    if tipo is int:
        return isinstance(valor, int)
    return isinstance(valor, (int, float))


def _valores_validos(entrada: dict, campos: dict, actual, donde: str) -> dict:
    """Filtra los campos de una entrada del JSON: devuelve solo los validos, ya con el tipo correcto."""
    cambios = {}
    for campo, valor in entrada.items():
        if campo.startswith("_"):
            continue
        tipo = campos.get(campo)
        if tipo is None:
            _log.warning("ajustes_catalogo: campo desconocido %r en %s (se ignora)", campo, donde)
            continue
        if tipo is dict:
            if not isinstance(valor, dict):
                _log.warning("ajustes_catalogo: %s.%s debe ser un objeto {tipo: factor} (se ignora)", donde, campo)
                continue
            fusion = dict(getattr(actual, campo))
            for objetivo, factor in valor.items():
                if objetivo.startswith("_"):
                    continue
                if objetivo not in TIPOS or objetivo == "base":
                    _log.warning("ajustes_catalogo: %s.%s: tipo de objetivo desconocido %r (se ignora)",
                                 donde, campo, objetivo)
                    continue
                if not _es_numero(factor, float) or factor < 0:
                    _log.warning("ajustes_catalogo: %s.%s.%s debe ser un numero >= 0 (se ignora)",
                                 donde, campo, objetivo)
                    continue
                fusion[objetivo] = float(factor)
            if fusion != getattr(actual, campo):
                cambios[campo] = fusion
            continue
        if not _es_numero(valor, tipo) or valor < 0:
            _log.warning("ajustes_catalogo: %s.%s debe ser un numero %s>= 0 (se ignora)",
                         donde, campo, "entero " if tipo is int else "")
            continue
        cambios[campo] = tipo(valor)
    return cambios


def aplicar_ajustes(ruta=None) -> dict:
    """Aplica los ajustes del instructor a CLASES, MODELOS y los topes de aeronaves.

    `ruta`: archivo JSON; si es None se usa la variable de entorno SIMULADOR_AJUSTES_CATALOGO o, en su
    defecto, backend/data/ajustes_catalogo.json. Si el archivo no existe no se hace nada. Las entradas
    desconocidas o con tipos incorrectos se registran como aviso y se ignoran. Devuelve un resumen
    {"clases": {id: [campos]}, "modelos": {id: [campos]}, "topes": [nombres]} de lo aplicado.
    """
    modulo = _sys.modules[__name__]
    resumen = {"clases": {}, "modelos": {}, "topes": []}
    if ruta is None:
        ruta = _os.environ.get(VAR_AJUSTES) or RUTA_AJUSTES
    ruta = _Path(ruta)
    if not ruta.is_file():
        return resumen
    try:
        datos = _json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _log.warning("ajustes_catalogo: no se pudo leer %s: %s (se ignora)", ruta, e)
        return resumen
    if not isinstance(datos, dict):
        _log.warning("ajustes_catalogo: %s debe contener un objeto JSON (se ignora)", ruta)
        return resumen

    for seccion, catalogo_sec, campos in (("clases", CLASES, _CAMPOS_CLASE), ("modelos", MODELOS, _CAMPOS_MODELO)):
        entradas = datos.get(seccion) or {}
        if not isinstance(entradas, dict):
            _log.warning("ajustes_catalogo: la seccion %r debe ser un objeto (se ignora)", seccion)
            continue
        for id_, entrada in entradas.items():
            if id_.startswith("_"):
                continue
            actual = catalogo_sec.get(id_)
            if actual is None:
                _log.warning("ajustes_catalogo: %s desconocido %r (se ignora)", seccion[:-1], id_)
                continue
            if not isinstance(entrada, dict):
                _log.warning("ajustes_catalogo: %s.%s debe ser un objeto (se ignora)", seccion, id_)
                continue
            cambios = _valores_validos(entrada, campos, actual, f"{seccion}.{id_}")
            if cambios:
                catalogo_sec[id_] = replace(actual, **cambios)
                resumen[seccion][id_] = sorted(cambios)

    topes = datos.get("topes") or {}
    if not isinstance(topes, dict):
        _log.warning("ajustes_catalogo: la seccion 'topes' debe ser un objeto (se ignora)")
    else:
        for nombre, valor in topes.items():
            if nombre.startswith("_"):
                continue
            if nombre not in _TOPES:
                _log.warning("ajustes_catalogo: tope desconocido %r (se ignora)", nombre)
                continue
            if not _es_numero(valor, int) or valor < 1:
                _log.warning("ajustes_catalogo: topes.%s debe ser un entero >= 1 (se ignora)", nombre)
                continue
            setattr(modulo, nombre, int(valor))
            resumen["topes"].append(nombre)

    for claves in (seccion for seccion in datos if seccion not in ("clases", "modelos", "topes")
                   and not seccion.startswith("_")):
        _log.warning("ajustes_catalogo: seccion desconocida %r (se ignora)", claves)
    if resumen["clases"] or resumen["modelos"] or resumen["topes"]:
        _log.info("ajustes_catalogo: aplicado %s (clases: %s, modelos: %s, topes: %s)", ruta,
                  ", ".join(resumen["clases"]) or "-", ", ".join(resumen["modelos"]) or "-",
                  ", ".join(resumen["topes"]) or "-")
    return resumen


aplicar_ajustes()
