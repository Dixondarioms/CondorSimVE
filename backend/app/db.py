"""Conexion a la base de datos: SQLite (por defecto, un solo servidor) o PostgreSQL.

La base se elige con la variable de entorno SIMULADOR_DATABASE_URL (o DATABASE_URL), por ejemplo
    postgresql://simulador:clave@localhost:5432/simulador
Sin ella se usa el archivo SQLite `backend/simulador_fenix.db` (o SIMULADOR_DB para otra ruta).
PostgreSQL es lo recomendado con varios alumnos conectados: maneja bien las escrituras concurrentes
(WebSockets, temporizador de turnos, varios procesos) y bloquea la fila del escenario al resolver un turno.

Las variables tambien pueden ir en `backend/.env` (lineas CLAVE=valor; lo escribe instalar.cmd -Postgres
o -Https). Se cargan al importar este modulo sin pisar las que ya esten definidas en el entorno.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent


def cargar_env(ruta: Path = BASE_DIR / ".env", entorno=os.environ) -> list[str]:
    """Carga CLAVE=valor de un archivo .env en `entorno` (solo las claves que no existan).
    Ignora lineas vacias y comentarios; quita comillas simples o dobles alrededor del valor."""
    cargadas = []
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return cargadas
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave, valor = clave.strip(), valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if clave and clave not in entorno:
            entorno[clave] = valor
            cargadas.append(clave)
    return cargadas


cargar_env()
# SIMULADOR_DB permite apuntar a otro archivo SQLite (pruebas, copias) sin tocar el de produccion.
DB_PATH = Path(os.environ.get("SIMULADOR_DB") or BASE_DIR / "simulador_fenix.db")

# Clave del bloqueo asesor de PostgreSQL que serializa las migraciones entre procesos.
CLAVE_MIGRACION = 727_272


def normalizar_url(url: str) -> str:
    """Acepta postgres:// y postgresql:// y fuerza el driver psycopg (v3)."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


def _url_por_defecto() -> str:
    url = os.environ.get("SIMULADOR_DATABASE_URL") or os.environ.get("DATABASE_URL")
    return normalizar_url(url) if url else f"sqlite:///{DB_PATH}"


DATABASE_URL = _url_por_defecto()


def es_sqlite(url: str = DATABASE_URL) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def crear_motor(url: str = DATABASE_URL):
    if es_sqlite(url):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        pool_size=int(os.environ.get("SIMULADOR_POOL_SIZE", "10")),
        max_overflow=int(os.environ.get("SIMULADOR_POOL_MAX_OVERFLOW", "20")),
        pool_pre_ping=True,  # descarta conexiones cortadas (reinicio de la base, red)
        pool_recycle=1800,
    )


engine = crear_motor()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def config_alembic(url: str = DATABASE_URL):
    from alembic.config import Config

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    # ConfigParser interpreta % como interpolacion: se escapa para claves con caracteres especiales
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def migrar(url: str = DATABASE_URL) -> None:
    """Aplica las migraciones pendientes. Una base creada antes de existir las
    migraciones (tablas sin alembic_version) se marca como version inicial.

    En PostgreSQL se toma un bloqueo asesor para que varios procesos que arrancan a la vez
    (p. ej. varios workers) no migren simultaneamente."""
    from alembic import command

    cfg = config_alembic(url)
    motor = crear_motor(url)
    try:
        with motor.connect() as con:
            if not es_sqlite(url):
                con.execute(text("SELECT pg_advisory_lock(:k)"), {"k": CLAVE_MIGRACION})
            try:
                tablas = set(inspect(con).get_table_names())
                if tablas and "alembic_version" not in tablas:
                    command.stamp(cfg, "0001")
                command.upgrade(cfg, "head")
            finally:
                if not es_sqlite(url):
                    con.rollback()
                    con.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": CLAVE_MIGRACION})
                    con.commit()
    finally:
        motor.dispose()


def init_db() -> None:
    migrar()
