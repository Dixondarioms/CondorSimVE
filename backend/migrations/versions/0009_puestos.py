"""Puesto por funcion de cada alumno dentro de su bando (Estado Mayor, A2, A3, A4, A5)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as b:
        b.add_column(sa.Column("puesto", sa.String(20), nullable=False, server_default="mando"))


def downgrade() -> None:
    with op.batch_alter_table("usuarios") as b:
        b.drop_column("puesto")
