"""TIEM etapa 2: documentos de la apreciacion inicial de cada bando y sus archivos adjuntos

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documentos_tiem",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False, index=True),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("contenido_json", sa.Text, nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("observaciones", sa.Text, nullable=False),
        sa.Column("editado_por", sa.String(50), nullable=False),
        sa.Column("editado_puesto", sa.String(20), nullable=False),
        sa.Column("actualizado_en", sa.DateTime, nullable=False),
        sa.Column("presentado_turno", sa.Integer, nullable=True),
        sa.Column("revisado_turno", sa.Integer, nullable=True),
        sa.UniqueConstraint("escenario_id", "bando", "tipo"),
    )
    op.create_table(
        "archivos_tiem",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("documento_id", sa.Integer, sa.ForeignKey("documentos_tiem.id"), nullable=False, index=True),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("tipo_mime", sa.String(120), nullable=False),
        sa.Column("tamano", sa.Integer, nullable=False),
        sa.Column("datos", sa.LargeBinary, nullable=False),
        sa.Column("subido_por", sa.String(50), nullable=False),
        sa.Column("subido_en", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("archivos_tiem")
    op.drop_table("documentos_tiem")
