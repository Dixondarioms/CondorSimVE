"""Plataformas aereas (engine/plataformas.py): ficha tecnica, largo y pista util, despegue y aterrizaje segun la
carrera de cada aeronave, logistica de mision (combustible y oxigeno liquido) y tipos propios con su ficha."""

import pytest

from app.engine import aeronaves, catalogo, misiones, plataformas
from app.models.unidad import Unidad
from tests.test_ciclo_vuelo import _base, _caza
from tests.test_orders import _escenario


def test_cada_aeronave_tiene_su_ficha_con_roles_conocidos():
    for m in catalogo.MODELOS.values():
        c = catalogo.CLASES[m.clase]
        f = plataformas.ficha_de_modelo(m)
        if c.tipo != "aerea" or c.misil or c.civil:  # los aviones comerciales no tienen ficha militar
            assert f is None
            continue
        assert f is not None and f.roles and set(f.roles) <= set(plataformas.ROLES), m.id
        assert f.crucero_kt > 0 and f.max_kt >= f.crucero_kt and f.radio_nm > 0 and f.combustible_kg > 0
    su30, f16 = plataformas.FICHAS["su30"], plataformas.FICHAS["f16"]
    assert su30.radio_nm > f16.radio_nm and su30.tripulacion == 2
    assert plataformas.FICHAS["helo_transporte"].despegue_m == 0  # vertical
    assert "AAR" in plataformas.FICHAS["kc135"].roles and plataformas.FICHAS["kc135"].transferible_kg > 0


def test_el_largo_de_pista_sale_del_plano_del_aerodromo_o_del_instructor():
    libertador = Unidad(clase="base_aerea", tipo="base", lat=10.18056, lon=-67.56111, dano_pista=0.0, nombre="BA")
    if plataformas.AERODROMOS.is_dir() and plataformas.pista_del_plano(10.18056, -67.56111):
        assert plataformas.largo_pista(libertador) == pytest.approx(3848, abs=5)
    lejos = Unidad(clase="base_aerea", tipo="base", lat=-40.0, lon=-10.0, dano_pista=0.0, nombre="BA")
    assert plataformas.largo_pista(lejos) == plataformas.PISTA_POR_DEFECTO_M
    lejos.pista_m = 1800.0
    assert plataformas.largo_pista(lejos) == 1800
    lejos.dano_pista = 25.0
    assert plataformas.pista_util(lejos) == 1350  # los craters acortan la carrera
    assert plataformas.largo_pista(Unidad(clase="portaaviones", tipo="naval", lat=0, lon=0)) is None


def test_no_despega_ni_aterriza_donde_su_carrera_no_entra(db_session):
    esc = _escenario(db_session)
    corta = _base(db_session, esc, pista_m=700.0)
    assert "más corta que la carrera para despegar de Su-30" in aeronaves.error_de_despegue(corta, "su30", 2, 0)
    assert aeronaves.error_de_despegue(corta, "ataque_ligero", 2, 0) is None  # el K-8 despega en 440 m
    assert aeronaves.error_de_despegue(corta, "helo_ataque", 2, 0) is None  # vertical
    assert aeronaves.error_de_despegue(corta, "f35b", 2, 0) is None  # carrera corta
    su30 = _caza(db_session, esc, modelo="su30", lat=0.05, aeronaves=2)
    assert "aterrizar" in aeronaves.error_de_aterrizaje(su30, corta, [corta, su30])
    larga = _base(db_session, esc, nombre="Larga", lat=0.3)
    assert aeronaves.base_mas_cercana(su30, [corta, larga, su30]) is larga  # la corta queda descartada


def test_logistica_de_mision_combustible_y_oxigeno_liquido():
    r = plataformas.requerimientos(catalogo.MODELOS["su30"], 2, 2.0)
    f = plataformas.FICHAS["su30"]
    assert r["combustible_por_aeronave_kg"] == round(f.consumo_kg_h * 2 * 1.2)
    assert r["combustible_kg"] == 2 * r["combustible_por_aeronave_kg"]
    assert r["lox_por_aeronave_l"] == pytest.approx(f.lox_l_h * 2 * 1.2, abs=0.1)
    assert r["tripulantes"] == 4 and not r["excede_interno"]
    largo = plataformas.requerimientos(catalogo.MODELOS["f16"], 1, 10.0)
    assert largo["excede_interno"] and largo["excede_lox"]  # 10 h no entran en sus tanques ni en su oxigeno
    assert plataformas.requerimientos(catalogo.MODELOS["f22"], 1, 2.0)["lox_l"] == 0  # OBOGS


def test_la_estimacion_de_la_mision_tiene_en_cuenta_el_perfil_de_vuelo():
    puntos = [{"tipo": "paso", "lat": 1.0, "lon": 0.0}]
    medio = misiones.estimar(0.0, 0.0, 900, 1800, 100.0, puntos)
    rasante = misiones.estimar(0.0, 0.0, 900, 1800, 100.0, puntos, 1.3)
    assert rasante["combustible_final"] < medio["combustible_final"]


def test_api_ficha_en_el_catalogo_pista_en_la_base_y_tipo_propio_con_ficha(api):
    prof = api("prof")
    cat = prof.get("/api/catalogo").json()
    su30 = next(m for m in cat["modelos"] if m["id"] == "su30")
    assert su30["ficha"]["crucero_kt"] == 480 and su30["ficha"]["autonomia_h"] > 1
    assert "Patrulla aérea de combate" in su30["ficha"]["roles_nombres"]
    r = prof.post("/api/catalogo/modelos", json={
        "nombre": "K-8W Karakorum AMB", "clase": "ataque", "velocidad_kmh": 800, "autonomia_km": 2200,
        "ficha": {"roles": "CAS RECO", "crucero_kt": 350, "despegue_m": 440, "lox_l": 3, "lox_l_h": 0.6}})
    assert r.status_code == 200, r.text
    tipo = next(m for m in prof.get("/api/catalogo").json()["modelos"] if m["nombre"] == "K-8W Karakorum AMB")
    assert tipo["ficha"]["roles"] == ["CAS", "RECO"] and tipo["ficha"]["despegue_m"] == 440
    assert tipo["ficha"]["radio_nm"] > 0  # lo que no cargo sale de su clase
    assert prof.post("/api/catalogo/modelos", json={"nombre": "Mala", "clase": "ataque", "ficha": {"crucero_kt": "x"}}).status_code == 400
    prof.delete(f"/api/catalogo/modelos/{tipo['id']}")
    esc = prof.post("/api/escenarios", json={"nombre": "Pistas"}).json()
    base = prof.post(f"/api/escenarios/{esc['id']}/unidades", json=dict(
        nombre="BA", bando="azul", tipo="base", clase="base_aerea", lat=-40.0, lon=-10.0)).json()
    assert base["pista_largo_m"] == plataformas.PISTA_POR_DEFECTO_M and base["pista_util_m"] == plataformas.PISTA_POR_DEFECTO_M
    r = prof.patch(f"/api/escenarios/{esc['id']}/unidades/{base['id']}", json={"pista_m": 1500})
    assert r.status_code == 200 and r.json()["pista_largo_m"] == 1500
