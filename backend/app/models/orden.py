import json

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Orden(Base):
    __tablename__ = "ordenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"))
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))

    # tipo: "mover" | "atacar" | "apoyar"
    tipo: Mapped[str] = mapped_column(String(20))

    # para ordenes de movimiento: lista de [lat, lon] en JSON
    waypoints_json: Mapped[str] = mapped_column(Text, default="[]")

    # para ordenes de ataque/apoyo: unidad objetivo
    objetivo_unidad_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidades.id"), nullable=True
    )

    # construir: "puente" | "vado"; despegar: JSON {"modelo", "aeronaves", "indicativo"}
    detalle: Mapped[str] = mapped_column(String(160), default="")

    turno_emitida: Mapped[int] = mapped_column(Integer)

    @property
    def waypoints(self) -> list:
        return json.loads(self.waypoints_json or "[]")

    # estado: "pendiente" | "resuelta" | "rechazada"
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    resultado: Mapped[str] = mapped_column(Text, default="")
