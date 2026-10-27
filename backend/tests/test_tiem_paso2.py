"""TIEM, etapa 3: apreciaciones de Estado Mayor (Paso 2), la confrontacion de las F/A con las capacidades del enemigo
y el juego de guerra (ensayo de una F/A en una copia del escenario contra la IA)."""

from app.engine import tiem
from app.models.escenario import Escenario
from app.models.unidad import Unidad
from tests.test_api import _preparar

FA = {"nombre": "F/A 1", "que": "Neutralizar la defensa aérea", "donde": "R1", "cuando": "D", "quien": "Caza",
      "naturaleza": "si", "integridad": "si", "oportunidad": "si", "practicabilidad": "practicable"}


def test_las_seis_apreciaciones_y_quien_las_redacta():
    redactan = {t: tiem.DOCUMENTOS[t].redactan[0] for t in tiem.ORDEN if t.startswith("apreciacion_")}
    assert redactan == {"apreciacion_inteligencia": "a2", "apreciacion_operaciones": "a3", "apreciacion_defensa_aerea": "a3da",
                        "apreciacion_personal": "a1", "apreciacion_logistica": "a4", "apreciacion_ce": "ce"}
    assert all(tiem.DOCUMENTOS[t].paso == "Fase I · Paso 2" for t in redactan)


def test_la_matriz_de_confrontacion():
    c = tiem.normalizar("apreciacion_operaciones", {"confrontacion": [
        {"fa": "F/A 1", "capacidad": "C1", "efecto": "degrada", "analisis": "x"},
        {"fa": "F/A 1", "capacidad": "C1", "efecto": "anula"},  # repetida: se descarta
        {"fa": "F/A 2", "capacidad": "C1", "efecto": "rara"},  # efecto invalido y sin analisis: se descarta
        {"fa": "", "capacidad": "C1", "efecto": "anula"}]})
    assert c["confrontacion"] == [{"fa": "F/A 1", "capacidad": "C1", "efecto": "degrada", "analisis": "x"}]
    assert any("Confrontación" in f for f in tiem.revisar("apreciacion_operaciones", {})["faltan"])
    assert not any("Confrontación" in f for f in tiem.revisar("apreciacion_operaciones", c)["faltan"])
    docs = {"formas_accion": {"formas": [FA, dict(FA, nombre="", que="Destruir la pista")]},
            "guia": {"capacidades_enemigo": [{"que": "Atacar la base"}, {"que": ""}]}}
    assert tiem.contexto(docs) == {"formas": ["F/A 1: Neutralizar la defensa aérea", "F/A 2: Destruir la pista"],
                                   "capacidades": ["C1: Atacar la base"]}
    docs["apreciacion_inteligencia"] = {"capacidades_enemigo": [{"que": "Interceptar"}]}  # la A-2 la actualiza
    assert tiem.contexto(docs)["capacidades"] == ["C1: Interceptar"]


def _alumnos(api):
    prof = api("prof")
    for nombre, puesto in (("ua1", "a1"), ("ua3", "a3"), ("ua4", "a4"), ("uce", "ce"), ("uda", "a3da")):
        assert prof.post("/api/usuarios", json={"username": nombre, "password": "clave-segura-1", "rol": "azul",
                                                "puesto": puesto}).status_code == 200
    return _preparar(api)


def test_permisos_y_sugerencias_de_las_apreciaciones(api):
    prof, base, *_ = _alumnos(api)
    prof.post(f"{base}/pmo/generar", json={})
    ruta = f"{base}/tiem/azul"
    a1, a3, a4, uce, uda = (api(n) for n in ("ua1", "ua3", "ua4", "uce", "uda"))
    assert a1.put(f"{ruta}/apreciacion_personal", json={"contenido": {"conclusiones": "x"}}).status_code == 200
    assert a4.put(f"{ruta}/apreciacion_personal", json={"contenido": {}}).status_code == 403
    assert a4.put(f"{ruta}/apreciacion_logistica", json={"contenido": {"conclusiones": "x"}}).status_code == 200
    assert uce.put(f"{ruta}/apreciacion_ce", json={"contenido": {"conclusiones": "x"}}).status_code == 200
    assert a3.put(f"{ruta}/apreciacion_defensa_aerea", json={"contenido": {}}).status_code == 403
    # las F/A y las capacidades alimentan la confrontacion
    assert a3.put(f"{ruta}/formas_accion", json={"contenido": {"formas": [FA, dict(FA, nombre="F/A 2", que="Destruir la pista")]}}).status_code == 200
    assert api("alfa").put(f"{ruta}/guia", json={"contenido": {"capacidades_enemigo": [{"que": "Atacar la base"}, {"que": "Interceptar"}]}}).status_code == 200
    vista = a3.get(f"{base}/tiem").json()
    assert vista["contexto"]["azul"]["formas"] == ["F/A 1: Neutralizar la defensa aérea", "F/A 2: Destruir la pista"]
    s = a3.get(f"{ruta}/apreciacion_operaciones/sugerencias").json()["contenido"]
    assert len(s["confrontacion"]) == 4 and {c["efecto"] for c in s["confrontacion"]} == {""}  # esqueleto 2 x 2
    assert [c["fa"] for c in s["comparacion"]] == vista["contexto"]["azul"]["formas"] and s["prc"] and s["mision_especifica"]["tarea"]
    da = uda.get(f"{ruta}/apreciacion_defensa_aerea/sugerencias").json()["contenido"]
    assert "Amenaza aérea estimada" in da["factores"]
    per = a1.get(f"{ruta}/apreciacion_personal/sugerencias").json()["contenido"]
    assert "Efectivos del bando" in per["situacion_area"] and len(per["analisis_fa"]) == 2
    log = a4.get(f"{ruta}/apreciacion_logistica/sugerencias").json()["contenido"]
    assert log["situacion_area"]
    intel = api("alfa").get(f"{ruta}/apreciacion_inteligencia/sugerencias").json()["contenido"]
    assert [c["capacidad"] for c in intel["analisis_capacidades"]] == ["C1: Atacar la base", "C2: Interceptar"]


def test_juego_de_guerra_ensayo_de_una_fa(api, db_session):
    prof, base, a, r1, r2 = _alumnos(api)
    esc_id = int(base.rsplit("/", 1)[1])
    prof.patch(f"{base}/unidades/{a['id']}", json={"fuerza": 70})  # estado actual, no el inicial
    a3 = api("ua3")
    assert api("ua4").post(f"{base}/tiem/azul/ensayos", json={"fa": "F/A 1: algo"}).status_code == 403
    r = a3.post(f"{base}/tiem/azul/ensayos", json={"fa": "F/A 1: Neutralizar la defensa aérea"})
    assert r.status_code == 200, r.text
    ens = r.json()
    assert ens["nombre"].startswith("Ensayo 1 · F/A 1 · Azul") and ens["turnos_jugados"] == 0
    copia = f"/api/escenarios/{ens['id']}"
    estado = a3.get(copia).json()
    assert estado["escenario"]["ensayo_de"] == esc_id and estado["escenario"]["conduccion_rojo"] == "ia"
    # tiempo real: la copia arranca detenida en la misma hora que el original
    original = prof.get(base).json()["escenario"]
    assert estado["escenario"]["estado"] == "pausado" and estado["escenario"]["sim_segundos"] == original["sim_segundos"]
    propia = next(u for u in estado["unidades"] if u["nombre"] == "A")
    assert propia["fuerza"] == 70
    assert api("bravo").get(copia).status_code == 404  # el enemigo no ve el ensayo
    # el reloj del ensayo lo maneja el Comandante del bando (no otra reparticion, ni el ejercicio original)
    assert a3.post(f"{copia}/reloj", json={"estado": "activo"}).status_code == 403
    assert api("alfa").post(f"{base}/reloj", json={"estado": "activo"}).status_code == 403
    assert api("alfa").post(f"{copia}/reloj", json={"velocidad": 10, "estado": "activo"}).status_code == 200
    assert api("alfa").post(f"{copia}/reloj", json={"estado": "pausado"}).status_code == 200
    assert api("alfa").post(f"{copia}/avanzar_turno?n=1").status_code == 200
    vista = a3.get(f"{base}/tiem").json()
    e = vista["ensayos"]["azul"][0]
    assert e["turnos_jugados"] == 1 and "1 hora(s) jugada(s)" in e["texto"] and vista["puede_ensayar"]["azul"] is True
    assert prof.get(base).json()["escenario"]["sim_segundos"] == original["sim_segundos"]  # el original no se movio
    assert a3.post(f"{copia}/tiem/azul/ensayos", json={"fa": "x"}).status_code == 400  # no se ensaya un ensayo
    for _ in range(2):
        assert a3.post(f"{base}/tiem/azul/ensayos", json={"fa": "F/A 2"}).status_code == 200
    assert a3.post(f"{base}/tiem/azul/ensayos", json={"fa": "F/A 2"}).status_code == 400  # tope de tres
    assert db_session.query(Escenario).filter(Escenario.ensayo_de == esc_id).count() == 3
    assert db_session.query(Unidad).filter(Unidad.escenario_id == ens["id"]).count() == 3
