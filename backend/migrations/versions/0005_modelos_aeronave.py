"""Modelos de aeronave (F-16, Su-30...), grupos aereos y orden de despegue

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("modelo", sa.String(30), nullable=False, server_default=""))
        b.add_column(sa.Column("aeronaves", sa.Integer, nullable=False, server_default="1"))

    with op.batch_alter_table("ordenes") as b:
        b.alter_column("detalle", existing_type=sa.String(20), type_=sa.String(160),
                       existing_nullable=False, existing_server_default="")


def downgrade() -> None:
    with op.batch_alter_table("ordenes") as b:
        b.alter_column("detalle", existing_type=sa.String(160), type_=sa.String(20),
                       existing_nullable=False, existing_server_default="")
    with op.batch_alter_table("unidades") as b:
        b.drop_column("aeronaves")
        b.drop_column("modelo")
