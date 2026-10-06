"""Solicitudes de cuenta con aprobacion del instructor y cambio de contrasena obligatorio al primer acceso

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Las cuentas existentes quedan aprobadas y sin obligacion de cambiar la contrasena.
    with op.batch_alter_table("usuarios") as b:
        b.add_column(sa.Column("aprobado", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("debe_cambiar_clave", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("usuarios") as b:
        b.drop_column("debe_cambiar_clave")
        b.drop_column("aprobado")
