"""Ciclo de vuelo: aeronaves en tierra, espera de reabastecimiento y misiones de patrulla

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("en_tierra", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("base_id", sa.Integer, nullable=True))
        b.add_column(sa.Column("espera_restante", sa.Integer, nullable=False, server_default="0"))
        b.add_column(sa.Column("mision", sa.String(20), nullable=False, server_default=""))
        b.add_column(sa.Column("mision_lat", sa.Float, nullable=True))
        b.add_column(sa.Column("mision_lon", sa.Float, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        for columna in ("mision_lon", "mision_lat", "mision", "espera_restante", "base_id", "en_tierra"):
            b.drop_column(columna)
