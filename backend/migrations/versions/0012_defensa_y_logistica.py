"""Control de emisiones de radares, fuego automatico de la antiaerea y existencias de las bases

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("emitiendo", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("fuego_libre", sa.Boolean, nullable=False, server_default=sa.true()))
        b.add_column(sa.Column("stock_combustible", sa.Float, nullable=False, server_default="1000"))
        b.add_column(sa.Column("stock_municion", sa.Float, nullable=False, server_default="1000"))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.drop_column("stock_municion")
        b.drop_column("stock_combustible")
        b.drop_column("fuego_libre")
        b.drop_column("emitiendo")
