"""Apresto de las aeronaves en tierra (alerta 5, 15, 30, 60 min o mantenimiento) y rearme segun la carga
(engine/aeronaves.py)."""

import pytest

from app.engine import aeronaves, armas
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica


def _en_base(db, esc, **kw):
    base = _unidad(db, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)
    c = _unidad(db, esc, nombre="Caza", en_tierra=True, base_id=base.id, modelo="f16", **CAZA, **kw)
    return base, c


def test_despega_cuando_se_cumple_su_alerta(db_session):
    esc = _escenario(db_session)
    _, c = _en_base(db_session, esc, apresto_min=30)
    o = _orden(db_session, esc, c, "mover", waypoints=[[0.5, 0.0]])
    assert o.estado == "en_ejecucion" and c.en_tierra and c.despega_hasta == pytest.approx(1800)
    _correr(db_session, esc, 1500)
    assert c.en_tierra and (c.lat, c.lon) == (0.0, 0.0)  # todavia carreteando
    _correr(db_session, esc, 600)
    assert not c.en_tierra and c.lat > 0.0


def test_por_defecto_alerta_5_y_la_interceptacion_la_respeta(db_session):
    esc = _escenario(db_session)
    _, c = _en_base(db_session, esc, apresto_min=15)
    assert aeronaves.apresto(_unidad(db_session, esc, nombre="Otro", **CAZA)) == aeronaves.APRESTO_POR_DEFECTO
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.4, lon=0.0, **CAZA)
    o = _orden(db_session, esc, c, "interceptar", objetivo=intruso)
    assert "despega en 15 min" in o.resultado
    _correr(db_session, esc, 600)
    assert (c.lat, c.lon) == (0.0, 0.0)


def test_cancelar_la_orden_deja_la_aeronave_en_tierra(db_session):
    from app.engine import tiempo_real

    esc = _escenario(db_session)
    _, c = _en_base(db_session, esc)
    _orden(db_session, esc, c, "mover", waypoints=[[0.5, 0.0]])
    tiempo_real.cancelar_ordenes_de(db_session, c, "Detenida.", "08:00")
    _correr(db_session, esc, 900)
    assert c.en_tierra and c.despega_hasta is None


def test_el_rearme_depende_de_la_carga(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0)
    aa = _unidad(db_session, esc, nombre="AA", modelo="f16", **CAZA)
    armas.armar(aa, "aire_aire")
    bombas = _unidad(db_session, esc, nombre="Bombas", modelo="f16", **CAZA)
    armas.armar(bombas, "ataque")
    assert aeronaves.rearme_s(aa, base) == 45 * 60 and aeronaves.rearme_s(bombas, base) == 120 * 60


def test_api_apresto_y_mantenimiento(api, db_engine):
    from sqlalchemy.orm import sessionmaker

    from app.models.unidad import Unidad

    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    bc = prof.post(f"{base}/unidades", json=dict(nombre="BA", bando="azul", tipo="base", clase="base_aerea", lat=0.0, lon=0.0)).json()
    c = prof.post(f"{base}/unidades", json=dict(nombre="Caza", bando="azul", tipo="aerea", clase="caza", modelo="f16",
                                                 lat=0.0, lon=0.0)).json()
    with sessionmaker(bind=db_engine)() as db:  # estacionada en la base
        u = db.get(Unidad, c["id"])
        u.en_tierra, u.base_id = True, bc["id"]
        db.commit()
    assert alfa.post(f"{base}/unidades/{a['id']}/apresto", json={"minutos": 15}).status_code == 400  # no es aeronave
    assert alfa.post(f"{base}/unidades/{c['id']}/apresto", json={"minutos": 7}).status_code == 400
    assert alfa.post(f"{base}/unidades/{c['id']}/apresto", json={"minutos": 0}).json() == {"apresto_min": 0}
    vista = next(u for u in alfa.get(base).json()["unidades"] if u["id"] == c["id"])
    assert vista["apresto"]["nombre"] == "Mantenimiento"
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": c["id"], "tipo": "mover", "waypoints": [[0.2, 0.0]]})
    assert r.status_code == 400 and "mantenimiento" in r.json()["detail"].lower()
    alfa.post(f"{base}/unidades/{c['id']}/apresto", json={"minutos": 60})
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": c["id"], "tipo": "mover", "waypoints": [[0.2, 0.0]]})
    assert r.status_code == 200, r.text
    vista = next(u for u in alfa.get(base).json()["unidades"] if u["id"] == c["id"])
    assert vista["apresto"]["despega_en_min"] == 60
    assert next(u for u in api("bravo").get(base).json()["unidades"] if u["id"] == a["id"])["apresto"] is None
