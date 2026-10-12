"""Comunicaciones que pesan en la operacion: porcentaje de ordenes que no llegan a tiempo

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("com_ordenes_pct", sa.Integer, nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.drop_column("com_ordenes_pct")
