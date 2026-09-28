from types import SimpleNamespace

from app.engine.vision import unidades_visibles
from tests.conftest import TerrenoFalso


def U(id, bando, lat, lon, tipo="terrestre", det=10.0, estado="activa"):
    return SimpleNamespace(
        id=id, bando=bando, lat=lat, lon=lon, tipo=tipo, deteccion_km=det, estado=estado
    )


def ids(lista):
    return {u.id for u in lista}


def test_ve_propias_y_enemigas_dentro_del_radio():
    us = [U(1, "azul", 0, 0), U(2, "rojo", 0.05, 0), U(3, "rojo", 1.0, 0)]  # 5.5 km y 111 km
    assert ids(unidades_visibles(us, "azul", TerrenoFalso())) == {1, 2}


def test_bosque_reduce_el_radio_de_deteccion():
    us = [U(1, "azul", 0, 0, det=10), U(2, "rojo", 0.07, 0)]  # ~7.8 km
    assert 2 in ids(unidades_visibles(us, "azul", TerrenoFalso()))
    bosque = TerrenoFalso(lambda lat, lon: "bosque")  # 10 km * 0.6 = 6 km
    assert 2 not in ids(unidades_visibles(us, "azul", bosque))


def test_unidades_aereas_no_se_ocultan_en_el_terreno():
    us = [U(1, "azul", 0, 0, det=10), U(2, "rojo", 0.07, 0, tipo="aerea")]
    bosque = TerrenoFalso(lambda lat, lon: "bosque")
    assert 2 in ids(unidades_visibles(us, "azul", bosque))


def test_unidad_destruida_no_detecta_y_enemigo_destruido_no_se_ve():
    us = [U(1, "azul", 0, 0, estado="destruida"), U(2, "rojo", 0.01, 0)]
    assert ids(unidades_visibles(us, "azul", TerrenoFalso())) == {1}
    us = [U(1, "azul", 0, 0), U(2, "rojo", 0.01, 0, estado="destruida")]
    assert ids(unidades_visibles(us, "azul", TerrenoFalso())) == {1}


def test_el_bando_rojo_no_ve_lo_que_ve_el_azul():
    us = [U(1, "azul", 0, 0, det=50), U(2, "rojo", 0.2, 0, det=1)]
    assert 2 in ids(unidades_visibles(us, "azul", TerrenoFalso()))
    assert 1 not in ids(unidades_visibles(us, "rojo", TerrenoFalso()))
