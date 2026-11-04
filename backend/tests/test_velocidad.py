"""Velocidad elegida de aeronaves y buques y velocidad y altura por tramo de la orden Mover (engine/movimiento.py)."""

import json

import pytest

from app.engine import movimiento
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica


def test_mas_rapido_gasta_mas_combustible_por_kilometro():
    caza = _Caza()
    lento = movimiento.simular(caza, [[0.0, 10.0]], TerrenoFalso(), horas=0.5)
    caza.velocidad_modo = "maxima"
    rapido = movimiento.simular(caza, [[0.0, 10.0]], TerrenoFalso(), horas=0.5)
    assert rapido.km_reales == pytest.approx(lento.km_reales * 1.3, rel=0.02)
    assert rapido.combustible_gastado / rapido.km_reales > 2 * lento.combustible_gastado / lento.km_reales
    caza.velocidad_modo = "economica"
    eco = movimiento.simular(caza, [[0.0, 10.0]], TerrenoFalso(), horas=0.5)
    assert eco.km_reales < lento.km_reales and eco.combustible_gastado < lento.combustible_gastado


class _Caza:
    tipo, clase, modelo, lat, lon, velocidad_kmh, autonomia_km, combustible = "aerea", "caza", "", 0.0, 0.0, 900, 1800, 100.0
    en_tierra, perfil_vuelo, velocidad_modo, sistemas_json = False, None, None, None


def test_la_orden_mover_cambia_velocidad_y_altura_en_cada_punto(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    tramos = [{"velocidad": "maxima", "perfil": "rasante"}, {"velocidad": "economica", "perfil": "alto"}]
    _orden(db_session, esc, c, "mover", waypoints=[[0.0, 0.5], [0.0, 3.0]], detalle=json.dumps({"tramos": tramos}))
    assert c.velocidad_modo == "maxima" and c.perfil_vuelo == "rasante"
    _correr(db_session, esc, 240)  # 0,5 grados (55 km) a 1170 km/h: en unos 3 min pasa el primer punto
    assert c.lon > 0.5 and c.velocidad_modo == "economica" and c.perfil_vuelo == "alto"


def test_api_velocidad_y_tramos(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    c = prof.post(f"{base}/unidades", json=dict(nombre="Caza", bando="azul", tipo="aerea", clase="caza", lat=0.0, lon=0.0)).json()
    assert alfa.post(f"{base}/unidades/{a['id']}/velocidad", json={"velocidad": "maxima"}).status_code == 400
    r = alfa.post(f"{base}/unidades/{c['id']}/velocidad", json={"velocidad": "economica"})
    assert r.status_code == 200 and r.json()["velocidad_actual"] == "economica"
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": c["id"], "tipo": "mover", "waypoints": [[0.1, 0.0], [0.2, 0.0]],
                                          "tramos": [{"velocidad": "maxima"}]})
    assert r.status_code == 400  # un tramo por punto
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.01, 0.0]],
                                          "tramos": [{"velocidad": "maxima"}]})
    assert r.status_code == 400  # las tropas no eligen velocidad
    r = alfa.post(f"{base}/ordenes", json={"unidad_id": c["id"], "tipo": "mover", "waypoints": [[0.1, 0.0], [0.2, 0.0]],
                                          "tramos": [{"velocidad": "maxima"}, {"perfil": "rasante"}]})
    assert r.status_code == 200, r.text
    vista = next(u for u in alfa.get(base).json()["unidades"] if u["id"] == c["id"])
    assert vista["velocidad_actual"] == "maxima"
