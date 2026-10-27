"""SIETE en tiempo real: reloj simulado del escenario, ruta y orden activa de cada unidad, plazos en segundos

Revision ID: 0040
Revises: 0039
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as t:
        t.add_column(sa.Column("sim_segundos", sa.Float(), nullable=False, server_default="0"))
        t.add_column(sa.Column("velocidad", sa.Integer(), nullable=False, server_default="60"))
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("ruta_json", sa.Text(), nullable=True))
        t.add_column(sa.Column("orden_id", sa.Integer(), nullable=True))
        t.add_column(sa.Column("rumbo", sa.Float(), nullable=True))
        t.add_column(sa.Column("espera_hasta", sa.Float(), nullable=True))
        t.add_column(sa.Column("recarga_hasta", sa.Float(), nullable=True))
    with op.batch_alter_table("ordenes") as t:
        t.add_column(sa.Column("emitida_seg", sa.Float(), nullable=True))
    # el reloj de los escenarios que ya existian arranca en su turno actual, detenido: el director lo pone en marcha
    op.execute("UPDATE escenarios SET sim_segundos = (turno_actual - 1) * 3600.0")
    op.execute("UPDATE escenarios SET estado = 'pausado' WHERE estado = 'activo'")


def downgrade() -> None:
    with op.batch_alter_table("ordenes") as t:
        t.drop_column("emitida_seg")
    with op.batch_alter_table("unidades") as t:
        for c in ("recarga_hasta", "espera_hasta", "rumbo", "orden_id", "ruta_json"):
            t.drop_column(c)
    with op.batch_alter_table("escenarios") as t:
        t.drop_column("velocidad")
        t.drop_column("sim_segundos")
