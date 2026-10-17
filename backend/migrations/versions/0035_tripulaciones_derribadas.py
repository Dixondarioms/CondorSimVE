"""tripulaciones derribadas (recuperacion de personal, SAR/CSAR)

Revision ID: 0035
Revises: 0034
"""

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("derribados_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("derribados_json")
