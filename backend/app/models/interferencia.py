from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Interferencia(Base):
    """Zona de interferencia electronica emitida al resolver el turno `turno`. Rige ese turno y la planificacion
    del siguiente (ver engine/guerra_electronica.py); para mantenerla hay que volver a ordenar la interferencia."""

    __tablename__ = "interferencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    unidad_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # emisor (sin FK: puede eliminarse)
    bando: Mapped[str] = mapped_column(String(10))  # quien interfiere
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    radio_km: Mapped[float] = mapped_column(Float)
    turno: Mapped[int] = mapped_column(Integer)
