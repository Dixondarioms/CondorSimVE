"""API: turnos, informe posterior, contactos, asignaciones, ver-como, seguridad."""

import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app import auth, turnos
from app.models.escenario import Escenario
from app.models.usuario import IntentoLogin, ahora
from app.routers import unidades as router_unidades
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar


def _esc_id(base):
    return base.rsplit("/", 1)[1]


# ---------- mecanica de turnos ----------
def test_listo_y_resolucion_automatica(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul, rojo = api("alfa"), api("bravo")
    prof.patch(f"{base}/config", json={"auto_resolver": True})

    e = azul.post(f"{base}/listo", json={"listo": True}).json()["escenario"]
    assert e["listo_azul"] and not e["listo_rojo"] and e["turno_actual"] == 1
    e = rojo.post(f"{base}/listo", json={"listo": True}).json()["escenario"]
    assert e["turno_actual"] == 2 and not e["listo_azul"] and not e["listo_rojo"]


def test_sin_resolucion_automatica_el_listo_no_avanza(api):
    prof, base, a, r1, r2 = _preparar(api)
    api("alfa").post(f"{base}/listo", json={"listo": True})
    e = api("bravo").post(f"{base}/listo", json={"listo": True}).json()["escenario"]
    assert e["turno_actual"] == 1 and e["listo_azul"] and e["listo_rojo"]


def test_emitir_o_cancelar_una_orden_anula_el_listo_del_bando(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    azul.post(f"{base}/listo", json={"listo": True})
    orden = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]}).json()
    assert not prof.get(base).json()["escenario"]["listo_azul"]
    azul.post(f"{base}/listo", json={"listo": True})
    azul.delete(f"{base}/ordenes/{orden['id']}")
    assert not prof.get(base).json()["escenario"]["listo_azul"]


def test_solo_los_bandos_marcan_listo(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert prof.post(f"{base}/listo", json={"listo": True}).status_code == 403
    assert api("obs").post(f"{base}/listo", json={"listo": True}).status_code == 403


def test_limite_de_decision_y_vencimiento(api):
    prof, base, a, r1, r2 = _preparar(api)
    e = prof.patch(f"{base}/config", json={"limite_decision_seg": 60}).json()["escenario"]
    assert e["limite_decision_seg"] == 60 and e["decision_termina_en"]

    Session = sessionmaker(bind=api.engine)
    with Session() as db:
        esc = db.get(Escenario, int(_esc_id(base)))
        esc.decision_termina_en = ahora() - timedelta(seconds=1)
        db.commit()
        assert asyncio.run(turnos.resolver_vencidos(db)) == [esc.id]
        db.refresh(esc)
        assert esc.turno_actual == 2 and esc.decision_termina_en > ahora()  # nuevo plazo
        assert asyncio.run(turnos.resolver_vencidos(db)) == []

    assert prof.patch(f"{base}/config", json={"limite_decision_seg": 0}).json()["escenario"]["decision_termina_en"] is None


def test_hora_simulada_inicial_configurable(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert prof.get(base).json()["escenario"]["hora_inicio_min"] == 360  # 06:00 por defecto
    e = prof.patch(f"{base}/config", json={"hora_inicio": "13:30"}).json()["escenario"]
    assert e["hora_inicio_min"] == 13 * 60 + 30
    for malo in ("25:00", "9:30", "12:60", "mediodia"):
        assert prof.patch(f"{base}/config", json={"hora_inicio": malo}).status_code == 422
    assert api("alfa").patch(f"{base}/config", json={"hora_inicio": "08:00"}).status_code == 403
    copia = prof.post(f"{base}/duplicar").json()
    assert copia["hora_inicio_min"] == 13 * 60 + 30


def test_las_ordenes_incluyen_sus_waypoints(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0.2], [0.3, 0.4]]})
    (o,) = azul.get(base).json()["ordenes"]
    assert o["waypoints"] == [[0.1, 0.2], [0.3, 0.4]] and o["tipo"] == "mover"
    azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    previa, o = azul.get(base).json()["ordenes"]  # tiempo real: la nueva reemplaza (cancela) a la anterior
    assert previa["estado"] == "cancelada" and o["estado"] == "en_ejecucion"
    assert o["waypoints"] == [] and o["objetivo_unidad_id"] == r1["id"]


def test_pausar_detiene_el_reloj(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.patch(f"{base}/config", json={"limite_decision_seg": 60})
    e = prof.post(f"{base}/pausar").json()["escenario"]
    assert e["decision_termina_en"] is None
    e = prof.post(f"{base}/reanudar").json()["escenario"]
    assert e["decision_termina_en"] is not None


def test_config_valida_y_solo_instructor(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert prof.patch(f"{base}/config", json={"clima": "granizo"}).status_code == 422
    assert prof.patch(f"{base}/config", json={"limite_decision_seg": -5}).status_code == 422
    assert api("alfa").patch(f"{base}/config", json={"clima": "lluvia"}).status_code == 403


def test_cambio_de_clima_avisa_a_todos(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.patch(f"{base}/config", json={"clima": "tormenta"})
    for nombre in ("alfa", "bravo"):
        est = api(nombre).get(base).json()
        assert est["escenario"]["clima"] == "tormenta"
        assert any(e["tipo"] == "clima" for e in est["eventos"])


def test_el_clima_reduce_lo_que_se_detecta(api):
    prof, base, a, r1, r2 = _preparar(api)  # R1 a ~5 km, deteccion de A = 10 km
    nombres = lambda: {u["nombre"] for u in api("alfa").get(base).json()["unidades"]}
    assert "R1" in nombres()
    prof.patch(f"{base}/config", json={"clima": "tormenta"})  # 10 km * 0.5 = 5 km < 5.005 km
    assert "R1" not in nombres()


# ---------- unidades: catalogo, ubicacion, ajustes ----------
def test_crear_unidad_por_clase_usa_los_valores_del_catalogo(api):
    prof, base, *_ = _preparar(api)
    r = prof.post(f"{base}/unidades", json={"nombre": "Blin", "bando": "azul", "clase": "blindado", "lat": 0, "lon": 0})
    assert r.status_code == 200
    u = r.json()
    assert (u["tipo"], u["clase"], u["velocidad_kmh"], u["autonomia_km"]) == ("terrestre", "blindado", 45, 250)
    assert u["sidc"].startswith("SFGPUCA") and len(u["sidc"]) == 15 and u["echelon"] == "compania"


def test_crear_unidad_valida_clase_tipo_y_escalon(api):
    prof, base, *_ = _preparar(api)
    crear = lambda **kw: prof.post(f"{base}/unidades", json=dict(nombre="x", bando="azul", lat=0, lon=0, **kw)).status_code
    assert crear(clase="no_existe") == 400
    assert crear(clase="caza", tipo="terrestre") == 400
    assert crear() == 400
    assert crear(clase="caza", echelon="galaxia") == 400
    assert crear(tipo="terrestre") == 200


def test_ubicacion_agua_y_tierra(api, monkeypatch):
    prof, base, *_ = _preparar(api)
    mar = TerrenoFalso(lambda lat, lon: "agua" if lon > 1 else "llano")
    monkeypatch.setattr(router_unidades, "get_terreno", lambda: mar)
    crear = lambda clase, lon: prof.post(
        f"{base}/unidades", json=dict(nombre="x", bando="azul", clase=clase, lat=0, lon=lon)).status_code
    assert crear("infanteria", 2) == 400  # terrestre en el agua
    assert crear("deposito", 2) == 400  # base en el agua
    assert crear("fragata", 0) == 400  # naval en tierra
    assert crear("fragata", 2) == 200
    assert crear("caza", 2) == 200  # las aereas van a cualquier parte


def test_ajuste_manual_queda_en_el_informe_y_no_lo_ven_los_alumnos(api):
    prof, base, a, r1, r2 = _preparar(api)
    assert prof.patch(f"{base}/unidades/{a['id']}", json={"fuerza": 40, "combustible": 20}).status_code == 200
    assert not any(e["tipo"] == "ajuste" for e in api("alfa").get(base).json()["eventos"])
    assert any(e["tipo"] == "ajuste" for e in prof.get(base).json()["eventos"])
    informe = prof.get(f"{base}/aar").json()  # el ajuste ocurrio en el turno 1, aun sin resolver
    (en_curso,) = [t for t in informe["turnos"] if t["en_curso"]]
    assert any("Ajuste manual de A" in ev["descripcion"] and "fuerza" in ev["descripcion"] for ev in en_curso["eventos"])


def test_previsualizar_movimiento(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes/previsualizar", json={"unidad_id": a["id"], "waypoints": [[1.0, 0.0]]})
    assert r.status_code == 200
    p = r.json()
    assert 0 < p["destino"][0] < 1.0 and p["km"] == pytest.approx(30, abs=1) and not p["llega"]
    assert p["combustible_restante"] == pytest.approx(90, abs=1) and len(p["ruta"]) >= 2
    r = azul.post(f"{base}/ordenes/previsualizar", json={"unidad_id": a["id"], "waypoints": [[0.01, 0.0]]})
    assert r.json()["llega"] is True
    assert api("bravo").post(f"{base}/ordenes/previsualizar", json={"unidad_id": a["id"], "waypoints": [[1, 0]]}).status_code == 404
    assert prof.post(f"{base}/ordenes/previsualizar", json={"unidad_id": a["id"], "waypoints": [[1, 0]]}).status_code == 403


def test_una_unidad_sin_municion_o_combustible_no_recibe_ordenes(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.patch(f"{base}/unidades/{a['id']}", json={"municion": 0, "combustible": 0})
    azul = api("alfa")
    assert azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]}).status_code == 400
    assert azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]}).status_code == 400


# ---------- contactos (ultimo conocido) ----------
def test_ultimo_contacto_conocido(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/avanzar_turno")  # turno 1: R1 visible -> queda registrado
    azul = api("alfa")
    assert azul.get(base).json()["contactos"] == []  # visible ahora: no es "contacto perdido"

    prof.patch(f"{base}/unidades/{r1['id']}", json={"lat": 1.0})  # sale del radio de deteccion
    prof.post(f"{base}/avanzar_turno")
    est = azul.get(base).json()
    assert "R1" not in {u["nombre"] for u in est["unidades"]}
    (c,) = est["contactos"]
    assert (c["nombre"], c["turno_visto"]) == ("R1", 2)  # tiempo real: se lo vio por ultima vez al empezar la hora 2
    assert c["lat"] == pytest.approx(0.045) and c["sidc"].startswith("SH")
    # el rojo tambien vio a A (5 km) y la perdio de vista: recuerda donde estaba
    assert [x["nombre"] for x in api("bravo").get(base).json()["contactos"]] == ["A"]


def test_un_contacto_destruido_desaparece(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/avanzar_turno")
    prof.patch(f"{base}/unidades/{r1['id']}", json={"lat": 1.0, "fuerza": 0})
    prof.post(f"{base}/avanzar_turno")
    assert api("alfa").get(base).json()["contactos"] == []


# ---------- ver como ----------
def test_ver_como_por_rest_y_solo_instructor(api):
    prof, base, a, r1, r2 = _preparar(api)
    nombres = lambda c, **p: {u["nombre"] for u in c.get(base, params=p).json()["unidades"]}
    assert nombres(prof) == {"A", "R1", "R2"}
    assert nombres(prof, vista="azul") == {"A", "R1"}
    assert nombres(prof, vista="rojo") == {"A", "R1", "R2"}  # rojo ve a A (detectada) y sus dos unidades
    assert api("alfa").get(base, params={"vista": "rojo"}).json()["vista"] == "azul"  # un alumno no puede


def test_ver_como_por_websocket(api):
    prof, base, a, r1, r2 = _preparar(api)
    with prof.websocket_connect(f"/ws/{_esc_id(base)}") as ws:
        assert ws.receive_json()["vista"] == "completa"
        assert ws.receive_json()["tipo"] == "chat_historial"
        ws.send_text(json.dumps({"vista": "azul"}))
        est = ws.receive_json()
        assert est["vista"] == "azul" and {u["nombre"] for u in est["unidades"]} == {"A", "R1"}
        ws.send_text(json.dumps({"vista": "completa"}))
        assert ws.receive_json()["vista"] == "completa"
    with api("alfa").websocket_connect(f"/ws/{_esc_id(base)}") as ws:
        ws.receive_json()
        ws.send_text(json.dumps({"vista": "rojo"}))  # ignorado para alumnos
        ws.send_text("ping")


# ---------- asignaciones y administracion ----------
def test_un_alumno_sin_asignar_no_ve_el_escenario(api):
    prof, base, a, r1, r2 = _preparar(api)
    ids = {u["username"]: u["id"] for u in prof.get("/api/usuarios").json()}
    prof.put(f"{base}/usuarios", json={"usuario_ids": [ids["alfa"]]})
    assert api("alfa").get(base).status_code == 200
    bravo = api("bravo")
    assert bravo.get(base).status_code == 404
    assert bravo.get(f"{base}/unidades").status_code == 404
    assert bravo.get(f"{base}/ordenes").status_code == 404
    assert bravo.get(f"{base}/aar").status_code == 404
    assert bravo.get("/api/escenarios").json() == []
    assert [e["id"] for e in api("alfa").get("/api/escenarios").json()] == [int(_esc_id(base))]
    with pytest.raises(WebSocketDisconnect):
        with bravo.websocket_connect(f"/ws/{_esc_id(base)}") as ws:
            ws.receive_json()


def test_asignar_ignora_instructores_e_ids_inexistentes(api):
    prof, base, *_ = _preparar(api)
    ids = {u["username"]: u["id"] for u in prof.get("/api/usuarios").json()}
    r = prof.put(f"{base}/usuarios", json={"usuario_ids": [ids["prof"], ids["alfa"], 9999]})
    assert r.json()["usuario_ids"] == [ids["alfa"]]
    assert prof.get(f"{base}/usuarios").json()["usuario_ids"] == [ids["alfa"]]
    assert api("alfa").put(f"{base}/usuarios", json={"usuario_ids": []}).status_code == 403


def test_archivar_oculta_del_listado(api):
    prof, base, *_ = _preparar(api)
    prof.post(f"{base}/archivar")
    assert prof.get("/api/escenarios").json() == []
    assert len(prof.get("/api/escenarios", params={"archivados": True}).json()) == 1
    assert api("alfa").get("/api/escenarios").json() == []
    prof.post(f"{base}/desarchivar")
    assert len(prof.get("/api/escenarios").json()) == 1
    assert api("alfa").post(f"{base}/archivar").status_code == 403


def test_duplicar_copia_el_despliegue_inicial(api):
    prof, base, a, r1, r2 = _preparar(api)
    api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.2, 0]]})
    prof.post(f"{base}/avanzar_turno")
    copia = prof.post(f"{base}/duplicar").json()
    assert copia["nombre"].endswith("(copia)") and copia["turno_actual"] == 1
    unidades = {u["nombre"]: u for u in prof.get(f"/api/escenarios/{copia['id']}/unidades").json()}
    assert set(unidades) == {"A", "R1", "R2"}
    assert unidades["A"]["lat"] == pytest.approx(0.0)  # posicion inicial, no la final
    assert unidades["A"]["fuerza"] == 100 and unidades["A"]["combustible"] == 100
    assert api("bravo").get(f"/api/escenarios/{copia['id']}").status_code == 200  # heredo las asignaciones


def test_exportar_solo_instructor(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.get(f"{base}/exportar")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    cuerpo = r.json()
    assert cuerpo["version"] == 1 and len(cuerpo["unidades"]) == 3 and "informe" in cuerpo
    assert api("alfa").get(f"{base}/exportar").status_code == 403


# ---------- informe posterior ----------
def _jugar_dos_turnos(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    prof.post(f"{base}/avanzar_turno")
    azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]})
    prof.post(f"{base}/avanzar_turno")
    return prof, base, a, r1, r2


def test_el_informe_reconstruye_el_ejercicio(api):
    prof, base, a, r1, r2 = _jugar_dos_turnos(api)
    inf = prof.get(f"{base}/aar").json()
    assert [t["turno"] for t in inf["turnos"]] == [0, 1, 2]
    t0, t1, t2 = inf["turnos"]
    fuerza = lambda t, nombre: next(u for u in t["unidades"] if u["nombre"] == nombre)["fuerza"]
    assert fuerza(t0, "A") == 100 and fuerza(t1, "A") < 100  # el combate del turno 1
    assert len(t1["combates"]) == 1 and t1["combates"][0]["atacante"] == "A"
    assert t2["combates"] == [] and t2["ordenes"][0]["tipo"] == "mover"
    assert t1["ordenes"][0]["resultado"]
    r = inf["resumen"]
    assert r["azul"]["combates_iniciados"] == 1 and r["rojo"]["combates_recibidos"] == 1
    assert r["azul"]["ordenes_emitidas"] == 2 and r["rojo"]["fuerza_perdida"] > 0
    # la posicion del turno 2 refleja el movimiento
    assert next(u for u in t2["unidades"] if u["nombre"] == "A")["lat"] > 0


def test_el_informe_solo_llega_a_los_alumnos_al_finalizar(api):
    prof, base, a, r1, r2 = _jugar_dos_turnos(api)
    for nombre in ("alfa", "bravo"):
        assert api(nombre).get(f"{base}/aar").status_code == 403
        assert api(nombre).get(f"{base}/aar.html").status_code == 403
    assert api("obs").get(f"{base}/aar").status_code == 200
    prof.post(f"{base}/finalizar")
    for nombre in ("alfa", "bravo"):
        r = api(nombre).get(f"{base}/aar.html")
        assert r.status_code == 200 and "Informe posterior" in r.text


def test_informe_html_escapa_el_contenido(api):
    prof, base, *_ = _preparar(api)
    nombre = "<img src=x onerror=alert(1)>"
    prof.post(f"{base}/unidades", json=dict(nombre=nombre, bando="rojo", clase="infanteria", lat=5, lon=5))
    prof.post(f"{base}/avanzar_turno")
    html = prof.get(f"{base}/aar.html").text
    assert "<img src=x" not in html and "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "<script" not in html


def test_informe_csv_neutraliza_formulas(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.patch(f"{base}/unidades/{a['id']}", json={"nombre": "=HYPERLINK(1)"})
    api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    prof.post(f"{base}/avanzar_turno")
    r = prof.get(f"{base}/aar.csv")
    assert r.headers["content-type"].startswith("text/csv") and "'=HYPERLINK(1)" in r.text
    assert r.text.splitlines()[0].startswith("turno,atacante")


def test_instantanea_inicial_y_finalizar(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/finalizar")  # sin turnos: solo el despliegue inicial
    inf = prof.get(f"{base}/aar").json()
    assert [t["turno"] for t in inf["turnos"]] == [0] and len(inf["turnos"][0]["unidades"]) == 3


# ---------- seguridad ----------
def test_cabeceras_de_seguridad(api):
    r = api().get("/")
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "strict-transport-security" not in r.headers
    assert api("prof").get("/api/escenarios").headers["cache-control"] == "no-store"


def test_https_activa_hsts_y_cookie_secure(api):
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app, base_url="https://testserver")
    r = c.post("/api/auth/login", json={"username": "prof", "password": "clave-segura-1"})
    assert r.status_code == 200
    assert "secure" in r.headers["set-cookie"].lower()
    assert "strict-transport-security" in r.headers
    r2 = api().post("/api/auth/login", json={"username": "prof", "password": "clave-segura-1"})
    assert "secure" not in r2.headers["set-cookie"].lower()


def test_el_bloqueo_de_login_persiste_en_la_base_y_expira(api):
    c = api()
    for _ in range(auth.MAX_FALLOS):
        c.post("/api/auth/login", json={"username": "alfa", "password": "mala"})
    Session = sessionmaker(bind=api.engine)
    with Session() as db:
        intento = db.get(IntentoLogin, "alfa")
        assert intento.fallos == auth.MAX_FALLOS and intento.bloqueado_hasta > ahora()
    assert c.post("/api/auth/login", json={"username": "alfa", "password": "clave-segura-1"}).status_code == 429
    with Session() as db:
        db.get(IntentoLogin, "alfa").bloqueado_hasta = ahora() - timedelta(seconds=1)
        db.commit()
    assert c.post("/api/auth/login", json={"username": "alfa", "password": "clave-segura-1"}).status_code == 200
    with Session() as db:
        assert db.get(IntentoLogin, "alfa") is None


def test_catalogo_requiere_sesion_y_lista_las_clases(api):
    assert api().get("/api/catalogo").status_code == 401
    cat = api("alfa").get("/api/catalogo").json()
    ids = {c["id"] for c in cat["clases"]}
    assert {"infanteria", "caza", "fragata", "deposito", "base_aerea", "puerto"} <= ids
    assert "brigada" in cat["escalones"] and "tormenta" in cat["climas"]
