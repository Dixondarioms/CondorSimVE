"""Combate continuo, azar, clima, logistica, unidades navales, bases, previsualizacion."""

import json

import pytest

from app.engine import azar, catalogo, clima, clock, combat, movimiento
from app.engine.combat import perdidas_por_ratio, resolver_combate
from app.models.aar import Combate
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_orders import _avanzar, _escenario, _orden, _unidad


# ---------- combate: curva continua y azar ----------
def test_las_perdidas_coinciden_con_los_anclajes():
    for ratio, perdida_def, perdida_atac in combat.ANCLAJES:
        assert perdidas_por_ratio(ratio) == pytest.approx((perdida_def, perdida_atac))


def test_curva_continua_y_monotona_sin_saltos():
    previos = None
    for i in range(1, 400):
        ratio = i / 50  # 0.02 .. 8
        d, a = perdidas_por_ratio(ratio)
        if previos:
            assert d >= previos[0] - 1e-9  # mejor ratio: el defensor pierde mas
            assert a <= previos[1] + 1e-9  # y el atacante pierde menos
            assert abs(d - previos[0]) < 1.5 and abs(a - previos[1]) < 1.5  # sin saltos bruscos
        previos = (d, a)


def test_ratio_casi_igual_ya_no_da_resultados_muy_distintos():
    assert abs(perdidas_por_ratio(0.99)[0] - perdidas_por_ratio(1.0)[0]) < 0.5


def test_azar_reproducible_y_distinto_por_semilla_turno_y_par():
    f = azar.factor_azar(7, 3, 1, 2)
    assert f == azar.factor_azar(7, 3, 1, 2)
    assert len({azar.factor_azar(s, 3, 1, 2) for s in range(8)}) > 1
    assert azar.factor_azar(7, 3, 1, 2) != azar.factor_azar(7, 4, 1, 2)
    assert all(0.55 < azar.factor_azar(s, t, 1, 2) < 1.65 for s in range(20) for t in range(20))


def test_azar_modifica_el_ratio_y_se_informa():
    base = resolver_combate(100, "terrestre", 100, "terrestre")
    con = resolver_combate(100, "terrestre", 100, "terrestre", azar=1.4)
    assert con.ratio == pytest.approx(base.ratio * 1.4)
    assert any("azar" in e for e in con.efectos)


def test_efectos_de_clase_clima_y_municion_en_el_ratio():
    base = resolver_combate(100, "aerea", 100, "terrestre", factor_ataque=1.0)
    assert resolver_combate(100, "aerea", 100, "terrestre", factor_ataque=1.3).ratio > base.ratio
    assert resolver_combate(100, "aerea", 100, "terrestre", factor_ataque=1.0, factor_clima=0.5).ratio < base.ratio
    assert resolver_combate(100, "aerea", 100, "terrestre", factor_ataque=1.0, factor_municion=0.4).ratio < base.ratio
    assert resolver_combate(100, "aerea", 100, "terrestre", factor_ataque=1.0, factor_defensa=1.15).ratio < base.ratio


def test_naval_no_recibe_bono_de_terreno():
    llano = resolver_combate(100, "aerea", 100, "naval", terreno_defensor="llano")
    monta = resolver_combate(100, "aerea", 100, "naval", terreno_defensor="montana")
    assert llano.ratio == monta.ratio


# ---------- clima ----------
def test_clima_reduce_deteccion_movimiento_y_ataque_aereo():
    assert clima.factor_deteccion("tormenta") < clima.factor_deteccion("lluvia") < 1.0
    assert clima.factor_movimiento("lluvia", "terrestre") < 1.0
    assert clima.factor_ataque_aereo("tormenta") < clima.factor_ataque_aereo("nublado") < 1.0
    assert clima.factor_movimiento("despejado", "aerea") == 1.0


def test_la_lluvia_frena_al_terrestre(db_session):
    resultados = {}
    for c in ("despejado", "lluvia"):
        esc = _escenario(db_session)
        esc.clima = c
        u = _unidad(db_session, esc, velocidad_kmh=40)
        _orden(db_session, esc, u, "mover", waypoints=[[2.0, 0.0]])
        _avanzar(db_session, esc)
        db_session.refresh(u)
        resultados[c] = u.lat
    assert resultados["lluvia"] == pytest.approx(resultados["despejado"] * 0.8, rel=0.05)


# ---------- movimiento: combustible, naval, bases ----------
def _u(**kw):
    datos = dict(tipo="terrestre", clase="", lat=0.0, lon=0.0, velocidad_kmh=60.0, autonomia_km=300.0, combustible=100.0)
    datos.update(kw)
    return type("U", (), datos)()


def test_el_combustible_limita_la_distancia():
    u = _u(combustible=5.0)  # 5% de 300 km = 15 km
    mov = movimiento.simular(u, [[2.0, 0.0]], TerrenoFalso())
    assert mov.km_reales == pytest.approx(15.0, abs=1.0)
    assert "combustible" in mov.nota
    assert mov.combustible_gastado == pytest.approx(5.0, abs=0.5)


def test_gasto_de_combustible_proporcional_a_la_distancia():
    mov = movimiento.simular(_u(velocidad_kmh=30), [[2.0, 0.0]], TerrenoFalso())
    assert mov.combustible_gastado == pytest.approx(30 / 300 * 100, rel=0.05)


def test_naval_solo_navega_sobre_agua():
    mar = TerrenoFalso(lambda lat, lon: "agua" if lat < 0.2 else "llano")
    mov = movimiento.simular(_u(tipo="naval", velocidad_kmh=100), [[1.0, 0.0]], mar)
    assert mov.lat <= 0.2 and "intransitable" in mov.nota
    # y un terrestre no entra al agua
    tierra = TerrenoFalso(lambda lat, lon: "agua" if lat > 0.1 else "llano")
    assert movimiento.simular(_u(velocidad_kmh=100), [[1.0, 0.0]], tierra).lat <= 0.1


def test_una_base_no_se_mueve():
    mov = movimiento.simular(_u(tipo="base", velocidad_kmh=0), [[1.0, 0.0]], TerrenoFalso())
    assert (mov.lat, mov.lon) == (0.0, 0.0)


def test_la_orden_gasta_combustible(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, velocidad_kmh=30, autonomia_km=300)
    _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc)
    db_session.refresh(u)
    assert u.combustible == pytest.approx(90.0, abs=1.0)


# ---------- logistica ----------
def test_atacar_consume_municion_y_sin_municion_se_rechaza(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, alcance_km=50, municion=100)
    d = _unidad(db_session, esc, bando="rojo", lat=0.01, fuerza=100)
    _orden(db_session, esc, a, "atacar", d)
    _avanzar(db_session, esc)
    db_session.refresh(a)
    assert a.municion == pytest.approx(75.0)  # terrestre: 25 por ataque

    esc2 = _escenario(db_session)
    a2 = _unidad(db_session, esc2, alcance_km=50, municion=0)
    d2 = _unidad(db_session, esc2, bando="rojo", lat=0.01)
    o = _orden(db_session, esc2, a2, "atacar", d2)
    _avanzar(db_session, esc2)
    db_session.refresh(o)
    assert o.estado == "rechazada" and "municion" in o.resultado.lower()


def test_municion_escasa_reduce_el_dano(db_session):
    resultados = {}
    for municion in (100, 10):
        esc = _escenario(db_session)
        a = _unidad(db_session, esc, alcance_km=50, municion=municion)
        d = _unidad(db_session, esc, bando="rojo", lat=0.01)
        _orden(db_session, esc, a, "atacar", d)
        _avanzar(db_session, esc)
        db_session.refresh(d)
        resultados[municion] = d.fuerza
    assert resultados[10] > resultados[100]


def test_reabastecimiento_junto_a_una_base_propia(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, tipo="base", clase="deposito", velocidad_kmh=0, alcance_km=20)
    cerca = _unidad(db_session, esc, nombre="cerca", lat=0.05, combustible=30, municion=30)
    lejos = _unidad(db_session, esc, nombre="lejos", lat=1.0, combustible=30, municion=30)
    enemigo = _unidad(db_session, esc, nombre="enemigo", bando="rojo", lat=0.05, combustible=30, municion=30)
    _avanzar(db_session, esc)
    for u in (cerca, lejos, enemigo):
        db_session.refresh(u)
    assert (cerca.combustible, cerca.municion) == (80.0, 80.0)
    assert (lejos.combustible, lejos.municion) == (30.0, 30.0)
    assert enemigo.combustible == 30.0  # la base no abastece al enemigo


def test_cada_base_solo_abastece_a_su_tipo(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=20)
    tierra = _unidad(db_session, esc, lat=0.05, combustible=30)
    _avanzar(db_session, esc)
    db_session.refresh(tierra)
    assert tierra.combustible == 30.0


def test_la_base_danada_deja_de_abastecer(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, tipo="base", clase="deposito", velocidad_kmh=0, alcance_km=20, fuerza=10)
    u = _unidad(db_session, esc, lat=0.05, combustible=30)
    _avanzar(db_session, esc)
    db_session.refresh(u)
    assert u.combustible == 30.0


def test_aeronave_sin_combustible_lejos_de_la_base_se_pierde(db_session):
    esc = _escenario(db_session)
    caza = _unidad(db_session, esc, tipo="aerea", clase="caza", velocidad_kmh=600, autonomia_km=1000, combustible=5)
    _orden(db_session, esc, caza, "mover", waypoints=[[3.0, 0.0]])
    _avanzar(db_session, esc)
    db_session.refresh(caza)
    assert caza.estado == "destruida"
    assert db_session.query(Evento).filter_by(escenario_id=esc.id, tipo="logistica", bando_destino="azul").count() == 1


def test_aeronave_sin_combustible_junto_a_su_base_se_salva(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, tipo="base", clase="base_aerea", velocidad_kmh=0, alcance_km=30)
    caza = _unidad(db_session, esc, tipo="aerea", clase="caza", velocidad_kmh=600, combustible=0.0)
    _avanzar(db_session, esc)
    db_session.refresh(caza)
    assert caza.estado == "activa" and caza.combustible == 50.0


# ---------- combate por clase, bases y registro ----------
def test_la_clase_cambia_el_resultado(db_session):
    resultados = {}
    for clase in ("infanteria", "artilleria"):
        esc = _escenario(db_session)
        a = _unidad(db_session, esc, clase=clase, alcance_km=50, fuerza=60)
        d = _unidad(db_session, esc, bando="rojo", lat=0.01, clase="infanteria")
        _orden(db_session, esc, a, "atacar", d)
        _avanzar(db_session, esc)
        db_session.refresh(d)
        resultados[clase] = d.fuerza
    assert resultados["artilleria"] < resultados["infanteria"]


def test_antiaerea_es_mucho_mejor_contra_aviones(db_session):
    resultados = {}
    for clase in ("infanteria", "antiaerea"):
        esc = _escenario(db_session)
        a = _unidad(db_session, esc, clase=clase, alcance_km=50)
        avion = _unidad(db_session, esc, bando="rojo", tipo="aerea", clase="caza", lat=0.01)
        _orden(db_session, esc, a, "atacar", avion)
        _avanzar(db_session, esc)
        db_session.refresh(avion)
        resultados[clase] = avion.fuerza
    assert resultados["antiaerea"] < resultados["infanteria"]


def test_una_base_puede_ser_atacada_y_no_ataca(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, alcance_km=50)
    base = _unidad(db_session, esc, bando="rojo", tipo="base", clase="deposito", velocidad_kmh=0, lat=0.01)
    _orden(db_session, esc, a, "atacar", base)
    orden_base = _orden(db_session, esc, base, "atacar", a)
    _avanzar(db_session, esc)
    db_session.refresh(base)
    db_session.refresh(orden_base)
    assert base.fuerza < 100
    assert orden_base.estado == "rechazada"


def test_naval_bombardea_costa_y_se_registra_el_combate(db_session):
    esc = _escenario(db_session)
    barco = _unidad(db_session, esc, tipo="naval", clase="fragata", alcance_km=40, velocidad_kmh=40)
    blanco = _unidad(db_session, esc, bando="rojo", lat=0.05)
    _orden(db_session, esc, barco, "atacar", blanco)
    _avanzar(db_session, esc)
    combates = db_session.query(Combate).filter_by(escenario_id=esc.id).all()
    assert len(combates) == 1
    c = combates[0]
    assert (c.turno, c.atacante_nombre, c.defensor_bando) == (1, barco.nombre, "rojo")
    assert c.perdida_defensor > 0 and c.ratio > 0


def test_el_azar_del_escenario_es_reproducible(db_session):
    finales = []
    for _ in range(2):
        esc = _escenario(db_session)
        esc.azar, esc.semilla = True, 12345
        a = _unidad(db_session, esc, alcance_km=50)
        d = _unidad(db_session, esc, bando="rojo", lat=0.01)
        # ids distintos entre corridas cambian el factor: se compara con el calculo directo
        _orden(db_session, esc, a, "atacar", d)
        _avanzar(db_session, esc)
        db_session.refresh(d)
        esperado = combat.resolver_combate(
            100, "terrestre", 100, "terrestre", factor_ataque=1.0, factor_municion=1.0,
            azar=azar.factor_azar(12345, 1, a.id, d.id)).fuerza_defensor_resultante
        assert d.fuerza == pytest.approx(esperado)
        finales.append(d.fuerza)


# ---------- catalogo ----------
def test_catalogo_es_coherente():
    for c in catalogo.CLASES.values():
        assert c.tipo in catalogo.TIPOS and len(c.funcion) == 6 and set(c.ataque_vs) == {"terrestre", "aerea", "naval"}
        sidc = catalogo.generar_sidc("azul", c)
        assert len(sidc) == 15 and sidc[:4] == f"SF{c.dimension}P"
    assert all(catalogo.obtener(None, t).tipo == t for t in catalogo.TIPOS)
    assert catalogo.obtener("caza", "terrestre").tipo == "terrestre"  # clase incompatible: cae al defecto
    assert catalogo.generar_sidc("rojo", catalogo.CLASES["infanteria"], "brigada")[11] == "H"
