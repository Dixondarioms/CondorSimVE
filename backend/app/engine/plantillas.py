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

from app.engine import catalogo, relieve
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
    perfil_vuelo: str | None = None  # aeronaves: "alto" | "medio" | "rasante" (None = el de su clase)
    personal: int | None = None  # efectivos al inicio (None = los de su clase; ver engine/personal.py)
    radio_km: float | None = None  # puentes: tramo que corta su destruccion


@dataclass(frozen=True)
class ObjetivoPlantilla:
    bando: str
    tipo: str  # "ocupar" | "destruir" | "neutralizar" | "proteger" | "efecto"
    nombre: str
    puntos: int = 20
    lat: float | None = None
    lon: float | None = None
    radio_km: float = 5.0
    turnos_requeridos: int = 1
    unidad: str | None = None  # nombre de una UnidadPlantilla de esta misma plantilla (destruir/proteger)
    hasta_turno: int | None = None
    # cadena de objetivos del TIEM (ver engine/objetivos.py); `padre` es el nombre del objetivo superior
    nivel: str = "material"
    padre: str | None = None
    efecto: str = ""
    indicador: str = ""
    umbral: float | None = None


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
    # adversario automatico ya encendido (el simulador conduce ese bando desde el primer turno)
    ia_azul: bool = False
    ia_rojo: bool = False
    dia_noche: bool = False  # ciclo de dia y noche encendido
    # TIEM: quien conduce cada bando, calendario D/H y Problema Militar Operativo de cada bando ({bando: contenido})
    conduce_azul: str = "alumnos"
    conduce_rojo: str = "alumnos"
    fecha_inicio: str | None = None
    turno_h: int | None = None
    turno_final: int | None = None
    fases: tuple = ()
    pmo: dict = field(default_factory=dict)


_DEMO_LLANOS = Plantilla(
    id="demo_llanos", nombre="Demo: Piedemonte andino - Llanos",
    descripcion="Escenario de práctica genérico (no representa un hecho real): ambos bandos empiezan sin "
    "verse entre sí. Sirve para ensayar el flujo de órdenes, la niebla de guerra y el combate básico.",
    unidades=(
        UnidadPlantilla("1ra Brigada de Infanteria", "azul", "infanteria", 8.60, -70.60, "brigada"),
        UnidadPlantilla("Grupo Blindado A", "azul", "blindado", 8.62, -70.45, "batallon"),
        UnidadPlantilla("Artilleria de Campana A", "azul", "artilleria", 8.60, -70.55, "batallon"),
        UnidadPlantilla("Ala de Caza 1", "azul", "caza", 8.70, -70.40),
        # base del ejercicio que opera desde el aeropuerto civil de Barinas (SVBI): no es una base de la AMB
        UnidadPlantilla("Aeropuerto de Barinas", "azul", "base_aerea", 8.62, -70.21),
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

def _av(nombre, modelo, n, lat, lon, perfil=None, base=None):
    """Grupo de aeronaves de EE. UU. de la reconstruccion del 3 de enero (bando rojo)."""
    return UnidadPlantilla(nombre, "rojo", catalogo.MODELOS[modelo].clase, lat, lon, modelo=modelo, aeronaves=n,
                           perfil_vuelo=perfil, en_tierra=base is not None, base=base)


_ATAQUE_3_ENERO = Plantilla(
    id="ataque_3_enero_2026", nombre="3 de enero de 2026: Operación Resolución Absoluta (reconstrucción)",
    descripcion=(
        "Reconstrucción, con fuentes abiertas, del ataque de EE. UU. de la madrugada del 3 de enero de 2026 sobre "
        "Caracas, Miranda y La Guaira. Rojo = EE. UU., con los tipos de aeronave que se informaron: F-22A (Langley), "
        "F-35A (Guardia Nacional de Vermont) y F-35B de la Infantería de Marina desde Roosevelt Roads, el ala aérea del "
        "USS Gerald R. Ford (F/A-18E/F, EA-18G, E-2D), bombarderos B-1B, E-3G, RC-135V/W, EC-130H, P-8A, aviones "
        "cisterna, RQ-170, MQ-9, drones de ataque de un solo uso y los helicópteros del 160.º SOAR (MH-47G, MH-60M, "
        "MH-60 DAP, AH-6M y MH-6M) que operan desde el USS Iwo Jima. Azul = Venezuela: La Carlota y Charallave, los "
        "Buk-M2E de La Carlota e Higuerote, Fuerte Tiuna con sus Igla-S, El Volcán, La Guaira y los Su-30MK2 en tierra "
        "en El Libertador. Comienza a la 01:00; los ataques se informaron hacia las 02:00. Representa 73 "
        "aeronaves de las más de 150 que se informaron; las posiciones de los buques, de los radares y de los grupos "
        "aéreos son aproximadas, y las cifras de los modelos son didácticas. El desenlace político (la captura del "
        "jefe de Estado) queda fuera del alcance de este ejercicio táctico."
    ),
    clima="despejado", hora_inicio_min=60, nacion_azul="venezuela", nacion_rojo="estados_unidos", dia_noche=True,
    unidades=(
        # ---- Venezuela (azul) ----
        UnidadPlantilla("Base Aérea Generalísimo Francisco de Miranda (La Carlota)", "azul", "base_aerea", 10.4850, -66.8436),
        UnidadPlantilla("Buk-M2E La Carlota", "azul", "antiaerea", 10.4812, -66.8540),
        UnidadPlantilla("Aeropuerto de Charallave (Óscar Machado Zuloaga)", "azul", "base_aerea", 10.2869, -66.8158),
        UnidadPlantilla("Buk-M2E Higuerote", "azul", "antiaerea", 10.4625, -66.0928),
        UnidadPlantilla("Radar JY-27A (Barlovento, ubicación aproximada)", "azul", "radar", 10.3500, -66.2500),
        UnidadPlantilla("Radar JYL-1 (Paraguaná, ubicación aproximada)", "azul", "radar", 11.8200, -69.9500),
        UnidadPlantilla("Cerro El Volcán (antenas y enlaces de mando)", "azul", "radar", 10.4050, -66.8350),
        UnidadPlantilla("Fuerte Tiuna (comandancia y guarnición)", "azul", "infanteria", 10.4408, -66.9091, "brigada"),
        UnidadPlantilla("Igla-S Grupos 397/398 (Fuerte Tiuna)", "azul", "antiaerea_portatil", 10.4455, -66.8990),
        UnidadPlantilla("Igla-S Batallón Ayala (Fuerte Tiuna)", "azul", "antiaerea_portatil", 10.4370, -66.9180),
        UnidadPlantilla("Comando de la Milicia Bolivariana (ant. Observatorio Cagigal)", "azul", "infanteria",
                        10.5047, -66.9290, "batallon"),
        UnidadPlantilla("Puerto de La Guaira", "azul", "puerto", 10.6025, -66.9330),
        UnidadPlantilla("Patrullero (Base Naval de Catia La Mar)", "azul", "patrullero", 10.6150, -67.0250),
        UnidadPlantilla("Base Aérea El Libertador", "azul", "base_aerea", 10.18056, -67.56111),
        UnidadPlantilla("Su-30MK2 (El Libertador)", "azul", "caza", 10.18056, -67.56111, modelo="su30", aeronaves=4,
                        en_tierra=True, base="Base Aérea El Libertador"),
        # ---- Estados Unidos (rojo): bases y buques ----
        UnidadPlantilla("Base Naval Roosevelt Roads (Puerto Rico)", "rojo", "base_aerea", 18.2473, -65.6398),
        UnidadPlantilla("Aeropuerto Rafael Hernández, Aguadilla (Puerto Rico)", "rojo", "base_aerea", 18.4949, -67.1294),
        UnidadPlantilla("Base Aérea Dyess (Texas)", "rojo", "base_aerea", 32.4208, -99.8546),
        UnidadPlantilla("USS Gerald R. Ford (CVN-78)", "rojo", "portaaviones", 12.80, -67.20),
        UnidadPlantilla("Destructor de escolta CSG-12 (1)", "rojo", "destructor", 12.70, -67.00),
        UnidadPlantilla("Destructor de escolta CSG-12 (2)", "rojo", "destructor", 12.95, -67.45),
        UnidadPlantilla("USS Iwo Jima (LHD-7), 22.ª MEU", "rojo", "portaaviones", 11.45, -66.55),
        UnidadPlantilla("USS San Antonio (LPD-17)", "rojo", "buque_desembarco", 11.40, -66.38),
        # ---- aeronaves: paquetes de ataque y escolta (desde Puerto Rico y el Ford) ----
        _av("F-22A Raptor (escolta) 1", "f22", 4, 11.68, -67.05, "alto"),
        _av("F-22A Raptor (escolta) 2", "f22", 4, 11.68, -66.40, "alto"),
        _av("F-22A Raptor (patrulla aérea) 3", "f22", 4, 12.00, -67.45, "alto"),
        _av("F-35A Lightning II (SEAD, Vermont ANG) 1", "f35a", 4, 11.52, -67.25),
        _av("F-35A Lightning II (SEAD, Vermont ANG) 2", "f35a", 4, 11.52, -66.10),
        _av("F-35B Lightning II (VMFA-225)", "f35b", 4, 11.52, -66.42),
        _av("F/A-18E/F Super Hornet (CVW-8) 1", "fa18ef", 4, 11.75, -67.35),
        _av("F/A-18E/F Super Hornet (CVW-8) 2", "fa18ef", 4, 11.92, -66.95),
        _av("F/A-18E/F Super Hornet (CVW-8) 3", "fa18ef", 4, 12.20, -67.60),
        _av("EA-18G Growler 1", "ea18g", 3, 11.52, -66.95),
        _av("EA-18G Growler 2", "ea18g", 3, 11.72, -66.10),
        _av("B-1B Lancer", "b1b", 4, 14.20, -66.60),
        _av("Dron de ataque de un solo uso (tipo LUCAS)", "lucas", 4, 11.25, -66.30, "rasante"),
        # ---- vigilancia, mando y control, guerra electrónica y reabastecimiento ----
        _av("E-2D Advanced Hawkeye 1", "e2d", 1, 12.40, -67.00),
        _av("E-2D Advanced Hawkeye 2", "e2d", 1, 12.80, -67.20, base="USS Gerald R. Ford (CVN-78)"),
        _av("E-3G Sentry (AWACS)", "e3g", 1, 13.30, -66.50),
        _av("RC-135V/W Rivet Joint", "rc135", 1, 12.60, -68.20, "alto"),
        _av("EC-130H Compass Call", "ec130h", 1, 12.20, -66.30),
        _av("P-8A Poseidon", "p8a", 1, 12.30, -65.80),
        _av("KC-135R Stratotanker 1", "kc135", 2, 13.00, -66.80),
        _av("KC-135R Stratotanker 2", "kc135", 2, 13.20, -67.80),
        _av("RQ-170 Sentinel", "rq170", 1, 10.80, -66.70, "alto"),
        _av("MQ-9A Reaper", "mq9", 2, 12.00, -66.00),
        # ---- 160.º SOAR: fuerza de asalto desde el USS Iwo Jima (vuelo rasante sobre el mar) ----
        _av("MH-47G Chinook (fuerza de asalto)", "mh47g", 3, 11.32, -66.85, "rasante"),
        _av("MH-60M Black Hawk (fuerza de asalto)", "mh60m", 2, 11.32, -66.66, "rasante"),
        _av("MH-60M DAP (escolta armada)", "mh60dap", 2, 11.42, -67.02, "rasante"),
        _av("AH-6M Little Bird (apoyo de fuego)", "ah6m", 2, 11.18, -66.76, "rasante"),
        _av("MH-6M Little Bird (inserción)", "mh6m", 1, 11.18, -66.95, "rasante"),
    ),
    objetivos=(
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar el Buk-M2E de La Carlota", 20, unidad="Buk-M2E La Carlota"),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar el Buk-M2E de Higuerote", 20, unidad="Buk-M2E Higuerote"),
        ObjetivoPlantilla("rojo", "destruir", "Cortar los enlaces de El Volcán", 15,
                          unidad="Cerro El Volcán (antenas y enlaces de mando)"),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar la defensa antiaérea de Fuerte Tiuna", 15,
                          unidad="Igla-S Grupos 397/398 (Fuerte Tiuna)"),
        ObjetivoPlantilla("rojo", "proteger", "Preservar la fuerza de asalto", 30,
                          unidad="MH-47G Chinook (fuerza de asalto)", hasta_turno=4),
        ObjetivoPlantilla("azul", "proteger", "Mantener el Buk-M2E de La Carlota", 20, unidad="Buk-M2E La Carlota", hasta_turno=4),
        ObjetivoPlantilla("azul", "proteger", "Mantener el Buk-M2E de Higuerote", 20, unidad="Buk-M2E Higuerote", hasta_turno=4),
        ObjetivoPlantilla("azul", "proteger", "Mantener los enlaces de El Volcán", 15,
                          unidad="Cerro El Volcán (antenas y enlaces de mando)", hasta_turno=4),
        ObjetivoPlantilla("azul", "proteger", "Defender Fuerte Tiuna", 25, unidad="Fuerte Tiuna (comandancia y guarnición)",
                          hasta_turno=4),
        ObjetivoPlantilla("azul", "destruir", "Derribar la fuerza de asalto", 30, unidad="MH-47G Chinook (fuerza de asalto)"),
    ),
)

def _grupo(nombre, bando, modelo, n, lat, lon, base=None, perfil=None):
    return UnidadPlantilla(nombre, bando, catalogo.MODELOS[modelo].clase, lat, lon, modelo=modelo, aeronaves=n,
                           en_tierra=base is not None, base=base, perfil_vuelo=perfil)


# ---- biblioteca de escenarios para un solo bando de alumnos (el rojo lo conduce el adversario automatico) ----
_DEFENSA_CENTRAL = Plantilla(
    id="defensa_aerea_central", nombre="Defensa aérea de la región central (contra la IA)",
    descripcion=(
        "El bando azul defiende la Base Aérea El Libertador y la región Maracay-Valencia de un ataque aeronaval que "
        "llega desde el Caribe: un portaaviones con su escolta, cazas embarcados, guerra electrónica y drones armados. "
        "Ejercita la alerta temprana con el radar de montaña, el empleo de los Su-30 y F-16, la defensa antiaérea por "
        "capas y la protección de la base y de la infraestructura de la región: si el enemigo daña Planta Centro, los "
        "radares fijos pierden alcance; si daña la refinería El Palito, los depósitos reponen menos combustible. El "
        "bando rojo lo conduce el adversario automático (puede apagarse en Consola → Dirección del ejercicio). Fuerzas "
        "genéricas, sin pretensión de representar a un país real."
    ),
    clima="despejado", hora_inicio_min=300, nacion_azul="venezuela", nacion_rojo="", ia_rojo=True, dia_noche=True,
    unidades=(
        UnidadPlantilla("Base Aérea El Libertador", "azul", "base_aerea", 10.18056, -67.56111),
        _grupo("Su-30MK2 (alerta)", "azul", "su30", 4, 10.18056, -67.56111, base="Base Aérea El Libertador"),
        _grupo("F-16 (alerta)", "azul", "f16", 2, 10.18056, -67.56111, base="Base Aérea El Libertador"),
        UnidadPlantilla("Radar de montaña (Cordillera de la Costa)", "azul", "radar", 10.33, -67.45),
        UnidadPlantilla("Defensa antiaérea de la base", "azul", "antiaerea", 10.20, -67.53),
        UnidadPlantilla("Igla-S Maracay", "azul", "antiaerea_portatil", 10.17, -67.58),
        UnidadPlantilla("Guerra electrónica central", "azul", "guerra_electronica", 10.22, -67.48),
        UnidadPlantilla("Puerto Cabello", "azul", "puerto", 10.48, -68.01),
        UnidadPlantilla("Patrullero (Puerto Cabello)", "azul", "patrullero", 10.62, -68.05),
        # infraestructura real de la region (OpenStreetMap; ver engine/infraestructura.py)
        UnidadPlantilla("Planta Centro (Morón)", "azul", "termoelectrica", 10.49125, -68.15567),
        UnidadPlantilla("Refinería El Palito", "azul", "refineria", 10.48087, -68.12201),
        UnidadPlantilla("Depósito logístico central", "azul", "deposito", 10.25, -67.60),
        UnidadPlantilla("Portaaviones rojo", "rojo", "portaaviones", 11.80, -67.90),
        UnidadPlantilla("Destructor de escolta rojo", "rojo", "destructor", 11.50, -68.30),
        _grupo("Cazas embarcados 1", "rojo", "caza_embarcado", 4, 11.20, -67.60),
        _grupo("Cazas embarcados 2", "rojo", "caza_embarcado", 4, 11.80, -67.90, base="Portaaviones rojo"),
        _grupo("Avión de guerra electrónica rojo", "rojo", "ge_aereo", 1, 11.60, -67.40),
        _grupo("Drones armados rojos", "rojo", "uav_armado", 2, 11.10, -67.90),
    ),
    objetivos=(
        ObjetivoPlantilla("azul", "proteger", "Mantener operativa El Libertador", 40, unidad="Base Aérea El Libertador", hasta_turno=8),
        ObjetivoPlantilla("azul", "proteger", "Mantener el radar de montaña", 20,
                          unidad="Radar de montaña (Cordillera de la Costa)", hasta_turno=8),
        ObjetivoPlantilla("azul", "destruir", "Hundir el portaaviones", 40, unidad="Portaaviones rojo"),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar El Libertador", 40, unidad="Base Aérea El Libertador"),
        ObjetivoPlantilla("rojo", "destruir", "Dejar sin energía la región: Planta Centro", 25, unidad="Planta Centro (Morón)"),
        ObjetivoPlantilla("rojo", "destruir", "Cortar el combustible: refinería El Palito", 20, unidad="Refinería El Palito"),
        ObjetivoPlantilla("azul", "proteger", "Mantener Planta Centro", 20, unidad="Planta Centro (Morón)", hasta_turno=8),
        ObjetivoPlantilla("rojo", "destruir", "Cegar el radar de montaña", 20, unidad="Radar de montaña (Cordillera de la Costa)"),
    ),
)

_INTERDICCION_LLANOS = Plantilla(
    id="interdiccion_llanos", nombre="Interdicción en los llanos (contra la IA)",
    descripcion=(
        "Una columna mecanizada roja con sus convoyes avanza desde Guasdualito hacia Barinas. El bando azul debe "
        "detenerla antes de que ocupe la ciudad: aviones de ataque K-8W y helicópteros Mi-35 desde el aeropuerto de "
        "Barinas, drones armados de reconocimiento y ataque, y una defensa terrestre escalonada. Ejercita la "
        "interdicción de la logística (los convoyes son vulnerables), el apoyo aéreo cercano y la coordinación entre "
        "los puestos. El bando rojo lo conduce el adversario automático. Fuerzas genéricas, sin pretensión de "
        "representar a un país real."
    ),
    clima="despejado", hora_inicio_min=360, nacion_azul="venezuela", nacion_rojo="", ia_rojo=True, dia_noche=True,
    unidades=(
        UnidadPlantilla("Aeropuerto de Barinas", "azul", "base_aerea", 8.62, -70.21),
        _grupo("K-8W (ataque)", "azul", "ataque_ligero", 4, 8.62, -70.21, base="Aeropuerto de Barinas"),
        _grupo("Mi-35M (ataque)", "azul", "helo_ataque", 2, 8.62, -70.21, base="Aeropuerto de Barinas"),
        _grupo("Drones armados azules", "azul", "uav_armado", 2, 8.62, -70.21, base="Aeropuerto de Barinas"),
        UnidadPlantilla("Brigada de Infantería Barinas", "azul", "infanteria", 8.63, -70.24, "brigada"),
        UnidadPlantilla("Grupo de Caballería Blindada", "azul", "blindado", 8.23, -70.82, "batallon"),
        UnidadPlantilla("Artillería de campaña", "azul", "artilleria", 8.45, -70.40, "batallon"),
        UnidadPlantilla("Depósito Barinas", "azul", "deposito", 8.60, -70.26),
        UnidadPlantilla("Columna blindada roja", "rojo", "blindado", 7.70, -70.55, "batallon"),
        UnidadPlantilla("Infantería mecanizada roja", "rojo", "infanteria", 7.55, -70.65, "batallon"),
        UnidadPlantilla("Antiaérea portátil roja", "rojo", "antiaerea_portatil", 7.60, -70.60),
        UnidadPlantilla("Convoy rojo 1", "rojo", "transporte", 7.40, -70.75),
        UnidadPlantilla("Convoy rojo 2", "rojo", "transporte", 7.30, -70.80),
        UnidadPlantilla("Depósito rojo (Guasdualito)", "rojo", "deposito", 7.24, -70.73),
    ),
    objetivos=(
        ObjetivoPlantilla("rojo", "ocupar", "Ocupar Barinas", 50, lat=8.63, lon=-70.24, radio_km=8, turnos_requeridos=2),
        ObjetivoPlantilla("azul", "proteger", "Mantener Barinas", 40, unidad="Brigada de Infantería Barinas", hasta_turno=10),
        ObjetivoPlantilla("azul", "destruir", "Cortar el convoy rojo 1", 20, unidad="Convoy rojo 1"),
        ObjetivoPlantilla("azul", "destruir", "Cortar el convoy rojo 2", 20, unidad="Convoy rojo 2"),
        ObjetivoPlantilla("azul", "destruir", "Detener la columna blindada", 30, unidad="Columna blindada roja"),
    ),
)

_COSTA_ORIENTAL = Plantilla(
    id="defensa_costa_oriental", nombre="Defensa de la costa oriental (contra la IA)",
    descripcion=(
        "Una fuerza anfibia roja (dos buques de desembarco con fragatas de escolta y helicópteros) se aproxima a "
        "Barcelona y Puerto La Cruz. El bando azul defiende la costa con misiles costeros, patrulleros, infantería "
        "de marina, un radar y aviación desde Barcelona. Ejercita la defensa de costa, el ataque a la fuerza naval "
        "antes del desembarco y la defensa de la playa y de la refinería de Puerto La Cruz, cuyo daño deja a los "
        "depósitos con menos combustible. El bando rojo lo conduce el adversario automático. Fuerzas genéricas, sin "
        "pretensión de representar a un país real."
    ),
    clima="despejado", hora_inicio_min=240, nacion_azul="venezuela", nacion_rojo="", ia_rojo=True, dia_noche=True,
    unidades=(
        UnidadPlantilla("Aeropuerto de Barcelona", "azul", "base_aerea", 10.107, -64.689),
        _grupo("F-16 (Barcelona)", "azul", "f16", 2, 10.107, -64.689, base="Aeropuerto de Barcelona"),
        _grupo("Mi-35M (Barcelona)", "azul", "helo_ataque", 2, 10.107, -64.689, base="Aeropuerto de Barcelona"),
        UnidadPlantilla("Batería de misiles costeros", "azul", "lanzador_misiles", 10.12, -64.72),
        UnidadPlantilla("Radar costero", "azul", "radar", 10.05, -64.45),
        UnidadPlantilla("Infantería de Marina (Barcelona)", "azul", "infanteria", 10.11, -64.66, "batallon"),
        UnidadPlantilla("Antiaérea costera", "azul", "antiaerea", 10.08, -64.70),
        UnidadPlantilla("Puerto de Puerto La Cruz", "azul", "puerto", 10.21, -64.63),
        UnidadPlantilla("Patrullero oriental", "azul", "patrullero", 10.35, -64.50),
        UnidadPlantilla("Refinería de Puerto La Cruz", "azul", "refineria", 10.22075, -64.62064),
        UnidadPlantilla("Depósito logístico oriental", "azul", "deposito", 10.10, -64.60),
        UnidadPlantilla("Buque de desembarco rojo 1", "rojo", "buque_desembarco", 10.45, -64.55),
        UnidadPlantilla("Buque de desembarco rojo 2", "rojo", "buque_desembarco", 10.55, -64.30),
        UnidadPlantilla("Fragata de escolta roja 1", "rojo", "fragata", 10.70, -64.70),
        UnidadPlantilla("Fragata de escolta roja 2", "rojo", "fragata", 10.55, -64.80),
        _grupo("Helicópteros de ataque rojos", "rojo", "helo_ataque", 2, 10.60, -64.55),
    ),
    objetivos=(
        ObjetivoPlantilla("rojo", "destruir", "Abrir la playa: batir a la Infantería de Marina", 40,
                          unidad="Infantería de Marina (Barcelona)"),
        ObjetivoPlantilla("rojo", "destruir", "Neutralizar la batería costera", 25, unidad="Batería de misiles costeros"),
        ObjetivoPlantilla("azul", "destruir", "Hundir el buque de desembarco 1", 30, unidad="Buque de desembarco rojo 1"),
        ObjetivoPlantilla("azul", "destruir", "Hundir el buque de desembarco 2", 30, unidad="Buque de desembarco rojo 2"),
        ObjetivoPlantilla("azul", "proteger", "Mantener la batería costera", 20, unidad="Batería de misiles costeros", hasta_turno=8),
        ObjetivoPlantilla("rojo", "destruir", "Cortar el combustible: refinería de Puerto La Cruz", 20,
                          unidad="Refinería de Puerto La Cruz"),
        ObjetivoPlantilla("azul", "proteger", "Mantener la refinería de Puerto La Cruz", 15,
                          unidad="Refinería de Puerto La Cruz", hasta_turno=8),
    ),
)

PLANTILLAS: dict[str, Plantilla] = {p.id: p for p in [
    _DEMO_LLANOS, _DEFENSA_3_ENERO, _ATAQUE_3_ENERO, _DEFENSA_CENTRAL, _INTERDICCION_LLANOS, _COSTA_ORIENTAL]}


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
                    nacion_azul=p.nacion_azul, nacion_rojo=p.nacion_rojo, ia_azul=p.ia_azul, ia_rojo=p.ia_rojo,
                    dia_noche=p.dia_noche, conduce_azul=p.conduce_azul, conduce_rojo=p.conduce_rojo,
                    fecha_inicio=p.fecha_inicio, turno_h=p.turno_h, turno_final=p.turno_final,
                    fases_json=json.dumps(list(p.fases), ensure_ascii=False) if p.fases else None)
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
        if u.perfil_vuelo and u.perfil_vuelo in relieve.perfiles_permitidos(unidad):
            unidad.perfil_vuelo = u.perfil_vuelo
        unidad.personal, unidad.radio_km = u.personal, u.radio_km
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

    creados: list[tuple[ObjetivoPlantilla, Objetivo]] = []
    for o in p.objetivos:
        obj = Objetivo(
            escenario_id=esc.id, bando=o.bando, tipo=o.tipo, nombre=o.nombre, puntos=o.puntos,
            lat=o.lat, lon=o.lon, radio_km=o.radio_km, turnos_requeridos=o.turnos_requeridos,
            unidad_id=unidades[o.unidad].id if o.unidad else None, hasta_turno=o.hasta_turno,
            nivel=o.nivel, efecto=o.efecto, indicador=o.indicador, umbral=o.umbral,
        )
        db.add(obj)
        creados.append((o, obj))
    db.flush()
    for o, obj in creados:  # la cadena de objetivos se arma por nombre dentro de cada bando
        if o.padre:
            padre = next((x for po, x in creados if po.bando == o.bando and po.nombre == o.padre and x is not obj), None)
            obj.padre_id = padre.id if padre else None
    if p.pmo:
        from app.engine import pmo  # importacion tardia: pmo importa este modulo indirectamente

        for bando, contenido in p.pmo.items():
            pmo.guardar(db, esc, bando, contenido, "instructor")

    db.commit()
    db.refresh(esc)
    if esc.ia_azul or esc.ia_rojo:
        from app import adversario  # importacion tardia: el adversario usa la validacion de las ordenes (routers)
        adversario.jugar_turno(db, esc)  # el bando del simulador ya da las ordenes del primer turno
        db.commit()
    return esc


def plantilla_dict(p: Plantilla) -> dict:
    return {
        "id": p.id, "nombre": p.nombre, "descripcion": p.descripcion, "nacion_azul": p.nacion_azul,
        "nacion_rojo": p.nacion_rojo, "unidades": len(p.unidades), "objetivos": len(p.objetivos),
        "origen": p.origen, "con_estado": p.con_estado, "guardada_en": p.guardada_en,
        "ia_azul": p.ia_azul, "ia_rojo": p.ia_rojo, "dia_noche": p.dia_noche,
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
        if u.tipo == "aerea" and u.perfil_vuelo:
            d["perfil_vuelo"] = u.perfil_vuelo
        if u.personal is not None:
            d["personal"] = int(u.personal)
        if u.radio_km is not None:
            d["radio_km"] = round(float(u.radio_km), 3)
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
    todos = db.query(Objetivo).filter(Objetivo.escenario_id == esc.id).order_by(Objetivo.id).all()
    nombre_obj = {o.id: o.nombre for o in todos}
    for o in todos:
        if o.tipo in ("destruir", "neutralizar", "proteger") and o.unidad_id not in nombres:
            continue  # la unidad ya no existe: el objetivo no tiene sentido en la plantilla
        objetivos.append({
            "bando": o.bando, "tipo": o.tipo, "nombre": o.nombre, "puntos": o.puntos, "lat": o.lat, "lon": o.lon,
            "radio_km": o.radio_km, "turnos_requeridos": o.turnos_requeridos,
            "unidad": nombres.get(o.unidad_id) if o.unidad_id is not None else None, "hasta_turno": o.hasta_turno,
            "nivel": o.nivel or "material", "padre": nombre_obj.get(o.padre_id), "efecto": o.efecto or "",
            "indicador": o.indicador or "", "umbral": o.umbral,
        })
    from app.models.problema_militar import ProblemaMilitar  # importacion tardia: solo al guardar

    problemas = {pm.bando: json.loads(pm.contenido_json)
                 for pm in db.query(ProblemaMilitar).filter(ProblemaMilitar.escenario_id == esc.id)}
    return {
        "id": plantilla_id, "nombre": nombre, "descripcion": descripcion, "origen": "usuario",
        "guardada_en": datetime.now(timezone.utc).isoformat(timespec="seconds"), "escenario_origen": esc.id,
        "con_estado": bool(con_estado), "clima": esc.clima, "hora_inicio_min": esc.hora_inicio_min,
        "nacion_azul": esc.nacion_azul or "", "nacion_rojo": esc.nacion_rojo or "",
        "ia_azul": bool(esc.ia_azul), "ia_rojo": bool(esc.ia_rojo), "dia_noche": bool(esc.dia_noche),
        "conduce_azul": esc.conduce_azul or "alumnos", "conduce_rojo": esc.conduce_rojo or "alumnos",
        "fecha_inicio": esc.fecha_inicio, "turno_h": esc.turno_h, "turno_final": esc.turno_final,
        "fases": json.loads(esc.fases_json) if esc.fases_json else [], "pmo": problemas,
        "unidades": unidades, "objetivos": objetivos,
    }


def _entero_opcional(v) -> int | None:
    try:
        return None if v is None else max(0, min(200000, int(v)))
    except (TypeError, ValueError):
        raise PlantillaInvalida("personal: indique un numero entero") from None


def _radio_opcional(v) -> float | None:
    try:
        return None if v is None else max(0.05, min(20.0, float(v)))
    except (TypeError, ValueError):
        raise PlantillaInvalida("radio_km: indique un numero") from None


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
            perfil_vuelo=d.get("perfil_vuelo") if d.get("perfil_vuelo") in relieve.PERFILES else None,
            personal=_entero_opcional(d.get("personal")), radio_km=_radio_opcional(d.get("radio_km")),
        ))
    objetivos: list[ObjetivoPlantilla] = []
    for d in datos.get("objetivos") or []:
        if (d.get("tipo") not in ("ocupar", "destruir", "neutralizar", "proteger", "efecto")
                or d.get("bando") not in ("azul", "rojo")):
            raise PlantillaInvalida("Objetivo con tipo o bando invalido")
        unidad = d.get("unidad")
        if d["tipo"] not in ("ocupar", "efecto") and unidad not in vistos:
            raise PlantillaInvalida(f"El objetivo {d.get('nombre')!r} referencia una unidad que no esta en la plantilla")
        nivel = d.get("nivel") if d.get("nivel") in ("ulterior", "asignado", "material") else "material"
        if d["tipo"] == "efecto" and nivel == "material":
            nivel = "asignado"
        umbral = d.get("umbral")
        objetivos.append(ObjetivoPlantilla(
            d["bando"], d["tipo"], str(d.get("nombre") or "Objetivo"), int(d.get("puntos") or 0),
            lat=d.get("lat"), lon=d.get("lon"), radio_km=float(d.get("radio_km") or 5.0),
            turnos_requeridos=int(d.get("turnos_requeridos") or 1),
            unidad=unidad if d["tipo"] not in ("ocupar", "efecto") else None, hasta_turno=d.get("hasta_turno"),
            nivel=nivel, padre=d.get("padre") or None, efecto=str(d.get("efecto") or "")[:300],
            indicador=str(d.get("indicador") or "")[:300],
            umbral=None if umbral is None else max(0.0, min(100.0, float(umbral))),
        ))
    from app.engine import calendario  # importacion tardia: evita el ciclo con los modelos

    try:
        fases = tuple(calendario.validar_fases(datos.get("fases") or []))
    except ValueError as exc:
        raise PlantillaInvalida(f"Fases de la operacion: {exc}") from None

    def turno_opcional(campo):
        v = datos.get(campo)
        return None if v in (None, "", 0) else max(1, int(v))
    return Plantilla(
        id=plantilla_id, nombre=nombre, descripcion=str(datos.get("descripcion") or ""),
        clima=str(datos.get("clima") or "despejado"), hora_inicio_min=int(datos.get("hora_inicio_min") or 360),
        nacion_azul=str(datos.get("nacion_azul") or ""), nacion_rojo=str(datos.get("nacion_rojo") or ""),
        unidades=tuple(unidades), objetivos=tuple(objetivos), origen="usuario",
        con_estado=bool(datos.get("con_estado")), guardada_en=str(datos.get("guardada_en") or ""),
        escenario_origen=datos.get("escenario_origen"),
        ia_azul=bool(datos.get("ia_azul")), ia_rojo=bool(datos.get("ia_rojo")), dia_noche=bool(datos.get("dia_noche")),
        conduce_azul="instructor" if datos.get("conduce_azul") == "instructor" else "alumnos",
        conduce_rojo="instructor" if datos.get("conduce_rojo") == "instructor" else "alumnos",
        fecha_inicio=str(datos["fecha_inicio"])[:10] if datos.get("fecha_inicio") else None,
        turno_h=turno_opcional("turno_h"), turno_final=turno_opcional("turno_final"), fases=fases,
        pmo={b: c for b, c in (datos.get("pmo") or {}).items() if b in ("azul", "rojo") and isinstance(c, dict)},
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


# ---------------------------------------------------------------------------------------------------------
# Plantillas del sistema generadas por herramientas (JSON en backend/data/plantillas_sistema), p. ej. la del mapa
# ficticio (tools/generar_mapa_ficticio.py), cuyas posiciones dependen del terreno generado. Son del sistema
# ("codigo"): no se pueden eliminar desde la interfaz.
RUTA_PLANTILLAS_SISTEMA = Path(__file__).resolve().parents[2] / "data" / "plantillas_sistema"


def _cargar_sistema() -> None:
    from dataclasses import replace

    if not RUTA_PLANTILLAS_SISTEMA.is_dir():
        return
    for archivo in sorted(RUTA_PLANTILLAS_SISTEMA.glob("*.json")):
        try:
            p = desde_dict(json.loads(archivo.read_text(encoding="utf-8")))
        except (PlantillaInvalida, ValueError, TypeError, KeyError, OSError) as exc:
            log.warning("Plantilla del sistema ignorada (%s): %s", archivo.name, exc)
            continue
        if p.id not in PLANTILLAS:
            PLANTILLAS[p.id] = replace(p, origen="codigo", guardada_en="", escenario_origen=None)


_cargar_sistema()
