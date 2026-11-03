"""Interceptacion aerea y naval (engine/interceptacion.py y la orden «interceptar» del motor en tiempo real)."""

import json

import pytest

from app.engine import doctrina, geo, interceptacion, tiempo_real
from app.models.aar import Combate
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica

BUQUE = dict(tipo="naval", clase="fragata", velocidad_kmh=55, alcance_km=60, deteccion_km=80, autonomia_km=8000)


def _accion(accion):
    return interceptacion.codificar(accion)


def _fase(o):
    return json.loads(o.detalle)["fase"]


def _combates(db, blanco):
    return db.query(Combate).filter(Combate.defensor_id == blanco.id).count()


def test_punto_de_encuentro_con_punteria_adelantada():
    # blanco a 100 km al norte que va al este a 400 km/h; el interceptor (800 km/h) apunta adelante, no al blanco
    t, lat, lon = interceptacion.solucion(0.0, 0.0, 800.0, 0.9, 0.0, 400.0, 0.0)
    assert lon > 0.2 and lat == pytest.approx(0.9)
    assert geo.distancia_km(0.0, 0.0, lat, lon) == pytest.approx(800.0 * t, rel=0.01)
    # un blanco que se aleja mas rapido no se alcanza
    assert interceptacion.solucion(0.0, 0.0, 300.0, 0.9, 0.0, 0.0, 500.0) is None


def test_la_doctrina_decide_si_hay_que_identificar():
    assert interceptacion.necesita_identificar("seguir", "libre")
    assert interceptacion.necesita_identificar("neutralizar", "libre")
    assert not interceptacion.necesita_identificar("directo", "libre")
    assert interceptacion.necesita_identificar("directo", "restringido")


def test_vectorea_identifica_a_la_vista_y_ataca(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.4, lon=0.3, **CAZA)
    _orden(db_session, esc, intruso, "mover", waypoints=[[0.4, -3.0]])
    o = _orden(db_session, esc, c, "interceptar", objetivo=intruso, detalle=_accion("neutralizar"))
    assert o.estado == "en_ejecucion" and "vectorea hacia Intruso" in o.resultado
    _correr(db_session, esc, 15)
    assert c.lon < 0.0  # punteria adelantada: va hacia donde estara el intruso (al oeste), no hacia donde esta
    fases = set()
    for _ in range(20):
        _correr(db_session, esc, 15)
        fases.add(_fase(o))
        if _combates(db_session, intruso):
            break
    assert {"contacto", "ataque"} <= fases
    assert _combates(db_session, intruso) >= 1
    p = tiempo_real.mundo_de(esc.id).pistas[("azul", intruso.id)]
    assert p["etapa"] == "identificado"  # neutralizar identifica antes de tirar


def test_identificar_y_seguir_no_tira_y_lo_escolta_a_distancia(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.4, lon=0.0, velocidad_kmh=500,
                      **{k: v for k, v in CAZA.items() if k != "velocidad_kmh"})
    _orden(db_session, esc, intruso, "mover", waypoints=[[0.4, -5.0]])
    o = _orden(db_session, esc, c, "interceptar", objetivo=intruso, detalle=_accion("seguir"))
    _correr(db_session, esc, 900)
    assert _fase(o) == "seguimiento" and o.estado == "en_ejecucion"
    assert _combates(db_session, intruso) == 0
    assert geo.distancia_km(c.lat, c.lon, intruso.lat, intruso.lon) < 15.0


def test_sin_contacto_estima_busca_y_aborta(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.4, lon=0.0, **CAZA)
    o = _orden(db_session, esc, c, "interceptar", objetivo=intruso, detalle=_accion("neutralizar"))
    _correr(db_session, esc, 15)
    intruso.lat, intruso.lon = 8.0, 8.0  # se escapa de la vista (el director lo movio lejos)
    db_session.commit()
    _correr(db_session, esc, 120)
    assert _fase(o) == "estima"
    _correr(db_session, esc, interceptacion.ESTIMA_S)
    assert _fase(o) == "busqueda"
    _correr(db_session, esc, interceptacion.BUSQUEDA_S)
    assert o.estado == "cancelada" and "interceptación se abortó" in o.resultado and c.mision == "espera"


def test_en_alerta_en_tierra_despega_y_sale(db_session):
    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA", tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=25)
    c = _unidad(db_session, esc, nombre="Caza", en_tierra=True, base_id=base.id, **CAZA)
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.4, lon=0.0, **CAZA)
    o = _orden(db_session, esc, c, "interceptar", objetivo=intruso, detalle=_accion("directo"))
    assert not c.en_tierra and _fase(o) == "alerta" and "Alerta en tierra" in o.resultado
    _correr(db_session, esc, 120)
    assert (c.lat, c.lon) == (0.0, 0.0)  # todavia despegando
    _correr(db_session, esc, interceptacion.ALERTA_TIERRA_S)
    assert c.lat > 0.0 and _fase(o) != "alerta"


def test_directo_con_armas_restringidas_igual_identifica(db_session):
    esc = _escenario(db_session)
    doctrina.fijar_bando(esc, "azul", {"armas_aire": "restringido"})
    db_session.commit()
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    intruso = _unidad(db_session, esc, nombre="Intruso", bando="rojo", lat=0.55, lon=0.0, velocidad_kmh=0,
                      **{k: v for k, v in CAZA.items() if k != "velocidad_kmh"})
    _orden(db_session, esc, c, "interceptar", objetivo=intruso, detalle=_accion("directo"))
    _correr(db_session, esc, 120)  # a ~30 km: a su alcance (80 km) pero sin identificar no tira
    assert _combates(db_session, intruso) == 0
    _correr(db_session, esc, 240)
    assert _combates(db_session, intruso) >= 1


def test_el_buque_intercepta_buques_y_no_aeronaves(db_session):
    esc = _escenario(db_session)
    f = _unidad(db_session, esc, nombre="Fragata", **BUQUE)
    avion = _unidad(db_session, esc, nombre="Avion", bando="rojo", lat=0.2, **CAZA)
    assert "no alcanza a una aeronave" in interceptacion.puede_interceptar(f, avion, "neutralizar")
    buque = _unidad(db_session, esc, nombre="Patrullero", bando="rojo", lat=0.6, lon=0.0, **BUQUE)
    o = _orden(db_session, esc, f, "interceptar", objetivo=buque, detalle=_accion("neutralizar"))
    tiempo_real.paso(db_session, esc, 5400, TerrenoFalso(lambda lat, lon: "agua"))
    db_session.commit()
    assert _fase(o) == "ataque" and buque.fuerza < 100


def test_api_estima_antes_de_emitir_y_valida(api):
    prof, base, a, r1, r2 = _preparar(api)
    c = prof.post(f"{base}/unidades", json=dict(nombre="Caza", bando="azul", tipo="aerea", clase="caza", lat=0.0,
                                                 lon=0.05)).json()
    alfa = api("alfa")
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": c["id"], "tipo": "interceptar", "objetivo_unidad_id": r1["id"],
                                          "accion_intercepcion": "neutralizar"})
    assert r.status_code == 400 and "aeronaves en vuelo y buques" in r.json()["detail"]
    avion = prof.post(f"{base}/unidades", json=dict(nombre="Bandido", bando="rojo", tipo="aerea", clase="caza",
                                                     lat=0.04, lon=0.0)).json()
    r = alfa.post(f"{base}/ordenes/interceptacion", json={"unidad_id": c["id"], "objetivo_unidad_id": avion["id"],
                                                          "accion_intercepcion": "directo"})
    assert r.status_code == 200, r.text
    est = r.json()
    assert est["alcanzable"] and est["minutos"] >= 0 and "combustible_llegada" in est and est["identifica"] is False
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": c["id"], "tipo": "interceptar", "objetivo_unidad_id": avion["id"],
                                          "accion_intercepcion": "seguir"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "en_ejecucion" and "identificar y seguir" in r.json()["resultado"]
