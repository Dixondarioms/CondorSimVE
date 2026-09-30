from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Unidad(Base):
    __tablename__ = "unidades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"))

    nombre: Mapped[str] = mapped_column(String(120))
    # bando: "azul" (propio) | "rojo" (oponente)
    bando: Mapped[str] = mapped_column(String(10))
    # tipo: "terrestre" | "aerea" | "naval" | "base"
    tipo: Mapped[str] = mapped_column(String(20))
    # clase: ver engine/catalogo.py (infanteria, caza, fragata, deposito, ...)
    clase: Mapped[str] = mapped_column(String(30), default="")
    echelon: Mapped[str] = mapped_column(String(40), default="")
    # modelo de aeronave (ver engine/catalogo.py: f16, su30) y aeronaves que forman el grupo aereo
    modelo: Mapped[str] = mapped_column(String(30), default="")
    aeronaves: Mapped[int] = mapped_column(Integer, default=1)

    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    fuerza: Mapped[float] = mapped_column(Float, default=100.0)
    velocidad_kmh: Mapped[float] = mapped_column(Float, default=30.0)
    alcance_km: Mapped[float] = mapped_column(Float, default=10.0)
    # radio en el que la unidad detecta unidades enemigas (niebla de guerra)
    deteccion_km: Mapped[float] = mapped_column(Float, default=8.0)

    # logistica: porcentaje de combustible y municion, y distancia con tanque lleno
    combustible: Mapped[float] = mapped_column(Float, default=100.0)
    municion: Mapped[float] = mapped_column(Float, default=100.0)
    autonomia_km: Mapped[float] = mapped_column(Float, default=300.0)

    # suministros que lleva un convoy (%), y contadores de fidelidad de plataforma
    carga: Mapped[float] = mapped_column(Float, default=0.0)
    recarga_restante: Mapped[int] = mapped_column(Integer, default=0)  # turnos sin poder disparar
    despliegue_restante: Mapped[int] = mapped_column(Integer, default=0)  # turnos quieta para poder disparar

    # ciclo de vuelo: aeronave estacionada en una base (con turnos de espera para reabastecer y rearmar) y
    # mision persistente ("patrulla" sobre un punto)
    en_tierra: Mapped[bool] = mapped_column(Boolean, default=False)
    base_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    espera_restante: Mapped[int] = mapped_column(Integer, default=0)
    mision: Mapped[str] = mapped_column(String(20), default="")
    mision_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    mision_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    # misil de crucero en vuelo: unidad a la que se dirige (mision "impacto"; mision_lat/lon = ultimo punto conocido)
    blanco_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # sensores y defensa aerea: radar emitiendo (control de emisiones) y fuego automatico de la antiaerea
    emitiendo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    fuego_libre: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # bases: existencias de combustible y municion (puntos: 100 = llenar una unidad; ver engine/logistica.py)
    stock_combustible: Mapped[float] = mapped_column(Float, default=1000.0, server_default="1000")
    stock_municion: Mapped[float] = mapped_column(Float, default=1000.0, server_default="1000")

    # codigo de simbolo (SIDC) para milsymbol.js
    sidc: Mapped[str] = mapped_column(String(20), default="")

    # estado: "activa" | "destruida" | "replegada"
    estado: Mapped[str] = mapped_column(String(20), default="activa")
