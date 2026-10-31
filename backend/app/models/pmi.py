from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PedidoPmi(Base):
    """Pedido de Operaciones (A-3) a Inteligencia (A-2) de los puntos medios de impacto (PMI) sobre la pista de una base
    aerea enemiga, y los puntos que A-2 entrega (engine/pmi.py). Con los PMI entregados, el ataque a la pista de esa
    base hace todo su daño; sin ellos, las bombas caen dispersas."""

    __tablename__ = "pedidos_pmi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))  # el bando que pide (y ataca)
    base_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))  # la base aerea enemiga
    estado: Mapped[str] = mapped_column(String(12), default="pedido")  # pedido | entregado | cancelado
    pedido_por: Mapped[str] = mapped_column(String(80), default="")
    entregado_por: Mapped[str] = mapped_column(String(80), default="")
    puntos_json: Mapped[str] = mapped_column(Text, default="[]")  # [{"id": "PMI-01", "lat", "lon", "nota"}]
    pista_json: Mapped[str] = mapped_column(Text, default="{}")  # la pista sobre la que se calcularon
    nota: Mapped[str] = mapped_column(String(300), default="")
    turno: Mapped[int] = mapped_column(Integer, default=1)
    pedido_seg: Mapped[float | None] = mapped_column(Float, nullable=True)
    entregado_seg: Mapped[float | None] = mapped_column(Float, nullable=True)
