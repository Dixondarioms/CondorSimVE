from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ZonaClima(Base):
    """Zona meteorologica (frente de nubes, lluvia o tormenta) que el instructor coloca sobre el mapa. Se desplaza
    cada turno segun su deriva y caduca en `hasta_turno` (None = hasta que la quite). Ver engine/clima.py."""

    __tablename__ = "zonas_clima"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(60), default="")
    tipo: Mapped[str] = mapped_column(String(20))  # nublado | lluvia | tormenta
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    radio_km: Mapped[float] = mapped_column(Float)
    deriva_rumbo: Mapped[float] = mapped_column(Float, default=0.0)  # grados desde el norte
    deriva_kmh: Mapped[float] = mapped_column(Float, default=0.0)  # desplazamiento por turno (1 h)
    hasta_turno: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creada_turno: Mapped[int] = mapped_column(Integer, default=1)
