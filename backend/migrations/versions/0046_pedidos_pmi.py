"""Cóndor: pedidos de puntos medios de impacto (PMI) de Operaciones a Inteligencia sobre las pistas enemigas

Revision ID: 0046
Revises: 0045
"""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pedidos_pmi",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escenario_id", sa.Integer(), sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("base_id", sa.Integer(), sa.ForeignKey("unidades.id"), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False, server_default="pedido"),
        sa.Column("pedido_por", sa.String(80), nullable=False, server_default=""),
        sa.Column("entregado_por", sa.String(80), nullable=False, server_default=""),
        sa.Column("puntos_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("pista_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("nota", sa.String(300), nullable=False, server_default=""),
        sa.Column("turno", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pedido_seg", sa.Float(), nullable=True),
        sa.Column("entregado_seg", sa.Float(), nullable=True),
    )
    op.create_index("ix_pedidos_pmi_escenario_id", "pedidos_pmi", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_pedidos_pmi_escenario_id", table_name="pedidos_pmi")
    op.drop_table("pedidos_pmi")
