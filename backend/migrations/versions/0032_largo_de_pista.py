"""Largo de la pista de una base aerea fijado por el instructor (engine/plataformas.py)

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("pista_m", sa.Float, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("pista_m")
