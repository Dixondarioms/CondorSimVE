"""Herramientas de direccion: interruptores del motor por escenario e informes inyectados con posicion

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("niebla", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("logistica", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("efectos_clima", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("fuego_automatico", sa.Boolean, nullable=False, server_default=sa.true()))
    with op.batch_alter_table("eventos") as b:
        b.add_column(sa.Column("lat", sa.Float, nullable=True))
        b.add_column(sa.Column("lon", sa.Float, nullable=True))
        b.add_column(sa.Column("hasta_turno", sa.Integer, nullable=True))
        b.add_column(sa.Column("fuente", sa.String(60), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("eventos") as b:
        b.drop_column("fuente")
        b.drop_column("hasta_turno")
        b.drop_column("lon")
        b.drop_column("lat")
    with op.batch_alter_table("escenarios") as b:
        b.drop_column("fuego_automatico")
        b.drop_column("efectos_clima")
        b.drop_column("logistica")
        b.drop_column("niebla")
