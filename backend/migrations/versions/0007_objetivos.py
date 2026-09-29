"""Objetivos del ejercicio con puntaje

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "objetivos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("puntos", sa.Integer, nullable=False),
        sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lon", sa.Float, nullable=True),
        sa.Column("radio_km", sa.Float, nullable=False),
        sa.Column("turnos_requeridos", sa.Integer, nullable=False),
        sa.Column("progreso", sa.Integer, nullable=False),
        sa.Column("unidad_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=True),
        sa.Column("hasta_turno", sa.Integer, nullable=True),
        sa.Column("estado", sa.String(10), nullable=False),
        sa.Column("turno_resuelto", sa.Integer, nullable=True),
    )
    op.create_index("ix_objetivos_escenario_id", "objetivos", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_objetivos_escenario_id", table_name="objetivos")
    op.drop_table("objetivos")
