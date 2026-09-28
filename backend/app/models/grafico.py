from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Grafico(Base):
    """Grafico de control trazado en el mapa (linea de fase, eje de avance, zona de reunion,
    punto de control), como geometria GeoJSON compartida con todo el bando."""

    __tablename__ = "graficos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))  # "azul" | "rojo" | "todos" (neutral, del instructor)
    tipo: Mapped[str] = mapped_column(String(20))
    etiqueta: Mapped[str] = mapped_column(String(60), default="")
    geojson: Mapped[str] = mapped_column(Text)  # geometria (GeoJSON) en JSON
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    autor_nombre: Mapped[str] = mapped_column(String(50), default="")
    turno: Mapped[int] = mapped_column(Integer, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora)
