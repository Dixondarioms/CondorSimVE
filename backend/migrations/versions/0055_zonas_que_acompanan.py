"""Cóndor: zonas que acompañan a una unidad

Revision ID: 0055
Revises: 0054
"""

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("zonas") as t:
        t.add_column(sa.Column("unidad_id", sa.Integer(), sa.ForeignKey("unidades.id", name="fk_zonas_unidad_id"), nullable=True))
        t.add_column(sa.Column("ancla_lat", sa.Float(), nullable=True))
        t.add_column(sa.Column("ancla_lon", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("zonas") as t:
        t.drop_column("ancla_lon")
        t.drop_column("ancla_lat")
        t.drop_column("unidad_id")
