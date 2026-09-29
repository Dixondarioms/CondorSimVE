"""Escenarios precargados: el instructor crea un escenario nuevo a partir de una plantilla (unidades,
objetivos, clima e identidad nacional ya definidos) en lugar de armarlo unidad por unidad.

Las plantillas son datos declarativos (`Plantilla`); `crear_desde_plantilla` las traduce a filas reales
(`Unidad`, `Objetivo`) con el mismo motor y catalogo que usa el resto de la aplicacion."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.engine import catalogo
from app.models.escenario import Escenario
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad


@dataclass(frozen=True)
class UnidadPlantilla:
    nombre: str
    bando: str
    clase: str
    lat: float
    lon: float
    escalon: str = ""
    modelo: str = ""
    aeronaves: int = 1
    fuerza: float = 100.0


@dataclass(frozen=True)
class ObjetivoPlantilla:
    bando: str
    tipo: str  # "ocupar" | "destruir" | "proteger"
    nombre: str
    puntos: int = 20
    lat: float | None = None
    lon: float | None = None
    radio_km: float = 5.0
    turnos_requeridos: int = 1
    unidad: str | None = None  # nombre de una UnidadPlantilla de esta misma plantilla (destruir/proteger)
    hasta_turno: int | None = None


@dataclass(frozen=True)
class Plantilla:
    id: str
    nombre: str
    descripcion: str
    clima: str = "despejado"
    hora_inicio_min: int = 360
    nacion_azul: str = "venezuela"
    nacion_rojo: str = ""
    unidades: tuple[UnidadPlantilla, ...] = field(default_factory=tuple)
    objetivos: tuple[ObjetivoPlantilla, ...] = field(default_factory=tuple)


_DEMO_LLANOS = Plantilla(
    id="demo_llanos", nombre="Demo: Piedemonte andino - Llanos",
    descripcion="Escenario de práctica genérico (no representa un hecho real): ambos bandos empiezan sin "
    "verse entre sí. Sirve para ensayar el flujo de órdenes, la niebla de guerra y el combate básico.",
    unidades=(
        UnidadPlantilla("1ra Brigada de Infanteria", "azul", "infanteria", 8.60, -70.60, "brigada"),
        UnidadPlantilla("Grupo Blindado A", "azul", "blindado", 8.62, -70.45, "batallon"),
        UnidadPlantilla("Artilleria de Campana A", "azul", "artilleria", 8.60, -70.55, "batallon"),
        UnidadPlantilla("Ala de Caza 1", "azul", "caza", 8.70, -70.40),
        UnidadPlantilla("Base Aerea Barinas", "azul", "base_aerea", 8.62, -70.21),
        UnidadPlantilla("Batallon de Montana R", "rojo", "infanteria", 8.60, -70.85, "batallon"),
        UnidadPlantilla("Compania de Fusileros R", "rojo", "infanteria", 8.75, -70.95, "compania"),
        UnidadPlantilla("Escuadrilla R", "rojo", "caza", 8.80, -71.20),
        UnidadPlantilla("Deposito R Merida", "rojo", "deposito", 8.59, -71.14),
    ),
)

_DEFENSA_3_ENERO = Plantilla(
    id="defensa_3_enero_2026", nombre="3 de enero de 2026 (estudio): defensa del litoral central",
    descripcion=(
        "Ejercicio de estudio para practicar la defensa aérea y naval del litoral central en las horas previas "
        "a un ataque como el ocurrido la madrugada del 3 de enero de 2026, cuando fuerzas de EE. UU. "
        "bombardearon instalaciones militares en Caracas y Vargas (\"Operación Resolución Absoluta\"). "
        "La ubicación de las unidades propias (La Carlota, Fuerte Tiuna, La Guaira, Charallave) es real; las "
        "fuerzas y la composición exacta de ambos bandos son una simplificación para el ejercicio, no una "
        "reconstrucción de las unidades que realmente intervinieron (que incluyeron cazas F-22/F-35, "
        "bombarderos B-1B y un mayor número de medios). El bando rojo se deja sin modelo de aeronave "
        "específico por esa razón. El desenlace político real (captura del jefe de Estado) queda fuera del "
        "alcance de este ejercicio táctico. Cifras de bajas y detalles varían entre fuentes; usar como "
        "punto de partida para el análisis, no como registro histórico definitivo."
    ),
    clima="despejado", hora_inicio_min=120, nacion_azul="venezuela", nacion_rojo="estados_unidos",
    unidades=(
        UnidadPlantilla("Base Aérea La Carlota", "azul", "base_aerea", 10.4850, -66.8436),
        UnidadPlantilla("Escuadrón de Caza La Carlota", "azul", "caza", 10.4920, -66.8300, "escuadrilla", "f16", 4),
        UnidadPlantilla("AA La Carlota", "azul", "antiaerea", 10.4830, -66.8500),
        UnidadPlantilla("Guarnición Fuerte Tiuna", "azul", "infanteria", 10.4675, -66.9581, "brigada"),
        UnidadPlantilla("Puesto Naval La Guaira", "azul", "patrullero", 10.6050, -66.9250),
        UnidadPlantilla("Guarnición Charallave", "azul", "infanteria", 10.2869, -66.8158, "compania"),
        UnidadPlantilla("Paquete de Ataque 1", "rojo", "ataque", 11.40, -66.85),
        UnidadPlantilla("Paquete de Ataque 2", "rojo", "caza", 11.35, -67.05),
        UnidadPlantilla("Grupo Naval de Superficie", "rojo", "fragata", 11.00, -66.95),
    ),
    objetivos=(
        ObjetivoPlantilla("azul", "proteger", "Mantener operativa La Carlota", 30, unidad="Base Aérea La Carlota", hasta_turno=8),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar La Carlota", 30, unidad="Base Aérea La Carlota"),
        ObjetivoPlantilla("azul", "proteger", "Mantener Fuerte Tiuna", 25, unidad="Guarnición Fuerte Tiuna", hasta_turno=8),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar Fuerte Tiuna", 25, unidad="Guarnición Fuerte Tiuna"),
        ObjetivoPlantilla("azul", "proteger", "Proteger el puerto de La Guaira", 20, unidad="Puesto Naval La Guaira", hasta_turno=8),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar la defensa naval de La Guaira", 20, unidad="Puesto Naval La Guaira"),
        ObjetivoPlantilla("azul", "proteger", "Proteger Charallave", 15, unidad="Guarnición Charallave", hasta_turno=8),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar Charallave", 15, unidad="Guarnición Charallave"),
    ),
)

PLANTILLAS: dict[str, Plantilla] = {p.id: p for p in [_DEMO_LLANOS, _DEFENSA_3_ENERO]}


def crear_desde_plantilla(db: Session, plantilla_id: str) -> Escenario:
    """Crea un escenario nuevo con las unidades y objetivos de la plantilla. Lanza KeyError si no existe."""
    p = PLANTILLAS[plantilla_id]
    esc = Escenario(nombre=p.nombre, clima=p.clima, hora_inicio_min=p.hora_inicio_min,
                    nacion_azul=p.nacion_azul, nacion_rojo=p.nacion_rojo)
    db.add(esc)
    db.flush()

    unidades: dict[str, Unidad] = {}
    for u in p.unidades:
        modelo = catalogo.MODELOS.get(u.modelo) if u.modelo else None
        c = catalogo.CLASES[u.clase]
        ref = modelo or c
        unidad = Unidad(
            escenario_id=esc.id, nombre=u.nombre, bando=u.bando, tipo=c.tipo, clase=c.id,
            modelo=modelo.id if modelo else "", aeronaves=u.aeronaves if modelo else 1,
            echelon=u.escalon or (catalogo.escalon_grupo(u.aeronaves) if modelo else c.escalon),
            lat=u.lat, lon=u.lon, fuerza=u.fuerza, velocidad_kmh=ref.velocidad_kmh, alcance_km=ref.alcance_km,
            deteccion_km=ref.deteccion_km, autonomia_km=ref.autonomia_km, carga=c.carga_max,
            sidc=catalogo.generar_sidc(u.bando, c, u.escalon or (catalogo.escalon_grupo(u.aeronaves) if modelo else "")),
        )
        db.add(unidad)
        db.flush()
        unidades[u.nombre] = unidad

    for o in p.objetivos:
        db.add(Objetivo(
            escenario_id=esc.id, bando=o.bando, tipo=o.tipo, nombre=o.nombre, puntos=o.puntos,
            lat=o.lat, lon=o.lon, radio_km=o.radio_km, turnos_requeridos=o.turnos_requeridos,
            unidad_id=unidades[o.unidad].id if o.unidad else None, hasta_turno=o.hasta_turno,
        ))

    db.commit()
    db.refresh(esc)
    return esc


def plantilla_dict(p: Plantilla) -> dict:
    return {
        "id": p.id, "nombre": p.nombre, "descripcion": p.descripcion, "nacion_azul": p.nacion_azul,
        "nacion_rojo": p.nacion_rojo, "unidades": len(p.unidades), "objetivos": len(p.objetivos),
    }
