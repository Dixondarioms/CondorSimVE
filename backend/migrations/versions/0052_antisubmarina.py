"""Cóndor: guerra antisubmarina (profundidad de los submarinos y sonoboyas)

Revision ID: 0052
Revises: 0051
"""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("profundidad", sa.String(12), nullable=True))
    op.create_table(
        "sonoboyas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escenario_id", sa.Integer(), sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("unidad_id", sa.Integer(), sa.ForeignKey("unidades.id"), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("radio_km", sa.Float(), nullable=False),
        sa.Column("desde_seg", sa.Float(), nullable=False),
        sa.Column("hasta_seg", sa.Float(), nullable=False),
    )
    op.create_index("ix_sonoboyas_escenario_id", "sonoboyas", ["escenario_id"])


def downgrade() -> None:
    op.drop_index("ix_sonoboyas_escenario_id", table_name="sonoboyas")
    op.drop_table("sonoboyas")
    with op.batch_alter_table("unidades") as t:
        t.drop_column("profundidad")
