"""Pruebas especificas de PostgreSQL (se omiten si no hay un servidor de prueba disponible)."""

import itertools
import threading

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app import migrar_a_postgres
from app.db import Base, config_alembic, es_sqlite, migrar, normalizar_url
from app.engine import clock
from app.models.aar import Instantanea
from app.models.escenario import Escenario
from app.models.unidad import Unidad


def _cabeza() -> str:
    """Ultima migracion de Alembic (asi la prueba no se rompe al agregar una nueva)."""
    return ScriptDirectory.from_config(config_alembic("sqlite://")).get_current_head()

_contador = itertools.count(1)


@pytest.fixture()
def base_nueva(url_postgres):
    """URL de una base PostgreSQL recien creada (una por prueba) que se elimina al terminar."""
    nombre = f"prueba_{next(_contador)}_{threading.get_ident() % 10000}"
    admin = create_engine(url_postgres, isolation_level="AUTOCOMMIT")
    with admin.connect() as con:
        con.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))
        con.execute(text(f'CREATE DATABASE "{nombre}"'))
    url = make_url(url_postgres).set(database=nombre).render_as_string(hide_password=False)
    yield url
    with admin.connect() as con:
        con.execute(text(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)'))
    admin.dispose()


def test_normalizar_url_fuerza_el_driver_psycopg():
    assert normalizar_url("postgres://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert normalizar_url("postgresql://u:p@h:5433/d") == "postgresql+psycopg://u:p@h:5433/d"
    assert normalizar_url("postgresql+psycopg://u@h/d") == "postgresql+psycopg://u@h/d"
    assert normalizar_url("sqlite:///x.db") == "sqlite:///x.db"
    assert es_sqlite("sqlite:///x.db") and not es_sqlite("postgresql+psycopg://u@h/d")


def test_las_migraciones_crean_el_esquema_de_los_modelos_en_postgresql(base_nueva):
    migrar(base_nueva)
    motor = create_engine(base_nueva)
    with motor.connect() as con:
        diferencias = compare_metadata(MigrationContext.configure(con), Base.metadata)
        version = con.execute(text("SELECT version_num FROM alembic_version")).scalar()
    motor.dispose()
    assert diferencias == [], f"modelos y migraciones divergen en PostgreSQL: {diferencias}"
    assert version == _cabeza()


def test_una_base_postgresql_antigua_con_datos_se_actualiza_sin_perderlos(base_nueva):
    command.upgrade(config_alembic(base_nueva), "0001")
    motor = create_engine(base_nueva)
    with motor.begin() as con:
        con.execute(text("INSERT INTO escenarios (nombre, turno_actual, fase, estado, creado_en) "
                         "VALUES ('Viejo', 3, 'decision', 'activo', '2026-01-01')"))
        for nombre, tipo in (("U1", "terrestre"), ("U2", "aerea")):
            con.execute(text(
                "INSERT INTO unidades (escenario_id, nombre, bando, tipo, echelon, lat, lon, fuerza, velocidad_kmh, "
                "alcance_km, deteccion_km, sidc, estado) VALUES "
                f"(1, '{nombre}', 'azul', '{tipo}', '', 8, -70, 80, 30, 10, 8, 'SFGP------', 'activa')"))
        for nombre, rol in (("prof", "instructor"), ("alfa", "azul")):
            con.execute(text("INSERT INTO usuarios (username, password_hash, rol, activo, creado_en) "
                             f"VALUES ('{nombre}', 'x', '{rol}', true, '2026-01-01')"))
    migrar(base_nueva)
    with motor.connect() as con:
        esc = con.execute(text("SELECT nombre, clima, azar, semilla, hora_inicio_min, com_perdida_pct FROM escenarios")).one()
        assert (esc.nombre, esc.clima, esc.azar, esc.hora_inicio_min, esc.com_perdida_pct) == ("Viejo", "despejado", False, 360, 0)
        assert 0 <= esc.semilla < 2**31
        u = {r.nombre: r for r in con.execute(text("SELECT nombre, clase, autonomia_km, fuerza, carga FROM unidades"))}
        assert (u["U1"].clase, u["U1"].autonomia_km, u["U1"].fuerza, u["U1"].carga) == ("infanteria", 300, 80, 0)
        assert (u["U2"].clase, u["U2"].autonomia_km) == ("caza", 1800)
        asignados = con.execute(text("SELECT COUNT(*) FROM asignaciones")).scalar()
        assert asignados == 1  # solo el alumno conserva su acceso; el instructor ve todo
        assert "alembic_version" in inspect(con).get_table_names()
    motor.dispose()


def test_migraciones_simultaneas_se_serializan_con_el_bloqueo_asesor(base_nueva):
    errores = []

    def correr():
        try:
            migrar(base_nueva)
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=correr) for _ in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []
    motor = create_engine(base_nueva)
    with motor.connect() as con:
        assert con.execute(text("SELECT version_num FROM alembic_version")).scalar() == _cabeza()
    motor.dispose()


# ---------------------------------------------------------------- copia SQLite -> PostgreSQL
@pytest.fixture()
def sqlite_con_datos(tmp_path):
    from app.models.aar import Combate
    from app.models.orden import Orden
    from app.models.usuario import Usuario

    url = f"sqlite:///{tmp_path / 'origen.db'}"
    migrar(url)
    motor = create_engine(url)
    with sessionmaker(bind=motor)() as db:
        db.add_all([Usuario(username="prof", password_hash="h", rol="instructor"),
                    Usuario(username="alfa", password_hash="h", rol="azul", activo=False)])
        esc = Escenario(nombre="Origen", clima="lluvia", azar=True, semilla=99, com_perdida_pct=15)
        db.add(esc)
        db.flush()
        a = Unidad(escenario_id=esc.id, nombre="A", bando="azul", tipo="terrestre", clase="infanteria", lat=8.5,
                   lon=-70.5, sidc="SFGP", carga=12.5)
        r = Unidad(escenario_id=esc.id, nombre="R", bando="rojo", tipo="terrestre", clase="infanteria", lat=8.6,
                   lon=-70.4, sidc="SHGP")
        db.add_all([a, r])
        db.flush()
        o = Orden(escenario_id=esc.id, unidad_id=a.id, tipo="atacar", objetivo_unidad_id=r.id, turno_emitida=1,
                  resultado="ok", detalle="")
        db.add(o)
        db.flush()
        db.add(Combate(escenario_id=esc.id, turno=1, orden_id=o.id, atacante_id=a.id, defensor_id=r.id,
                       atacante_nombre="A", defensor_nombre="R", atacante_bando="azul", defensor_bando="rojo",
                       ratio=1.5, fuerza_ini_atacante=100, fuerza_ini_defensor=100, perdida_atacante=10,
                       perdida_defensor=20, lat=8.6, lon=-70.4))
        db.commit()
    motor.dispose()
    return url


def test_copiar_traslada_todas_las_tablas_y_reajusta_las_secuencias(sqlite_con_datos, base_nueva):
    copiadas = migrar_a_postgres.copiar(sqlite_con_datos, base_nueva)
    assert copiadas["usuarios"] == 2 and copiadas["escenarios"] == 1 and copiadas["unidades"] == 2
    assert copiadas["ordenes"] == 1 and copiadas["combates"] == 1

    motor = create_engine(base_nueva)
    with sessionmaker(bind=motor)() as db:
        esc = db.query(Escenario).one()
        assert (esc.nombre, esc.clima, esc.azar, esc.semilla, esc.com_perdida_pct) == ("Origen", "lluvia", True, 99, 15)
        assert db.query(Unidad).filter_by(nombre="A").one().carga == 12.5
        assert [u.activo for u in db.query(__import__("app.models.usuario", fromlist=["Usuario"]).Usuario).order_by("id")] == [True, False]
        # las secuencias siguen a lo copiado: un registro nuevo no choca con los ids existentes
        nuevo = Escenario(nombre="Nuevo")
        db.add(nuevo)
        db.commit()
        assert nuevo.id == 2
        u = Unidad(escenario_id=nuevo.id, nombre="N", bando="azul", tipo="terrestre", lat=0, lon=0, sidc="x")
        db.add(u)
        db.commit()
        assert u.id == 3
    motor.dispose()


def test_copiar_no_pisa_un_destino_con_datos_salvo_que_se_fuerce(sqlite_con_datos, base_nueva):
    migrar_a_postgres.copiar(sqlite_con_datos, base_nueva)
    with pytest.raises(RuntimeError, match="ya tiene datos"):
        migrar_a_postgres.copiar(sqlite_con_datos, base_nueva)
    copiadas = migrar_a_postgres.copiar(sqlite_con_datos, base_nueva, forzar=True)
    assert copiadas["escenarios"] == 1
    motor = create_engine(base_nueva)
    with motor.connect() as con:
        assert con.execute(text("SELECT COUNT(*) FROM escenarios")).scalar() == 1  # no se duplico
        assert con.execute(text("SELECT COUNT(*) FROM unidades")).scalar() == 2
    motor.dispose()


def test_copiar_exige_un_destino_postgresql(sqlite_con_datos, tmp_path):
    with pytest.raises(ValueError, match="PostgreSQL"):
        migrar_a_postgres.copiar(sqlite_con_datos, f"sqlite:///{tmp_path / 'otro.db'}")


# ---------------------------------------------------------------- concurrencia
def test_dos_resoluciones_simultaneas_del_mismo_turno_solo_avanzan_una_vez(motor_postgres):
    """Instructor y temporizador (o dos procesos) pulsan a la vez: el bloqueo de fila evita el doble turno."""
    Session = sessionmaker(bind=motor_postgres)
    with Session() as db:
        for i in range(8):
            db.add(Escenario(nombre=f"carrera {i}"))
        db.commit()
        ids = [e.id for e in db.query(Escenario).order_by(Escenario.id)]
        for eid in ids:
            db.add(Unidad(escenario_id=eid, nombre="U", bando="azul", tipo="terrestre", lat=0, lon=0, sidc="x"))
        db.commit()

    resueltos: dict[int, int] = {eid: 0 for eid in ids}
    cedidos: dict[int, int] = {eid: 0 for eid in ids}
    errores: list = []
    barrera = threading.Barrier(len(ids) * 2)

    def resolver(eid):
        try:
            with Session() as db:
                esc = db.get(Escenario, eid)
                barrera.wait()  # todos arrancan a la vez
                if clock.avanzar_turno(db, esc, turno_esperado=1) is None:
                    cedidos[eid] += 1  # el otro proceso ya lo estaba resolviendo
                else:
                    resueltos[eid] += 1
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=resolver, args=(eid,)) for eid in ids for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert errores == [], f"el perdedor de la carrera fallo en lugar de ceder el turno: {errores[:1]}"
    assert all(v == 1 for v in resueltos.values()) and all(v == 1 for v in cedidos.values())
    with Session() as db:
        for eid in ids:
            esc = db.get(Escenario, eid)
            assert esc.turno_actual == 2, f"el escenario {eid} avanzo {esc.turno_actual - 1} veces"
            turnos = sorted(t for (t,) in db.query(Instantanea.turno).filter_by(escenario_id=eid))
            assert turnos == [0, 1]
