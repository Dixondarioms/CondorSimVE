"""Escenarios precargados (plantillas): listado, creacion por la API y por la CLI, y contenido de la
plantilla de estudio del 3 de enero de 2026."""

import subprocess
import sys
from pathlib import Path

from app.engine import objetivos, plantillas

RAIZ = Path(__file__).resolve().parents[1]


# ---------- catalogo de plantillas ----------
def test_hay_al_menos_la_demo_y_la_del_3_de_enero():
    assert {"demo_llanos", "defensa_3_enero_2026"} <= set(plantillas.PLANTILLAS)


def test_cada_plantilla_referencia_clases_y_modelos_validos_y_nombres_de_unidad_unicos():
    from app.engine import catalogo

    for p in plantillas.PLANTILLAS.values():
        nombres = [u.nombre for u in p.unidades]
        assert len(nombres) == len(set(nombres)), p.id
        for u in p.unidades:
            assert u.clase in catalogo.CLASES, (p.id, u.clase)
            assert u.bando in ("azul", "rojo")
            if u.modelo:
                assert u.modelo in catalogo.MODELOS and catalogo.MODELOS[u.modelo].clase == u.clase
        for o in p.objetivos:
            assert o.tipo in objetivos.TIPOS, (p.id, o.tipo)
            if o.tipo == "ocupar":
                assert o.lat is not None and o.lon is not None
            elif o.tipo != "efecto":
                assert o.unidad in nombres, (p.id, o.nombre)


def test_la_plantilla_del_3_de_enero_empareja_proteger_y_destruir_en_las_cuatro_instalaciones():
    """No toda unidad azul es un objetivo (los cazas y la AA solo defienden): las 4 instalaciones si."""
    p = plantillas.PLANTILLAS["defensa_3_enero_2026"]
    instalaciones = {"Base Aérea La Carlota", "Guarnición Fuerte Tiuna", "Puesto Naval La Guaira", "Guarnición Charallave"}
    assert instalaciones <= {u.nombre for u in p.unidades if u.bando == "azul"}
    for nombre in instalaciones:
        tipos = {o.tipo for o in p.objetivos if o.unidad == nombre}
        assert tipos == {"proteger", "destruir"}, nombre
    assert p.nacion_azul == "venezuela" and p.nacion_rojo == "estados_unidos"
    assert not any(u.modelo for u in p.unidades if u.bando == "rojo")  # sin afirmar un modelo real de EE. UU.


# ---------- crear_desde_plantilla (motor) ----------
def test_crear_desde_plantilla_arma_unidades_y_objetivos_correctamente(db_session):
    esc = plantillas.crear_desde_plantilla(db_session, "defensa_3_enero_2026")
    assert esc.nombre.startswith("3 de enero de 2026")
    assert (esc.nacion_azul, esc.nacion_rojo, esc.hora_inicio_min) == ("venezuela", "estados_unidos", 120)

    from app.models.objetivo import Objetivo
    from app.models.unidad import Unidad
    unidades = db_session.query(Unidad).filter_by(escenario_id=esc.id).all()
    assert len(unidades) == 9
    carlota = next(u for u in unidades if u.nombre == "Base Aérea La Carlota")
    assert (carlota.clase, carlota.tipo, carlota.bando) == ("base_aerea", "base", "azul")
    escuadron = next(u for u in unidades if u.nombre == "Escuadrón de Caza La Carlota")
    assert (escuadron.modelo, escuadron.aeronaves, escuadron.echelon) == ("f16", 4, "escuadrilla")
    assert escuadron.velocidad_kmh == 950  # valores del modelo F-16, no de la clase generica "caza"

    objetivos = db_session.query(Objetivo).filter_by(escenario_id=esc.id).all()
    assert len(objetivos) == 8
    proteger_carlota = next(o for o in objetivos if o.nombre == "Mantener operativa La Carlota")
    assert (proteger_carlota.bando, proteger_carlota.tipo, proteger_carlota.unidad_id, proteger_carlota.hasta_turno) == (
        "azul", "proteger", carlota.id, 8)


def test_plantilla_desconocida_lanza_keyerror(db_session):
    import pytest
    with pytest.raises(KeyError):
        plantillas.crear_desde_plantilla(db_session, "no_existe")


def test_se_pueden_crear_varias_veces_sin_chocar(db_session):
    a = plantillas.crear_desde_plantilla(db_session, "demo_llanos")
    b = plantillas.crear_desde_plantilla(db_session, "demo_llanos")
    assert a.id != b.id and a.nombre == b.nombre


# ---------- API ----------
def test_listar_plantillas_es_publico_y_no_revela_de_mas(api):
    r = api("alfa").get("/api/plantillas")
    assert r.status_code == 200
    por_id = {p["id"]: p for p in r.json()["plantillas"]}
    assert "defensa_3_enero_2026" in por_id
    assert por_id["defensa_3_enero_2026"]["unidades"] == 9 and por_id["defensa_3_enero_2026"]["objetivos"] == 8
    assert api().get("/api/plantillas").status_code == 401


def test_solo_el_instructor_crea_un_escenario_desde_una_plantilla(api):
    assert api("alfa").post("/api/plantillas/demo_llanos").status_code == 403
    r = api("prof").post("/api/plantillas/demo_llanos")
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Demo: Piedemonte andino - Llanos"


def test_plantilla_inexistente_da_404(api):
    r = api("prof").post("/api/plantillas/no_existe")
    assert r.status_code == 404


def test_el_escenario_creado_por_la_api_queda_disponible_con_su_identidad_y_objetivos(api):
    prof = api("prof")
    creado = prof.post("/api/plantillas/defensa_3_enero_2026").json()
    base = f"/api/escenarios/{creado['id']}"
    ids = [u["id"] for u in prof.get("/api/usuarios").json() if u["rol"] != "instructor"]
    prof.put(f"{base}/usuarios", json={"usuario_ids": ids})
    estado = prof.get(base).json()
    assert (estado["escenario"]["nacion_azul"], estado["escenario"]["nacion_rojo"]) == ("venezuela", "estados_unidos")
    assert len(estado["unidades"]) == 9 and len(estado["objetivos"]) == 8
    rojo_ve = api("bravo").get(base).json()
    assert all(o["bando"] == "rojo" for o in rojo_ve["objetivos"])


# ---------- CLI ----------
def test_la_cli_crea_el_escenario_en_la_base_indicada(tmp_path):
    db = tmp_path / "prueba_plantillas.db"
    r = subprocess.run(
        [sys.executable, "-m", "app.crear_demo", "defensa_3_enero_2026"],
        cwd=RAIZ, env={**__import__("os").environ, "SIMULADOR_DB": str(db)},
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert "creado desde la plantilla 'defensa_3_enero_2026'" in r.stdout
    assert db.is_file()


def test_la_cli_rechaza_una_plantilla_desconocida(tmp_path):
    db = tmp_path / "prueba_plantillas2.db"
    r = subprocess.run(
        [sys.executable, "-m", "app.crear_demo", "no_existe"],
        cwd=RAIZ, env={**__import__("os").environ, "SIMULADOR_DB": str(db)},
        capture_output=True, text=True,
    )
    assert r.returncode != 0 and "Plantilla desconocida" in r.stderr
    assert not db.exists()  # no debe crear ni tocar la base si el id no existe


def test_operacion_guri_respeta_la_zdo_y_las_cifras_de_la_situacion(db_session):
    """tools/crear_ejercicio_guri.py: Rojo al norte del paralelo 7 y Azul al sur, con las flotas de los documentos."""
    from app.engine import catalogo

    p = plantillas.PLANTILLAS["guri_2026"]
    aereas = {"azul": 0, "rojo": 0}
    for u in p.unidades:
        if u.clase != "puente":
            assert (u.lat > 7.0) == (u.bando == "rojo"), u.nombre
        if catalogo.CLASES[u.clase].tipo == "aerea":
            aereas[u.bando] += u.aeronaves
            assert u.aeronaves <= 8, u.nombre
    assert aereas == {"azul": 160, "rojo": 77}  # tripuladas y drones de la Situación de cada bando
    assert sum(u.personal or 0 for u in p.unidades if u.bando == "azul" and u.clase == "infanteria") == 6750
    assert set(p.pmo) == {"azul", "rojo"} and p.pmo["azul"]["mision"]["tarea"] == "Neutralizar"
    esc = plantillas.crear_desde_plantilla(db_session, "guri_2026")
    assert esc.fecha_inicio == "2026-06-02" and esc.turno_final == 12


def test_operacion_guri_las_tropas_de_asalto_pueden_embarcar_desde_el_primer_turno():
    from app.engine import geo, transporte

    p = plantillas.PLANTILLAS["guri_2026"]
    bases = {u.nombre.split(" ")[1]: u for u in p.unidades if u.clase == "base_aerea"}
    for u in p.unidades:
        if u.bando == "azul" and u.clase == "infanteria":
            b = bases[u.nombre.split("(")[-1].rstrip(")")]
            assert geo.distancia_km(u.lat, u.lon, b.lat, b.lon) < transporte.RADIO_EMBARQUE_KM, u.nombre


def test_tutorial_del_condor_es_chico_lo_conduce_un_alumno_contra_la_ia_y_el_enemigo_esta_lejos(db_session):
    """tools/crear_ejercicio_tutorial.py: para aprender la pantalla, con tiempo para mover y detectar antes del combate."""
    from app.engine import geo

    p = plantillas.PLANTILLAS["tutorial_condor"]
    assert len(p.unidades) <= 24 and p.ia_rojo and not p.ia_azul
    por = {u.nombre: u for u in p.unidades}
    inf, blind = por["1.ª Brigada de Infantería azul"], por["Brigada Blindada rojo"]
    assert 60 < geo.distancia_km(inf.lat, inf.lon, blind.lat, blind.lon) < 120
    assert {o.bando for o in p.objetivos} == {"azul", "rojo"}
    esc = plantillas.crear_desde_plantilla(db_session, "tutorial_condor")
    assert esc.nombre == "Tutorial del Cóndor" and esc.ia_rojo
