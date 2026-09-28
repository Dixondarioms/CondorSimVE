"""Hora simulada inicial del escenario

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("hora_inicio_min", sa.Integer, nullable=False, server_default="360"))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.drop_column("hora_inicio_min")
