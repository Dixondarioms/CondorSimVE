"""Daño por partes de las bases aereas (pista, plataforma, deposito) y refugios reforzados."""

import pytest

from app.engine import aeronaves, bases, logistica
from app.models.evento import Evento
from tests.test_ciclo_vuelo import _base, _caza, _orden, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad


def _artilleria(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="Art", bando="rojo", clase="artilleria", lat=0.1, alcance_km=30, fuerza=100, municion=100), **kw})


def test_una_base_nueva_tiene_refugios_y_partes_intactas(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc)
    assert base.refugios == 4 and base.dano_pista == 0 and bases.pista_operativa(base)
    assert _unidad(db_session, esc, nombre="Dep", tipo="base", clase="deposito").refugios == 0


def test_un_ataque_dirigido_a_la_pista_la_deja_inoperativa_y_bloquea_despegues(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    for k in range(3):
        _artilleria(db_session, esc, nombre=f"Art{k}", lon=0.01 * k)
    for a in db_session.query(type(base)).filter(type(base).bando == "rojo"):
        _orden(db_session, esc, a, "atacar", objetivo=base, detalle="pista")
    _avanzar(db_session, esc)
    _refrescar(db_session, base)
    assert base.dano_pista > base.dano_plataforma == base.dano_combustible == 0
    # el daño dirigido a la pista es 1,5 veces la perdida de fuerza, menos la reparacion propia del turno
    assert base.dano_pista == pytest.approx((100 - base.fuerza) * bases.DANO_A_PARTE_DIRIGIDO - bases.REPARACION_PISTA_SOLA, abs=0.5)
    base.dano_pista = 70.0
    db_session.commit()
    assert not bases.pista_operativa(base)
    assert "inoperativa" in aeronaves.error_de_despegue(base, "f16", 2, 0)
    caza = _caza(db_session, esc, lat=0.05)
    assert "inoperativa" in aeronaves.error_de_aterrizaje(caza, base, [base, caza])
    assert aeronaves.base_mas_cercana(caza, [base, caza]) is None


def test_la_pista_se_repara_sola_y_mucho_mas_con_ingenieros(db_session):
    esc = _escenario(db_session)
    sola = _base(db_session, esc, nombre="Sola", lat=0.0, dano_pista=70.0, dano_plataforma=40.0)
    con_ing = _base(db_session, esc, nombre="ConIng", lat=2.0, dano_pista=70.0, dano_plataforma=40.0)
    _unidad(db_session, esc, nombre="Ing", clase="ingenieros", lat=2.01)
    _avanzar(db_session, esc)
    _refrescar(db_session, sola, con_ing)
    assert sola.dano_pista == pytest.approx(70 - bases.REPARACION_PISTA_SOLA) and sola.dano_plataforma == 40
    assert con_ing.dano_pista == pytest.approx(70 - bases.REPARACION_PISTA_SOLA - bases.REPARACION_CON_INGENIEROS)
    assert con_ing.dano_plataforma == pytest.approx(40 - bases.REPARACION_CON_INGENIEROS)
    assert any("vuelve a estar operativa" in e.descripcion for e in db_session.query(Evento).all())


def test_los_refugios_protegen_a_los_primeros_grupos_y_la_plataforma_danada_expone_al_resto(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0, refugios=1, dano_plataforma=50.0)
    protegido = _caza(db_session, esc, nombre="Protegido", lat=0.006, en_tierra=True, base_id=base.id)
    expuesto = _caza(db_session, esc, nombre="Expuesto", lat=0.012, en_tierra=True, base_id=base.id)
    _orden(db_session, esc, _artilleria(db_session, esc), "atacar", objetivo=base)
    _avanzar(db_session, esc)
    _refrescar(db_session, base, protegido, expuesto)
    perdida = 100 - base.fuerza
    assert perdida > 5
    factor_plat = 1 + base.dano_plataforma / 100  # la plataforma ya recibio su parte del daño general
    assert 100 - expuesto.fuerza == pytest.approx(perdida * aeronaves.PERDIDA_EN_TIERRA * factor_plat, abs=0.05)
    assert 100 - protegido.fuerza == pytest.approx(perdida * aeronaves.PERDIDA_EN_TIERRA * factor_plat * bases.PROTECCION_REFUGIO, abs=0.05)


def test_el_deposito_danado_guarda_menos_existencias(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, stock_combustible=2000, stock_municion=2000)
    assert logistica.maximo(base) == 2000
    base.dano_combustible = 50.0
    assert logistica.maximo(base) == 1000
    logistica.cambiar_stock(base, "combustible", 0)  # se recorta al maximo nuevo
    assert logistica.stock(base, "combustible") <= 1000


def test_api_permite_elegir_la_parte_atacada_solo_contra_bases(api):
    from tests.test_api import _preparar

    prof, base, a, r1, r2 = _preparar(api)
    rojo_base = prof.post(f"{base}/unidades", json=dict(nombre="BA Roja", bando="rojo", tipo="base", clase="base_aerea", lat=0.05, lon=0.0)).json()
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": rojo_base["id"], "parte": "pista"})
    assert r.status_code == 200, r.text
    assert r.json()["detalle"] == "pista"
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"], "parte": "pista"})
    assert r.status_code == 400
