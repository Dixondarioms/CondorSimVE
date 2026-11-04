"""Cóndor (el SIETE en tiempo real): el ejercicio avanza segundo a segundo en lugar de por turnos.

El reloj del escenario (`sim_segundos`) corre a la velocidad que fija el director (1x, 10x o 60x: segundos simulados
por cada segundo real) y se detiene con la pausa. Cada segundo real el servidor llama a `paso`, que divide el tiempo
transcurrido en pasos cortos (a lo sumo PASO_MAX_S simulados) y en cada uno:

1. Mueve las unidades por la ruta que les falta (`ruta_json`), con el mismo terreno, carreteras, rios, clima y
   combustible que el SIETE por turnos (engine/movimiento.py con la duracion del paso). Las aeronaves sin ruta orbitan
   sobre su punto (patrulla o espera) gastando combustible; los misiles persiguen a su blanco.
2. Detecta: cada bando ve lo que sus sensores detectan ahora (engine/vision.py), con niebla de guerra.
3. Combate: las ordenes de ataque se cumplen en vivo. En tierra y en el mar el fuego es continuo mientras el blanco
   este a la vista y al alcance (las perdidas de la tabla de combate son por hora de combate y se aplican segun el
   tiempo transcurrido). Las aeronaves y los misiles atacan por pasadas (un ataque completo cada vez). Las patrullas
   interceptan solas; la defensa aerea reacciona, lanza, espera el vuelo del misil y evalua (engine/defensa_aerea.py).
4. Logistica: combustible por kilometro y en orbita, regreso automatico con combustible critico, aterrizaje de
   emergencia o perdida sin combustible, y espera en tierra para reabastecer y rearmar.

Al cumplirse cada hora simulada (el "turno" sigue siendo la hora en curso) se ejecutan los procesos horarios del
SIETE: reabastecimiento desde las bases y convoyes, reparaciones, clima, objetivos, inteligencia e instantanea del
informe posterior.

Las ordenes se aplican al emitirse (`aplicar_orden`): la unidad empieza a cumplirla en el paso siguiente.
"""

import hashlib
import json
import logging
import math
import random
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.engine import armas as armas_mod
from app.engine import aar, bases as bases_mod, catalogo, combat, geo, logistica, movimiento, relieve, vision
from app.engine import aeronaves as aeronaves_mod
from app.engine import apoyo_aereo as apoyo_mod
from app.engine import apresto as apresto_mod
from app.engine import azar as azar_mod
from app.engine import clima as clima_mod
from app.engine import contramedidas as contra_mod
from app.engine import enlace as enlace_mod
from app.engine import gastos as gastos_mod
from app.engine import iff as iff_mod
from app.engine import mar as mar_mod
from app.engine import contactos_vivo
from app.engine import doctrina as doctrina_mod
from app.engine import defensa_aerea as da_mod
from app.engine import guerra_electronica as ge_mod
from app.engine import infraestructura as infra_mod
from app.engine import interceptacion as intercep_mod
from app.engine import inteligencia as intel_mod
from app.engine import misiles as misiles_mod
from app.engine import objetivos as objetivos_mod
from app.engine import pmi as pmi_mod
from app.engine import orders
from app.engine import ota as ota_mod
from app.engine import rescate as rescate_mod
from app.engine import rutas as rutas_mod
from app.engine import transporte as transporte_mod
from app.engine import asw as asw_mod
from app.engine import balisticos as balisticos_mod
from app.engine import minas as minas_mod
from app.engine import eventos_auto
from app.engine import sistemas as sistemas_mod
from app.engine import trafico as trafico_mod
from app.engine import zonas as zonas_mod
from app.models.aar import Combate, Fotograma, RegistroLogistico
from app.models.contacto import Contacto
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.interferencia import Interferencia
from app.models.obra import Obra
from app.models.orden import Orden
from app.models.unidad import Unidad
from app.terreno import Terreno, get_terreno

log = logging.getLogger("uvicorn.error")

VELOCIDADES = (1, 10, 60)  # segundos simulados por segundo real que puede elegir el director
PASO_MAX_S = 15.0  # el tiempo de cada llamada se divide en pasos de a lo sumo esto (simulado)
DETECCION_CADA_S = 60.0  # en un avance largo (adelantar el reloj) la deteccion se rehace cada este tiempo simulado
MAX_ADELANTO_H = 24
LOGISTICA_CADA_S = 60.0  # el reabastecimiento (por hora en las tablas) se aplica de a un minuto simulado
CISTERNA_CADA_S = 900.0  # un avion cisterna atiende a sus receptores en tandas de 15 minutos
FOTOGRAMA_CADA_S = 300.0  # la repeticion guarda donde esta cada unidad cada 5 minutos simulados
IA_CADA_S = 300.0  # igual que adversario.IA_CADA_S (aqui para no importar el adversario al cargar el motor)
RECARGA_LANZADOR_S = 1800.0  # un lanzador de misiles de crucero recarga media hora despues de cada salva
REINTENTOS_RUTA = 2  # veces que una unidad varada busca otro camino antes de detenerse
RADIO_ORBITA_KM = 12.0  # las aeronaves sin ruta orbitan en un circulo de este radio sobre su punto
LLEGADA_ORBITA_KM = RADIO_ORBITA_KM + 2.0
RECARGA_PASADA_S = 300.0  # entre dos pasadas de ataque de una aeronave
RECARGA_AIRE_AIRE_S = 180.0  # entre dos enfrentamientos aire-aire de una patrulla
CONTACTO_PERDIDO_S = 600.0  # sin ver el blanco este tiempo, el ataque se da por terminado
AVISO_CONTACTO_S = 900.0  # un enemigo que reaparece despues de esto se informa como contacto nuevo
DESPLIEGUE_POR_TURNO_S = 900.0  # tiempo quieta para disparar, por cada "turno de despliegue" del catalogo
MISIONES_CONTINUAS = frozenset({"patrulla", "espera"})
TIPOS_DE_ORDEN = ("mover", "atacar", "patrullar", "aterrizar", "despegar", "lanzar", "interferir", "construir",
                  "embarcar", "desembarcar", "apoyar", "rumbo", "interceptar", "torpedo", "sonoboyas", "sonar",
                  "minar", "barrer")
TASA_GIRO_GPS = 3.0  # grados por segundo al virar por una orden de rumbo (viraje estandar del transito aereo)
LEJOS_KM = 500.0  # punto de referencia por delante en el rumbo (la aeronave nunca llega: sigue el rumbo)
TIEMPO_OBRA_S = {"vado": 1800.0, "puente": 3600.0}  # trabajo de los ingenieros en el sitio hasta que la obra queda lista
EMBARQUE_S = 600.0  # lo que tarda una unidad en subir a su transporte
DEMORA_MIN_S, DEMORA_MAX_S = 900.0, 2700.0  # una orden que no llega a tiempo tarda entre 15 y 45 minutos
MOTIVO_ETAPA = "Ese tipo de orden no existe en el Cóndor."


def hora_del_dia(escenario: Escenario, sim_segundos: float | None = None) -> str:
    """Hora simulada HH:MM del escenario (ahora, o en `sim_segundos`)."""
    t = escenario.sim_segundos if sim_segundos is None else sim_segundos
    minutos = int((escenario.hora_inicio_min or 0) + (t or 0.0) // 60)
    return f"{minutos % 1440 // 60:02d}:{minutos % 60:02d}"


def turno_de(sim_segundos: float) -> int:
    return int((sim_segundos or 0.0) // 3600) + 1


def rumbo(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumbo verdadero en grados de (lat1, lon1) a (lat2, lon2)."""
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
         - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2 - lon1)))
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def rumbo_objetivo(actual: float, modo: str, grados: float, sentido: str) -> tuple[float, str]:
    """Rumbo final y lado del viraje de una orden de rumbo dada con la aeronave en el rumbo `actual`.

    "virar" N grados a la derecha o a la izquierda; "rumbo" N por el lado pedido o, con "corto", por el mas corto
    (a igual distancia, a la derecha)."""
    actual = (actual or 0.0) % 360.0
    if modo == "virar":
        return (actual + grados if sentido == "derecha" else actual - grados) % 360.0, sentido
    objetivo = grados % 360.0
    if sentido in ("derecha", "izquierda"):
        return objetivo, sentido
    return objetivo, "derecha" if (objetivo - actual) % 360.0 <= 180.0 else "izquierda"


def texto_rumbo(objetivo: float, sentido: str, actual: float | None) -> str:
    """«vira a la derecha 30° al rumbo 110°» (o «mantiene el rumbo 080°» si ya va en ese rumbo)."""
    actual = (actual or 0.0) % 360.0
    giro = (objetivo - actual) % 360.0 if sentido == "derecha" else (actual - objetivo) % 360.0
    if giro < 0.5:
        return f"mantiene el rumbo {objetivo:03.0f}°"
    return f"vira a la {sentido} {giro:.0f}° al rumbo {objetivo:03.0f}°"


# ------------------------------------------------------------------------------------------- estado en memoria
@dataclass
class Mundo:
    """Lo que el motor recuerda entre pasos y no hace falta guardar: si el servidor se reinicia, se rehace solo."""

    visibles: dict = field(default_factory=lambda: {"azul": set(), "rojo": set()})
    detectado: bool = False  # ya hubo una deteccion desde que arranco el servidor
    visto_en: dict = field(default_factory=dict)  # (bando, unidad_id) -> segundo simulado en que se la vio
    movio_en: dict = field(default_factory=dict)  # unidad_id -> ultimo segundo simulado en que se movio
    pos_previa: dict = field(default_factory=dict)  # unidad_id -> (lat, lon) del paso anterior
    da: dict = field(default_factory=dict)  # bateria_id -> enfrentamientos en curso
    combates: dict = field(default_factory=dict)  # (atacante_id, defensor_id) -> fuego continuo acumulado
    bajo_fuego: dict = field(default_factory=dict)  # (atacante_id, defensor_id) -> ultimo aviso de fuego continuo
    ia_pensada: float = -1e9  # segundo simulado de la ultima decision del adversario automatico
    logistica_en: float | None = None  # ultimo reabastecimiento continuo (bases, convoyes, depositos)
    cisternas_en: float | None = None  # ultimo reabastecimiento en vuelo
    registro: dict = field(default_factory=dict)  # (unidad_id, variable, causa) -> cambio acumulado en la hora
    reintentos_ruta: dict = field(default_factory=dict)  # (unidad_id, orden_id) -> veces que busco otro camino
    ultimo_contacto_guardado: float = -1e9
    # seguimiento de contactos (engine/contactos_vivo.py): (bando, unidad_id) -> etapa, puntos, incertidumbre
    pistas: dict = field(default_factory=dict)
    pistas_cargadas: bool = False
    pistas_en: dict = field(default_factory=dict)  # bando -> ultimo segundo simulado en que se sumaron puntos
    # interceptaciones en curso: orden_id -> ultima traza del blanco {lat, lon, t, ve, vn} (engine/interceptacion.py)
    intercepciones: dict = field(default_factory=dict)
    en_zona: set = field(default_factory=set)  # (zona_id, unidad_id) dentro de una zona de exclusion o de no vuelo
    patrulla_idx: dict = field(default_factory=dict)  # unidad_id -> proximo vertice de su area de patrulla
    trafico_en: float = -1e9  # ultimo segundo simulado en que se mantuvo el trafico civil (engine/trafico.py)
    colateral: dict = field(default_factory=dict)  # (atacante_id, neutral_id) -> ultimo aviso de daño colateral
    punto_disparos: dict = field(default_factory=dict)  # buque_id -> disparos de defensa de punto acumulados
    minado_desde: dict = field(default_factory=dict)  # orden_id -> segundo simulado en que el buque empezo a minar
    antimisil_disparos: dict = field(default_factory=dict)  # bateria_id -> interceptores antimisil acumulados
    # eventos automaticos del director (engine/eventos_auto.py): (regla, unidad) dentro de su area
    eventos_dentro: set = field(default_factory=set)
    eventos_listo: bool = False
    relevo_aviso: dict = field(default_factory=dict)  # orden_id -> ultimo aviso de que no hay con que relevarla


MUNDOS: dict[int, Mundo] = {}


def mundo_de(escenario_id: int) -> Mundo:
    return MUNDOS.setdefault(escenario_id, Mundo())


@dataclass
class Informe:
    """Resultado de un `paso`: si hubo cambios que piden reenviar el estado completo, las horas cumplidas y las
    alertas para los bandos (se envian al instante: contacto nuevo, ataque, perdida, combustible, mision)."""

    cambios: bool = False
    horas: list = field(default_factory=list)
    alertas: list = field(default_factory=list)
    chats: list = field(default_factory=list)  # mensajes del chat que escribio el director automatico (eventos_auto)


# Causas de pausa automatica (el director elige cuales detienen el reloj) y sus nombres para la pantalla.
CAUSAS_PAUSA = {"contacto": "Contacto nuevo", "ataque": "Ataque a una unidad propia", "perdida": "Unidad perdida",
                "combustible": "Combustible crítico", "mision": "Misión terminada",
                "intercepcion": "Fase de una interceptación", "zona": "Intrusión en una zona",
                "colateral": "Daño colateral (ataque a una unidad neutral)",
                "evento": "Mensaje de un evento automático"}
REPETIR_ALERTA_FUEGO_S = 900.0  # una unidad bajo fuego continuo se vuelve a avisar despues de esto


def pausa_auto(esc) -> dict:
    """{causa: bool} de la pausa automatica del escenario (sin configurar, ninguna)."""
    try:
        datos = json.loads(getattr(esc, "pausa_auto_json", None) or "{}")
    except ValueError:
        datos = {}
    return {c: bool(datos.get(c)) for c in CAUSAS_PAUSA}


class _Ctx:
    def __init__(self, db: Session, esc: Escenario, terreno: Terreno):
        self.db, self.esc, self.terreno = db, esc, terreno
        self.mundo = mundo_de(esc.id)
        self.releer()
        self.clima = clima_mod.contexto(db, esc) if esc.efectos_clima else clima_mod.ClimaLocal("despejado")
        self.ge = ge_mod.contexto(db, esc)
        obras = db.query(Obra).filter(Obra.escenario_id == esc.id, Obra.expira_turno >= esc.turno_actual).all()
        self.obras = obras + infra_mod.cortes(self.lista)
        self.informe = Informe()
        self.en_mision: set[int] = set()
        self.pausas = pausa_auto(esc)
        self._doctrinas: dict[int, dict] = {}
        self.pausa: dict | None = None  # la alerta que pide detener el reloj en este paso
        self.bit = _BitacoraEnVivo(self)
        self.perdidas: dict[int, float] = {}
        self.con_pmi: set | None = None  # (bando, base) con PMI de Inteligencia: se lee al primer ataque a una pista
        self.zonas = {z.id: z for z in zonas_mod.de_escenario(db, esc.id)}  # areas y zonas (engine/zonas.py)
        self.sin_enlace: set = set()  # unidades fuera de la red de enlace de datos (engine/enlace.py)
        asw_mod.AHORA[esc.id] = esc.sim_segundos or 0.0
        asw_mod.cargar_boyas(db, esc.id, esc.sim_segundos or 0.0)  # sonoboyas activas (engine/asw.py)
        from app.models.mina import CampoMinas  # campos de minas con minas (engine/minas.py)

        self.campos_minas = db.query(CampoMinas).filter(CampoMinas.escenario_id == esc.id, CampoMinas.densidad > 0).all()
        self.zona_armada: dict[str, set] = {}  # bando -> intrusos dentro de sus zonas con «armas» (tiran contra ellos)

    def releer(self) -> None:
        """Unidades y ordenes en curso (de nuevo despues de que el adversario automatico da ordenes)."""
        self.unidades = {u.id: u for u in self.db.query(Unidad).filter(Unidad.escenario_id == self.esc.id)}
        self.lista = list(self.unidades.values())
        self.ordenes = {o.id: o for o in self.db.query(Orden).filter(Orden.escenario_id == self.esc.id,
                                                                     Orden.estado == "en_ejecucion")}

    @property
    def t(self) -> float:
        return self.esc.sim_segundos

    def evento(self, tipo: str, bando: str, texto: str, lat=None, lon=None) -> None:
        self.db.add(Evento(escenario_id=self.esc.id, turno=self.esc.turno_actual, tipo=tipo, bando_destino=bando,
                           descripcion=f"[{hora_del_dia(self.esc)}] {texto}", lat=lat, lon=lon, sim_segundos=self.t,
                           hasta_turno=self.esc.turno_actual + 1 if lat is not None else None))
        self.informe.cambios = True

    def alerta(self, causa: str, bando: str, texto: str, lat=None, lon=None, nivel: str = "aviso") -> None:
        """Alerta para un bando (y el director): se envia al instante y, si el director lo eligio, detiene el reloj."""
        a = {"causa": causa, "bando": bando, "nivel": nivel, "texto": f"[{hora_del_dia(self.esc)}] {texto}",
             "lat": lat, "lon": lon, "sim_segundos": self.t}
        self.informe.alertas.append(a)
        if self.pausa is None and self.pausas.get(causa):
            self.pausa = a

    def doctrina(self, u: Unidad) -> dict:
        """Doctrina efectiva de la unidad (la suya o la de su bando), una vez por paso."""
        d = self._doctrinas.get(u.id)
        if d is None:
            d = self._doctrinas[u.id] = doctrina_mod.de_unidad(self.esc, u)
        return d

    def identificado(self, bando: str, x: Unidad) -> bool:
        """El bando tiene a `x` identificado como enemigo (para las armas en estado restringido)."""
        return contactos_vivo.identificado(self, bando, x)

    def autoriza(self, u: Unidad, x: Unidad, dominio: str) -> bool:
        """La doctrina de `u` le permite tirar por su cuenta contra `x` ("aire" o "superficie")."""
        if not self.esc.fuego_automatico:
            return False
        if x.bando == u.bando:  # fuego amigo (engine/iff.py): con armas libres, a la aeronave propia con el IFF apagado
            return dominio == "aire" and iff_mod.sin_iff(x) and self.doctrina(u)["armas_aire"] == "libre"
        if x.bando == "neutral":
            # un neutral (trafico civil o un pais ajeno) solo se ataca por error: con las armas libres y mientras
            # el bando no lo haya clasificado (sin niebla de guerra, todos saben que es neutral)
            if not self.esc.niebla or self.doctrina(u)["armas_aire" if dominio == "aire" else "armas_superficie"] != "libre":
                return False
            if getattr(self.esc, f"ia_{u.bando}", False):
                return False  # el adversario automatico no arriesga daño colateral (no puede corregir su doctrina)
            p = self.mundo.pistas.get((u.bando, x.id))
            return p is None or p["etapa"] == "desconocido"
        if x.id in self.zona_armada.get(u.bando, ()):
            return True  # dentro de una zona propia con «armas»: se tira aunque la doctrina las restrinja
        estado = self.doctrina(u)["armas_aire" if dominio == "aire" else "armas_superficie"]
        if estado == "retenido":
            return False
        return estado == "libre" or self.identificado(u.bando, x)

    def visible_para(self, u: Unidad, bando: str) -> bool:
        return u.bando == bando or not self.esc.niebla or u.id in self.mundo.visibles.get(bando, ())

    def ve(self, sensor: Unidad, u: Unidad) -> bool:
        """Lo que puede tirarle `sensor`: lo que ve su bando o, si esta fuera de la red de enlace de datos, lo que ven
        sus propios sensores (engine/enlace.py)."""
        if self.visible_para(u, sensor.bando):
            return True
        return sensor.id in self.sin_enlace and vision.detecta(sensor, u, self.terreno, self.clima, self.ge)

    def orden_de(self, u: Unidad) -> Orden | None:
        return self.ordenes.get(u.orden_id) if u.orden_id else None

    def terminar(self, orden: Orden | None, u: Unidad | None, texto: str, estado: str = "resuelta") -> None:
        if orden is not None and orden.estado == "en_ejecucion":
            orden.estado, orden.resultado = estado, f"[{hora_del_dia(self.esc)}] {texto}"
            self.ordenes.pop(orden.id, None)
        if u is not None and (orden is None or u.orden_id == orden.id):
            u.orden_id = None
            u.ruta_json = None
        self.informe.cambios = True


def _poner_ruta(u: Unidad, waypoints: list | None) -> None:
    u.ruta_json = json.dumps([[round(a, 6), round(b, 6)] for a, b in waypoints]) if waypoints else None


def _esperar(u: Unidad, lat: float | None = None, lon: float | None = None) -> None:
    """La aeronave queda orbitando sobre el punto a la espera de ordenes; sin punto, en una orbita que pasa por donde
    esta (con centro a su derecha), para que no tenga que desviarse."""
    if lat is None or lon is None:
        lat, lon = geo.destino(u.lat, u.lon, ((u.rumbo or 0.0) + 90.0) % 360.0, RADIO_ORBITA_KM)
    u.mision, u.mision_lat, u.mision_lon = "espera", lat, lon


class _BitacoraEnVivo:
    """Como orders._Bitacora (cada cambio de combustible, municion o carga con su causa), pero en tiempo real los
    cambios son pequeños y continuos: se acumulan por unidad, variable y causa, y al cerrar cada hora se escribe una
    fila del registro logistico por cada uno (la linea de tiempo del informe los cruza con los combates)."""

    def __init__(self, ctx: "_Ctx"):
        self.ctx, self.db, self.escenario = ctx, ctx.db, ctx.esc

    def poner(self, u: Unidad, variable: str, valor: float, causa: str, orden_id: int | None = None) -> None:
        antes = getattr(u, variable)
        if not self.escenario.logistica and variable in ("combustible", "municion") and valor < antes:
            return
        valor = max(0.0, min(100.0, valor))
        if abs(valor - antes) < 1e-9:
            return
        setattr(u, variable, valor)
        acc = self.ctx.mundo.registro.setdefault((u.id, variable, causa), {"antes": antes, "delta": 0.0, "orden": orden_id})
        acc["delta"] += valor - antes

    def volcar(self, turno: int) -> None:
        """Escribe las filas de la hora en el registro logistico y empieza a acumular de nuevo."""
        for (uid, variable, causa), acc in sorted(self.ctx.mundo.registro.items(), key=lambda x: x[0]):
            u = self.ctx.unidades.get(uid)
            if u is None or abs(acc["delta"]) < 0.05:
                continue
            despues = max(0.0, min(100.0, acc["antes"] + acc["delta"]))
            self.db.add(RegistroLogistico(
                escenario_id=self.escenario.id, turno=turno, unidad_id=uid, unidad_nombre=u.nombre, bando=u.bando,
                variable=variable, antes=round(acc["antes"], 2), despues=round(despues, 2), causa=causa,
                orden_id=acc["orden"]))
        self.ctx.mundo.registro.clear()


def _cambiar(ctx: _Ctx, u: Unidad, variable: str, valor: float, causa: str) -> None:
    """Combustible o municion: el cambio queda en el registro logistico de la hora (agrupado por causa)."""
    ctx.bit.poner(u, variable, valor, causa)


# ------------------------------------------------------------------------------------------- ordenes en vivo
def aplicar_orden(db: Session, esc: Escenario, orden: Orden, unidad: Unidad) -> None:
    """La unidad empieza a cumplir la orden (ya validada). Las ordenes anteriores de la unidad ya se cancelaron.

    mover, patrullar, aterrizar y atacar quedan "en_ejecucion" hasta cumplirse; despegar y lanzar se cumplen en el
    acto (el grupo o la salva nacen junto a su base o su lanzador)."""
    orden.emitida_seg = esc.sim_segundos
    hora = hora_del_dia(esc)
    if orden.tipo == "despegar":
        datos = aeronaves_mod.decodificar(orden.detalle)
        modelo_id, n = datos.get("modelo"), int(datos.get("aeronaves") or 1)
        lanzados = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.tipo == "aerea",
                                           Unidad.estado == "activa").count()
        grupo = aeronaves_mod.crear_grupo(unidad, modelo_id, n, datos.get("indicativo", ""), lanzados % 6)
        _esperar(grupo, unidad.lat, unidad.lon)
        grupo.rumbo = 0.0
        carga = armas_mod.armar(grupo, datos.get("carga"), unidad)
        logistica.descontar_despegue(unidad, n)
        db.add(grupo)
        db.flush()
        orden.estado = "resuelta"
        orden.resultado = (f"[{hora}] {grupo.nombre} ({catalogo.MODELOS[modelo_id].corto} x{n}) despegó de {unidad.nombre}"
                           + (f" con {carga}" if carga else "") + " y espera órdenes sobre la base.")
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, sim_segundos=esc.sim_segundos, tipo="despegue", bando_destino=unidad.bando,
                      descripcion=f"[{hora}] Despegó {grupo.nombre} desde {unidad.nombre}."))
        return
    if orden.tipo == "torpedo":
        blanco = db.get(Unidad, orden.objetivo_unidad_id)
        torpedo = asw_mod.crear_torpedo(unidad, blanco, esc.sim_segundos or 0.0)
        torpedo.rumbo = rumbo(unidad.lat, unidad.lon, blanco.lat, blanco.lon)
        asw_mod.gastar_torpedo(unidad)
        gastos_mod.anotar(db, esc, unidad, "Torpedos", "Torpedo", 1)
        asw_mod.exponer(unidad, (esc.sim_segundos or 0.0) + asw_mod.EXPUESTO_S)
        db.add(torpedo)
        db.flush()
        orden.estado = "resuelta"
        llega = geo.distancia_km(unidad.lat, unidad.lon, blanco.lat, blanco.lon) / asw_mod.VELOCIDAD_TORPEDO_KMH * 60
        orden.resultado = f"[{hora}] {unidad.nombre} lanzó un torpedo contra {blanco.nombre} (llega en unos {llega:.0f} min)."
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, sim_segundos=esc.sim_segundos, tipo="lanzamiento",
                      bando_destino=unidad.bando, descripcion=orden.resultado))
        return
    if orden.tipo == "lanzar" and balisticos_mod.lanza(unidad):
        blanco = db.get(Unidad, orden.objetivo_unidad_id)
        n = misiles_mod.decodificar(orden.detalle).get("misiles")
        for misil in balisticos_mod.crear(unidad, blanco, n):
            misil.rumbo = rumbo(unidad.lat, unidad.lon, blanco.lat, blanco.lon)
            db.add(misil)
        unidad.municion = max(0.0, unidad.municion - balisticos_mod.MUNICION_POR_MISIL * n)
        gastos_mod.anotar(db, esc, unidad, "Misiles balísticos", "Misil balístico", n)
        unidad.recarga_hasta = esc.sim_segundos + RECARGA_LANZADOR_S
        db.flush()
        km = geo.distancia_km(unidad.lat, unidad.lon, blanco.lat, blanco.lon)
        impacto = hora_del_dia(esc, (esc.sim_segundos or 0.0) + balisticos_mod.minutos_de_vuelo(km) * 60.0)
        orden.estado = "resuelta"
        orden.resultado = f"[{hora}] {unidad.nombre} lanzó {n} misil(es) balístico(s) contra {blanco.nombre}: impacto a las {impacto}."
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, sim_segundos=esc.sim_segundos, tipo="lanzamiento",
                      bando_destino=unidad.bando, descripcion=orden.resultado))
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, sim_segundos=esc.sim_segundos, tipo="radar",
                      bando_destino=blanco.bando, lat=blanco.lat, lon=blanco.lon, hasta_turno=esc.turno_actual + 1,
                      descripcion=f"[{hora}] Alerta temprana: lanzamiento de {n} misil(es) balístico(s) enemigo(s) hacia "
                                  f"la zona de {blanco.nombre}; impacto estimado a las {impacto}."))
        return
    if orden.tipo == "lanzar":
        blanco = db.get(Unidad, orden.objetivo_unidad_id)
        n = misiles_mod.decodificar(orden.detalle).get("misiles")
        for misil in misiles_mod.crear_misiles(unidad, blanco, n):  # cada misil vuela por separado
            misil.rumbo = rumbo(unidad.lat, unidad.lon, blanco.lat, blanco.lon)
            db.add(misil)
        unidad.municion = max(0.0, unidad.municion - misiles_mod.MUNICION_POR_MISIL * n)
        gastos_mod.anotar(db, esc, unidad, "Misiles de crucero", misiles_mod.modelo_misil(unidad).corto, n)
        unidad.recarga_hasta = esc.sim_segundos + RECARGA_LANZADOR_S
        asw_mod.exponer(unidad, (esc.sim_segundos or 0.0) + asw_mod.EXPUESTO_S)  # un submarino que lanza se delata
        db.flush()
        orden.estado = "resuelta"
        orden.resultado = f"[{hora}] {unidad.nombre} lanzó {n} misil(es) de crucero contra {blanco.nombre}."
        db.add(Evento(escenario_id=esc.id, turno=esc.turno_actual, sim_segundos=esc.sim_segundos, tipo="lanzamiento", bando_destino=unidad.bando,
                      descripcion=orden.resultado))
        return

    if orden.tipo == "interferir":
        punto = orden.waypoints[0]
        radio = catalogo.obtener(unidad.clase, unidad.tipo).interferencia_km
        db.add(Interferencia(escenario_id=esc.id, unidad_id=unidad.id, bando=unidad.bando, lat=punto[0], lon=punto[1],
                             radio_km=radio, turno=esc.turno_actual, inicio_seg=esc.sim_segundos))
        orders._aviso_interferencia(db, esc, esc.turno_actual, unidad.bando, punto[0], punto[1], radio)
        orden.resultado = (f"[{hora}] Interfiere en un radio de {radio:.0f} km sobre ({punto[0]:.3f}, {punto[1]:.3f}) "
                           "mientras mantenga la orden. Al emitir, el enemigo localiza al interferidor.")
        if aeronaves_mod.en_vuelo(unidad):  # el avion de GE orbita donde esta mientras interfiere
            _esperar(unidad)
    orden.estado = "en_ejecucion"
    unidad.orden_id = orden.id
    en_alerta = unidad.en_tierra and orden.tipo == "interceptar"
    alerta_s = aeronaves_mod.despegue_s(unidad)
    if unidad.en_tierra and orden.tipo in ("mover", "patrullar", "atacar", "interceptar", "sonoboyas", "sonar", "minar"):
        if armas_mod.aplica(unidad) and not armas_mod.tiene_carga(unidad):  # sale con la carga de su modelo
            armas_mod.armar(unidad, None, db.get(Unidad, unidad.base_id) if unidad.base_id else None)
        unidad.espera_hasta = None
        if en_alerta:  # la interceptacion lleva su propia cuenta del despegue (fase «alerta»)
            aeronaves_mod.despegar_unidad(unidad)
        else:  # carretea y despega segun su apresto (_esperas_en_tierra); mientras, sigue en tierra
            unidad.despega_hasta = (esc.sim_segundos or 0.0) + alerta_s
    if orden.tipo == "mover":
        _poner_ruta(unidad, orden.waypoints)
        tramos = movimiento.tramos_de(orden)
        if tramos:  # la velocidad y la altura del primer tramo rigen desde ya
            movimiento.aplicar_tramo(unidad, tramos[0])
        if unidad.tipo == "aerea":
            unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None
    elif orden.tipo == "patrullar" and zonas_mod.zona_de_orden(orden):
        # area de patrulla: la recorre de vertice en vertice (_patrullar_zona) y reacciona a lo que entra
        unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None
        _poner_ruta(unidad, None)
        mundo_de(esc.id).patrulla_idx.pop(unidad.id, None)
    elif orden.tipo == "patrullar":
        punto = orden.waypoints[-1]
        unidad.mision, unidad.mision_lat, unidad.mision_lon = "patrulla", punto[0], punto[1]
        _poner_ruta(unidad, None)
    elif orden.tipo == "aterrizar":
        base = db.get(Unidad, orden.objetivo_unidad_id)
        unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None
        _poner_ruta(unidad, [[base.lat, base.lon]])
    elif orden.tipo == "atacar":
        _poner_ruta(unidad, None)
        if unidad.tipo == "aerea":
            unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None
    elif orden.tipo == "construir":
        _poner_ruta(unidad, None)
        listo = hora_del_dia(esc, esc.sim_segundos + TIEMPO_OBRA_S.get(orden.detalle, 3600.0))
        orden.resultado = f"[{hora}] Trabajando en el {orden.detalle}: listo a las {listo} si los ingenieros siguen en el sitio."
    elif orden.tipo == "embarcar":
        _poner_ruta(unidad, None)
        orden.resultado = f"[{hora}] Embarcando: a bordo a las {hora_del_dia(esc, esc.sim_segundos + EMBARQUE_S)}."
    elif orden.tipo == "desembarcar":
        punto = orden.waypoints[-1]
        ruta = [list(w) for w in orden.waypoints]
        if unidad.tipo == "naval":  # el buque se acerca por el agua: navega hasta el anteultimo punto (o se queda)
            ruta = ruta[:-1]
        _poner_ruta(unidad, ruta)
        orden.resultado = f"[{hora}] Va a desembarcar en ({punto[0]:.3f}, {punto[1]:.3f})."
    elif orden.tipo == "apoyar":
        _poner_ruta(unidad, None)
    elif orden.tipo in ("minar", "barrer"):
        _poner_ruta(unidad, None)
        if unidad.tipo == "aerea":
            unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None
        punto = orden.waypoints[0]
        orden.resultado = f"[{hora}] Va a ({punto[0]:.3f}, {punto[1]:.3f}) a " + (
            "sembrar un campo de minas." if orden.tipo == "minar" else "barrer minas.")
    elif orden.tipo in ("sonoboyas", "sonar"):
        _poner_ruta(unidad, None)
        unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None
        punto = orden.waypoints[0]
        orden.resultado = (f"[{hora}] Vuela a ({punto[0]:.3f}, {punto[1]:.3f}) a "
                           + ("sembrar 4 sonoboyas." if orden.tipo == "sonoboyas" else "calar el sonar de inmersión."))
    elif orden.tipo == "interceptar":
        _poner_ruta(unidad, None)
        unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None
        datos = intercep_mod.decodificar(orden.detalle)
        accion = datos.get("accion", "neutralizar")
        blanco = db.get(Unidad, orden.objetivo_unidad_id)
        extra = {"despega": round(esc.sim_segundos + alerta_s)} if en_alerta else {}
        orden.detalle = intercep_mod.codificar(accion, "alerta" if en_alerta else "vectoreo", **extra)
        est = intercep_mod.estimar(unidad, blanco, db.query(Unidad).filter(Unidad.escenario_id == esc.id).all())             if blanco is not None else {}
        cuando = (f" Punto de encuentro estimado en {est['minutos']} min, a {est['km']} km." if est.get("alcanzable")
                  else " El blanco se aleja más rápido: lo persigue por si cambia de rumbo." if est else "")
        orden.resultado = (f"[{hora}] " + (f"Alerta en tierra: despega en {alerta_s / 60:.0f} min y " if en_alerta else "")
                           + f"vectorea hacia {blanco.nombre if blanco else 'el blanco'} para "
                           + intercep_mod.ACCIONES.get(accion, accion).lower() + "." + cuando)
        mundo_de(esc.id).intercepciones.pop(orden.id, None)
    elif orden.tipo == "rumbo":
        # el viraje relativo se cuenta desde el rumbo que trae al recibir la orden (puede llegar demorada)
        pedido = json.loads(orden.detalle or "{}")
        objetivo, sentido = rumbo_objetivo(unidad.rumbo, pedido.get("modo", "rumbo"), float(pedido.get("grados") or 0.0),
                                           pedido.get("sentido", "corto"))
        orden.detalle = json.dumps({**pedido, "objetivo": round(objetivo, 1), "lado": sentido})
        orden.resultado = f"[{hora}] Rumbo {(unidad.rumbo or 0.0) % 360:03.0f}°: {texto_rumbo(objetivo, sentido, unidad.rumbo)} y lo mantiene."
        _poner_ruta(unidad, None)
        unidad.mision, unidad.mision_lat, unidad.mision_lon = "", None, None


def demora_de_orden(db: Session, esc: Escenario, unidad: Unidad, tipo: str) -> float:
    """Segundos simulados que tarda en llegar la orden por las comunicaciones (0 si llega en el acto): la demora que
    fijo el instructor, los centros de comunicaciones caidos, el plan de transmisiones y, dentro de una interferencia
    enemiga, 40 puntos mas. El despegue y el lanzamiento (lineas fijas de la base o el lanzador) llegan siempre."""
    if tipo in ("despegar", "lanzar"):
        return 0.0
    from app.engine import transmisiones as trans_mod

    todas = db.query(Unidad).filter(Unidad.escenario_id == esc.id).all()
    extra = infra_mod.demora_extra_pct(todas, unidad.bando) + trans_mod.demora_extra_pct(esc, unidad.bando, esc.turno_actual)
    extra += sistemas_mod.DEMORA_COMUNICACIONES_PCT * sistemas_mod.dano(unidad, "comunicaciones") / 100.0
    p = orders.prob_demora(esc, unidad, ge_mod.contexto(db, esc), extra)
    if p <= 0:
        return 0.0
    clave = f"{esc.semilla}:demora:{unidad.id}:{esc.sim_segundos:.0f}"
    rng = random.Random(int.from_bytes(hashlib.sha256(clave.encode()).digest()[:8], "big"))
    if rng.random() >= p:
        return 0.0
    return DEMORA_MIN_S + rng.random() * (DEMORA_MAX_S - DEMORA_MIN_S)


def cancelar_ordenes_de(db: Session, unidad: Unidad, motivo: str, hora: str) -> None:
    """Las ordenes en ejecucion o pendientes de la unidad quedan canceladas (las reemplaza otra o la detiene)."""
    for o in db.query(Orden).filter(Orden.unidad_id == unidad.id, Orden.estado.in_(("en_ejecucion", "pendiente"))):
        o.estado, o.resultado = "cancelada", f"[{hora}] {motivo}"
    unidad.orden_id = None
    if getattr(unidad, "en_tierra", False):
        unidad.despega_hasta = None  # sin orden, la aeronave que carreteaba se queda en tierra
    unidad.ruta_json = None


def detener(db: Session, esc: Escenario, unidad: Unidad) -> None:
    """Orden de alto: la unidad se detiene donde esta; una aeronave en vuelo queda orbitando alli."""
    cancelar_ordenes_de(db, unidad, "Detenida por orden.", hora_del_dia(esc))
    if aeronaves_mod.en_vuelo(unidad) and not catalogo.es_misil(unidad):
        _esperar(unidad)


# ------------------------------------------------------------------------------------------- el paso
def paso(db: Session, esc: Escenario, segundos: float, terreno: Terreno | None = None) -> Informe:
    """Avanza el escenario `segundos` simulados. No confirma la sesion (lo hace quien llama)."""
    terreno = terreno or get_terreno()
    ctx = _Ctx(db, esc, terreno)
    aar.asegurar_linea_base(db, esc)
    if db.query(Fotograma.id).filter(Fotograma.escenario_id == esc.id).first() is None:
        guardar_fotograma(ctx)  # el punto de partida de la repeticion
    _detectar(ctx, avisar=True)  # lo que aparecio entre pasos (p. ej., el director movio una unidad)
    restante = max(0.0, segundos)
    detectado = ctx.t
    while restante > 1e-6:
        h = min(PASO_MAX_S, restante)
        _pensar_ia(ctx)
        _logistica(ctx)
        _subpaso(ctx, h)
        clima_mod.derivar(clima_mod.zonas_de(ctx.db, esc), h / 3600.0)  # los frentes se mueven continuos
        restante -= h
        antes = esc.sim_segundos or 0.0
        esc.sim_segundos = antes + h
        if int(esc.sim_segundos // FOTOGRAMA_CADA_S) > int(antes // FOTOGRAMA_CADA_S):
            guardar_fotograma(ctx)
        if ctx.t - detectado >= DETECCION_CADA_S and restante > 1e-6:
            _detectar(ctx, avisar=True)
            detectado = ctx.t
        while turno_de(esc.sim_segundos) > esc.turno_actual:
            _fin_de_hora(ctx)
        if ctx.pausa is not None:
            _pausa_automatica(ctx)
            break
    _detectar(ctx, avisar=True)
    _guardar_contactos(ctx)
    return ctx.informe


def _logistica(ctx: _Ctx) -> None:
    """Reabastecimiento continuo: bases, depositos, convoyes y portaaviones (cada LOGISTICA_CADA_S, la parte de la hora
    transcurrida) y aviones cisterna (cada CISTERNA_CADA_S, con esos minutos para atender receptores)."""
    m = ctx.mundo
    if m.logistica_en is None or m.logistica_en > ctx.t:
        m.logistica_en = m.cisternas_en = ctx.t
        return
    if ctx.t - m.logistica_en >= LOGISTICA_CADA_S:
        fraccion = (ctx.t - m.logistica_en) / 3600.0
        m.logistica_en = ctx.t
        for u in ctx.lista:  # control de averias de los sistemas dañados (engine/sistemas.py)
            if u.estado == "activa" and u.sistemas_json:
                for s in sistemas_mod.reparar(u, fraccion, ctx.lista):
                    ctx.evento("logistica", u.bando, f"{u.nombre}: el control de averías volvió a poner en servicio "
                                                     f"{sistemas_mod.nombre(u, s).lower()}.")
                ctx.informe.cambios = True
        orders._reabastecer(ctx.lista, ctx.bit, {b: infra_mod.factor_combustible(ctx.lista, b) for b in ("azul", "rojo")},
                            fraccion)
    if ctx.t - m.cisternas_en >= CISTERNA_CADA_S:
        minutos = (ctx.t - m.cisternas_en) / 60.0
        m.cisternas_en = ctx.t
        for t in ctx.lista:
            if t.estado == "activa" and apoyo_mod.es_cisterna(t) and not t.en_tierra:
                r = apoyo_mod.reabastecer(t, ctx.lista, ctx.bit, lambda x, b: ctx.visible_para(x, b), minutos)
                if r["receptores"]:
                    detalle = ", ".join(f"{n} ({k} aeronave{'s' if k != 1 else ''})" for n, k, _ in r["receptores"])
                    ctx.evento("logistica", t.bando, f"{t.nombre} reabasteció en vuelo a {detalle}.")


def _pausa_automatica(ctx: _Ctx) -> None:
    """El reloj se detiene por una alerta que el director eligio (el resto del tiempo de este paso no corre)."""
    a = ctx.pausa
    ctx.esc.estado, ctx.esc.pausa_motivo = "pausado", a["texto"][:300]  # el texto de la alerta ya dice que paso
    ctx.evento("direccion", "todos", f"Pausa automática ({CAUSAS_PAUSA.get(a['causa'], a['causa']).lower()}).")
    ctx.informe.cambios = True


def _pensar_ia(ctx: _Ctx) -> None:
    """El adversario automatico decide cada IA_CADA_S simulados (sus ordenes se cumplen desde este mismo paso)."""
    if not (ctx.esc.ia_azul or ctx.esc.ia_rojo) or ctx.t - ctx.mundo.ia_pensada < IA_CADA_S:
        return
    from app import adversario  # importacion tardia: el adversario usa la validacion de las ordenes (routers)

    ctx.mundo.ia_pensada = ctx.t
    ctx.db.flush()  # la sesion no se vacia sola: el adversario tiene que ver las ordenes ya cumplidas
    decisiones = adversario.jugar_turno(ctx.db, ctx.esc, ctx.terreno)
    if any(decisiones.values()):
        ctx.releer()
        ctx.informe.cambios = True


def _subpaso(ctx: _Ctx, h: float) -> None:
    ctx.perdidas = {}
    asw_mod.AHORA[ctx.esc.id] = ctx.t
    mar_mod.fijar(ctx.esc)
    iff_mod.fijar(ctx.esc)
    for u in ctx.lista:
        if u.estado == "activa":
            ctx.mundo.pos_previa[u.id] = (u.lat, u.lon)
    _esperas_en_tierra(ctx)
    _ordenes_demoradas(ctx)
    _interferencias(ctx)
    from app.engine import misiones_vivo  # importacion tardia: el modulo de misiones usa este motor

    misiones_vivo.activar(ctx)
    ctx.en_mision = misiones_vivo.avanzar(ctx, h)  # los grupos en mision los conduce su mision
    for u in list(ctx.lista):
        if u.estado != "activa" or u.tipo == "base" or transporte_mod.embarcada(u) or u.en_tierra or u.id in ctx.en_mision:
            continue
        if catalogo.es_misil(u):
            _guiar_misil(ctx, u, h)
            continue
        orden = ctx.orden_de(u)
        if orden is not None and orden.tipo == "atacar":
            _atacar(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "construir":
            _construir(ctx, u, orden)
        elif orden is not None and orden.tipo == "embarcar":
            _embarcar(ctx, u, orden)
        elif orden is not None and orden.tipo == "desembarcar":
            _desembarcar(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "apoyar":
            _apoyar(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "rumbo":
            _volar_rumbo(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "interceptar":
            _intercepcion(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "patrullar" and zonas_mod.zona_de_orden(orden):
            _patrullar_zona(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "sonoboyas":
            _sembrar_boyas(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "sonar":
            _sonar_inmersion(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "minar":
            _minar(ctx, u, orden, h)
        elif orden is not None and orden.tipo == "barrer":
            _barrer(ctx, u, orden, h)
        elif u.ruta_json:
            _mover(ctx, u, orden, h)
        elif u.tipo == "aerea":
            _orbitar(ctx, u, h)
    aeronaves_mod.seguir_portaaviones(ctx.lista)
    transporte_mod.seguir_transporte(ctx.lista)
    _vigilar_zonas(ctx)
    _relevos(ctx)
    _vigilar_minas(ctx)
    if ctx.t - ctx.mundo.trafico_en >= trafico_mod.MANTENER_CADA_S:
        ctx.mundo.trafico_en = ctx.t
        trafico_mod.mantener(ctx)
    _defensa_de_punto(ctx, h)  # los buques se defienden de los misiles aunque el fuego automatico este apagado
    _defensa_antimisil(ctx, h)  # y los sistemas antimisil, de los balisticos
    if ctx.esc.fuego_automatico:
        _interceptar(ctx)
        _antiaerea_generica(ctx, h)
        _fuego_de_oportunidad(ctx, h)
    _defensa_aerea(ctx)
    _aplicar_perdidas(ctx)
    for u in ctx.lista:
        armas_mod.sincronizar(u)  # el reabastecimiento en % no cambia la municion de una aeronave con carga
    _combustible(ctx)
    eventos_auto.evaluar(ctx)  # reglas del director: disparador -> acciones


# ------------------------------------------------------------------------------------------- movimiento
def _avanzar(ctx: _Ctx, u: Unidad, waypoints: list, h: float) -> movimiento.Movimiento:
    mov = movimiento.simular(u, waypoints, ctx.terreno, ctx.clima, ctx.obras, horas=h / 3600.0)
    if mov.km_reales > 0:
        u.rumbo = rumbo(u.lat, u.lon, mov.lat, mov.lon)
        u.lat, u.lon = mov.lat, mov.lon
        ctx.mundo.movio_en[u.id] = ctx.t + h
    _cambiar(ctx, u, "combustible", u.combustible - mov.combustible_gastado, "movimiento")
    return mov


def _mover(ctx: _Ctx, u: Unidad, orden: Orden | None, h: float) -> None:
    ruta = u.ruta
    destino_base = None
    if orden is not None and orden.tipo == "aterrizar":
        destino_base = ctx.unidades.get(orden.objetivo_unidad_id)
        if destino_base is not None:
            ruta = [[destino_base.lat, destino_base.lon]]  # el portaaviones se mueve: se lo sigue
    mov = _avanzar(ctx, u, ruta, h)
    quedan = ruta[mov.alcanzados:]
    _poner_ruta(u, quedan)
    if mov.alcanzados and orden is not None and orden.tipo == "mover":
        tramos = movimiento.tramos_de(orden)  # al pasar un punto, la velocidad y la altura del tramo que sigue
        pasados = len(orden.waypoints) - len(quedan)
        if 0 <= pasados < len(tramos):
            movimiento.aplicar_tramo(u, tramos[pasados])
    if quedan and not (mov.km_reales <= 0 and mov.nota):
        return
    if orden is not None and orden.tipo == "aterrizar" and destino_base is not None:
        _aterrizar(ctx, u, destino_base, orden)
        return
    if quedan and u.tipo == "terrestre" and u.combustible > 0 and _buscar_otro_camino(ctx, u, orden, quedan[-1]):
        return
    if quedan:  # bloqueada: rio sin puente, terreno intransitable o sin combustible
        ctx.terminar(orden, u, f"Se detuvo en ({u.lat:.4f}, {u.lon:.4f}): {mov.nota}")
        ctx.evento("movimiento", u.bando, f"{u.nombre} se detuvo: {mov.nota}")
        return
    ctx.terminar(orden, u, f"Llegó a su destino ({u.lat:.4f}, {u.lon:.4f}); combustible {u.combustible:.0f} %.")
    if u.tipo == "aerea":
        if orden is not None and orden.tipo == "patrullar":
            return
        _esperar(u)


def _volar_rumbo(ctx: _Ctx, u: Unidad, orden: Orden, h: float) -> None:
    """Orden de rumbo: la aeronave vira hacia el rumbo pedido (TASA_GIRO_GPS grados por segundo, del lado indicado) y
    lo mantiene hasta otra orden o hasta que el combustible la haga regresar."""
    datos = json.loads(orden.detalle or "{}")
    objetivo, lado = float(datos.get("objetivo", u.rumbo or 0.0)), datos.get("lado", "derecha")
    actual = (u.rumbo or 0.0) % 360.0
    falta = (objetivo - actual) % 360.0 if lado == "derecha" else (actual - objetivo) % 360.0
    giro = min(falta, TASA_GIRO_GPS * h)
    nuevo = (actual + giro if lado == "derecha" else actual - giro) % 360.0
    _avanzar(ctx, u, [list(geo.destino(u.lat, u.lon, nuevo, LEJOS_KM))], h)
    u.rumbo = nuevo
    if falta > 0 and giro >= falta:
        orden.resultado = f"[{hora_del_dia(ctx.esc, ctx.t + h)}] En el rumbo {objetivo:03.0f}°: lo mantiene hasta otra orden."


def _buscar_otro_camino(ctx: _Ctx, u: Unidad, orden: Orden | None, destino: list) -> bool:
    """Una unidad terrestre que se encuentra un rio o un terreno que no puede cruzar busca otro camino hasta su destino
    por carreteras y puentes (a lo sumo REINTENTOS_RUTA veces por orden). True si sigue en marcha."""
    clave = (u.id, orden.id if orden is not None else None)
    intentos = ctx.mundo.reintentos_ruta.get(clave, 0)
    if intentos >= REINTENTOS_RUTA:
        return False
    ctx.mundo.reintentos_ruta[clave] = intentos + 1
    r = rutas_mod.ruta(u, list(destino), ctx.terreno, ctx.obras)
    if not r["waypoints"] or r["nota"].startswith(("No hay camino", "El destino es intransitable")):
        return False
    _poner_ruta(u, r["waypoints"])
    ctx.evento("movimiento", u.bando, f"{u.nombre} encontró un obstáculo y sigue por otro camino ({r['km']:.0f} km).")
    return True


def _aterrizar(ctx: _Ctx, u: Unidad, base: Unidad, orden: Orden | None) -> None:
    if geo.distancia_km(u.lat, u.lon, base.lat, base.lon) > aeronaves_mod.RADIO_ATERRIZAJE_KM:
        return
    motivo = aeronaves_mod.error_de_aterrizaje(u, base, ctx.lista)
    if motivo:
        ctx.terminar(orden, u, f"No pudo aterrizar en {base.nombre}: {motivo}")
        _esperar(u)
        ctx.evento("logistica", u.bando, f"{u.nombre} no pudo aterrizar en {base.nombre}: {motivo}")
        return
    aeronaves_mod.aterrizar(u, base, len(aeronaves_mod.estacionadas(base, ctx.lista)))
    rearme = aeronaves_mod.rearme_s(u, base)  # depende de la carga (engine/aeronaves.py)
    u.espera_hasta = ctx.t + rearme
    u.espera_restante = max(1, math.ceil(rearme / 3600.0))
    ctx.terminar(orden, u, f"Aterrizó en {base.nombre}; combustible {u.combustible:.0f} %. "
                           f"Lista para despegar en {rearme / 60:.0f} min (reabastecer y rearmar).")
    ctx.evento("logistica", u.bando, f"{u.nombre} aterrizó en {base.nombre}.")


def _orbitar(ctx: _Ctx, u: Unidad, h: float) -> None:
    """Aeronave sin ruta: vuela hacia su punto de patrulla o espera y orbita sobre el (en sentido horario) gastando
    combustible. Si esta mas cerca o mas lejos que el radio de la orbita, se abre o se cierra de a poco."""
    if u.mision not in MISIONES_CONTINUAS or u.mision_lat is None:
        _esperar(u)
    lat0, lon0 = u.mision_lat, u.mision_lon
    distancia = geo.distancia_km(u.lat, u.lon, lat0, lon0)
    if distancia > LLEGADA_ORBITA_KM:
        _avanzar(ctx, u, [[lat0, lon0]], h)
        return
    km = u.velocidad_kmh * 0.7 * h / 3600.0
    r = min(RADIO_ORBITA_KM, distancia + km) if distancia < RADIO_ORBITA_KM else max(RADIO_ORBITA_KM, distancia - km)
    angulo = rumbo(lat0, lon0, u.lat, u.lon) if distancia > 0.05 else ((u.rumbo or 0.0) + 270.0) % 360.0
    nuevo = (angulo + math.degrees(km / max(r, 1.0))) % 360.0
    lat, lon = geo.destino(lat0, lon0, nuevo, r)
    u.rumbo = rumbo(u.lat, u.lon, lat, lon)
    u.lat, u.lon = lat, lon
    ctx.mundo.movio_en[u.id] = ctx.t + h
    _cambiar(ctx, u, "combustible", u.combustible - aeronaves_mod.combustible_loiter(u) * h / 3600.0,
             "patrulla" if u.mision == "patrulla" else "espera en vuelo")


def _ordenes_demoradas(ctx: _Ctx) -> None:
    """Las ordenes demoradas por las comunicaciones llegan a su unidad: reemplazan a la que cumplia y empiezan."""
    pendientes = [o for o in ctx.db.query(Orden).filter(Orden.escenario_id == ctx.esc.id, Orden.estado == "pendiente",
                                                        Orden.llega_seg.isnot(None), Orden.llega_seg <= ctx.t)]
    for o in pendientes:
        u = ctx.unidades.get(o.unidad_id)
        if u is None or u.estado != "activa":
            o.estado, o.resultado = "rechazada", f"[{hora_del_dia(ctx.esc)}] La orden llegó tarde: la unidad ya no está activa."
            continue
        for previa in ctx.db.query(Orden).filter(Orden.unidad_id == u.id, Orden.id != o.id,
                                                 Orden.estado.in_(("en_ejecucion", "pendiente"))):
            previa.estado, previa.resultado = "cancelada", f"[{hora_del_dia(ctx.esc)}] Reemplazada por una orden que llegó demorada."
            ctx.ordenes.pop(previa.id, None)
        u.orden_id, u.ruta_json = None, None
        aplicar_orden(ctx.db, ctx.esc, o, u)
        o.emitida_seg = o.emitida_seg  # la hora de emision queda la original
        if o.estado == "en_ejecucion":
            ctx.ordenes[o.id] = o
        ctx.evento("comunicaciones", u.bando, f"Llegó a {u.nombre} la orden «{o.tipo}» que estaba demorada.")


def _interferencias(ctx: _Ctx) -> None:
    """Las zonas de interferencia rigen mientras su emisor siga interfiriendo: con la orden "interferir" en curso, o
    en la orbita de una mision de guerra electronica, activo, en vuelo si es un avion y con la zona a su alcance."""
    from app.models.mision import Mision

    vivas = ctx.db.query(Interferencia).filter(Interferencia.escenario_id == ctx.esc.id, Interferencia.inicio_seg.isnot(None),
                                               Interferencia.fin_seg.is_(None)).all()
    centros: dict[int, tuple] = {}  # unidad -> (lat, lon) donde debe interferir
    for o in ctx.ordenes.values():
        if o.tipo == "interferir" and o.estado == "en_ejecucion" and o.waypoints:
            centros[o.unidad_id] = tuple(o.waypoints[0])
    for m in ctx.db.query(Mision).filter(Mision.escenario_id == ctx.esc.id, Mision.estado == "en_curso", Mision.rol == "GE",
                                         Mision.espera_hasta.isnot(None)):
        pts = json.loads(m.puntos_json or "[]")
        if m.unidad_id is not None and m.indice < len(pts) and pts[m.indice]["tipo"] == "orbita":
            p = pts[m.indice]
            centros[m.unidad_id] = tuple(p.get("centro") or (p["lat"], p["lon"]))
    cambio = False
    con_zona = set()
    for z in vivas:
        u = ctx.unidades.get(z.unidad_id)
        sigue = (u is not None and u.estado == "activa" and not u.en_tierra and z.unidad_id in centros
                 and geo.distancia_km(z.lat, z.lon, *centros[z.unidad_id]) < 0.5
                 and geo.distancia_km(u.lat, u.lon, z.lat, z.lon) <= u.alcance_km + RADIO_ORBITA_KM)
        if sigue:
            con_zona.add(z.unidad_id)
        else:
            z.fin_seg, cambio = ctx.t, True
    for uid, (lat, lon) in centros.items():  # misiones de GE que empiezan a orbitar
        u = ctx.unidades.get(uid)
        if uid in con_zona or u is None or u.estado != "activa":
            continue
        radio = catalogo.obtener(u.clase, u.tipo).interferencia_km
        if not radio:
            continue
        ctx.db.add(Interferencia(escenario_id=ctx.esc.id, unidad_id=uid, bando=u.bando, lat=lat, lon=lon, radio_km=radio,
                                 turno=ctx.esc.turno_actual, inicio_seg=ctx.t))
        orders._aviso_interferencia(ctx.db, ctx.esc, ctx.esc.turno_actual, u.bando, lat, lon, radio)
        cambio = True
    if cambio:
        ctx.db.flush()
        ctx.ge = ge_mod.contexto(ctx.db, ctx.esc)
        ctx.informe.cambios = True


def _esperas_en_tierra(ctx: _Ctx) -> None:
    for u in ctx.lista:
        if not u.en_tierra or u.estado != "activa":
            continue
        if u.despega_hasta is not None:  # recibio una orden de vuelo: despega al cumplirse su apresto
            if ctx.t >= u.despega_hasta:
                base = ctx.unidades.get(u.base_id)
                aeronaves_mod.despegar_unidad(u)
                ctx.evento("despegue", u.bando, f"{u.nombre} despegó" + (f" de {base.nombre}" if base else "") + ".",
                           u.lat, u.lon)
                ctx.informe.cambios = True
            continue
        if u.espera_hasta is None:
            continue
        falta = u.espera_hasta - ctx.t
        if falta <= 0:
            u.espera_hasta, u.espera_restante = None, 0
            contra_mod.reponer(u)
            carga = armas_mod.rearmar(u, ctx.unidades.get(u.base_id)) if armas_mod.aplica(u) else ""
            ctx.evento("logistica", u.bando, f"{u.nombre} terminó de reabastecer y rearmar: lista para despegar"
                       + (f" ({carga})." if carga else "."))
        else:
            u.espera_restante = max(1, math.ceil(falta / 3600.0))


# ------------------------------------------------------------------------------------------- deteccion
def _detectar(ctx: _Ctx, avisar: bool = False) -> None:
    anteriores = {b: set(v) for b, v in ctx.mundo.visibles.items()}
    if not ctx.mundo.detectado:  # recien arrancado el servidor: lo ya registrado como contacto no es nuevo
        for bando, uid in ctx.db.query(Contacto.bando, Contacto.unidad_id).filter(Contacto.escenario_id == ctx.esc.id):
            anteriores.setdefault(bando, set()).add(uid)
    ctx.sin_enlace = set()
    for bando in ("azul", "rojo"):
        red = enlace_mod.para(ctx.esc, ctx.lista, bando, ctx.ge)  # imagen comun por enlace de datos
        if red is not None:
            ctx.sin_enlace |= {u.id for u in ctx.lista if u.bando == bando} - red
        vis = vision.unidades_visibles(ctx.lista, bando, ctx.terreno, ctx.clima, ctx.ge, red)
        ids = {u.id for u in vis if u.bando != bando and u.estado == "activa"}
        ctx.mundo.visibles[bando] = ids
        if ctx.esc.niebla:
            contactos_vivo.actualizar(ctx, bando, ids)
        nuevos = ids - anteriores.get(bando, set())
        if nuevos or anteriores.get(bando, set()) - ids:
            ctx.informe.cambios = True
        if avisar and nuevos:
            textos = []
            for uid in sorted(nuevos):
                visto = ctx.mundo.visto_en.get((bando, uid))
                if visto is None or ctx.t - visto > AVISO_CONTACTO_S:
                    textos.append(_rotulo_contacto(ctx, bando, ctx.unidades[uid]))
            if textos:
                texto = f"Contacto nuevo: {', '.join(textos[:4])}" + (f" y {len(textos) - 4} más" if len(textos) > 4 else "") + "."
                ctx.evento("radar", bando, texto)
                primero = ctx.unidades[min(nuevos)]
                ctx.alerta("contacto", bando, texto, primero.lat, primero.lon, "critica")
        for uid in ids:
            ctx.mundo.visto_en[(bando, uid)] = ctx.t
    ctx.mundo.detectado = True


def _rotulo_contacto(ctx: _Ctx, bando: str, x: Unidad) -> str:
    """Como se nombra un contacto en los avisos: lo que el bando sabe de el (engine/contactos_vivo.py)."""
    p = ctx.mundo.pistas.get((bando, x.id)) if ctx.esc.niebla else None
    etapa = p["etapa"] if p is not None else "identificado"
    if etapa == "desconocido":
        return "aeronave desconocida" if x.tipo == "aerea" else "contacto de superficie desconocido"
    texto = catalogo.obtener(x.clase, x.tipo).nombre.lower() + (" en vuelo" if aeronaves_mod.en_vuelo(x) else "")
    return f"{x.nombre} ({texto})" if etapa == "identificado" and p is not None else texto


def _guardar_contactos(ctx: _Ctx, cada_s: float = 60.0) -> None:
    """Ultimo contacto conocido de cada enemigo visto (para cuando sale de la vista), a lo sumo cada minuto simulado."""
    if ctx.t - ctx.mundo.ultimo_contacto_guardado < cada_s:
        return
    ctx.mundo.ultimo_contacto_guardado = ctx.t
    existentes = {(c.bando, c.unidad_id): c for c in ctx.db.query(Contacto).filter(Contacto.escenario_id == ctx.esc.id)}
    for bando, ids in ctx.mundo.visibles.items():
        for uid in ids:
            u = ctx.unidades.get(uid)
            if u is None:
                continue
            c = existentes.get((bando, uid))
            if c is None:
                c = Contacto(escenario_id=ctx.esc.id, bando=bando, unidad_id=uid, lat=u.lat, lon=u.lon,
                             turno_visto=ctx.esc.turno_actual)
                ctx.db.add(c)
            else:
                c.lat, c.lon, c.turno_visto = u.lat, u.lon, ctx.esc.turno_actual
            p = ctx.mundo.pistas.get((bando, uid))
            if p is not None:
                c.etapa, c.puntos, c.incertidumbre_km = p["etapa"], round(p["puntos"], 2), p["inc"]
    for (bando, uid), c in existentes.items():
        u = ctx.unidades.get(uid)
        if u is None or u.estado != "activa":
            ctx.db.delete(c)


# ------------------------------------------------------------------------------------------- combate
def _azar(ctx: _Ctx, clave: int, a: Unidad, d: Unidad) -> float:
    return azar_mod.factor_azar(ctx.esc.semilla, clave, a.id, d.id) if ctx.esc.azar else 1.0


def _resolver(ctx: _Ctx, a: Unidad, d: Unidad, fraccion: float, clave: int, parte: str | None = None):
    """Combate de `a` contra `d` durante `fraccion` de hora (1 = un ataque completo, como un turno). Devuelve
    (perdida del atacante, perdida del defensor, municion gastada, resultado)."""
    t_a, t_d = orders.tipo_efectivo(a), orders.tipo_efectivo(d)
    clase_a, clase_d = catalogo.perfil(a), catalogo.perfil(d)
    aaa_optica = clase_a.emisor and t_d == "aerea" and a.emitiendo is False
    aaa_interferida = clase_a.emisor and t_d == "aerea" and not aaa_optica and ctx.ge.interferido(a)
    consumo = (clase_a.municion_por_ataque or orders.MUNICION_POR_ATAQUE.get(a.tipo, 25.0)) * clase_a.cadencia_fuego
    apoyos = _apoyos(ctx)
    sorpresa = 1.0
    if not ctx.visible_para(a, d.bando):
        sorpresa = orders.SORPRESA_EMBOSCADA if catalogo.obtener(d.clase, d.tipo).vulnerable_emboscada else orders.SORPRESA_GENERAL
    res = combat.resolver_combate(
        fuerza_atacante=a.fuerza, tipo_atacante=t_a, fuerza_defensor=d.fuerza, tipo_defensor=t_d,
        terreno_defensor=ctx.terreno.clase(d.lat, d.lon),
        cobertura_aerea_defensor=orders._tiene_cobertura_aerea(d.bando, d.lat, d.lon, ctx.lista),
        cobertura_aerea_atacante=orders._tiene_cobertura_aerea(a.bando, a.lat, a.lon, ctx.lista),
        bono_atacante=orders._bono_apoyo(a, apoyos, ctx.unidades),
        bono_defensor=orders._bono_apoyo(d, apoyos, ctx.unidades),
        factor_ataque=clase_a.ataque_vs.get(t_d, 1.0) * catalogo.factor_grupo(a) * sistemas_mod.factor(a, "armas")
        * (ge_mod.FACTOR_ANTIAEREA if aaa_interferida else 1.0) * (ge_mod.FACTOR_TIRO_OPTICO if aaa_optica else 1.0)
        * relieve.factor_portatil(a, d) * ota_mod.factor_ataque(a, d) * apresto_mod.factor_adiestramiento(ctx.esc, a.bando)
        * apoyo_mod.factor_control(a, d, ctx.lista, lambda x, b: ctx.visible_para(x, b)),
        factor_defensa=clase_d.defensa * catalogo.factor_grupo(d),
        factor_clima=clima_mod.factor_ataque_aereo(ctx.clima, d.lat, d.lon) if a.tipo == "aerea" else 1.0,
        factor_municion=1.0 if armas_mod.tiene_carga(a) else min(1.0, a.municion / max(consumo * fraccion, 1e-9)),
        azar=_azar(ctx, clave, a, d), sorpresa=sorpresa, cadencia=clase_a.cadencia_fuego,
    )
    # perdidas de la tabla (puntos por hora de combate) por la fraccion de hora; no se calculan sobre la fuerza que
    # queda, para que una unidad muy debil termine fuera de combate en vez de debilitarse cada vez menos
    perd_a = min(a.fuerza, res.perdida_atacante_pct * fraccion)
    perd_d = min(d.fuerza, res.perdida_defensor_pct * fraccion)
    for apoyado in (a, d):  # quien apoya gasta municion mientras su fuego cuenta en el combate
        for sid in apoyos.get(apoyado.id, []):
            s = ctx.unidades.get(sid)
            if s is not None and s.estado == "activa" and s.municion > 0 \
                    and geo.distancia_km(s.lat, s.lon, apoyado.lat, apoyado.lon) <= s.alcance_km:
                _cambiar(ctx, s, "municion", s.municion - orders.MUNICION_POR_APOYO * fraccion, "apoyo")
    if catalogo.opera_aeronaves(d) and perd_d > 0:
        if parte == "pista":  # sin los PMI de Inteligencia las bombas caen dispersas sobre la pista (engine/pmi.py)
            if ctx.con_pmi is None:
                ctx.con_pmi = pmi_mod.entregados(ctx.db, ctx.esc.id)
            bases_mod.aplicar_dano(d, perd_d * pmi_mod.factor_pista(a.bando, d.id, ctx.con_pmi), parte)
        else:
            bases_mod.aplicar_dano(d, perd_d, parte)
    return perd_a, perd_d, consumo * fraccion, res


def _apoyos(ctx: _Ctx) -> dict[int, list[int]]:
    """{unidad apoyada: [unidades que la apoyan]} segun las ordenes de apoyo en curso."""
    salida: dict[int, list[int]] = {}
    for o in ctx.ordenes.values():
        if o.tipo == "apoyar" and o.estado == "en_ejecucion" and o.objetivo_unidad_id:
            salida.setdefault(o.objetivo_unidad_id, []).append(o.unidad_id)
    return salida


def _colateral(ctx: _Ctx, a: Unidad, d: Unidad, perdida: float) -> None:
    """Un bando tiro contra una unidad neutral (trafico civil o un pais ajeno): daño colateral. Alerta al bando que
    tiro (y al director) y evento para el informe; el puntaje lo descuenta engine/objetivos.py."""
    if d.bando != "neutral" or a.bando not in ("azul", "rojo"):
        return
    if ctx.t - ctx.mundo.colateral.get((a.id, d.id), -1e9) < REPETIR_ALERTA_FUEGO_S:
        return
    ctx.mundo.colateral[(a.id, d.id)] = ctx.t
    clase = catalogo.obtener(d.clase, d.tipo).nombre.lower()
    texto = (f"Daño colateral: {a.nombre} tiró contra {d.nombre} ({clase}, neutral)"
             + (f" y le quitó {perdida:.0f} puntos de fuerza." if perdida >= 0.5 else ".")
             + " Penaliza el puntaje del bando.")
    ctx.evento("colateral", a.bando, texto, d.lat, d.lon)
    ctx.alerta("colateral", a.bando, texto, d.lat, d.lon, "critica")


def _perder(ctx: _Ctx, u: Unidad, puntos: float) -> None:
    if puntos > 0:
        ctx.perdidas[u.id] = ctx.perdidas.get(u.id, 0.0) + puntos


def _registrar_combate(ctx: _Ctx, a: Unidad, d: Unidad, orden_id: int | None, perd_a: float, perd_d: float,
                       ratio: float, efectos: str, desde: float | None = None) -> None:
    if a.bando == d.bando and perd_d > 0:  # fuego amigo (engine/iff.py)
        texto = (f"Fuego amigo: {a.nombre} le tiró a {d.nombre}, que volaba con el IFF apagado "
                 f"(−{perd_d:.0f} puntos de fuerza).")
        ctx.evento("fuego_amigo", a.bando, texto, d.lat, d.lon)
        ctx.alerta("ataque", a.bando, texto, d.lat, d.lon, "critica")
    ctx.db.add(Combate(
        escenario_id=ctx.esc.id, turno=ctx.esc.turno_actual, orden_id=orden_id, atacante_id=a.id, defensor_id=d.id,
        atacante_nombre=a.nombre, defensor_nombre=d.nombre, atacante_bando=a.bando, defensor_bando=d.bando,
        ratio=round(ratio, 3), fuerza_ini_atacante=a.fuerza, fuerza_ini_defensor=d.fuerza,
        perdida_atacante=round(perd_a, 2), perdida_defensor=round(perd_d, 2), terreno=ctx.terreno.clase(d.lat, d.lon),
        efectos=efectos, lat=d.lat, lon=d.lon, sim_segundos=ctx.t if desde is None else desde,
    ))


def _pasada(ctx: _Ctx, a: Unidad, d: Unidad, orden: Orden | None, recarga_s: float) -> str:
    """Un ataque completo (pasada de una aeronave, impacto de un misil, enfrentamiento aire-aire). Una aeronave con
    carga de armamento (engine/armas.py) tira con el arma que mejor sirve contra el blanco a esa distancia y la gasta;
    sin un arma que sirva, no hay pasada ("")."""
    arma = None
    if armas_mod.tiene_carga(a):
        arma = armas_mod.elegir(a, d, geo.distancia_km(a.lat, a.lon, d.lat, d.lon))
        if arma is None:
            return ""
        a.arma_elegida = arma
        if arma in misiles_mod.MISIL_DEL_ARMA and d.tipo == "naval":
            return _lanzar_antibuque(ctx, a, d, arma, recarga_s)
    clave = orden.id if orden is not None else int(ctx.t)
    parte = orden.detalle if orden is not None and orden.tipo == "atacar" else None
    perd_a, perd_d, gasto, res = _resolver(ctx, a, d, 1.0, clave, parte)
    if arma is not None and armas_mod.tipo(arma) == "aa" and aeronaves_mod.en_vuelo(d) and contra_mod.usar(d):
        perd_d *= contra_mod.FACTOR  # la aeronave atacada suelta bengalas y chaff
        res.efectos.append(f"{d.nombre} soltó bengalas y chaff")
        gastos_mod.anotar(ctx.db, ctx.esc, d, "Contramedidas", contra_mod.nombre(d), 1, ctx.t)
    _perder(ctx, a, perd_a)
    _perder(ctx, d, perd_d)
    con = ""
    if arma is not None:
        tiradas = armas_mod.gastar(a, arma)
        gastos_mod.arma_aerea(ctx.db, ctx.esc, a, arma, tiradas, ctx.t)
        _cambiar(ctx, a, "municion", armas_mod.municion_pct(a), "combate")
        con = f" con {tiradas} {ota_mod.ARMAMENTO[arma][0]}"
    else:
        _cambiar(ctx, a, "municion", a.municion - gasto, "combate")
    a.recarga_hasta = ctx.t + recarga_s
    _registrar_combate(ctx, a, d, orden.id if orden is not None else None, perd_a, perd_d, res.ratio,
                       "; ".join(res.efectos) + con)
    texto = f"{a.nombre} atacó a {d.nombre}{con}: {res.resumen}"
    _colateral(ctx, a, d, perd_d)
    asw_mod.exponer(a, ctx.t + asw_mod.EXPUESTO_S)  # un submarino que ataca se delata
    ctx.evento("combate", a.bando, texto, d.lat, d.lon)
    if d.bando != a.bando:
        recibido = (f"{d.nombre} fue atacado" + (f" por {a.nombre}" if ctx.visible_para(a, d.bando) else "")
                    + f": perdió {perd_d:.0f} puntos de fuerza.")
        ctx.evento("combate", d.bando, recibido, d.lat, d.lon)
        ctx.alerta("ataque", d.bando, recibido, d.lat, d.lon, "critica")
    return texto


def _lanzar_antibuque(ctx: _Ctx, a: Unidad, d: Unidad, arma: str, recarga_s: float) -> str:
    """La aeronave suelta sus misiles antibuque: cada uno vuela por separado hasta el buque (engine/misiles.py)."""
    tiradas = armas_mod.gastar(a, arma)
    gastos_mod.arma_aerea(ctx.db, ctx.esc, a, arma, tiradas, ctx.t)
    _cambiar(ctx, a, "municion", armas_mod.municion_pct(a), "combate")
    a.recarga_hasta = ctx.t + recarga_s
    for x in misiles_mod.crear_misiles(a, d, tiradas, misiles_mod.MISIL_DEL_ARMA[arma]):
        x.rumbo = rumbo(a.lat, a.lon, d.lat, d.lon)
        ctx.db.add(x)
        ctx.db.flush()
        ctx.unidades[x.id] = x
        ctx.lista.append(x)
    texto = f"{a.nombre} lanzó {tiradas} {ota_mod.ARMAMENTO[arma][0]} contra {d.nombre}."
    ctx.evento("combate", a.bando, texto, d.lat, d.lon)
    ctx.informe.cambios = True
    return texto


def _fuego_continuo(ctx: _Ctx, a: Unidad, d: Unidad, orden: Orden | None, h: float) -> None:
    clave = orden.id if orden is not None else 0
    if ctx.t - ctx.mundo.bajo_fuego.get((a.id, d.id), -1e9) >= REPETIR_ALERTA_FUEGO_S:
        ctx.mundo.bajo_fuego[(a.id, d.id)] = ctx.t
        ctx.alerta("ataque", d.bando, f"{d.nombre} está bajo fuego enemigo.", d.lat, d.lon, "critica")
    # la parte de la base que eligio la orden (pista, plataforma o deposito) tambien vale para el fuego continuo
    parte = orden.detalle if orden is not None and orden.tipo == "atacar" and orden.detalle in bases_mod.PARTES else None
    perd_a, perd_d, gasto, res = _resolver(ctx, a, d, h / 3600.0, clave, parte)
    _perder(ctx, a, perd_a)
    _perder(ctx, d, perd_d)
    _colateral(ctx, a, d, perd_d)
    asw_mod.exponer(a, ctx.t + asw_mod.EXPUESTO_S)
    _cambiar(ctx, a, "municion", a.municion - gasto, "combate")
    acc = ctx.mundo.combates.setdefault((a.id, d.id), {"orden": orden.id if orden is not None else None,
                                                     "perd_a": 0.0, "perd_d": 0.0, "ratio": res.ratio,
                                                     "efectos": "; ".join(res.efectos), "desde": ctx.t})
    acc["perd_a"] += perd_a
    acc["perd_d"] += perd_d
    acc["ratio"] = res.ratio
    acc["hasta"] = ctx.t + h


def _cerrar_combates(ctx: _Ctx, todos: bool = False) -> None:
    """Los fuegos continuos que terminaron, los que llevan FOTOGRAMA_CADA_S (asi la repeticion los muestra mientras
    ocurren) y todos al cerrar la hora quedan registrados en el informe, con la hora en que empezo ese lapso."""
    for clave, acc in list(ctx.mundo.combates.items()):
        sigue = acc.get("hasta", 0.0) >= ctx.t - 1.0
        if not todos and sigue and acc.get("hasta", 0.0) - acc["desde"] < FOTOGRAMA_CADA_S:
            continue
        a, d = ctx.unidades.get(clave[0]), ctx.unidades.get(clave[1])
        del ctx.mundo.combates[clave]
        if a is None or d is None or (acc["perd_a"] < 0.05 and acc["perd_d"] < 0.05):
            continue
        minutos = max(1, round((acc.get("hasta", ctx.t) - acc["desde"]) / 60.0))
        _registrar_combate(ctx, a, d, acc["orden"], acc["perd_a"], acc["perd_d"], acc["ratio"],
                           f"fuego continuo durante {minutos} min" + (f"; {acc['efectos']}" if acc["efectos"] else ""),
                           desde=acc["desde"])


def _puede_disparar(ctx: _Ctx, a: Unidad) -> str:
    clase = catalogo.obtener(a.clase, a.tipo)
    if a.municion <= 0:
        return "Sin munición."
    if a.recarga_hasta and a.recarga_hasta > ctx.t:
        return "recargando"
    if clase.despliegue_turnos and a.tipo != "aerea":
        quieta = ctx.t - ctx.mundo.movio_en.get(a.id, -1e9)
        if quieta < clase.despliegue_turnos * DESPLIEGUE_POR_TURNO_S:
            return "desplegando"
    return ""


def _atacar(ctx: _Ctx, a: Unidad, orden: Orden, h: float) -> None:
    """Orden de ataque en curso: acercarse al blanco hasta tenerlo al alcance y batirlo."""
    d = ctx.unidades.get(orden.objetivo_unidad_id)
    if d is None or d.estado != "activa":
        ctx.terminar(orden, a, "El blanco ya está fuera de combate.")
        if a.tipo == "aerea":
            _esperar(a)
        return
    if ge_mod.enlace_perdido(a, ctx.ge):
        ctx.terminar(orden, a, ge_mod.MOTIVO_SIN_ENLACE)
        if a.tipo == "aerea":
            _esperar(a)
        return
    visto = ctx.visible_para(d, a.bando)
    if not visto:
        ultimo = ctx.mundo.visto_en.get((a.bando, d.id), orden.emitida_seg if orden.emitida_seg is not None else ctx.t)
        if ctx.t - ultimo > CONTACTO_PERDIDO_S:
            ctx.terminar(orden, a, f"Se perdió el contacto con {d.nombre}.")
            if a.tipo == "aerea":
                _esperar(a)
            return
    clase_a = catalogo.perfil(a)
    t_d = orders.tipo_efectivo(d)
    if clase_a.ataque_vs.get(t_d, 0.0) <= 0:
        ctx.terminar(orden, a, f"{clase_a.nombre} no puede atacar objetivos de tipo {t_d}.", "rechazada")
        return
    if a.municion <= 0:
        ctx.terminar(orden, a, "Sin munición: el ataque terminó.")
        if a.tipo == "aerea":
            _esperar(a)
        return
    if armas_mod.tiene_carga(a) and not armas_mod.utiles(a, d):
        ctx.terminar(orden, a, f"No le quedan armas que sirvan contra {d.nombre}: el ataque terminó.")
        _esperar(a)
        return
    distancia = geo.distancia_km(a.lat, a.lon, d.lat, d.lon)
    alcance = armas_mod.alcance(a, d) if a.tipo == "aerea" else a.alcance_km * 0.9
    if distancia > alcance or not visto:
        if a.velocidad_kmh > 0 and a.tipo != "base":
            objetivo = [d.lat, d.lon] if visto else list(ctx.mundo.pos_previa.get(d.id, (d.lat, d.lon)))
            if a.tipo != "aerea" and distancia > alcance:
                # en tierra y en el mar se avanza solo hasta quedar al alcance
                lat, lon = geo.avanzar_hacia(d.lat, d.lon, a.lat, a.lon, alcance * 0.8)
                objetivo = [lat, lon]
            mov = _avanzar(ctx, a, [objetivo], h)
            if mov.km_reales <= 0 and mov.nota:
                ctx.terminar(orden, a, f"No puede acercarse al blanco: {mov.nota}")
        return
    if relieve.fuera_de_techo(a, d):
        return
    if catalogo.obtener(a.clase, a.tipo).defensa_aerea and a.tipo != "aerea" and relieve.en_vuelo(d) \
            and not relieve.linea_de_vista(ctx.terreno, a, d):
        return
    if a.tipo == "aerea":
        if a.recarga_hasta and a.recarga_hasta > ctx.t:
            _orbitar_sobre(ctx, a, d, h)
            return
        aire_aire = t_d == "aerea"
        _pasada(ctx, a, d, orden, RECARGA_AIRE_AIRE_S if aire_aire else RECARGA_PASADA_S)
        if catalogo.obtener(a.clase, a.tipo).se_consume:
            a.estado, a.fuerza = "destruida", 0.0
            ctx.terminar(orden, a, f"Impactó contra {d.nombre} (munición merodeadora).")
            return
        if not aire_aire:
            ctx.terminar(orden, a, f"Pasada de ataque sobre {d.nombre} cumplida; queda en espera sobre la zona.")
            _esperar(a)
        return
    motivo = _puede_disparar(ctx, a)
    if motivo == "Sin munición.":
        ctx.terminar(orden, a, "Sin munición: el ataque terminó.")
        return
    if motivo:
        return
    _fuego_continuo(ctx, a, d, orden, h)


def _vigilar_zonas(ctx: _Ctx) -> None:
    """Zonas de exclusion y de no vuelo (engine/zonas.py): quien entra dispara una alerta (al dueno de la zona, si lo
    ve; en las del director, al bando del intruso) y, en las zonas con «armas», queda como blanco autorizado."""
    ctx.zona_armada = {}
    vigentes = set()
    for z in ctx.zonas.values():  # las que acompañan a una unidad se corren con ella
        u = ctx.unidades.get(z.unidad_id) if z.unidad_id else None
        if u is not None and u.estado == "activa" and zonas_mod.seguir(z, u):
            ctx.informe.cambios = True
    for z in ctx.zonas.values():
        if z.tipo not in ("exclusion", "no_vuelo"):
            continue
        poligono = zonas_mod.puntos(z)
        if len(poligono) < 3:
            continue
        for u in ctx.lista:
            if not zonas_mod.ajena(z, u) or not zonas_mod.afecta(z, u) or not zonas_mod.dentro(u.lat, u.lon, poligono):
                continue
            vigentes.add((z.id, u.id))
            if z.armas and z.bando != "todos":
                ctx.zona_armada.setdefault(z.bando, set()).add(u.id)
            if (z.id, u.id) in ctx.mundo.en_zona:
                continue
            if z.bando == "todos":
                texto = f"{u.nombre} entró a la {zonas_mod.nombre(z)} fijada por la dirección del ejercicio."
                ctx.evento("zona", u.bando, texto, u.lat, u.lon)
                ctx.alerta("zona", u.bando, texto, u.lat, u.lon, "critica")
            elif ctx.visible_para(u, z.bando):
                texto = (f"Intrusión: {_rotulo_contacto(ctx, z.bando, u)} entró a la {zonas_mod.nombre(z)}"
                         + (": las armas propias tiran contra él." if z.armas else "."))
                ctx.evento("zona", z.bando, texto, u.lat, u.lon)
                ctx.alerta("zona", z.bando, texto, u.lat, u.lon, "critica")
            else:
                continue  # no se lo ve: se avisara cuando se lo detecte adentro
    ctx.mundo.en_zona = {k for k in ctx.mundo.en_zona if k in vigentes} | {
        k for k in vigentes if ctx.zonas[k[0]].bando == "todos" or ctx.visible_para(ctx.unidades[k[1]], ctx.zonas[k[0]].bando)}


RELEVO_MARGEN = 20.0  # puntos de combustible sobre el de regreso: con esto sale el relevo de una patrulla permanente
RELEVO_AVISO_S = 1800.0  # cada cuanto se repite el aviso de que no hay con que relevar


def _detalle_json(orden) -> dict:
    try:
        d = json.loads(orden.detalle or "{}")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def _candidato_relevo(ctx: _Ctx, u: Unidad, punto) -> Unidad | None:
    """Aeronave propia en tierra, lista, de la misma clase, sin orden y no en mantenimiento: la mas cercana al punto."""
    listas = [a for a in ctx.lista if a.bando == u.bando and a.tipo == "aerea" and a.estado == "activa" and a.en_tierra
              and a.clase == u.clase and not a.orden_id and a.despega_hasta is None and a.espera_hasta is None
              and aeronaves_mod.apresto(a) != aeronaves_mod.MANTENIMIENTO]
    return min(listas, key=lambda a: geo.distancia_km(a.lat, a.lon, punto[0], punto[1]), default=None)


def _relevos(ctx: _Ctx) -> None:
    """Patrulla permanente: cuando a la aeronave que patrulla le queda poco combustible (el de regreso mas
    RELEVO_MARGEN), sale de una base propia otra igual con la misma orden, para que el punto o el area no queden sin
    cubrir. La que se va regresa sola al llegar a su combustible de regreso."""
    patrullas = [o for o in ctx.ordenes.values() if o.tipo == "patrullar"]
    relevadas = {_detalle_json(o).get("relevo_de") for o in patrullas}
    for o in patrullas:
        d = _detalle_json(o)
        if not d.get("permanente") or o.id in relevadas:
            continue
        u = ctx.unidades.get(o.unidad_id)
        if u is None or u.estado != "activa" or not aeronaves_mod.en_vuelo(u):
            continue
        if u.combustible > ctx.doctrina(u)["combustible_regreso"] + RELEVO_MARGEN:
            continue
        z = ctx.zonas.get(zonas_mod.zona_de_orden(o))
        punto = zonas_mod.centro(zonas_mod.puntos(z)) if z is not None else (o.waypoints[-1] if o.waypoints else (u.lat, u.lon))
        relevo = _candidato_relevo(ctx, u, punto)
        if relevo is None:
            if ctx.t - ctx.mundo.relevo_aviso.get(o.id, -1e9) >= RELEVO_AVISO_S:
                ctx.mundo.relevo_aviso[o.id] = ctx.t
                ctx.evento("logistica", u.bando, f"No hay aeronaves listas en tierra para relevar a {u.nombre} en su "
                                                 "patrulla permanente.", u.lat, u.lon)
            continue
        nueva = Orden(escenario_id=ctx.esc.id, unidad_id=relevo.id, tipo="patrullar", waypoints_json=o.waypoints_json,
                      detalle=json.dumps({**{k: v for k, v in d.items() if k != "relevo_de"}, "relevo_de": o.id}),
                      turno_emitida=ctx.esc.turno_actual)
        ctx.db.add(nueva)
        ctx.db.flush()
        aplicar_orden(ctx.db, ctx.esc, nueva, relevo)
        if nueva.estado == "en_ejecucion":
            ctx.ordenes[nueva.id] = nueva
        relevadas.add(o.id)
        base = ctx.unidades.get(relevo.base_id)
        ctx.evento("despegue", u.bando, f"Relevo: {relevo.nombre} sale" + (f" de {base.nombre}" if base else "")
                   + f" para relevar a {u.nombre} en su patrulla.", u.lat, u.lon)
        ctx.informe.cambios = True


def _patrullar_zona(ctx: _Ctx, u: Unidad, orden: Orden, h: float) -> None:
    """Orden «patrullar» sobre un area: recorre el poligono de vertice en vertice y, si entra un enemigo que su bando
    ve y su doctrina le permite atacar, sale contra el y lo ataca; despues sigue patrullando."""
    z = ctx.zonas.get(zonas_mod.zona_de_orden(orden))
    poligono = zonas_mod.puntos(z) if z is not None else []
    if len(poligono) < 3:
        ctx.terminar(orden, u, "El área de patrulla ya no existe.", "cancelada")
        if u.tipo == "aerea":
            _esperar(u)
        return
    clase = catalogo.perfil(u)
    blancos = []
    if u.municion > 0:
        for x in ctx.lista:
            if x.bando == u.bando or x.estado != "activa" or transporte_mod.embarcada(x) or catalogo.es_misil(x):
                continue
            if clase.ataque_vs.get(orders.tipo_efectivo(x), 0.0) <= 0 or not ctx.visible_para(x, u.bando):
                continue
            if armas_mod.tiene_carga(u) and not armas_mod.utiles(u, x):
                continue
            if not zonas_mod.dentro(x.lat, x.lon, poligono):
                continue
            if ctx.autoriza(u, x, "aire" if aeronaves_mod.en_vuelo(x) else "superficie"):
                blancos.append((geo.distancia_km(u.lat, u.lon, x.lat, x.lon), x))
    if blancos:
        dist, x = min(blancos, key=lambda b: b[0])
        alcance = (armas_mod.alcance(u, x) if u.tipo == "aerea" else u.alcance_km) * ctx.doctrina(u)["distancia_pct"] / 100.0
        if dist > alcance and u.velocidad_kmh > 0:
            ve, vn = intercep_mod.velocidad_de(x)
            plat, plon, _ = intercep_mod.punto_de_mira(u.lat, u.lon, u.velocidad_kmh, x.lat, x.lon, ve, vn)
            _avanzar(ctx, u, [[plat, plon]], h)
            return
        if dist <= alcance and not relieve.fuera_de_techo(u, x):
            if u.tipo == "aerea":
                if not (u.recarga_hasta and u.recarga_hasta > ctx.t):
                    _pasada(ctx, u, x, None, RECARGA_AIRE_AIRE_S if aeronaves_mod.en_vuelo(x) else RECARGA_PASADA_S)
                else:
                    _orbitar_sobre(ctx, u, x, h)
            elif not _puede_disparar(ctx, u):
                _fuego_continuo(ctx, u, x, None, h)
            return
    if u.velocidad_kmh <= 0:
        return
    i = ctx.mundo.patrulla_idx.get(u.id)
    if i is None:  # empieza por el vertice mas cercano
        i = min(range(len(poligono)), key=lambda k: geo.distancia_km(u.lat, u.lon, *poligono[k]))
    destino = poligono[i % len(poligono)]
    mov = _avanzar(ctx, u, [list(destino)], h)
    if geo.distancia_km(u.lat, u.lon, *destino) <= zonas_mod.LLEGADA_VERTICE_KM or (mov.km_reales <= 0 and mov.nota):
        i += 1  # al vertice siguiente (si uno no se puede alcanzar, lo saltea)
    ctx.mundo.patrulla_idx[u.id] = i % len(poligono)


def _sembrar_boyas(ctx: _Ctx, u: Unidad, orden: Orden, h: float) -> None:
    """Orden «sonoboyas»: el avion de patrulla maritima vuela al punto y siembra un cuadro de 4 sonoboyas
    (engine/asw.py); despues queda en espera alli."""
    from app.models.sonoboya import Sonoboya

    punto = orden.waypoints[0]
    if geo.distancia_km(u.lat, u.lon, punto[0], punto[1]) > asw_mod.LLEGADA_KM:
        u.mision, u.mision_lat, u.mision_lon = "", None, None
        _avanzar(ctx, u, [list(punto)], h)
        return
    for lat, lon in asw_mod.cuadro_de_boyas(punto[0], punto[1]):
        ctx.db.add(Sonoboya(escenario_id=ctx.esc.id, bando=u.bando, unidad_id=u.id, lat=lat, lon=lon,
                            radio_km=asw_mod.BOYA_RADIO_KM * mar_mod.factor_boyas(u), desde_seg=ctx.t,
                            hasta_seg=ctx.t + asw_mod.BOYA_VIDA_S))
    gastos_mod.anotar(ctx.db, ctx.esc, u, "Sonoboyas", "Sonoboya", 4, ctx.t)
    ctx.db.flush()
    asw_mod.cargar_boyas(ctx.db, ctx.esc.id, ctx.t)
    hasta = hora_del_dia(ctx.esc, ctx.t + asw_mod.BOYA_VIDA_S)
    ctx.terminar(orden, u, f"Sembró 4 sonoboyas sobre ({punto[0]:.3f}, {punto[1]:.3f}): escuchan submarinos a "
                           f"{asw_mod.BOYA_RADIO_KM * mar_mod.factor_boyas(u):.0f} km hasta las {hasta}.")
    ctx.evento("asw", u.bando, f"{u.nombre} sembró sonoboyas (escuchan hasta las {hasta}).", punto[0], punto[1])
    _esperar(u, punto[0], punto[1])


def _sonar_inmersion(ctx: _Ctx, u: Unidad, orden: Orden, h: float) -> None:
    """Orden «sonar»: el helicoptero antisubmarino va al punto, queda en vuelo estacionario y escucha con el sonar
    calado mientras mantenga la orden (engine/asw.py)."""
    punto = orden.waypoints[0]
    if geo.distancia_km(u.lat, u.lon, punto[0], punto[1]) > asw_mod.ESTACIONARIO_KM * 0.5:
        u.mision, u.mision_lat, u.mision_lon = "", None, None
        _avanzar(ctx, u, [list(punto)], h)
        return
    if u.mision != "sonar":
        u.mision, u.mision_lat, u.mision_lon = "sonar", punto[0], punto[1]
        orden.resultado = (f"[{hora_del_dia(ctx.esc)}] Sonar calado en ({punto[0]:.3f}, {punto[1]:.3f}): escucha "
                           f"submarinos a {asw_mod.SONAR_INMERSION_KM:.0f} km.")
        ctx.informe.cambios = True
    _cambiar(ctx, u, "combustible", u.combustible - aeronaves_mod.combustible_loiter(u) * h / 3600.0, "sonar de inmersion")


def _minar(ctx: _Ctx, u: Unidad, orden: Orden, h: float) -> None:
    """Orden «minar»: va al punto y siembra un campo de minas (el buque tarda; la aeronave, una pasada)."""
    from app.models.mina import CampoMinas

    punto = orden.waypoints[0]
    if geo.distancia_km(u.lat, u.lon, punto[0], punto[1]) > minas_mod.LLEGADA_KM:
        u.mision, u.mision_lat, u.mision_lon = "", None, None
        mov = _avanzar(ctx, u, [list(punto)], h)
        if mov.km_reales <= 0 and mov.nota:
            ctx.terminar(orden, u, f"No puede llegar al punto: {mov.nota}", "cancelada")
        return
    if u.tipo == "naval":
        desde = ctx.mundo.minado_desde.setdefault(orden.id, ctx.t)
        if ctx.t - desde < minas_mod.SIEMBRA_BUQUE_S:
            listo = hora_del_dia(ctx.esc, desde + minas_mod.SIEMBRA_BUQUE_S)
            orden.resultado = f"[{hora_del_dia(ctx.esc)}] Sembrando minas: termina a las {listo}."
            return
    campo = CampoMinas(escenario_id=ctx.esc.id, bando=u.bando, unidad_id=u.id, lat=punto[0], lon=punto[1],
                       radio_km=minas_mod.RADIO_KM, densidad=1.0, conocido_por="[]", creado_seg=ctx.t)
    ctx.db.add(campo)
    ctx.db.flush()
    ctx.campos_minas.append(campo)
    gastos_mod.anotar(ctx.db, ctx.esc, u, "Minas navales", "Mina", minas_mod.MINAS_POR_CAMPO, ctx.t)
    _cambiar(ctx, u, "municion", u.municion - minas_mod.MUNICION_POR_CAMPO, "minado")
    ctx.mundo.minado_desde.pop(orden.id, None)
    ctx.terminar(orden, u, f"Sembró un campo de {minas_mod.MINAS_POR_CAMPO} minas en ({punto[0]:.3f}, {punto[1]:.3f}), "
                           f"radio {minas_mod.RADIO_KM:.0f} km.")
    ctx.evento("minas", u.bando, f"{u.nombre} sembró un campo de minas.", punto[0], punto[1])
    if u.tipo == "aerea":
        _esperar(u)


def _barrer(ctx: _Ctx, u: Unidad, orden: Orden, h: float) -> None:
    """Orden «barrer»: el cazaminas va al punto y limpia el campo de minas que encuentra alli."""
    punto = orden.waypoints[0]
    campos = [c for c in ctx.campos_minas if c.densidad > 0 and minas_mod.dentro(c, punto[0], punto[1])]
    if geo.distancia_km(u.lat, u.lon, punto[0], punto[1]) > minas_mod.LLEGADA_KM:
        mov = _avanzar(ctx, u, [list(punto)], h)
        if mov.km_reales <= 0 and mov.nota:
            ctx.terminar(orden, u, f"No puede llegar al punto: {mov.nota}", "cancelada")
        return
    if not campos:
        ctx.terminar(orden, u, "No hay minas en ese punto: el barrido terminó.")
        return
    c = campos[0]
    minas_mod.revelar(c, u.bando)
    c.densidad = max(0.0, c.densidad - minas_mod.BARRIDO_POR_HORA * h / 3600.0)
    quedan = round(c.densidad * minas_mod.MINAS_POR_CAMPO)
    orden.resultado = f"[{hora_del_dia(ctx.esc)}] Barriendo el campo de minas: quedan unas {quedan}."
    if c.densidad <= 0.02:
        c.densidad = 0.0
        ctx.terminar(orden, u, "Campo de minas barrido: el paso quedó libre.")
        ctx.evento("minas", u.bando, f"{u.nombre} terminó de barrer un campo de minas.", c.lat, c.lon)
    ctx.informe.cambios = True


def _vigilar_minas(ctx: _Ctx) -> None:
    """Los buques que navegan dentro de un campo arriesgan chocar una mina; los cazaminas descubren los campos."""
    campos = [c for c in ctx.campos_minas if c.densidad > 0]
    if not campos:
        return
    for u in ctx.lista:
        if u.estado != "activa" or u.tipo != "naval" or catalogo.es_misil(u) or transporte_mod.embarcada(u):
            continue
        previa = ctx.mundo.pos_previa.get(u.id)
        for c in campos:
            if minas_mod.barre(u) and geo.distancia_km(u.lat, u.lon, c.lat, c.lon) <= c.radio_km + minas_mod.DETECCION_CAZAMINAS_KM:
                if minas_mod.revelar(c, u.bando):
                    texto = f"{u.nombre} detectó un campo de minas."
                    ctx.evento("minas", u.bando, texto, c.lat, c.lon)
                    ctx.alerta("contacto", u.bando, texto, c.lat, c.lon)
            if previa is None:
                continue
            km = minas_mod.km_dentro(c, previa, (u.lat, u.lon))
            p = minas_mod.riesgo(u, km, c)
            dano = minas_mod.choque(ctx.esc.semilla or 0, u, c, ctx.t, p, bool(ctx.esc.azar))
            if dano <= 0:
                continue
            _perder(ctx, u, dano)
            minas_mod.gastar_mina(c, 1.0 if ctx.esc.azar else p)
            nuevo = minas_mod.revelar(c, u.bando)
            if ctx.esc.azar or nuevo:
                texto = f"{u.nombre} chocó una mina (−{dano:.0f} puntos de fuerza)." if ctx.esc.azar \
                    else f"{u.nombre} entró a un campo de minas: sufre daños."
                ctx.evento("minas", u.bando, texto, u.lat, u.lon)
                ctx.alerta("ataque", u.bando, texto, u.lat, u.lon, "critica")
            ctx.informe.cambios = True


def _traza(ctx: _Ctx, orden: Orden, d: Unidad) -> dict:
    """Ultima traza del blanco que tiene el interceptor: posicion, hora y velocidad estimada con dos posiciones
    (como una pista de radar); sin dos posiciones todavia, la de su marcha (engine/interceptacion.py)."""
    tr = ctx.mundo.intercepciones.get(orden.id)
    if tr is None:
        ve, vn = intercep_mod.velocidad_de(d)
        tr = ctx.mundo.intercepciones[orden.id] = {"lat": d.lat, "lon": d.lon, "t": ctx.t, "ve": ve, "vn": vn,
                                                  "lat0": d.lat, "lon0": d.lon, "t0": ctx.t}
    return tr


def _actualizar_traza(ctx: _Ctx, tr: dict, d: Unidad) -> None:
    tr["lat"], tr["lon"], tr["t"] = d.lat, d.lon, ctx.t
    dt = ctx.t - tr["t0"]
    if dt >= intercep_mod.TRAZA_MIN_S:
        x, y = intercep_mod._km(tr["lat0"], tr["lon0"], d.lat, d.lon)
        tr["ve"], tr["vn"] = x / (dt / 3600.0), y / (dt / 3600.0)
        tr["lat0"], tr["lon0"], tr["t0"] = d.lat, d.lon, ctx.t


def _fase_intercepcion(ctx: _Ctx, a: Unidad, orden: Orden, datos: dict, fase: str, texto: str,
                       x: Unidad | None = None) -> None:
    """Cambio de fase: queda en la orden y se avisa al bando (vectoreo, contacto, identificacion, seguimiento...)."""
    if datos.get("fase") == fase:
        return
    datos["fase"] = fase
    extra = {k: v for k, v in datos.items() if k not in ("accion", "fase")}
    orden.detalle = intercep_mod.codificar(datos.get("accion", "neutralizar"), fase, **extra)
    nombre = intercep_mod.FASES.get(fase, fase)
    orden.resultado = f"[{hora_del_dia(ctx.esc)}] {nombre[0].upper() + nombre[1:]}: {texto}"
    lat, lon = (x.lat, x.lon) if x is not None else (a.lat, a.lon)
    ctx.evento("intercepcion", a.bando, f"{a.nombre} ({nombre}): {texto}", lat, lon)
    ctx.alerta("intercepcion", a.bando, f"{a.nombre} ({nombre}): {texto}", lat, lon,
               "critica" if fase == "ataque" else "aviso")


def _intercepcion(ctx: _Ctx, a: Unidad, orden: Orden, h: float) -> None:
    """Orden de interceptacion: curso con punteria adelantada hacia el punto de encuentro, fases con avisos y, segun la
    accion elegida, seguimiento a distancia o ataque (engine/interceptacion.py)."""
    datos = intercep_mod.decodificar(orden.detalle)
    accion = datos.get("accion", "neutralizar")
    d = ctx.unidades.get(orden.objetivo_unidad_id)

    def fin(texto: str, estado: str = "resuelta") -> None:
        ctx.terminar(orden, a, texto, estado)
        ctx.mundo.intercepciones.pop(orden.id, None)
        if a.tipo == "aerea" and a.estado == "activa":
            _esperar(a)
        ctx.alerta("intercepcion", a.bando, f"{a.nombre}: {texto}", a.lat, a.lon)

    if d is None or d.estado != "activa":
        fin(f"{d.nombre if d is not None else 'El blanco'} quedó fuera de combate: interceptación terminada.")
        return
    if not intercep_mod.tipo_blanco(d):
        fin(f"{d.nombre} aterrizó: interceptación terminada.")
        return
    if ge_mod.enlace_perdido(a, ctx.ge):
        fin(ge_mod.MOTIVO_SIN_ENLACE, "cancelada")
        return
    if datos.get("despega") and ctx.t < datos["despega"]:  # alerta en tierra: carreteo y despegue
        return
    if datos.get("fase") == "alerta":
        _fase_intercepcion(ctx, a, orden, datos, "vectoreo", f"despegó y vectorea hacia {d.nombre}.", d)
    tr = _traza(ctx, orden, d)
    visto = ctx.visible_para(d, a.bando)
    if visto:
        _actualizar_traza(ctx, tr, d)
    sin_ver = ctx.t - tr["t"]
    if sin_ver > intercep_mod.ESTIMA_S + intercep_mod.BUSQUEDA_S:
        fin(f"Se perdió el contacto con {d.nombre}: tras buscar sobre el último punto conocido, la interceptación "
            "se abortó.", "cancelada")
        return
    if not visto and sin_ver > intercep_mod.ESTIMA_S:  # busqueda: orbita sobre el ultimo punto estimado
        lat, lon = intercep_mod.estimada(tr["lat"], tr["lon"], tr["ve"], tr["vn"], intercep_mod.ESTIMA_S)
        _fase_intercepcion(ctx, a, orden, datos, "busqueda",
                           f"sin contacto con {d.nombre}: busca sobre el último punto estimado.")
        if a.tipo == "aerea":
            mision = a.mision
            a.mision, a.mision_lat, a.mision_lon = "espera", lat, lon
            _orbitar(ctx, a, h)
            a.mision = mision
        else:
            _avanzar(ctx, a, [[lat, lon]], h)
        return
    if visto:
        tlat, tlon = d.lat, d.lon
    else:
        tlat, tlon = intercep_mod.estimada(tr["lat"], tr["lon"], tr["ve"], tr["vn"], sin_ver)
        _fase_intercepcion(ctx, a, orden, datos, "estima",
                           f"se perdió el contacto con {d.nombre}: sigue la estima de su rumbo y velocidad.")
    dist = geo.distancia_km(a.lat, a.lon, tlat, tlon)
    estado_armas = ctx.doctrina(a)[intercep_mod.dominio(d)]
    hace_falta_id = ctx.esc.niebla and intercep_mod.necesita_identificar(accion, estado_armas)
    identificado = visto and ctx.identificado(a.bando, d)
    if visto and datos.get("fase") in ("vectoreo", "estima", "busqueda") \
            and vision.detecta(a, d, ctx.terreno, ctx.clima, ctx.ge):
        _fase_intercepcion(ctx, a, orden, datos, "contacto",
                           f"tiene a {_rotulo_contacto(ctx, a.bando, d)} en sus sensores, a {dist:.0f} km.", d)
    lista_para_actuar = visto and (identificado or not hace_falta_id)
    if visto and not lista_para_actuar and datos.get("fase") == "contacto" \
            and dist <= 3 * contactos_vivo.IDENTIFICACION_VISUAL_KM:
        _fase_intercepcion(ctx, a, orden, datos, "identificacion", "se acerca para identificarlo a la vista.", d)
    # el curso: punto de encuentro con punteria adelantada (o detras del blanco, a distancia, al seguirlo)
    seguir = accion == "seguir" and lista_para_actuar
    if seguir:
        km_seg = intercep_mod.DISTANCIA_SEGUIMIENTO_KM["aerea" if d.tipo == "aerea" else "naval"]
        if math.hypot(tr["ve"], tr["vn"]) > 1.0:
            rumbo_b = math.degrees(math.atan2(tr["ve"], tr["vn"])) % 360.0
        else:
            rumbo_b = rumbo(a.lat, a.lon, tlat, tlon)
        objetivo = list(geo.destino(tlat, tlon, (rumbo_b + 180.0) % 360.0, km_seg))
        if datos.get("fase") != "seguimiento":
            _fase_intercepcion(ctx, a, orden, datos, "seguimiento",
                               f"identificó a {d.nombre} y lo sigue a {km_seg:.0f} km, a la vista del bando.", d)
    else:
        plat, plon, _ = intercep_mod.punto_de_mira(a.lat, a.lon, a.velocidad_kmh, tlat, tlon, tr["ve"], tr["vn"])
        objetivo = [plat, plon]
    if accion != "seguir" and armas_mod.tiene_carga(a) and not armas_mod.utiles(a, d):
        fin(f"No le quedan armas que sirvan contra {d.nombre}: la interceptación terminó.")
        return
    alcance = armas_mod.alcance(a, d) * ctx.doctrina(a)["distancia_pct"] / 100.0
    al_alcance = visto and dist <= alcance and not relieve.fuera_de_techo(a, d)
    # un buque al alcance se queda a tirar; los demas siguen el curso (en posicion de seguimiento, no se mueve)
    quieto = (a.tipo == "naval" and al_alcance and lista_para_actuar and not seguir) or (seguir and geo.distancia_km(a.lat, a.lon, *objetivo) < 1.0)
    if not quieto:
        mov = _avanzar(ctx, a, [objetivo], h)
        if mov.km_reales <= 0 and mov.nota:
            fin(f"No puede acercarse a {d.nombre}: {mov.nota}", "cancelada")
            return
    if seguir or not lista_para_actuar or not al_alcance:
        return
    if datos.get("fase") != "ataque":
        _fase_intercepcion(ctx, a, orden, datos, "ataque", f"ataca a {d.nombre}.", d)
    if a.municion <= 0:
        fin("Sin munición: la interceptación terminó.")
        return
    if a.tipo == "aerea":
        if a.recarga_hasta and a.recarga_hasta > ctx.t:
            return
        _pasada(ctx, a, d, orden, RECARGA_AIRE_AIRE_S if d.tipo == "aerea" else RECARGA_PASADA_S)
        if catalogo.obtener(a.clase, a.tipo).se_consume:
            a.estado, a.fuerza = "destruida", 0.0
            ctx.terminar(orden, a, f"Impactó contra {d.nombre} (munición merodeadora).")
        return
    if not _puede_disparar(ctx, a):
        _fuego_continuo(ctx, a, d, orden, h)


def _construir(ctx: _Ctx, u: Unidad, orden: Orden) -> None:
    """Los ingenieros trabajan en el sitio; al cumplirse el tiempo de obra el puente o el vado queda tendido."""
    sitio = orden.waypoints[0] if orden.waypoints else None
    tipo = orden.detalle
    if sitio is None or tipo not in orders.COSTO_OBRA:
        ctx.terminar(orden, u, "Orden de construcción incompleta.", "rechazada")
        return
    if geo.distancia_km(u.lat, u.lon, sitio[0], sitio[1]) > u.alcance_km:
        ctx.terminar(orden, u, "Los ingenieros dejaron el sitio: la obra quedó sin terminar.", "cancelada")
        return
    if ctx.t - (orden.emitida_seg if orden.emitida_seg is not None else ctx.t) < TIEMPO_OBRA_S.get(tipo, 3600.0):
        return
    if any(geo.distancia_km(o.lat, o.lon, sitio[0], sitio[1]) < o.radio_km for o in ctx.obras if o.tipo in orders.COSTO_OBRA):
        ctx.terminar(orden, u, "Ya hay una obra en ese punto.", "rechazada")
        return
    if u.municion < orders.COSTO_OBRA[tipo]:
        ctx.terminar(orden, u, f"Material insuficiente ({u.municion:.0f} % < {orders.COSTO_OBRA[tipo]:.0f} %).", "rechazada")
        return
    _cambiar(ctx, u, "municion", u.municion - orders.COSTO_OBRA[tipo], "construccion")
    obra = Obra(escenario_id=ctx.esc.id, unidad_id=u.id, bando=u.bando, tipo=tipo, lat=sitio[0], lon=sitio[1],
                radio_km=movimiento.OBRA_RADIO_KM, creada_turno=ctx.esc.turno_actual,
                expira_turno=ctx.esc.turno_actual + orders.DURACION_OBRA[tipo])
    ctx.db.add(obra)
    ctx.obras.append(obra)
    ctx.terminar(orden, u, f"{tipo.capitalize()} tendido en ({sitio[0]:.4f}, {sitio[1]:.4f}); transitable "
                           f"{orders.DURACION_OBRA[tipo]} h (hasta la hora {obra.expira_turno} del ejercicio).")
    ctx.evento("logistica", u.bando, f"{u.nombre} terminó un {tipo} sobre el río.", sitio[0], sitio[1])


def _embarcar(ctx: _Ctx, u: Unidad, orden: Orden) -> None:
    t = ctx.unidades.get(orden.objetivo_unidad_id)
    motivo = transporte_mod.error_de_embarque(u, t, ctx.lista)
    if motivo:
        ctx.terminar(orden, u, f"No pudo embarcar: {motivo}", "rechazada")
        return
    if ctx.t - (orden.emitida_seg if orden.emitida_seg is not None else ctx.t) < EMBARQUE_S:
        return
    transporte_mod.embarcar(u, t)
    ctx.terminar(orden, u, f"Embarcó en {t.nombre}: viaja a bordo y no se la ve por separado.")
    ctx.evento("logistica", u.bando, f"{u.nombre} embarcó en {t.nombre}.")


def _desembarcar(ctx: _Ctx, t: Unidad, orden: Orden, h: float) -> None:
    """El transporte navega (o vuela) hacia el punto y, a menos de RADIO_DESEMBARCO_KM, deja alli a las tropas."""
    punto = orden.waypoints[-1]
    ruta = t.ruta
    if ruta:
        mov = _avanzar(ctx, t, ruta, h)
        _poner_ruta(t, ruta[mov.alcanzados:])
        if mov.km_reales <= 0 and mov.nota:
            _poner_ruta(t, None)  # no puede seguir acercandose: intenta desde donde esta
    bajadas = transporte_mod.desembarcar(t, punto, ctx.lista, ctx.terreno)
    if bajadas:
        nombres = ", ".join(x.nombre for x in bajadas)
        for x in bajadas:
            ctx.mundo.movio_en[x.id] = ctx.t  # recien desembarcadas: tienen que desplegarse para tirar
        ctx.terminar(orden, t, f"Desembarcó a {nombres} en ({punto[0]:.3f}, {punto[1]:.3f}).")
        ctx.evento("logistica", t.bando, f"{t.nombre} desembarcó a {nombres}.", punto[0], punto[1])
        if t.tipo == "aerea":
            _esperar(t)
        return
    if not t.ruta_json:
        if t.tipo == "aerea":  # el helicoptero vuela hasta el punto mismo
            _poner_ruta(t, [punto])
        else:
            faltan = geo.distancia_km(t.lat, t.lon, punto[0], punto[1])
            ctx.terminar(orden, t, f"No pudo acercarse lo suficiente al punto de desembarco (queda a {faltan:.0f} km): "
                                   "elija un punto en la costa.")


def _apoyar(ctx: _Ctx, a: Unidad, orden: Orden, h: float) -> None:
    """Apoyo de fuego: la unidad se mantiene al alcance de la apoyada (se acerca si hace falta); su fuego cuenta en
    los combates de la apoyada mientras le quede municion."""
    obj = ctx.unidades.get(orden.objetivo_unidad_id)
    if obj is None or obj.estado != "activa":
        ctx.terminar(orden, a, "La unidad apoyada ya no está activa.")
        return
    if a.municion <= 0:
        ctx.terminar(orden, a, "Sin munición: el apoyo terminó.")
        return
    d = geo.distancia_km(a.lat, a.lon, obj.lat, obj.lon)
    if d > a.alcance_km * 0.9 and a.velocidad_kmh > 0:
        lat, lon = geo.avanzar_hacia(obj.lat, obj.lon, a.lat, a.lon, a.alcance_km * 0.7)
        _avanzar(ctx, a, [[lat, lon]], h)
    elif a.tipo == "aerea":
        _orbitar_sobre(ctx, a, obj, h)


def _orbitar_sobre(ctx: _Ctx, a: Unidad, d: Unidad, h: float) -> None:
    a.mision_lat, a.mision_lon = d.lat, d.lon
    mision = a.mision
    a.mision = "espera"
    _orbitar(ctx, a, h)
    a.mision = mision


def _guiar_misil(ctx: _Ctx, m: Unidad, h: float) -> None:
    if m.clase == "torpedo" and m.espera_hasta is not None and ctx.t > m.espera_hasta:
        m.estado, m.fuerza = "destruida", 0.0  # agoto su autonomia sin alcanzar el blanco
        ctx.evento("combate", m.bando, f"{m.nombre} no alcanzó su blanco y se perdió.")
        return
    if balisticos_mod.es_balistico(m):  # trayectoria balistica: cae donde estaba el blanco al lanzar
        _avanzar(ctx, m, [[m.mision_lat, m.mision_lon]], h)
        if geo.distancia_km(m.lat, m.lon, m.mision_lat, m.mision_lon) <= balisticos_mod.LLEGADA_KM:
            blanco = ctx.unidades.get(m.blanco_id) if m.blanco_id else None
            if (blanco is not None and blanco.estado == "activa"
                    and geo.distancia_km(blanco.lat, blanco.lon, m.mision_lat, m.mision_lon) <= balisticos_mod.RADIO_IMPACTO_KM):
                _impacto_misil(ctx, m, blanco)
            else:
                ctx.evento("combate", m.bando, f"{m.nombre} cayó en el punto previsto, pero el blanco ya no estaba.",
                           m.lat, m.lon)
            m.estado, m.fuerza = "destruida", 0.0
            ctx.informe.cambios = True
        return
    blanco = ctx.unidades.get(m.blanco_id) if m.blanco_id else None
    guiado = misiles_mod.blanco_valido(blanco) and blanco.bando != m.bando
    if guiado:
        m.mision_lat, m.mision_lon = blanco.lat, blanco.lon
    if m.mision_lat is None:
        m.estado, m.fuerza = "destruida", 0.0
        return
    _avanzar(ctx, m, [[m.mision_lat, m.mision_lon]], h)
    if guiado and geo.distancia_km(m.lat, m.lon, blanco.lat, blanco.lon) <= m.alcance_km:
        if misiles_mod.salva_de(m):
            _impacto_misil(ctx, m, blanco)
        else:
            _pasada(ctx, m, blanco, None, 0.0)  # salva de un solo bloque (anterior a los misiles por separado)
        m.estado = "destruida"
        m.fuerza = 0.0
        ctx.informe.cambios = True
    elif not guiado and geo.distancia_km(m.lat, m.lon, m.mision_lat, m.mision_lon) <= misiles_mod.LLEGADA_KM:
        m.estado, m.fuerza = "destruida", 0.0
        ctx.evento("combate", m.bando, f"{m.nombre} no encontró su blanco en el último punto conocido y se perdió.")


def _impacto_misil(ctx: _Ctx, m: Unidad, blanco: Unidad) -> None:
    """Un misil de la salva llega: impacta con su probabilidad y hace su parte del daño que la tabla de combate le da
    a la salva completa (engine/misiles.py). Sin azar, el daño esperado (por la probabilidad y lo que le quedo de
    fuerza tras la defensa de punto)."""
    d = misiles_mod.salva_de(m)
    n, pk = max(1, int(d.get("salva") or 1)), float(d.get("pk") or misiles_mod.PK_POR_DEFECTO)
    if blanco.tipo == "naval" and contra_mod.usar(blanco):  # el buque lanza un señuelo
        pk *= contra_mod.FACTOR
        gastos_mod.anotar(ctx.db, ctx.esc, blanco, "Contramedidas", contra_mod.nombre(blanco), 1, ctx.t)
    if ctx.esc.azar:
        clave = f"{ctx.esc.semilla}:impacto:{m.id}:{blanco.id}:{ctx.t:.0f}"
        rng = random.Random(int.from_bytes(hashlib.sha256(clave.encode()).digest()[:8], "big"))
        escala = 1.0 if rng.random() < pk else 0.0
    else:
        escala = pk * max(0.0, m.fuerza) / 100.0
    if escala <= 0:
        ctx.evento("combate", m.bando, f"{m.nombre} falló contra {blanco.nombre}.", blanco.lat, blanco.lon)
        return
    m.aeronaves = n  # la tabla de combate, para la salva completa
    _, perd_d, _, res = _resolver(ctx, m, blanco, 1.0, m.id)
    m.aeronaves = 1
    perd_d = min(blanco.fuerza, perd_d * escala / n)
    _perder(ctx, blanco, perd_d)
    _registrar_combate(ctx, m, blanco, None, 0.0, perd_d, res.ratio, f"impacto de 1 de {n} misiles; " + "; ".join(res.efectos))
    ctx.evento("combate", m.bando, f"{m.nombre} impactó en {blanco.nombre} (−{perd_d:.0f} puntos de fuerza).", blanco.lat, blanco.lon)
    texto = f"{blanco.nombre} recibió el impacto de un misil enemigo (−{perd_d:.0f} puntos de fuerza)."
    ctx.evento("combate", blanco.bando, texto, blanco.lat, blanco.lon)
    ctx.alerta("ataque", blanco.bando, texto, blanco.lat, blanco.lon, "critica")
    _colateral(ctx, m, blanco, perd_d)


def _defensa_de_punto(ctx: _Ctx, h: float) -> None:
    """Defensa de punto de los buques (cañones y misiles de corto alcance): cada canal tira a un misil enemigo en
    vuelo a su alcance por ciclo; una salva grande satura los canales (engine/misiles.py)."""
    misiles = [x for x in ctx.lista if x.estado == "activa" and x.tipo == "aerea" and catalogo.es_misil(x)
               and not balisticos_mod.es_balistico(x)]
    if not misiles:
        return
    for b in ctx.lista:
        dp = misiles_mod.DEFENSA_PUNTO.get(b.clase or "")
        if dp is None or b.estado != "activa" or b.tipo != "naval":
            continue
        cerca = sorted((geo.distancia_km(b.lat, b.lon, x.lat, x.lon), x.id, x) for x in misiles
                       if x.bando != b.bando and x.estado == "activa" and geo.distancia_km(b.lat, b.lon, x.lat, x.lon) <= dp["km"])
        if not cerca:
            continue
        acumulado = ctx.mundo.punto_disparos.get(b.id, 0.0) + dp["canales"] * h / misiles_mod.CICLO_PUNTO_S
        disparos = int(acumulado)
        ctx.mundo.punto_disparos[b.id] = acumulado - disparos
        pk = dp["pk"] * sistemas_mod.factor(b, "armas")
        derribados = tirados = 0
        for _, _, x in cerca:
            if disparos <= 0:
                break
            while disparos > 0 and x.estado == "activa":
                disparos -= 1
                tirados += 1
                if ctx.esc.azar:
                    clave = f"{ctx.esc.semilla}:punto:{b.id}:{x.id}:{ctx.t:.0f}:{disparos}"
                    rng = random.Random(int.from_bytes(hashlib.sha256(clave.encode()).digest()[:8], "big"))
                    x.fuerza = 0.0 if rng.random() < pk else x.fuerza
                else:
                    x.fuerza = max(0.0, x.fuerza - pk * 100.0)
                if x.fuerza <= 0.5:
                    x.estado, x.fuerza = "destruida", 0.0
                    derribados += 1
        gastos_mod.anotar(ctx.db, ctx.esc, b, "Defensa de punto", "Disparo de defensa de punto", tirados, ctx.t)
        if derribados:
            ctx.evento("combate", b.bando, f"La defensa de punto de {b.nombre} derribó {derribados} misil(es) enemigo(s).",
                       b.lat, b.lon)
            ctx.informe.cambios = True


def _defensa_antimisil(ctx: _Ctx, h: float) -> None:
    """Sistemas antimisil contra los misiles balisticos enemigos en fase terminal a su alcance (engine/balisticos.py)."""
    balisticos = [x for x in ctx.lista if x.estado == "activa" and balisticos_mod.es_balistico(x)
                  and balisticos_mod.fase(x) == "terminal"]
    if not balisticos:
        return
    for b in ctx.lista:
        am = balisticos_mod.antimisil(b)
        if am is None or b.estado != "activa":
            continue
        if catalogo.obtener(b.clase, b.tipo).emisor and not ge_mod.emite_radar(b):
            continue  # con el radar apagado no hay solucion de tiro
        cerca = sorted((geo.distancia_km(b.lat, b.lon, x.lat, x.lon), x.id, x) for x in balisticos
                       if x.bando != b.bando and x.estado == "activa" and geo.distancia_km(b.lat, b.lon, x.lat, x.lon) <= am["km"])
        if not cerca:
            continue
        acumulado = ctx.mundo.antimisil_disparos.get(b.id, 0.0) + am["canales"] * h / balisticos_mod.CICLO_ANTIMISIL_S
        disparos = int(acumulado)
        ctx.mundo.antimisil_disparos[b.id] = acumulado - disparos
        s = da_mod.sistema(b)
        listos = da_mod.cargas(b, s) if s is not None else None
        reserva = da_mod.reservas(b, s) if s is not None else None
        pk = am["pk"] * sistemas_mod.factor(b, "armas")
        derribados = tirados = 0
        for _, _, x in cerca:
            while disparos > 0 and x.estado == "activa":
                if listos is not None:  # gasta un misil del arma de mas alcance que tenga lista
                    arma = max((a for a in s.armas if listos[a.id] > 0), key=lambda a: a.alcance_max_km, default=None)
                    if arma is None:
                        disparos = 0
                        break
                    listos[arma.id] -= 1
                elif b.municion < balisticos_mod.MUNICION_POR_INTERCEPTOR:
                    disparos = 0
                    break
                else:
                    b.municion -= balisticos_mod.MUNICION_POR_INTERCEPTOR
                disparos -= 1
                tirados += 1
                if ctx.esc.azar:
                    clave = f"{ctx.esc.semilla}:antimisil:{b.id}:{x.id}:{ctx.t:.0f}:{disparos}"
                    rng = random.Random(int.from_bytes(hashlib.sha256(clave.encode()).digest()[:8], "big"))
                    x.fuerza = 0.0 if rng.random() < pk else x.fuerza
                else:
                    x.fuerza = max(0.0, x.fuerza - pk * 100.0)
                if x.fuerza <= 0.5:
                    x.estado, x.fuerza = "destruida", 0.0
                    derribados += 1
            if disparos <= 0:
                break
        if listos is not None and tirados:
            da_mod.guardar_cargas(b, listos, reserva)
        gastos_mod.anotar(ctx.db, ctx.esc, b, "Interceptores antimisil", "Interceptor antimisil", tirados, ctx.t)
        if tirados:
            ctx.evento("combate", b.bando, f"{b.nombre} lanzó {tirados} interceptor(es) antimisil: derribó {derribados} "
                                           "misil(es) balístico(s).", b.lat, b.lon)
            ctx.informe.cambios = True


def _amenazas_aereas(ctx: _Ctx, u: Unidad, alcance_km: float, linea_de_vista: bool = False) -> list:
    lista = []
    for x in ctx.lista:
        propia = x.bando == u.bando
        if (propia and not iff_mod.sin_iff(x)) or not aeronaves_mod.en_vuelo(x) or not (propia or ctx.ve(u, x)):
            continue
        if balisticos_mod.es_balistico(x):
            continue  # solo los sistemas antimisil pueden con un misil balistico (_defensa_antimisil)
        dist = geo.distancia_km(u.lat, u.lon, x.lat, x.lon)
        if dist > alcance_km:
            continue
        if linea_de_vista and not relieve.linea_de_vista(ctx.terreno, u, x):
            continue
        lista.append((dist, x))
    return [x for _, x in sorted(lista, key=lambda p: p[0])]


def _interceptar(ctx: _Ctx) -> None:
    """Las patrullas sin otra orden combaten al avion enemigo detectado mas cercano a su alcance."""
    for u in ctx.lista:
        if u.mision != "patrulla" or not aeronaves_mod.en_vuelo(u) or u.orden_id and ctx.orden_de(u) and ctx.orden_de(u).tipo == "atacar":
            continue
        if u.municion <= 0 or (u.recarga_hasta and u.recarga_hasta > ctx.t):
            continue
        if catalogo.perfil(u).ataque_vs.get("aerea", 0.0) <= 0:
            continue
        pct = ctx.doctrina(u)["distancia_pct"] / 100.0
        amenazas = [x for x in _amenazas_aereas(ctx, u, u.alcance_km * pct) if ctx.autoriza(u, x, "aire")
                    and geo.distancia_km(u.lat, u.lon, x.lat, x.lon) <= armas_mod.alcance(u, x) * pct]
        if amenazas:
            _pasada(ctx, u, amenazas[0], None, RECARGA_AIRE_AIRE_S)


def _fuego_de_oportunidad(ctx: _Ctx, h: float) -> None:
    """Con las armas de superficie libres (o restringidas), una unidad de tierra o del mar sin orden tira contra el
    enemigo de superficie mas cercano que tiene a su alcance y su bando ve (o tiene identificado)."""
    for u in ctx.lista:
        if (u.estado != "activa" or u.tipo in ("base", "aerea") or u.orden_id is not None or u.ruta_json
                or transporte_mod.embarcada(u)
                or (ctx.doctrina(u)["armas_superficie"] == "retenido" and not ctx.zona_armada.get(u.bando))):
            continue
        clase = catalogo.perfil(u)
        if not any(clase.ataque_vs.get(t, 0.0) > 0 for t in ("terrestre", "naval")) or _puede_disparar(ctx, u):
            continue
        alcance = u.alcance_km * ctx.doctrina(u)["distancia_pct"] / 100.0
        candidatos = []
        for x in ctx.lista:
            if (x.bando == u.bando or x.estado != "activa" or aeronaves_mod.en_vuelo(x) or transporte_mod.embarcada(x)
                    or catalogo.es_misil(x)):
                continue
            if clase.ataque_vs.get(orders.tipo_efectivo(x), 0.0) <= 0 or not ctx.visible_para(x, u.bando):
                continue
            d = geo.distancia_km(u.lat, u.lon, x.lat, x.lon)
            if d <= alcance and ctx.autoriza(u, x, "superficie"):
                candidatos.append((d, x))
        if candidatos:
            _fuego_continuo(ctx, u, min(candidatos, key=lambda c: c[0])[1], None, h)


def _antiaerea_generica(ctx: _Ctx, h: float) -> None:
    """Antiaerea sin sistema de armas detallado: fuego continuo contra la aeronave mas cercana a su alcance."""
    for u in ctx.lista:
        clase = catalogo.obtener(u.clase, u.tipo)
        if not clase.defensa_aerea or da_mod.sistema(u) is not None or u.estado != "activa" or u.fuego_libre is False:
            continue
        orden = ctx.orden_de(u)
        if orden is not None and orden.tipo == "atacar":
            continue
        if _puede_disparar(ctx, u):
            continue
        if clase.emisor and not ge_mod.emite_radar(u):
            continue
        alcance = u.alcance_km * ctx.doctrina(u)["distancia_pct"] / 100.0
        amenazas = [x for x in _amenazas_aereas(ctx, u, alcance, linea_de_vista=True)
                    if not relieve.fuera_de_techo(u, x) and ctx.autoriza(u, x, "aire")]
        if amenazas:
            _fuego_continuo(ctx, u, amenazas[0], None, h)


def _defensa_aerea(ctx: _Ctx) -> None:
    """Baterias con armas propias: cada canal de tiro sigue el ciclo reaccion -> lanzamiento -> vuelo del misil ->
    evaluacion, con sus misiles listos, su reserva y sus recargas."""
    for bat in ctx.lista:
        s = da_mod.sistema(bat)
        if s is None or bat.estado != "activa":
            continue
        enf = ctx.mundo.da.setdefault(bat.id, [])
        listos, reserva = da_mod.cargas(bat, s), da_mod.reservas(bat, s)
        cambio = False
        clase = catalogo.obtener(bat.clase, bat.tipo)
        radar_ok = not clase.emisor or ge_mod.emite_radar(bat)
        interferida = ctx.ge.interferido(bat)
        radio_radar = s.radar_tiro_km * (da_mod.FACTOR_INTERFERENCIA_ALCANCE if interferida else 1.0)
        noche = getattr(ctx.clima, "periodo", "dia") == "noche"
        # 1) los enfrentamientos en curso avanzan
        for e in list(enf):
            if e["hasta"] > ctx.t:
                continue
            arma = s.arma(e["arma"])
            d = ctx.unidades.get(e.get("blanco"))
            if e["fase"] == "recarga":
                n = min(arma.cargados - listos[arma.id], reserva[arma.id])
                listos[arma.id] += n
                reserva[arma.id] -= n
                cambio = True
                enf.remove(e)
            elif e["fase"] == "reaccion":
                if d is None or not aeronaves_mod.en_vuelo(d):
                    enf.remove(e)
                    continue
                dist = geo.distancia_km(bat.lat, bat.lon, d.lat, d.lon)
                if not da_mod.puede_batir(arma, dist, relieve.altura_sobre_terreno(d)) or listos[arma.id] < e["por_salva"]:
                    enf.remove(e)
                    continue
                listos[arma.id] -= e["por_salva"]
                gastos_mod.anotar(ctx.db, ctx.esc, bat, "Cañones antiaéreos" if arma.tipo == "canon" else "Misiles antiaéreos",
                                  arma.nombre, e["por_salva"], ctx.t)
                cambio = True
                e["fase"], e["hasta"] = "vuelo", ctx.t + dist * 1000.0 / arma.velocidad_ms
                ctx.evento("combate", bat.bando, f"{bat.nombre} lanzó {e['por_salva']} {arma.nombre} contra {d.nombre}.")
                if e["tripulada"]:
                    ctx.evento("combate", d.bando, f"{d.nombre}: misil enemigo en vuelo, maniobra evasiva.")
                    if arma.tipo != "canon" and contra_mod.usar(d):
                        e["p"] *= contra_mod.FACTOR
                        e["efectos"] = list(e["efectos"]) + ["bengalas y chaff"]
                        gastos_mod.anotar(ctx.db, ctx.esc, d, "Contramedidas", contra_mod.nombre(d), 1, ctx.t)
                ctx.alerta("ataque", d.bando, f"{d.nombre}: misil antiaéreo enemigo en vuelo.", d.lat, d.lon, "critica")
            elif e["fase"] == "vuelo":
                e["fase"], e["hasta"] = "evaluacion", ctx.t + da_mod.EVALUACION_S
                if d is None or not aeronaves_mod.en_vuelo(d):
                    continue
                total = max(1, int(getattr(d, "aeronaves", 1) or 1))
                if ctx.esc.azar:
                    clave = f"{ctx.esc.semilla}:{bat.id}:{d.id}:{ctx.t:.0f}"
                    rng = random.Random(int.from_bytes(hashlib.sha256(clave.encode()).digest()[:8], "big"))
                    derribos = 1.0 if rng.random() < e["p"] else 0.0
                else:
                    derribos = e["p"]
                perdida = min(d.fuerza, derribos / total * 100.0)
                _perder(ctx, d, perdida)
                _colateral(ctx, bat, d, perdida)
                _registrar_combate(ctx, bat, d, None, 0.0, perdida, e["p"],
                                   f"{arma.nombre}: {e['por_salva']} misil(es), {e['aspecto']}; " + "; ".join(e["efectos"]))
                if derribos >= 1.0 or perdida >= d.fuerza - 0.05:
                    texto = f"{arma.nombre} de {bat.nombre} derribó a {d.nombre}" if perdida >= d.fuerza - 0.05 \
                        else f"{arma.nombre} de {bat.nombre} derribó una aeronave de {d.nombre}"
                elif derribos > 0:
                    texto = f"{arma.nombre} de {bat.nombre} alcanzó a {d.nombre} (−{perdida:.0f} puntos de fuerza)"
                else:
                    texto = f"{arma.nombre} de {bat.nombre} falló contra {d.nombre}"
                ctx.evento("combate", bat.bando, texto + ".", d.lat, d.lon)
                if perdida > 0:
                    ctx.evento("combate", d.bando, f"{d.nombre} fue alcanzado por la defensa aérea enemiga (−{perdida:.0f} puntos).")
            else:  # evaluacion terminada: el canal queda libre
                enf.remove(e)
        # 2) recargar lanzadores vacios desde la reserva (ocupa un canal)
        for a in s.armas:
            if (listos[a.id] < a.por_blanco and reserva[a.id] > 0 and listos[a.id] < a.cargados
                    and not any(e["fase"] == "recarga" and e["arma"] == a.id for e in enf) and len(enf) < max(1, s.canales)):
                enf.append({"fase": "recarga", "arma": a.id, "hasta": ctx.t + a.recarga_min * 60.0})
                ctx.evento("combate", bat.bando, f"{bat.nombre} recarga {a.nombre} desde su reserva ({a.recarga_min:.0f} min).")
        # 3) nuevos blancos con canales libres
        libres = max(1, s.canales) - len(enf)
        orden = ctx.orden_de(bat)
        doct = ctx.doctrina(bat)
        automatico = ctx.esc.fuego_automatico and bat.fuego_libre is not False and (
            doct["armas_aire"] != "retenido" or bool(ctx.zona_armada.get(bat.bando)))
        if libres > 0 and (automatico or (orden is not None and orden.tipo == "atacar")):
            quieta = ctx.t - ctx.mundo.movio_en.get(bat.id, -1e9)
            if quieta >= (s.repliegue_min + s.despliegue_min) * 60.0:
                ocupados = {e.get("blanco") for e in enf}
                blancos = _amenazas_aereas(ctx, bat, max(a.alcance_max_km for a in s.armas), linea_de_vista=True)
                ordenado = orden.objetivo_unidad_id if orden is not None and orden.tipo == "atacar" else None
                # por su cuenta, solo contra lo que la doctrina autoriza (el blanco ordenado, siempre)
                blancos = [x for x in blancos if x.id == ordenado or (automatico and ctx.autoriza(bat, x, "aire"))]
                if ordenado is not None:
                    blancos.sort(key=lambda x: x.id != ordenado)
                forzada = da_mod.arma_elegida(bat, s)
                for d in blancos:
                    if libres <= 0:
                        break
                    if d.id in ocupados:
                        continue
                    dist = geo.distancia_km(bat.lat, bat.lon, d.lat, d.lon)
                    altura = relieve.altura_sobre_terreno(d)
                    arma, _ = da_mod.elegir_arma(s, forzada, dist, altura, radar_ok, radio_radar, listos, {k: 0 for k in reserva})
                    if arma is None:
                        continue
                    f_asp, aspecto = da_mod.factor_aspecto(bat, ctx.mundo.pos_previa.get(d.id), (d.lat, d.lon))
                    if dist > arma.alcance_max_km * f_asp * doct["distancia_pct"] / 100.0:
                        continue
                    cx = catalogo.obtener(d.clase, d.tipo)
                    tripulada = not (cx.dron or cx.misil or cx.se_consume)
                    pk, efectos, _ = da_mod.pk_efectivo(arma, d, interferida=interferida, noche=noche, tripulada=tripulada,
                                                        firma=catalogo.firma(d), altura_m=altura)
                    pk *= sistemas_mod.factor(bat, "armas")  # armas dañadas (engine/sistemas.py)
                    cercano = dist <= arma.alcance_max_km * da_mod.ZONA_CERCANA
                    por_salva = min(listos[arma.id], arma.por_blanco if cercano or arma.tipo == "canon" else 1)
                    if doct["disparos_por_blanco"] and arma.tipo != "canon":  # la doctrina fija los misiles por salva
                        por_salva = min(listos[arma.id], doct["disparos_por_blanco"])
                    if por_salva <= 0:
                        continue
                    traza_propia = vision.detecta(bat, d, ctx.terreno, ctx.clima, ctx.ge)
                    enf.append({"fase": "reaccion", "arma": arma.id, "blanco": d.id, "por_salva": por_salva,
                                "p": 1.0 - (1.0 - pk) ** por_salva, "efectos": efectos, "aspecto": aspecto,
                                "tripulada": tripulada,
                                "hasta": ctx.t + s.reaccion_s + (0.0 if traza_propia else da_mod.REACCION_CUE_S)})
                    libres -= 1
        if cambio:
            da_mod.guardar_cargas(bat, listos, reserva)
            usados = sum(a.cargados + a.reserva for a in s.armas) - sum(listos.values()) - sum(reserva.values())
            total = sum(a.cargados + a.reserva for a in s.armas)
            if total:
                bat.municion = max(0.0, 100.0 * (1 - usados / total))


def _aplicar_perdidas(ctx: _Ctx) -> None:
    for uid, perdida in ctx.perdidas.items():
        u = ctx.unidades[uid]
        if u.estado != "activa":
            continue
        u.fuerza = max(0.0, u.fuerza - perdida)
        if u.fuerza > 0.05:  # el impacto daña uno o dos de sus sistemas (engine/sistemas.py)
            for s in sistemas_mod.recibir(u, perdida, ctx.esc.semilla or 0, ctx.t):
                texto = f"{u.nombre}: {sistemas_mod.nombre(u, s).lower()} fuera de servicio."
                ctx.evento("combate", u.bando, texto, u.lat, u.lon)
                ctx.alerta("ataque", u.bando, texto, u.lat, u.lon, "critica")
        if u.fuerza <= 0.05:
            u.fuerza, u.estado = 0.0, "destruida"
            ctx.terminar(ctx.orden_de(u), u, "La unidad quedó fuera de combate.")
            texto = f"{u.nombre} quedó fuera de combate."
            ctx.evento("combate", u.bando, texto, u.lat, u.lon)
            ctx.alerta("perdida", u.bando, texto, u.lat, u.lon, "critica")
            for b in ("azul", "rojo"):
                if b != u.bando and ctx.visible_para(u, b):
                    ctx.evento("combate", b, f"{u.nombre} enemigo fue destruido.", u.lat, u.lon)
            for x in transporte_mod.repartir_dano(u, perdida, ctx.lista) if transporte_mod.es_transporte(u) else []:
                if x.estado == "destruida":
                    ctx.evento("combate", x.bando, f"{x.nombre} se perdió a bordo de {u.nombre}.")
            ctx.mundo.da.pop(uid, None)
    ctx.perdidas = {}
    _cerrar_combates(ctx)


# ------------------------------------------------------------------------------------------- combustible
def _regresar(ctx: _Ctx, u: Unidad, orden: Orden | None, base: Unidad, detalle: str, texto: str) -> None:
    """La aeronave deja lo que hacia y vuelve a la base (orden automatica de aterrizaje)."""
    if orden is not None:
        ctx.terminar(orden, u, texto, "cancelada")
    rtb = Orden(escenario_id=ctx.esc.id, unidad_id=u.id, tipo="aterrizar", objetivo_unidad_id=base.id, detalle=detalle,
                turno_emitida=ctx.esc.turno_actual, estado="en_ejecucion", emitida_seg=ctx.t)
    ctx.db.add(rtb)
    ctx.db.flush()
    ctx.ordenes[rtb.id] = rtb
    u.orden_id = rtb.id
    u.mision, u.mision_lat, u.mision_lon = "", None, None
    _poner_ruta(u, [[base.lat, base.lon]])
    ctx.evento("logistica", u.bando, texto)


def _combustible(ctx: _Ctx) -> None:
    for u in ctx.lista:
        if not aeronaves_mod.en_vuelo(u) or catalogo.es_misil(u):
            continue
        if u.combustible <= 0:
            base = aeronaves_mod.base_mas_cercana(u, ctx.lista)
            if base is not None and geo.distancia_km(u.lat, u.lon, base.lat, base.lon) <= base.alcance_km:
                orden = ctx.orden_de(u)
                aeronaves_mod.aterrizar(u, base, len(aeronaves_mod.estacionadas(base, ctx.lista)))
                u.espera_hasta = ctx.t + u.espera_restante * 3600.0
                ctx.terminar(orden, u, f"Aterrizó de emergencia en {base.nombre} sin combustible.")
                ctx.evento("logistica", u.bando, f"{u.nombre} aterrizó de emergencia en {base.nombre} sin combustible.")
            else:
                u.estado, u.fuerza = "destruida", 0.0
                ctx.terminar(ctx.orden_de(u), u, "Se quedó sin combustible y se perdió.")
                ctx.evento("logistica", u.bando, f"{u.nombre} se quedó sin combustible lejos de una base y se perdió.",
                           u.lat, u.lon)
                ctx.alerta("perdida", u.bando, f"{u.nombre} se quedó sin combustible y se perdió.", u.lat, u.lon, "critica")
            continue
        orden = ctx.orden_de(u)
        if u.id in ctx.en_mision:
            continue  # su mision resuelve el regreso con combustible critico
        doct = ctx.doctrina(u)
        sin_armas = (doct["regreso_sin_armas"] and u.municion <= 0.5 and not catalogo.obtener(u.clase, u.tipo).se_consume
                     and any(v > 0 for v in catalogo.perfil(u).ataque_vs.values()))
        if sin_armas and (orden is None or orden.tipo not in ("aterrizar", "mover", "rumbo", "interceptar")):
            base = aeronaves_mod.base_mas_cercana(u, ctx.lista)
            if base is not None:
                _regresar(ctx, u, orden, base, "sin armamento",
                          f"{u.nombre} agotó su armamento y regresa a {base.nombre} a rearmarse.")
            continue
        if u.combustible <= doct["combustible_regreso"] and (orden is None or orden.tipo != "aterrizar"):
            base = aeronaves_mod.base_mas_cercana(u, ctx.lista)
            if base is None:
                continue
            if orden is not None:
                ctx.terminar(orden, u, f"Combustible crítico ({u.combustible:.0f} %): regresa a {base.nombre}.", "cancelada")
            rtb = Orden(escenario_id=ctx.esc.id, unidad_id=u.id, tipo="aterrizar", objetivo_unidad_id=base.id,
                        detalle="combustible critico", turno_emitida=ctx.esc.turno_actual, estado="en_ejecucion",
                        emitida_seg=ctx.t)
            ctx.db.add(rtb)
            ctx.db.flush()
            ctx.ordenes[rtb.id] = rtb
            u.orden_id = rtb.id
            u.mision, u.mision_lat, u.mision_lon = "", None, None
            _poner_ruta(u, [[base.lat, base.lon]])
            ctx.evento("logistica", u.bando,
                       f"{u.nombre} con combustible crítico ({u.combustible:.0f} %) regresa a {base.nombre}.")
            ctx.alerta("combustible", u.bando, f"{u.nombre} con combustible crítico ({u.combustible:.0f} %) regresa a "
                                               f"{base.nombre}.", u.lat, u.lon)


# ------------------------------------------------------------------------------------------- cada hora
def _fin_de_hora(ctx: _Ctx) -> None:
    """Procesos horarios del SIETE al cumplirse la hora `turno_actual`; despues el turno pasa a la hora siguiente."""
    esc, db, turno = ctx.esc, ctx.db, ctx.esc.turno_actual
    _cerrar_combates(ctx, todos=True)
    ctx.bit.volcar(turno)  # el reabastecimiento ya fue continuo (_logistica): queda el registro de la hora
    for u in ctx.lista:
        u.recarga_restante = max(0, u.recarga_restante - 1)
        u.despliegue_restante = max(0, u.despliegue_restante - 1)
    for bando, texto in apresto_mod.avanzar(esc, turno):
        ctx.evento("direccion", bando, texto)
    for d, nuevo in rescate_mod.avanzar(esc, ctx.lista, turno):
        if nuevo != "capturado":
            ctx.evento("combate", d["bando"], f"Se perdió el contacto con {d['tripulantes']} tripulante(s) de {d['grupo']}.")
    for u in ctx.lista:
        if catalogo.opera_aeronaves(u) and u.estado == "activa":
            bases_mod.reparar(u, ctx.lista)
    for z in clima_mod.avanzar(db, esc, turno, mover=False):
        ctx.evento("clima", "todos", f"Se disipó la zona de {z.tipo}{' ' + z.nombre if z.nombre else ''}.")
    for o in db.query(Obra).filter(Obra.escenario_id == esc.id, Obra.expira_turno <= turno):
        db.delete(o)
    db.flush()
    objetivos_mod.evaluar(db, esc)
    intel_mod.procesar_turno(db, esc)
    aar.guardar_instantanea(db, esc, turno)
    esc.turno_actual = turno + 1
    ctx.informe.horas.append(turno)
    ctx.informe.cambios = True


def guardar_fotograma(ctx: _Ctx) -> None:
    """Fotograma de la repeticion: donde esta, con cuanta fuerza y en que estado cada unidad ahora."""
    filas = [[u.id, round(u.lat, 5), round(u.lon, 5), round(u.fuerza, 1), u.estado]
             for u in sorted(ctx.lista, key=lambda x: x.id)]
    ctx.db.add(Fotograma(escenario_id=ctx.esc.id, sim_segundos=ctx.t, turno=turno_de(ctx.t), clima=ctx.esc.clima,
                         datos_json=json.dumps(filas, separators=(",", ":"))))


# ------------------------------------------------------------------------------------------- difusion
def posiciones_para(db: Session, esc: Escenario, rol: str) -> dict:
    """Mensaje liviano que se envia cada segundo: el reloj y donde esta cada unidad que el rol ve (niebla de guerra).
    Cada unidad: [id, lat, lon, rumbo, en_tierra, fuerza, combustible] (fuerza y combustible solo de las propias)."""
    mundo = mundo_de(esc.id)
    propio = rol if rol in ("azul", "rojo") else None
    filas = []
    for u in db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.estado == "activa"):
        if transporte_mod.embarcada(u) and u.bando != propio:
            continue
        if propio and u.bando != propio and esc.niebla and u.id not in mundo.visibles.get(propio, ()):
            continue
        ve_datos = propio is None or u.bando == propio
        lat, lon = u.lat, u.lon
        if not ve_datos and esc.niebla:  # el enemigo, donde el bando cree que esta (engine/contactos_vivo.py)
            inc = contactos_vivo.incertidumbre(contactos_vivo.pista(db, esc, propio, u.id), u, esc.sim_segundos or 0.0)
            lat, lon = contactos_vivo.aproximar(esc.semilla, propio, u.id, lat, lon, inc, esc.sim_segundos or 0.0)
        filas.append([u.id, round(lat, 5), round(lon, 5), round(u.rumbo) if u.rumbo is not None else None,
                      1 if u.en_tierra else 0, round(u.fuerza) if ve_datos else None,
                      round(u.combustible) if ve_datos else None])
    return {"tipo": "posiciones", "reloj": reloj(esc), "unidades": filas}


def reloj(esc: Escenario) -> dict:
    return {"sim_segundos": round(esc.sim_segundos or 0.0, 1), "velocidad": esc.velocidad, "estado": esc.estado,
            "turno": esc.turno_actual, "hora": hora_del_dia(esc)}
