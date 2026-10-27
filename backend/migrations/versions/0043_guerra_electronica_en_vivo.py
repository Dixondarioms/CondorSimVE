"""SIETE en tiempo real: zonas de interferencia que duran mientras el emisor interfiere, y ordenes demoradas por las
comunicaciones (llegan a la unidad mas tarde)

Revision ID: 0043
Revises: 0042
"""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interferencias") as t:
        t.add_column(sa.Column("inicio_seg", sa.Float(), nullable=True))
        t.add_column(sa.Column("fin_seg", sa.Float(), nullable=True))
    with op.batch_alter_table("ordenes") as t:
        t.add_column(sa.Column("llega_seg", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ordenes") as t:
        t.drop_column("llega_seg")
    with op.batch_alter_table("interferencias") as t:
        t.drop_column("fin_seg")
        t.drop_column("inicio_seg")
