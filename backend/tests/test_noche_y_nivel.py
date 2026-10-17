"""Ciclo de dia y noche (la deteccion a simple vista baja de noche; el radar no) y niveles del adversario automatico."""

from types import SimpleNamespace

from app import adversario
from app.engine import clima as clima_mod
from app.engine import vision
from tests.conftest import TerrenoFalso
from tests.test_adversario import _jugar, _ordenes
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad


def test_periodo_del_dia_segun_la_hora_simulada():
    assert clima_mod.periodo_del_dia(8 * 60, 1) == "dia"
    assert clima_mod.periodo_del_dia(6 * 60, 1) == "crepusculo"
    assert clima_mod.periodo_del_dia(17 * 60, 2) == "crepusculo"  # turno 2 = 18:00
    assert clima_mod.periodo_del_dia(60, 1) == "noche"  # 01:00, como el ataque del 3 de enero
    assert clima_mod.periodo_del_dia(22 * 60, 4) == "noche"  # pasa de medianoche: 01:00


def test_sin_ciclo_siempre_es_de_dia():
    esc = SimpleNamespace(dia_noche=False, hora_inicio_min=60, turno_actual=1)
    assert clima_mod.periodo_de(esc) == "dia"
    esc.dia_noche = True
    assert clima_mod.periodo_de(esc) == "noche"


def test_el_radar_no_depende_de_la_luz():
    radar = SimpleNamespace(emisor=True, solo_aereo=True, tipo="terrestre", dron=False, id="radar")
    tropa = SimpleNamespace(emisor=False, solo_aereo=False, tipo="terrestre", dron=False, id="infanteria")
    avion = SimpleNamespace(emisor=False, solo_aereo=False, tipo="aerea", dron=False, id="caza")
    assert clima_mod.factor_nocturno(radar, "noche") == 1.0
    assert clima_mod.factor_nocturno(tropa, "noche") == 0.5
    assert clima_mod.factor_nocturno(avion, "noche") == 0.8
    assert clima_mod.factor_nocturno(tropa, "dia") == 1.0


def test_de_noche_la_tropa_ve_la_mitad(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A", bando="azul", lat=0.0, lon=0.0, deteccion_km=10)
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.063, lon=0.0, deteccion_km=10)  # 7 km
    unidades = [a, r]
    de_dia = vision.unidades_visibles(unidades, "azul", TerrenoFalso(), clima_mod.ClimaLocal(periodo="dia"))
    de_noche = vision.unidades_visibles(unidades, "azul", TerrenoFalso(), clima_mod.ClimaLocal(periodo="noche"))
    assert r in de_dia and r not in de_noche


def _persigue(db, nivel):
    esc = _escenario(db)
    esc.ia_rojo = True
    esc.ia_nivel = nivel
    db.commit()
    _unidad(db, esc, nombre="A", bando="azul", lat=0.0, lon=0.0, deteccion_km=5)
    rojo = _unidad(db, esc, nombre="R", bando="rojo", lat=0.9, lon=0.0, alcance_km=10, deteccion_km=120)  # 100 km
    _jugar(db, esc)
    return rojo.id in _ordenes(db, esc)


def test_la_ia_agresiva_persigue_mas_lejos_que_la_normal(db_session):
    assert not _persigue(db_session, "normal")
    assert _persigue(db_session, "agresiva")


def test_niveles_conocidos():
    assert set(adversario.NIVELES) == {"prudente", "normal", "agresiva"}
    p, n, a = (adversario.NIVELES[k] for k in ("prudente", "normal", "agresiva"))
    assert p["relacion"] > n["relacion"] > a["relacion"]
    assert p["persecucion_km"] < n["persecucion_km"] < a["persecucion_km"]


def test_el_instructor_cambia_nivel_y_ciclo_desde_la_consola(api):
    prof, base, *_ = _preparar(api)
    r = prof.patch(f"{base}/config", json={"ia_nivel": "agresiva", "dia_noche": True})
    assert r.status_code == 200, r.text
    esc = r.json()["escenario"]
    assert esc["ia_nivel"] == "agresiva" and esc["dia_noche"] is True and esc["periodo"] in clima_mod.PERIODOS
    assert prof.patch(f"{base}/config", json={"ia_nivel": "temeraria"}).status_code == 422
    eventos = prof.get(base).json()["eventos"]
    assert any("ciclo de dia y noche activado" in ev["descripcion"] for ev in eventos)
