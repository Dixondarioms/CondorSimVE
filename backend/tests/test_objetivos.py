"""Objetivos del ejercicio, marcador, informe y editor de escenarios (borrar unidades, duplicar)."""

import json

import pytest

from app.engine import objetivos as motor
from app.models.aar import Combate
from app.models.evento import Evento
from app.models.objetivo import Objetivo
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.test_aeronaves import _base_aerea
from tests.test_api import _preparar
from tests.test_orders import _avanzar, _escenario, _unidad


def _objetivo(db, esc, **kw):
    o = Objetivo(**{**dict(escenario_id=esc.id, bando="azul", tipo="ocupar", nombre="Cerro 1", puntos=20, lat=0.0, lon=0.0,
                            radio_km=5.0, turnos_requeridos=1), **kw})
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


# ---------- ocupar ----------
def test_ocupar_se_cumple_al_mantener_la_zona_los_turnos_pedidos(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="Inf", lat=0.01)
    o = _objetivo(db_session, esc, turnos_requeridos=2)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert (o.estado, o.progreso) == ("pendiente", 1)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert (o.estado, o.progreso, o.turno_resuelto) == ("cumplido", 2, 2)
    assert motor.marcador(db_session, esc)["azul"]["objetivos"] == 20
    ev = db_session.query(Evento).filter_by(tipo="objetivo").one()
    assert ev.bando_destino == "azul" and "cumplido: Cerro 1" in ev.descripcion and "+20" in ev.descripcion
    _avanzar(db_session, esc)  # un objetivo resuelto ya no cambia ni suma dos veces
    assert motor.marcador(db_session, esc)["azul"]["objetivos"] == 20
    assert db_session.query(Evento).filter_by(tipo="objetivo").count() == 1


def test_ocupar_se_reinicia_si_el_enemigo_entra_o_se_sale_de_la_zona(db_session):
    esc = _escenario(db_session)
    inf = _unidad(db_session, esc, nombre="Inf", lat=0.01)
    o = _objetivo(db_session, esc, turnos_requeridos=3)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.progreso == 1
    enemigo = _unidad(db_session, esc, nombre="Rojo", bando="rojo", lat=0.02)  # disputa la zona
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.progreso == 0
    enemigo.estado = "destruida"
    inf.lat = 1.0  # se retira
    db_session.commit()
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.progreso == 0 and o.estado == "pendiente"


def test_solo_cuentan_las_unidades_terrestres_activas(db_session):
    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="Avion", tipo="aerea", clase="caza", lat=0.0)
    _unidad(db_session, esc, nombre="Muerta", lat=0.0, estado="destruida")
    o = _objetivo(db_session, esc)
    _avanzar(db_session, esc)
    db_session.refresh(o)
    assert o.estado == "pendiente" and o.progreso == 0


# ---------- destruir y proteger ----------
def test_destruir_se_cumple_cuando_la_unidad_cae(db_session):
    esc = _escenario(db_session)
    objetivo = _unidad(db_session, esc, nombre="Puesto de mando", bando="rojo", lat=0.03, fuerza=1.0)
    art = _unidad(db_session, esc, nombre="Art", clase="artilleria", lat=0.0, alcance_km=30)
    o = _objetivo(db_session, esc, tipo="destruir", unidad_id=objetivo.id, nombre="Destruir el PM", puntos=50, lat=None, lon=None)
    db_session.add(Orden(escenario_id=esc.id, unidad_id=art.id, tipo="atacar", objetivo_unidad_id=objetivo.id, turno_emitida=1))
    db_session.commit()
    _avanzar(db_session, esc)
    db_session.refresh(o)
    db_session.refresh(objetivo)
    assert objetivo.estado == "destruida" and o.estado == "cumplido" and o.turno_resuelto == 1
    m = motor.marcador(db_session, esc)
    assert m["azul"]["objetivos"] == 50 and m["azul"]["total"] >= 50 and m["rojo"]["objetivos"] == 0


def test_proteger_falla_si_la_unidad_cae_y_se_cumple_al_llegar_al_turno(db_session):
    esc = _escenario(db_session)
    frag = _unidad(db_session, esc, nombre="Frágil", lat=0.0, fuerza=1.0)
    solida = _unidad(db_session, esc, nombre="Sólida", lat=1.0)
    art = _unidad(db_session, esc, nombre="ArtR", bando="rojo", clase="artilleria", lat=0.05, alcance_km=30)
    perdida = _objetivo(db_session, esc, tipo="proteger", unidad_id=frag.id, nombre="Salvar la frágil", hasta_turno=5, lat=None, lon=None)
    ganada = _objetivo(db_session, esc, tipo="proteger", unidad_id=solida.id, nombre="Mantener la sólida", hasta_turno=2, lat=None, lon=None, puntos=30)
    db_session.add(Orden(escenario_id=esc.id, unidad_id=art.id, tipo="atacar", objetivo_unidad_id=frag.id, turno_emitida=1))
    db_session.commit()
    _avanzar(db_session, esc)
    db_session.refresh(perdida)
    db_session.refresh(ganada)
    assert perdida.estado == "fallido" and ganada.estado == "pendiente"
    _avanzar(db_session, esc)
    db_session.refresh(ganada)
    assert ganada.estado == "cumplido" and ganada.turno_resuelto == 2
    assert motor.marcador(db_session, esc)["azul"]["objetivos"] == 30  # el fallido no suma
    assert "fallido: Salvar la frágil" in db_session.query(Evento).filter(Evento.descripcion.like("%fallido%")).one().descripcion


def test_el_marcador_suma_un_punto_por_cada_10_de_fuerza_infligida_en_ambos_sentidos(db_session):
    esc = _escenario(db_session)
    a = _unidad(db_session, esc, nombre="A")
    r = _unidad(db_session, esc, nombre="R", bando="rojo", lat=0.05)
    db_session.add_all([
        Combate(escenario_id=esc.id, turno=1, atacante_id=a.id, defensor_id=r.id, atacante_nombre="A", defensor_nombre="R",
                atacante_bando="azul", defensor_bando="rojo", ratio=1.0, fuerza_ini_atacante=100, fuerza_ini_defensor=100,
                perdida_atacante=14.0, perdida_defensor=37.0, lat=0, lon=0),
        Combate(escenario_id=esc.id, turno=2, atacante_id=r.id, defensor_id=a.id, atacante_nombre="R", defensor_nombre="A",
                atacante_bando="rojo", defensor_bando="azul", ratio=1.0, fuerza_ini_atacante=80, fuerza_ini_defensor=90,
                perdida_atacante=5.0, perdida_defensor=25.0, lat=0, lon=0),
    ])
    db_session.commit()
    m = motor.marcador(db_session, esc)
    # azul inflige 37 (atacando) + 5 (defendiendo) = 42 -> 4 puntos; rojo inflige 25 (atacando) + 14 (defendiendo) = 39 -> 3
    assert m["azul"]["bajas"] == 4 and m["rojo"]["bajas"] == 3
    assert m["azul"]["total"] == 4 and m["rojo"]["total"] == 3


# ---------- API ----------
def _crear(prof, base, **kw):
    return prof.post(f"{base}/objetivos", json={**dict(tipo="ocupar", bando="azul", nombre="Cota 500", puntos=25, lat=0.1, lon=0.1, radio_km=4), **kw})


def test_solo_el_instructor_crea_y_borra_objetivos(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert _crear(api("alfa"), base).status_code == 403
    r = _crear(prof, base)
    assert r.status_code == 200, r.text
    assert (r.json()["tipo"], r.json()["puntos"], r.json()["estado"], r.json()["progreso"]) == ("ocupar", 25, "pendiente", 0)
    assert api("alfa").delete(f"{base}/objetivos/{r.json()['id']}").status_code == 403
    assert prof.delete(f"{base}/objetivos/{r.json()['id']}").status_code == 200
    assert prof.delete(f"{base}/objetivos/{r.json()['id']}").status_code == 404


def test_validacion_de_objetivos(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert "centro de la zona" in _crear(prof, base, lat=None, lon=None).json()["detail"]
    assert "unidad del escenario" in _crear(prof, base, tipo="destruir", unidad_id=None).json()["detail"]
    assert "unidad del escenario" in _crear(prof, base, tipo="destruir", unidad_id=999).json()["detail"]
    assert "bando contrario" in _crear(prof, base, tipo="destruir", unidad_id=a["id"]).json()["detail"]
    assert _crear(prof, base, tipo="destruir", unidad_id=r1["id"]).status_code == 200
    assert "propio bando" in _crear(prof, base, tipo="proteger", unidad_id=r1["id"], hasta_turno=5).json()["detail"]
    assert "hasta que turno" in _crear(prof, base, tipo="proteger", unidad_id=a["id"]).json()["detail"]
    assert _crear(prof, base, tipo="proteger", unidad_id=a["id"], hasta_turno=5).status_code == 200
    assert _crear(prof, base, puntos=-1).status_code == 422
    assert _crear(prof, base, radio_km=0).status_code == 422
    assert _crear(prof, base, tipo="capturar").status_code == 422


def test_cada_bando_ve_solo_sus_objetivos_pero_todos_ven_el_marcador(api):
    prof, base, a, r1, r2 = _preparar(api)
    _crear(prof, base, nombre="Objetivo azul")
    _crear(prof, base, bando="rojo", nombre="Objetivo rojo", lat=0.5)
    nombres = lambda c: sorted(o["nombre"] for o in c.get(base).json()["objetivos"])
    assert nombres(prof) == ["Objetivo azul", "Objetivo rojo"]
    assert nombres(api("obs")) == ["Objetivo azul", "Objetivo rojo"]
    assert nombres(api("alfa")) == ["Objetivo azul"]
    assert nombres(api("bravo")) == ["Objetivo rojo"]
    listado = api("alfa").get(f"{base}/objetivos").json()
    assert [o["nombre"] for o in listado["objetivos"]] == ["Objetivo azul"]
    assert set(listado["marcador"]) == {"azul", "rojo"}
    assert api("bravo").get(base).json()["marcador"]["azul"] == {
        "objetivos": 0, "bajas": 0, "total": 0, "cumplidos": 0, "fallidos": 0, "asignados": 1, "cumplidos_pct": 0.0, "colateral": 0, "neutrales_atacados": 0}


def test_un_objetivo_se_cumple_por_la_api_y_llega_al_informe(api):
    prof, base, a, r1, r2 = _preparar(api)
    _crear(prof, base, lat=0.0, lon=0.0, radio_km=3, puntos=40, nombre="Mantener el punto")
    assert prof.post(f"{base}/avanzar_turno").status_code == 200
    estado = api("alfa").get(base).json()
    assert estado["objetivos"][0]["estado"] == "cumplido" and estado["marcador"]["azul"]["total"] >= 40
    assert any(e["tipo"] == "objetivo" and "Mantener el punto" in e["descripcion"] for e in estado["eventos"])
    rojo = api("bravo").get(base).json()
    assert rojo["objetivos"] == [] and all(e["tipo"] != "objetivo" for e in rojo["eventos"])
    informe = prof.get(f"{base}/aar").json()
    assert informe["marcador"]["azul"]["objetivos"] == 40
    assert [o["nombre"] for o in informe["objetivos"]] == ["Mantener el punto"]
    assert prof.get(f"{base}/exportar").json()["objetivos"][0]["puntos"] == 40


def test_duplicar_copia_objetivos_y_modelos_de_aeronave(api):
    prof, base, a, r1, r2 = _preparar(api)
    caza = prof.post(f"{base}/unidades", json=dict(nombre="Halcon", bando="azul", modelo="f16", aeronaves=4, lat=0.2, lon=0.2)).json()
    _crear(prof, base, nombre="Zona")
    _crear(prof, base, tipo="destruir", unidad_id=r1["id"], nombre="Destruir R1")
    _crear(prof, base, bando="rojo", tipo="proteger", unidad_id=r1["id"], hasta_turno=9, nombre="Proteger R1")
    copia = prof.post(f"{base}/duplicar").json()
    base2 = f"/api/escenarios/{copia['id']}"
    unidades = {u["nombre"]: u for u in prof.get(base2).json()["unidades"]}
    assert (unidades["Halcon"]["modelo"], unidades["Halcon"]["aeronaves"]) == ("f16", 4)
    objetivos = {o["nombre"]: o for o in prof.get(base2).json()["objetivos"]}
    assert set(objetivos) == {"Zona", "Destruir R1", "Proteger R1"}
    assert objetivos["Destruir R1"]["unidad_id"] == unidades["R1"]["id"] != r1["id"]
    assert all(o["estado"] == "pendiente" and o["progreso"] == 0 for o in objetivos.values())
    assert caza["id"] not in [u["id"] for u in unidades.values()]


# ---------- editor: borrar unidades ----------
def test_borrar_una_unidad_limpia_sus_referencias(api):
    prof, base, a, r1, r2 = _preparar(api)
    _crear(prof, base, tipo="destruir", unidad_id=r1["id"], nombre="Destruir R1")
    orden = api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    assert orden.status_code == 200, orden.text
    assert api("alfa").delete(f"{base}/unidades/{r1['id']}").status_code == 403
    assert prof.delete(f"{base}/unidades/{r1['id']}").json() == {"ok": True}
    estado = prof.get(base).json()
    assert r1["id"] not in [u["id"] for u in estado["unidades"]]
    assert estado["objetivos"] == [] and estado["ordenes"] == []  # el objetivo y la orden que la citaban desaparecen
    assert prof.delete(f"{base}/unidades/{r1['id']}").status_code == 404
    eventos = [e["descripcion"] for t in prof.get(f"{base}/aar").json()["turnos"] for e in t["eventos"]]
    assert any("Unidad eliminada del escenario: R1 (rojo)" in d for d in eventos)  # queda constancia en el informe


def test_no_se_borra_una_unidad_que_ya_combatio(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]}).status_code == 200
    assert prof.post(f"{base}/avanzar_turno").status_code == 200
    r = prof.delete(f"{base}/unidades/{r1['id']}")
    assert r.status_code == 409 and "destruida" in r.json()["detail"]
    assert r1["id"] in [u["id"] for u in prof.get(base).json()["unidades"]]


def test_borrar_una_base_libera_a_los_aviones_estacionados(api):
    prof, base, a, r1, r2 = _preparar(api)
    ba = _base_aerea(prof, base, lat=0.0, lon=0.3)
    caza = prof.post(f"{base}/unidades", json=dict(nombre="C", bando="azul", modelo="f16", aeronaves=2, lat=0.0, lon=0.3)).json()
    with api.engine.begin() as con:
        from sqlalchemy import text
        con.execute(text("UPDATE unidades SET en_tierra=:t, base_id=:b, espera_restante=1 WHERE id=:i"), dict(t=True, b=ba["id"], i=caza["id"]))
    assert prof.delete(f"{base}/unidades/{ba['id']}").status_code == 200
    c = {u["nombre"]: u for u in prof.get(base).json()["unidades"]}["C"]
    assert (c["en_tierra"], c["base_id"], c["espera_restante"]) == (False, None, 0)
