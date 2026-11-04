"""Cóndor: velocidad elegida de aeronaves y buques (económica, crucero o máxima)

Revision ID: 0057
Revises: 0056
"""

import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("velocidad_modo", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.drop_column("velocidad_modo")
