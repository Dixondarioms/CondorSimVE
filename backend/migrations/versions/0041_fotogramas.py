"""SIETE en tiempo real: fotogramas de la repeticion (cada pocos minutos simulados) y hora simulada de combates y eventos

Revision ID: 0041
Revises: 0040
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fotogramas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("escenario_id", sa.Integer(), sa.ForeignKey("escenarios.id"), nullable=False, index=True),
        sa.Column("sim_segundos", sa.Float(), nullable=False),
        sa.Column("turno", sa.Integer(), nullable=False),
        sa.Column("clima", sa.String(20), nullable=False, server_default="despejado"),
        sa.Column("datos_json", sa.Text(), nullable=False),
    )
    with op.batch_alter_table("combates") as t:
        t.add_column(sa.Column("sim_segundos", sa.Float(), nullable=True))
    with op.batch_alter_table("eventos") as t:
        t.add_column(sa.Column("sim_segundos", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("eventos") as t:
        t.drop_column("sim_segundos")
    with op.batch_alter_table("combates") as t:
        t.drop_column("sim_segundos")
    op.drop_table("fotogramas")
