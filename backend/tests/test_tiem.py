"""TIEM, etapa 1: calendario D/H y fases, Problema Militar Operativo (redactado o generado), cadena de objetivos
con efecto deseado y quien conduce cada bando (alumnos, instructor o IA)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.engine import calendario, objetivos, plantillas, pmo
from app.models.escenario import Escenario
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad
from tests.test_api import _preparar


def _esc(**kw):
    base = dict(hora_inicio_min=360, fecha_inicio="2026-10-20", turno_h=None, turno_final=None, fases_json=None,
                turno_actual=1)
    base.update(kw)
    return SimpleNamespace(**base)


# ---------- calendario ----------
def test_referencias_d_y_h_de_cada_turno():
    esc = _esc(turno_h=4)  # turno 1 a las 06:00 del 20; H = turno 4 = 09:00 del 20
    assert calendario.referencia(esc, 4) == {"turno": 4, "fecha": "2026-10-20", "hora": "09:00", "dia": "D", "hora_h": "H",
                                             "fase": "Ejecucion"}
    assert calendario.referencia(esc, 1)["hora_h"] == "H-3"
    r = calendario.referencia(esc, 22)  # 03:00 del dia siguiente
    assert (r["fecha"], r["hora"], r["dia"], r["hora_h"]) == ("2026-10-21", "03:00", "D+1", "H+18")
    assert calendario.texto(r) == "D+1 · H+18 · 03:00 · Ejecucion"
    sin = _esc(fecha_inicio=None, turno_h=None)
    assert calendario.resumen(sin) is None
    assert calendario.referencia(sin, 3)["dia"] is None


def test_fases_por_defecto_y_validacion():
    f = calendario.fases_por_defecto(5, 24)
    assert [(x["nombre"], x["desde"], x["hasta"]) for x in f] == [
        ("Alistamiento", 1, 2), ("Concentracion y despliegue", 3, 4), ("Ejecucion", 5, 22), ("Repliegue", 23, 24)]
    assert [x["nombre"] for x in calendario.fases_por_defecto(1, None)] == ["Ejecucion"]
    with pytest.raises(ValueError):
        calendario.validar_fases([{"nombre": "A", "desde": 1, "hasta": 5}, {"nombre": "B", "desde": 4, "hasta": 9}])
    with pytest.raises(ValueError):
        calendario.validar_fases([{"nombre": "A", "desde": 6, "hasta": 2}])
    assert calendario.validar_fases([{"nombre": " B ", "desde": 4, "hasta": None}, {"nombre": "A", "desde": 1, "hasta": 3}]) == [
        {"nombre": "A", "desde": 1, "hasta": 3}, {"nombre": "B", "desde": 4, "hasta": None}]


# ---------- mision ----------
def test_reglas_para_enunciar_la_mision():
    bien = {"tarea": "Conducir operaciones aéreas defensivas", "que": "para impedir la superioridad aérea enemiga",
            "donde": "en el área de operaciones", "cuando": "a partir de D/H", "proposito": "preservar la soberanía"}
    assert pmo.avisos_mision(bien) == []
    assert pmo.texto_mision(bien) == ("Conducir operaciones aéreas defensivas para impedir la superioridad aérea enemiga "
                                      "en el área de operaciones a partir de D/H, a fin de preservar la soberanía.")
    mal = dict(bien, tarea="Operaciones defensivas", proposito="", cuando="si el enemigo ataca")
    avisos = " ".join(pmo.avisos_mision(mal))
    assert "infinitivo" in avisos and "propósito" in avisos and "condiciones" in avisos


# ---------- objetivos: neutralizar, efecto y plazos ----------
def _obj(db, esc, **kw):
    o = Objetivo(escenario_id=esc.id, bando="azul", nombre=kw.pop("nombre", "O"), **kw)
    db.add(o)
    db.flush()
    return o


def test_neutralizar_efecto_y_plazo(db_session):
    esc = Escenario(nombre="E", turno_actual=3)
    db_session.add(esc)
    db_session.flush()
    r1 = Unidad(escenario_id=esc.id, nombre="R1", bando="rojo", tipo="terrestre", lat=0, lon=0, fuerza=45)
    r2 = Unidad(escenario_id=esc.id, nombre="R2", bando="rojo", tipo="terrestre", lat=0, lon=0, fuerza=90)
    r3 = Unidad(escenario_id=esc.id, nombre="R3", bando="rojo", tipo="terrestre", lat=0, lon=0, fuerza=90)
    db_session.add_all([r1, r2, r3])
    db_session.flush()
    ult = _obj(db_session, esc, tipo="efecto", nivel="ulterior", umbral=100)
    asig = _obj(db_session, esc, tipo="efecto", nivel="asignado", padre_id=ult.id, umbral=50)
    n1 = _obj(db_session, esc, tipo="neutralizar", unidad_id=r1.id, padre_id=asig.id)  # fuerza 45 <= 50: cumplido
    n2 = _obj(db_session, esc, tipo="neutralizar", unidad_id=r2.id, padre_id=asig.id, umbral=30)
    plazo = _obj(db_session, esc, tipo="destruir", unidad_id=r3.id, hasta_turno=3)  # vence sin destruirla
    db_session.commit()
    cambiados = objetivos.evaluar(db_session, esc)
    assert (n1.estado, n2.estado, plazo.estado) == ("cumplido", "pendiente", "fallido")
    assert asig.estado == "cumplido" and ult.estado == "cumplido"  # 1 de 2 alcanza el 50 %; el ulterior, su unico hijo
    assert {o.id for o in cambiados} == {n1.id, plazo.id, asig.id, ult.id}
    assert objetivos.avance_efecto(asig, [n1, n2]) == {"cumplidos": 1, "total": 2, "requerido_pct": 50}


def test_un_efecto_falla_cuando_ya_no_puede_alcanzar_su_umbral():
    o = SimpleNamespace(umbral=100.0)
    hijos = [SimpleNamespace(estado="cumplido"), SimpleNamespace(estado="fallido")]
    assert objetivos.estado_efecto(o, hijos) == "fallido"
    assert objetivos.estado_efecto(SimpleNamespace(umbral=50.0), hijos) == "cumplido"
    assert objetivos.estado_efecto(o, []) == "pendiente"


# ---------- generacion automatica ----------
def test_la_situacion_se_genera_sola_a_partir_del_escenario(db_session):
    esc = plantillas.crear_desde_plantilla(db_session, "teatro_ficticio")
    hecho = pmo.generar(db_session, esc, hoy=date(2026, 10, 15))
    db_session.commit()
    assert hecho["calendario"] and set(hecho["pmo"]) == {"azul", "rojo"} and hecho["objetivos"] > 2
    assert (esc.fecha_inicio, esc.turno_h, esc.turno_final) == ("2026-10-16", 3, 24)
    for bando, pais, enemigo in (("azul", "Valdoria", "Ostrania"), ("rojo", "Ostrania", "Valdoria")):
        d = pmo.como_dict(pmo.obtener(db_session, esc, bando), bando)
        c = d["contenido"]
        assert d["origen"] == "automatico" and d["avisos_mision"] == []
        assert pais in c["situacion_general"] and enemigo in c["fuerzas_enemigas"]
        assert ", a fin de " in d["mision_texto"] and "día D (2026-10-16)" in d["mision_texto"]
        assert c["medios"].startswith("- Aeronaves:") and "paralelos" in c["area_operaciones"]
        assert "Ejecucion" in c["idea_general"] and "Restricciones" in c["limitaciones"]
    # la cadena: un ulterior por bando, con asignados que agrupan a todos los objetivos materiales
    objs = db_session.query(Objetivo).filter(Objetivo.escenario_id == esc.id).all()
    for b in ("azul", "rojo"):
        ult = [o for o in objs if o.bando == b and o.nivel == "ulterior"]
        asig = [o for o in objs if o.bando == b and o.nivel == "asignado"]
        assert len(ult) == 1 and asig and all(a.padre_id == ult[0].id for a in asig)
        assert all(o.padre_id in {a.id for a in asig} for o in objs if o.bando == b and o.nivel == "material")
    # repetir no duplica la cadena; un PMO del instructor se respeta salvo que se pida sobrescribirlo
    pmo.guardar(db_session, esc, "azul", {"situacion_general": "Redactada por el instructor"}, "instructor")
    otra = pmo.generar(db_session, esc)
    assert otra["objetivos"] == 0 and otra["pmo"] == ["rojo"] and not otra["calendario"]
    assert "instructor" in pmo.como_dict(pmo.obtener(db_session, esc, "azul"), "azul")["contenido"]["situacion_general"]
    assert "azul" in pmo.generar(db_session, esc, sobrescribir=True)["pmo"]


def test_el_pmo_no_revela_posiciones_exactas_del_enemigo(db_session):
    esc = plantillas.crear_desde_plantilla(db_session, "teatro_ficticio")
    pmo.generar(db_session, esc)
    texto = json.dumps(pmo.como_dict(pmo.obtener(db_session, esc, "azul"), "azul")["contenido"]["fuerzas_enemigas"])
    rojas = db_session.query(Unidad).filter(Unidad.escenario_id == esc.id, Unidad.bando == "rojo").all()
    assert not any(f"{u.lat:.3f}" in texto for u in rojas)
    assert not any(u.nombre in texto for u in rojas if u.tipo != "base" and not u.nombre.startswith(("Central", "Refin")))


# ---------- API ----------
def test_api_del_pmo_cada_bando_ve_el_suyo(api):
    prof, base, *_ = _preparar(api)
    r = prof.post(f"{base}/pmo/generar", json={})
    assert r.status_code == 200 and set(r.json()["bandos"]) == {"azul", "rojo"} and r.json()["calendario"]["turno_h"] == 3
    alfa = api("alfa")
    vista = alfa.get(f"{base}/pmo").json()
    assert list(vista["bandos"]) == ["azul"] and vista["bandos"]["azul"]["existe"]
    assert alfa.post(f"{base}/pmo/generar", json={}).status_code == 403
    assert alfa.put(f"{base}/pmo/azul", json={"contenido": {}}).status_code == 403
    nuevo = {"situacion_general": "Texto del instructor", "mision": {"tarea": "Defender", "que": "la base",
             "donde": "en el área", "cuando": "desde H", "proposito": "preservar la soberanía"}}
    r = prof.put(f"{base}/pmo/rojo", json={"contenido": nuevo})
    assert r.status_code == 200 and r.json()["bandos"]["rojo"]["origen"] == "instructor"
    assert api("bravo").get(f"{base}/pmo").json()["bandos"]["rojo"]["mision_texto"].endswith("a fin de preservar la soberanía.")
    eventos = [e for e in api("bravo").get(base).json()["eventos"] if e["tipo"] == "pmo"]
    assert eventos and all(e["bando_destino"] == "rojo" for e in eventos)


def test_api_calendario_y_fases(api):
    prof, base, *_ = _preparar(api)
    r = prof.patch(f"{base}/config", json={"fecha_inicio": "2026-11-02", "turno_h": 4, "turno_final": 20})
    cal = r.json()["escenario"]["calendario"]
    assert (cal["dia_d"], cal["hora_h"], cal["actual"]["hora_h"]) == ("2026-11-02", "09:00", "H-3")
    assert cal["fases"][0]["nombre"] == "Alistamiento" and not cal["fases_propias"]
    fases = [{"nombre": "Preparacion", "desde": 1, "hasta": 3}, {"nombre": "Ataque", "desde": 4, "hasta": None}]
    cal = prof.patch(f"{base}/config", json={"fases": fases}).json()["escenario"]["calendario"]
    assert [f["nombre"] for f in cal["fases"]] == ["Preparacion", "Ataque"] and cal["fases_propias"]
    malas = [{"nombre": "A", "desde": 1, "hasta": 5}, {"nombre": "B", "desde": 3, "hasta": None}]
    assert prof.patch(f"{base}/config", json={"fases": malas}).status_code == 400
    assert prof.patch(f"{base}/config", json={"turno_final": 2}).status_code == 400  # antes de H
    assert prof.patch(f"{base}/config", json={"fecha_inicio": "", "turno_h": 0, "fases": []}).json()["escenario"]["calendario"] is None


def test_el_instructor_puede_conducir_un_bando(api):
    prof, base, a, r1, r2 = _preparar(api)
    orden = {"unidad_id": r1["id"], "tipo": "mover", "waypoints": [[0.1, 0.0]]}
    cab = {"X-Conduce-Bando": "rojo"}
    assert prof.post(f"{base}/ordenes", json=orden, headers=cab).status_code == 403  # aun lo conducen los alumnos
    r = prof.patch(f"{base}/config", json={"conduccion_rojo": "instructor"})
    assert r.json()["escenario"]["conduccion_rojo"] == "instructor"
    assert prof.post(f"{base}/ordenes", json=orden).status_code == 403  # sin decir por que bando
    r = prof.post(f"{base}/ordenes", json=orden, headers=cab)
    assert r.status_code == 200, r.text
    assert prof.post(f"{base}/ordenes", json=dict(orden, unidad_id=a["id"]), headers=cab).status_code == 404  # no es rojo
    assert prof.post(f"{base}/listo", json={"listo": True}, headers=cab).status_code == 200
    # la IA tiene prioridad y se enciende desde el mismo selector
    r = prof.patch(f"{base}/config", json={"conduccion_rojo": "ia"})
    assert r.json()["escenario"]["ia_rojo"] is True and r.json()["escenario"]["conduccion_rojo"] == "ia"
    r = prof.patch(f"{base}/config", json={"conduccion_rojo": "alumnos"})
    assert r.json()["escenario"]["ia_rojo"] is False and r.json()["escenario"]["conduccion_rojo"] == "alumnos"
    # las ordenes del instructor no se evaluan como si fueran de un alumno
    rub = prof.get(f"{base}/aar/rubrica").json()
    assert "prof" not in {x["username"] for x in rub["alumnos"]}


def test_objetivos_de_la_cadena_por_api(api):
    prof, base, a, r1, r2 = _preparar(api)
    ruta = f"{base}/objetivos"
    ult = prof.post(ruta, json={"tipo": "efecto", "nivel": "ulterior", "bando": "azul", "nombre": "Restablecer la frontera"}).json()
    asig = prof.post(ruta, json={"tipo": "efecto", "nivel": "asignado", "bando": "azul", "nombre": "Superioridad aérea",
                                 "padre_id": ult["id"], "umbral": 50, "efecto": "Degradar la defensa aérea",
                                 "indicador": "Antiaéreas neutralizadas"}).json()
    r = prof.post(ruta, json={"tipo": "neutralizar", "bando": "azul", "nombre": "Neutralizar R1", "unidad_id": r1["id"],
                              "padre_id": asig["id"], "umbral": 40, "hasta_turno": 6})
    assert r.status_code == 200 and (r.json()["umbral"], r.json()["hasta_turno"], r.json()["padre_id"]) == (40, 6, asig["id"])
    # reglas de la cadena
    assert prof.post(ruta, json={"tipo": "efecto", "bando": "azul", "nombre": "x"}).status_code == 400  # efecto material
    assert prof.post(ruta, json={"tipo": "neutralizar", "bando": "azul", "nombre": "x", "unidad_id": a["id"]}).status_code == 400
    assert prof.post(ruta, json={"tipo": "efecto", "nivel": "ulterior", "bando": "azul", "nombre": "x",
                                 "padre_id": asig["id"]}).status_code == 400  # el superior debe tener nivel mas alto
    lista = api("alfa").get(ruta).json()["objetivos"]
    asig_v = next(o for o in lista if o["id"] == asig["id"])
    assert asig_v["avance"] == {"cumplidos": 0, "total": 1, "requerido_pct": 50.0} and asig_v["efecto"] == "Degradar la defensa aérea"
    r = prof.patch(f"{ruta}/{asig['id']}", json={"indicador": "Dos antiaéreas fuera de servicio", "umbral": 100})
    assert r.status_code == 200 and r.json()["indicador"] == "Dos antiaéreas fuera de servicio"
    assert prof.delete(f"{ruta}/{asig['id']}").status_code == 200
    assert all(o["padre_id"] is None for o in prof.get(ruta).json()["objetivos"] if o["nombre"] == "Neutralizar R1")


def test_plantilla_guarda_pmo_calendario_y_cadena(db_session, monkeypatch):
    esc = plantillas.crear_desde_plantilla(db_session, "teatro_ficticio")
    pmo.generar(db_session, esc)
    esc.conduce_rojo = "instructor"
    db_session.commit()
    datos = plantillas.serializar_escenario(db_session, esc, "Con TIEM", "", False)
    assert datos["turno_h"] == esc.turno_h and set(datos["pmo"]) == {"azul", "rojo"}
    assert any(o["nivel"] == "asignado" and o["padre"] for o in datos["objetivos"])
    p = plantillas.desde_dict(datos)
    monkeypatch.setitem(plantillas.PLANTILLAS, p.id, p)
    copia = plantillas.crear_desde_plantilla(db_session, p.id)
    assert (copia.turno_h, copia.conduce_rojo) == (esc.turno_h, "instructor")
    assert pmo.obtener(db_session, copia, "azul") is not None
    objs = db_session.query(Objetivo).filter(Objetivo.escenario_id == copia.id).all()
    ids = {o.id for o in objs}
    assert sum(1 for o in objs if o.padre_id in ids) == sum(1 for o in objs if o.nivel != "ulterior")
