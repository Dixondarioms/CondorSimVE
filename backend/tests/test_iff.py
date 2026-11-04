"""Fuego amigo e IFF (engine/iff.py): con el interruptor, la antiaerea propia con armas libres tira a la aeronave
propia con el IFF apagado, y la escucha enemiga oye el IFF encendido."""

from app.engine import doctrina, vision
from app.models.evento import Evento
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _correr, mundo_limpio  # noqa: F401 - fixture automatica


def _cuadro(db, fuego_amigo=True, iff=False):
    esc = _escenario(db)
    esc.fuego_amigo = fuego_amigo
    db.commit()
    aa = _unidad(db, esc, nombre="AA propia", clase="antiaerea", alcance_km=20, deteccion_km=20, velocidad_kmh=0)
    caza = _unidad(db, esc, nombre="Caza propio", lat=0.05, iff=iff, **{**CAZA, "velocidad_kmh": 0})
    return esc, aa, caza


def _fuego_amigo(db):
    return [e for e in db.query(Evento) if e.tipo == "fuego_amigo"]


def test_con_el_iff_apagado_y_armas_libres_la_antiaerea_propia_le_tira(db_session):
    esc, aa, caza = _cuadro(db_session)
    _correr(db_session, esc, 600)
    assert caza.fuerza < 100 and _fuego_amigo(db_session)
    from app.engine import aar
    from app.informe_html import render_html

    informe = aar.construir_informe(db_session, esc)
    assert informe["fuego_amigo"] and "Fuego amigo" in render_html(informe)


def test_con_el_iff_encendido_armas_restringidas_o_sin_interruptor_no(db_session):
    for fuego_amigo, iff, armas in ((True, True, "libre"), (True, False, "restringido"), (False, False, "libre")):
        esc, aa, caza = _cuadro(db_session, fuego_amigo, iff)
        doctrina.fijar_bando(esc, "azul", {"armas_aire": armas})
        db_session.commit()
        _correr(db_session, esc, 600)
        assert caza.fuerza == 100, (fuego_amigo, iff, armas)
    assert not _fuego_amigo(db_session)


def test_la_escucha_enemiga_oye_el_iff_encendido(db_session):
    esc, aa, caza = _cuadro(db_session, iff=True)
    escucha = _unidad(db_session, esc, nombre="Escucha roja", bando="rojo", clase="guerra_electronica", lat=1.0,
                      deteccion_km=5, velocidad_kmh=0)
    _correr(db_session, esc, 1)  # fija el interruptor del escenario
    assert vision.escucha(escucha, caza, None, TerrenoFalso())
    caza.iff = False
    assert not vision.escucha(escucha, caza, None, TerrenoFalso())


def test_api_iff(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    c = prof.post(f"{base}/unidades", json=dict(nombre="Caza", bando="azul", tipo="aerea", clase="caza", lat=0.0, lon=0.0)).json()
    assert next(u for u in alfa.get(base).json()["unidades"] if u["id"] == c["id"])["iff"] is None  # sin el interruptor
    prof.patch(f"{base}/config", json={"fuego_amigo": True})
    assert alfa.post(f"{base}/unidades/{c['id']}/iff", json={"iff": False}).json() == {"iff": False}
    assert next(u for u in alfa.get(base).json()["unidades"] if u["id"] == c["id"])["iff"] is False
    assert alfa.post(f"{base}/unidades/{a['id']}/iff", json={"iff": False}).status_code == 400
