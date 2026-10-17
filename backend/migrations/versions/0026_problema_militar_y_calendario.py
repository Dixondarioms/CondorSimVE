"""TIEM: Problema Militar Operativo por bando, calendario D/H con fases, quien conduce cada bando y cadena de objetivos

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("conduce_azul", sa.String(12), nullable=False, server_default="alumnos"))
        b.add_column(sa.Column("conduce_rojo", sa.String(12), nullable=False, server_default="alumnos"))
        b.add_column(sa.Column("fecha_inicio", sa.String(10), nullable=True))
        b.add_column(sa.Column("turno_h", sa.Integer, nullable=True))
        b.add_column(sa.Column("turno_final", sa.Integer, nullable=True))
        b.add_column(sa.Column("fases_json", sa.Text, nullable=True))
    with op.batch_alter_table("objetivos") as b:
        b.add_column(sa.Column("nivel", sa.String(12), nullable=False, server_default="material"))
        b.add_column(sa.Column("padre_id", sa.Integer, sa.ForeignKey("objetivos.id", name="fk_objetivos_padre_id"),
                               nullable=True))
        b.add_column(sa.Column("efecto", sa.String(300), nullable=False, server_default=""))
        b.add_column(sa.Column("indicador", sa.String(300), nullable=False, server_default=""))
        b.add_column(sa.Column("umbral", sa.Float, nullable=True))
    op.create_table(
        "problemas_militares",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False, index=True),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("contenido_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("origen", sa.String(12), nullable=False, server_default="instructor"),
        sa.Column("actualizado_en", sa.DateTime, nullable=False),
        sa.UniqueConstraint("escenario_id", "bando"),
    )


def downgrade() -> None:
    op.drop_table("problemas_militares")
    with op.batch_alter_table("objetivos") as b:
        b.drop_column("umbral")
        b.drop_column("indicador")
        b.drop_column("efecto")
        b.drop_column("padre_id")
        b.drop_column("nivel")
    with op.batch_alter_table("escenarios") as b:
        for c in ("fases_json", "turno_final", "turno_h", "fecha_inicio", "conduce_rojo", "conduce_azul"):
            b.drop_column(c)
