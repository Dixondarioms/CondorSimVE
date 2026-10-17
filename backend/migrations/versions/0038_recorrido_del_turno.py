"""camino que recorrio cada unidad en el ultimo turno (para animarlo en el mapa)

Revision ID: 0038
Revises: 0037
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.add_column(sa.Column("recorrido_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("unidades") as t:
        t.drop_column("recorrido_json")
