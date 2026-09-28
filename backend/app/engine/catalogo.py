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
          "batallon"),
    Clase("antiaerea_portatil", "Antiaerea portatil (tipo IGLA-S)", "terrestre", "G", "UCDM--", 20, 5, 10, 200,
          _atk(0.0, 2.6, 0.0), 0.6, "equipo", movilidad="ligera", municion_por_ataque=50.0,
          despliegue_turnos=1, recarga_turnos=1,
          armamento="Sistema portatil antiaereo: debe desplegarse (1 turno quieto) y recargar (1 turno) entre disparos"),
    Clase("ingenieros", "Ingenieros", "terrestre", "G", "UCEC--", 25, 5, 8, 250, _atk(0.5, 0.1, 0.2), 0.9,
          "compania", movilidad="ligera", construye=True,
          armamento="Tiende vados (rapidos, precarios) y puentes (mas lentos, permiten pasar a los vehiculos)"),
    Clase("transporte", "Transporte logistico (convoy)", "terrestre", "G", "USTM--", 40, 0, 6, 400,
          _atk(0.0, 0.0, 0.0), 0.5, "compania", suministra=("terrestre",), vulnerable_emboscada=True,
          nodo_movil_km=3.0, carga_max=100.0,
          armamento="Convoy: reabastece en marcha a las unidades terrestres a <= 3 km; muy vulnerable a emboscadas"),
    # ---- aereas ----
    Clase("caza", "Caza", "aerea", "A", "MFF---", 900, 80, 60, 1800, _atk(0.7, 1.25, 0.7), 1.0, movilidad="aerea"),
    Clase("ataque", "Ataque a tierra", "aerea", "A", "MFA---", 700, 100, 30, 2000, _atk(1.3, 0.4, 1.2), 0.8,
          movilidad="aerea"),
    Clase("helicoptero", "Helicoptero", "aerea", "A", "MH----", 250, 25, 20, 500, _atk(1.1, 0.3, 0.9), 0.8,
          movilidad="aerea"),
    Clase("helicoptero_artillado", "Helicoptero de transporte artillado", "aerea", "A", "MHU---", 220, 6, 15, 450,
          _atk(0.45, 0.15, 0.3), 0.7, movilidad="aerea", penalizacion_movilidad=0.15, cadencia_fuego=1.6,
          armamento="Ametralladora de 12,7 mm en afuste: alta cadencia (mas municion), -15 % de velocidad por peso"),
    # ---- navales ----
    Clase("fragata", "Fragata", "naval", "S", "CLFF--", 40, 40, 30, 4000, _atk(0.6, 0.5, 1.2), 1.0, movilidad="naval"),
    Clase("patrullero", "Patrullero", "naval", "S", "CPSB--", 55, 20, 20, 1500, _atk(0.4, 0.3, 0.9), 0.7,
          movilidad="naval"),
    # ---- bases ----
    Clase("base_aerea", "Base aerea", "base", "G", "IBA---", 0, 25, 6, 0, _atk(0.0, 0.0, 0.0), 1.0, "",
          ("aerea",), movilidad="fija"),
    Clase("deposito", "Deposito logistico", "base", "G", "UUS---", 0, 20, 5, 0, _atk(0.0, 0.0, 0.0), 1.0, "",
          ("terrestre",), movilidad="fija"),
    Clase("puerto", "Puerto / base naval", "base", "G", "IBN---", 0, 25, 6, 0, _atk(0.0, 0.0, 0.0), 1.0, "",
          ("naval",), movilidad="fija"),
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
        "carga_max": c.carga_max, "construye": c.construye,
    }
