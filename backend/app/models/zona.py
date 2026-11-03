from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Zona(Base):
    """Area de referencia dibujada en el mapa (engine/zonas.py): area de patrulla, zona de exclusion o zona de no
    vuelo, de un bando o del director ("todos")."""

    __tablename__ = "zonas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))  # "azul" | "rojo" | "todos" (del director)
    tipo: Mapped[str] = mapped_column(String(12))  # "patrulla" | "exclusion" | "no_vuelo"
    nombre: Mapped[str] = mapped_column(String(60), default="")
    puntos_json: Mapped[str] = mapped_column(Text, default="[]")  # vertices [[lat, lon], ...]
    # las armas propias tiran contra quien entre (solo exclusion y no vuelo)
    armas: Mapped[bool] = mapped_column(Boolean, default=False)
    autor: Mapped[str] = mapped_column(String(50), default="")
    creada_seg: Mapped[float | None] = mapped_column(Float, nullable=True)
