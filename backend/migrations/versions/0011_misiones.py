"""Misiones aereas planificadas (rol + ruta de navegacion)

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "misiones",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(60), nullable=False, server_default=""),
        sa.Column("estado", sa.String(20), nullable=False, server_default="programada"),
        sa.Column("unidad_id", sa.Integer, nullable=True),
        sa.Column("base_id", sa.Integer, nullable=True),
        sa.Column("modelo", sa.String(30), nullable=False, server_default=""),
        sa.Column("aeronaves", sa.Integer, nullable=False, server_default="0"),
        sa.Column("turno_despegue", sa.Integer, nullable=False),
        sa.Column("creada_turno", sa.Integer, nullable=False),
        sa.Column("puntos_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("plan_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("indice", sa.Integer, nullable=False, server_default="0"),
        sa.Column("espera", sa.Integer, nullable=False, server_default="-1"),
        sa.Column("resultado", sa.String(300), nullable=False, server_default=""),
        sa.Column("autor", sa.String(50), nullable=False, server_default=""),
    )
    op.create_index("ix_misiones_escenario_id", "misiones", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_misiones_escenario_id", table_name="misiones")
    op.drop_table("misiones")
