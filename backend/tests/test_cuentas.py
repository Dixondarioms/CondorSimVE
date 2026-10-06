"""Solicitudes de cuenta con aprobacion del instructor, administrador inicial y cambio de contrasena obligatorio."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app import auth
from app.main import app
from app.models.usuario import Usuario

CLAVE = "clave-segura-1"


def _login(c: TestClient, nombre: str, clave: str):
    return c.post("/api/auth/login", json={"username": nombre, "password": clave})


def _usuario(api, nombre: str) -> Usuario:
    with sessionmaker(bind=api.engine)() as db:
        return db.query(Usuario).filter(Usuario.username == nombre).first()


# ---------------------------------------------------------------- solicitudes desde la pantalla de acceso
def test_solicitud_queda_pendiente_y_no_permite_entrar(api):
    anon = api()
    r = anon.post("/api/auth/solicitar", json={"username": "Delta", "password": "otra-clave-9", "rol": "azul", "puesto": "logistica"})
    assert r.status_code == 201, r.text
    u = _usuario(api, "delta")
    assert u.aprobado is False and u.rol == "azul" and u.puesto == "logistica"

    r = _login(api(), "delta", "otra-clave-9")
    assert r.status_code == 403 and "aprobada" in r.json()["detail"]
    # con la contrasena equivocada no se revela que la solicitud existe
    r = _login(api(), "delta", "equivocada-1")
    assert r.status_code == 401


def test_solicitud_valida_nombre_repetido_y_contrasena_corta(api):
    anon = api()
    assert anon.post("/api/auth/solicitar", json={"username": "alfa", "password": "otra-clave-9", "rol": "azul"}).status_code == 409
    assert anon.post("/api/auth/solicitar", json={"username": "nuevo", "password": "corta", "rol": "rojo"}).status_code == 400
    assert anon.post("/api/auth/solicitar", json={"username": "n o", "password": "otra-clave-9", "rol": "rojo"}).status_code == 422


def test_tope_de_solicitudes_pendientes(api, monkeypatch):
    monkeypatch.setattr(auth, "MAX_SOLICITUDES_PENDIENTES", 2)
    anon = api()
    for n in ("uno", "dos"):
        assert anon.post("/api/auth/solicitar", json={"username": n, "password": "otra-clave-9", "rol": "observador"}).status_code == 201
    assert anon.post("/api/auth/solicitar", json={"username": "tres", "password": "otra-clave-9", "rol": "observador"}).status_code == 429


def test_el_instructor_aprueba_con_otro_rol_y_el_alumno_entra(api):
    api().post("/api/auth/solicitar", json={"username": "eco", "password": "otra-clave-9", "rol": "instructor"})
    prof = api("prof")
    pendiente = next(u for u in prof.get("/api/usuarios").json() if u["username"] == "eco")
    assert pendiente["aprobado"] is False

    r = prof.post(f"/api/usuarios/{pendiente['id']}/aprobar", json={"rol": "rojo", "puesto": "planificacion"})
    assert r.status_code == 200, r.text
    assert r.json()["aprobado"] is True and r.json()["rol"] == "rojo" and r.json()["puesto"] == "planificacion"

    c = api()
    assert _login(c, "eco", "otra-clave-9").status_code == 200
    # eligio su propia contrasena: no se le pide cambiarla
    assert c.get("/api/auth/yo").json()["debe_cambiar_clave"] is False
    assert c.get("/api/escenarios").status_code == 200


def test_rechazar_borra_la_solicitud_y_libera_el_nombre(api):
    anon = api()
    anon.post("/api/auth/solicitar", json={"username": "foxtrot", "password": "otra-clave-9", "rol": "azul"})
    prof = api("prof")
    uid = _usuario(api, "foxtrot").id
    assert prof.delete(f"/api/usuarios/{uid}/solicitud").status_code == 200
    assert _usuario(api, "foxtrot") is None
    assert anon.post("/api/auth/solicitar", json={"username": "foxtrot", "password": "otra-clave-9", "rol": "azul"}).status_code == 201


def test_solo_el_instructor_aprueba_y_no_se_reaprueba_una_cuenta(api):
    api().post("/api/auth/solicitar", json={"username": "golf", "password": "otra-clave-9", "rol": "azul"})
    uid = _usuario(api, "golf").id
    assert api("alfa").post(f"/api/usuarios/{uid}/aprobar").status_code == 403
    assert api("alfa").delete(f"/api/usuarios/{uid}/solicitud").status_code == 403
    prof = api("prof")
    assert prof.post(f"/api/usuarios/{uid}/aprobar").status_code == 200
    # una cuenta ya aprobada no es una solicitud: ni se reaprueba ni se borra por esta via
    assert prof.post(f"/api/usuarios/{uid}/aprobar").status_code == 404
    assert prof.delete(f"/api/usuarios/{uid}/solicitud").status_code == 404


# ---------------------------------------------------------------- administrador inicial y cambio obligatorio
def test_base_vacia_crea_el_admin_con_contrasena_inicial(db_session):
    usuario = auth.crear_admin_si_no_hay_usuarios(db_session)
    assert usuario.username == auth.ADMIN_INICIAL and usuario.rol == "instructor"
    assert usuario.debe_cambiar_clave is True
    assert auth.verificar_password(auth.CLAVE_INICIAL, usuario.password_hash)
    # con usuarios ya no se crea nada
    assert auth.crear_admin_si_no_hay_usuarios(db_session) is None


def test_admin_inicial_debe_cambiar_la_contrasena_antes_de_usar_el_simulador(api):
    with sessionmaker(bind=api.engine)() as db:
        auth.restablecer_admin(db)
    c = api()
    r = _login(c, auth.ADMIN_INICIAL, auth.CLAVE_INICIAL)
    assert r.status_code == 200 and r.json()["debe_cambiar_clave"] is True
    # todo lo demas queda bloqueado hasta cambiarla
    assert c.get("/api/escenarios").status_code == 403
    assert c.get("/api/usuarios").status_code == 403
    assert c.get("/api/auth/yo").status_code == 200
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws/1"):
            pass

    assert c.post("/api/auth/cambiar-clave", json={"actual": "mala-clave-1", "nueva": "nueva-clave-1"}).status_code == 400
    assert c.post("/api/auth/cambiar-clave", json={"actual": auth.CLAVE_INICIAL, "nueva": auth.CLAVE_INICIAL}).status_code == 400
    assert c.post("/api/auth/cambiar-clave", json={"actual": auth.CLAVE_INICIAL, "nueva": "corta"}).status_code == 400
    r = c.post("/api/auth/cambiar-clave", json={"actual": auth.CLAVE_INICIAL, "nueva": "nueva-clave-1"})
    assert r.status_code == 200 and r.json()["debe_cambiar_clave"] is False
    # la sesion sigue abierta y ya puede trabajar; la contrasena inicial deja de servir
    assert c.get("/api/escenarios").status_code == 200
    assert _login(api(), auth.ADMIN_INICIAL, auth.CLAVE_INICIAL).status_code == 401
    assert _login(api(), auth.ADMIN_INICIAL, "nueva-clave-1").status_code == 200


def test_cambiar_la_contrasena_cierra_las_otras_sesiones(api):
    otra = api("alfa")
    c = api("alfa")
    assert c.post("/api/auth/cambiar-clave", json={"actual": CLAVE, "nueva": "nueva-clave-1"}).status_code == 200
    assert c.get("/api/auth/yo").status_code == 200
    assert otra.get("/api/auth/yo").status_code == 401


def test_restablecer_admin_recupera_el_acceso(api):
    with sessionmaker(bind=api.engine)() as db:
        admin = auth.restablecer_admin(db)
        admin.password_hash = auth.hash_password("perdida-1234")
        admin.debe_cambiar_clave = False
        admin.activo = False
        db.commit()
        auth.restablecer_admin(db)
    r = _login(api(), auth.ADMIN_INICIAL, auth.CLAVE_INICIAL)
    assert r.status_code == 200 and r.json()["debe_cambiar_clave"] is True


def test_contrasena_puesta_por_el_instructor_se_cambia_al_entrar(api):
    prof = api("prof")
    r = prof.post("/api/usuarios", json={"username": "hotel", "password": "puesta-1234", "rol": "azul"})
    assert r.status_code == 200 and r.json()["debe_cambiar_clave"] is True
    c = api()
    assert _login(c, "hotel", "puesta-1234").json()["debe_cambiar_clave"] is True
    assert c.get("/api/escenarios").status_code == 403

    # el olvido de contrasena: el instructor pone una nueva y el alumno la cambia al entrar
    uid = _usuario(api, "alfa").id
    assert prof.patch(f"/api/usuarios/{uid}", json={"password": "temporal-123"}).json()["debe_cambiar_clave"] is True
    # su propia contrasena, cambiada desde el panel, no le obliga a nada
    yo = _usuario(api, "prof").id
    assert prof.patch(f"/api/usuarios/{yo}", json={"password": "propia-12345"}).json()["debe_cambiar_clave"] is False


def test_el_arranque_del_servidor_crea_el_admin_en_una_base_vacia(api, monkeypatch):
    """El lifespan de la aplicacion llama a crear_admin_si_no_hay_usuarios con la base configurada."""
    from app import main

    Session = sessionmaker(bind=api.engine)
    with Session() as db:
        db.query(Usuario).delete()
        db.commit()
    async def sin_vigilancia():
        return None

    # solo se ejecuta la creacion del admin: ni migraciones, ni terreno real, ni respaldos, ni la base del aula
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "get_terreno", lambda: type("T", (), {"disponible": True})())
    monkeypatch.setattr(main.turnos, "vigilar_plazos", sin_vigilancia)
    monkeypatch.setenv("SIMULADOR_RESPALDO_HORAS", "0")
    with TestClient(app):
        pass
    assert _usuario(api, auth.ADMIN_INICIAL).debe_cambiar_clave is True
