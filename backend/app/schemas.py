from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Bando = Literal["azul", "rojo"]
TipoUnidad = Literal["terrestre", "aerea", "naval", "base"]
Clima = Literal["despejado", "nublado", "lluvia", "tormenta"]
Rol = Literal["instructor", "azul", "rojo", "observador"]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    rol: str
    activo: bool


class UsuarioCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=200)
    rol: Rol


class UsuarioUpdate(BaseModel):
    password: str | None = Field(default=None, max_length=200)
    rol: Rol | None = None
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
    # comunicaciones simuladas: solo las ve el instructor (state.estado_para las quita al resto)
    com_latencia_ms: int = 0
    com_jitter_ms: int = 0
    com_perdida_pct: int = 0


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
    # hora simulada del turno 1, "HH:MM"
    hora_inicio: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ListoIn(BaseModel):
    listo: bool


class AsignacionIn(BaseModel):
    usuario_ids: list[int] = Field(default_factory=list, max_length=500)


class PrevisualizarIn(BaseModel):
    unidad_id: int
    waypoints: list[tuple[float, float]] = Field(min_length=1, max_length=30)


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


class UnidadAjuste(BaseModel):
    """Ajuste manual del instructor (adjudicacion)."""

    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    fuerza: float | None = Field(default=None, ge=0, le=100)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    estado: Literal["activa", "destruida", "replegada"] | None = None
    combustible: float | None = Field(default=None, ge=0, le=100)
    municion: float | None = Field(default=None, ge=0, le=100)


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


class OrdenCreate(BaseModel):
    unidad_id: int
    tipo: Literal["mover", "atacar", "apoyar", "construir", "despegar"]
    waypoints: list[tuple[float, float]] = Field(default_factory=list, max_length=30)
    objetivo_unidad_id: int | None = None
    # solo para "construir": obra que se tiende en el punto indicado
    detalle: Literal["puente", "vado"] | None = None
    # solo para "despegar" (la unidad de la orden es la base aerea de origen)
    modelo: str | None = Field(default=None, max_length=30)
    aeronaves: int | None = Field(default=None, ge=1, le=12)
    indicativo: str | None = Field(default=None, max_length=40)


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
    estado: str
    resultado: str


class EventoCreate(BaseModel):
    tipo: str = Field(default="general", max_length=40)
    descripcion: str = Field(min_length=1, max_length=1000)
    bando_destino: Literal["todos", "azul", "rojo"] = "todos"


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escenario_id: int
    turno: int
    tipo: str
    descripcion: str
    bando_destino: str


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
