"""Cóndor: reproducción de operaciones históricas (ficha de la operación real)

Revision ID: 0064
Revises: 0063
"""

import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("historia_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("historia_json")
