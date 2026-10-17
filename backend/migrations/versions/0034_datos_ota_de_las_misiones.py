"""datos de la OTA de las misiones (paquete, comandante de mision, armamento, IFF, TOT)

Revision ID: 0034
Revises: 0033
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("misiones") as t:
        t.add_column(sa.Column("ota_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("misiones") as t:
        t.drop_column("ota_json")
