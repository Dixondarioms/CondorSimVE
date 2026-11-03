"""Cóndor: daño por sistemas (sensores, armas, propulsion y comunicaciones) de buques y unidades de tierra

Revision ID: 0050
Revises: 0049
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("sistemas_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.drop_column("sistemas_json")
