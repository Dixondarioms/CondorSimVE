"""TIEM, etapa 4: decision del Comandante, analisis previo al plan, Plan de Operaciones y sus tareas, que se emiten
como ordenes del simulador desde la Orden de Operaciones."""

from app.engine import tiem
from app.models.orden import Orden
from tests.test_api import _preparar


def test_tareas_del_plan():
    t = tiem.normalizar_tarea({"unidad_id": "3", "tipo": "atacar", "turno": "2", "objetivo": "u:7", "objetivo_nombre": "R1",
                               "unidad_nombre": "A", "id": "abcd1234"})
    assert t == {"id": "abcd1234", "unidad_id": 3, "unidad_nombre": "A", "tipo": "atacar", "turno": 2, "objetivo": "u:7",
                 "objetivo_nombre": "R1", "detalle": ""}
    assert tiem.texto_tarea(t, "H+1") == "Atacar con A a R1 (turno 2, H+1)"
    malo = tiem.normalizar_tarea({"tipo": "bailar", "objetivo": "x:1", "id": "MAL ID", "detalle": "algo"})
    assert malo["tipo"] == "" and malo["objetivo"] == "" and len(malo["id"]) == 8
    assert tiem.normalizar_tarea({}) is None
    r = tiem.revisar("plan_operaciones", {"tareas": [{"unidad_id": 3, "tipo": "mover"}]})
    assert any("Tarea 1: falta turno, objetivo o destino" in f for f in r["faltan"])


def test_decision_y_plan_quien_los_redacta():
    assert tiem.DOCUMENTOS["decision"].redactan == ("comandante",)
    assert tiem.DOCUMENTOS["analisis_previo"].paso == "Fase II · Paso 1"
    assert "a3" in tiem.DOCUMENTOS["plan_operaciones"].redactan


def _alumnos(api):
    prof = api("prof")
    for nombre, puesto in (("ua3", "a3"), ("ujem", "jem"), ("ua4", "a4")):
        assert prof.post("/api/usuarios", json={"username": nombre, "password": "clave-segura-1", "rol": "azul",
                                                "puesto": puesto}).status_code == 200
    return _preparar(api)


def test_sugerencias_de_la_decision_y_el_plan(api):
    prof, base, *_ = _alumnos(api)
    prof.post(f"{base}/pmo/generar", json={})
    ruta = f"{base}/tiem/azul"
    alfa, a3 = api("alfa"), api("ua3")
    a3.put(f"{ruta}/apreciacion_operaciones", json={"contenido": {"fa_recomendada": "F/A 1: Neutralizar", "justificacion": "Menor riesgo"}})
    assert a3.put(f"{ruta}/decision", json={"contenido": {}}).status_code == 403  # solo el Comandante
    s = alfa.get(f"{ruta}/decision/sugerencias").json()["contenido"]
    assert s["fa_adoptada"] == "F/A 1: Neutralizar" and s["fundamentacion"] == "Menor riesgo" and s["organizacion_fuerza"]
    alfa.put(f"{ruta}/decision", json={"contenido": {"fa_adoptada": "F/A 1", "idea_maniobra": "Primero la defensa aérea."}})
    p = a3.get(f"{ruta}/plan_operaciones/sugerencias").json()["contenido"]
    assert p["concepto"] == "Primero la defensa aérea." and p["mision"]["tarea"] and p["organizacion_fuerzas"]
    prev = a3.get(f"{ruta}/analisis_previo/sugerencias").json()["contenido"]
    assert "Decisión del Comandante: F/A 1" in prev["estudio"]


def test_las_tareas_del_plan_se_emiten_como_ordenes(api):
    prof, base, a, r1, r2 = _alumnos(api)
    ruta = f"{base}/tiem/azul"
    a3, a4 = api("ua3"), api("ua4")
    vista = a3.get(f"{base}/tiem").json()
    opciones = vista["opciones_tarea"]["azul"]
    assert [u["nombre"] for u in opciones["unidades"]] == ["A"]
    claves = {o["clave"]: o["grupo"] for o in opciones["objetivos"]}
    assert claves.get(f"u:{r1['id']}") == "Unidades enemigas conocidas"  # R1 esta a 5 km: se lo ve
    assert f"u:{r2['id']}" not in claves  # R2, a 200 km, no
    tareas = [
        {"id": "t0000001", "unidad_id": a["id"], "unidad_nombre": "A", "tipo": "atacar", "turno": 1, "objetivo": f"u:{r1['id']}", "objetivo_nombre": "R1"},
        {"id": "t0000002", "unidad_id": a["id"], "unidad_nombre": "A", "tipo": "mover", "turno": 1, "objetivo": f"u:{r2['id']}", "objetivo_nombre": "R2"},
        {"id": "t0000003", "unidad_id": a["id"], "unidad_nombre": "A", "tipo": "mover", "turno": 3, "objetivo": f"u:{r1['id']}", "objetivo_nombre": "R1"},
    ]
    assert a3.put(f"{ruta}/plan_operaciones", json={"contenido": {"tareas": tareas}}).status_code == 200
    # la A-4 no conduce esa unidad: la validacion de la orden la rechaza con el motivo
    r = a4.post(f"{ruta}/emitir", json={}).json()
    assert r["emitidas"] == 0 and all(not x["ok"] for x in r["resultados"]) and len(r["resultados"]) == 2
    r = a3.post(f"{ruta}/emitir", json={}).json()
    por_id = {x["id"]: x for x in r["resultados"]}
    assert set(por_id) == {"t0000001", "t0000002"}  # la del turno 3 todavia no vence
    assert por_id["t0000001"]["ok"] and "Atacar con A a R1" in por_id["t0000001"]["texto"]
    assert not por_id["t0000002"]["ok"] and "localizarlo" in por_id["t0000002"]["motivo"]  # R2 no se conoce
    ej = a3.get(f"{base}/tiem").json()["ejecuciones"]["azul"]
    assert ej["t0000001"]["estado"] == "emitida" and ej["t0000002"]["estado"] == "rechazada"
    ordenes = a3.get(f"{base}/ordenes").json()
    assert [(o["tipo"], o["objetivo_unidad_id"], o["autor"]) for o in ordenes] == [("atacar", r1["id"], "ua3")]
    # emitir de nuevo solo reintenta la rechazada (la emitida no se duplica)
    r = a3.post(f"{ruta}/emitir", json={}).json()
    assert [x["id"] for x in r["resultados"]] == ["t0000002"]
    # el instructor tambien puede emitir las de un bando (como su comandante)
    assert prof.post(f"{ruta}/emitir", json={"ids": ["t0000002"]}).status_code == 200
    assert api("bravo").post(f"{ruta}/emitir", json={}).status_code == 403


def test_tareas_hacia_objetivos_de_zona(api, db_session):
    prof, base, a, r1, r2 = _alumnos(api)
    zona = prof.post(f"{base}/objetivos", json={"tipo": "ocupar", "bando": "azul", "nombre": "Cruce", "lat": 0.2, "lon": 0.1}).json()
    tareas = [{"id": "z0000001", "unidad_id": a["id"], "tipo": "mover", "turno": 1, "objetivo": f"o:{zona['id']}", "objetivo_nombre": "Cruce"},
              {"id": "z0000002", "unidad_id": a["id"], "tipo": "atacar", "turno": 1, "objetivo": f"o:{zona['id']}", "objetivo_nombre": "Cruce"}]
    a3 = api("ua3")
    a3.put(f"{base}/tiem/azul/plan_operaciones", json={"contenido": {"tareas": tareas}})
    r = {x["id"]: x for x in a3.post(f"{base}/tiem/azul/emitir", json={}).json()["resultados"]}
    assert "hace falta una unidad" in r["z0000002"]["motivo"]
    assert r["z0000001"]["ok"]
    o = db_session.query(Orden).filter(Orden.id == r["z0000001"]["orden_id"]).one()
    assert o.tipo == "mover" and "0.2" in o.waypoints_json
