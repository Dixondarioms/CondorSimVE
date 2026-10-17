"""Defensa aerea: misiles listos de cada arma y arma elegida por el operador (engine/defensa_aerea.py)

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("cargas_json", sa.Text, nullable=True))
        b.add_column(sa.Column("arma_elegida", sa.String(30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("arma_elegida")
        b.drop_column("cargas_json")
