"""Cóndor: doctrina y reglas de enfrentamiento (engine/doctrina.py) por bando y por unidad."""

import json

import pytest

from app.engine import catalogo, doctrina, geo, tiempo_real
from app.models.orden import Orden
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad

CAZA = dict(tipo="aerea", clase="caza", velocidad_kmh=900, alcance_km=80, deteccion_km=60, autonomia_km=1800)
KM = 1 / 111.195


@pytest.fixture(autouse=True)
def mundo_limpio():
    tiempo_real.MUNDOS.clear()
    yield
    tiempo_real.MUNDOS.clear()


def _doctrina(db, esc, bando="azul", **d):
    esc.doctrina_json = json.dumps({bando: d})
    db.commit()


def _correr(db, esc, s):
    informe = tiempo_real.paso(db, esc, s, TerrenoFalso())
    db.commit()
    return informe


def test_por_defecto_aire_libre_y_superficie_retenido_y_la_unidad_hereda_lo_que_no_fija(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, nombre="A")
    assert doctrina.de_unidad(esc, u) == doctrina.DEFECTO
    _doctrina(db_session, esc, armas_superficie="libre", combustible_regreso=40)
    doctrina.fijar_unidad(u, {"armas_superficie": "restringido"})
    d = doctrina.de_unidad(esc, u)
    assert (d["armas_superficie"], d["combustible_regreso"], d["armas_aire"]) == ("restringido", 40, "libre")
    doctrina.fijar_unidad(u, {"armas_superficie": None})  # vuelve a heredar
    assert doctrina.de_unidad(esc, u)["armas_superficie"] == "libre" and u.doctrina_json is None
    assert doctrina.errores({"armas_aire": "a discrecion", "color": 1}) and not doctrina.errores({"distancia_pct": 75})


def test_con_superficie_retenido_no_tira_por_su_cuenta_y_libre_si(db_session):
    def fuerza_enemiga(estado):
        tiempo_real.MUNDOS.clear()
        esc = _escenario(db_session)
        if estado:
            _doctrina(db_session, esc, armas_superficie=estado)
        _unidad(db_session, esc, nombre="A", alcance_km=10, deteccion_km=30)
        r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05, deteccion_km=1, velocidad_kmh=0)
        _correr(db_session, esc, 1800)
        return r.fuerza

    assert fuerza_enemiga(None) == 100  # por defecto, retenido: sin orden no tira
    assert fuerza_enemiga("libre") < 100  # libre: tira contra lo que tiene a su alcance


def test_la_patrulla_retenida_no_intercepta_y_la_distancia_de_tiro_acorta_el_alcance(db_session):
    def intercepta(**d):
        tiempo_real.MUNDOS.clear()
        esc = _escenario(db_session)
        if d:
            _doctrina(db_session, esc, **d)
        c = _unidad(db_session, esc, nombre="CAP", mision="patrulla", mision_lat=0.0, mision_lon=0.0, **CAZA)
        intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=60 * KM, mision="espera",
                          mision_lat=60 * KM, mision_lon=1.0, **CAZA)
        _correr(db_session, esc, 15)
        return intruso.fuerza < 100

    assert intercepta()  # libre, a 60 km (alcance 80)
    assert not intercepta(armas_aire="retenido")
    assert not intercepta(distancia_pct=50)  # solo abre fuego a 40 km


def test_la_defensa_aerea_retenida_no_lanza_y_los_misiles_por_blanco_salen_de_la_doctrina(db_session):
    def enfrentamientos(**d):
        tiempo_real.MUNDOS.clear()
        esc = _escenario(db_session)
        if d:
            _doctrina(db_session, esc, **d)
        bat = _unidad(db_session, esc, nombre="Bateria", clase=catalogo.MODELOS["pechora_2m"].clase, modelo="pechora_2m",
                      deteccion_km=160, alcance_km=32, velocidad_kmh=0)
        avion = _unidad(db_session, esc, nombre="Bandido", bando="rojo", lat=0.25, perfil_vuelo="medio", **CAZA)
        o = Orden(escenario_id=esc.id, unidad_id=avion.id, tipo="mover", waypoints_json="[[-1.0, 0.0]]", turno_emitida=1)
        db_session.add(o)
        db_session.flush()
        tiempo_real.aplicar_orden(db_session, esc, o, avion)
        db_session.commit()
        _correr(db_session, esc, 30)
        return tiempo_real.mundo_de(esc.id).da.get(bat.id) or []

    assert enfrentamientos(armas_aire="retenido") == []
    (e,) = enfrentamientos(disparos_por_blanco=2)
    assert e["por_salva"] == 2  # de lejos, la doctrina pide dos misiles por blanco (el arma, uno)


def test_bingo_y_winchester_hacen_volver_a_la_base(db_session):
    esc = _escenario(db_session)
    _doctrina(db_session, esc, combustible_regreso=50)
    _unidad(db_session, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)
    sediento = _unidad(db_session, esc, nombre="Sediento", lat=0.5, combustible=48.0, mision="patrulla",
                       mision_lat=0.5, mision_lon=0.0, **CAZA)
    vacio = _unidad(db_session, esc, nombre="Vacio", lat=0.5, lon=0.2, municion=0.0, mision="patrulla",
                    mision_lat=0.5, mision_lon=0.2, **CAZA)
    _correr(db_session, esc, 30)
    detalles = {o.unidad_id: o.detalle for o in db_session.query(Orden).filter(Orden.tipo == "aterrizar")}
    assert detalles == {sediento.id: "combustible critico", vacio.id: "sin armamento"}


def test_api_doctrina_del_bando_y_de_la_unidad(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa, bravo = api("alfa"), api("bravo")
    r = alfa.put(f"{base}/doctrina/azul", json={"armas_superficie": "libre", "distancia_pct": 75})
    assert r.status_code == 200 and r.json()["doctrina"]["armas_superficie"] == "libre" and "75 %" in r.json()["texto"]
    assert bravo.put(f"{base}/doctrina/azul", json={"armas_aire": "retenido"}).status_code == 403
    assert alfa.put(f"{base}/doctrina/azul", json={"armas_aire": "fuego"}).status_code == 400
    assert prof.put(f"{base}/doctrina/rojo", json={"armas_aire": "restringido"}).status_code == 200
    est = alfa.get(base).json()
    assert list(est["doctrina"]) == ["azul"] and est["doctrina"]["azul"]["valores"]["distancia_pct"] == 75
    r = alfa.put(f"{base}/unidades/{a['id']}/doctrina", json={"armas_superficie": "retenido"})
    assert r.status_code == 200 and r.json()["doctrina"] == {"armas_superficie": "retenido"}
    assert alfa.put(f"{base}/unidades/{a['id']}/doctrina", json={"armas_superficie": None}).json()["doctrina"] == {}
    assert bravo.put(f"{base}/unidades/{a['id']}/doctrina", json={"armas_aire": "libre"}).status_code == 404
    enemiga = next(u for u in bravo.get(base).json()["unidades"] if u["id"] == a["id"])
    assert enemiga["doctrina"] is None  # del enemigo no se ve su doctrina
