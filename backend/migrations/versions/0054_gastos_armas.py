"""Cóndor: gastos de armas (informe de perdidas y gastos)

Revision ID: 0054
Revises: 0053
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gastos_armas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escenario_id", sa.Integer(), sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("unidad_id", sa.Integer(), sa.ForeignKey("unidades.id"), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("arma", sa.String(80), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("turno", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sim_segundos", sa.Float(), nullable=True),
    )
    op.create_index("ix_gastos_armas_escenario_id", "gastos_armas", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_gastos_armas_escenario_id", table_name="gastos_armas")
    op.drop_table("gastos_armas")
