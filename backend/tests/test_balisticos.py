"""Misiles balisticos y defensa antimisil (engine/balisticos.py)."""

import json

from app.engine import balisticos, tiempo_real
from app.models.evento import Evento
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import _orden, mundo_limpio  # noqa: F401 - fixture automatica

LANZADOR = dict(tipo="terrestre", clase="lanzador_balistico", velocidad_kmh=40, alcance_km=500, deteccion_km=10)


def _correr(db, esc, segundos):
    tiempo_real.paso(db, esc, segundos, TerrenoFalso())
    db.commit()


def _lanzar(db, esc, n=2, lat_blanco=2.0, quieto=True, **kw_blanco):
    lanzador = _unidad(db, esc, nombre="Iskander", bando="rojo", **LANZADOR)
    blanco = _unidad(db, esc, nombre="Deposito", lat=lat_blanco, velocidad_kmh=0 if quieto else 40, deteccion_km=5, **kw_blanco)
    _unidad(db, esc, nombre="Reco roja", bando="rojo", lat=lat_blanco - 0.05, deteccion_km=20)
    o = _orden(db, esc, lanzador, "lanzar", objetivo=blanco, detalle=json.dumps({"misiles": n}))
    return lanzador, blanco, o


def test_vuela_unos_minutos_y_cae_donde_estaba_el_blanco(db_session):
    esc = _escenario(db_session)
    lanzador, blanco, o = _lanzar(db_session, esc)  # 222 km: unos 2,7 minutos
    assert o.estado == "resuelta" and "impacto a las" in o.resultado and lanzador.municion == 50
    ms = db_session.query(Unidad).filter(Unidad.clase == "misil_balistico").all()
    assert len(ms) == 2 and balisticos.info(ms[0])["fase"] == "ascenso"
    alerta = db_session.query(Evento).filter(Evento.bando_destino == "azul", Evento.descripcion.like("%Alerta temprana%")).one()
    assert "misil(es) balístico(s)" in alerta.descripcion
    _correr(db_session, esc, 90)
    assert all(m.estado == "activa" for m in ms) and balisticos.fase(ms[0]) == "medio curso"
    _correr(db_session, esc, 120)
    assert all(m.estado == "destruida" for m in ms) and blanco.fuerza < 100


def test_si_el_blanco_se_movio_no_le_pega(db_session):
    esc = _escenario(db_session)
    _, blanco, _ = _lanzar(db_session, esc, quieto=False)
    _orden(db_session, esc, blanco, "mover", waypoints=[[2.0, 0.5]])
    _correr(db_session, esc, 300)  # en 3 minutos se alejo 2 km del punto de impacto
    assert blanco.fuerza == 100
    assert db_session.query(Evento).filter(Evento.descripcion.like("%el blanco ya no estaba%")).count() == 2


def test_la_antiaerea_comun_no_puede_y_el_antimisil_si(db_session):
    esc = _escenario(db_session)
    _, blanco, _ = _lanzar(db_session, esc, n=4)
    comun = _unidad(db_session, esc, nombre="Antiaerea", tipo="terrestre", clase="antiaerea", lat=2.0, alcance_km=20,
                    deteccion_km=60)
    s300 = _unidad(db_session, esc, nombre="S-300VM", tipo="terrestre", clase="antiaerea", modelo="s300vm", lat=2.01,
                   alcance_km=100, deteccion_km=200)
    assert balisticos.antimisil(s300) and not balisticos.antimisil(comun)
    municion_comun = comun.municion
    _correr(db_session, esc, 300)
    assert comun.municion == municion_comun  # no tiro
    ev = db_session.query(Evento).filter(Evento.descripcion.like("%interceptor(es) antimisil%")).all()
    assert ev and blanco.fuerza > 100 - 4 * 30  # algunos misiles derribados en la fase terminal


def test_api_lanzar_balistico(api):
    prof, base, a, r1, r2 = _preparar(api)
    lanz = prof.post(f"{base}/unidades", json=dict(nombre="Iskander", bando="azul", tipo="terrestre",
                                                    clase="lanzador_balistico", lat=0.0, lon=0.01)).json()
    alfa = api("alfa")
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": lanz["id"], "tipo": "lanzar", "objetivo_unidad_id": r1["id"], "misiles": 2})
    assert r.status_code == 200, r.text
    assert "balístico" in r.json()["resultado"]
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": lanz["id"], "tipo": "lanzar", "objetivo_unidad_id": r1["id"], "misiles": 9})
    assert r.status_code == 422
