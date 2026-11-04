"""Estado del mar (engine/mar.py): sonar del helicoptero, sonoboyas, sonares, buques chicos y reabastecimiento."""

from types import SimpleNamespace

from app.engine import asw, mar, movimiento, tiempo_real
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_salvas import AGUA
from tests.test_tiempo_real import mundo_limpio  # noqa: F401 - fixture automatica


def _con_mar(esc_id, estado):
    mar.fijar(SimpleNamespace(id=esc_id, estado_mar=estado))


def test_con_mar_gruesa_el_helicoptero_no_cala_el_sonar_y_los_sonares_oyen_menos():
    helo = SimpleNamespace(escenario_id=901, tipo="aerea", modelo="nh90", clase="helicoptero_artillado", en_tierra=False,
                           mision="sonar", mision_lat=0.0, mision_lon=0.0, lat=0.0, lon=0.0)
    fragata = SimpleNamespace(escenario_id=901, tipo="naval", clase="fragata", sistemas_json=None)
    _con_mar(901, "calmo")
    assert asw.sonar_km(helo) == asw.SONAR_INMERSION_KM
    calmo = asw.sonar_km(fragata)
    _con_mar(901, "grueso")
    assert asw.sonar_km(helo) == 0.0 and asw.sonar_km(fragata) < calmo
    assert mar.factor_boyas(fragata) < 1.0 and not mar.reabastecer_en_el_mar(fragata)


def test_el_oleaje_frena_a_los_buques_chicos(db_session):
    esc = _escenario(db_session)
    lancha = _unidad(db_session, esc, nombre="Lancha", tipo="naval", clase="patrullero", velocidad_kmh=60)
    _con_mar(esc.id, "calmo")
    calmo = movimiento.simular(lancha, [[0.0, 3.0]], AGUA, horas=0.5).km_reales
    _con_mar(esc.id, "muy_grueso")
    assert movimiento.simular(lancha, [[0.0, 3.0]], AGUA, horas=0.5).km_reales < calmo * 0.6


def test_con_mar_gruesa_no_se_reabastece_en_el_mar(db_session):
    esc = _escenario(db_session)
    esc.estado_mar = "grueso"
    _unidad(db_session, esc, nombre="Petrolero", tipo="naval", clase="buque_logistico", velocidad_kmh=0, carga=300.0)
    f = _unidad(db_session, esc, nombre="Fragata", tipo="naval", clase="fragata", lat=0.02, velocidad_kmh=0, combustible=30.0)
    tiempo_real.paso(db_session, esc, 3600, AGUA)
    db_session.commit()
    assert f.combustible <= 30.0


def test_api_el_director_fija_el_estado_del_mar(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert prof.patch(f"{base}/config", json={"estado_mar": "grueso"}).status_code == 200
    assert prof.get(base).json()["escenario"]["estado_mar"] == "grueso"
    assert prof.patch(f"{base}/config", json={"estado_mar": "tsunami"}).status_code == 422
