from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Mensaje(Base):
    """Mensaje del chat tactico. La perdida y la demora de la entrega por interferencia se
    deciden al enviarlo y se guardan por bando, para que el historial sea coherente."""

    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    # canal: "azul" | "rojo" (red del bando) | "todos" (difusion) | "mando" (alumno -> instructor)
    canal: Mapped[str] = mapped_column(String(10))
    remitente_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    remitente_nombre: Mapped[str] = mapped_column(String(50))
    remitente_rol: Mapped[str] = mapped_column(String(20))
    texto: Mapped[str] = mapped_column(Text)
    turno: Mapped[int] = mapped_column(Integer, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora)
    demora_azul_ms: Mapped[int] = mapped_column(Integer, default=0)
    demora_rojo_ms: Mapped[int] = mapped_column(Integer, default=0)
    perdido_azul: Mapped[bool] = mapped_column(Boolean, default=False)
    perdido_rojo: Mapped[bool] = mapped_column(Boolean, default=False)
