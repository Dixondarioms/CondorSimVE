"""Esquema inicial (escenarios, unidades, ordenes, eventos, usuarios, sesiones)

Revision ID: 0001
Revises:
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "escenarios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("turno_actual", sa.Integer, nullable=False),
        sa.Column("fase", sa.String(20), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
    )
    op.create_table(
        "unidades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("echelon", sa.String(40), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("fuerza", sa.Float, nullable=False),
        sa.Column("velocidad_kmh", sa.Float, nullable=False),
        sa.Column("alcance_km", sa.Float, nullable=False),
        sa.Column("deteccion_km", sa.Float, nullable=False),
        sa.Column("sidc", sa.String(20), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
    )
    op.create_table(
        "ordenes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("unidad_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("waypoints_json", sa.Text, nullable=False),
        sa.Column("objetivo_unidad_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=True),
        sa.Column("turno_emitida", sa.Integer, nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("resultado", sa.Text, nullable=False),
    )
    op.create_table(
        "eventos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("bando_destino", sa.String(10), nullable=False),
        sa.Column("descripcion", sa.Text, nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
    )
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
    )
    op.create_index("ix_usuarios_username", "usuarios", ["username"], unique=True)
    op.create_table(
        "sesiones",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("creada_en", sa.DateTime, nullable=False),
        sa.Column("expira_en", sa.DateTime, nullable=False),
    )
    op.create_index("ix_sesiones_usuario_id", "sesiones", ["usuario_id"])


def downgrade() -> None:
    for tabla in ("sesiones", "usuarios", "eventos", "ordenes", "unidades", "escenarios"):
        op.drop_table(tabla)
