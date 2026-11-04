"""Cóndor: fuego amigo e IFF (interruptor del director y el IFF de cada aeronave)

Revision ID: 0063
Revises: 0062
"""

import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("fuego_amigo", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("iff", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.drop_column("iff")
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("fuego_amigo")
