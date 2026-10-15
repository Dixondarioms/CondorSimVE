"""Personal de las unidades (dotacion fijada por el instructor) y largo de los puentes de infraestructura

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("personal", sa.Integer, nullable=True))
        b.add_column(sa.Column("radio_km", sa.Float, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("radio_km")
        b.drop_column("personal")
