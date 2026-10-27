"""Meteorologia por zonas: clima efectivo por punto, efectos en el motor, deriva, caducidad y API."""

from app import state
from app.engine import clima as clima_mod
from app.engine import movimiento, vision
from app.models.zona_clima import ZonaClima
from tests.conftest import TerrenoFalso
from tests.test_ciclo_vuelo import _caza, _orden, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad

T = TerrenoFalso()


def _zona(db, esc, tipo="tormenta", lat=0.0, lon=0.0, radio=50.0, rumbo=0.0, kmh=0.0, hasta=None):
    z = ZonaClima(escenario_id=esc.id, tipo=tipo, lat=lat, lon=lon, radio_km=radio, deriva_rumbo=rumbo, deriva_kmh=kmh,
                  hasta_turno=hasta, creada_turno=esc.turno_actual)
    db.add(z)
    db.commit()
    db.refresh(z)
    return z


def test_el_clima_efectivo_es_el_peor_entre_el_general_y_las_zonas_que_cubren_el_punto():
    class Z:  # zona minima
        def __init__(self, tipo, lat, lon, radio_km):
            self.tipo, self.lat, self.lon, self.radio_km = tipo, lat, lon, radio_km
    c = clima_mod.ClimaLocal("nublado", [Z("tormenta", 0.0, 0.0, 30.0), Z("lluvia", 1.0, 0.0, 100.0)])
    assert c.en(0.0, 0.0) == "tormenta"
    assert c.en(1.0, 0.0) == "lluvia"
    assert c.en(5.0, 5.0) == "nublado"  # fuera de toda zona: el general
    assert clima_mod.resolver(c) == "nublado" and clima_mod.resolver("lluvia", 0, 0) == "lluvia"
    assert clima_mod.factor_deteccion(c, 0.0, 0.0) == 0.5 and clima_mod.factor_deteccion(c, 5.0, 5.0) == 0.9
    assert clima_mod.factor_movimiento(c, "terrestre", 0.0, 0.0) == 0.6
    assert clima_mod.factor_ataque_aereo("despejado") == 1.0


def test_dentro_de_una_tormenta_se_ve_menos_y_se_avanza_menos(db_session):
    esc = _escenario(db_session)
    _zona(db_session, esc, "tormenta", lat=0.0, lon=0.0, radio=40.0)
    ctx = clima_mod.contexto(db_session, esc)
    detector = _unidad(db_session, esc, nombre="D", deteccion_km=20, lat=0.0)
    cerca = _unidad(db_session, esc, nombre="E", bando="rojo", lat=0.15)  # ~17 km: se ve con cielo despejado
    assert vision.detecta(detector, cerca, T, "despejado")
    assert not vision.detecta(detector, cerca, T, ctx)  # en la tormenta el radio baja a la mitad
    movil = _unidad(db_session, esc, nombre="M", velocidad_kmh=30, lat=0.0)
    lejos = _unidad(db_session, esc, nombre="L", velocidad_kmh=30, lat=3.0)  # fuera de la zona
    assert movimiento.simular(movil, [[2.0, 0.0]], T, ctx).km_reales < movimiento.simular(lejos, [[5.0, 0.0]], T, ctx).km_reales


def test_las_zonas_derivan_cada_turno_y_caducan(db_session):
    esc = _escenario(db_session)
    movil = _zona(db_session, esc, "lluvia", lat=0.0, lon=0.0, radio=30.0, rumbo=90.0, kmh=50.0)
    breve = _zona(db_session, esc, "nublado", lat=2.0, lon=2.0, radio=30.0, hasta=esc.turno_actual)
    _avanzar(db_session, esc)
    _refrescar(db_session, movil)
    assert movil.lon > 0.4 and abs(movil.lat) < 1e-6  # ~50 km al este
    assert db_session.get(ZonaClima, breve.id) is None
    eventos = [e.descripcion for e in db_session.query(__import__("app.models.evento", fromlist=["Evento"]).Evento).all()]
    assert any("disipo" in e for e in eventos)


def test_el_estado_incluye_las_zonas_y_la_api_las_administra(api):
    from tests.test_api import _preparar

    prof, base, *_ = _preparar(api)
    r = prof.post(f"{base}/clima/zonas", json={"tipo": "tormenta", "lat": 0.0, "lon": 0.0, "radio_km": 40, "deriva_rumbo": 45, "deriva_kmh": 20, "turnos": 3, "nombre": "Frente 1"})
    assert r.status_code == 200, r.text
    zona = r.json()
    assert zona["tipo"] == "tormenta" and zona["hasta_turno"] == 4 and zona["nombre"] == "Frente 1"
    assert prof.post(f"{base}/clima/zonas", json={"tipo": "despejado", "lat": 0, "lon": 0, "radio_km": 40}).status_code == 422
    assert prof.post(f"{base}/clima/zonas", json={"tipo": "lluvia", "lat": 0, "lon": 0, "radio_km": 2}).status_code == 400
    estado = prof.get(base).json()
    assert [z["id"] for z in estado["clima_zonas"]] == [zona["id"]]
    assert prof.get(f"{base}/clima/en?lat=0&lon=0").json()["clima"] == "tormenta"
    assert prof.get(f"{base}/clima/en?lat=3&lon=3").json()["clima"] == "despejado"
    alumno = api("alfa")
    assert alumno.post(f"{base}/clima/zonas", json={"tipo": "lluvia", "lat": 0, "lon": 0, "radio_km": 40}).status_code == 403
    assert alumno.get(f"{base}/clima/zonas").status_code == 200
    assert prof.delete(f"{base}/clima/zonas/{zona['id']}").status_code == 200
    assert prof.get(f"{base}/clima/zonas").json() == []


def test_en_tiempo_real_la_zona_se_mueve_continua_y_no_a_saltos(db_session):
    from app.engine import tiempo_real

    esc = _escenario(db_session)
    movil = _zona(db_session, esc, "lluvia", lat=0.0, lon=0.0, radio=30.0, rumbo=90.0, kmh=40.0)
    tiempo_real.paso(db_session, esc, 900, T)  # un cuarto de hora: 10 km al este, sin esperar al fin de la hora
    db_session.commit()
    _refrescar(db_session, movil)
    assert abs(movil.lon * 111.32 - 10.0) < 0.1
    tiempo_real.paso(db_session, esc, 2700, T)  # se completa la hora: 40 km, sin el salto extra del fin de la hora
    db_session.commit()
    _refrescar(db_session, movil)
    assert abs(movil.lon * 111.32 - 40.0) < 0.2
