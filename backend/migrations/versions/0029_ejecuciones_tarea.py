"""TIEM etapa 4: ejecucion de las tareas del Plan de Operaciones (tarea -> orden)

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ejecuciones_tarea",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False, index=True),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("tarea_id", sa.String(16), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
        sa.Column("orden_id", sa.Integer, nullable=True),
        sa.Column("motivo", sa.String(300), nullable=False),
        sa.Column("emitida_por", sa.String(50), nullable=False),
        sa.UniqueConstraint("escenario_id", "bando", "tarea_id"),
    )


def downgrade() -> None:
    op.drop_table("ejecuciones_tarea")
