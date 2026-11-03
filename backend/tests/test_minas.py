"""Minas navales: sembrar, riesgo al cruzar, descubrir y barrer (engine/minas.py)."""

import json

import pytest

from app.engine import minas, tiempo_real
from app.models.mina import CampoMinas
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _orden, mundo_limpio  # noqa: F401 - fixture automatica

AGUA = TerrenoFalso(lambda lat, lon: "agua")
KM = 1 / 111.2
PATRULLERO = dict(tipo="naval", clase="patrullero", velocidad_kmh=55, alcance_km=20, deteccion_km=20, autonomia_km=1500)


def _correr(db, esc, segundos):
    tiempo_real.paso(db, esc, segundos, AGUA)
    db.commit()


def _campo(db, esc, bando="rojo", lat=0.0, lon=0.0):
    c = CampoMinas(escenario_id=esc.id, bando=bando, lat=lat, lon=lon, radio_km=minas.RADIO_KM, densidad=1.0,
                   conocido_por="[]")
    db.add(c)
    db.commit()
    return c


def test_el_buque_siembra_un_campo_tras_media_hora(db_session):
    esc = _escenario(db_session)
    p = _unidad(db_session, esc, nombre="Minador", **PATRULLERO)
    o = _orden(db_session, esc, p, "minar", waypoints=[[10 * KM, 0.0]])
    _correr(db_session, esc, 900)
    assert db_session.query(CampoMinas).count() == 0 and "Sembrando" in o.resultado
    _correr(db_session, esc, minas.SIEMBRA_BUQUE_S)
    c = db_session.query(CampoMinas).one()
    assert c.bando == "azul" and o.estado == "resuelta" and p.municion == 100 - minas.MUNICION_POR_CAMPO
    assert minas.conocido(c, "azul") and not minas.conocido(c, "rojo")


def test_la_aeronave_siembra_en_una_pasada(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="Su-24", clase="ataque", **{k: v for k, v in CAZA.items() if k != "clase"})
    o = _orden(db_session, esc, a, "minar", waypoints=[[0.3, 0.0]])
    _correr(db_session, esc, 300)
    assert o.estado == "resuelta" and db_session.query(CampoMinas).count() == 1


def test_cruzar_un_campo_dana_y_lo_descubre(db_session):
    esc = _escenario(db_session)  # sin azar: el daño esperado
    c = _campo(db_session, esc)
    b = _unidad(db_session, esc, nombre="Fragata", tipo="naval", clase="fragata", lat=-5 * KM, velocidad_kmh=40,
                alcance_km=40, deteccion_km=30, autonomia_km=4000)
    _orden(db_session, esc, b, "mover", waypoints=[[5 * KM, 0.0]])
    _correr(db_session, esc, 1200)  # 10 km, 6 dentro del campo
    assert b.fuerza < 100 and minas.conocido(c, "azul") and c.densidad < 1.0
    esperado = 6 * minas.RIESGO_POR_KM * sum(minas.DANO_MINA) / 2
    assert 100 - b.fuerza == pytest.approx(esperado, rel=0.35)


def test_el_cazaminas_lo_descubre_y_lo_barre(db_session):
    esc = _escenario(db_session)
    c = _campo(db_session, esc)
    cm = _unidad(db_session, esc, nombre="Cazaminas", tipo="naval", clase="cazaminas", lat=-7 * KM, velocidad_kmh=25,
                 alcance_km=5, deteccion_km=15, autonomia_km=3000)
    _correr(db_session, esc, 30)
    assert minas.conocido(c, "azul")  # lo detecta a 5 km del borde
    o = _orden(db_session, esc, cm, "barrer", waypoints=[[0.0, 0.0]])
    _correr(db_session, esc, 5 * 3600)
    db_session.refresh(c)
    assert c.densidad == 0 and o.estado == "resuelta" and cm.fuerza > 90  # poco riesgo para el cazaminas


def test_api_minas_y_estado(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "minar", "waypoints": [[0.1, 0.1]]})
    assert r.status_code == 400 and "Siembran minas" in r.json()["detail"]
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "barrer", "waypoints": [[0.1, 0.1]]})
    assert r.status_code == 400 and "cazaminas" in r.json()["detail"]
    assert alfa.get(base).json()["minas"] == []
    assert alfa.get("/api/catalogo").json()["minas"]["minas"] == minas.MINAS_POR_CAMPO
    assert json.loads("[]") == []
