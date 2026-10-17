"""Camino que recorre cada unidad en el turno (para animarlo en el mapa por la carretera)."""

from app.engine import movimiento
from tests.test_api import _preparar
from tests.test_orders import _avanzar, _escenario, _orden, _unidad


def test_la_unidad_guarda_el_camino_del_turno_por_sus_puntos(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=60.0)
    _orden(db_session, esc, u, "mover", waypoints=[[0.0, 0.1], [0.1, 0.1]])  # un codo, como en una carretera
    quieta = _unidad(db_session, esc, nombre="Quieta", lat=1.0)
    _avanzar(db_session, esc)
    db_session.refresh(u)
    db_session.refresh(quieta)
    assert u.recorrido[0] == [0.0, 0.0] and [0.0, 0.1] in u.recorrido and u.recorrido[-1] == [round(u.lat, 5), round(u.lon, 5)]
    assert quieta.recorrido is None
    _avanzar(db_session, esc)  # el turno siguiente, sin orden nueva, el camino viejo se borra
    db_session.refresh(u)
    assert u.recorrido is None


def test_el_camino_largo_se_acota():
    mov = movimiento.Movimiento(0, 0, km_reales=10, ruta=[[i / 1000, 0] for i in range(500)])
    import json

    assert len(json.loads(movimiento.recorrido_json(mov))) == movimiento.MAX_PUNTOS_RECORRIDO
    assert movimiento.recorrido_json(movimiento.Movimiento(0, 0)) is None


def test_el_enemigo_no_ve_el_camino(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa, bravo = api("alfa"), api("bravo")
    alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.0, 0.02], [0.02, 0.02]]})
    prof.post(f"{base}/avanzar_turno")
    propia = next(u for u in alfa.get(base).json()["unidades"] if u["id"] == a["id"])
    assert propia["recorrido"] and len(propia["recorrido"]) >= 2
    vista_roja = [u for u in bravo.get(base).json()["unidades"] if u["id"] == a["id"]]
    assert all(u["recorrido"] is None for u in vista_roja)
