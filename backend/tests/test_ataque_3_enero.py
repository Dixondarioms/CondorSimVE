"""Plantilla del 3 de enero de 2026 (reconstruccion), aeronaves de EE. UU. del catalogo, firma furtiva y cisternas."""

from types import SimpleNamespace

import pytest

from app.engine import catalogo, plantillas, puestos, relieve, vision
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_orders import _avanzar, _escenario, _unidad

MODELOS_EEUU = ("f22", "f35a", "f35b", "fa18ef", "ea18g", "b1b", "p8a", "e2d", "e3g", "rc135", "ec130h", "kc135",
                "rq170", "mq9", "lucas", "mh47g", "mh60m", "mh60dap", "ah6m", "mh6m")


def test_la_plantilla_reconstruye_el_ataque_con_los_tipos_de_aeronave_informados():
    p = plantillas.PLANTILLAS["ataque_3_enero_2026"]
    assert (p.nacion_azul, p.nacion_rojo, p.hora_inicio_min) == ("venezuela", "estados_unidos", 60)
    rojas = [u for u in p.unidades if u.bando == "rojo" and catalogo.CLASES[u.clase].tipo == "aerea"]
    assert {u.modelo for u in rojas} == set(MODELOS_EEUU)  # todos los tipos de aeronave estan representados
    assert sum(u.aeronaves for u in rojas) == 73
    assert all(1 <= u.aeronaves <= catalogo.MAX_AERONAVES_GRUPO for u in rojas)
    nombres = {u.nombre for u in p.unidades}
    assert len(nombres) == len(p.unidades)
    for o in p.objetivos:
        assert o.unidad in nombres
    assert {"Buk-M2E La Carlota", "Buk-M2E Higuerote", "USS Gerald R. Ford (CVN-78)", "USS Iwo Jima (LHD-7), 22.ª MEU"} <= nombres


def test_crear_el_escenario_del_3_de_enero(db_session):
    esc = plantillas.crear_desde_plantilla(db_session, "ataque_3_enero_2026")
    unidades = {u.nombre: u for u in db_session.query(Unidad).filter_by(escenario_id=esc.id)}
    assert len(unidades) == len(plantillas.PLANTILLAS["ataque_3_enero_2026"].unidades)
    assert db_session.query(Objetivo).filter_by(escenario_id=esc.id).count() == 10

    chinook = unidades["MH-47G Chinook (fuerza de asalto)"]
    assert (chinook.modelo, chinook.aeronaves, relieve.perfil_de(chinook)) == ("mh47g", 3, "rasante")
    assert relieve.perfil_de(unidades["F-22A Raptor (escolta) 1"]) == "alto"
    assert relieve.perfil_de(unidades["E-3G Sentry (AWACS)"]) == "alto"  # alerta temprana: alto por defecto
    hawkeye = unidades["E-2D Advanced Hawkeye 2"]
    assert hawkeye.en_tierra and hawkeye.base_id == unidades["USS Gerald R. Ford (CVN-78)"].id
    su30 = unidades["Su-30MK2 (El Libertador)"]
    assert su30.en_tierra and su30.bando == "azul" and su30.modelo == "su30"


def test_guardar_como_plantilla_conserva_el_perfil_de_vuelo(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(plantillas, "RUTA_PLANTILLAS_USUARIO", tmp_path)
    esc = plantillas.crear_desde_plantilla(db_session, "ataque_3_enero_2026")
    p = plantillas.guardar_desde_escenario(db_session, esc, "Copia del 3 de enero")
    chinook = next(u for u in p.unidades if u.modelo == "mh47g")
    assert chinook.perfil_vuelo == "rasante"


def test_modelos_de_eeuu_en_el_catalogo():
    for m in MODELOS_EEUU:
        modelo = catalogo.MODELOS[m]
        assert modelo.pais == "Estados Unidos" and modelo.clase in catalogo.CLASES
    assert catalogo.MODELOS["e2d"].clase == "alerta_temprana" and catalogo.MODELOS["kc135"].clase == "cisterna"
    assert all(catalogo.modelo_embarcable(catalogo.MODELOS[m]) for m in ("fa18ef", "ea18g", "e2d", "f35b"))
    assert not catalogo.modelo_embarcable(catalogo.MODELOS["b1b"])


def test_los_furtivos_se_detectan_mucho_mas_cerca():
    radar = SimpleNamespace(tipo="terrestre", clase="radar", modelo="", deteccion_km=150.0, lat=0.0, lon=0.0)

    def avion(modelo):
        return SimpleNamespace(tipo="aerea", clase="caza", modelo=modelo, en_tierra=False, lat=0.0, lon=0.0)

    f16 = vision.radio_efectivo(radar, avion("f16"), TerrenoFalso())
    f22 = vision.radio_efectivo(radar, avion("f22"), TerrenoFalso())
    assert f22 == pytest.approx(f16 * 0.3)
    assert catalogo.firma(avion("fa18ef")) == 1.0  # sin firma propia: la de su clase


def test_el_avion_cisterna_reabastece_combustible_en_vuelo(db_session):
    esc = _escenario(db_session)
    kc = _unidad(db_session, esc, tipo="aerea", clase="cisterna", modelo="kc135", nombre="KC", carga=100,
                 velocidad_kmh=800, alcance_km=0, autonomia_km=9000)
    datos = dict(tipo="aerea", clase="caza", velocidad_kmh=900, alcance_km=80, autonomia_km=1800, combustible=50,
                 municion=30)
    cerca = _unidad(db_session, esc, nombre="cerca", lat=0.2, **datos)    # 22 km: dentro de los 40 km
    lejos = _unidad(db_session, esc, nombre="lejos", lat=1.0, **datos)    # 111 km
    _avanzar(db_session, esc)
    for u in (kc, cerca, lejos):
        db_session.refresh(u)
    assert cerca.combustible == pytest.approx(lejos.combustible + 40.0)
    assert cerca.municion == lejos.municion  # el cisterna no da municion
    assert kc.carga == pytest.approx(85.0)


def test_el_cisterna_y_la_alerta_temprana_los_conduce_operaciones():
    for clase in ("cisterna", "alerta_temprana"):
        u = SimpleNamespace(tipo="aerea", clase=clase)
        assert puestos.funcion_de_orden(u, "mover", catalogo.CLASES[clase]) == "aereo"
