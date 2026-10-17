from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Objetivo(Base):
    """Objetivo del ejercicio de un bando: ocupar una zona, destruir o neutralizar una unidad enemiga, proteger una
    propia, o un efecto que agrupa a otros objetivos (cadena de objetivos del TIEM: ulterior, asignado, material)."""

    __tablename__ = "objetivos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))  # el bando que debe lograrlo
    # tipo: "ocupar" | "destruir" | "neutralizar" | "proteger" | "efecto"
    tipo: Mapped[str] = mapped_column(String(12))
    nombre: Mapped[str] = mapped_column(String(120))
    puntos: Mapped[int] = mapped_column(Integer, default=10)

    # ocupar: zona circular que hay que mantener `turnos_requeridos` turnos seguidos (`progreso` cuenta los logrados)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    radio_km: Mapped[float] = mapped_column(Float, default=5.0)
    turnos_requeridos: Mapped[int] = mapped_column(Integer, default=1)
    progreso: Mapped[int] = mapped_column(Integer, default=0)

    # destruir / proteger: la unidad en cuestion; proteger se cumple al llegar `hasta_turno` con la unidad viva
    unidad_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id"), nullable=True)
    hasta_turno: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # cadena de objetivos (TIEM): nivel "ulterior" (del escalon superior), "asignado" (al componente) o "material"
    # (lo que se ataca o protege en el terreno); `padre_id` es el objetivo al que contribuye
    nivel: Mapped[str] = mapped_column(String(12), default="material", server_default="material")
    padre_id: Mapped[int | None] = mapped_column(ForeignKey("objetivos.id"), nullable=True)
    # efecto deseado e indicador con que se mide (texto libre: "Degradar la defensa aerea del ENO al 50 %")
    efecto: Mapped[str] = mapped_column(String(300), default="", server_default="")
    indicador: Mapped[str] = mapped_column(String(300), default="", server_default="")
    # neutralizar: fuerza (%) a la que debe quedar la unidad; efecto: % de los objetivos hijos que deben cumplirse
    umbral: Mapped[float | None] = mapped_column(Float, nullable=True)

    # estado: "pendiente" | "cumplido" | "fallido"
    estado: Mapped[str] = mapped_column(String(10), default="pendiente")
    turno_resuelto: Mapped[int | None] = mapped_column(Integer, nullable=True)
