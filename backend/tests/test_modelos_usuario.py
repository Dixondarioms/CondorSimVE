"""Catalogo propio: tipos de unidad definidos por el instructor desde la consola, disponibles al instante."""

from app.engine import catalogo, modelos_usuario
from tests.test_api import _preparar

BUK = {"nombre": "Buk-M2E", "corto": "Buk", "clase": "antiaerea", "pais": "Venezuela", "velocidad_kmh": 45,
       "alcance_km": 45, "deteccion_km": 100, "autonomia_km": 400, "defensa": 1.0,
       "ataque_vs": {"terrestre": 0.2, "aerea": 2.6, "naval": 0.2}}


def test_el_instructor_crea_un_tipo_y_lo_usa_al_agregar_una_unidad(api):
    prof, base, *_ = _preparar(api)
    r = prof.post("/api/catalogo/modelos", json=BUK)
    assert r.status_code == 200, r.text
    tipo = r.json()
    assert tipo["id"] == "u_buk_m2e" and tipo["propio"] and tipo["clase"] == "antiaerea"
    assert any(m["id"] == "u_buk_m2e" for m in prof.get("/api/catalogo").json()["modelos"])
    r = prof.post(f"{base}/unidades", json={"nombre": "Buk La Carlota", "bando": "azul", "lat": 0.3, "lon": 0.3,
                                            "modelo": "u_buk_m2e"})
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["clase"] == "antiaerea" and u["alcance_km"] == 45 and u["deteccion_km"] == 100
    assert u["echelon"] == catalogo.CLASES["antiaerea"].escalon  # no se toma el escalon de un grupo aereo
    assert modelos_usuario.RUTA.is_file()


def test_editar_y_eliminar_un_tipo_propio(api):
    prof, *_ = _preparar(api)
    prof.post("/api/catalogo/modelos", json=BUK)
    r = prof.post("/api/catalogo/modelos", json={**BUK, "id": "u_buk_m2e", "alcance_km": 50})
    assert r.json()["alcance_km"] == 50
    assert sum(1 for m in prof.get("/api/catalogo").json()["modelos"] if m["propio"]) == 1
    assert prof.delete("/api/catalogo/modelos/u_buk_m2e").status_code == 200
    assert "u_buk_m2e" not in catalogo.MODELOS
    assert prof.delete("/api/catalogo/modelos/u_buk_m2e").status_code == 404
    assert prof.delete("/api/catalogo/modelos/f16").status_code == 404  # los del sistema no se tocan


def test_valida_los_datos_y_solo_el_instructor_puede(api):
    prof, *_ = _preparar(api)
    assert prof.post("/api/catalogo/modelos", json={**BUK, "clase": "base_aerea"}).status_code == 400
    assert prof.post("/api/catalogo/modelos", json={**BUK, "alcance_km": -5}).status_code == 400
    assert prof.post("/api/catalogo/modelos", json={**BUK, "nombre": "x"}).status_code == 400
    assert prof.post("/api/catalogo/modelos", json={**BUK, "defensa": 0}).status_code == 400
    assert api("alfa").post("/api/catalogo/modelos", json=BUK).status_code == 403


def test_un_archivo_con_tipos_invalidos_no_impide_cargar_los_validos(tmp_path, monkeypatch):
    import json
    ruta = tmp_path / "m.json"
    ruta.write_text(json.dumps({"tipos": [BUK, {"nombre": "Malo", "clase": "inexistente"}]}), encoding="utf-8")
    monkeypatch.setattr(modelos_usuario, "RUTA", ruta)
    assert modelos_usuario.aplicar() == ["u_buk_m2e"]
