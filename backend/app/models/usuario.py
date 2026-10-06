from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import false as sa_false
from sqlalchemy import true as sa_true
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def ahora() -> datetime:
    """Fecha/hora UTC sin zona (SQLite no guarda tzinfo)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    # rol: "instructor" | "azul" | "rojo" | "observador"
    rol: Mapped[str] = mapped_column(String(20))
    # puesto dentro del bando (solo alumnos): mando | inteligencia | operaciones | logistica | planificacion
    puesto: Mapped[str] = mapped_column(String(20), default="mando", server_default="mando")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # False = solicitud de cuenta hecha desde la pantalla de acceso, a la espera de que un instructor la apruebe
    aprobado: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_true())
    # True = contrasena inicial o puesta por el instructor: debe cambiarla al entrar antes de usar el simulador
    debe_cambiar_clave: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Sesion(Base):
    __tablename__ = "sesiones"

    # Se guarda el SHA-256 del token: un volcado de la BD no permite suplantar sesiones.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    expira_en: Mapped[datetime] = mapped_column(DateTime)


class IntentoLogin(Base):
    """Intentos fallidos por usuario: el bloqueo sobrevive a reinicios y a varios procesos."""

    __tablename__ = "intentos_login"

    clave: Mapped[str] = mapped_column(String(50), primary_key=True)
    fallos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
