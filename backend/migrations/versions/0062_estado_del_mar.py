"""Cóndor: estado del mar

Revision ID: 0062
Revises: 0061
"""

import sqlalchemy as sa
from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("estado_mar", sa.String(12), nullable=False, server_default="calmo"))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("estado_mar")
