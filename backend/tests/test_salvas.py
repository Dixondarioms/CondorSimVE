"""Salvas de misiles: cada misil vuela por separado, impacta con su probabilidad, la defensa de punto de los buques los
derriba y una salva grande satura los canales (engine/misiles.py)."""

import json

import pytest

from app.engine import armas, misiles, tiempo_real
from app.models.aar import Combate
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _orden, mundo_limpio  # noqa: F401 - fixture automatica

AGUA = TerrenoFalso(lambda lat, lon: "agua")
LANZADOR = dict(clase="lanzador_misiles", deteccion_km=5)


def _correr(db, esc, segundos, terreno=AGUA):
    tiempo_real.paso(db, esc, segundos, terreno)
    db.commit()


def _misiles(db, blanco):
    return db.query(Unidad).filter(Unidad.blanco_id == blanco.id, Unidad.clase == "misil_crucero").all()


def test_cada_misil_hace_su_parte_de_la_tabla(db_session):
    """Sin defensa: 4 misiles hacen, en total, el daño de la salva completa por su probabilidad de impacto."""
    esc = _escenario(db_session)
    lanzador = _unidad(db_session, esc, nombre="Lanzador", **LANZADOR)
    r = _unidad(db_session, esc, nombre="Deposito", bando="rojo", lat=0.5, deteccion_km=5, velocidad_kmh=0)
    _unidad(db_session, esc, nombre="Reco", lat=0.45, deteccion_km=20)
    _orden(db_session, esc, lanzador, "lanzar", objetivo=r, detalle=json.dumps({"misiles": 4}))
    ms = _misiles(db_session, r)
    assert len(ms) == 4 and all(m.aeronaves == 1 and misiles.salva_de(m) == {"salva": 4, "pk": 0.85} for m in ms)
    _correr(db_session, esc, 600, TerrenoFalso())
    assert all(m.estado == "destruida" for m in ms)
    perdida = 100 - r.fuerza
    # la misma salva en un bloque (como antes) da el daño de la tabla completo
    esc2 = _escenario(db_session)
    lanzador2 = _unidad(db_session, esc2, nombre="Lanzador", **LANZADOR)
    r2 = _unidad(db_session, esc2, nombre="Deposito", bando="rojo", lat=0.5, deteccion_km=5, velocidad_kmh=0)
    _unidad(db_session, esc2, nombre="Reco", lat=0.45, deteccion_km=20)
    bloque = misiles.crear_salva(lanzador2, r2, 4)
    db_session.add(bloque)
    db_session.commit()
    _correr(db_session, esc2, 600, TerrenoFalso())
    assert perdida == pytest.approx((100 - r2.fuerza) * 0.85, rel=0.05)


def _salva_contra_fragata(db, n):
    esc = _escenario(db)
    lanzador = _unidad(db, esc, nombre="Bateria", bando="rojo", tipo="terrestre", clase="lanzador_misiles", lat=-0.6,
                       deteccion_km=5)
    f = _unidad(db, esc, nombre="Fragata", tipo="naval", clase="fragata", velocidad_kmh=0, alcance_km=40, deteccion_km=30)
    _unidad(db, esc, nombre="Reco", bando="rojo", lat=-0.1, deteccion_km=30)
    _orden(db, esc, lanzador, "lanzar", objetivo=f, detalle=json.dumps({"misiles": n}))
    ms = _misiles(db, f)
    _correr(db, esc, 900)
    return f, ms


def test_la_defensa_de_punto_derriba_y_una_salva_grande_la_satura(db_session):
    f_chica, _ = _salva_contra_fragata(db_session, 2)
    f_grande, _ = _salva_contra_fragata(db_session, 6)
    impactos = lambda f: db_session.query(Combate).filter(Combate.defensor_id == f.id).count()
    # contra 2 misiles la fragata (2 canales) se defiende mejor que cuando llegan 6 a la vez: pasan mas, en proporcion
    assert impactos(f_chica) / 2 < impactos(f_grande) / 6
    assert f_grande.fuerza < 100


def test_la_aeronave_suelta_misiles_antibuque_que_vuelan(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Halcon", modelo="f16", aeronaves=2, **CAZA)
    armas.armar(c, "antibuque")
    buque = _unidad(db_session, esc, nombre="Corbeta", bando="rojo", tipo="naval", clase="patrullero", lat=0.9,
                    velocidad_kmh=0, deteccion_km=20)
    _unidad(db_session, esc, nombre="Reco", lat=0.8, deteccion_km=30)
    db_session.commit()
    _orden(db_session, esc, c, "atacar", objetivo=buque)
    _correr(db_session, esc, 30)  # a 100 km: el Harpoon llega a 120
    harpoons = db_session.query(Unidad).filter(Unidad.modelo == "harpoon").all()
    assert len(harpoons) == 2 and buque.fuerza == 100 and armas.datos(c)["quedan"]["HPN"] == 2
    _correr(db_session, esc, 900)
    assert all(h.estado == "destruida" for h in harpoons) and buque.fuerza < 100
