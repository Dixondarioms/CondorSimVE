"""Herramientas de direccion: interruptores del motor, informes inyectados con posicion y diapositivas del AAR."""

from app.engine import clima as clima_mod
from app.models.unidad import Unidad
from tests.test_api import _preparar
from tests.test_ciclo_vuelo import _orden, _refrescar
from tests.test_orders import _avanzar, _escenario, _unidad


def test_sin_niebla_todos_ven_todo_y_los_interruptores_quedan_registrados(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    assert {u["nombre"] for u in alfa.get(base).json()["unidades"]} == {"A", "R1"}  # R2 esta lejos: no se ve
    r = prof.patch(f"{base}/config", json={"niebla": False, "fuego_automatico": False})
    assert r.status_code == 200, r.text
    assert r.json()["escenario"]["niebla"] is False
    assert {u["nombre"] for u in alfa.get(base).json()["unidades"]} == {"A", "R1", "R2"}
    assert any("niebla de guerra desactivado" in ev["descripcion"] for ev in prof.get(base).json()["eventos"])


def test_con_la_logistica_apagada_no_se_consume_combustible(db_session):
    esc = _escenario(db_session)
    esc.logistica = False
    db_session.commit()
    u = _unidad(db_session, esc, velocidad_kmh=30.0, combustible=50.0)
    _orden(db_session, esc, u, "mover", waypoints=[[1.0, 0.0]])
    _avanzar(db_session, esc)
    _refrescar(db_session, u)
    assert u.lat > 0.1 and u.combustible == 50.0


def test_con_los_efectos_del_clima_apagados_la_tormenta_no_frena(db_session):
    esc = _escenario(db_session)
    esc.clima = "tormenta"
    esc.efectos_clima = False
    db_session.commit()
    assert clima_mod.contexto(db_session, esc).en(0, 0) == "despejado"


def test_informe_inyectado_con_posicion_aparece_en_el_mapa_del_bando_y_caduca(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.post(f"{base}/eventos", json={"tipo": "inteligencia", "descripcion": "Columna enemiga avistada", "bando_destino": "azul",
                                           "lat": 0.5, "lon": 0.5, "turnos": 2, "fuente": "Inteligencia"})
    assert r.status_code == 200, r.text
    assert r.json()["hasta_turno"] == 3 and r.json()["fuente"] == "Inteligencia"
    informes = api("alfa").get(base).json()["informes"]
    assert len(informes) == 1 and informes[0]["lat"] == 0.5
    assert api("bravo").get(base).json()["informes"] == []
    for _ in range(3):
        prof.post(f"{base}/avanzar_turno")
    assert api("alfa").get(base).json()["informes"] == []


def test_diapositivas_del_aar(api):
    prof, base, a, r1, r2 = _preparar(api)
    api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    prof.post(f"{base}/avanzar_turno")
    r = prof.get(f"{base}/aar/diapositivas.html")
    assert r.status_code == 200 and "Turno 1" in r.text and "Resumen del ejercicio" in r.text and "Preguntas" in r.text
    assert api("alfa").get(f"{base}/aar/diapositivas.html").status_code == 403
