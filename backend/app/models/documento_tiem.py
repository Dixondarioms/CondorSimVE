from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DocumentoTiem(Base):
    """Documento del TIEM de un bando (analisis de la mision, concepto, guia, formas de accion; ver engine/tiem.py)."""

    __tablename__ = "documentos_tiem"
    __table_args__ = (UniqueConstraint("escenario_id", "bando", "tipo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    escenario_id: Mapped[int] = mapped_column(ForeignKey("escenarios.id"), index=True)
    bando: Mapped[str] = mapped_column(String(10))
    tipo: Mapped[str] = mapped_column(String(30))
    contenido_json: Mapped[str] = mapped_column(Text, default="{}")
    # borrador | presentado | aprobado | devuelto (ver engine/tiem.ESTADOS)
    estado: Mapped[str] = mapped_column(String(12), default="borrador")
    observaciones: Mapped[str] = mapped_column(Text, default="")  # del instructor al revisarlo
    editado_por: Mapped[str] = mapped_column(String(50), default="")
    editado_puesto: Mapped[str] = mapped_column(String(20), default="")
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora, onupdate=_ahora)
    presentado_turno: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revisado_turno: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ArchivoTiem(Base):
    """Archivo (Word, PDF) adjunto a un documento del TIEM; se guarda en la base para viajar con sus respaldos."""

    __tablename__ = "archivos_tiem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos_tiem.id"), index=True)
    nombre: Mapped[str] = mapped_column(String(200))
    tipo_mime: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    tamano: Mapped[int] = mapped_column(Integer, default=0)
    datos: Mapped[bytes] = mapped_column(LargeBinary)
    subido_por: Mapped[str] = mapped_column(String(50), default="")
    subido_en: Mapped[datetime] = mapped_column(DateTime, default=_ahora)
