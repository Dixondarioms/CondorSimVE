"""Cóndor: ejercicio de practica (el alumno maneja el reloj)

Revision ID: 0060
Revises: 0059
"""

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("practica", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("practica")
