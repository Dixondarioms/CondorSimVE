"""Daño por sistemas de buques y unidades de tierra y control de averias (engine/sistemas.py)."""

import json
from types import SimpleNamespace

import pytest

from app.engine import movimiento, sistemas, tiempo_real, vision
from app.models.evento import Evento
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica

FRAGATA = dict(tipo="naval", clase="fragata", velocidad_kmh=40, alcance_km=40, deteccion_km=30, autonomia_km=4000)
AGUA = TerrenoFalso(lambda lat, lon: "agua")


def test_los_impactos_criticos_danan_sistemas_reproducible(db_session):
    esc = _escenario(db_session)
    f = _unidad(db_session, esc, nombre="Fragata", **FRAGATA)
    sistemas.recibir(f, 50.0, 7, 100.0)  # 50 puntos: 2 impactos criticos
    d = sistemas.datos(f)
    assert 1 <= sum(1 for v in d.values() if v > 0) <= 2
    assert 2 * sistemas.DANO_IMPACTO[0] <= sum(d.values()) <= 2 * sistemas.DANO_IMPACTO[1]
    g = SimpleNamespace(id=f.id, tipo="naval", clase="fragata", sistemas_json=None)  # misma unidad, semilla e instante
    sistemas.recibir(g, 50.0, 7, 100.0)
    assert sistemas.datos(g) == d
    avion = _unidad(db_session, esc, nombre="Avion", tipo="aerea", clase="caza")
    assert sistemas.recibir(avion, 50.0, 7, 0.0) == [] and sistemas.publico(avion) is None


def test_efectos_sobre_deteccion_velocidad_y_armas(db_session):
    esc = _escenario(db_session)
    f = _unidad(db_session, esc, nombre="Fragata", **FRAGATA)
    blanco = _unidad(db_session, esc, nombre="Blanco", bando="rojo", tipo="naval", clase="patrullero", lat=0.2)
    radio = vision.radio_efectivo(f, blanco, AGUA)
    f.sistemas_json = json.dumps({"sensores": 50, "propulsion": 100})
    assert vision.radio_efectivo(f, blanco, AGUA) == pytest.approx(radio * 0.5)
    mov = movimiento.simular(f, [[0.5, 0.0]], AGUA, horas=1.0)
    assert mov.km_reales == 0 and "fuera de servicio" in mov.nota
    f.sistemas_json = json.dumps({"propulsion": 50})
    assert movimiento.simular(f, [[1.0, 0.0]], AGUA, horas=1.0).km_reales == pytest.approx(20.0, rel=0.05)
    assert sistemas.factor(f, "armas") == 1.0


def test_el_control_de_averias_repara_con_el_tiempo_y_en_puerto_del_todo(db_session):
    esc = _escenario(db_session)
    f = _unidad(db_session, esc, nombre="Fragata", **FRAGATA)
    f.sistemas_json = json.dumps({"armas": 30, "propulsion": 90})
    assert sistemas.reparar(f, 1.0, [f]) == []  # propulsion 90 -> 80: sigue fuera de servicio
    d = sistemas.datos(f)
    assert d["armas"] == pytest.approx(30 - sistemas.REPARACION_POR_HORA) and d["propulsion"] == pytest.approx(80)
    assert sistemas.reparar(f, 1.0, [f]) == ["propulsion"]  # 80 -> 70: vuelve a servicio
    sistemas.reparar(f, 10.0, [f])
    assert sistemas.datos(f)["armas"] == 0 and sistemas.datos(f)["propulsion"] == sistemas.AVERIA_GRAVE  # en el mar, no mas
    puerto = _unidad(db_session, esc, nombre="Puerto", tipo="base", clase="puerto", lat=0.01)
    sistemas.reparar(f, 10.0, [f, puerto])
    assert f.sistemas_json is None


def test_en_combate_los_sistemas_se_danan_y_caen_con_aviso(db_session):
    esc = _escenario(db_session)
    esc.semilla = 817030737  # los impactos criticos son al azar: semilla fija para que la prueba sea reproducible
    f = _unidad(db_session, esc, nombre="Fragata", **FRAGATA)
    atacante = _unidad(db_session, esc, nombre="Destructor", bando="rojo", tipo="naval", clase="destructor", lat=0.1,
                       alcance_km=60, deteccion_km=60, velocidad_kmh=0)
    _orden(db_session, esc, atacante, "atacar", objetivo=f)
    peor = 0.0
    while f.estado == "activa" and f.fuerza > 20:
        tiempo_real.paso(db_session, esc, 300, AGUA)
        db_session.commit()
        peor = max([peor, *sistemas.datos(f).values()])
    assert peor >= sistemas.DANO_IMPACTO[0]  # al menos un impacto critico en mas de 80 puntos de fuerza perdidos
    caidas = db_session.query(Evento).filter(Evento.descripcion.like("%fuera de servicio%")).count()
    assert (peor >= sistemas.FUERA_DE_SERVICIO) == (caidas >= 1)


def test_api_muestra_los_sistemas_solo_al_propio_bando(api):
    prof, base, a, r1, r2 = _preparar(api)
    est_azul = api("alfa").get(base).json()
    mia = next(u for u in est_azul["unidades"] if u["id"] == a["id"])
    assert set(mia["sistemas"]) == set(sistemas.SISTEMAS) and mia["sistemas"]["armas"]["dano"] == 0
    enemiga = next((u for u in est_azul["unidades"] if u["id"] == r1["id"]), None)
    assert enemiga is None or enemiga["sistemas"] is None
