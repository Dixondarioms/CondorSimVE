"""Imagen comun por enlace de datos (engine/enlace.py): lo que ve una unidad fuera de la red no lo ve su bando."""

from app import state
from app.engine import enlace
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import mundo_limpio  # noqa: F401 - fixture automatica


def _cuadro(db):
    esc = _escenario(db)
    _unidad(db, esc, nombre="Radar", clase="radar", lat=0.0, lon=0.0, deteccion_km=5, velocidad_kmh=0)
    cerca = _unidad(db, esc, nombre="Patrulla cerca", clase="reconocimiento", lat=0.3, deteccion_km=20)  # 33 km
    lejos = _unidad(db, esc, nombre="Patrulla lejos", clase="reconocimiento", lat=2.0, deteccion_km=20)  # 222 km
    r1 = _unidad(db, esc, nombre="Rojo 1", bando="rojo", lat=0.35, deteccion_km=1)
    r2 = _unidad(db, esc, nombre="Rojo 2", bando="rojo", lat=2.05, deteccion_km=1)
    return esc, cerca, lejos, r1, r2


def test_solo_comparte_lo_que_ven_las_unidades_en_la_red(db_session):
    esc, cerca, lejos, r1, r2 = _cuadro(db_session)
    ids = lambda: {u.id for u in state.unidades_visibles_para(db_session, esc, "azul")}  # noqa: E731
    assert {r1.id, r2.id} <= ids()  # apagado: el bando ve todo lo que ve cualquiera
    esc.enlace_datos = True
    db_session.commit()
    red = enlace.enlazadas(db_session.query(type(cerca)).filter_by(escenario_id=esc.id).all(), "azul")
    assert cerca.id in red and lejos.id not in red
    assert r1.id in ids() and r2.id not in ids()
    vista = {u["nombre"]: u for u in state.estado_para(db_session, esc, "azul")["unidades"]}
    assert vista["Patrulla lejos"]["enlace"] is False and vista["Patrulla cerca"]["enlace"] is True
    assert "Rojo 2" not in vista


def test_la_red_se_extiende_de_unidad_en_unidad_y_la_interferencia_la_corta(db_session):
    esc, cerca, lejos, r1, r2 = _cuadro(db_session)
    puente = _unidad(db_session, esc, nombre="Avion", tipo="aerea", clase="caza", lat=1.2, deteccion_km=60)
    todas = db_session.query(type(cerca)).filter_by(escenario_id=esc.id).all()
    assert {puente.id, lejos.id} <= enlace.enlazadas(todas, "azul")  # el avion enlaza a la patrulla lejana

    class GE:
        def interferido(self, u):
            return u.id == puente.id
    assert lejos.id not in enlace.enlazadas(todas, "azul", GE())


def test_api_el_director_la_enciende(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.patch(f"{base}/config", json={"enlace_datos": True})
    assert r.status_code == 200, r.text
    assert prof.get(base).json()["escenario"]["enlace_datos"] is True


def test_el_descarte_rapido_por_distancia_no_cambia_lo_que_se_ve(db_session):
    """vision._cota_km: mas alla de la cota no hace falta el calculo fino; con y sin el descarte se ve lo mismo."""
    from app.engine import vision
    from tests.conftest import TerrenoFalso

    esc, cerca, lejos, r1, r2 = _cuadro(db_session)
    todas = db_session.query(type(cerca)).filter_by(escenario_id=esc.id).all()
    for d in todas:
        for o in todas:
            if d.bando != o.bando:
                radio = vision.radio_efectivo(d, o, TerrenoFalso())
                assert radio <= vision._cota_km(d)
    ve = {u.id for u in vision.unidades_visibles(todas, "azul", TerrenoFalso())}
    assert {r1.id, r2.id} <= ve
