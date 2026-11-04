"""Fixtures de las pruebas.

Por defecto usan SQLite en memoria (rapido). Con TEST_DB=postgres se ejecutan contra un PostgreSQL real:
el servidor embebido de `pixeltable-pgserver` o el indicado en TEST_DATABASE_URL.

    TEST_DB=postgres python -m pytest
"""

import os
from pathlib import Path

# Las pruebas usan el catalogo del codigo, no los ajustes del instructor de este equipo
# (backend/data/ajustes_catalogo.json): se apunta a un archivo que no existe antes de importar la aplicacion.
os.environ.setdefault("SIMULADOR_AJUSTES_CATALOGO", os.path.join(os.path.dirname(__file__), "_sin_ajustes_catalogo.json"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import adversario as adversario_mod  # noqa: E402
from app import auth  # noqa: E402
from app import models  # noqa: E402,F401  (registra todas las tablas)
from app import state as state_mod  # noqa: E402
from app.db import Base, get_db, normalizar_url  # noqa: E402
from app.engine import orders  # noqa: E402
from app.main import app  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.routers import ordenes as router_ordenes  # noqa: E402
from app.routers import unidades as router_unidades  # noqa: E402
from app.terreno import Terreno  # noqa: E402

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
    monkeypatch.setattr(adversario_mod, "get_terreno", lambda: TerrenoFalso())
    from app.engine import tiempo_real
    monkeypatch.setattr(tiempo_real, "get_terreno", lambda: TerrenoFalso())
    monkeypatch.setattr(auth, "ITERACIONES", 1000)  # hash rapido solo en tests
    from app.engine import mar
    monkeypatch.setattr(mar, "_POR_ESCENARIO", {})  # el estado del mar de cada escenario: cada prueba empieza en calma


@pytest.fixture(autouse=True)
def plantillas_usuario_temporales(monkeypatch, tmp_path):
    """Las plantillas guardadas por el instructor van a una carpeta temporal: nunca a backend/data."""
    from app.engine import plantillas

    monkeypatch.setattr(plantillas, "RUTA_PLANTILLAS_USUARIO", tmp_path / "plantillas_usuario")
    # el catalogo propio del instructor tambien: nunca se escribe backend/data/modelos_usuario.json en las pruebas
    from app.engine import catalogo, modelos_usuario
    monkeypatch.setattr(modelos_usuario, "RUTA", tmp_path / "modelos_usuario.json")
    monkeypatch.setattr(catalogo, "MODELOS", {k: v for k, v in catalogo.MODELOS.items() if not k.startswith("u_")})


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
            if r.json().get("debe_cambiar_clave"):
                # usuario creado desde el panel: se da por cambiada la contrasena (eso se prueba en test_cuentas.py)
                with Session() as db:
                    db.query(Usuario).filter(Usuario.username == nombre).update({"debe_cambiar_clave": False})
                    db.commit()
        return c

    cliente.engine = db_engine
    yield cliente
    app.dependency_overrides.clear()


# SIETE en tiempo real: estas pruebas describen el SIETE por turnos (LISTO, resolver el turno, una orden pendiente por
# turno, el adversario automatico) o funciones que llegan en las proximas etapas (construir, interferir, embarcar). Se
# conservan para retomarlas en cada etapa; la lista esta en tests/pruebas_por_turnos.txt.
_POR_TURNOS = {
    linea.strip() for linea in (Path(__file__).parent / "pruebas_por_turnos.txt").read_text(encoding="utf-8").splitlines()
    if linea.strip() and not linea.startswith("#")
}


def pytest_collection_modifyitems(config, items):
    import pytest

    marca = pytest.mark.skip(reason="SIETE por turnos o etapa siguiente del tiempo real (tests/pruebas_por_turnos.txt)")
    for item in items:
        if item.nodeid.replace("\\", "/") in _POR_TURNOS:
            item.add_marker(marca)
