from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ProblemaMilitar(Base):
    """Problema Militar Operativo de un bando (TIEM): situacion, mision del escalon superior, idea general de la
    operacion conjunta, mision del componente, medios, area de operaciones y limitaciones. Lo redacta el instructor o
    lo genera el simulador a partir del escenario (ver engine/pmo.py); cada bando ve solo el suyo."""

    __tablename__ = "problemas_militares"
    __table_args__ = (UniqueConstraint("escenario_id", "bando"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))
    # campos del documento como JSON (ver engine/pmo.CAMPOS)
    contenido_json: Mapped[str] = mapped_column(Text, default="{}")
    # "instructor" (redactado o corregido a mano) | "automatico" (generado por el simulador)
    origen: Mapped[str] = mapped_column(String(12), default="instructor")
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora, onupdate=_ahora)
