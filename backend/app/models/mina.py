from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CampoMinas(Base):
    """Campo de minas navales sembrado por un bando (engine/minas.py): centro, radio y la fraccion de minas que le
    queda; lo conoce quien lo sembro y los bandos que lo descubrieron (`conocido_por`)."""

    __tablename__ = "campos_minas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))
    unidad_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id"), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    radio_km: Mapped[float] = mapped_column(Float)
    densidad: Mapped[float] = mapped_column(Float, default=1.0)
    conocido_por: Mapped[str] = mapped_column(Text, default="[]")
    creado_seg: Mapped[float | None] = mapped_column(Float, nullable=True)
