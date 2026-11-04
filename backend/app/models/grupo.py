from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GrupoTarea(Base):
    """Grupo de tarea de un bando (app/routers/grupos.py): unidades propias bajo un nombre, que se eligen juntas para
    darles una orden en formacion."""

    __tablename__ = "grupos_tarea"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))
    nombre: Mapped[str] = mapped_column(String(60))
    unidades_json: Mapped[str] = mapped_column(Text, default="[]")  # ids de las unidades del grupo
