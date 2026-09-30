"""Daño por partes de las bases aereas (pista, plataforma, deposito de combustible) y refugios reforzados

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("dano_pista", sa.Float, nullable=False, server_default="0"))
        b.add_column(sa.Column("dano_plataforma", sa.Float, nullable=False, server_default="0"))
        b.add_column(sa.Column("dano_combustible", sa.Float, nullable=False, server_default="0"))
        b.add_column(sa.Column("refugios", sa.Integer, nullable=False, server_default="0"))
    # las bases aereas existentes nacen con refugios
    op.execute("UPDATE unidades SET refugios = 4 WHERE clase = 'base_aerea'")


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("refugios")
        b.drop_column("dano_combustible")
        b.drop_column("dano_plataforma")
        b.drop_column("dano_pista")
