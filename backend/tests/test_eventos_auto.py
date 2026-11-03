"""Eventos automaticos del director: disparadores y acciones (engine/eventos_auto.py)."""

import json

from app.engine import eventos_auto, objetivos, tiempo_real
from app.models.escenario import Escenario
from app.models.evento import Evento
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad
from tests.test_api import _preparar
from tests.test_orders import _escenario, _unidad
from tests.test_tiempo_real import _correr, _orden, mundo_limpio  # noqa: F401 - fixture automatica

CUADRO = [[0.1, -0.1], [0.1, 0.1], [0.3, 0.1], [0.3, -0.1]]


def _reglas(db, esc, *reglas):
    d = eventos_auto.config(esc)
    assert not eventos_auto.validar(list(reglas)), eventos_auto.validar(list(reglas))
    d["reglas"] = eventos_auto.normalizar(list(reglas), d["reglas"])
    eventos_auto.guardar(esc, d)
    db.commit()


def _mensajes(db, para):
    return [e.descripcion for e in db.query(Evento).filter(Evento.tipo == "mensaje", Evento.bando_destino == para)]


def test_validacion():
    assert eventos_auto.validar([{"disparador": {"tipo": "hora", "hora": "25:00"}, "acciones": [{"tipo": "pausar"}]}])
    assert eventos_auto.validar([{"disparador": {"tipo": "hora", "hora": "07:00"}, "acciones": []}])
    assert not eventos_auto.validar([{"disparador": {"tipo": "hora", "hora": "07:00"}, "acciones": [{"tipo": "pausar"}]}])


def test_entra_a_un_area_manda_un_mensaje_una_sola_vez(db_session):
    esc = _escenario(db_session)
    u = _unidad(db_session, esc, nombre="Patrulla", velocidad_kmh=60)
    _reglas(db_session, esc, {"nombre": "Llegada", "disparador": {"tipo": "entra_area", "area": CUADRO, "bando": "azul"},
                              "acciones": [{"tipo": "mensaje", "para": "rojo", "texto": "Fuerzas azules en el valle"}]})
    _correr(db_session, esc, 60)  # todavia afuera
    assert not _mensajes(db_session, "rojo")
    _orden(db_session, esc, u, "mover", waypoints=[[0.4, 0.0]])
    _correr(db_session, esc, 1800)  # entra y sale
    assert _mensajes(db_session, "rojo") == [m for m in _mensajes(db_session, "rojo")] and len(_mensajes(db_session, "rojo")) == 1
    assert "Fuerzas azules en el valle" in _mensajes(db_session, "rojo")[0]
    assert eventos_auto.config(esc)["reglas"][0]["disparos"] == 1


def test_a_una_hora_cambia_el_clima_da_puntos_y_pausa(db_session):
    esc = _escenario(db_session)  # empieza a las 06:00
    esc.estado = "activo"
    _reglas(db_session, esc, {"nombre": "Frente", "disparador": {"tipo": "hora", "hora": "06:30"},
                              "acciones": [{"tipo": "clima", "clima": "tormenta"}, {"tipo": "puntos", "bando": "rojo", "puntos": 15},
                                           {"tipo": "pausar"}]})
    _correr(db_session, esc, 1200)
    assert esc.clima != "tormenta"
    _correr(db_session, esc, 1200)
    assert esc.clima == "tormenta" and esc.estado == "pausado" and "Frente" in esc.pausa_motivo
    assert objetivos.marcador(db_session, esc)["rojo"]["eventos"] == 15
    assert objetivos.marcador(db_session, esc)["rojo"]["total"] == 15


def test_al_destruirse_una_unidad_aparecen_refuerzos(db_session):
    esc = _escenario(db_session)
    v = _unidad(db_session, esc, nombre="Puesto Alfa", fuerza=1.0)
    _unidad(db_session, esc, nombre="Artilleria roja", bando="rojo", tipo="terrestre", clase="artilleria", lat=0.1,
            alcance_km=30, deteccion_km=30, velocidad_kmh=0)
    _reglas(db_session, esc, {"nombre": "Refuerzos", "disparador": {"tipo": "destruida", "unidad": "Puesto Alfa"},
                              "acciones": [{"tipo": "aparecer", "bando": "azul", "clase": "infanteria", "cantidad": 2,
                                            "lat": -0.2, "lon": 0.0, "nombre": "Cía de reserva"}]})
    ataque = db_session.query(Unidad).filter(Unidad.nombre == "Artilleria roja").one()
    _orden(db_session, esc, ataque, "atacar", objetivo=v)
    _correr(db_session, esc, 1800)
    assert v.estado == "destruida"
    nuevas = db_session.query(Unidad).filter(Unidad.nombre.like("Cía de reserva%")).all()
    assert len(nuevas) == 2 and all(u.bando == "azul" and u.clase == "infanteria" for u in nuevas)


def test_al_cumplirse_un_objetivo(db_session):
    esc = _escenario(db_session)
    o = Objetivo(escenario_id=esc.id, bando="azul", tipo="ocupar", nombre="Tomar el puente", lat=0, lon=0, radio_km=5,
                 puntos=10)
    db_session.add(o)
    db_session.commit()
    _reglas(db_session, esc, {"nombre": "Puente", "disparador": {"tipo": "objetivo", "objetivo": "Tomar el puente"},
                              "acciones": [{"tipo": "mensaje", "para": "todos", "texto": "El puente cayó"}]})
    _correr(db_session, esc, 60)
    assert not _mensajes(db_session, "todos")
    o.estado = "cumplido"
    db_session.commit()
    _correr(db_session, esc, 60)
    assert any("El puente cayó" in m for m in _mensajes(db_session, "todos"))


def test_api_solo_el_director_y_se_guardan_en_la_plantilla(api, db_session):
    prof, base, a, r1, r2 = _preparar(api)
    regla = {"nombre": "Aviso", "disparador": {"tipo": "hora", "hora": "08:00"},
             "acciones": [{"tipo": "mensaje", "para": "azul", "texto": "Hora H"}]}
    assert api("alfa").put(f"{base}/eventos_auto", json={"reglas": [regla]}).status_code == 403
    r = prof.put(f"{base}/eventos_auto", json={"reglas": [regla, {"disparador": {"tipo": "hora"}, "acciones": []}]})
    assert r.status_code == 400
    r = prof.put(f"{base}/eventos_auto", json={"reglas": [regla]})
    assert r.status_code == 200 and r.json()["reglas"][0]["id"] == "r1"
    assert prof.get(f"{base}/eventos_auto").json()["reglas"][0]["nombre"] == "Aviso"
    r = prof.post(f"{base}/guardar_plantilla", json={"nombre": "Con eventos de prueba", "descripcion": ""})
    assert r.status_code == 200, r.text
    r = prof.post(f"/api/plantillas/{r.json()['id']}")
    assert r.status_code == 200, r.text
    esc = db_session.get(Escenario, r.json()["id"])
    assert json.loads(esc.eventos_auto_json)["reglas"][0]["nombre"] == "Aviso"
