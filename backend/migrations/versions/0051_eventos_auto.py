"""Cóndor: eventos automaticos del director (reglas disparador -> acciones)

Revision ID: 0051
Revises: 0050
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("eventos_auto_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("eventos_auto_json")
