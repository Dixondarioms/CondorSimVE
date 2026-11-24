"""Pantallas por reparticion: la PC del director abre la ventana de una reparticion en solo lectura
(X-Solo-Lectura) o dando ordenes desde ella (X-Conduce-Bando + X-Conduce-Puesto)."""

from tests.test_api import _preparar

SOLO_LECTURA = {"X-Solo-Lectura": "1"}


def test_la_ventana_en_solo_lectura_no_escribe_nada(api):
    prof, base, a, r1, _ = _preparar(api)
    # leer, si
    assert prof.get(base, headers=SOLO_LECTURA).status_code == 200
    assert prof.get(f"{base}/pmo", headers=SOLO_LECTURA).status_code == 200
    # escribir, no: ni las funciones del director (reloj, configuracion, unidades) ni las ordenes ni el TIEM
    escrituras = [
        ("patch", f"{base}/config", {"velocidad": 10}),
        ("post", f"{base}/unidades", {"nombre": "X", "bando": "azul", "tipo": "terrestre", "lat": 0.0, "lon": 0.1}),
        ("post", f"{base}/ordenes", {"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0.0]]}),
        ("put", f"{base}/pmo/rojo", {"contenido": {"situacion_general": "x"}}),
    ]
    for metodo, ruta, cuerpo in escrituras:
        r = getattr(prof, metodo)(ruta, json=cuerpo, headers=SOLO_LECTURA)
        assert r.status_code == 403, (ruta, r.text)
        assert r.json()["detail"] == "Esta ventana esta en solo lectura"
        assert r.headers["X-Frame-Options"] == "DENY"  # la respuesta lleva las cabeceras de seguridad
    r = prof.delete(f"{base}/unidades/{r1['id']}", headers=SOLO_LECTURA)
    assert r.status_code == 403
    assert prof.get(base).json()["escenario"]["velocidad"] != 10
    assert r1["id"] in {u["id"] for u in prof.get(base).json()["unidades"]}
    # sin la cabecera, el director sigue pudiendo todo
    assert prof.patch(f"{base}/config", json={"velocidad": 10}).status_code == 200


def test_la_ventana_en_solo_lectura_puede_salir_y_entrar(api):
    prof = api("prof")
    assert prof.post("/api/auth/logout", headers=SOLO_LECTURA).status_code == 200
    r = prof.post("/api/auth/login", json={"username": "prof", "password": "clave-segura-1"}, headers=SOLO_LECTURA)
    assert r.status_code == 200, r.text


def test_el_director_ordena_desde_la_reparticion_elegida(api):
    prof, base, _, r1, _ = _preparar(api)
    assert prof.patch(f"{base}/config", json={"conduccion_rojo": "instructor"}).status_code == 200
    orden = {"unidad_id": r1["id"], "tipo": "mover", "waypoints": [[0.1, 0.0]]}

    def ordenar(puesto=None):
        cab = {"X-Conduce-Bando": "rojo"}
        if puesto is not None:
            cab["X-Conduce-Puesto"] = puesto
        return prof.post(f"{base}/ordenes", json=orden, headers=cab)

    # A-1 (Personal) no ordena unidades: el servidor aplica las funciones de esa reparticion
    r = ordenar("a1")
    assert r.status_code == 403 and "Personal" in r.json()["detail"]
    assert ordenar("a3").status_code == 200  # Operaciones conduce la maniobra
    assert ordenar().status_code == 200  # sin reparticion: Comandante
    assert ordenar("desconocido").status_code == 200  # una reparticion desconocida cuenta como Comandante
