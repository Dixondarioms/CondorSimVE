import secrets
from datetime import datetime, timezone

from sqlalchemy import true, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Escenario(Base):
    __tablename__ = "escenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200))
    turno_actual: Mapped[int] = mapped_column(Integer, default=1)
    # fase: "decision" (los alumnos emiten ordenes) | "resolucion" (el motor resuelve)
    fase: Mapped[str] = mapped_column(String(20), default="decision")
    # estado: "activo" | "pausado" | "finalizado"
    estado: Mapped[str] = mapped_column(String(20), default="activo")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora)

    # clima: "despejado" | "nublado" | "lluvia" | "tormenta"
    clima: Mapped[str] = mapped_column(String(20), default="despejado")
    # azar: los combates incluyen variacion aleatoria reproducible (semilla + turno + unidades)
    azar: Mapped[bool] = mapped_column(Boolean, default=False)
    semilla: Mapped[int] = mapped_column(Integer, default=lambda: secrets.randbelow(2**31))

    # mecanica de turnos
    auto_resolver: Mapped[bool] = mapped_column(Boolean, default=False)
    limite_decision_seg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_termina_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    listo_azul: Mapped[bool] = mapped_column(Boolean, default=False)
    listo_rojo: Mapped[bool] = mapped_column(Boolean, default=False)

    archivado: Mapped[bool] = mapped_column(Boolean, default=False)

    # comunicaciones simuladas (chat): demora base, variacion y probabilidad de perdida por interferencia
    com_latencia_ms: Mapped[int] = mapped_column(Integer, default=0)
    com_jitter_ms: Mapped[int] = mapped_column(Integer, default=0)
    com_perdida_pct: Mapped[int] = mapped_column(Integer, default=0)

    # hora simulada del turno 1, en minutos desde medianoche (cada turno dura 1 h)
    hora_inicio_min: Mapped[int] = mapped_column(Integer, default=360)

    # interruptores del motor (herramientas de direccion): niebla de guerra, consumo/reabastecimiento, efectos del
    # clima y fuego automatico (patrullas y antiaerea). Apagarlos simplifica el ejercicio para fines didacticos.
    niebla: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    logistica: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    efectos_clima: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    fuego_automatico: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    # identidad nacional de cada bando (ver engine/naciones.py); "" = sin especificar (se muestra "Azul"/"Rojo")
    nacion_azul: Mapped[str] = mapped_column(String(20), default="venezuela")
    nacion_rojo: Mapped[str] = mapped_column(String(20), default="")
