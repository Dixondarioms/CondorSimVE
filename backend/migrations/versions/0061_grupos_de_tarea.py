"""Cóndor: grupos de tarea

Revision ID: 0061
Revises: 0060
"""

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grupos_tarea",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escenario_id", sa.Integer(), sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("unidades_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_grupos_tarea_escenario_id", "grupos_tarea", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_grupos_tarea_escenario_id", table_name="grupos_tarea")
    op.drop_table("grupos_tarea")
