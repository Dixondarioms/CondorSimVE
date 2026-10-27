import json

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.usuario import Usuario


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

    # estado: "pendiente" | "en_ejecucion" (la unidad la esta cumpliendo) | "resuelta" | "rechazada" | "cancelada"
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    # segundo simulado en que se emitio (tiempo real)
    emitida_seg: Mapped[float | None] = mapped_column(Float, nullable=True)
    # orden demorada por las comunicaciones: segundo simulado en que llega a la unidad (queda "pendiente" hasta entonces)
    llega_seg: Mapped[float | None] = mapped_column(Float, nullable=True)
    resultado: Mapped[str] = mapped_column(Text, default="")

    # quien la emitio y el puesto que ocupaba en ese momento (mando | inteligencia | operaciones | logistica |
    # planificacion). Vacios en las ordenes automaticas del motor (intercepciones, fuego automatico) y en las
    # anteriores a la migracion 0018.
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    autor_puesto: Mapped[str | None] = mapped_column(String(20), nullable=True)
    autor_usuario: Mapped[Usuario | None] = relationship(Usuario, lazy="joined")

    @property
    def autor(self) -> str:
        """Nombre de usuario del autor ('' si no quedo registrado)."""
        return self.autor_usuario.username if self.autor_usuario is not None else ""
