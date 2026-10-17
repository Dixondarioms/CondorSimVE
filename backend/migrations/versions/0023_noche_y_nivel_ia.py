"""Ciclo de dia y noche (deteccion segun la hora simulada) y nivel del adversario automatico

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("dia_noche", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("ia_nivel", sa.String(10), nullable=False, server_default="normal"))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.drop_column("ia_nivel")
        b.drop_column("dia_noche")
