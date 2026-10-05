"""Autor de cada orden y mision aerea (usuario y puesto al emitirla) para la rubrica por alumno

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Las filas existentes quedan sin autor: la rubrica las muestra como "sin autor registrado".
    for tabla in ("ordenes", "misiones"):
        with op.batch_alter_table(tabla) as b:
            # en SQLite (modo batch) la clave foranea necesita nombre
            b.add_column(sa.Column("autor_id", sa.Integer, sa.ForeignKey("usuarios.id", name=f"fk_{tabla}_autor_id"),
                                   nullable=True))
            b.add_column(sa.Column("autor_puesto", sa.String(20), nullable=True))


def downgrade() -> None:
    for tabla in ("misiones", "ordenes"):
        with op.batch_alter_table(tabla) as b:
            b.drop_column("autor_puesto")
            b.drop_column("autor_id")
