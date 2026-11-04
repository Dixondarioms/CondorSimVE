"""Cóndor: imagen comun por enlace de datos (interruptor del director)

Revision ID: 0059
Revises: 0058
"""

import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("enlace_datos", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("enlace_datos")
