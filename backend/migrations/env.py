from alembic import context
from sqlalchemy import create_engine

from app.db import Base, es_sqlite
from app import models  # noqa: F401  (registra todos los modelos)

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    # la URL viene de app/db.py (respeta SIMULADOR_DATABASE_URL); "%%" es el escape de ConfigParser
    url = config.get_main_option("sqlalchemy.url").replace("%%", "%")
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite no soporta ALTER TABLE completo: se usa la copia de tabla; PostgreSQL, ALTER nativo
            render_as_batch=es_sqlite(url),
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


run_migrations_online()
