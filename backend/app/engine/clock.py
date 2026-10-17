from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.engine import aar, contactos, objetivos, orders
from app.engine import inteligencia
from app.models.escenario import Escenario
from app.models.orden import Orden


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def programar_limite(escenario: Escenario) -> None:
    """(Re)inicia la cuenta regresiva de la fase de decision, si hay limite de tiempo."""
    if escenario.limite_decision_seg and escenario.estado == "activo" and escenario.fase == "decision":
        escenario.decision_termina_en = _ahora() + timedelta(seconds=escenario.limite_decision_seg)
    else:
        escenario.decision_termina_en = None


def avanzar_turno(
    db: Session, escenario: Escenario, terreno=None, turno_esperado: int | None = None
) -> list[Orden] | None:
    """Cierra la fase de decision, resuelve las ordenes pendientes y abre el
    siguiente turno. Guarda la instantanea para el informe posterior.

    Con `turno_esperado` se bloquea la fila del escenario (SELECT ... FOR UPDATE en PostgreSQL) y solo se
    resuelve si sigue en ese turno: asi dos peticiones simultaneas (el instructor y el temporizador, o
    dos procesos) no resuelven el mismo turno dos veces. Devuelve None si cedio el turno a otro proceso."""
    if turno_esperado is not None:
        db.query(Escenario).filter(Escenario.id == escenario.id).populate_existing().with_for_update().one()
        if (escenario.turno_actual != turno_esperado or escenario.estado != "activo"
                or escenario.fase != "decision"):
            db.rollback()  # libera el bloqueo: otro proceso ya resolvio este turno
            return None
    aar.asegurar_linea_base(db, escenario)
    escenario.fase = "resolucion"
    db.flush()

    ordenes_procesadas = orders.procesar_ordenes(db, escenario, terreno)
    db.flush()

    objetivos.evaluar(db, escenario)
    contactos.actualizar_contactos(db, escenario, terreno)
    inteligencia.procesar_turno(db, escenario)
    aar.guardar_instantanea(db, escenario, escenario.turno_actual)

    escenario.turno_actual += 1
    escenario.fase = "decision"
    escenario.listo_azul = escenario.listo_rojo = False
    programar_limite(escenario)
    if escenario.ia_azul or escenario.ia_rojo:
        from app import adversario  # importacion tardia: el adversario usa la validacion de las ordenes (routers)
        adversario.jugar_turno(db, escenario, terreno)
    db.commit()
    db.refresh(escenario)
    return ordenes_procesadas


def marcar_listo(db: Session, escenario: Escenario, bando: str, listo: bool) -> bool:
    """Marca al bando como listo (o no). Devuelve True si ambos estan listos."""
    setattr(escenario, f"listo_{bando}", listo)
    db.commit()
    return escenario.listo_azul and escenario.listo_rojo


def pausar(db: Session, escenario: Escenario) -> None:
    escenario.estado = "pausado"
    escenario.decision_termina_en = None
    db.commit()


def reanudar(db: Session, escenario: Escenario) -> None:
    escenario.estado = "activo"
    programar_limite(escenario)
    db.commit()


def finalizar(db: Session, escenario: Escenario) -> None:
    aar.asegurar_linea_base(db, escenario)
    aar.guardar_instantanea(db, escenario, escenario.turno_actual - 1)
    escenario.estado = "finalizado"
    escenario.decision_termina_en = None
    db.commit()
