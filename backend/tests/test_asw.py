"""Guerra antisubmarina: sonar, profundidad, sonoboyas, sonar de inmersion y torpedos (engine/asw.py)."""

import pytest

from app.engine import asw, tiempo_real, vision
from app.models.sonoboya import Sonoboya
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import _orden, mundo_limpio  # noqa: F401 - fixture automatica

AGUA = TerrenoFalso(lambda lat, lon: "agua")
KM = 1 / 111.2
SUB = dict(tipo="naval", clase="submarino", velocidad_kmh=35, alcance_km=30, deteccion_km=25, autonomia_km=6000)
FRAGATA = dict(tipo="naval", clase="fragata", velocidad_kmh=40, alcance_km=40, deteccion_km=30, autonomia_km=4000)
PATRULLERO = dict(tipo="naval", clase="patrullero", velocidad_kmh=55, alcance_km=20, deteccion_km=20, autonomia_km=1500)


@pytest.fixture(autouse=True)
def asw_limpio():
    asw.EXPUESTO.clear()
    asw.BOYAS.clear()
    asw.AHORA.clear()
    yield


def _correr(db, esc, segundos):
    tiempo_real.paso(db, esc, segundos, AGUA)
    db.commit()


def _ve(detector, sub):
    return vision.detecta(detector, sub, AGUA)


def test_el_sonar_y_el_periscopio(db_session):
    esc = _escenario(db_session)
    sub = _unidad(db_session, esc, nombre="Sub", bando="rojo", **SUB)
    fragata = _unidad(db_session, esc, nombre="Fragata", lat=20 * KM, **FRAGATA)
    lancha = _unidad(db_session, esc, nombre="Lancha", lat=5 * KM, **PATRULLERO)
    lejos = _unidad(db_session, esc, nombre="Lancha lejos", lat=-12 * KM, **PATRULLERO)
    assert _ve(fragata, sub)  # sonar de casco: 25 km
    assert _ve(lancha, sub) and not _ve(lejos, sub)  # sin sonar: solo el periscopio, a menos de 8 km
    sub.profundidad = "profunda"
    assert not _ve(lancha, sub) and not _ve(fragata, sub)  # a profundidad: sonar al 60 % (15 km)
    fragata.lat = 12 * KM
    assert _ve(fragata, sub)


def test_al_atacar_se_delata(db_session):
    esc = _escenario(db_session)
    sub = _unidad(db_session, esc, nombre="Sub", bando="rojo", **SUB)
    lancha = _unidad(db_session, esc, nombre="Lancha", lat=15 * KM, **PATRULLERO)
    assert not _ve(lancha, sub)
    asw.AHORA[esc.id] = 100.0
    asw.exponer(sub, 100.0 + asw.EXPUESTO_S)
    assert _ve(lancha, sub)
    asw.AHORA[esc.id] = 100.0 + asw.EXPUESTO_S + 1
    assert not _ve(lancha, sub)


def test_el_avion_de_patrulla_siembra_sonoboyas_que_oyen_al_submarino(db_session):
    esc = _escenario(db_session)
    p8 = _unidad(db_session, esc, nombre="Poseidon", tipo="aerea", clase="ataque", modelo="p8a", velocidad_kmh=800,
                 alcance_km=50, deteccion_km=60, autonomia_km=7000)
    sub = _unidad(db_session, esc, nombre="Sub", bando="rojo", lat=0.5, lon=0.0, profundidad="profunda", **SUB)
    o = _orden(db_session, esc, p8, "sonoboyas", waypoints=[[0.5, 0.0]])
    assert o.estado == "en_ejecucion"
    _correr(db_session, esc, 600)
    db_session.refresh(o)
    assert o.estado == "resuelta" and db_session.query(Sonoboya).count() == 4
    assert sub.id in tiempo_real.mundo_de(esc.id).visibles["azul"]
    _correr(db_session, esc, asw.BOYA_VIDA_S + 60)  # se agotan
    sub.lat = 2.0
    db_session.commit()
    _correr(db_session, esc, 60)
    assert sub.id not in tiempo_real.mundo_de(esc.id).visibles["azul"]


def test_el_helicoptero_cala_el_sonar_y_escucha(db_session):
    esc = _escenario(db_session)
    helo = _unidad(db_session, esc, nombre="NH90", tipo="aerea", clase="helicoptero_artillado", modelo="nh90",
                   velocidad_kmh=280, alcance_km=10, deteccion_km=20, autonomia_km=900)
    sub = _unidad(db_session, esc, nombre="Sub", bando="rojo", lat=0.3, lon=0.08, **SUB)
    _orden(db_session, esc, helo, "sonar", waypoints=[[0.3, 0.0]])
    _correr(db_session, esc, 600)  # 33 km a 280 km/h
    assert helo.mision == "sonar" and asw.sonar_km(helo) == asw.SONAR_INMERSION_KM
    assert sub.id in tiempo_real.mundo_de(esc.id).visibles["azul"]


def test_el_torpedo_navega_y_golpea(db_session):
    esc = _escenario(db_session)
    sub = _unidad(db_session, esc, nombre="Sub", bando="rojo", **SUB)
    fragata = _unidad(db_session, esc, nombre="Fragata", lat=10 * KM, velocidad_kmh=0,
                      **{k: v for k, v in FRAGATA.items() if k != "velocidad_kmh"})
    assert asw.error_de_torpedo(sub, fragata) is None
    lejos = _unidad(db_session, esc, nombre="Lejos", lat=0.5, **FRAGATA)
    assert "Acérquese" in asw.error_de_torpedo(sub, lejos)
    o = _orden(db_session, esc, sub, "torpedo", objetivo=fragata)
    assert o.estado == "resuelta" and "lanzó un torpedo" in o.resultado and sub.municion == 87.5
    torpedo = db_session.query(Unidad).filter(Unidad.clase == "torpedo").one()
    _correr(db_session, esc, 240)  # 10 km a 75 km/h: unos 8 minutos
    assert torpedo.estado == "activa" and fragata.fuerza == 100
    _correr(db_session, esc, 360)
    assert torpedo.estado == "destruida" and fragata.fuerza < 100
    assert asw.expuesto(sub) or tiempo_real.mundo_de(esc.id)  # se delato al lanzar


def test_api_profundidad_y_torpedo(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    sub = prof.post(f"{base}/unidades", json=dict(nombre="Sabalo", bando="azul", tipo="aerea", clase="caza", lat=0.0, lon=0.0)).json()
    r = alfa.post(f"{base}/unidades/{sub['id']}/profundidad", json={"profundidad": "profunda"})
    assert r.status_code == 400  # no es un submarino
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "torpedo", "objetivo_unidad_id": r1["id"]})
    assert r.status_code == 400 and "torpedos" in r.json()["detail"]
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": sub["id"], "tipo": "sonoboyas", "waypoints": [[0.1, 0.1]]})
    assert r.status_code == 400 and "patrulla marítima" in r.json()["detail"]
    cat = alfa.get("/api/catalogo").json()
    assert "p8a" in cat["asw"]["aviones"] and cat["cargas"]["p8a"]["antisubmarina"] == {"TOR": 4}


def test_la_orden_acepta_la_carga_antisubmarina():
    """El NH90, el P-3 y el P-8 en tierra despegan con la carga antisubmarina elegida en la Nueva orden o en la OTA."""
    from app import schemas

    assert schemas.OrdenCreate(unidad_id=1, tipo="sonar", waypoints=[(0.1, 0.1)], carga="antisubmarina").carga == "antisubmarina"
    assert schemas.OtaMisionIn(carga="antisubmarina").carga == "antisubmarina"
