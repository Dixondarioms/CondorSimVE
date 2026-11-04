"""Perdidas y gastos: cada arma gastada queda anotada y el informe la suma por bando (engine/gastos.py)."""

import json

from app.engine import aar, gastos
from app.informe_html import render_html
from tests.test_salvas import _misiles, _salva_contra_fragata
from tests.test_tiempo_real import mundo_limpio  # noqa: F401 - fixture automatica


def test_la_salva_y_la_defensa_de_punto_quedan_en_el_informe(db_session):
    f, ms = _salva_contra_fragata(db_session, 4)
    esc_id = f.escenario_id
    from app.models.escenario import Escenario

    esc = db_session.get(Escenario, esc_id)
    r = gastos.resumen(db_session, esc)
    rojo = {(g["tipo"], g["arma"]): g["cantidad"] for g in r["rojo"]["gastos"]}
    assert sum(n for (t, _), n in rojo.items() if t == "Misiles de crucero") == 4
    azul = {g["tipo"]: g["cantidad"] for g in r["azul"]["gastos"]}
    assert azul.get("Defensa de punto", 0) >= 1
    assert all(m.estado == "destruida" for m in ms)
    assert r["rojo"]["perdidas"]["Aeronaves"] == 0  # los misiles no cuentan como perdidas
    informe = aar.construir_informe(db_session, esc)
    assert informe["perdidas_gastos"] == r
    html = render_html(informe)
    assert "Pérdidas y gastos" in html and "Misiles de crucero" in html


def test_las_perdidas_cuentan_aviones_buques_y_tierra(db_session):
    from app.models.unidad import Unidad
    from tests.test_orders import _escenario, _unidad

    esc = _escenario(db_session)
    _unidad(db_session, esc, nombre="Caza", tipo="aerea", clase="caza", aeronaves=4, estado="destruida")
    _unidad(db_session, esc, nombre="Fragata", tipo="naval", clase="fragata", estado="destruida")
    _unidad(db_session, esc, nombre="Brigada", bando="rojo", clase="infanteria", estado="destruida")
    _unidad(db_session, esc, nombre="Misil", bando="rojo", tipo="aerea", clase="misil_crucero", estado="destruida")
    r = gastos.resumen(db_session, esc)
    assert r["azul"]["perdidas"] == {"Aeronaves": 4, "Buques": 1, "Unidades de tierra": 0, "Instalaciones": 0}
    assert r["rojo"]["perdidas"]["Unidades de tierra"] == 1 and r["rojo"]["perdidas"]["Aeronaves"] == 0
    assert db_session.query(Unidad).count() >= 4 and json.dumps(r)
