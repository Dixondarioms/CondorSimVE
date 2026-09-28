import json

import pytest

from app.engine import clock, orders
from app.models.escenario import Escenario
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso


def _escenario(db):
    esc = Escenario(nombre="Ejercicio de prueba")
    db.add(esc)
    db.commit()
    db.refresh(esc)
    return esc


def _unidad(db, esc, **kw):
    datos = dict(
        escenario_id=esc.id, nombre="U", bando="azul", tipo="terrestre",
        lat=0.0, lon=0.0, fuerza=100.0, velocidad_kmh=30.0, alcance_km=10.0,
    )
    datos.update(kw)
    u = Unidad(**datos)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _orden(db, esc, unidad, tipo, objetivo=None, waypoints=None):
    o = Orden(
        escenario_id=esc.id, unidad_id=unidad.id, tipo=tipo,
        objetivo_unidad_id=objetivo.id if objetivo else None,
        waypoints_json=json.dumps(waypoints or []), turno_emitida=esc.turno_actual,
    )
    db.add(o)
    db.commit()
    return o


def _avanzar(db, esc, terreno=None):
    clock.avanzar_turno(db, esc, terreno or TerrenoFalso())


# ---------- movimiento ----------
def test_movimiento_limitado_por_velocidad(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=30.0)
    o = _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc)
    db_session.refresh(u)
    db_session.refresh(o)
    assert o.estado == "resuelta"
    assert 0.0 < u.lat < 1.0
    # 30 km a ~111 km/grado
    assert u.lat == pytest.approx(30 / 111.19, rel=0.02)


def test_bosque_frena_el_avance_terrestre(db_session):
    esc = _escenario(db_session)
    u_llano = _unidad(db_session, esc, nombre="llano", lat=0.0, lon=0.0, velocidad_kmh=30)
    u_bosque = _unidad(db_session, esc, nombre="bosque", lat=0.0, lon=1.0, velocidad_kmh=30)
    _orden(db_session, esc, u_llano, "mover", waypoints=[[1.0, 0.0]])
    _orden(db_session, esc, u_bosque, "mover", waypoints=[[1.0, 1.0]])
    _avanzar(db_session, esc, TerrenoFalso(lambda lat, lon: "bosque" if lon > 0.5 else "llano"))
    db_session.refresh(u_llano)
    db_session.refresh(u_bosque)
    assert u_bosque.lat == pytest.approx(u_llano.lat * 0.6, rel=0.05)


def test_unidad_aerea_ignora_el_terreno(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, tipo="aerea", velocidad_kmh=300)
    _orden(db_session, esc, u, "mover", waypoints=[[5.0, 0.0]])
    _avanzar(db_session, esc, TerrenoFalso(lambda lat, lon: "montana"))
    db_session.refresh(u)
    assert u.lat == pytest.approx(300 / 111.19, rel=0.02)


def test_agua_bloquea_el_avance_terrestre(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=100)
    o = _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    # el agua empieza a ~0.1 grados (11 km) al norte
    _avanzar(db_session, esc, TerrenoFalso(lambda lat, lon: "agua" if lat > 0.1 else "llano"))
    db_session.refresh(u)
    db_session.refresh(o)
    assert u.lat <= 0.1
    assert "intransitable" in o.resultado


# ---------- combate ----------
def test_ataque_fuera_de_alcance_se_rechaza(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, alcance_km=5.0)
    d = _unidad(db_session, esc, bando="rojo", lat=5.0, lon=5.0)
    o = _orden(db_session, esc, a, "atacar", d)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    db_session.refresh(d)
    assert o.estado == "rechazada"
    assert d.fuerza == 100.0


def test_ataque_aplica_perdidas_y_destruye(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, alcance_km=50.0)
    d = _unidad(db_session, esc, bando="rojo", lat=0.01, fuerza=3.0)
    o = _orden(db_session, esc, a, "atacar", d)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    db_session.refresh(d)
    assert o.estado == "resuelta"
    assert d.fuerza == 0.0
    assert d.estado == "destruida"


def test_terreno_defensivo_reduce_perdidas_del_defensor(db_session):
    resultados = {}
    for clase in ("llano", "montana"):
        esc = _escenario(db_session)
        a = _unidad(db_session, esc, alcance_km=50.0)
        d = _unidad(db_session, esc, bando="rojo", lat=0.01)
        _orden(db_session, esc, a, "atacar", d)
        _avanzar(db_session, esc, TerrenoFalso(lambda lat, lon, c=clase: c))
        db_session.refresh(d)
        resultados[clase] = d.fuerza
    assert resultados["montana"] > resultados["llano"]


def test_ataques_son_simultaneos_e_independientes_del_orden(db_session):
    """Dos unidades que se atacan mutuamente pierden lo mismo sin importar quien emitio primero."""
    finales = []
    for invertir in (False, True):
        esc = _escenario(db_session)
        a = _unidad(db_session, esc, alcance_km=50.0, fuerza=100)
        b = _unidad(db_session, esc, bando="rojo", lat=0.01, alcance_km=50.0, fuerza=60)
        pares = [(a, b), (b, a)]
        for atacante, objetivo in (reversed(pares) if invertir else pares):
            _orden(db_session, esc, atacante, "atacar", objetivo)
        _avanzar(db_session, esc)
        db_session.refresh(a)
        db_session.refresh(b)
        finales.append((a.fuerza, b.fuerza))
    assert finales[0] == finales[1]


def test_cobertura_aerea_del_defensor_reduce_efecto_del_ataque_aereo(db_session):
    resultados = {}
    for con_cobertura in (False, True):
        esc = _escenario(db_session)
        caza = _unidad(db_session, esc, tipo="aerea", alcance_km=100, lat=0.05)
        blanco = _unidad(db_session, esc, bando="rojo", lat=0.0)
        if con_cobertura:
            _unidad(db_session, esc, bando="rojo", tipo="aerea", lat=0.1, nombre="escolta")
        o = _orden(db_session, esc, caza, "atacar", blanco)
        _avanzar(db_session, esc)
        db_session.refresh(blanco)
        db_session.refresh(o)
        resultados[con_cobertura] = blanco.fuerza
    assert resultados[False] < resultados[True]


def test_apoyo_de_unidad_cercana_mejora_el_ataque(db_session):
    resultados = {}
    for con_apoyo in (False, True):
        esc = _escenario(db_session)
        a = _unidad(db_session, esc, alcance_km=50.0)
        d = _unidad(db_session, esc, bando="rojo", lat=0.01, fuerza=60)
        if con_apoyo:
            artilleria = _unidad(db_session, esc, nombre="arti", lat=0.005, alcance_km=50.0)
            _orden(db_session, esc, artilleria, "apoyar", a)
        _orden(db_session, esc, a, "atacar", d)
        _avanzar(db_session, esc)
        db_session.refresh(d)
        resultados[con_apoyo] = d.fuerza
    assert resultados[True] < resultados[False]


def test_apoyo_a_unidad_enemiga_se_rechaza(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, alcance_km=50.0)
    enemigo = _unidad(db_session, esc, bando="rojo", lat=0.01)
    o = _orden(db_session, esc, a, "apoyar", enemigo)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "rechazada"


def test_avanzar_turno_incrementa_contador_y_reabre_fase_decision(db_session):
    esc = _escenario(db_session)
    turno = esc.turno_actual
    _avanzar(db_session, esc)
    assert esc.turno_actual == turno + 1
    assert esc.fase == "decision"


def test_sin_terreno_real_el_motor_usa_llano(db_session):
    # procesar_ordenes sin terreno explicito usa get_terreno() (parchado a llano)
    esc = _escenario(db_session)
    u = _unidad(db_session, esc)
    _orden(db_session, esc, u, "mover", waypoints=[[0.1, 0.0]])
    orders.procesar_ordenes(db_session, esc)
    db_session.commit()
    db_session.refresh(u)
    assert u.lat > 0
