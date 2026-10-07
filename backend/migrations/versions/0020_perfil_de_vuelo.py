"""Perfil de vuelo de las aeronaves (alto, medio, rasante) para la linea de vista con el relieve

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL = el perfil por defecto de la clase (medio; rasante para helicopteros y misiles)
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("perfil_vuelo", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("perfil_vuelo")
