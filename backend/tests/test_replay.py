"""Repeticion animada del informe: GET /api/escenarios/{id}/aar/replay entrega, en tiempo real, un cuadro cada 5
minutos simulados con las posiciones de todas las unidades, los combates de ese lapso con su lugar, las novedades
publicas y el marcador acumulado."""

from tests.test_api import _preparar


def _jugar_tres_horas(api):
    """A avanza hacia el norte, vuelve junto a R1 y la ataca en la tercera hora (cada hora, adelantando el reloj)."""
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0.0]]})
    assert r.status_code == 200, r.text
    prof.post(f"{base}/avanzar_turno")  # hora 1: ~11 km al norte (llega en unos 22 min)
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.02, 0.0]]})
    assert r.status_code == 200, r.text
    prof.post(f"{base}/avanzar_turno")  # hora 2: vuelve al sur, a ~3 km de R1
    r = azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    assert r.status_code == 200, r.text
    prof.post(f"{base}/avanzar_turno")  # hora 3: combate continuo
    return prof, base, a, r1, r2


def test_el_replay_tiene_un_cuadro_cada_cinco_minutos(api):
    prof, base, a, r1, r2 = _jugar_tres_horas(api)
    rp = prof.get(f"{base}/aar/replay").json()
    assert rp["escenario"]["id"] == int(base.rsplit("/", 1)[1]) and rp["escenario"]["hora_inicio_min"] == 360
    assert rp["escenario"]["tiempo_real"] is True and rp["escenario"]["duracion_cuadro_ms"] > 0
    cuadros = rp["turnos"]
    assert [c["sim_segundos"] for c in cuadros] == [300.0 * i for i in range(37)]  # 3 h: inicio + 36 cuadros
    assert cuadros[0]["hora"] == "06:00" and cuadros[12]["hora"] == "07:00" and cuadros[-1]["hora"] == "09:00"
    assert cuadros[0]["turno"] == 1 and cuadros[-1]["turno"] == 4
    for c in cuadros:
        assert len(c["unidades"]) == 3
        for u in c["unidades"]:
            assert set(u) == {"id", "nombre", "bando", "tipo", "clase", "sidc", "lat", "lon", "fuerza", "estado"}
    lat_a = [next(u for u in c["unidades"] if u["id"] == a["id"])["lat"] for c in cuadros]
    assert lat_a[0] == 0.0 and 0 < lat_a[1] < lat_a[2] < lat_a[4]  # avanza de a poco, cuadro a cuadro
    assert abs(lat_a[12] - 0.1) < 0.005 and abs(lat_a[24] - 0.02) < 0.005  # al final de las horas 1 y 2
    assert {next(u for u in c["unidades"] if u["id"] == r2["id"])["lat"] for c in cuadros} == {1.8}


def test_el_replay_ubica_los_combates_en_su_cuadro(api):
    prof, base, a, r1, r2 = _jugar_tres_horas(api)
    cuadros = prof.get(f"{base}/aar/replay").json()["turnos"]
    assert all(c["combates"] == [] for c in cuadros[:25])  # nada hasta la hora 3
    con = [c for c in cuadros if c["combates"]]
    assert con, "el combate continuo de la hora 3 tiene que figurar"
    c = con[0]["combates"][0]
    assert c["atacante_id"] == a["id"] and c["defensor_id"] == r1["id"] and c["perdida_defensor"] > 0
    fuerza = lambda cuadro, uid: next(u for u in cuadro["unidades"] if u["id"] == uid)["fuerza"]  # noqa: E731
    assert fuerza(cuadros[24], r1["id"]) == 100 and fuerza(cuadros[-1], r1["id"]) < 100
    assert cuadros[-1]["marcador"] == prof.get(f"{base}/aar").json()["marcador"]


def test_el_replay_solo_muestra_novedades_publicas(api):
    prof, base, a, r1, r2 = _jugar_tres_horas(api)
    prof.post(f"{base}/eventos", json={"tipo": "inteligencia", "descripcion": "Solo para azul", "bando_destino": "azul"})
    prof.post(f"{base}/eventos", json={"tipo": "inteligencia", "descripcion": "Para todos", "bando_destino": "todos"})
    prof.patch(f"{base}/config", json={"clima": "lluvia"})
    prof.post(f"{base}/avanzar_turno")  # los eventos ocurrieron a las 09:00: van en el cuadro siguiente
    cuadros = prof.get(f"{base}/aar/replay").json()["turnos"]
    c = next(x for x in cuadros if x["sim_segundos"] == 3 * 3600 + 300)
    assert c["clima"] == "lluvia"
    descripciones = [e["descripcion"] for e in c["eventos"]]
    assert "Para todos" in descripciones and "El clima cambia a lluvia." in descripciones
    assert "Solo para azul" not in descripciones
    assert all("Para todos" not in [e["descripcion"] for e in x["eventos"]] for x in cuadros if x is not c)


def test_el_replay_respeta_los_permisos_del_informe(api):
    prof, base, *_ = _jugar_tres_horas(api)
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
