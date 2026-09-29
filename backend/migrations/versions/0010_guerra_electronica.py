"""Zonas de interferencia electronica (guerra electronica)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interferencias",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("unidad_id", sa.Integer, nullable=True),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("radio_km", sa.Float, nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
    )
    op.create_index("ix_interferencias_escenario_id", "interferencias", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_interferencias_escenario_id", table_name="interferencias")
    op.drop_table("interferencias")
