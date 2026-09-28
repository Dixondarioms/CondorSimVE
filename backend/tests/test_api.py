"""Pruebas de la API: autenticacion, roles y niebla de guerra."""

from app import auth


def _preparar(api):
    """Escenario con: azul A (0,0), rojo R1 cerca (5 km), rojo R2 lejos (200 km)."""
    prof = api("prof")
    esc = prof.post("/api/escenarios", json={"nombre": "Prueba"}).json()
    base = f"/api/escenarios/{esc['id']}"

    def unidad(nombre, bando, lat, lon, tipo="terrestre", **kw):
        r = prof.post(f"{base}/unidades", json=dict(nombre=nombre, bando=bando, tipo=tipo, lat=lat, lon=lon, **kw))
        assert r.status_code == 200, r.text
        return r.json()

    ids = [u["id"] for u in prof.get("/api/usuarios").json() if u["rol"] != "instructor"]
    assert prof.put(f"{base}/usuarios", json={"usuario_ids": ids}).status_code == 200
    a = unidad("A", "azul", 0.0, 0.0, alcance_km=50, deteccion_km=10)
    r1 = unidad("R1", "rojo", 0.045, 0.0, alcance_km=50, deteccion_km=10)
    r2 = unidad("R2", "rojo", 1.8, 0.0, deteccion_km=10)
    return prof, base, a, r1, r2


# ---------- autenticacion ----------
def test_endpoints_protegidos_sin_sesion(api):
    c = api()
    assert c.get("/api/escenarios").status_code == 401
    assert c.get("/api/usuarios").status_code == 401
    assert c.post("/api/escenarios", json={"nombre": "x"}).status_code == 401


def test_login_incorrecto_y_bloqueo_por_intentos(api):
    c = api()
    for _ in range(auth.MAX_FALLOS):
        assert c.post("/api/auth/login", json={"username": "alfa", "password": "mala"}).status_code == 401
    r = c.post("/api/auth/login", json={"username": "alfa", "password": "clave-segura-1"})
    assert r.status_code == 429


def test_login_correcto_fija_cookie_httponly_y_logout_invalida(api):
    c = api()
    r = c.post("/api/auth/login", json={"username": "ALFA", "password": "clave-segura-1"})
    assert r.status_code == 200 and r.json()["rol"] == "azul"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert c.get("/api/auth/yo").json()["username"] == "alfa"
    c.post("/api/auth/logout")
    assert c.get("/api/auth/yo").status_code == 401


def test_contrasena_guardada_con_hash(db_session):
    h = auth.hash_password("clave-segura-1")
    assert "clave-segura-1" not in h
    assert auth.verificar_password("clave-segura-1", h)
    assert not auth.verificar_password("otra", h)


def test_gestion_de_usuarios_solo_instructor(api):
    assert api("alfa").get("/api/usuarios").status_code == 403
    prof = api("prof")
    r = prof.post("/api/usuarios", json={"username": "nuevo", "password": "corta", "rol": "azul"})
    assert r.status_code == 400  # contrasena corta
    r = prof.post("/api/usuarios", json={"username": "nuevo", "password": "clave-larga-2", "rol": "azul"})
    assert r.status_code == 200
    assert prof.post("/api/usuarios", json={"username": "nuevo", "password": "clave-larga-2", "rol": "azul"}).status_code == 409
    r = api().post("/api/auth/login", json={"username": "nuevo", "password": "clave-larga-2"})
    assert r.status_code == 200 and r.json()["rol"] == "azul"


def test_desactivar_usuario_revoca_su_sesion(api):
    alumno = api("alfa")
    assert alumno.get("/api/escenarios").status_code == 200
    prof = api("prof")
    uid = next(u["id"] for u in prof.get("/api/usuarios").json() if u["username"] == "alfa")
    assert prof.patch(f"/api/usuarios/{uid}", json={"activo": False}).status_code == 200
    assert alumno.get("/api/escenarios").status_code == 401
    assert api().post("/api/auth/login", json={"username": "alfa", "password": "clave-segura-1"}).status_code == 401


def test_instructor_no_puede_quitarse_su_propio_rol(api):
    prof = api("prof")
    uid = prof.get("/api/auth/yo").json()["id"]
    assert prof.patch(f"/api/usuarios/{uid}", json={"rol": "azul"}).status_code == 400
    assert prof.get("/api/auth/yo").json()["rol"] == "instructor"


# ---------- roles ----------
def test_alumnos_y_observador_no_pueden_administrar(api):
    prof, base, a, r1, r2 = _preparar(api)
    for nombre in ("alfa", "bravo", "obs"):
        c = api(nombre)
        assert c.post("/api/escenarios", json={"nombre": "x"}).status_code == 403
        assert c.post(f"{base}/avanzar_turno").status_code == 403
        assert c.post(f"{base}/pausar").status_code == 403
        assert c.post(f"{base}/eventos", json={"descripcion": "x"}).status_code == 403
        assert c.post(f"{base}/unidades", json=dict(nombre="x", bando="azul", tipo="terrestre", lat=0, lon=0)).status_code == 403
        assert c.patch(f"{base}/unidades/{a['id']}", json={"fuerza": 1}).status_code == 403


def test_observador_no_emite_ordenes(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = api("obs").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]})
    assert r.status_code == 403


def test_alumno_solo_ordena_a_sus_unidades(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul, rojo = api("alfa"), api("bravo")
    orden = {"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]}
    assert azul.post(f"{base}/ordenes", json=orden).status_code == 200
    assert rojo.post(f"{base}/ordenes", json=orden).status_code == 404


def test_nueva_orden_reemplaza_a_la_pendiente(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    for lat in (0.1, 0.2):
        azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[lat, 0]]})
    assert len(azul.get(f"{base}/ordenes").json()) == 1


def test_validacion_de_entradas(api):
    prof, base, a, r1, r2 = _preparar(api)
    r = prof.post(f"{base}/unidades", json=dict(nombre="x", bando="verde", tipo="terrestre", lat=0, lon=0))
    assert r.status_code == 422
    r = prof.post(f"{base}/unidades", json=dict(nombre="x", bando="azul", tipo="terrestre", lat=95, lon=0))
    assert r.status_code == 422
    assert prof.patch(f"{base}/unidades/{a['id']}", json={"fuerza": 500}).status_code == 422
    r = api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[200, 0]]})
    assert r.status_code == 400


# ---------- niebla de guerra ----------
def test_niebla_de_guerra_en_la_api(api):
    prof, base, a, r1, r2 = _preparar(api)
    visto = {u["nombre"]: u for u in api("alfa").get(f"{base}/unidades").json()}
    assert set(visto) == {"A", "R1"}  # R2 esta a 200 km: oculto
    assert visto["A"]["fuerza"] == 100
    assert visto["R1"]["fuerza"] is None  # de enemigos solo se ve lo observable

    rojo = {u["nombre"]: u for u in api("bravo").get(f"{base}/unidades").json()}
    assert set(rojo) == {"A", "R1", "R2"}  # propias + A (detectada por R1)
    assert rojo["A"]["fuerza"] is None and rojo["R2"]["fuerza"] == 100
    assert {u["nombre"] for u in prof.get(f"{base}/unidades").json()} == {"A", "R1", "R2"}
    assert {u["nombre"] for u in api("obs").get(f"{base}/unidades").json()} == {"A", "R1", "R2"}
    estado = api("alfa").get(base).json()
    assert {u["nombre"] for u in estado["unidades"]} == {"A", "R1"}


def test_no_se_puede_atacar_una_unidad_no_detectada(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    assert azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r2["id"]}).status_code == 404
    assert azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]}).status_code == 200


def test_ordenes_y_eventos_se_filtran_por_bando(api):
    prof, base, a, r1, r2 = _preparar(api)
    api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]})
    assert api("bravo").get(f"{base}/ordenes").json() == []
    assert len(prof.get(f"{base}/ordenes").json()) == 1

    prof.post(f"{base}/eventos", json={"descripcion": "solo azul", "bando_destino": "azul"})
    prof.post(f"{base}/eventos", json={"descripcion": "para todos"})
    desc = lambda c: {e["descripcion"] for e in c.get(base).json()["eventos"]}
    assert desc(api("alfa")) == {"solo azul", "para todos"}
    assert desc(api("bravo")) == {"para todos"}
    assert desc(prof) == {"solo azul", "para todos"}


def test_turno_completo_con_combate_y_niebla(api):
    prof, base, a, r1, r2 = _preparar(api)
    azul = api("alfa")
    azul.post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "atacar", "objetivo_unidad_id": r1["id"]})
    assert prof.post(f"{base}/avanzar_turno").status_code == 200
    vista = {u["nombre"]: u for u in prof.get(f"{base}/unidades").json()}
    assert vista["R1"]["fuerza"] < 100 and vista["A"]["fuerza"] < 100
    resultado = azul.get(f"{base}/ordenes").json()[0]
    assert resultado["estado"] == "resuelta" and "Ratio" in resultado["resultado"]


def test_ordenes_bloqueadas_si_el_escenario_esta_pausado(api):
    prof, base, a, r1, r2 = _preparar(api)
    prof.post(f"{base}/pausar")
    r = api("alfa").post(f"{base}/ordenes", json={"unidad_id": a["id"], "tipo": "mover", "waypoints": [[0.1, 0]]})
    assert r.status_code == 400


# ---------- websocket ----------
def test_websocket_requiere_sesion(api):
    prof, base, a, r1, r2 = _preparar(api)
    esc_id = base.rsplit("/", 1)[1]
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with api().websocket_connect(f"/ws/{esc_id}") as ws:
            ws.receive_json()


def test_websocket_envia_estado_filtrado_por_rol(api):
    prof, base, a, r1, r2 = _preparar(api)
    esc_id = base.rsplit("/", 1)[1]
    with api("alfa").websocket_connect(f"/ws/{esc_id}") as ws:
        estado = ws.receive_json()
        assert {u["nombre"] for u in estado["unidades"]} == {"A", "R1"}
        assert estado["vista"] == "azul"
    with prof.websocket_connect(f"/ws/{esc_id}") as ws:
        estado = ws.receive_json()
        assert {u["nombre"] for u in estado["unidades"]} == {"A", "R1", "R2"}


def test_websocket_rechaza_origen_ajeno(api):
    prof, base, a, r1, r2 = _preparar(api)
    esc_id = base.rsplit("/", 1)[1]
    import pytest
    from starlette.websockets import WebSocketDisconnect

    c = api("alfa")
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect(f"/ws/{esc_id}", headers={"origin": "http://sitio-malicioso.example"}) as ws:
            ws.receive_json()
