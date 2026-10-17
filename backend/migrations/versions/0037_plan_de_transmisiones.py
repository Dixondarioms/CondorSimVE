"""plan de transmisiones de cada bando (redes y frecuencias)

Revision ID: 0037
Revises: 0036
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("transmisiones_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("transmisiones_json")
