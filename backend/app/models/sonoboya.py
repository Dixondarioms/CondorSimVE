from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Sonoboya(Base):
    """Sonoboya sembrada por un avion de patrulla maritima: escucha submarinos a su alrededor hasta `hasta_seg`
    (engine/asw.py)."""

    __tablename__ = "sonoboyas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))
    unidad_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id"), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    radio_km: Mapped[float] = mapped_column(Float)
    desde_seg: Mapped[float] = mapped_column(Float)
    hasta_seg: Mapped[float] = mapped_column(Float)
