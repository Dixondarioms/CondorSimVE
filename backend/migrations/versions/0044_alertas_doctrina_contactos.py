"""Cóndor: pausa automatica (causas y motivo), doctrina y reglas de enfrentamiento (bando y unidad) y contactos con
clasificacion por etapas e incertidumbre de posicion

Revision ID: 0044
Revises: 0043
"""

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("pausa_auto_json", sa.Text(), nullable=True))
        t.add_column(sa.Column("pausa_motivo", sa.String(300), nullable=True))
        t.add_column(sa.Column("doctrina_json", sa.Text(), nullable=True))
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("doctrina_json", sa.Text(), nullable=True))
    with op.batch_alter_table("contactos") as t:
        t.add_column(sa.Column("etapa", sa.String(15), nullable=True))
        t.add_column(sa.Column("puntos", sa.Float(), nullable=True))
        t.add_column(sa.Column("incertidumbre_km", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("contactos") as t:
        for c in ("incertidumbre_km", "puntos", "etapa"):
            t.drop_column(c)
    with op.batch_alter_table("unidades") as t:
        t.drop_column("doctrina_json")
    with op.batch_alter_table("escenarios") as t:
        for c in ("doctrina_json", "pausa_motivo", "pausa_auto_json"):
            t.drop_column(c)
