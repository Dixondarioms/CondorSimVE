"""Identidad nacional de cada bando (Venezuela y sus vecinos)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("nacion_azul", sa.String(20), nullable=False, server_default="venezuela"))
        b.add_column(sa.Column("nacion_rojo", sa.String(20), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.drop_column("nacion_rojo")
        b.drop_column("nacion_azul")
