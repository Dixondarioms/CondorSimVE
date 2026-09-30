"""Transporte de tropas: unidad a bordo de un buque de desembarco o un helicoptero de transporte

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("transporte_id", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("transporte_id")
