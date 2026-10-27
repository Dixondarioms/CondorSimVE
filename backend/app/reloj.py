"""Reloj del Cóndor: cada segundo avanza los escenarios en marcha y difunde las posiciones.

Solo corre un escenario "activo" que alguien tiene abierto (una conexion WebSocket): sin nadie mirando, el tiempo no
pasa. Cada vuelta avanza `segundos reales x velocidad` simulados (engine/tiempo_real.py), confirma y envia a cada
conexion un mensaje liviano de posiciones; el estado completo se reenvia cuando algo cambio (una deteccion, un combate,
un aterrizaje...) a lo sumo cada ESTADO_MIN_S, y de todos modos cada ESTADO_MAX_S.

El paso del motor es sincronico y no cede el control entre que lee y guarda las unidades: las ordenes (que llegan por
endpoints async del mismo bucle de eventos) nunca se mezclan con un paso a medias.
"""

import asyncio
import logging
import time

from app.db import SessionLocal
from app.engine import tiempo_real
from app.models.escenario import Escenario
from app.ws_manager import manager

log = logging.getLogger("uvicorn.error")

TICK_S = 1.0
ESTADO_MIN_S = 2.0
ESTADO_MAX_S = 15.0
MAX_ATRASO_S = 5.0  # si el servidor se demoro (suspension, depurador), no se simula de golpe mas que esto

_ultimo_estado: dict[int, float] = {}
_pendiente: set[int] = set()


def marcar_cambios(escenario_id: int) -> None:
    """Pide reenviar el estado completo del escenario en la proxima vuelta."""
    _pendiente.add(escenario_id)


async def vuelta(db, real_s: float) -> list[int]:
    """Una vuelta del reloj: avanza y difunde cada escenario en marcha con conexiones. Devuelve los avanzados."""
    avanzados = []
    ids = [eid for eid in manager.escenarios_con_conexiones()]
    if not ids:
        return avanzados
    for esc in db.query(Escenario).filter(Escenario.id.in_(ids)):
        if esc.estado == "activo" and not esc.archivado:
            informe = tiempo_real.paso(db, esc, real_s * max(1, esc.velocidad or 1))
            db.commit()
            avanzados.append(esc.id)
            if informe.cambios:
                _pendiente.add(esc.id)
        await manager.difundir_posiciones(db, esc)
        ahora = time.monotonic()
        ultimo = _ultimo_estado.get(esc.id, 0.0)
        if (esc.id in _pendiente and ahora - ultimo >= ESTADO_MIN_S) or (
                esc.estado == "activo" and ahora - ultimo >= ESTADO_MAX_S):
            _pendiente.discard(esc.id)
            _ultimo_estado[esc.id] = ahora
            await manager.difundir_estado(db, esc)
    return avanzados


async def correr(intervalo: float = TICK_S) -> None:
    """Bucle de fondo del reloj."""
    antes = time.monotonic()
    while True:
        await asyncio.sleep(intervalo)
        ahora = time.monotonic()
        real = min(ahora - antes, MAX_ATRASO_S)
        antes = ahora
        try:
            with SessionLocal() as db:
                await vuelta(db, real)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Error en el reloj de tiempo real")
