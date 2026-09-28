"""API de la fase 2: obras, graficos tacticos, chat con interferencia, timeline y bloqueo de turnos."""

import asyncio
import random
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app import comunicaciones
from app.engine import clock
from app.models.escenario import Escenario
from app.models.usuario import ahora
from app.routers import ordenes as router_ordenes
from app.engine import orders as motor_ordenes
from tests.conftest import TerrenoFalso
from tests.test_api import _preparar
from tests.test_orders import _avanzar as _avanzar_db, _escenario as _escenario_db, _unidad as _unidad_db

RIO = TerrenoFalso(lambda lat, lon: "rio" if 0.10 <= lat <= 0.11 else "llano")


def _base(base):
    return int(base.rsplit("/", 1)[1])


def _ingenieros(prof, base, lat=0.098, **kw):
    r = prof.post(f"{base}/unidades", json=dict(nombre="Ing", bando="azul", clase="ingenieros", lat=lat, lon=0, **kw))
    assert r.status_code == 200, r.text
    return r.json()


# ---------- clases nuevas en la API ----------
def test_el_catalogo_expone_las_clases_y_atributos_nuevos(api):
    cat = api("alfa").get("/api/catalogo").json()
    por_id = {c["id"]: c for c in cat["clases"]}
    assert {"ingenieros", "transporte", "helicoptero_artillado", "antiaerea_portatil"} <= set(por_id)
    assert por_id["antiaerea_portatil"]["despliegue_turnos"] == 1 and por_id["antiaerea_portatil"]["recarga_turnos"] == 1
    assert por_id["helicoptero_artillado"]["cadencia_fuego"] == 1.6
    assert por_id["transporte"]["nodo_movil_km"] == 3.0 and por_id["ingenieros"]["construye"] is True


def test_crear_convoy_lo_carga_y_los_enemigos_no_ven_sus_contadores(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.post(f"{base}/unidades", json=dict(nombre="Conv", bando="rojo", clase="transporte", lat=0.04, lon=0))
    assert r.json()["carga"] == 100 and r.json()["velocidad_kmh"] == 40
    visto = {u["nombre"]: u for u in api("alfa").get(base).json()["unidades"]}
    assert visto["Conv"]["carga"] is None and visto["Conv"]["recarga_restante"] is None
    assert visto["A"]["carga"] == 0


# ---------- construccion de obras por la API ----------
@pytest.fixture()
def con_rio(monkeypatch):
    monkeypatch.setattr(router_ordenes, "get_terreno", lambda: RIO)
    monkeypatch.setattr(motor_ordenes, "get_terreno", lambda: RIO)


def _construir(cliente, base, ing, tipo="puente", sitio=(0.105, 0.0)):
    return cliente.post(f"{base}/ordenes", json={
        "unidad_id": ing["id"], "tipo": "construir", "detalle": tipo, "waypoints": [list(sitio)]})


def test_construir_por_la_api_valida_clase_punto_y_material(api, con_rio):
    prof, base, a, r1, r2 = _preparar(api)
    ing = _ingenieros(prof, base)
    azul = api("alfa")
    assert _construir(azul, base, ing).status_code == 200
    assert _construir(azul, base, {"id": a["id"]}).json()["detail"].startswith("Solo los ingenieros")  # infanteria
    assert "no esta sobre un rio" in _construir(azul, base, ing, sitio=(0.13, 0.0)).json()["detail"]
    assert "fuera del alcance" in _construir(azul, base, ing, sitio=(0.105, 0.5)).json()["detail"]
    r = azul.post(f"{base}/ordenes", json={"unidad_id": ing["id"], "tipo": "construir", "waypoints": [[0.105, 0]]})
    assert r.status_code == 400 and "puente o un vado" in r.json()["detail"]
    r = azul.post(f"{base}/ordenes", json={"unidad_id": ing["id"], "tipo": "construir", "detalle": "balsa", "waypoints": [[0.105, 0]]})
    assert r.status_code == 422
    prof.patch(f"{base}/unidades/{ing['id']}", json={"municion": 10})
    assert "Material insuficiente" in _construir(azul, base, ing).json()["detail"]


def test_la_obra_se_construye_y_es_visible_para_su_bando_y_el_instructor(api, con_rio):
    prof, base, a, r1, r2 = _preparar(api)
    ing = _ingenieros(prof, base)
    assert _construir(api("alfa"), base, ing, tipo="vado").status_code == 200
    assert prof.post(f"{base}/avanzar_turno").status_code == 200
    (obra,) = api("alfa").get(base).json()["obras"]
    assert (obra["tipo"], obra["bando"], obra["expira_turno"]) == ("vado", "azul", 5)
    assert len(prof.get(base).json()["obras"]) == 1
    assert len(api("obs").get(base).json()["obras"]) == 1
    # el rojo no la ve mientras ninguna de sus unidades la detecte (R1 y R2 estan a mas de 10 km)
    prof.patch(f"{base}/unidades/{r1['id']}", json={"lat": 1.0})
    assert api("bravo").get(base).json()["obras"] == []
    # ... y si una unidad roja pasa cerca, si
    prof.patch(f"{base}/unidades/{r1['id']}", json={"lat": 0.11, "lon": 0.0})
    assert len(api("bravo").get(base).json()["obras"]) == 1


def test_las_ordenes_de_construccion_incluyen_su_detalle(api, con_rio):
    prof, base, a, r1, r2 = _preparar(api)
    ing = _ingenieros(prof, base)
    _construir(api("alfa"), base, ing, tipo="puente")
    (o,) = api("alfa").get(base).json()["ordenes"]
    assert (o["tipo"], o["detalle"], o["waypoints"]) == ("construir", "puente", [[0.105, 0.0]])


def test_no_se_ordena_atacar_a_un_tipo_de_objetivo_imposible(api):
    prof, base, a, r1, r2 = _preparar(api)
    aa = prof.post(f"{base}/unidades", json=dict(nombre="AAp", bando="azul", clase="antiaerea_portatil", lat=0.001, lon=0)).json()
    r = api("alfa").post(f"{base}/ordenes", json={"unidad_id": aa["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    assert r.status_code == 400 and "no puede atacar objetivos de tipo terrestre" in r.json()["detail"]
    conv = prof.post(f"{base}/unidades", json=dict(nombre="Conv", bando="azul", clase="transporte", lat=0.001, lon=0)).json()
    r = api("alfa").post(f"{base}/ordenes", json={"unidad_id": conv["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    assert r.status_code == 400


def test_ajustar_combustible_o_municion_queda_en_el_registro_logistico(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.patch(f"{base}/unidades/{a['id']}", json={"municion": 10})
    tl = prof.get(f"{base}/aar/timeline").json()
    assert tl["escenario"]["id"] == _base(base)
    ajuste = next(e for e in tl["eventos"] if e["tipo"] == "logistico")
    assert (ajuste["subtipo"], ajuste["causas"], ajuste["antes"], ajuste["despues"]) == ("ajuste_manual", ["ajuste"], 100.0, 10.0)
    assert tl["resumen"]["ajustes_manuales"] == 1 and tl["resumen"]["caidas_abruptas"] == 0


# ---------- graficos tacticos ----------
LINEA = {"type": "LineString", "coordinates": [[-66.9, 10.6], [-66.8, 10.61], [-66.7, 10.6]]}
ZONA = {"type": "Polygon", "coordinates": [[[-66.9, 10.5], [-66.8, 10.5], [-66.8, 10.6], [-66.9, 10.5]]]}
PUNTO = {"type": "Point", "coordinates": [-66.85, 10.55]}


def test_graficos_se_validan_segun_su_tipo(api):
    prof, base, *_ = _preparar(api)
    azul = api("alfa")
    ok = azul.post(f"{base}/graficos", json={"tipo": "linea_fase", "etiqueta": "LF ALFA", "geometria": LINEA})
    assert ok.status_code == 200 and ok.json()["bando"] == "azul" and ok.json()["autor"] == "alfa"
    assert azul.post(f"{base}/graficos", json={"tipo": "zona_reunion", "geometria": ZONA}).status_code == 200
    assert azul.post(f"{base}/graficos", json={"tipo": "punto_control", "geometria": PUNTO}).status_code == 200
    assert azul.post(f"{base}/graficos", json={"tipo": "eje_avance", "geometria": LINEA}).status_code == 200
    malos = [
        {"tipo": "linea_fase", "geometria": PUNTO},  # tipo de geometria equivocado
        {"tipo": "zona_reunion", "geometria": LINEA},
        {"tipo": "punto_control", "geometria": LINEA},
        {"tipo": "linea_fase", "geometria": {"type": "LineString", "coordinates": [[0, 0]]}},
        {"tipo": "linea_fase", "geometria": {"type": "LineString", "coordinates": [[0, 0], [200, 0]]}},
        {"tipo": "linea_fase", "geometria": {"type": "LineString", "coordinates": [[0, 0], ["x", 1]]}},
        {"tipo": "zona_reunion", "geometria": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0.5, 0.5]]]}},
        {"tipo": "linea_fase", "geometria": {"type": "LineString", "coordinates": [[0, 0]] * 300}},
        {"tipo": "cohete", "geometria": LINEA},
        {"tipo": "linea_fase", "etiqueta": "x" * 61, "geometria": LINEA},
    ]
    for cuerpo in malos:
        assert azul.post(f"{base}/graficos", json=cuerpo).status_code == 422, cuerpo


def test_los_graficos_son_del_bando_y_el_instructor_ve_todos(api):
    prof, base, *_ = _preparar(api)
    g = api("alfa").post(f"{base}/graficos", json={"tipo": "linea_fase", "etiqueta": "LF", "geometria": LINEA}).json()
    api("bravo").post(f"{base}/graficos", json={"tipo": "punto_control", "etiqueta": "PC", "geometria": PUNTO})
    neutral = prof.post(f"{base}/graficos", json={"tipo": "zona_reunion", "etiqueta": "ZR", "geometria": ZONA}).json()
    assert neutral["bando"] == "todos"
    etiquetas = lambda c: {x["etiqueta"] for x in c.get(f"{base}/graficos").json()}
    assert etiquetas(api("alfa")) == {"LF", "ZR"}
    assert etiquetas(api("bravo")) == {"PC", "ZR"}
    assert etiquetas(prof) == {"LF", "PC", "ZR"} and etiquetas(api("obs")) == {"LF", "PC", "ZR"}
    # tambien llegan en el estado (sincronizacion inicial)
    assert {x["etiqueta"] for x in api("alfa").get(base).json()["graficos"]} == {"LF", "ZR"}
    # el instructor viendo como el bando azul ve solo lo de azul
    assert {x["etiqueta"] for x in prof.get(base, params={"vista": "azul"}).json()["graficos"]} == {"LF", "ZR"}
    # borrar: el otro bando no puede (ni sabe que existe)
    assert api("bravo").delete(f"{base}/graficos/{g['id']}").status_code == 404
    assert api("alfa").delete(f"{base}/graficos/{g['id']}").status_code == 200
    assert etiquetas(prof) == {"PC", "ZR"}
    assert api("alfa").delete(f"{base}/graficos/{neutral['id']}").status_code == 404  # neutral: solo el instructor
    assert prof.delete(f"{base}/graficos/{neutral['id']}").status_code == 200


def test_el_instructor_dirige_un_grafico_a_un_bando_y_el_observador_no_dibuja(api):
    prof, base, *_ = _preparar(api)
    prof.post(f"{base}/graficos", json={"tipo": "punto_control", "etiqueta": "SOLO ROJO", "bando": "rojo", "geometria": PUNTO})
    assert api("alfa").get(f"{base}/graficos").json() == []
    assert len(api("bravo").get(f"{base}/graficos").json()) == 1
    assert api("obs").post(f"{base}/graficos", json={"tipo": "punto_control", "geometria": PUNTO}).status_code == 403
    assert api().post(f"{base}/graficos", json={"tipo": "punto_control", "geometria": PUNTO}).status_code == 401
    # un alumno no puede elegir el bando de destino
    g = api("alfa").post(f"{base}/graficos", json={"tipo": "punto_control", "bando": "rojo", "geometria": PUNTO}).json()
    assert g["bando"] == "azul"


def test_los_graficos_no_se_pueden_crear_en_un_escenario_finalizado_ni_sin_acceso(api):
    prof, base, *_ = _preparar(api)
    prof.post(f"{base}/finalizar")
    assert api("alfa").post(f"{base}/graficos", json={"tipo": "punto_control", "geometria": PUNTO}).status_code == 400
    ids = {u["username"]: u["id"] for u in prof.get("/api/usuarios").json()}
    prof.put(f"{base}/usuarios", json={"usuario_ids": [ids["alfa"]]})
    assert api("bravo").get(f"{base}/graficos").status_code == 404


def test_los_graficos_se_sincronizan_por_websocket_solo_con_el_bando(api):
    prof, base, *_ = _preparar(api)
    esc = _base(base)
    with api("alfa").websocket_connect(f"/ws/{esc}") as ws_azul, api("bravo").websocket_connect(f"/ws/{esc}") as ws_rojo, \
            prof.websocket_connect(f"/ws/{esc}") as ws_instr:
        for ws in (ws_azul, ws_rojo, ws_instr):
            ws.receive_json()  # estado
            ws.receive_json()  # historial del chat
        g = api("alfa").post(f"{base}/graficos", json={"tipo": "linea_fase", "etiqueta": "LF", "geometria": LINEA}).json()
        for ws in (ws_azul, ws_instr):
            m = ws.receive_json()
            assert m["tipo"] == "grafico" and m["accion"] == "crear" and m["grafico"]["etiqueta"] == "LF"
        api("alfa").delete(f"{base}/graficos/{g['id']}")
        for ws in (ws_azul, ws_instr):
            assert ws.receive_json() == {"tipo": "grafico", "accion": "borrar", "id": g["id"]}
        # el rojo no recibio nada del bando azul: su siguiente mensaje es el que provoca el instructor
        prof.post(f"{base}/graficos", json={"tipo": "punto_control", "etiqueta": "NEUTRAL", "geometria": PUNTO})
        assert ws_rojo.receive_json()["grafico"]["etiqueta"] == "NEUTRAL"


# ---------- comunicaciones simuladas ----------
def test_el_interceptor_decide_perdida_y_demora():
    e = comunicaciones.Enlace(latencia_ms=500, jitter_ms=200, perdida_pct=0)
    it = comunicaciones.Interceptor(random.Random(1))
    demoras = [it.decidir(e).demora_ms for _ in range(200)]
    assert min(demoras) >= 500 and max(demoras) <= 700 and len(set(demoras)) > 20
    assert not any(it.decidir(e).perdido for _ in range(200))
    total = comunicaciones.Interceptor(random.Random(2))
    assert all(total.decidir(comunicaciones.Enlace(perdida_pct=100)).perdido for _ in range(50))
    mitad = comunicaciones.Interceptor(random.Random(3))
    perdidos = sum(mitad.decidir(comunicaciones.Enlace(perdida_pct=30)).perdido for _ in range(2000))
    assert 500 < perdidos < 700  # ~30 %
    assert comunicaciones.Interceptor().decidir(comunicaciones.Enlace()) == comunicaciones.Entrega(False, 0)


def test_canales_por_rol():
    assert comunicaciones.canal_de("azul", "bando") == "azul" and comunicaciones.canal_de("rojo", "bando") == "rojo"
    assert comunicaciones.canal_de("azul", "mando") == "mando"
    assert comunicaciones.canal_de("azul", "todos") is None and comunicaciones.canal_de("azul", "rojo") is None
    assert comunicaciones.canal_de("instructor", "todos") == "todos" and comunicaciones.canal_de("instructor", "bando") is None
    assert comunicaciones.canal_de("observador", "bando") is None
    assert comunicaciones.lados_afectados("todos", "instructor") == ("azul", "rojo")
    assert comunicaciones.lados_afectados("mando", "rojo") == ("rojo",)


class _WS:
    def __init__(self):
        self.enviados = []

    async def send_json(self, m):
        self.enviados.append(m)


def _mundo(db_session, **enlace):
    """Escenario con una conexion instructor, dos azules (alfa, alfa2) y un rojo, sin red real."""
    from app.models.usuario import Usuario

    esc = Escenario(nombre="chat", **enlace)
    db_session.add(esc)
    db_session.flush()
    usuarios = {}
    for nombre, rol in (("prof", "instructor"), ("alfa", "azul"), ("alfa2", "azul"), ("bravo", "rojo"), ("obs", "observador")):
        u = Usuario(username=nombre, password_hash="x", rol=rol)
        db_session.add(u)
        db_session.flush()
        usuarios[nombre] = u
    db_session.commit()
    conexiones = {n: SimpleNamespace(websocket=_WS(), usuario_id=u.id, rol=u.rol, rol_efectivo=u.rol) for n, u in usuarios.items()}
    manager = SimpleNamespace(conexiones=lambda _id: list(conexiones.values()))
    return esc, usuarios, conexiones, manager


def _enviar(manager, db, esc, usuario, canal, texto="hola", **kw):
    async def correr():
        error = await comunicaciones.procesar(manager, db, esc, usuario, {"canal": canal, "texto": texto, **kw})
        if comunicaciones._tareas:
            await asyncio.gather(*list(comunicaciones._tareas))
        return error
    return asyncio.run(correr())


@pytest.fixture(autouse=True)
def _chat_limpio(monkeypatch):
    comunicaciones._recientes.clear()
    esperas = []

    async def dormir(seg):
        esperas.append(seg)

    monkeypatch.setattr(comunicaciones, "dormir", dormir)
    monkeypatch.setattr(comunicaciones, "interceptor", comunicaciones.Interceptor(random.Random(7)))
    return esperas


def _textos(c):
    return [m["mensaje"]["texto"] for m in c.websocket.enviados if m["tipo"] == "chat"]


def test_un_mensaje_de_bando_llega_al_bando_y_al_instructor_pero_no_al_enemigo(db_session):
    esc, us, cx, mgr = _mundo(db_session)
    assert _enviar(mgr, db_session, esc, us["alfa"], "bando", "avanzamos") is None
    assert _textos(cx["alfa"]) == ["avanzamos"] and _textos(cx["alfa2"]) == ["avanzamos"]  # eco y companero
    assert _textos(cx["prof"]) == ["avanzamos"]
    assert _textos(cx["bravo"]) == [] and _textos(cx["obs"]) == []
    m = cx["prof"].websocket.enviados[0]["mensaje"]
    assert m["canal"] == "azul" and m["remitente"] == "alfa" and m["entrega"]["azul"] == {"perdido": False, "demora_ms": 0}
    assert "entrega" not in cx["alfa2"].websocket.enviados[0]["mensaje"]


def test_el_canal_mando_solo_lo_ven_el_remitente_y_el_instructor(db_session):
    esc, us, cx, mgr = _mundo(db_session)
    _enviar(mgr, db_session, esc, us["alfa"], "mando", "solicito apoyo")
    assert _textos(cx["alfa"]) == ["solicito apoyo"] and _textos(cx["prof"]) == ["solicito apoyo"]
    assert _textos(cx["alfa2"]) == [] and _textos(cx["bravo"]) == []


def test_perdida_total_el_companero_no_recibe_pero_el_instructor_lo_ve_marcado(db_session):
    esc, us, cx, mgr = _mundo(db_session, com_perdida_pct=100)
    _enviar(mgr, db_session, esc, us["alfa"], "bando", "sin señal")
    assert _textos(cx["alfa2"]) == []
    assert _textos(cx["alfa"]) == ["sin señal"]  # quien escribe se ve a si mismo
    assert cx["prof"].websocket.enviados[0]["mensaje"]["entrega"]["azul"]["perdido"] is True


def test_la_latencia_retrasa_solo_al_receptor(db_session, _chat_limpio):
    esc, us, cx, mgr = _mundo(db_session, com_latencia_ms=1500, com_jitter_ms=500)
    _enviar(mgr, db_session, esc, us["alfa"], "bando", "retrasado")
    assert _textos(cx["alfa2"]) == ["retrasado"]  # llego, pero tras esperar
    assert len(_chat_limpio) == 1 and 1.5 <= _chat_limpio[0] <= 2.0
    assert cx["prof"].websocket.enviados[0]["mensaje"]["entrega"]["azul"]["demora_ms"] == round(_chat_limpio[0] * 1000)


def test_la_difusion_del_instructor_degrada_cada_bando_por_separado(db_session):
    esc, us, cx, mgr = _mundo(db_session, com_perdida_pct=50)
    llegaron = {"alfa2": 0, "bravo": 0}
    for i in range(60):
        comunicaciones._recientes.clear()
        _enviar(mgr, db_session, esc, us["prof"], "todos", f"aviso {i}")
    for n in llegaron:
        llegaron[n] = len(_textos(cx[n]))
    assert 15 < llegaron["alfa2"] < 45 and 15 < llegaron["bravo"] < 45
    assert len(_textos(cx["prof"])) == 60  # el instructor recibe todo


def test_el_instructor_puede_hablar_a_un_solo_bando(db_session):
    esc, us, cx, mgr = _mundo(db_session)
    _enviar(mgr, db_session, esc, us["prof"], "rojo", "ordene repliegue")
    assert _textos(cx["bravo"]) == ["ordene repliegue"] and _textos(cx["alfa"]) == [] and _textos(cx["obs"]) == []


def test_validaciones_del_chat(db_session):
    esc, us, cx, mgr = _mundo(db_session)
    assert "vacio" in _enviar(mgr, db_session, esc, us["alfa"], "bando", "   ")
    assert "supera" in _enviar(mgr, db_session, esc, us["alfa"], "bando", "x" * 501)
    assert "acceso" in _enviar(mgr, db_session, esc, us["obs"], "bando", "hola")
    assert "acceso" in _enviar(mgr, db_session, esc, us["alfa"], "todos", "hola")
    assert "acceso" in _enviar(mgr, db_session, esc, us["prof"], "bando", "hola")
    esc.estado = "finalizado"
    assert "finalizo" in _enviar(mgr, db_session, esc, us["alfa"], "bando", "hola")
    assert all(_textos(c) == [] for c in cx.values())


def test_limite_de_mensajes_por_ventana(db_session):
    esc, us, cx, mgr = _mundo(db_session)
    errores = [_enviar(mgr, db_session, esc, us["alfa"], "bando", f"m{i}") for i in range(comunicaciones.LIMITE_MENSAJES + 2)]
    assert errores[: comunicaciones.LIMITE_MENSAJES] == [None] * comunicaciones.LIMITE_MENSAJES
    assert all("Demasiados" in e for e in errores[comunicaciones.LIMITE_MENSAJES:])
    assert _enviar(mgr, db_session, esc, us["bravo"], "bando", "otro usuario") is None  # el limite es por usuario


def test_historial_coherente_con_lo_que_cada_uno_recibio(db_session):
    esc, us, cx, mgr = _mundo(db_session)
    _enviar(mgr, db_session, esc, us["alfa"], "bando", "llego")
    esc.com_perdida_pct = 100
    _enviar(mgr, db_session, esc, us["alfa"], "bando", "se perdio")
    esc.com_perdida_pct = 0
    esc.com_latencia_ms = 3_600_000  # tardara una hora en llegar: aun no forma parte del historial
    _enviar(mgr, db_session, esc, us["alfa"], "bando", "en transito")
    _enviar(mgr, db_session, esc, us["bravo"], "bando", "del rojo")
    _enviar(mgr, db_session, esc, us["alfa"], "mando", "reservado")
    h = lambda u: [m["mensaje"]["texto"] for m in comunicaciones.historial_para(db_session, esc, us[u])]
    assert h("alfa2") == ["llego"]
    assert h("alfa") == ["llego", "se perdio", "en transito", "reservado"]  # el remitente ve todo lo suyo
    assert h("bravo") == ["del rojo"]
    assert h("prof") == ["llego", "se perdio", "en transito", "del rojo", "reservado"]
    assert h("obs") == []
    marcados = {m["mensaje"]["texto"]: m["mensaje"]["entrega"] for m in comunicaciones.historial_para(db_session, esc, us["prof"])}
    assert marcados["se perdio"]["azul"]["perdido"] is True and marcados["en transito"]["azul"]["demora_ms"] == 3_600_000


def test_el_chat_por_websocket_de_punta_a_punta(api):
    prof, base, *_ = _preparar(api)
    esc = _base(base)
    prof.patch(f"{base}/config", json={"com_latencia_ms": 0, "com_perdida_pct": 0})
    with api("alfa").websocket_connect(f"/ws/{esc}") as ws_azul, prof.websocket_connect(f"/ws/{esc}") as ws_instr:
        for ws in (ws_azul, ws_instr):
            ws.receive_json()
            assert ws.receive_json() == {"tipo": "chat_historial", "mensajes": []}
        ws_azul.send_text('{"tipo": "chat", "canal": "mando", "texto": "Azul solicita apoyo aereo"}')
        assert ws_azul.receive_json()["mensaje"]["texto"] == "Azul solicita apoyo aereo"
        recibido = ws_instr.receive_json()["mensaje"]
        assert recibido["remitente"] == "alfa" and recibido["canal"] == "mando" and "entrega" in recibido
        ws_azul.send_text('{"tipo": "chat", "canal": "todos", "texto": "no permitido"}')
        assert ws_azul.receive_json() == {"tipo": "chat_error", "detalle": "No tiene acceso a ese canal de comunicaciones."}
        ws_azul.send_text("no es json")  # se ignora sin cerrar la conexion
        ws_azul.send_text("ping")
    with api("alfa").websocket_connect(f"/ws/{esc}") as ws:  # al reconectar recupera su historial
        ws.receive_json()
        assert [m["mensaje"]["texto"] for m in ws.receive_json()["mensajes"]] == ["Azul solicita apoyo aereo"]


# ---------- configuracion de las comunicaciones ----------
def test_configurar_comunicaciones_valida_rangos_y_solo_el_instructor_las_ve(api):
    prof, base, *_ = _preparar(api)
    e = prof.patch(f"{base}/config", json={"com_latencia_ms": 800, "com_jitter_ms": 300, "com_perdida_pct": 25}).json()["escenario"]
    assert (e["com_latencia_ms"], e["com_jitter_ms"], e["com_perdida_pct"]) == (800, 300, 25)
    for malo in ({"com_perdida_pct": 101}, {"com_perdida_pct": -1}, {"com_latencia_ms": -5}, {"com_latencia_ms": 60001}):
        assert prof.patch(f"{base}/config", json=malo).status_code == 422
    assert "com_perdida_pct" not in api("alfa").get(base).json()["escenario"]
    assert "com_latencia_ms" not in prof.get(base, params={"vista": "azul"}).json()["escenario"]
    assert prof.get(base).json()["escenario"]["com_perdida_pct"] == 25
    ajustes = [e["texto"] for e in prof.get(f"{base}/aar/timeline").json()["eventos"] if e["subtipo"] == "ajuste"]
    assert any("perdida de mensajes 25" in t and "latencia de radio 800" in t for t in ajustes)
    copia = prof.post(f"{base}/duplicar").json()
    assert prof.get(f"/api/escenarios/{copia['id']}").json()["escenario"]["com_perdida_pct"] == 25


# ---------- timeline del AAR ----------
def test_timeline_cruza_logistica_con_combates(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    prof.patch(f"{base}/unidades/{a['id']}", json={"municion": 40})  # queda al 40 %
    azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    prof.post(f"{base}/avanzar_turno")  # T1: ataca (-25 %) -> 15 %: cae por debajo del nivel critico
    azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    prof.post(f"{base}/avanzar_turno")  # T2: llega a combatir con 15 % y gasta lo que le queda
    tl = prof.get(f"{base}/aar/timeline").json()

    assert tl["ejes"]["turnos"] == [0, 1, 2] and tl["ejes"]["umbrales"] == {"caida_abrupta": 30.0, "nivel_critico": 25.0}
    serie = next(s for s in tl["series"] if s["nombre"] == "A")
    assert serie["turnos"] == [0, 1, 2] and serie["municion"] == [40.0, 15.0, 0.0]
    assert len(serie["fuerza"]) == len(serie["combustible"]) == len(serie["estado"]) == 3

    combates = [e for e in tl["eventos"] if e["tipo"] == "combate"]
    assert [c["turno"] for c in combates] == [1, 2] and combates[0]["atacante"] == "A"
    logisticos = [e for e in tl["eventos"] if e["tipo"] == "logistico" and e["unidad"] == "A"]
    critico = next(e for e in logisticos if e["subtipo"] == "nivel_critico")
    assert (critico["turno"], critico["antes"], critico["despues"]) == (1, 40.0, 15.0)
    assert critico["causas"] == ["combate"] and critico["variable"] == "municion"
    ids = {e["id"] for e in tl["eventos"]}
    assert all(c["logistico"] in ids | {None} and c["combate"] in ids for c in tl["correlaciones"])

    tipos = {c["tipo"] for c in tl["correlaciones"]}
    assert "combate_con_logistica_baja" in tipos  # T2: llego a combatir con la municion al 15 %
    baja = next(c for c in tl["correlaciones"] if c["tipo"] == "combate_con_logistica_baja")
    assert baja["turno"] == 2 and "municion 15%" in baja["detalle"] and baja["unidad_id"] == a["id"]
    consumo = next(c for c in tl["correlaciones"] if c["tipo"] == "consumo_en_combate")
    assert consumo["combate"] in ids and consumo["logistico"] == critico["id"]
    assert tl["resumen"]["combates"] == 2 and tl["resumen"]["por_bando"]["azul"]["combates_iniciados"] == 2
    # los eventos van en orden cronologico
    assert [e["turno"] for e in tl["eventos"]] == sorted(e["turno"] for e in tl["eventos"])


def test_caida_abrupta_de_combustible_por_movimiento_coincide_con_el_combate(api):
    prof, base, a, r1, r2 = _preparar(api)
    caza = prof.post(f"{base}/unidades", json=dict(
        nombre="Caza", bando="azul", clase="caza", lat=0.0, lon=0.0, velocidad_kmh=900, autonomia_km=1000)).json()
    azul = api("alfa")
    azul.post(f"{base}/ordenes", json={"unidad_id": caza["id"], "tipo": "mover", "waypoints": [[4.0, 0.0]]})
    prof.post(f"{base}/avanzar_turno")  # ~445 km: -44 % de combustible
    tl = prof.get(f"{base}/aar/timeline").json()
    caida = next(e for e in tl["eventos"] if e["tipo"] == "logistico" and e["unidad"] == "Caza")
    assert caida["subtipo"] == "caida_abrupta" and caida["causas"] == ["movimiento"] and caida["delta"] < -30


def test_timeline_respeta_los_permisos_del_informe(api):
    prof, base, *_ = _preparar(api)
    assert api("alfa").get(f"{base}/aar/timeline").status_code == 403  # antes de finalizar
    assert api("obs").get(f"{base}/aar/timeline").status_code == 200
    prof.post(f"{base}/finalizar")
    assert api("alfa").get(f"{base}/aar/timeline").status_code == 200
    assert api().get(f"{base}/aar/timeline").status_code == 401
    exportado = prof.get(f"{base}/exportar").json()
    assert "timeline" in exportado and exportado["timeline"]["ejes"]["turnos"] == [0]


def test_timeline_de_un_escenario_sin_turnos_esta_vacio(api):
    prof, base, *_ = _preparar(api)
    tl = prof.get(f"{base}/aar/timeline").json()
    assert tl["series"] == [] and tl["eventos"] == [] and tl["correlaciones"] == [] and tl["ejes"]["turnos"] == []


# ---------- bloqueo contra doble resolucion ----------
def test_avanzar_con_turno_esperado_no_resuelve_dos_veces(db_session):
    esc = _escenario_db(db_session)
    _unidad_db(db_session, esc)
    clock.avanzar_turno(db_session, esc, turno_esperado=1)
    assert esc.turno_actual == 2
    clock.avanzar_turno(db_session, esc, turno_esperado=1)  # otro proceso ya lo habia resuelto
    assert esc.turno_actual == 2
    clock.avanzar_turno(db_session, esc, turno_esperado=2)
    assert esc.turno_actual == 3


def test_avanzar_con_turno_esperado_respeta_pausa_y_fase(db_session):
    esc = _escenario_db(db_session)
    esc.estado = "pausado"
    db_session.commit()
    clock.avanzar_turno(db_session, esc, turno_esperado=1)
    assert esc.turno_actual == 1
    esc.estado, esc.fase = "activo", "resolucion"
    db_session.commit()
    clock.avanzar_turno(db_session, esc, turno_esperado=1)
    assert esc.turno_actual == 1


def test_dos_avances_simultaneos_de_la_api_solo_resuelven_un_turno(api):
    prof, base, *_ = _preparar(api)
    assert prof.post(f"{base}/avanzar_turno").status_code == 200
    assert prof.get(base).json()["escenario"]["turno_actual"] == 2
