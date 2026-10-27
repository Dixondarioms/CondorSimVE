"""Cóndor: contactos con clasificacion por etapas e incertidumbre de la posicion (engine/contactos_vivo.py)."""

import json

import pytest

from app import state
from app.engine import contactos_vivo, geo, tiempo_real
from app.models.evento import Evento
from tests.conftest import TerrenoFalso
from tests.test_orders import _escenario, _unidad

KM = 1 / 111.195


@pytest.fixture(autouse=True)
def mundo_limpio():
    tiempo_real.MUNDOS.clear()
    yield
    tiempo_real.MUNDOS.clear()


def _correr(db, esc, s):
    informe = tiempo_real.paso(db, esc, s, TerrenoFalso())
    db.commit()
    return informe


def _lejano(db):
    """Azul A con un sensor de 60 km y un rojo R quieto a 44 km (se lo detecta, no se lo ve a ojo)."""
    esc = _escenario(db)
    a = _unidad(db, esc, nombre="A", deteccion_km=60, alcance_km=50)
    r = _unidad(db, esc, nombre="R", bando="rojo", lat=44 * KM, deteccion_km=1, velocidad_kmh=0)
    return esc, a, r


def _visto(db, esc, rol, uid):
    return next(u for u in state.estado_para(db, esc, rol, TerrenoFalso())["unidades"] if u["id"] == uid)


def test_el_contacto_lejano_pasa_de_desconocido_a_clasificado_y_a_identificado(db_session):
    esc, a, r = _lejano(db_session)
    _correr(db_session, esc, 1)
    v = _visto(db_session, esc, "azul", r.id)
    assert (v["etapa"], v["nombre"], v["clase"]) == ("desconocido", "Contacto de superficie desconocido", None)
    assert v["sidc"].startswith("SU") and v["incertidumbre_km"] > 0.5
    assert geo.distancia_km(v["lat"], v["lon"], r.lat, r.lon) <= v["incertidumbre_km"] + 1e-6

    _correr(db_session, esc, 300)
    v = _visto(db_session, esc, "azul", r.id)
    assert v["etapa"] == "clasificado" and v["nombre"].endswith("(sin identificar)") and v["clase"] == r.clase

    _correr(db_session, esc, 1200)
    v = _visto(db_session, esc, "azul", r.id)
    assert (v["etapa"], v["nombre"]) == ("identificado", "R")
    textos = [e.descripcion for e in db_session.query(Evento).filter(Evento.escenario_id == esc.id)]
    assert any("Contacto clasificado" in t for t in textos) and any("Contacto identificado: R" in t for t in textos)
    # el instructor ve todo, sin incertidumbre
    v = _visto(db_session, esc, "instructor", r.id)
    assert v["nombre"] == "R" and (v["lat"], v["lon"]) == (r.lat, r.lon) and "etapa" not in v


def test_a_ojo_se_identifica_en_el_acto_y_las_bases_se_conocen(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="A", deteccion_km=60)
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=5 * KM, deteccion_km=1, velocidad_kmh=0)
    b = _unidad(db_session, esc, nombre="Base roja", bando="rojo", tipo="base", lat=40 * KM, deteccion_km=1, velocidad_kmh=0)
    _correr(db_session, esc, 1)
    assert _visto(db_session, esc, "azul", r.id)["etapa"] == "identificado"
    vb = _visto(db_session, esc, "azul", b.id)
    assert (vb["etapa"], vb["nombre"], vb["lat"]) == ("identificado", "Base roja", b.lat)


def test_la_etapa_se_guarda_y_se_recupera_si_el_servidor_se_reinicia(db_session):
    esc, a, r = _lejano(db_session)
    _correr(db_session, esc, 1)
    _correr(db_session, esc, 300)
    assert contactos_vivo.pista(db_session, esc, "azul", r.id)["etapa"] == "clasificado"
    tiempo_real.MUNDOS.clear()  # reinicio: se pierde la memoria
    p = contactos_vivo.pista(db_session, esc, "azul", r.id)
    assert p["etapa"] == "clasificado" and p["puntos"] >= contactos_vivo.PUNTOS_CLASIFICADO and p["inc"] > 0


def test_perdido_el_contacto_el_circulo_crece_con_lo_que_pudo_moverse(db_session):
    esc, a, r = _lejano(db_session)
    r.velocidad_kmh = 30
    db_session.commit()
    _correr(db_session, esc, 1)
    _correr(db_session, esc, 120)
    inc_visto = contactos_vivo.pista(db_session, esc, "azul", r.id)["inc"]
    r.lat = 2.0  # sale del alcance del sensor
    db_session.commit()
    _correr(db_session, esc, 3600)
    (c,) = state.estado_para(db_session, esc, "azul", TerrenoFalso())["contactos"]
    assert c["incertidumbre_km"] >= inc_visto + 29 and c["nombre"] == "Contacto de superficie desconocido"


def test_las_posiciones_de_cada_segundo_van_aproximadas(db_session):
    esc, a, r = _lejano(db_session)
    _correr(db_session, esc, 1)
    filas = {f[0]: f for f in tiempo_real.posiciones_para(db_session, esc, "azul")["unidades"]}
    inc = contactos_vivo.pista(db_session, esc, "azul", r.id)["inc"]
    assert (filas[a.id][1], filas[a.id][2]) == (round(a.lat, 5), round(a.lon, 5))  # las propias, exactas
    assert 0 < geo.distancia_km(filas[r.id][1], filas[r.id][2], r.lat, r.lon) <= inc + 0.01


def test_con_armas_restringidas_tira_recien_cuando_lo_identifica(db_session):
    esc, a, r = _lejano(db_session)
    esc.doctrina_json = json.dumps({"azul": {"armas_superficie": "restringido"}})
    db_session.commit()
    _correr(db_session, esc, 1)
    _correr(db_session, esc, 300)  # clasificado: todavia no
    assert contactos_vivo.pista(db_session, esc, "azul", r.id)["etapa"] != "identificado" and r.fuerza == 100
    _correr(db_session, esc, 1800)
    assert contactos_vivo.pista(db_session, esc, "azul", r.id)["etapa"] == "identificado" and r.fuerza < 100


def test_sin_niebla_de_guerra_no_hay_etapas(db_session):
    esc, a, r = _lejano(db_session)
    esc.niebla = False
    db_session.commit()
    _correr(db_session, esc, 1)
    v = _visto(db_session, esc, "azul", r.id)
    assert v["nombre"] == "R" and "etapa" not in v and (v["lat"], v["lon"]) == (r.lat, r.lon)
