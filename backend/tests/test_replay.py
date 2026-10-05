"""Replay animado del informe: GET /api/escenarios/{id}/aar/replay entrega, por turno, las posiciones de todas
las unidades, los combates con su lugar, las novedades publicas y el marcador acumulado."""

from tests.test_api import _preparar


def _jugar_tres_turnos(api):
    """A avanza hacia el norte, vuelve junto a R1 y la ataca en el tercer turno."""
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0.0]]})
    assert r.status_code == 200, r.text
    prof.post(f"{base}/avanzar_turno")  # T1: ~11 km al norte
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.02, 0.0]]})
    assert r.status_code == 200, r.text
    prof.post(f"{base}/avanzar_turno")  # T2: vuelve al sur, a ~3 km de R1
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    assert r.status_code == 200, r.text
    prof.post(f"{base}/avanzar_turno")  # T3: combate
    return prof, base, a, r1, r2


def test_el_replay_tiene_posiciones_distintas_por_turno(api):
    prof, base, a, r1, r2 = _jugar_tres_turnos(api)
    rp = prof.get(f"{base}/aar/replay").json()
    assert rp["escenario"]["id"] == int(base.rsplit("/", 1)[1]) and rp["escenario"]["hora_inicio_min"] == 360
    assert [t["turno"] for t in rp["turnos"]] == [0, 1, 2, 3]  # despliegue inicial + 3 turnos resueltos
    for t in rp["turnos"]:
        assert len(t["unidades"]) == 3
        for u in t["unidades"]:
            assert set(u) == {"id", "nombre", "bando", "tipo", "clase", "sidc", "lat", "lon", "fuerza", "estado"}
    lat_a = [next(u for u in t["unidades"] if u["id"] == a["id"])["lat"] for t in rp["turnos"]]
    assert lat_a[0] == 0.0 and lat_a[1] > lat_a[2] > lat_a[0]  # se movio en T1 (norte) y T2 (vuelve)
    assert abs(lat_a[1] - 0.1) < 0.01 and abs(lat_a[2] - 0.02) < 0.01 and lat_a[3] == lat_a[2]
    lat_r2 = {next(u for u in t["unidades"] if u["id"] == r2["id"])["lat"] for t in rp["turnos"]}
    assert lat_r2 == {1.8}  # R2 no recibio ordenes: no se mueve


def test_el_replay_incluye_combates_con_lugar_y_marcador_acumulado(api):
    prof, base, a, r1, r2 = _jugar_tres_turnos(api)
    rp = prof.get(f"{base}/aar/replay").json()
    t0, t1, t2, t3 = rp["turnos"]
    assert t0["combates"] == t1["combates"] == t2["combates"] == []
    (c,) = t3["combates"]
    assert c["atacante_id"] == a["id"] and c["defensor_id"] == r1["id"] and c["atacante_bando"] == "azul"
    assert c["lat"] is not None and c["lon"] is not None and c["perdida_defensor"] > 0
    # la fuerza de la instantanea refleja el combate
    fuerza = lambda t, uid: next(u for u in t["unidades"] if u["id"] == uid)["fuerza"]
    assert fuerza(t2, r1["id"]) == 100 and fuerza(t3, r1["id"]) < 100
    # el marcador acumulado solo suma a partir del turno del combate (un punto por cada 10 de fuerza infligida)
    assert t2["marcador"]["azul"]["total"] == 0
    assert t3["marcador"]["azul"]["bajas"] == int(c["perdida_defensor"] // 10)
    assert t3["marcador"]["azul"]["total"] == t3["marcador"]["azul"]["bajas"]
    assert t3["marcador"] == prof.get(f"{base}/aar").json()["marcador"]  # el ultimo turno coincide con el marcador actual


def test_el_replay_solo_muestra_novedades_publicas(api):
    prof, base, a, r1, r2 = _jugar_tres_turnos(api)
    prof.post(f"{base}/eventos", json={"tipo": "inteligencia", "descripcion": "Solo para azul", "bando_destino": "azul"})
    prof.post(f"{base}/eventos", json={"tipo": "inteligencia", "descripcion": "Para todos", "bando_destino": "todos"})
    prof.patch(f"{base}/config", json={"clima": "lluvia"})
    prof.post(f"{base}/avanzar_turno")  # T4: los eventos se emitieron durante el turno 4
    rp = prof.get(f"{base}/aar/replay").json()
    t4 = rp["turnos"][-1]
    assert t4["turno"] == 4 and t4["clima"] == "lluvia"
    descripciones = [e["descripcion"] for e in t4["eventos"]]
    assert "Para todos" in descripciones and "El clima cambia a lluvia." in descripciones
    assert "Solo para azul" not in descripciones


def test_el_replay_respeta_los_permisos_del_informe(api):
    prof, base, *_ = _jugar_tres_turnos(api)
    for nombre in ("alfa", "bravo"):
        assert api(nombre).get(f"{base}/aar/replay").status_code == 403  # antes de finalizar
    assert api("obs").get(f"{base}/aar/replay").status_code == 200
    prof.post(f"{base}/finalizar")
    for nombre in ("alfa", "bravo"):
        assert api(nombre).get(f"{base}/aar/replay").status_code == 200
    assert api().get(f"{base}/aar/replay").status_code == 401


def test_sin_turnos_resueltos_el_replay_esta_vacio(api):
    prof, base, *_ = _preparar(api)
    rp = prof.get(f"{base}/aar/replay").json()
    assert rp["turnos"] == [] and rp["escenario"]["turno_actual"] == 1
    # el informe completo sigue entregando lo mismo de siempre
    assert prof.get(f"{base}/aar").json()["turnos"] == []
