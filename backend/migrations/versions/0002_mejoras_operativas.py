"""Informe posterior, logistica, clima, turnos, contactos, asignaciones y bloqueo de login

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("escenarios") as b:
        b.add_column(sa.Column("clima", sa.String(20), nullable=False, server_default="despejado"))
        b.add_column(sa.Column("azar", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("semilla", sa.Integer, nullable=False, server_default="0"))
        b.add_column(sa.Column("auto_resolver", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("limite_decision_seg", sa.Integer, nullable=True))
        b.add_column(sa.Column("decision_termina_en", sa.DateTime, nullable=True))
        b.add_column(sa.Column("listo_azul", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("listo_rojo", sa.Boolean, nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("archivado", sa.Boolean, nullable=False, server_default=sa.false()))

    with op.batch_alter_table("unidades") as b:
        b.add_column(sa.Column("clase", sa.String(30), nullable=False, server_default=""))
        b.add_column(sa.Column("combustible", sa.Float, nullable=False, server_default="100"))
        b.add_column(sa.Column("municion", sa.Float, nullable=False, server_default="100"))
        b.add_column(sa.Column("autonomia_km", sa.Float, nullable=False, server_default="300"))

    op.create_table(
        "instantaneas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
        sa.Column("clima", sa.String(20), nullable=False),
        sa.Column("datos_json", sa.Text, nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
        sa.UniqueConstraint("escenario_id", "turno"),
    )
    op.create_index("ix_instantaneas_escenario_id", "instantaneas", ["escenario_id"])

    op.create_table(
        "combates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("turno", sa.Integer, nullable=False),
        sa.Column("orden_id", sa.Integer, sa.ForeignKey("ordenes.id"), nullable=True),
        sa.Column("atacante_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=False),
        sa.Column("defensor_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=False),
        sa.Column("atacante_nombre", sa.String(120), nullable=False),
        sa.Column("defensor_nombre", sa.String(120), nullable=False),
        sa.Column("atacante_bando", sa.String(10), nullable=False),
        sa.Column("defensor_bando", sa.String(10), nullable=False),
        sa.Column("ratio", sa.Float, nullable=False),
        sa.Column("fuerza_ini_atacante", sa.Float, nullable=False),
        sa.Column("fuerza_ini_defensor", sa.Float, nullable=False),
        sa.Column("perdida_atacante", sa.Float, nullable=False),
        sa.Column("perdida_defensor", sa.Float, nullable=False),
        sa.Column("terreno", sa.String(20), nullable=False),
        sa.Column("efectos", sa.Text, nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
    )
    op.create_index("ix_combates_escenario_id", "combates", ["escenario_id"])

    op.create_table(
        "contactos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), nullable=False),
        sa.Column("bando", sa.String(10), nullable=False),
        sa.Column("unidad_id", sa.Integer, sa.ForeignKey("unidades.id"), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False),
        sa.Column("turno_visto", sa.Integer, nullable=False),
        sa.UniqueConstraint("escenario_id", "bando", "unidad_id"),
    )
    op.create_index("ix_contactos_escenario_id", "contactos", ["escenario_id"])

    op.create_table(
        "asignaciones",
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("usuarios.id"), primary_key=True),
        sa.Column("escenario_id", sa.Integer, sa.ForeignKey("escenarios.id"), primary_key=True),
    )

    op.create_table(
        "intentos_login",
        sa.Column("clave", sa.String(50), primary_key=True),
        sa.Column("fallos", sa.Integer, nullable=False),
        sa.Column("bloqueado_hasta", sa.DateTime, nullable=True),
    )

    # ---- datos existentes ----
    if op.get_bind().dialect.name == "postgresql":
        op.execute("UPDATE escenarios SET semilla = floor(random() * 2147483647)::int")
    else:  # SQLite: random() devuelve un entero de 64 bits
        op.execute("UPDATE escenarios SET semilla = abs(random()) % 2147483647")
    op.execute("UPDATE unidades SET clase = 'infanteria', autonomia_km = 300 WHERE tipo = 'terrestre'")
    op.execute("UPDATE unidades SET clase = 'caza', autonomia_km = 1800 WHERE tipo = 'aerea'")
    # Antes todos los usuarios veian todos los escenarios: se conserva ese acceso.
    op.execute(
        "INSERT INTO asignaciones (usuario_id, escenario_id) "
        "SELECT u.id, e.id FROM usuarios u, escenarios e WHERE u.rol != 'instructor'"
    )


def downgrade() -> None:
    for tabla in ("intentos_login", "asignaciones", "contactos", "combates", "instantaneas"):
        op.drop_table(tabla)
    with op.batch_alter_table("unidades") as b:
        for c in ("clase", "combustible", "municion", "autonomia_km"):
            b.drop_column(c)
    with op.batch_alter_table("escenarios") as b:
        for c in ("clima", "azar", "semilla", "auto_resolver", "limite_decision_seg",
                  "decision_termina_en", "listo_azul", "listo_rojo", "archivado"):
            b.drop_column(c)
