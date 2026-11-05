"""Reproduccion de operaciones historicas: ordenes programadas por la cronologia, nadie da ordenes y el informe
compara con lo que paso en la realidad."""

import pytest

from app.engine import aar, plantillas, tiempo_real
from app.informe_html import render_html
from app.models.orden import Orden
from app.models.unidad import Unidad
from tests.conftest import TerrenoFalso

HISTORIA = {"fecha": "1999-01-01", "resumen": "Operación de prueba.",
            "resultado_real": {"texto": "El depósito fue destruido.", "perdidas_rojo": [], "perdidas_azul": ["Depósito"]},
            "fuentes": [{"titulo": "Fuente de prueba", "url": "https://example.org/fuente", "nota": "cronología"}],
            "incertidumbres": ["Posiciones aproximadas."]}


def _plantilla():
    U = plantillas.UnidadPlantilla
    return plantillas.Plantilla(
        id="prueba_historica", nombre="Operación de prueba", descripcion="", hora_inicio_min=60, historia=HISTORIA,
        unidades=(U("Base roja", "rojo", "base_aerea", 0.0, 0.0),
                  U("Ataque 1", "rojo", "ataque", 0.0, 0.01, aeronaves=2),
                  U("Depósito", "azul", "deposito", 0.9, 0.0)),
        eventos_auto=({"id": "h1", "nombre": "01:10 ataque", "activo": True, "repetir": False,
                       "disparador": {"tipo": "hora", "hora": "01:10"},
                       "acciones": [{"tipo": "mensaje", "para": "todos", "texto": "El paquete sale hacia el depósito."},
                                    {"tipo": "ordenar", "unidad": "Ataque 1", "orden": "atacar", "blanco": "Depósito"}]},),
    )


@pytest.fixture()
def esc(db_session, monkeypatch):
    monkeypatch.setitem(plantillas.PLANTILLAS, "prueba_historica", _plantilla())
    e = plantillas.crear_desde_plantilla(db_session, "prueba_historica")
    e.estado = "activo"
    db_session.commit()
    return e


def test_la_cronologia_da_las_ordenes_aunque_el_blanco_no_se_vea(db_session, esc):
    assert esc.historica and esc.historia["fecha"] == "1999-01-01"
    for _ in range(8):
        tiempo_real.paso(db_session, esc, 600, TerrenoFalso())
        db_session.commit()
    deposito = db_session.query(Unidad).filter_by(escenario_id=esc.id, nombre="Depósito").one()
    ataque = db_session.query(Orden).filter_by(escenario_id=esc.id, tipo="atacar").one()
    assert ataque.objetivo_unidad_id == deposito.id
    assert deposito.fuerza < 100  # lo encontro y lo ataco (blanco planificado: no hace falta verlo)


def test_nadie_da_ordenes_y_el_informe_compara_con_lo_real(db_session, esc):
    from fastapi import HTTPException

    from app.routers.ordenes import _en_decision

    with pytest.raises(HTTPException) as e:
        _en_decision(esc)
    assert "Reproducción histórica" in e.value.detail
    informe = aar.construir_informe(db_session, esc)
    assert informe["historia"]["resultado_real"]["perdidas_azul"] == ["Depósito"]
    assert set(informe["historia"]["simulado"]) == {"rojo", "azul"}
    html = render_html(informe)
    assert "Lo que pasó en la realidad" in html and "https://example.org/fuente" in html


def test_la_plantilla_guardada_conserva_la_historia(db_session, esc, tmp_path, monkeypatch):
    monkeypatch.setattr(plantillas, "RUTA_PLANTILLAS_USUARIO", tmp_path)
    p = plantillas.guardar_desde_escenario(db_session, esc, "Copia histórica")
    assert p.historia["fecha"] == "1999-01-01"


@pytest.mark.parametrize("pid", ["historica_malvinas_sheffield_1982", "historica_opera_1981",
                                 "historica_el_dorado_canyon_1986", "historica_tormenta_desierto_1991"])
def test_las_operaciones_historicas_se_reproducen_hasta_el_final(db_session, pid):
    from app.models.objetivo import Objetivo

    p = plantillas.PLANTILLAS[pid]
    assert p.historia and p.historia["fuentes"] and p.historia["resultado_real"]["texto"]
    assert not p.ia_azul and not p.ia_rojo
    e = plantillas.crear_desde_plantilla(db_session, pid)
    e.estado = "activo"
    db_session.commit()
    for _ in range(48):  # hasta 12 h en pasos de 15 minutos
        tiempo_real.paso(db_session, e, 900, TerrenoFalso())
        db_session.commit()
        if e.estado == "finalizado":
            break
    assert e.estado == "finalizado"
    assert db_session.query(Orden).filter_by(escenario_id=e.id).count() > 3  # la cronologia dio sus ordenes
    assert not db_session.query(Objetivo).filter_by(escenario_id=e.id, bando="rojo", estado="pendiente").count()


def test_el_regreso_espera_que_termine_el_ataque_y_la_carga_se_aplica(db_session, monkeypatch):
    import json as _json

    from app.engine import eventos_auto

    U = plantillas.UnidadPlantilla
    p = plantillas.Plantilla(
        id="prueba_espera", nombre="Espera", descripcion="", hora_inicio_min=60, historia=HISTORIA,
        unidades=(U("Base roja", "rojo", "base_aerea", 0.0, 0.0),
                  U("F-16A", "rojo", "caza", 0.0, 0.0, modelo="f16a", aeronaves=2, en_tierra=True, base="Base roja"),
                  U("Depósito", "azul", "deposito", 1.5, 0.0)),
        eventos_auto=({"id": "a", "nombre": "ataque", "activo": True, "disparador": {"tipo": "hora", "hora": "01:05"},
                       "acciones": [{"tipo": "ordenar", "unidad": "F-16A", "orden": "atacar", "blanco": "Depósito",
                                     "carga": "ataque"}]},
                      {"id": "b", "nombre": "regreso", "activo": True, "disparador": {"tipo": "hora", "hora": "01:10"},
                       "acciones": [{"tipo": "ordenar", "unidad": "F-16A", "orden": "aterrizar", "blanco": "Base roja"}]}),
    )
    monkeypatch.setitem(plantillas.PLANTILLAS, "prueba_espera", p)
    e = plantillas.crear_desde_plantilla(db_session, "prueba_espera")
    e.estado = "activo"
    db_session.commit()
    f16 = db_session.query(Unidad).filter_by(escenario_id=e.id, nombre="F-16A").one()
    for _ in range(3):  # hasta las 01:15: el ataque sigue (el deposito esta a 165 km)
        tiempo_real.paso(db_session, e, 300, TerrenoFalso())
        db_session.commit()
    assert _json.loads(f16.armamento_json)["nombre"] == "ataque"  # la carga de la mision
    assert db_session.get(Orden, f16.orden_id).tipo == "atacar"  # el regreso espera
    assert eventos_auto.config(e).get("pendientes")
    for _ in range(12):
        tiempo_real.paso(db_session, e, 300, TerrenoFalso())
        db_session.commit()
    assert db_session.query(Orden).filter_by(escenario_id=e.id, unidad_id=f16.id, tipo="aterrizar").count() >= 1
    assert not eventos_auto.config(e).get("pendientes")
