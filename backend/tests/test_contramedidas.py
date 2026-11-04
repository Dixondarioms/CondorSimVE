"""Contramedidas: bengalas y chaff de las aeronaves y señuelos de los buques (engine/contramedidas.py)."""

import json

from app.engine import contramedidas, gastos
from app.models.escenario import Escenario
from tests.test_orders import _escenario, _unidad
from tests.test_salvas import AGUA, _misiles
from tests.test_tiempo_real import CAZA, mundo_limpio  # noqa: F401 - fixture automatica
from tests.test_tiempo_real import _orden


def _salva(db, senuelos: int | None):
    from app.engine import tiempo_real

    esc = _escenario(db)
    lanzador = _unidad(db, esc, nombre="Bateria", bando="rojo", tipo="terrestre", clase="lanzador_misiles", lat=-0.6,
                       deteccion_km=5)
    # sin defensa de punto (un buque de desembarco tiene poca): lo que cambia son los señuelos
    f = _unidad(db, esc, nombre="Fragata", tipo="naval", clase="fragata", velocidad_kmh=0, alcance_km=40,
                deteccion_km=30, contramedidas=senuelos)
    _unidad(db, esc, nombre="Reco", bando="rojo", lat=-0.1, deteccion_km=30)
    _orden(db, esc, lanzador, "lanzar", objetivo=f, detalle=json.dumps({"misiles": 2}))
    assert len(_misiles(db, f)) == 2
    tiempo_real.paso(db, esc, 900, AGUA)
    db.commit()
    return esc, f


def test_el_buque_con_senuelos_recibe_menos_dano_y_los_gasta(db_session):
    _, sin = _salva(db_session, 0)
    esc, con = _salva(db_session, None)
    assert contramedidas.maximo(con) == 8 and contramedidas.quedan(con) < 8
    assert 100 - con.fuerza < 100 - sin.fuerza
    azul = {g["tipo"]: g["cantidad"] for g in gastos.resumen(db_session, db_session.get(Escenario, esc.id))["azul"]["gastos"]}
    assert azul.get("Contramedidas", 0) >= 1


def test_cuantas_llevan_y_se_reponen():
    class U:
        tipo, clase, aeronaves, modelo, contramedidas = "aerea", "caza", 2, "", None
    u = U()
    assert contramedidas.maximo(u) == 2 * contramedidas.POR_AERONAVE and contramedidas.quedan(u) == 8
    assert contramedidas.usar(u) and contramedidas.quedan(u) == 7
    u.contramedidas = 0
    assert not contramedidas.usar(u)
    contramedidas.reponer(u)
    assert contramedidas.quedan(u) == 8
    u.clase = "dron_reconocimiento"
    assert contramedidas.maximo(u) == 0 and contramedidas.publico(u) is None
    assert CAZA["tipo"] == "aerea"
