"""Resolucion de turnos y vigilancia de plazos (compartido por la API y el temporizador)."""

import asyncio
import logging

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.engine import clock
from app.models.escenario import Escenario
from app.models.usuario import ahora
from app.ws_manager import manager

log = logging.getLogger("uvicorn.error")


async def resolver_y_difundir(db: Session, escenario: Escenario) -> None:
    clock.avanzar_turno(db, escenario, turno_esperado=escenario.turno_actual)
    await manager.difundir_estado(db, escenario)


async def resolver_vencidos(db: Session) -> list[int]:
    """Resuelve los turnos cuyo tiempo de decision se agoto; devuelve los escenarios resueltos."""
    vencidos = (
        db.query(Escenario)
        .filter(
            Escenario.estado == "activo",
            Escenario.fase == "decision",
            Escenario.decision_termina_en.is_not(None),
            Escenario.decision_termina_en <= ahora(),
        )
        .all()
    )
    for esc in vencidos:
        log.info("Escenario %s: se agoto el tiempo de decision, resolviendo turno.", esc.id)
        await resolver_y_difundir(db, esc)
    return [e.id for e in vencidos]


async def vigilar_plazos(intervalo: float = 1.0) -> None:
    """Bucle de fondo que aplica `resolver_vencidos` cada `intervalo` segundos."""
    while True:
        try:
            with SessionLocal() as db:
                await resolver_vencidos(db)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Error al vigilar los plazos de decision")
        await asyncio.sleep(intervalo)
