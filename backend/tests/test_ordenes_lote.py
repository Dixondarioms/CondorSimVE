"""Seleccion multiple: la misma orden para varias unidades, con formacion."""

from tests.test_api import _preparar


def test_lote_de_movimiento_en_formacion_y_errores_por_unidad(api):
    prof, base, a, r1, r2 = _preparar(api)
    b = prof.post(f"{base}/unidades", json=dict(nombre="B", bando="azul", tipo="terrestre", lat=0.0, lon=0.05)).json()
    c = prof.post(f"{base}/unidades", json=dict(nombre="C", bando="azul", tipo="base", clase="deposito", lat=0.0, lon=0.1)).json()
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes/lote", json={"unidad_ids": [a["id"], b["id"], c["id"]], "formacion": True,
                                              "orden": {"tipo": "mover", "waypoints": [[0.2, 0.0]]}})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["emitidas"] == 2 and [x["ok"] for x in res["resultados"]] == [True, True, False]
    assert "no puede moverse" in res["resultados"][2]["detalle"]
    ordenes = {o["unidad_id"]: o for o in azul.get(base).json()["ordenes"]}
    assert ordenes[a["id"]]["waypoints"][0] == [0.2, 0.0]
    assert ordenes[b["id"]]["waypoints"][0] == [0.2, 0.05]  # conserva su posicion relativa (formacion)
    # sin formacion todas van al mismo punto; una orden de ataque en lote comparte el objetivo
    r = azul.post(f"{base}/ordenes/lote", json={"unidad_ids": [a["id"], b["id"]], "formacion": False, "orden": {"tipo": "mover", "waypoints": [[0.2, 0.0]]}})
    ordenes = {o["unidad_id"]: o for o in azul.get(base).json()["ordenes"]}
    assert ordenes[b["id"]]["waypoints"][0] == [0.2, 0.0]
    r = azul.post(f"{base}/ordenes/lote", json={"unidad_ids": [a["id"], b["id"]], "orden": {"tipo": "atacar", "objetivo_unidad_id": r1["id"]}})
    assert r.json()["emitidas"] == 2
    assert api("bravo").post(f"{base}/ordenes/lote", json={"unidad_ids": [a["id"]], "orden": {"tipo": "mover", "waypoints": [[0.2, 0.0]]}}).json()["emitidas"] == 0
    assert azul.post(f"{base}/ordenes", json={"tipo": "mover", "waypoints": [[0.2, 0.0]]}).status_code == 400
