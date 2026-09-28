from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Obra(Base):
    """Puente o vado tendido por ingenieros sobre un rio. Es temporal: deja de existir
    despues de `expira_turno`. Lo puede usar cualquier bando que llegue hasta el."""

    __tablename__ = "obras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    unidad_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id"), nullable=True)
    bando: Mapped[str] = mapped_column(String(10))  # quien la construyo
    tipo: Mapped[str] = mapped_column(String(10))  # "puente" | "vado"
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    radio_km: Mapped[float] = mapped_column(Float, default=0.8)
    creada_turno: Mapped[int] = mapped_column(Integer)
    expira_turno: Mapped[int] = mapped_column(Integer)  # ultimo turno en que sigue en pie
