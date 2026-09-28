from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.db import Base, migrar


def _motor(ruta):
    return create_engine(f"sqlite:///{ruta}")


def test_migraciones_producen_el_esquema_de_los_modelos(tmp_path):
    ruta = tmp_path / "nueva.db"
    migrar(f"sqlite:///{ruta}")
    with _motor(ruta).connect() as con:
        diferencias = compare_metadata(MigrationContext.configure(con), Base.metadata)
    assert diferencias == [], f"los modelos y las migraciones difieren: {diferencias}"


def test_base_previa_a_las_migraciones_se_marca_y_actualiza(tmp_path):
    """Una BD creada sin Alembic (esquema 0001) conserva sus datos al migrar."""
    ruta = tmp_path / "antigua.db"
    url = f"sqlite:///{ruta}"
    from alembic import command
    from app.db import config_alembic

    command.upgrade(config_alembic(url), "0001")  # esquema inicial
    motor = _motor(ruta)
    with motor.begin() as con:
        con.execute(text("DROP TABLE alembic_version"))  # simula BD sin control de versiones
        con.execute(text("INSERT INTO usuarios (username, password_hash, rol, activo, creado_en) "
                         "VALUES ('prof', 'x', 'instructor', 1, '2026-01-01')"))
    migrar(url)
    with motor.connect() as con:
        assert con.execute(text("SELECT username FROM usuarios")).scalar() == "prof"
        assert "alembic_version" in inspect(con).get_table_names()
        diferencias = compare_metadata(MigrationContext.configure(con), Base.metadata)
    assert diferencias == []
