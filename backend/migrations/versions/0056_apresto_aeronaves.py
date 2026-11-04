"""Cóndor: apresto de las aeronaves en tierra (alerta 5, 15, 30, 60 min o mantenimiento)

Revision ID: 0056
Revises: 0055
"""

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("apresto_min", sa.Integer(), nullable=True))
        t.add_column(sa.Column("despega_hasta", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.drop_column("despega_hasta")
        t.drop_column("apresto_min")
