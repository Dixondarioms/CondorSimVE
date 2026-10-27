from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.engine.puestos import EQUIVALENCIAS

Bando = Literal["azul", "rojo"]
TipoUnidad = Literal["terrestre", "aerea", "naval", "base"]
Clima = Literal["despejado", "nublado", "lluvia", "tormenta"]
Rol = Literal["instructor", "azul", "rojo", "observador"]
# reparticion del TIEM dentro del bando (ver engine/puestos.py); solo tiene efecto en los alumnos. Acepta los ids
# anteriores (mando, inteligencia...) y los traduce.
Puesto = Annotated[Literal["comandante", "jem", "a1", "a2", "a3", "a3da", "a4", "ce"],
                   BeforeValidator(lambda v: EQUIVALENCIAS.get(v, v))]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    rol: str
    puesto: str = "comandante"
    activo: bool
    aprobado: bool = True
    debe_cambiar_clave: bool = False


class SolicitudCuentaIn(BaseModel):
    """Solicitud de cuenta hecha desde la pantalla de acceso (sin sesion); la aprueba un instructor."""

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=200)
    rol: Rol
    puesto: Puesto = "comandante"


class CambioClaveIn(BaseModel):
    actual: str = Field(min_length=1, max_length=200)
    nueva: str = Field(min_length=1, max_length=200)


class AprobacionIn(BaseModel):
    """Rol y puesto con que el instructor aprueba la solicitud (por defecto, los pedidos)."""

    rol: Rol | None = None
    puesto: Puesto | None = None


class UsuarioCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=200)
    rol: Rol
    puesto: Puesto = "comandante"


class UsuarioUpdate(BaseModel):
    password: str | None = Field(default=None, max_length=200)
    rol: Rol | None = None
    puesto: Puesto | None = None
    activo: bool | None = None


class EscenarioCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)


class EscenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    turno_actual: int
    fase: str
    estado: str
    clima: str = "despejado"
    azar: bool = False
    auto_resolver: bool = False
    limite_decision_seg: int | None = None
    decision_termina_en: datetime | None = None
    listo_azul: bool = False
    listo_rojo: bool = False
    archivado: bool = False
    hora_inicio_min: int = 360
    sim_segundos: float = 0.0
    velocidad: int = 60
    nacion_azul: str = ""
    nacion_rojo: str = ""
    # comunicaciones simuladas: solo las ve el instructor (state.estado_para las quita al resto)
    com_latencia_ms: int = 0
    com_jitter_ms: int = 0
    com_perdida_pct: int = 0
    com_ordenes_pct: int = 0
    niebla: bool = True
    logistica: bool = True
    efectos_clima: bool = True
    fuego_automatico: bool = True
    ia_azul: bool = False
    ia_rojo: bool = False
    ia_nivel: str = "normal"
    dia_noche: bool = False
    periodo: str = "dia"  # dia | crepusculo | noche del turno en curso (solo informa si dia_noche)
    # disponibilidad y fallas de las aeronaves y personal de cada bando (engine/disponibilidad.py, engine/toe.py)
    fallas: bool = False
    personal: dict | None = None
    inteligencia: dict | None = None  # satelites de cada bando (solo el instructor)
    apresto: dict | None = None  # grado de apresto y PCAO de cada bando (solo el instructor)
    # quien conduce cada bando: alumnos | instructor | ia
    conduccion_azul: str = "alumnos"
    conduccion_rojo: str = "alumnos"
    # calendario de la operacion (TIEM): dia D, hora H, fases y referencia del turno en curso
    fecha_inicio: str | None = None
    turno_h: int | None = None
    turno_final: int | None = None
    calendario: dict | None = None
    # juego de guerra: copia de ensayo de una F/A (ver app/ensayos.py)
    ensayo_de: int | None = None
    ensayo_bando: str | None = None
    ensayo_fa: str = ""


class FaseIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    desde: int = Field(ge=1, le=9999)
    hasta: int | None = Field(default=None, ge=1, le=9999)


class RedTransmisionIn(BaseModel):
    """Una red del plan de transmisiones (engine/transmisiones.py)."""

    red: Literal["mando", "gci", "ataque", "defensa", "logistica"]
    banda: Literal["HF", "VHF", "UHF"]
    primaria: float = Field(ge=0, le=1000)
    secundaria: float = Field(ge=0, le=1000)
    indicativo: str = Field(default="", max_length=12)


class PlanTransmisionesIn(BaseModel):
    bando: Literal["azul", "rojo"] | None = None  # solo el instructor elige el bando
    redes: list[RedTransmisionIn] = Field(min_length=1, max_length=8)


class FotoIn(BaseModel):
    """Foto que el instructor carga para un tipo de unidad (modelo) o una clase (engine/fotos_usuario.py)."""

    seccion: Literal["modelos", "clases"]
    id: str = Field(min_length=1, max_length=60)
    imagen: str = Field(min_length=10, max_length=17_000_000)  # data URL o base64 (hasta 12 MB de imagen)
    autor: str = Field(default="", max_length=120)
    fuente: str = Field(default="", max_length=300)
    recortar: bool = True  # recortar la unidad del fondo (si rembg esta instalado)


class AprestoBandoIn(BaseModel):
    """Grado de Apresto Operacional de un bando y plazos de la PCAO (engine/apresto.py)."""

    grado: Literal["paz", "elevado", "completo"] | None = None
    fase: int | None = Field(default=None, ge=1, le=3)  # elevado: 1 amarilla, 2 naranja, 3 roja
    adiestramiento: int | None = Field(default=None, ge=0, le=100)
    adiestramiento_meta: int | None = Field(default=None, ge=0, le=100)
    plazos: dict[Literal["aviso", "incorporacion", "organizacion", "material", "adiestramiento"], int] | None = None
    reiniciar_pcao: bool = False  # vuelve a tiempo de paz o elevado sin PCAO en marcha


class PcaoIn(BaseModel):
    bando: Literal["azul", "rojo"] | None = None  # solo el instructor elige el bando


class InteligenciaBandoIn(BaseModel):
    """Satelites de reconocimiento de un bando (engine/inteligencia.py)."""

    satelites: int | None = Field(default=None, ge=0, le=4)
    tipo: Literal["optico", "radar"] | None = None


class PersonalBandoIn(BaseModel):
    """Personal de un bando (engine/toe.py): % de la plantilla que tiene, reservas activas y milicianos disponibles
    para cubrir el deficit, y tripulaciones por aeronave (3 normal, 4 operaciones intensas)."""

    cobertura: int | None = Field(default=None, ge=0, le=100)
    reserva: int | None = Field(default=None, ge=0, le=1000000)
    milicia: int | None = Field(default=None, ge=0, le=1000000)
    tripulaciones: Literal[3, 4] | None = None


class RelojIn(BaseModel):
    """Reloj del SIETE en tiempo real: velocidad (segundos simulados por segundo real) y marcha o pausa."""

    velocidad: int | None = None
    estado: Literal["activo", "pausado"] | None = None


class EscenarioConfig(BaseModel):
    """Configuracion que el instructor puede cambiar en cualquier momento."""

    clima: Clima | None = None
    azar: bool | None = None
    auto_resolver: bool | None = None
    # 0 desactiva el limite de tiempo de la fase de decision
    limite_decision_seg: int | None = Field(default=None, ge=0, le=86400)
    # comunicaciones simuladas: demora base, variacion y probabilidad de perdida de los mensajes
    com_latencia_ms: int | None = Field(default=None, ge=0, le=60000)
    com_jitter_ms: int | None = Field(default=None, ge=0, le=60000)
    com_perdida_pct: int | None = Field(default=None, ge=0, le=100)
    # ordenes que no llegan a tiempo (se cumplen el turno siguiente)
    com_ordenes_pct: int | None = Field(default=None, ge=0, le=100)
    # hora simulada del turno 1, "HH:MM"
    hora_inicio: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    # interruptores del motor (direccion del ejercicio)
    niebla: bool | None = None
    logistica: bool | None = None
    efectos_clima: bool | None = None
    fuego_automatico: bool | None = None
    # adversario automatico: el simulador conduce ese bando
    ia_azul: bool | None = None
    ia_rojo: bool | None = None
    ia_nivel: Literal["prudente", "normal", "agresiva"] | None = None
    # ciclo de dia y noche: de noche se detecta menos a simple vista
    dia_noche: bool | None = None
    # disponibilidad y fallas de las aeronaves, y personal de cada bando: {"azul": {cobertura, reserva, milicia,
    # tripulaciones}, "rojo": {...}}
    fallas: bool | None = None
    personal: dict[Literal["azul", "rojo"], PersonalBandoIn] | None = None
    inteligencia: dict[Literal["azul", "rojo"], "InteligenciaBandoIn"] | None = None
    apresto: dict[Literal["azul", "rojo"], "AprestoBandoIn"] | None = None
    # identidad nacional de cada bando (ver /api/naciones); "" quita la identidad y deja "Azul"/"Rojo"
    nacion_azul: str | None = None
    nacion_rojo: str | None = None
    # quien conduce cada bando (a eleccion del instructor); "ia" equivale a encender ia_<bando>
    conduccion_azul: Literal["alumnos", "instructor", "ia"] | None = None
    conduccion_rojo: Literal["alumnos", "instructor", "ia"] | None = None
    # calendario: fecha del turno 1 ("" la quita), turno de la hora H y ultimo turno previsto (0 los quita) y fases
    # de la operacion ([] vuelve a las de por defecto)
    fecha_inicio: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    turno_h: int | None = Field(default=None, ge=0, le=9999)
    turno_final: int | None = Field(default=None, ge=0, le=9999)
    fases: list[FaseIn] | None = Field(default=None, max_length=8)


class ListoIn(BaseModel):
    listo: bool


class AsignacionIn(BaseModel):
    usuario_ids: list[int] = Field(default_factory=list, max_length=500)


class PrevisualizarIn(BaseModel):
    unidad_id: int
    waypoints: list[tuple[float, float]] = Field(min_length=1, max_length=120)


class RutaIn(BaseModel):
    unidad_id: int
    destino: tuple[float, float]


class UnidadCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    bando: Bando
    # Si se indica la clase (ver /api/catalogo), el tipo y los valores por defecto salen de ella.
    clase: str | None = Field(default=None, max_length=30)
    tipo: TipoUnidad | None = None
    echelon: str = Field(default="", max_length=40)
    # aeronaves: modelo del catalogo (f16, su30) y tamano del grupo aereo
    modelo: str | None = Field(default=None, max_length=30)
    aeronaves: int = Field(default=1, ge=1, le=12)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    fuerza: float = Field(default=100.0, gt=0, le=100)
    velocidad_kmh: float | None = Field(default=None, ge=0, le=3000)
    alcance_km: float | None = Field(default=None, ge=0, le=2000)
    deteccion_km: float | None = Field(default=None, ge=0, le=2000)
    autonomia_km: float | None = Field(default=None, gt=0, le=20000)
    # efectivos al inicio (None = la dotacion de su clase y escalon; ver engine/personal.py)
    personal: int | None = Field(default=None, ge=0, le=200000)
    # puentes: radio del tramo que corta su destruccion
    radio_km: float | None = Field(default=None, gt=0, le=20)
    # bases aereas y PRO: largo de la pista (PRO: solo en un tramo de carretera apto o en un aerodromo; 0 = sin pista)
    pista_m: float | None = Field(default=None, ge=0, le=6000)


class UnidadAjuste(BaseModel):
    """Ajuste manual del instructor (adjudicacion)."""

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    fuerza: float | None = Field(default=None, ge=0, le=100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    estado: Literal["activa", "destruida", "replegada"] | None = None
    combustible: float | None = Field(default=None, ge=0, le=100)
    municion: float | None = Field(default=None, ge=0, le=100)
    emitiendo: bool | None = None
    fuego_libre: bool | None = None
    # existencias de una base (puntos; 100 = llenar una unidad)
    stock_combustible: float | None = Field(default=None, ge=0, le=100000)
    stock_municion: float | None = Field(default=None, ge=0, le=100000)
    # bases aereas: daño por partes y refugios reforzados
    dano_pista: float | None = Field(default=None, ge=0, le=100)
    dano_plataforma: float | None = Field(default=None, ge=0, le=100)
    dano_combustible: float | None = Field(default=None, ge=0, le=100)
    refugios: int | None = Field(default=None, ge=0, le=24)
    pista_m: float | None = Field(default=None, ge=0, le=6000)  # 0 = la del plano del aerodromo
    personal: int | None = Field(default=None, ge=0, le=200000)


class PerfilVueloIn(BaseModel):
    """Perfil de vuelo de una aeronave propia: rige de inmediato (ver engine/relieve.py)."""

    perfil_vuelo: Literal["alto", "medio", "rasante"]


class DefensaIn(BaseModel):
    """Control de emisiones (radar), fuego automatico (antiaerea) y arma a emplear (sistemas de defensa aerea:
    el id del arma, o "" para la eleccion automatica) de una unidad propia."""

    emitiendo: bool | None = None
    fuego_libre: bool | None = None
    arma: str | None = Field(default=None, max_length=30)


class UnidadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escenario_id: int
    nombre: str
    bando: str
    tipo: str
    clase: str = ""
    modelo: str = ""
    aeronaves: int = 1
    en_tierra: bool = False
    base_id: int | None = None
    espera_restante: int = 0
    mision: str = ""
    mision_lat: float | None = None
    mision_lon: float | None = None
    blanco_id: int | None = None
    transporte_id: int | None = None
    dano_pista: float = 0.0
    dano_plataforma: float = 0.0
    dano_combustible: float = 0.0
    refugios: int = 0
    echelon: str
    lat: float
    lon: float
    fuerza: float
    velocidad_kmh: float
    alcance_km: float
    deteccion_km: float
    combustible: float = 100.0
    municion: float = 100.0
    autonomia_km: float = 300.0
    carga: float = 0.0
    recarga_restante: int = 0
    despliegue_restante: int = 0
    sidc: str
    estado: str
    terreno: str = ""
    emitiendo: bool | None = True
    fuego_libre: bool | None = True
    perfil_vuelo: str | None = None
    # perfil efectivo y los que puede elegir (aeronaves; ver engine/relieve.py)
    perfil_actual: str | None = None
    perfiles_permitidos: list[str] = []
    stock_combustible: float | None = None
    stock_municion: float | None = None
    # personal (ver engine/personal.py) y largo de los puentes
    personal_inicial: int | None = None
    personal_actual: int | None = None
    radio_km: float | None = None
    # sistemas de defensa aerea: misiles listos y en reserva de cada arma y el arma elegida (engine/defensa_aerea.py)
    sistema_da: dict | None = None
    # camino del ultimo turno (solo el propio bando: el del enemigo no se conoce)
    recorrido: list | None = None
    # tiempo real: waypoints que le faltan, orden que cumple y rumbo
    ruta: list = Field(default_factory=list)
    orden_id: int | None = None
    rumbo: float | None = None
    # bases aereas: largo de la pista y pista util con su dano (engine/plataformas.py)
    pista_largo_m: float | None = None
    pista_util_m: float | None = None


class OrdenCreate(BaseModel):
    unidad_id: int | None = None  # obligatorio salvo dentro de un lote (POST /ordenes/lote)
    tipo: Literal["mover", "atacar", "apoyar", "construir", "despegar", "patrullar", "aterrizar", "interferir", "lanzar", "embarcar", "desembarcar"]
    waypoints: list[tuple[float, float]] = Field(default_factory=list, max_length=120)  # rutas por carretera largas
    objetivo_unidad_id: int | None = None
    # solo para "construir": obra que se tiende en el punto indicado
    detalle: Literal["puente", "vado"] | None = None
    # solo para "despegar" (la unidad de la orden es la base aerea de origen)
    modelo: str | None = Field(default=None, max_length=30)
    aeronaves: int | None = Field(default=None, ge=1, le=12)
    indicativo: str | None = Field(default=None, max_length=40)
    # solo para "lanzar": misiles de crucero de la salva (el blanco va en objetivo_unidad_id)
    misiles: int | None = Field(default=None, ge=1, le=4)
    # solo para "atacar" a una base aerea o portaaviones: parte que se ataca (None = ataque general)
    parte: Literal["pista", "plataforma", "combustible"] | None = None


class OrdenLote(BaseModel):
    """La misma orden para varias unidades (seleccion multiple); `formacion` conserva las posiciones relativas."""

    unidad_ids: list[int] = Field(min_length=1, max_length=40)
    orden: "OrdenCreate"
    formacion: bool = True


class OrdenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escenario_id: int
    unidad_id: int
    tipo: str
    objetivo_unidad_id: int | None
    waypoints: list[list[float]] = Field(default_factory=list)
    detalle: str = ""
    turno_emitida: int
    emitida_seg: float | None = None
    llega_seg: float | None = None
    estado: str
    resultado: str
    # quien la emitio (nombre de usuario) y su puesto; vacios en las ordenes automaticas del motor
    autor: str = ""
    autor_puesto: str | None = None


class PuntoMisionIn(BaseModel):
    tipo: Literal["paso", "orbita", "blanco", "aterrizaje"]
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    turnos: int = Field(default=1, ge=1, le=12)  # solo orbita
    objetivo_unidad_id: int | None = None  # solo blanco (opcional: sin el, ataca al enemigo detectado mas cercano)
    base_id: int | None = None  # solo aterrizaje
    centro: tuple[float, float] | None = None  # orbita de guerra electronica: punto que interfiere
    perfil: Literal["alto", "medio", "rasante"] | None = None  # altura del tramo que llega a este punto
    reunion: bool = False  # solo paso: punto de reunion del paquete (espera a los demas grupos)
    reabastecimiento: bool = False  # solo paso: punto de reabastecimiento en vuelo (espera un turno a la cisterna)
    corte: bool = False  # solo blanco sin unidad: corte de carretera (crater) en ese punto


class OtaMisionIn(BaseModel):
    """Datos de la mision en la OTA (directiva AV/D 5-47)."""

    paquete: str = Field(default="", max_length=12)
    funcion: Literal["CM", "ACM", "-"] = "-"
    alerta: int = Field(default=1, ge=1, le=3)
    armamento_primario: str = Field(default="", max_length=5)
    armamento_secundario: str = Field(default="", max_length=5)
    iff: str = Field(default="", max_length=5)
    codigo: str = Field(default="", max_length=5)  # codigo de mision de la tabla (vacio: el del rol)
    pdi: str = Field(default="", max_length=30)
    tot_turno: int | None = None  # turno sobre el blanco: con despegue desde una base, fija el turno de despegue


class MisionIn(BaseModel):
    """Mision aerea: para un grupo existente (unidad_id) o para uno que despegara de una base (base_id + modelo)."""

    rol: str = Field(max_length=20)
    nombre: str = Field(default="", max_length=40)
    puntos: list[PuntoMisionIn] = Field(min_length=1, max_length=12)
    unidad_id: int | None = None
    base_id: int | None = None
    modelo: str | None = Field(default=None, max_length=30)
    aeronaves: int | None = Field(default=None, ge=1, le=12)
    turno_despegue: int | None = None
    # rol ESCOLTA: mision que escolta; paquete: escolta que se crea junto con esta mision (mismo turno de despegue)
    escolta_de: int | None = None
    escolta: "EscoltaIn | None" = None
    ota: OtaMisionIn | None = None


class EscoltaIn(BaseModel):
    """Escolta de un paquete: un grupo existente o un grupo que despega de una base con la mision escoltada."""

    unidad_id: int | None = None
    base_id: int | None = None
    modelo: str | None = Field(default=None, max_length=30)
    aeronaves: int | None = Field(default=None, ge=1, le=12)
    nombre: str = Field(default="", max_length=40)


class ZonaClimaIn(BaseModel):
    tipo: Literal["nublado", "lluvia", "tormenta"]
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radio_km: float = Field(default=60.0, ge=1, le=1000)
    deriva_rumbo: float = Field(default=0.0, ge=-360, le=720)
    deriva_kmh: float = Field(default=0.0, ge=0, le=200)
    turnos: int | None = Field(default=None, ge=1, le=240)  # None = hasta que el instructor la quite
    nombre: str | None = Field(default=None, max_length=60)


class EventoCreate(BaseModel):
    tipo: str = Field(default="general", max_length=40)
    descripcion: str = Field(min_length=1, max_length=1000)
    bando_destino: Literal["todos", "azul", "rojo"] = "todos"
    # informe con posicion (inteligencia, poblacion, reconocimiento...): marca en el mapa durante `turnos` turnos
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    turnos: int | None = Field(default=None, ge=1, le=48)
    fuente: str = Field(default="", max_length=60)  # "Inteligencia", "Poblacion", "Reconocimiento aereo"...


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escenario_id: int
    turno: int
    tipo: str
    descripcion: str
    bando_destino: str
    lat: float | None = None
    lon: float | None = None
    hasta_turno: int | None = None
    fuente: str = ""


class ObraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bando: str
    tipo: str
    lat: float
    lon: float
    radio_km: float
    creada_turno: int
    expira_turno: int


class ObjetivoIn(BaseModel):
    tipo: Literal["ocupar", "destruir", "neutralizar", "proteger", "efecto"]
    bando: Bando
    nombre: str = Field(min_length=1, max_length=120)
    puntos: int = Field(default=10, ge=0, le=1000)
    # ocupar
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    radio_km: float = Field(default=5.0, gt=0, le=200)
    turnos_requeridos: int = Field(default=1, ge=1, le=48)
    # destruir / neutralizar / proteger
    unidad_id: int | None = None
    # proteger: hasta cuando; en los demas, plazo (si llega sin cumplirse, falla)
    hasta_turno: int | None = Field(default=None, ge=1, le=999)
    # cadena de objetivos del TIEM
    nivel: Literal["ulterior", "asignado", "material"] = "material"
    padre_id: int | None = None
    efecto: str = Field(default="", max_length=300)
    indicador: str = Field(default="", max_length=300)
    # neutralizar: fuerza (%) a alcanzar; efecto: % de los objetivos dependientes que deben cumplirse
    umbral: float | None = Field(default=None, ge=0, le=100)


class ObjetivoEdicion(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    puntos: int | None = Field(default=None, ge=0, le=1000)
    hasta_turno: int | None = Field(default=None, ge=1, le=999)
    padre_id: int | None = None
    efecto: str | None = Field(default=None, max_length=300)
    indicador: str | None = Field(default=None, max_length=300)
    umbral: float | None = Field(default=None, ge=0, le=100)


class ObjetivoOut(BaseModel):
    id: int
    bando: str
    tipo: str
    nombre: str
    puntos: int
    lat: float | None = None
    lon: float | None = None
    radio_km: float
    turnos_requeridos: int
    progreso: int
    unidad_id: int | None = None
    unidad_nombre: str = ""
    hasta_turno: int | None = None
    estado: str
    turno_resuelto: int | None = None
    nivel: str = "material"
    padre_id: int | None = None
    efecto: str = ""
    indicador: str = ""
    umbral: float | None = None
    avance: dict | None = None  # efecto: {cumplidos, total, requerido_pct}


TipoGrafico = Literal["linea_fase", "eje_avance", "zona_reunion", "punto_control"]


class GraficoIn(BaseModel):
    tipo: TipoGrafico
    etiqueta: str = Field(default="", max_length=60)
    # geometria GeoJSON (Point, LineString o Polygon); se valida en el servidor segun el tipo
    geometria: dict
    # solo el instructor puede elegir el bando ("todos" = visible para ambos)
    bando: Literal["azul", "rojo", "todos"] | None = None


class GraficoOut(BaseModel):
    id: int
    bando: str
    tipo: str
    etiqueta: str
    geometria: dict
    autor: str
    turno: int


class MensajeOut(BaseModel):
    id: int
    canal: str
    remitente: str
    rol: str
    texto: str
    turno: int
    creado_en: datetime


class PlantillaGuardarIn(BaseModel):
    """Guardar el escenario actual como plantilla del instructor (engine/plantillas.py)."""

    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str = Field(default="", max_length=1000)
    # True: conserva fuerza, combustible, municion y existencias actuales; False: todo al 100 %
    con_estado: bool = False
    reemplazar: bool = False
