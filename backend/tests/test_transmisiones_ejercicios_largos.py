"""Plan de transmisiones (engine/transmisiones.py), avance de varios turnos y estado liviano en ejercicios largos."""

from types import SimpleNamespace

from app.engine import guerra_electronica as ge_mod
from app.engine import orders, transmisiones
from app.models.orden import Orden
from tests.test_api import _preparar


def _esc(**kw):
    return SimpleNamespace(transmisiones_json=None, turno_actual=1, com_ordenes_pct=20, **kw)


def test_el_plan_sugerido_es_valido_y_se_detectan_los_errores():
    esc = _esc()
    sug = transmisiones.sugerido("azul", 1)
    transmisiones.guardar(esc, "azul", sug["redes"], 1)
    assert transmisiones.errores(transmisiones.plan(esc, "azul"), 1) == []
    redes = [dict(r) for r in sug["redes"]]
    redes[0]["primaria"] = 45.0  # HF fuera de banda
    redes[1]["secundaria"] = 243.0  # guardia
    redes[2]["primaria"] = redes[1]["primaria"] + 0.01  # pisa a otra red
    transmisiones.guardar(esc, "azul", redes[:4], 1)  # falta logistica
    e = " ".join(transmisiones.errores(transmisiones.plan(esc, "azul"), 1))
    assert "fuera de la banda HF" in e and "guardia" in e and "pisa a" in e and "Falta la red Logística" in e
    transmisiones.guardar(esc, "azul", sug["redes"], 1)
    assert any("vencido" in x for x in transmisiones.errores(transmisiones.plan(esc, "azul"), 1 + transmisiones.VIGENCIA_TURNOS + 1))


def test_el_plan_cambia_la_demora_de_las_ordenes():
    u = SimpleNamespace(bando="azul", lat=0.0, lon=0.0)
    zona = SimpleNamespace(bando="rojo", lat=0.0, lon=0.0, radio_km=25, unidad_id=None)
    sin_plan = _esc()
    assert orders.prob_demora(sin_plan, u, ge_mod.Contexto([zona])) == 0.6
    valido = _esc()
    transmisiones.guardar(valido, "azul", transmisiones.sugerido("azul", 1)["redes"], 1)
    assert orders.prob_demora(valido, u, ge_mod.Contexto([zona])) == 0.4  # salta a la secundaria: la mitad
    malo = _esc()
    redes = transmisiones.sugerido("azul", 1)["redes"]
    redes[0] = {**redes[0], "primaria": 121.5}
    transmisiones.guardar(malo, "azul", redes, 1)
    assert transmisiones.demora_extra_pct(malo, "azul", 1) == transmisiones.DEMORA_PLAN_PCT
    assert transmisiones.demora_extra_pct(sin_plan, "azul", 1) == 0.0
    assert "Mando y control" in transmisiones.lineas_spins(valido, "azul")
    assert "sin plan" in transmisiones.lineas_spins(sin_plan, "azul")


def test_api_cada_bando_guarda_su_plan_y_va_a_los_spins(api):
    prof, base, *_ = _preparar(api)
    alfa, bravo = api("alfa"), api("bravo")
    estado = alfa.get(base).json()
    assert set(estado["transmisiones"]) == {"azul"} and estado["transmisiones"]["azul"]["plan"] is None
    redes = [{k: r[k] for k in ("red", "banda", "primaria", "secundaria", "indicativo")}
             for r in estado["transmisiones"]["azul"]["sugerido"]["redes"]]
    r = alfa.put(f"{base}/transmisiones", json={"bando": "rojo", "redes": redes})  # el alumno no elige el bando
    assert r.status_code == 200 and r.json()["errores"] == []
    assert alfa.get(base).json()["transmisiones"]["azul"]["plan"] is not None
    assert bravo.get(base).json()["transmisiones"]["rojo"]["plan"] is None
    assert any("Mando y control" in x for x in alfa.get(f"{base}/misiones/ota").json()["spins"])
    assert api("obs").put(f"{base}/transmisiones", json={"redes": redes}).status_code == 403


def test_api_avanzar_varios_turnos_y_estado_liviano(api, db_engine):
    prof, base, a, *_ = _preparar(api)
    alfa = api("alfa")
    assert prof.post(f"{base}/avanzar_turno?n=99").status_code == 400
    for _ in range(2):
        alfa.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.01, 0.0]]})
        prof.post(f"{base}/avanzar_turno")
    antes = prof.get(base).json()["escenario"]["turno_actual"]
    r = prof.post(f"{base}/avanzar_turno?n=6")
    assert r.status_code == 200 and r.json()["escenario"]["turno_actual"] == antes + 6
    from sqlalchemy.orm import sessionmaker
    with sessionmaker(bind=db_engine)() as db:
        assert db.query(Orden).count() >= 2
    assert prof.get(base).json()["ordenes"] == []  # las resueltas hace mas de 3 turnos ya no viajan con el estado
