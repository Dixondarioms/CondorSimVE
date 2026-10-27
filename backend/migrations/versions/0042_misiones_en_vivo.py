"""SIETE en tiempo real: hasta cuando orbita (o espera) cada mision aerea, en segundos simulados

Revision ID: 0042
Revises: 0041
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("misiones") as t:
        t.add_column(sa.Column("espera_hasta", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("misiones") as t:
        t.drop_column("espera_hasta")
