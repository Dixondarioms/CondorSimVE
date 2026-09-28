"""Ingenieros/convoyes/fidelidad de plataforma, graficos tacticos, chat con interferencia y registro logistico

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("carga", sa.Float, nullable=False, server_default="0"))
        b.add_column(sa.Column("recarga_restante", sa.Integer, nullable=False, server_default="0"))
        b.add_column(sa.Column("despliegue_restante", sa.Integer, nullable=False, server_default="0"))

    with op.batch_alter_table("ordenes") as b:
        b.add_column(sa.Column("detalle", sa.String(20), nullable=False, server_default=""))

    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("com_latencia_ms", sa.Integer, nullable=False, server_default="0"))
        b.add_column(sa.Column("com_jitter_ms", sa.Integer, nullable=False, server_default="0"))
        b.add_column(sa.Column("com_perdida_pct", sa.Integer, nullable=False, server_default="0"))

    op.create_table(
        "obras",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("unidad_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=True),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("radio_km", sa.Float, nullable=False),
        sa.Column("creada_turno", sa.Integer, nullable=False),
        sa.Column("expira_turno", sa.Integer, nullable=False),
    )
    op.create_index("ix_obras_escenario_id", "obras", ["escenario_id"])

    op.create_table(
        "graficos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("etiqueta", sa.String(60), nullable=False),
        sa.Column("geojson", sa.Text, nullable=False),
        sa.Column("autor_id", sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("autor_nombre", sa.String(50), nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
    )
    op.create_index("ix_graficos_escenario_id", "graficos", ["escenario_id"])

    op.create_table(
        "mensajes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("canal", sa.String(10), nullable=False),
        sa.Column("remitente_id", sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("remitente_nombre", sa.String(50), nullable=False),
        sa.Column("remitente_rol", sa.String(20), nullable=False),
        sa.Column("texto", sa.Text, nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
        sa.Column("demora_azul_ms", sa.Integer, nullable=False),
        sa.Column("demora_rojo_ms", sa.Integer, nullable=False),
        sa.Column("perdido_azul", sa.Boolean, nullable=False),
        sa.Column("perdido_rojo", sa.Boolean, nullable=False),
    )
    op.create_index("ix_mensajes_escenario_id", "mensajes", ["escenario_id"])

    op.create_table(
        "registro_logistico",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
        sa.Column("unidad_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=False),
        sa.Column("unidad_nombre", sa.String(120), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("variable", sa.String(12), nullable=False),
        sa.Column("antes", sa.Float, nullable=False),
        sa.Column("despues", sa.Float, nullable=False),
        sa.Column("causa", sa.String(20), nullable=False),
        sa.Column("orden_id", sa.Integer, sa.ForeignKey("ordenes.id"), nullable=True),
    )
    op.create_index("ix_registro_logistico_escenario_id", "registro_logistico", ["escenario_id"])

    # Los convoyes existentes (no hay) partirian llenos; el resto de unidades no transporta suministros.


def downgrade() -> None:
    for tabla in ("registro_logistico", "mensajes", "graficos", "obras"):
        op.drop_table(tabla)
    with op.batch_alter_table("escenarios") as b:
        for c in ("com_latencia_ms", "com_jitter_ms", "com_perdida_pct"):
            b.drop_column(c)
    with op.batch_alter_table("ordenes") as b:
        b.drop_column("detalle")
    with op.batch_alter_table("unidades") as b:
        for c in ("carga", "recarga_restante", "despliegue_restante"):
            b.drop_column(c)
