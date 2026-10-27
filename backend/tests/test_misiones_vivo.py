"""Misiones aereas en tiempo real: despegue a su hora, vuelo en vivo por la ruta, orbita por horas, ataque al blanco,
escolta, regreso por combustible y aterrizaje (engine/misiones_vivo.py)."""

import pytest

from app.engine import geo, tiempo_real
from app.models.mision import Mision
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_ciclo_vuelo import _base, _caza
from tests.test_misiones import KM, P, _mision, aterrizaje
from tests.test_orders import _escenario, _unidad


@pytest.fixture(autouse=True)
def mundo_limpio():
    tiempo_real.MUNDOS.clear()
    yield
    tiempo_real.MUNDOS.clear()


def _correr(db, esc, segundos):
    tiempo_real.paso(db, esc, segundos, TerrenoFalso())
    db.commit()


def test_cap_orbita_las_horas_indicadas_intercepta_y_aterriza(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, nombre="Halcon", lat=0.0)
    m = _mision(db_session, esc, "CAP", [P("orbita", 45, turnos=1), aterrizaje(base)], unidad=caza)
    _correr(db_session, esc, 240)  # 45 km a 900 km/h: llega en 3 minutos y empieza a orbitar
    assert m.estado == "en_curso" and m.espera_hasta == pytest.approx(180 + 3600, abs=tiempo_real.PASO_MAX_S + 1)
    assert caza.mision == "patrulla"
    intruso = _caza(db_session, esc, nombre="Intruso", bando="rojo", lat=60 * KM)
    _correr(db_session, esc, 60)
    assert intruso.fuerza < 100  # la CAP intercepta en su orbita
    _correr(db_session, esc, 1800)
    assert geo.distancia_km(caza.lat, caza.lon, 45 * KM, 0.0) == pytest.approx(tiempo_real.RADIO_ORBITA_KM, abs=1.0)
    _correr(db_session, esc, 1800 + 600)  # termina la hora de orbita y vuelve
    assert m.estado == "cumplida" and caza.en_tierra and caza.base_id == base.id and "aterrizó" in m.resultado


def test_el_grupo_programado_despega_al_empezar_su_hora(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    m = _mision(db_session, esc, "TRASLADO", [P("paso", 50), aterrizaje(base)], base=base, modelo="f16", aeronaves=2,
                turno=2, nombre="Aguila")
    _correr(db_session, esc, 3000)
    assert m.estado == "programada" and db_session.query(Unidad).filter(Unidad.nombre == "Aguila").count() == 0
    _correr(db_session, esc, 900)  # empieza la hora 2: despega y sale hacia el punto de paso
    g = db_session.query(Unidad).filter(Unidad.nombre == "Aguila").one()
    assert m.estado == "en_curso" and m.unidad_id == g.id and g.lat > base.lat


def test_interdiccion_ataca_al_tener_el_blanco_a_su_alcance_y_regresa(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, nombre="Ataque", lat=0.0)
    blanco = _unidad(db_session, esc, nombre="Deposito rojo", bando="rojo", lat=150 * KM, deteccion_km=5)
    _unidad(db_session, esc, nombre="Reco", lat=140 * KM, deteccion_km=30)  # alguien propio lo ve
    m = _mision(db_session, esc, "INTERDICCION",
                [{"tipo": "blanco", "lat": blanco.lat, "lon": 0.0, "objetivo_unidad_id": blanco.id}, aterrizaje(base)],
                unidad=caza)
    _correr(db_session, esc, 300)  # a 80 km del blanco ya lo tiene a su alcance: ataca sin llegar encima (a 4,7 min)
    assert blanco.fuerza < 100 and m.indice == 1  # ya va hacia la base
    assert geo.distancia_km(caza.lat, caza.lon, blanco.lat, blanco.lon) > 60
    _correr(db_session, esc, 900)
    assert m.estado == "cumplida" and caza.en_tierra


def test_una_orden_directa_reemplaza_la_mision(db_session, api):
    from tests.test_api import _preparar

    prof, base_url, a, r1, r2 = _preparar(api)
    esc_id = int(base_url.rsplit("/", 1)[1])
    base = prof.post(f"{base_url}/unidades", json=dict(nombre="BA", bando="azul", tipo="base", clase="base_aerea",
                                                       lat=0.3, lon=0.3)).json()
    caza = prof.post(f"{base_url}/unidades", json=dict(nombre="Caza", bando="azul", modelo="f16", lat=0.3, lon=0.31,
                                                       tipo="aerea", clase="caza")).json()
    mision = {"unidad_id": caza["id"], "rol": "CAP", "puntos": [
        {"tipo": "orbita", "lat": 0.5, "lon": 0.3, "turnos": 2},
        {"tipo": "aterrizaje", "lat": 0.3, "lon": 0.3, "base_id": base["id"]}]}
    r = api("alfa").post(f"{base_url}/misiones", json=mision)
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "Se inicia en el acto."
    r = api("alfa").post(f"{base_url}/ordenes", json={"unidad_id": caza["id"], "tipo": "mover", "waypoints": [[0.4, 0.4]]})
    assert r.status_code == 200
    m = db_session.query(Mision).filter(Mision.escenario_id == esc_id).one()
    assert m.estado == "cancelada" and "orden directa" in m.resultado


def test_con_combustible_critico_abandona_la_ruta_y_regresa(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    caza = _caza(db_session, esc, nombre="Sediento", lat=0.0, combustible=30.0)
    m = _mision(db_session, esc, "CAP", [P("orbita", 100, turnos=6), aterrizaje(base)], unidad=caza)
    _correr(db_session, esc, 3600)
    assert m.estado == "cumplida" and caza.en_tierra and m.puntos_json.count("orbita") == 0


def test_la_escolta_acompana_al_grupo_escoltado(db_session):
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    principal = _caza(db_session, esc, nombre="Principal", lat=0.0)
    escolta = _caza(db_session, esc, nombre="Escolta", lat=0.0, lon=0.05)
    m = _mision(db_session, esc, "RECO", [P("orbita", 200, turnos=1), aterrizaje(base)], unidad=principal)
    e = _mision(db_session, esc, "ESCOLTA", [aterrizaje(base)], unidad=escolta)
    e.plan_json = '{"escolta_de": %d}' % m.id
    db_session.commit()
    _correr(db_session, esc, 600)
    assert geo.distancia_km(escolta.lat, escolta.lon, principal.lat, principal.lon) <= 9.0
    assert escolta.mision == "patrulla" and e.estado == "en_curso"


def test_la_mision_cumplida_no_cambia_de_estado_en_el_mismo_paso(db_session):
    db_session.autoflush = False  # como la sesion del servidor (app/db.py)
    esc = _escenario(db_session)
    base = _base(db_session, esc, lat=0.0)
    m = _mision(db_session, esc, "TRASLADO", [P("paso", 30), aterrizaje(base)], base=base, modelo="f16", aeronaves=2,
                nombre="Ida y vuelta")
    tiempo_real.paso(db_session, esc, 900, TerrenoFalso())  # despega, va y vuelve en un solo paso largo
    db_session.commit()
    assert m.estado == "cumplida" and db_session.query(Unidad).filter(Unidad.nombre == "Ida y vuelta").count() == 1
