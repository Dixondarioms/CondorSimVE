from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Mision(Base):
    """Mision aerea planificada: rol + ruta de puntos para un grupo aereo existente o para un grupo que despegara
    de una base en un turno programado (ver engine/misiones.py)."""

    __tablename__ = "misiones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))
    rol: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(60), default="")
    # programada | en_curso | cumplida | abortada | fallida | cancelada
    estado: Mapped[str] = mapped_column(String(20), default="programada")
    unidad_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # grupo que la vuela (sin FK: puede eliminarse)
    base_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # base de despegue si el grupo aun no existe
    modelo: Mapped[str] = mapped_column(String(30), default="")
    aeronaves: Mapped[int] = mapped_column(Integer, default=0)
    turno_despegue: Mapped[int] = mapped_column(Integer)
    creada_turno: Mapped[int] = mapped_column(Integer)
    puntos_json: Mapped[str] = mapped_column(Text, default="[]")
    plan_json: Mapped[str] = mapped_column(Text, default="{}")  # estimacion de hora y combustible al planificarla
    indice: Mapped[int] = mapped_column(Integer, default=0)  # punto de la ruta hacia el que va
    espera: Mapped[int] = mapped_column(Integer, default=-1)  # turnos de orbita que le quedan (-1: no esta orbitando)
    resultado: Mapped[str] = mapped_column(String(300), default="")
    autor: Mapped[str] = mapped_column(String(50), default="")  # nombre de usuario de quien la planifico
    # id del autor y puesto que ocupaba al planificarla (nulos en las misiones anteriores a la migracion 0018)
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    autor_puesto: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # datos de la OTA (engine/ota.py): paquete, funcion (CM/ACM), alerta, armamento, IFF, TOT pedido, PDI
    ota_json: Mapped[str | None] = mapped_column(Text, nullable=True)
