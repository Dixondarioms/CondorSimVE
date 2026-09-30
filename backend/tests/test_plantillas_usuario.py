"""Plantillas guardadas por el instructor desde un escenario en curso (POST /api/escenarios/{id}/guardar_plantilla):
se listan junto a las del codigo, se instancian con POST /api/plantillas/{id} y se eliminan con DELETE."""

import json

import pytest

from app.engine import plantillas
from app.models.objetivo import Objetivo
from app.models.unidad import Unidad
from tests.test_api import _preparar


def _guardar(prof, base, **extra):
    cuerpo = {"nombre": "Ejercicio Guardado: Ataque al Río", "descripcion": "Situación tras dos turnos", **extra}
    return prof.post(f"{base}/guardar_plantilla", json=cuerpo)


# ---------- generar_id / validar_id ----------
def test_el_id_se_deriva_del_nombre_sin_acentos_ni_simbolos():
    assert plantillas.generar_id("Ejercicio Guardado: Ataque al Río") == "ejercicio-guardado-ataque-al-rio"
    assert plantillas.generar_id("  ¡¡Hola!!  ") == "hola"
    assert plantillas.generar_id("!!!") == ""
    assert len(plantillas.generar_id("a" * 200)) == 60


@pytest.mark.parametrize("malo", ["", "../x", "..", "a/b", "a\\b", "Mayus", "con espacio", "-empieza", "x" * 61, "ñ"])
def test_validar_id_rechaza_rutas_y_caracteres_raros(malo):
    with pytest.raises(plantillas.PlantillaInvalida):
        plantillas.validar_id(malo)
    with pytest.raises(plantillas.PlantillaInvalida):
        plantillas.eliminar_usuario(malo)


# ---------- ciclo completo por la API ----------
def test_guardar_listar_instanciar_y_eliminar(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/objetivos", json={"bando": "azul", "tipo": "destruir", "nombre": "Destruir R1", "puntos": 30,
                                         "unidad_id": r1["id"]})
    prof.patch(f"{base}/config", json={"clima": "lluvia", "nacion_azul": "venezuela", "nacion_rojo": "colombia"})
    # movemos A para comprobar que se guarda la posicion ACTUAL, no la inicial
    api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.2, 0]]})
    prof.post(f"{base}/avanzar_turno")
    lat_actual = next(u["lat"] for u in prof.get(base).json()["unidades"] if u["id"] == a["id"])
    assert lat_actual > 0

    r = _guardar(prof, base)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == "ejercicio-guardado-ataque-al-rio" and d["origen"] == "usuario" and d["con_estado"] is False
    assert d["unidades"] == 3 and d["objetivos"] == 1 and d["nacion_rojo"] == "colombia"

    archivo = plantillas.RUTA_PLANTILLAS_USUARIO / "ejercicio-guardado-ataque-al-rio.json"
    assert archivo.is_file()
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    assert [u["nombre"] for u in datos["unidades"]] == ["A", "R1", "R2"]
    assert datos["unidades"][0]["lat"] == pytest.approx(lat_actual, abs=1e-5)
    assert "fuerza" not in datos["unidades"][0] and datos["clima"] == "lluvia"
    assert datos["objetivos"][0]["unidad"] == "R1"

    # aparece en la lista junto a las del codigo (para cualquier usuario con sesion), marcada como del usuario
    lista = {p["id"]: p for p in api("alfa").get("/api/plantillas").json()["plantillas"]}
    assert "demo_llanos" in lista and lista["demo_llanos"]["origen"] == "codigo"
    assert lista["ejercicio-guardado-ataque-al-rio"]["origen"] == "usuario"

    # se instancia por el mismo camino que las del codigo
    nuevo = prof.post("/api/plantillas/ejercicio-guardado-ataque-al-rio")
    assert nuevo.status_code == 200, nuevo.text
    estado = prof.get(f"/api/escenarios/{nuevo.json()['id']}").json()
    assert estado["escenario"]["nombre"] == "Ejercicio Guardado: Ataque al Río"
    assert (estado["escenario"]["clima"], estado["escenario"]["nacion_rojo"]) == ("lluvia", "colombia")
    assert sorted(u["nombre"] for u in estado["unidades"]) == ["A", "R1", "R2"]
    copia_a = next(u for u in estado["unidades"] if u["nombre"] == "A")
    assert copia_a["lat"] == pytest.approx(lat_actual, abs=1e-5) and copia_a["fuerza"] == 100
    assert estado["objetivos"][0]["nombre"] == "Destruir R1" and estado["objetivos"][0]["estado"] == "pendiente"

    # y se elimina (solo las del usuario)
    assert prof.delete("/api/plantillas/ejercicio-guardado-ataque-al-rio").status_code == 200
    assert not archivo.exists()
    assert "ejercicio-guardado-ataque-al-rio" not in {p["id"] for p in prof.get("/api/plantillas").json()["plantillas"]}
    assert prof.post("/api/plantillas/ejercicio-guardado-ataque-al-rio").status_code == 404
    assert prof.delete("/api/plantillas/ejercicio-guardado-ataque-al-rio").status_code == 404
    assert prof.delete("/api/plantillas/demo_llanos").status_code == 400


def test_con_estado_conserva_fuerza_combustible_y_municion(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.patch(f"{base}/unidades/{a['id']}", json={"fuerza": 55, "combustible": 40, "municion": 20})
    r = _guardar(prof, base, con_estado=True)
    assert r.status_code == 200, r.text
    estado = prof.get(f"/api/escenarios/{prof.post('/api/plantillas/' + r.json()['id']).json()['id']}").json()
    copia_a = next(u for u in estado["unidades"] if u["nombre"] == "A")
    assert (copia_a["fuerza"], copia_a["combustible"], copia_a["municion"]) == (55, 40, 20)


def test_las_unidades_destruidas_y_sus_objetivos_no_se_guardan(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/objetivos", json={"bando": "azul", "tipo": "destruir", "nombre": "Destruir R2", "puntos": 10,
                                         "unidad_id": r2["id"]})
    prof.patch(f"{base}/unidades/{r2['id']}", json={"estado": "destruida"})
    r = _guardar(prof, base, con_estado=True)
    assert r.status_code == 200, r.text
    assert (r.json()["unidades"], r.json()["objetivos"]) == (2, 0)


def test_solo_el_instructor_guarda_y_elimina(api):
    prof, base, *_ = _preparar(api)
    for nombre in ("alfa", "bravo", "obs"):
        assert api(nombre).post(f"{base}/guardar_plantilla", json={"nombre": "x"}).status_code == 403
        assert api(nombre).delete("/api/plantillas/lo-que-sea").status_code == 403
    assert api().post(f"{base}/guardar_plantilla", json={"nombre": "x"}).status_code == 401


@pytest.mark.parametrize("nombre", ["", "   ", "!!!", "¿?", "x" * 81, "demo_llanos", "Demo Llanos"])
def test_nombres_invalidos_o_que_chocan_con_una_del_sistema_dan_400(api, nombre):
    prof, base, *_ = _preparar(api)
    r = prof.post(f"{base}/guardar_plantilla", json={"nombre": nombre})
    assert r.status_code in (400, 422), (nombre, r.text)
    assert not plantillas.RUTA_PLANTILLAS_USUARIO.exists() or not list(plantillas.RUTA_PLANTILLAS_USUARIO.iterdir())


def test_no_pisa_una_plantilla_existente_salvo_que_se_pida(api):
    prof, base, *_ = _preparar(api)
    assert _guardar(prof, base).status_code == 200
    assert _guardar(prof, base).status_code == 409
    r = _guardar(prof, base, reemplazar=True, descripcion="segunda version")
    assert r.status_code == 200 and r.json()["descripcion"] == "segunda version"


def test_un_archivo_corrupto_se_ignora_sin_romper_el_listado(api):
    prof, base, *_ = _preparar(api)
    assert _guardar(prof, base).status_code == 200
    carpeta = plantillas.RUTA_PLANTILLAS_USUARIO
    (carpeta / "roto.json").write_text("{esto no es json", encoding="utf-8")
    (carpeta / "clase-mala.json").write_text(json.dumps({"id": "clase-mala", "nombre": "x", "unidades": [
        {"nombre": "U", "bando": "azul", "clase": "no_existe", "lat": 0, "lon": 0}]}), encoding="utf-8")
    ids = {p["id"] for p in prof.get("/api/plantillas").json()["plantillas"]}
    assert "ejercicio-guardado-ataque-al-rio" in ids and "roto" not in ids and "clase-mala" not in ids


def test_aeronave_en_tierra_conserva_su_base_al_instanciar(db_session):
    from tests.test_orders import _escenario, _unidad

    esc = _escenario(db_session)
    base = _unidad(db_session, esc, nombre="BA Sur", tipo="base", clase="base_aerea", lat=8.6, lon=-70.2)
    grupo = _unidad(db_session, esc, nombre="Halcon 1", tipo="aerea", clase="caza", modelo="f16", aeronaves=2,
                    lat=8.6, lon=-70.2, en_tierra=True, base_id=base.id)
    _unidad(db_session, esc, nombre="Halcon 1", tipo="aerea", clase="caza", lat=8.7, lon=-70.3)  # nombre repetido
    p = plantillas.guardar_desde_escenario(db_session, esc, "Con base", con_estado=False)
    nombres = [u.nombre for u in p.unidades]
    assert nombres == ["BA Sur", "Halcon 1", "Halcon 1 (2)"]
    assert p.unidades[1].en_tierra and p.unidades[1].base == "BA Sur" and p.unidades[1].modelo == "f16"

    nuevo = plantillas.crear_desde_plantilla(db_session, p.id)
    unidades = {u.nombre: u for u in db_session.query(Unidad).filter_by(escenario_id=nuevo.id)}
    assert unidades["Halcon 1"].en_tierra and unidades["Halcon 1"].base_id == unidades["BA Sur"].id
    assert unidades["Halcon 1"].aeronaves == 2 and unidades["Halcon 1 (2)"].base_id is None
    assert db_session.query(Objetivo).filter_by(escenario_id=nuevo.id).count() == 0
    assert plantillas.todas()["con-base"].origen == "usuario" and "demo_llanos" in plantillas.todas()
