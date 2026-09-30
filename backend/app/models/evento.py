from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Evento(Base):
    """Evento inyectado por el instructor/director de ejercicio (umpire)."""

    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"))
    turno: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(40), default="general")
    # a quien va dirigido: "todos" | "azul" | "rojo"
    bando_destino: Mapped[str] = mapped_column(String(10), default="todos")
    descripcion: Mapped[str] = mapped_column(Text)
    # informes inyectados con posicion (p. ej. "inteligencia"): se marcan en el mapa hasta `hasta_turno`
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    hasta_turno: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuente: Mapped[str] = mapped_column(String(60), default="", server_default="")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
