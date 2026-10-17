"""Plantilla de personal (TOE) por bando, disponibilidad y fallas, y esfuerzo aereo (engine/toe.py, disponibilidad.py)

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("fallas", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("personal_json", sa.Text, nullable=True))
        b.add_column(sa.Column("esfuerzo_json", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.drop_column("esfuerzo_json")
        b.drop_column("personal_json")
        b.drop_column("fallas")
