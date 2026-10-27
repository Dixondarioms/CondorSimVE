"""Indicadores doctrinales con calificacion de 1 a 20 y comparacion de ejercicios."""

from app.engine import aar
from app.models.aar import Combate
from app.models.orden import Orden
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad


def _combate(db, esc, turno, atacante, defensor):
    db.add(Combate(escenario_id=esc.id, turno=turno, atacante_id=atacante.id, defensor_id=defensor.id,
                   atacante_nombre=atacante.nombre, defensor_nombre=defensor.nombre, atacante_bando=atacante.bando,
                   defensor_bando=defensor.bando, ratio=1.0, fuerza_ini_atacante=100, fuerza_ini_defensor=100,
                   perdida_atacante=5, perdida_defensor=10, lat=0, lon=0))


def test_la_rubrica_trae_indicadores_doctrinales_y_una_nota_de_1_a_20(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", bando="azul")
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05)
    _combate(db_session, esc, 1, r, a)  # el rojo ataca en el turno 1...
    db_session.add(Orden(escenario_id=esc.id, unidad_id=a.id, tipo="atacar", objetivo_unidad_id=r.id,
                         turno_emitida=2, estado="resuelta"))  # ...y el azul responde en el 2
    esc.turno_actual = 3
    db_session.commit()
    d = aar.construir_rubrica(db_session, esc)["bandos"]["azul"]["doctrina"]
    ind = {i["id"]: i for i in d["indicadores"]}
    assert ind["reaccion"]["puntaje"] == 100 and "1.0 hora" in ind["reaccion"]["valor"]
    assert ind["coordinacion"]["puntaje"] is None  # nadie trabajo con puestos especializados
    assert ind["economia"]["puntaje"] == round(100 * 5 / 15)  # el azul inflige 5 y sufre 10
    assert 1 <= d["nota"] <= 20 and all(i["criterio"] for i in d["indicadores"])
    rojo = {i["id"]: i for i in aar.construir_rubrica(db_session, esc)["bandos"]["rojo"]["doctrina"]["indicadores"]}
    assert rojo["reaccion"]["puntaje"] is None  # el azul nunca lo ataco primero


def test_la_amenaza_sin_respuesta_baja_la_reaccion(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", bando="azul")
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05)
    _combate(db_session, esc, 1, r, a)
    esc.turno_actual = 4
    db_session.commit()
    ind = {i["id"]: i for i in aar.construir_rubrica(db_session, esc)["bandos"]["azul"]["doctrina"]["indicadores"]}
    assert ind["reaccion"]["puntaje"] == 0 and "sin respuesta" in ind["reaccion"]["valor"]


def test_comparar_ejercicios(api):
    prof, base, *_ = _preparar(api)
    otro = prof.post("/api/escenarios", json={"nombre": "Segundo"}).json()["id"]
    primero = int(base.rsplit("/", 1)[1])
    r = prof.get(f"/api/evaluacion/comparar?ids={primero},{otro}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert [e["id"] for e in d["ejercicios"]] == [primero, otro]
    assert "reaccion" in d["indicadores"] and set(d["ejercicios"][0]["bandos"]) == {"azul", "rojo"}
    assert prof.get("/api/evaluacion/comparar?ids=x").status_code == 400
    assert prof.get("/api/evaluacion/comparar?ids=99999").status_code == 404
    assert api("alfa").get(f"/api/evaluacion/comparar?ids={primero}").status_code == 403
