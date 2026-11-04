"""Comunicaciones simuladas (chat tactico sobre el WebSocket existente).

Un *interceptor* decide, para cada mensaje y cada bando receptor, si se pierde por interferencia
electronica y cuanto demora en llegar (latencia base + variacion), segun la configuracion del
escenario. El instructor (celula de control) ve todo al instante, con la etiqueta de lo que le
paso a cada bando. La decision se guarda en el mensaje para que el historial sea coherente.

Canales:
- alumno: "bando" (la red de su bando) o "mando" (hacia el instructor);
- instructor: "azul", "rojo" o "todos" (difusion; cada bando sufre su propia interferencia);
- observador: sin acceso.
"""

import asyncio
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.escenario import Escenario
from app.models.mensaje import Mensaje
from app.models.usuario import Usuario, ahora

BANDOS = ("azul", "rojo")
MAX_TEXTO = 500
LIMITE_MENSAJES = 6  # por usuario y ventana
VENTANA_S = 10.0
HISTORIAL = 50


@dataclass(frozen=True)
class Enlace:
    """Calidad del enlace de radio del escenario."""

    latencia_ms: int = 0
    jitter_ms: int = 0
    perdida_pct: int = 0

    @classmethod
    def de(cls, escenario: Escenario) -> "Enlace":
        return cls(escenario.com_latencia_ms or 0, escenario.com_jitter_ms or 0, escenario.com_perdida_pct or 0)


@dataclass(frozen=True)
class Entrega:
    perdido: bool
    demora_ms: int


class Interceptor:
    """Decide la suerte de cada mensaje. `rng` se puede fijar en las pruebas."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    def decidir(self, enlace: Enlace) -> Entrega:
        perdido = self.rng.random() * 100.0 < enlace.perdida_pct
        demora = enlace.latencia_ms + (self.rng.randint(0, enlace.jitter_ms) if enlace.jitter_ms else 0)
        return Entrega(perdido, demora)


interceptor = Interceptor()
dormir = asyncio.sleep  # reemplazable en las pruebas
_recientes: dict[int, deque] = defaultdict(deque)
_tareas: set = set()  # referencias a las entregas diferidas (para que no las recoja el GC)


def canal_de(rol: str, canal_pedido: str) -> str | None:
    """Canal real del mensaje o None si ese rol no puede usar el canal pedido."""
    if rol in BANDOS:
        return {"bando": rol, "mando": "mando"}.get(canal_pedido)
    if rol == "instructor":
        return canal_pedido if canal_pedido in ("azul", "rojo", "todos") else None
    return None


def lados_afectados(canal: str, rol_remitente: str) -> tuple[str, ...]:
    """Bandos cuya recepcion se degrada."""
    if canal in BANDOS:
        return (canal,)
    if canal == "todos":
        return BANDOS
    return (rol_remitente,) if rol_remitente in BANDOS else ()  # "mando": el enlace del remitente


def _iso(dt) -> str:
    return dt.isoformat() + "Z"


def _payload(m: Mensaje, con_entrega: bool) -> dict:
    d = {
        "id": m.id, "canal": m.canal, "remitente": m.remitente_nombre, "rol": m.remitente_rol,
        "texto": m.texto, "turno": m.turno, "creado_en": _iso(m.creado_en),
    }
    if con_entrega:
        d["entrega"] = {
            lado: {"perdido": getattr(m, f"perdido_{lado}"), "demora_ms": getattr(m, f"demora_{lado}_ms")}
            for lado in lados_afectados(m.canal, m.remitente_rol)
        }
    return {"tipo": "chat", "mensaje": d}


def payload_de(m: Mensaje) -> dict:
    """El mensaje tal como lo recibe la pantalla (sin los datos de entrega)."""
    return _payload(m, False)


def historial_para(db: Session, escenario: Escenario, usuario: Usuario) -> list[dict]:
    """Mensajes que `usuario` ya deberia haber recibido (los perdidos o aun en transito no salen)."""
    if usuario.rol not in BANDOS and usuario.rol != "instructor":
        return []
    filas = (
        db.query(Mensaje).filter(Mensaje.escenario_id == escenario.id)
        .order_by(Mensaje.id.desc()).limit(HISTORIAL * 3).all()
    )
    salida = []
    t = ahora()
    for m in reversed(filas):
        if usuario.rol == "instructor":
            salida.append(_payload(m, True))
        elif m.remitente_id == usuario.id:
            salida.append(_payload(m, False))
        elif m.canal in (usuario.rol, "todos"):
            perdido = getattr(m, f"perdido_{usuario.rol}")
            llega = m.creado_en + timedelta(milliseconds=getattr(m, f"demora_{usuario.rol}_ms"))
            if not perdido and llega <= t:
                salida.append(_payload(m, False))
    return salida[-HISTORIAL:]


async def _entregar(conexion, payload: dict, demora_ms: int) -> None:
    if demora_ms > 0:
        await dormir(demora_ms / 1000.0)
    try:
        await conexion.websocket.send_json(payload)
    except Exception:
        pass  # el cliente se fue mientras el mensaje "viajaba"


async def procesar(manager, db: Session, escenario: Escenario, usuario: Usuario, datos: dict) -> str | None:
    """Valida, guarda y entrega un mensaje. Devuelve un texto de error o None si salio bien."""
    canal = canal_de(usuario.rol, str(datos.get("canal", "")))
    if canal is None:
        return "No tiene acceso a ese canal de comunicaciones."
    texto = str(datos.get("texto", "")).strip()
    if not texto:
        return "El mensaje esta vacio."
    if len(texto) > MAX_TEXTO:
        return f"El mensaje supera los {MAX_TEXTO} caracteres."
    if escenario.estado == "finalizado":
        return "El escenario ya finalizo."

    ahora_m = time.monotonic()
    recientes = _recientes[usuario.id]
    while recientes and ahora_m - recientes[0] > VENTANA_S:
        recientes.popleft()
    if len(recientes) >= LIMITE_MENSAJES:
        return "Demasiados mensajes: espere unos segundos."
    recientes.append(ahora_m)

    lados = lados_afectados(canal, usuario.rol)
    enlace = Enlace.de(escenario)
    decisiones = {lado: interceptor.decidir(enlace) for lado in lados}
    m = Mensaje(
        escenario_id=escenario.id, canal=canal, remitente_id=usuario.id, remitente_nombre=usuario.username,
        remitente_rol=usuario.rol, texto=texto, turno=escenario.turno_actual,
        demora_azul_ms=decisiones["azul"].demora_ms if "azul" in decisiones else 0,
        demora_rojo_ms=decisiones["rojo"].demora_ms if "rojo" in decisiones else 0,
        perdido_azul=decisiones["azul"].perdido if "azul" in decisiones else False,
        perdido_rojo=decisiones["rojo"].perdido if "rojo" in decisiones else False,
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    base, con_entrega = _payload(m, False), _payload(m, True)
    for c in list(manager.conexiones(escenario.id)):
        if c.rol == "instructor":
            await _entregar(c, con_entrega, 0)  # la celula de control lo ve todo, al instante
        elif c.rol in BANDOS:
            if c.usuario_id == usuario.id:
                await _entregar(c, base, 0)  # eco inmediato para quien escribe
            elif c.rol in decisiones and canal in (c.rol, "todos"):
                d = decisiones[c.rol]
                if d.perdido:
                    continue
                if d.demora_ms > 0:
                    tarea = asyncio.create_task(_entregar(c, base, d.demora_ms))
                    _tareas.add(tarea)
                    tarea.add_done_callback(_tareas.discard)
                else:
                    await _entregar(c, base, 0)
    return None
