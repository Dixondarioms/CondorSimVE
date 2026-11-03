"""Cóndor: campos de minas navales

Revision ID: 0053
Revises: 0052
"""

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campos_minas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escenario_id", sa.Integer(), sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("unidad_id", sa.Integer(), sa.ForeignKey("unidades.id"), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("radio_km", sa.Float(), nullable=False),
        sa.Column("densidad", sa.Float(), nullable=False, server_default="1"),
        sa.Column("conocido_por", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("creado_seg", sa.Float(), nullable=True),
    )
    op.create_index("ix_campos_minas_escenario_id", "campos_minas", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_campos_minas_escenario_id", table_name="campos_minas")
    op.drop_table("campos_minas")
