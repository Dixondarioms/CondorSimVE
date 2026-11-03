"""Cóndor: cargas de armamento por aeronave y existencias de armas en bases y buques

Revision ID: 0048
Revises: 0047
"""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("armamento_json", sa.Text(), nullable=True))
        t.add_column(sa.Column("existencias_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.drop_column("existencias_json")
        t.drop_column("armamento_json")
