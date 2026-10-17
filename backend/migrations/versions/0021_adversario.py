"""Adversario automatico: el simulador conduce el bando azul y/o el rojo

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("ia_azul", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("ia_rojo", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.drop_column("ia_rojo")
        b.drop_column("ia_azul")
