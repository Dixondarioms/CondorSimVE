"""Meteorologia por zonas: frentes de nubes, lluvia o tormenta que se desplazan turno a turno

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zonas_clima",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False, index=True),
        sa.Column("nombre", sa.String(60), nullable=False, server_default=""),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("radio_km", sa.Float, nullable=False),
        sa.Column("deriva_rumbo", sa.Float, nullable=False, server_default="0"),
        sa.Column("deriva_kmh", sa.Float, nullable=False, server_default="0"),
        sa.Column("hasta_turno", sa.Integer, nullable=True),
        sa.Column("creada_turno", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("zonas_clima")
