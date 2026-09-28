from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Asignacion(Base):
    """Un alumno/observador solo accede a los escenarios que el instructor le asigna."""

    __tablename__ = "asignaciones"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), primary_key=True)
