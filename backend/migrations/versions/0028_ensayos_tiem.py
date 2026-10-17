"""TIEM etapa 3: copias de ensayo de las formas de accion (juego de guerra)

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("ensayo_de", sa.Integer, sa.ForeignKey("escenarios.id", name="fk_escenarios_ensayo_de"),
                               nullable=True))
        b.add_column(sa.Column("ensayo_bando", sa.String(10), nullable=True))
        b.add_column(sa.Column("ensayo_fa", sa.String(300), nullable=False, server_default=""))
        b.add_column(sa.Column("ensayo_desde", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        for c in ("ensayo_desde", "ensayo_fa", "ensayo_bando", "ensayo_de"):
            b.drop_column(c)
