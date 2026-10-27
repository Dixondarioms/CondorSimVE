"""Cóndor: cada unidad de los ejercicios ya creados pasa a tener el modelo real que corresponde a su nombre (por
ejemplo, un «A-29 Super Tucano» que figuraba como el avión de ataque genérico), con la velocidad, el alcance, la
detección y la autonomía de ese modelo (engine/modelo_por_nombre.py y engine/catalogo_ampliado.py)

Revision ID: 0045
Revises: 0044
"""

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.engine import catalogo
    from app.engine.modelo_por_nombre import modelo_para

    con = op.get_bind()
    filas = con.execute(sa.text("SELECT id, clase, nombre, modelo FROM unidades WHERE estado != 'destruida'")).fetchall()
    for id_, clase, nombre, actual in filas:
        actual = actual or None
        nombre_actual = catalogo.MODELOS[actual].nombre if actual in catalogo.MODELOS else None
        nuevo = modelo_para(clase or "", nombre or "", actual, nombre_actual)
        if not nuevo or nuevo not in catalogo.MODELOS or catalogo.MODELOS[nuevo].clase != clase:
            continue
        m = catalogo.MODELOS[nuevo]
        con.execute(sa.text("UPDATE unidades SET modelo = :m, velocidad_kmh = :v, alcance_km = :a, deteccion_km = :d, "
                            "autonomia_km = :au WHERE id = :id"),
                    {"m": m.id, "v": m.velocidad_kmh, "a": m.alcance_km, "d": m.deteccion_km, "au": m.autonomia_km,
                     "id": id_})


def downgrade() -> None:
    pass  # los modelos anteriores eran genericos: no se vuelve a ellos
