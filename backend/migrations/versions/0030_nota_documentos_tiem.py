"""TIEM etapa 6: nota del instructor (1 a 20) en cada documento

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("documentos_tiem") as b:
        b.add_column(sa.Column("nota", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documentos_tiem") as b:
        b.drop_column("nota")
