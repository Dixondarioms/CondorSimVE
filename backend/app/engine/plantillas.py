"""Escenarios precargados: el instructor crea un escenario nuevo a partir de una plantilla (unidades,
objetivos, clima e identidad nacional ya definidos) en lugar de armarlo unidad por unidad.

Las plantillas son datos declarativos (`Plantilla`); `crear_desde_plantilla` las traduce a filas reales
(`Unidad`, `Objetivo`) con el mismo motor y catalogo que usa el resto de la aplicacion.

Hay dos origenes: las declaradas en este archivo (`PLANTILLAS`, origen "codigo") y las que el instructor
guarda desde la interfaz a partir de un escenario en curso (origen "usuario"), un archivo JSON por plantilla
en `backend/data/plantillas_usuario/<id>.json` (`guardar_desde_escenario`, `cargar_usuario`, `eliminar_usuario`).
`todas()` reune ambas y `obtener(id)` busca en las dos."""

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.engine import catalogo
from app.models.escenario import Escenario
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad

log = logging.getLogger("uvicorn.error")

# Carpeta de las plantillas guardadas por el instructor (SIMULADOR_PLANTILLAS_USUARIO la cambia; las pruebas la
# apuntan a una carpeta temporal).
RUTA_PLANTILLAS_USUARIO = Path(
    os.environ.get("SIMULADOR_PLANTILLAS_USUARIO")
    or Path(__file__).resolve().parent.parent.parent / "data" / "plantillas_usuario"
)
PATRON_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,59}$")
LARGO_MAX_ID = 60
LARGO_MAX_NOMBRE = 80
LARGO_MAX_DESCRIPCION = 1000


class PlantillaInvalida(ValueError):
    """Nombre, id o contenido de plantilla inaceptable (la API lo traduce a 400)."""


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
    # estado logistico opcional (solo lo llevan las plantillas guardadas "con estado"); None = valor por defecto
    combustible: float | None = None
    municion: float | None = None
    stock_combustible: float | None = None
    stock_municion: float | None = None
    # aeronave estacionada en una base de esta misma plantilla (por nombre)
    en_tierra: bool = False
    base: str | None = None


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
    origen: str = "codigo"  # "codigo" (declarada aqui) | "usuario" (guardada desde la interfaz)
    con_estado: bool = False
    guardada_en: str = ""
    escenario_origen: int | None = None


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


def obtener(plantilla_id: str) -> Plantilla | None:
    """Plantilla por id, sea del codigo o guardada por el instructor."""
    return PLANTILLAS.get(plantilla_id) or cargar_usuario().get(plantilla_id)


def todas() -> dict[str, Plantilla]:
    """Las del codigo primero, despues las del instructor (una del instructor no puede tapar una del codigo)."""
    return {**{k: v for k, v in cargar_usuario().items() if k not in PLANTILLAS}, **PLANTILLAS}


def crear_desde_plantilla(db: Session, plantilla_id: str) -> Escenario:
    """Crea un escenario nuevo con las unidades y objetivos de la plantilla. Lanza KeyError si no existe."""
    p = obtener(plantilla_id)
    if p is None:
        raise KeyError(plantilla_id)
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
        for campo in ("combustible", "municion", "stock_combustible", "stock_municion"):
            valor = getattr(u, campo)
            if valor is not None:
                setattr(unidad, campo, valor)
        db.add(unidad)
        db.flush()
        unidades[u.nombre] = unidad
    for u in p.unidades:
        if u.en_tierra and u.base and u.base in unidades:
            unidades[u.nombre].en_tierra = True
            unidades[u.nombre].base_id = unidades[u.base].id

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
        "origen": p.origen, "con_estado": p.con_estado, "guardada_en": p.guardada_en,
    }


# ---------------------------------------------------------------------------------------------------------
# Plantillas guardadas por el instructor desde un escenario (archivos JSON en RUTA_PLANTILLAS_USUARIO)
_CAMPOS_ESTADO = ("fuerza", "combustible", "municion", "stock_combustible", "stock_municion")


def generar_id(nombre: str) -> str:
    """Identificador de archivo a partir del nombre: minusculas sin acentos, [a-z0-9-], maximo 60 caracteres."""
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", plano).strip("-")[:LARGO_MAX_ID].strip("-")
    return slug


def validar_id(plantilla_id: str) -> str:
    """Solo [a-z0-9_-], hasta 60 caracteres, sin separadores de ruta: no puede salir de la carpeta."""
    if not isinstance(plantilla_id, str) or not PATRON_ID.match(plantilla_id):
        raise PlantillaInvalida("Identificador de plantilla invalido (use letras minusculas, numeros, '-' o '_')")
    return plantilla_id


def _ruta(plantilla_id: str) -> Path:
    validar_id(plantilla_id)
    carpeta = RUTA_PLANTILLAS_USUARIO.resolve()
    ruta = (carpeta / f"{plantilla_id}.json").resolve()
    if ruta.parent != carpeta:
        raise PlantillaInvalida("Identificador de plantilla invalido")
    return ruta


def serializar_escenario(db: Session, esc: Escenario, nombre: str, descripcion: str, con_estado: bool) -> dict:
    """Describe el escenario TAL COMO ESTA AHORA (posiciones actuales, no las iniciales) como plantilla.

    Las unidades destruidas no se guardan. Sin `con_estado`, todas arrancan al 100 % de fuerza, combustible,
    municion y existencias; con `con_estado` se conserva el nivel actual de cada una."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise PlantillaInvalida("Indique un nombre para la plantilla")
    if len(nombre) > LARGO_MAX_NOMBRE:
        raise PlantillaInvalida(f"El nombre no puede superar los {LARGO_MAX_NOMBRE} caracteres")
    plantilla_id = generar_id(nombre)
    if not plantilla_id:
        raise PlantillaInvalida("El nombre debe contener al menos una letra o un numero")
    if plantilla_id.replace("-", "_") in {k.replace("-", "_") for k in PLANTILLAS}:
        raise PlantillaInvalida("Ese nombre coincide con una plantilla del sistema: elija otro")
    descripcion = (descripcion or "").strip()[:LARGO_MAX_DESCRIPCION]

    filas = [u for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id).order_by(Unidad.id)
             if u.estado != "destruida"]
    nombres: dict[int, str] = {}
    unidades = []
    for u in filas:
        # dos unidades con el mismo nombre se distinguen con un sufijo (los objetivos las referencian por nombre)
        base = u.nombre.strip() or f"Unidad {u.id}"
        n, candidato = 2, base
        while candidato in nombres.values():
            candidato = f"{base} ({n})"
            n += 1
        nombres[u.id] = candidato
        clase = catalogo.obtener(u.clase, u.tipo)
        modelo = catalogo.MODELOS.get(u.modelo or "")
        d = {
            "nombre": candidato, "bando": u.bando, "clase": clase.id, "lat": round(u.lat, 6), "lon": round(u.lon, 6),
            "escalon": u.echelon or "", "modelo": modelo.id if modelo and modelo.clase == clase.id else "",
            "aeronaves": int(u.aeronaves or 1),
        }
        if con_estado:
            d.update({c: round(float(getattr(u, c)), 2) for c in _CAMPOS_ESTADO})
        if u.en_tierra and u.base_id in {f.id for f in filas}:
            d["en_tierra"] = True
            d["base"] = u.base_id  # se traduce a nombre mas abajo
        unidades.append(d)
    for d in unidades:
        if d.get("base") is not None:
            d["base"] = nombres[d["base"]]

    objetivos = []
    for o in db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).order_by(Objetivo.id):
        if o.tipo in ("destruir", "proteger") and o.unidad_id not in nombres:
            continue  # la unidad ya no existe: el objetivo no tiene sentido en la plantilla
        objetivos.append({
            "bando": o.bando, "tipo": o.tipo, "nombre": o.nombre, "puntos": o.puntos, "lat": o.lat, "lon": o.lon,
            "radio_km": o.radio_km, "turnos_requeridos": o.turnos_requeridos,
            "unidad": nombres.get(o.unidad_id) if o.unidad_id is not None else None, "hasta_turno": o.hasta_turno,
        })
    return {
        "id": plantilla_id, "nombre": nombre, "descripcion": descripcion, "origen": "usuario",
        "guardada_en": datetime.now(timezone.utc).isoformat(timespec="seconds"), "escenario_origen": esc.id,
        "con_estado": bool(con_estado), "clima": esc.clima, "hora_inicio_min": esc.hora_inicio_min,
        "nacion_azul": esc.nacion_azul or "", "nacion_rojo": esc.nacion_rojo or "",
        "unidades": unidades, "objetivos": objetivos,
    }


def desde_dict(datos: dict) -> Plantilla:
    """Construye la Plantilla (mismos dataclasses que las del codigo) a partir del JSON, validando lo esencial."""
    if not isinstance(datos, dict):
        raise PlantillaInvalida("Plantilla mal formada")
    plantilla_id = validar_id(datos.get("id"))
    nombre = str(datos.get("nombre") or "").strip()
    if not nombre:
        raise PlantillaInvalida("Plantilla sin nombre")
    unidades: list[UnidadPlantilla] = []
    vistos: set[str] = set()
    for d in datos.get("unidades") or []:
        clase = d.get("clase")
        if clase not in catalogo.CLASES:
            raise PlantillaInvalida(f"Clase de unidad desconocida: {clase!r}")
        if d.get("bando") not in ("azul", "rojo"):
            raise PlantillaInvalida("Bando de unidad invalido")
        nombre_u = str(d.get("nombre") or "").strip()
        if not nombre_u or nombre_u in vistos:
            raise PlantillaInvalida("Nombres de unidad vacios o repetidos")
        vistos.add(nombre_u)
        modelo = d.get("modelo") or ""
        if modelo and (modelo not in catalogo.MODELOS or catalogo.MODELOS[modelo].clase != clase):
            modelo = ""
        lat, lon = float(d.get("lat")), float(d.get("lon"))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise PlantillaInvalida("Coordenadas de unidad fuera de rango")

        def pct(campo, por_defecto=None):
            v = d.get(campo)
            return por_defecto if v is None else max(0.0, float(v))

        unidades.append(UnidadPlantilla(
            nombre_u, d["bando"], clase, lat, lon, escalon=str(d.get("escalon") or ""), modelo=modelo,
            aeronaves=max(1, int(d.get("aeronaves") or 1)), fuerza=min(100.0, pct("fuerza", 100.0)),
            combustible=pct("combustible"), municion=pct("municion"),
            stock_combustible=pct("stock_combustible"), stock_municion=pct("stock_municion"),
            en_tierra=bool(d.get("en_tierra")), base=d.get("base") or None,
        ))
    objetivos: list[ObjetivoPlantilla] = []
    for d in datos.get("objetivos") or []:
        if d.get("tipo") not in ("ocupar", "destruir", "proteger") or d.get("bando") not in ("azul", "rojo"):
            raise PlantillaInvalida("Objetivo con tipo o bando invalido")
        unidad = d.get("unidad")
        if d["tipo"] != "ocupar" and unidad not in vistos:
            raise PlantillaInvalida(f"El objetivo {d.get('nombre')!r} referencia una unidad que no esta en la plantilla")
        objetivos.append(ObjetivoPlantilla(
            d["bando"], d["tipo"], str(d.get("nombre") or "Objetivo"), int(d.get("puntos") or 0),
            lat=d.get("lat"), lon=d.get("lon"), radio_km=float(d.get("radio_km") or 5.0),
            turnos_requeridos=int(d.get("turnos_requeridos") or 1), unidad=unidad if d["tipo"] != "ocupar" else None,
            hasta_turno=d.get("hasta_turno"),
        ))
    return Plantilla(
        id=plantilla_id, nombre=nombre, descripcion=str(datos.get("descripcion") or ""),
        clima=str(datos.get("clima") or "despejado"), hora_inicio_min=int(datos.get("hora_inicio_min") or 360),
        nacion_azul=str(datos.get("nacion_azul") or ""), nacion_rojo=str(datos.get("nacion_rojo") or ""),
        unidades=tuple(unidades), objetivos=tuple(objetivos), origen="usuario",
        con_estado=bool(datos.get("con_estado")), guardada_en=str(datos.get("guardada_en") or ""),
        escenario_origen=datos.get("escenario_origen"),
    )


def guardar_desde_escenario(db: Session, esc: Escenario, nombre: str, descripcion: str = "",
                            con_estado: bool = False, reemplazar: bool = False) -> Plantilla:
    """Guarda el escenario actual como plantilla del instructor. Lanza PlantillaInvalida o FileExistsError."""
    datos = serializar_escenario(db, esc, nombre, descripcion, con_estado)
    plantilla = desde_dict(datos)  # valida antes de escribir
    ruta = _ruta(plantilla.id)
    if ruta.exists() and not reemplazar:
        raise FileExistsError(plantilla.id)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    return plantilla


def cargar_usuario() -> dict[str, Plantilla]:
    """Plantillas guardadas por el instructor; un archivo corrupto se omite con un aviso en el registro."""
    carpeta = RUTA_PLANTILLAS_USUARIO
    if not carpeta.is_dir():
        return {}
    resultado: dict[str, Plantilla] = {}
    for archivo in sorted(carpeta.glob("*.json")):
        try:
            p = desde_dict(json.loads(archivo.read_text(encoding="utf-8")))
            if p.id != archivo.stem:
                raise PlantillaInvalida(f"el id {p.id!r} no coincide con el archivo")
        except (PlantillaInvalida, ValueError, TypeError, KeyError, OSError) as exc:
            log.warning("Plantilla de usuario ignorada (%s): %s", archivo.name, exc)
            continue
        resultado[p.id] = p
    return resultado


def eliminar_usuario(plantilla_id: str) -> bool:
    """Borra el archivo de una plantilla del instructor; False si no existia. Las del codigo no se tocan."""
    if plantilla_id in PLANTILLAS:
        raise PlantillaInvalida("Las plantillas del sistema no se pueden eliminar")
    ruta = _ruta(plantilla_id)
    if not ruta.is_file():
        return False
    ruta.unlink()
    return True
