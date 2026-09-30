"""Buques, portaaviones y misiles de crucero: blanco de cada salva de misiles en vuelo

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("blanco_id", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("blanco_id")
