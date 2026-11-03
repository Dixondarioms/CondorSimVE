"""Trafico civil y neutral: generacion por zona, aerovias, retiro, contactos desconocidos y daño colateral
(engine/trafico.py)."""

import json

from app.engine import doctrina, objetivos, tiempo_real, trafico
from app.models.evento import Evento
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import CAZA, _orden, mundo_limpio  # noqa: F401 - fixture automatica

ZONA = [0.0, 0.0, 2.0, 2.0]
MAR = TerrenoFalso(lambda lat, lon: "agua" if lon > 1.0 else "llano")  # la mitad este es mar


def _correr(db, esc, segundos, terreno=MAR):
    tiempo_real.paso(db, esc, segundos, terreno)
    db.commit()


def _civiles(db, esc, clase=None):
    q = db.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == "neutral", Unidad.estado == "activa")
    return [u for u in q if clase is None or u.clase == clase]


def test_genera_aviones_por_aerovias_y_buques_en_el_agua(db_session):
    esc = _escenario(db_session)
    d = trafico.configurar(esc, 4, 2, 2, ZONA)
    assert len(d["aerovias"]) == trafico.AEROVIAS and d["zona"] == ZONA
    db_session.commit()
    for _ in range(3):
        _correr(db_session, esc, trafico.MANTENER_CADA_S)
    aviones = _civiles(db_session, esc, "avion_comercial")
    barcos = _civiles(db_session, esc, "buque_mercante") + _civiles(db_session, esc, "pesquero")
    assert len(aviones) == 4 and aviones[0].nombre.startswith("Vuelo ") and aviones[0].sidc[1] == "N"
    assert len(barcos) == 4 and all(MAR.clase(u.lat, u.lon) == "agua" for u in barcos)
    # la misma zona conserva sus aerovias
    assert trafico.configurar(esc, 1, 0, 0, ZONA)["aerovias"] == d["aerovias"]


def test_el_que_sale_de_la_zona_se_retira_y_entra_otro(db_session):
    esc = _escenario(db_session)
    trafico.configurar(esc, 2, 0, 0, [0.0, 0.0, 0.3, 0.3])  # zona chica: los aviones la cruzan en minutos
    db_session.commit()
    _correr(db_session, esc, trafico.MANTENER_CADA_S)
    primeros = {u.id for u in _civiles(db_session, esc)}
    _correr(db_session, esc, 1800)
    retirados = db_session.query(Unidad).filter(Unidad.id.in_(primeros), Unidad.estado == "retirada").count()
    assert retirados >= 1 and len(_civiles(db_session, esc)) == 2
    est = tiempo_real.posiciones_para(db_session, esc, "instructor")
    assert not {f[0] for f in est["unidades"]} & {u.id for u in db_session.query(Unidad).filter(Unidad.estado == "retirada")}


def test_con_armas_libres_se_tira_al_desconocido_y_es_colateral(db_session):
    esc = _escenario(db_session)
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    _orden(db_session, esc, c, "patrullar", waypoints=[[0.0, 0.0]])
    avion = Unidad(escenario_id=esc.id, nombre="Vuelo AVA123", bando="neutral", tipo="aerea", clase="avion_comercial",
                   lat=0.4, lon=0.0, fuerza=100, velocidad_kmh=0, alcance_km=0, deteccion_km=0, autonomia_km=12000)
    db_session.add(avion)
    db_session.commit()
    _correr(db_session, esc, 30)  # recien detectado: desconocido, y las armas aire estan libres por defecto
    assert avion.fuerza < 100
    ev = db_session.query(Evento).filter(Evento.tipo == "colateral", Evento.bando_destino == "azul").one()
    assert "Daño colateral" in ev.descripcion and "Vuelo AVA123" in ev.descripcion
    m = objetivos.marcador(db_session, esc)
    assert m["azul"]["colateral"] >= trafico.PENALIDAD_ATAQUE and m["azul"]["bajas"] == 0
    assert m["azul"]["total"] == -m["azul"]["colateral"]


def test_con_armas_restringidas_o_ya_clasificado_no_se_le_tira(db_session):
    esc = _escenario(db_session)
    doctrina.fijar_bando(esc, "azul", {"armas_aire": "restringido"})
    db_session.commit()
    c = _unidad(db_session, esc, nombre="Caza", **CAZA)
    _orden(db_session, esc, c, "patrullar", waypoints=[[0.0, 0.0]])
    avion = Unidad(escenario_id=esc.id, nombre="Vuelo AVA123", bando="neutral", tipo="aerea", clase="avion_comercial",
                   lat=0.05, lon=0.0, fuerza=100, velocidad_kmh=0, alcance_km=0, deteccion_km=0, autonomia_km=12000)
    db_session.add(avion)
    db_session.commit()
    _correr(db_session, esc, 600)  # a 5 km lo identifica a la vista: es un avion comercial
    assert avion.fuerza == 100
    assert tiempo_real.mundo_de(esc.id).pistas[("azul", avion.id)]["etapa"] == "identificado"


def test_la_ia_no_toma_a_los_neutrales_como_enemigos(db_session):
    from app import adversario

    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="Rojo", bando="rojo", deteccion_km=50)
    db_session.add(Unidad(escenario_id=esc.id, nombre="M/V Aurora", bando="neutral", tipo="naval", clase="buque_mercante",
                          lat=0.1, lon=0.0, fuerza=100, velocidad_kmh=0, alcance_km=0, deteccion_km=0, autonomia_km=100))
    db_session.commit()
    ia = adversario._Turno(db_session, esc, "rojo", TerrenoFalso())
    assert ia.enemigos == []


def test_api_el_director_genera_y_quita_el_trafico(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.put(f"{base}/trafico", json={"aviones": 3, "mercantes": 1, "pesqueros": 0, "zona": [0, 0, 1, 1]})
    assert r.status_code == 200, r.text
    assert api("alfa").put(f"{base}/trafico", json={"aviones": 3, "zona": [0, 0, 1, 1]}).status_code == 403
    esc = prof.get(base).json()["escenario"]
    assert esc["trafico"]["aviones"] == 3 and len(esc["trafico"]["aerovias"]) == trafico.AEROVIAS
    r = prof.post(f"{base}/unidades", json=dict(nombre="Caza de Aruba", bando="neutral", tipo="aerea", clase="caza",
                                                 lat=0.3, lon=0.3))
    assert r.status_code == 200 and r.json()["sidc"][1] == "N"
    assert prof.delete(f"{base}/trafico").status_code == 200
    assert prof.get(base).json()["escenario"]["trafico"] is None
    assert json.loads(json.dumps(esc))  # serializable
