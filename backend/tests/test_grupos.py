"""Grupos de tarea (app/routers/grupos.py): unidades propias bajo un nombre que se eligen juntas."""

from tests.test_api import _preparar


def test_crear_ver_y_disolver_un_grupo_de_tarea(api):
    prof, base, a, r1, r2 = _preparar(api)
    alfa, bravo = api("alfa"), api("bravo")
    b = prof.post(f"{base}/unidades", json=dict(nombre="B", bando="azul", tipo="terrestre", lat=0.01, lon=0.0)).json()
    r = alfa.post(f"{base}/grupos", json={"nombre": "Grupo 1", "unidad_ids": [a["id"], b["id"]]})
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["bando"] == "azul" and g["unidad_ids"] == [a["id"], b["id"]]
    assert [x["nombre"] for x in alfa.get(base).json()["grupos"]] == ["Grupo 1"]
    assert bravo.get(base).json()["grupos"] == []  # el otro bando no los ve
    assert alfa.post(f"{base}/grupos", json={"nombre": "Mixto", "unidad_ids": [a["id"], r1["id"]]}).status_code == 400
    assert alfa.post(f"{base}/grupos", json={"nombre": "Solo", "unidad_ids": [a["id"]]}).status_code == 422
    assert bravo.delete(f"{base}/grupos/{g['id']}").status_code == 404
    assert alfa.delete(f"{base}/grupos/{g['id']}").status_code == 200
    assert alfa.get(base).json()["grupos"] == []
