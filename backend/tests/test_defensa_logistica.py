"""Control de emisiones de los radares, defensa antiaerea automatica y existencias (logistica) de las bases."""

import pytest

from app import state
from app.engine import aeronaves, logistica, vision
from app.models.evento import Evento
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _base, _caza, _orden, _refrescar
from tests.test_guerra_electronica import KM, T, _u
from tests.test_orders import _avanzar, _escenario, _unidad


# ---------- control de emisiones ----------
def test_un_radar_apagado_solo_ve_de_cerca_y_la_escucha_ya_no_lo_oye():
    radar = _u(1, "azul", "radar")
    lejano = _u(2, "rojo", "caza", 100)
    assert vision.detecta(radar, lejano, T)
    radar.emitiendo = False
    assert not vision.detecta(radar, lejano, T)
    assert vision.detecta(radar, _u(3, "rojo", "caza", 4), T)  # a ojo
    escucha = _u(4, "rojo", "guerra_electronica", 100)
    assert not vision.detecta(escucha, radar, T)
    radar.emitiendo = True
    assert vision.detecta(escucha, radar, T)


# ---------- defensa antiaerea automatica ----------
def _aa(db, esc, **kw):
    return _unidad(db, esc, **{**dict(nombre="AA", clase="antiaerea", alcance_km=20, deteccion_km=20, velocidad_kmh=30), **kw})


def _intruso(db, esc, km=10.0, **kw):
    return _caza(db, esc, **{**dict(nombre="Intruso", bando="rojo", lat=km * KM), **kw})


def _disparos(db, unidad):
    return db.query(Orden).filter(Orden.unidad_id == unidad.id, Orden.detalle == "defensa aerea").all()


def test_la_antiaerea_dispara_sola_contra_el_avion_enemigo_a_su_alcance(db_session):
    esc = _escenario(db_session)
    aa = _aa(db_session, esc)
    intruso = _intruso(db_session, esc)
    _avanzar(db_session, esc)
    _refrescar(db_session, intruso)
    [disparo] = _disparos(db_session, aa)
    assert disparo.estado == "resuelta" and disparo.objetivo_unidad_id == intruso.id
    assert intruso.fuerza < 100


@pytest.mark.parametrize("caso", ["fuego_retenido", "radar_apagado", "fuera_de_alcance", "avion_propio", "en_tierra"])
def test_casos_en_que_la_antiaerea_no_dispara_sola(db_session, caso):
    esc = _escenario(db_session)
    aa = _aa(db_session, esc, fuego_libre=caso != "fuego_retenido", emitiendo=caso != "radar_apagado")
    kw = {"fuera_de_alcance": dict(km=30), "avion_propio": dict(bando="azul"), "en_tierra": dict(en_tierra=True)}.get(caso, {})
    _intruso(db_session, esc, **kw)
    _avanzar(db_session, esc)
    assert _disparos(db_session, aa) == []


def test_la_antiaerea_portatil_no_necesita_radar(db_session):
    esc = _escenario(db_session)
    igla = _unidad(db_session, esc, nombre="IGLA", clase="antiaerea_portatil", alcance_km=5, deteccion_km=10)
    _intruso(db_session, esc, km=3)
    _avanzar(db_session, esc)
    assert len(_disparos(db_session, igla)) == 1


def test_con_el_radar_apagado_la_antiaerea_solo_tira_a_ojo_por_orden_y_con_poca_eficacia(db_session):
    esc = _escenario(db_session)
    aa = _aa(db_session, esc, emitiendo=False)
    intruso = _intruso(db_session, esc, km=4)
    o = _orden(db_session, esc, aa, "atacar", objetivo=intruso)
    _avanzar(db_session, esc)
    _refrescar(db_session, o)
    assert o.estado == "resuelta" and "Tiro optico" in o.resultado


# ---------- existencias de las bases ----------
def test_el_reabastecimiento_sale_de_las_existencias_de_la_base(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0, stock_combustible=30.0, stock_municion=1000.0)
    caza = _caza(db_session, esc, lat=0.0, en_tierra=True, base_id=base.id, espera_restante=2, combustible=20.0,
                 municion=20.0)
    _avanzar(db_session, esc)
    _refrescar(db_session, caza, base)
    assert caza.combustible == pytest.approx(50.0)  # solo quedaban 30 puntos en la base
    assert caza.municion == pytest.approx(70.0)
    assert base.stock_combustible == 0 and base.stock_municion == pytest.approx(950.0)
    assert any("se quedo sin combustible" in e.descripcion for e in db_session.query(Evento).all())


def test_sin_existencias_la_base_no_puede_lanzar_el_grupo():
    base = Unidad(nombre="BA", tipo="base", clase="base_aerea", estado="activa", fuerza=100.0,
                  stock_combustible=60.0, stock_municion=1000.0)
    motivo = aeronaves.error_de_despegue(base, "f16", 4, 0)  # necesita 100 de cada uno
    assert motivo and motivo.startswith("Sin logistica") and "combustible" in motivo
    assert aeronaves.error_de_despegue(base, "f16", 2, 0) is None


def test_el_despegue_descuenta_existencias(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    _orden(db_session, esc, base, "despegar", detalle=aeronaves.codificar("f16", 4, "Halcon"))
    _avanzar(db_session, esc)
    _refrescar(db_session, base)
    costo = logistica.costo_despegue(4)
    assert base.stock_combustible == pytest.approx(1000 - costo)
    assert base.stock_municion == pytest.approx(1000 - costo)


def test_el_deposito_repone_y_el_convoy_lleva_suministros_a_una_base_aerea(db_session):
    esc = _escenario(db_session)
    deposito = _unidad(db_session, esc, nombre="Deposito", tipo="base", clase="deposito", velocidad_kmh=0,
                       alcance_km=20, lat=-2.0, stock_combustible=500.0, stock_municion=500.0)
    base = _base(db_session, esc, lat=0.0, stock_combustible=100.0, stock_municion=100.0)
    convoy = _unidad(db_session, esc, nombre="Convoy", clase="transporte", velocidad_kmh=40, alcance_km=0, lat=0.0,
                     carga=100.0)
    _avanzar(db_session, esc)
    _refrescar(db_session, deposito, base, convoy)
    assert deposito.stock_combustible == pytest.approx(650.0)  # +150 por turno
    entregado = logistica.ENTREGA_CONVOY_POR_TURNO
    assert convoy.carga == pytest.approx(100.0 - entregado)
    assert base.stock_combustible == pytest.approx(100.0 + entregado * logistica.CARGA_A_STOCK / 2)


def test_el_convoy_se_recarga_con_las_existencias_del_deposito(db_session):
    esc = _escenario(db_session)
    deposito = _unidad(db_session, esc, nombre="Deposito", tipo="base", clase="deposito", velocidad_kmh=0, alcance_km=20)
    convoy = _unidad(db_session, esc, nombre="Convoy", clase="transporte", velocidad_kmh=40, alcance_km=0, carga=0.0)
    _avanzar(db_session, esc)
    _refrescar(db_session, deposito, convoy)
    assert convoy.carga == pytest.approx(50.0)
    # 50 de carga = 100 de cada existencia; despues repone 150
    assert deposito.stock_combustible == pytest.approx(1000 - 100 + 150)


# ---------- API ----------
def test_api_control_de_emisiones_y_fuego_automatico_con_puestos(api):
    prof = api("prof")
    for nombre, puesto in (("uda", "a3da"), ("ua3", "a3")):
        assert prof.post("/api/usuarios", json={"username": nombre, "password": "clave-segura-1", "rol": "azul",
                                                "puesto": puesto}).status_code == 200
    prof, base, a, *_ = _preparar(api)
    nueva = lambda clase: prof.post(f"{base}/unidades", json=dict(nombre=clase, bando="azul", clase=clase, lat=0.3, lon=0.3)).json()  # noqa: E731
    radar, aa = nueva("radar"), nueva("antiaerea")
    defensa = lambda cliente, u, cuerpo: api(cliente).post(f"{base}/unidades/{u['id']}/defensa", json=cuerpo)  # noqa: E731
    r = defensa("ua3", radar, {"emitiendo": False})
    assert r.status_code == 403 and "Defensa Aerea (A-3 D/A)" in r.json()["detail"]
    r = defensa("uda", radar, {"emitiendo": False})
    assert r.status_code == 200 and r.json()["emitiendo"] is False
    assert defensa("ua3", aa, {"fuego_libre": False}).status_code == 403
    assert defensa("uda", aa, {"fuego_libre": False}).json()["fuego_libre"] is False
    assert defensa("alfa", a, {"emitiendo": False}).status_code == 400  # la infanteria no tiene radar
    assert defensa("bravo", radar, {"emitiendo": True}).status_code == 404  # no es suya
    assert api("alfa").get(base).json()["unidades"][0].get("emitiendo") is not None


def test_el_instructor_ajusta_existencias_y_el_enemigo_no_las_ve(api):
    prof, base, *_ = _preparar(api)
    ba = prof.post(f"{base}/unidades", json=dict(nombre="BA", bando="azul", clase="base_aerea", lat=0.0, lon=0.3)).json()
    r = prof.patch(f"{base}/unidades/{ba['id']}", json={"stock_combustible": 50})
    assert r.status_code == 200 and r.json()["stock_combustible"] == 50
    assert {"emitiendo", "fuego_libre", "stock_combustible", "stock_municion"} <= set(state.CAMPOS_OCULTOS)
