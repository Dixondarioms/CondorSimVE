"""Fixtures de las pruebas.

Por defecto usan SQLite en memoria (rapido). Con TEST_DB=postgres se ejecutan contra un PostgreSQL real:
el servidor embebido de `pixeltable-pgserver` o el indicado en TEST_DATABASE_URL.

    TEST_DB=postgres python -m pytest
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app import models  # noqa: F401  (registra todas las tablas)
from app import state as state_mod
from app.db import Base, get_db, normalizar_url
from app.engine import orders
from app.main import app
from app.models.usuario import Usuario
from app.routers import ordenes as router_ordenes
from app.routers import unidades as router_unidades
from app.terreno import Terreno

USAR_POSTGRES = os.environ.get("TEST_DB", "sqlite").lower() in ("postgres", "postgresql", "pg")


class TerrenoFalso(Terreno):
    """Terreno de prueba: clase por funcion (lat, lon) -> nombre, por defecto llano."""

    def __init__(self, funcion=None):
        super().__init__()
        self.funcion = funcion or (lambda lat, lon: "llano")

    @property
    def disponible(self):
        return True

    def clase(self, lat, lon):
        return self.funcion(lat, lon)


@pytest.fixture(autouse=True)
def terreno_llano(monkeypatch):
    """Por defecto los tests no dependen de los datos de terreno reales."""
    monkeypatch.setattr(orders, "get_terreno", lambda: TerrenoFalso())
    monkeypatch.setattr(state_mod, "get_terreno", lambda: TerrenoFalso())
    monkeypatch.setattr(router_unidades, "get_terreno", lambda: TerrenoFalso())
    monkeypatch.setattr(router_ordenes, "get_terreno", lambda: TerrenoFalso())
    monkeypatch.setattr(auth, "ITERACIONES", 1000)  # hash rapido solo en tests


@pytest.fixture(autouse=True)
def plantillas_usuario_temporales(monkeypatch, tmp_path):
    """Las plantillas guardadas por el instructor van a una carpeta temporal: nunca a backend/data."""
    from app.engine import plantillas

    monkeypatch.setattr(plantillas, "RUTA_PLANTILLAS_USUARIO", tmp_path / "plantillas_usuario")


# ---------------------------------------------------------------- PostgreSQL de prueba
@pytest.fixture(scope="session")
def url_postgres(tmp_path_factory):
    """URL de un PostgreSQL vacio: TEST_DATABASE_URL o un servidor embebido temporal."""
    externa = os.environ.get("TEST_DATABASE_URL")
    if externa:
        yield normalizar_url(externa)
        return
    pgserver = pytest.importorskip("pixeltable_pgserver", reason="Sin PostgreSQL de prueba (pip install pixeltable-pgserver)")
    servidor = pgserver.get_server(tmp_path_factory.mktemp("pgdata"), cleanup_mode="delete")
    try:
        yield normalizar_url(servidor.get_uri())
    finally:
        servidor.cleanup()


@pytest.fixture(scope="session")
def motor_postgres(url_postgres):
    motor = create_engine(url_postgres, pool_size=10, max_overflow=20, pool_pre_ping=True)
    Base.metadata.drop_all(bind=motor)
    Base.metadata.create_all(bind=motor)
    yield motor
    motor.dispose()


def _vaciar(motor) -> None:
    nombres = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with motor.begin() as con:
        con.execute(text(f"TRUNCATE {nombres} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def db_engine(request):
    if USAR_POSTGRES:
        motor = request.getfixturevalue("motor_postgres")
        _vaciar(motor)
        yield motor
        return
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine


@pytest.fixture()
def db_session(db_engine):
    session = sessionmaker(bind=db_engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api(db_engine):
    """Fabrica de clientes HTTP con una BD de prueba y usuarios de cada rol."""
    Session = sessionmaker(bind=db_engine)

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    with Session() as db:
        for nombre, rol in (
            ("prof", "instructor"),
            ("alfa", "azul"),
            ("bravo", "rojo"),
            ("obs", "observador"),
        ):
            db.add(Usuario(username=nombre, password_hash=auth.hash_password("clave-segura-1"), rol=rol))
        db.commit()

    def cliente(nombre: str | None = None) -> TestClient:
        c = TestClient(app)
        if nombre:
            r = c.post("/api/auth/login", json={"username": nombre, "password": "clave-segura-1"})
            assert r.status_code == 200, r.text
        return c

    cliente.engine = db_engine
    yield cliente
    app.dependency_overrides.clear()
