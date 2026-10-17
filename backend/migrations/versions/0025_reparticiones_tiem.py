"""Reparticiones del TIEM: los puestos EM, A2, A3, A4 y A5 pasan a Comandante, A-2, A-3, A-4 y A-3

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

NUEVOS = {"mando": "comandante", "inteligencia": "a2", "operaciones": "a3", "logistica": "a4", "planificacion": "a3"}
VIEJOS = {"comandante": "mando", "jem": "mando", "a1": "mando", "a2": "inteligencia", "a3": "operaciones",
          "a3da": "operaciones", "a4": "logistica", "ce": "inteligencia"}


def _traducir(tabla: str, columna: str, mapa: dict) -> None:
    t = sa.table(tabla, sa.column(columna, sa.String))
    for viejo, nuevo in mapa.items():
        op.execute(t.update().where(t.c[columna] == viejo).values({columna: nuevo}))


def upgrade() -> None:
    _traducir("usuarios", "puesto", NUEVOS)
    _traducir("ordenes", "autor_puesto", NUEVOS)
    _traducir("misiones", "autor_puesto", NUEVOS)
    with op.batch_alter_table("usuarios") as b:
        b.alter_column("puesto", existing_type=sa.String(20), server_default="comandante")


def downgrade() -> None:
    _traducir("usuarios", "puesto", VIEJOS)
    _traducir("ordenes", "autor_puesto", VIEJOS)
    _traducir("misiones", "autor_puesto", VIEJOS)
    with op.batch_alter_table("usuarios") as b:
        b.alter_column("puesto", existing_type=sa.String(20), server_default="mando")
