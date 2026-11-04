from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GastoArma(Base):
    """Un disparo o una siembra que gasto armas reales (engine/gastos.py): para el informe de perdidas y gastos."""

    __tablename__ = "gastos_armas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))
    unidad_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id"), nullable=True)
    tipo: Mapped[str] = mapped_column(String(30))  # grupo del informe: "Misiles de crucero", "Torpedos"...
    arma: Mapped[str] = mapped_column(String(80))
    cantidad: Mapped[int] = mapped_column(Integer, default=1)
    turno: Mapped[int] = mapped_column(Integer, default=1)
    sim_segundos: Mapped[float | None] = mapped_column(Float, nullable=True)
