"""Cóndor: areas de referencia y zonas (patrulla, exclusion y no vuelo) del director y de cada bando

Revision ID: 0047
Revises: 0046
"""

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zonas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escenario_id", sa.Integer(), sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("nombre", sa.String(60), nullable=False, server_default=""),
        sa.Column("puntos_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("armas", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("autor", sa.String(50), nullable=False, server_default=""),
        sa.Column("creada_seg", sa.Float(), nullable=True),
    )
    op.create_index("ix_zonas_escenario_id", "zonas", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_zonas_escenario_id", table_name="zonas")
    op.drop_table("zonas")
