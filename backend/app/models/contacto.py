from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Contacto(Base):
    """Ultima posicion conocida de una unidad enemiga para un bando (niebla de guerra)."""

    __tablename__ = "contactos"
    __table_args__ = (UniqueConstraint("escenario_id", "bando", "unidad_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))  # el bando que tiene el contacto
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    turno_visto: Mapped[int] = mapped_column(Integer)
    # Cóndor: etapa de clasificacion (desconocido | clasificado | identificado), puntos de seguimiento acumulados y
    # radio de la zona de incertidumbre de la posicion (engine/contactos_vivo.py)
    etapa: Mapped[str | None] = mapped_column(String(15), nullable=True)
    puntos: Mapped[float | None] = mapped_column(Float, nullable=True)
    incertidumbre_km: Mapped[float | None] = mapped_column(Float, nullable=True)
