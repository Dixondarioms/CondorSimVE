"""apresto operacional: grado de cada bando y Puesta en Completo Apresto Operacional (PCAO)

Revision ID: 0039
Revises: 0038
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("apresto_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("apresto_json")
