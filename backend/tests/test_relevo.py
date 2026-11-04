"""Patrulla permanente: la base manda el relevo antes de que la aeronave que patrulla se vaya (tiempo_real._relevos)."""

import json

from app.models.evento import Evento
from app.models.orden import Orden
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica


def _patrulla(db, combustible):
    esc = _escenario(db)
    base = _unidad(db, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)
    p = _unidad(db, esc, nombre="Patrulla 1", lat=0.5, combustible=combustible, **CAZA)
    reserva = _unidad(db, esc, nombre="Reserva", en_tierra=True, base_id=base.id, **CAZA)
    o = _orden(db, esc, p, "patrullar", waypoints=[[0.5, 0.0]], detalle=json.dumps({"permanente": True}))
    return esc, p, reserva, o


def test_sale_el_relevo_cuando_le_queda_poco_combustible_y_una_sola_vez(db_session):
    esc, p, reserva, o = _patrulla(db_session, 40.0)
    _correr(db_session, esc, 60)
    relevo = db_session.query(Orden).filter(Orden.unidad_id == reserva.id).one()
    assert relevo.tipo == "patrullar" and json.loads(relevo.detalle) == {"permanente": True, "relevo_de": o.id}
    assert relevo.waypoints == [[0.5, 0.0]]
    assert any("Relevo: Reserva" in e.descripcion for e in db_session.query(Evento))
    _correr(db_session, esc, 600)
    assert db_session.query(Orden).filter(Orden.unidad_id == reserva.id).count() == 1
    assert not reserva.en_tierra  # despego (alerta 5)


def test_con_combustible_de_sobra_no_y_sin_reserva_avisa(db_session):
    esc, p, reserva, o = _patrulla(db_session, 90.0)
    _correr(db_session, esc, 60)
    assert db_session.query(Orden).filter(Orden.unidad_id == reserva.id).count() == 0
    reserva.apresto_min = 0  # en mantenimiento: no sirve de relevo
    p.combustible = 40.0
    db_session.commit()
    _correr(db_session, esc, 60)
    assert db_session.query(Orden).filter(Orden.unidad_id == reserva.id).count() == 0
    assert any("No hay aeronaves listas" in e.descripcion for e in db_session.query(Evento))


def test_api_patrulla_permanente(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    c = prof.post(f"{base}/unidades", json=dict(nombre="Caza", bando="azul", tipo="aerea", clase="caza", lat=0.0, lon=0.0)).json()
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": c["id"], "tipo": "patrullar", "waypoints": [[0.1, 0.1]], "permanente": True})
    assert r.status_code == 200, r.text
    assert json.loads(r.json()["detalle"]) == {"permanente": True}
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.01, 0.0]], "permanente": True})
    assert r.status_code == 400
