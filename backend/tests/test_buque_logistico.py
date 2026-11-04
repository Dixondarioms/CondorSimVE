"""Reabastecimiento en el mar: el buque logistico reabastece a los buques propios cercanos y se recarga en puerto."""

from app import adversario
from app.engine import catalogo, contramedidas, puestos, tiempo_real
from tests.test_orders import _escenario, _unidad
from tests.test_salvas import AGUA
from tests.test_tiempo_real import mundo_limpio  # noqa: F401 - fixture automatica

LOGISTICO = dict(tipo="naval", clase="buque_logistico", velocidad_kmh=35, alcance_km=5, deteccion_km=20)


def test_reabastece_en_el_mar_y_repone_los_senuelos(db_session):
    esc = _escenario(db_session)
    log = _unidad(db_session, esc, nombre="Petrolero", carga=300.0, **LOGISTICO)
    f = _unidad(db_session, esc, nombre="Fragata", tipo="naval", clase="fragata", lat=0.02, velocidad_kmh=0,
                combustible=30.0, municion=20.0, contramedidas=1)
    lejos = _unidad(db_session, esc, nombre="Lejos", tipo="naval", clase="fragata", lat=0.5, velocidad_kmh=0, combustible=30.0)
    tiempo_real.paso(db_session, esc, 3600, AGUA)
    db_session.commit()
    assert f.combustible > 60 and f.municion > 50 and contramedidas.quedan(f) == contramedidas.maximo(f)
    assert lejos.combustible <= 30.0 and log.carga < 300.0


def test_se_recarga_en_puerto_lo_ordena_a4_y_la_ia_lo_lleva_a_los_buques(db_session):
    esc = _escenario(db_session)
    esc.ia_azul = True
    _unidad(db_session, esc, nombre="Puerto", tipo="base", clase="puerto", velocidad_kmh=0, alcance_km=25)
    log = _unidad(db_session, esc, nombre="Petrolero", carga=10.0, **LOGISTICO)
    tiempo_real.paso(db_session, esc, 3600, AGUA)
    db_session.commit()
    assert log.carga > 10.0
    clase = catalogo.CLASES["buque_logistico"]
    assert puestos.funcion_de_orden(log, "mover", clase) == puestos.funcion_de_orden(
        _unidad(db_session, esc, nombre="Convoy", clase="transporte", carga=50.0), "mover", catalogo.CLASES["transporte"])
    _unidad(db_session, esc, nombre="Fragata sedienta", tipo="naval", clase="fragata", lat=0.6, combustible=20.0)
    log.carga = 200.0
    db_session.commit()
    r = adversario.jugar_turno(db_session, esc, AGUA)
    assert any("Petrolero" in d for d in r.get("azul", []))
