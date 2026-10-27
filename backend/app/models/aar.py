from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Instantanea(Base):
    """Estado completo del escenario al terminar el turno `turno` (0 = despliegue inicial)."""

    __tablename__ = "instantaneas"
    __table_args__ = (UniqueConstraint("escenario_id", "turno"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    turno: Mapped[int] = mapped_column(Integer)
    clima: Mapped[str] = mapped_column(String(20), default="despejado")
    datos_json: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora)


class Fotograma(Base):
    """Posicion, fuerza y estado de cada unidad en un instante del ejercicio en tiempo real (cada pocos minutos
    simulados), para la repeticion: [[id, lat, lon, fuerza, estado], ...]. El nombre, el bando y el simbolo se toman
    de la unidad (no cambian)."""

    __tablename__ = "fotogramas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    sim_segundos: Mapped[float] = mapped_column(Float)
    turno: Mapped[int] = mapped_column(Integer)
    clima: Mapped[str] = mapped_column(String(20), default="despejado")
    datos_json: Mapped[str] = mapped_column(Text)


class Combate(Base):
    """Registro estructurado de cada enfrentamiento resuelto (para el informe)."""

    __tablename__ = "combates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    turno: Mapped[int] = mapped_column(Integer)
    orden_id: Mapped[int | None] = mapped_column(ForeignKey("ordenes.id"), nullable=True)
    atacante_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    defensor_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    atacante_nombre: Mapped[str] = mapped_column(String(120))
    defensor_nombre: Mapped[str] = mapped_column(String(120))
    atacante_bando: Mapped[str] = mapped_column(String(10))
    defensor_bando: Mapped[str] = mapped_column(String(10))
    ratio: Mapped[float] = mapped_column(Float)
    fuerza_ini_atacante: Mapped[float] = mapped_column(Float)
    fuerza_ini_defensor: Mapped[float] = mapped_column(Float)
    perdida_atacante: Mapped[float] = mapped_column(Float)
    perdida_defensor: Mapped[float] = mapped_column(Float)
    terreno: Mapped[str] = mapped_column(String(20), default="llano")
    efectos: Mapped[str] = mapped_column(Text, default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    sim_segundos: Mapped[float | None] = mapped_column(Float, nullable=True)  # tiempo real: cuando ocurrio


class RegistroLogistico(Base):
    """Cada variacion de combustible, municion o carga de una unidad durante la resolucion de un
    turno, con su causa. Permite cruzar la logistica con los combates en la linea de tiempo."""

    __tablename__ = "registro_logistico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    turno: Mapped[int] = mapped_column(Integer)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    unidad_nombre: Mapped[str] = mapped_column(String(120))
    bando: Mapped[str] = mapped_column(String(10))
    variable: Mapped[str] = mapped_column(String(12))  # "combustible" | "municion" | "carga"
    antes: Mapped[float] = mapped_column(Float)
    despues: Mapped[float] = mapped_column(Float)
    # causa: movimiento | combate | apoyo | reabastecimiento | convoy | construccion | perdida
    causa: Mapped[str] = mapped_column(String(20))
    orden_id: Mapped[int | None] = mapped_column(ForeignKey("ordenes.id"), nullable=True)
