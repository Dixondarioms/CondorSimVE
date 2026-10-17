"""Comunicaciones que pesan en la operacion: ordenes que no llegan a tiempo y se cumplen el turno siguiente."""

from types import SimpleNamespace

from app.engine import guerra_electronica as ge_mod
from app.engine import orders
from app.models.evento import Evento
from tests.test_orders import _avanzar, _escenario, _orden, _unidad


def test_la_orden_que_no_llega_a_tiempo_se_cumple_el_turno_siguiente(db_session, monkeypatch):
    esc = _escenario(db_session)
    esc.com_ordenes_pct = 100
    db_session.commit()
    # la demora tiene un tope (DEMORA_MAXIMA_PCT = 90 %) y la semilla del escenario es al azar: sin esto, 1 de cada
    # 10 veces la orden llegaria a tiempo. Aqui se prueba lo que pasa cuando no llega.
    monkeypatch.setattr(orders, "prob_demora", lambda *a, **k: 1.0)
    u = _unidad(db_session, esc, velocidad_kmh=30.0)
    o = _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc)
    db_session.refresh(u)
    db_session.refresh(o)
    assert u.lat == 0.0 and o.estado == "pendiente"
    aviso = db_session.query(Evento).filter(Evento.tipo == "comunicaciones").one()
    assert aviso.bando_destino == "azul" and "no llego a tiempo" in aviso.descripcion
    _avanzar(db_session, esc)  # ya demorada una vez: se cumple
    db_session.refresh(u)
    db_session.refresh(o)
    assert o.estado == "resuelta" and u.lat > 0.1


def test_sin_demora_configurada_todas_llegan(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=30.0)
    o = _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "resuelta"


def test_la_interferencia_enemiga_aumenta_la_demora():
    esc = SimpleNamespace(com_ordenes_pct=20)
    u = SimpleNamespace(bando="azul", lat=0.0, lon=0.0)
    zona = SimpleNamespace(bando="rojo", lat=0.0, lon=0.0, radio_km=25, unidad_id=None)
    assert orders.prob_demora(esc, u, ge_mod.Contexto()) == 0.2
    assert orders.prob_demora(esc, u, ge_mod.Contexto([zona])) == 0.6
    assert orders.prob_demora(SimpleNamespace(com_ordenes_pct=0), u, ge_mod.Contexto([zona])) == 0.0
