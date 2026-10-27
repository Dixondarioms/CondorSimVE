"""TIEM, etapa 5: supervision de la ejecucion (objetivo, resultado, diferencia, causa y accion correctiva), parte del
turno y ordenes fragmentarias que se emiten como ordenes."""

from app.engine import tiem
from tests.test_api import _preparar


def _alumnos(api):
    prof = api("prof")
    assert prof.post("/api/usuarios", json={"username": "ua3", "password": "clave-segura-1", "rol": "azul",
                                            "puesto": "a3"}).status_code == 200
    return _preparar(api)


def _tarea(id_, unidad, tipo, turno, objetivo, nombre):
    return {"id": id_, "unidad_id": unidad["id"], "unidad_nombre": unidad["nombre"], "tipo": tipo, "turno": turno,
            "objetivo": objetivo, "objetivo_nombre": nombre}


def test_el_documento_de_supervision():
    d = tiem.DOCUMENTOS["supervision"]
    assert d.paso == "Fase III" and "a3" in d.redactan
    assert [c.clave for c in d.campos] == ["registro", "apreciaciones_rapidas", "ordenes_fragmentarias"]
    assert tiem.revisar("supervision", {})["faltan"] == []  # se lleva todo el ejercicio: nada es obligatorio


def test_el_cuadro_de_supervision_compara_lo_previsto_con_lo_ocurrido(api):
    prof, base, a, r1, r2 = _alumnos(api)
    a3 = api("ua3")
    tareas = [_tarea("s0000001", a, "atacar", 1, f"u:{r1['id']}", "R1"),  # se emitira y cumplira
              _tarea("s0000002", a, "mover", 1, f"u:{r2['id']}", "R2")]    # R2 no se conoce: rechazada
    a3.put(f"{base}/tiem/azul/plan_operaciones", json={"contenido": {"tareas": tareas}})
    prof.post(f"{base}/objetivos", json={"tipo": "destruir", "bando": "azul", "nombre": "Destruir R2", "unidad_id": r2["id"],
                                         "hasta_turno": 2})
    sup = a3.get(f"{base}/tiem").json()["supervision"]["azul"]
    filas = {f["clave"]: f for f in sup["cuadro"]}
    assert filas["t:s0000001"]["estado"] == "desvio" and "No se emitió" in filas["t:s0000001"]["resultado"]
    assert sup["parte"] is None  # todavia no se resolvio ningun turno
    a3.post(f"{base}/tiem/azul/emitir", json={})
    filas = {f["clave"]: f for f in a3.get(f"{base}/tiem").json()["supervision"]["azul"]["cuadro"]}
    assert filas["t:s0000001"]["estado"] == "en curso"
    assert filas["t:s0000002"]["estado"] == "desvio" and "localizarlo" in filas["t:s0000002"]["causa_sugerida"]
    destruir = next(f for k, f in filas.items() if k.startswith("o:"))
    assert destruir["estado"] == "desvio" and "Vence en la hora 2" in destruir["diferencia"]
    # pasa una hora: el ataque sigue en curso (fuego continuo mientras R1 resista) y aparece el parte de la hora 1
    assert prof.post(f"{base}/avanzar_turno").status_code == 200
    sup = a3.get(f"{base}/tiem").json()["supervision"]["azul"]
    filas = {f["clave"]: f for f in sup["cuadro"]}
    assert filas["t:s0000001"]["estado"] == "en curso" and "cumpliendo" in filas["t:s0000001"]["resultado"]
    assert sup["parte"]["turno"] == 1 and "1 en curso" in sup["parte"]["lineas"][0]
    # si se detiene la orden, la tarea queda con desvio
    orden_id = next(o["id"] for o in a3.get(f"{base}/ordenes").json() if o["tipo"] == "atacar")
    assert a3.delete(f"{base}/ordenes/{orden_id}").status_code == 200
    filas = {f["clave"]: f for f in a3.get(f"{base}/tiem").json()["supervision"]["azul"]["cuadro"]}
    assert filas["t:s0000001"]["estado"] == "desvio" and "otra orden" in filas["t:s0000001"]["causa_sugerida"]
    assert sup["cuenta"]["desvio"] >= 1
    # el enemigo no ve la supervision de azul
    assert list(api("bravo").get(f"{base}/tiem").json()["supervision"]) == ["rojo"]


def test_las_ordenes_fragmentarias_se_emiten_aunque_el_plan_este_aprobado(api):
    prof, base, a, r1, r2 = _alumnos(api)
    a3 = api("ua3")
    ruta = f"{base}/tiem/azul"
    a3.put(f"{ruta}/plan_operaciones", json={"contenido": {"tareas": [_tarea("p0000001", a, "mover", 5, f"u:{r1['id']}", "R1")]}})
    prof.post(f"{ruta}/plan_operaciones/revisar", json={"estado": "aprobado"})
    assert a3.put(f"{ruta}/plan_operaciones", json={"contenido": {}}).status_code == 400  # el plan queda bloqueado
    frago = {"ordenes_fragmentarias": [_tarea("f0000001", a, "atacar", 1, f"u:{r1['id']}", "R1")],
             "registro": [{"turno": "1", "objetivo": "Mover A", "diferencia": "R1 se adelantó", "causa": "Ataque enemigo",
                           "accion": "Atacar R1 de inmediato", "estado": "abierta"}]}
    assert a3.put(f"{ruta}/supervision", json={"contenido": frago}).status_code == 200
    r = a3.post(f"{ruta}/emitir", json={}).json()
    assert [(x["id"], x["ok"]) for x in r["resultados"]] == [("f0000001", True)]
    filas = {f["clave"]: f for f in a3.get(f"{base}/tiem").json()["supervision"]["azul"]["cuadro"]}
    assert filas["t:f0000001"]["origen"] == "Orden fragmentaria"
