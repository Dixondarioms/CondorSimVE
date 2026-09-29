"""Autenticacion por sesion (cookie HttpOnly) y control de acceso por rol."""

import base64
import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response, WebSocket
from sqlalchemy.orm import Session

from app.db import get_db
from app.engine import puestos
from app.models.asignacion import Asignacion
from app.models.escenario import Escenario
from app.models.usuario import IntentoLogin, Sesion, Usuario, ahora

ROLES = ("instructor", "azul", "rojo", "observador")
COOKIE = "sid"
DURACION_SESION = timedelta(hours=12)
ITERACIONES = 600_000
MIN_PASSWORD = 8

MAX_FALLOS = 5
BLOQUEO_SEGUNDOS = 300


# ---------- Contrasenas ----------
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERACIONES)
    return "pbkdf2_sha256${}${}${}".format(
        ITERACIONES, base64.b64encode(salt).decode(), base64.b64encode(dk).decode()
    )


def verificar_password(password: str, almacenado: str) -> bool:
    try:
        esquema, iters, salt_b64, dk_b64 = almacenado.split("$")
        if esquema != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(iters)
        )
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except Exception:
        return False


_HASH_FALSO = hash_password(secrets.token_urlsafe(16))


def validar_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise HTTPException(
            status_code=400, detail=f"La contrasena debe tener al menos {MIN_PASSWORD} caracteres"
        )


# ---------- Bloqueo por intentos fallidos (persistente en BD) ----------
def _comprobar_bloqueo(db: Session, clave: str) -> None:
    intento = db.get(IntentoLogin, clave)
    if intento is None or intento.fallos < MAX_FALLOS:
        return
    if intento.bloqueado_hasta and ahora() < intento.bloqueado_hasta:
        raise HTTPException(
            status_code=429, detail="Demasiados intentos fallidos. Espere unos minutos."
        )
    db.delete(intento)  # el bloqueo ya vencio
    db.commit()


def _registrar_fallo(db: Session, clave: str) -> None:
    intento = db.get(IntentoLogin, clave)
    if intento is None:
        intento = IntentoLogin(clave=clave, fallos=0)
        db.add(intento)
    intento.fallos += 1
    intento.bloqueado_hasta = ahora() + timedelta(seconds=BLOQUEO_SEGUNDOS)
    db.commit()


def autenticar(db: Session, username: str, password: str) -> Usuario:
    clave = username.strip().lower()[:50]
    _comprobar_bloqueo(db, clave)
    usuario = db.query(Usuario).filter(Usuario.username == clave).first()
    # Se verifica siempre un hash para no revelar por tiempo si el usuario existe.
    valido = verificar_password(password, usuario.password_hash if usuario else _HASH_FALSO)
    if not usuario or not valido or not usuario.activo:
        _registrar_fallo(db, clave)
        raise HTTPException(status_code=401, detail="Usuario o contrasena incorrectos")
    intento = db.get(IntentoLogin, clave)
    if intento is not None:
        db.delete(intento)
        db.commit()
    return usuario


# ---------- Sesiones ----------
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def crear_sesion(db: Session, usuario: Usuario, response: Response, secure: bool = False) -> None:
    db.query(Sesion).filter(Sesion.expira_en < ahora()).delete()
    token = secrets.token_urlsafe(32)
    db.add(
        Sesion(
            token_hash=_hash_token(token),
            usuario_id=usuario.id,
            expira_en=ahora() + DURACION_SESION,
        )
    )
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(DURACION_SESION.total_seconds()),
        httponly=True,
        samesite="strict",
        secure=secure or os.environ.get("SIMULADOR_COOKIE_SECURE") == "1",
        path="/",
    )


def cerrar_sesion(db: Session, token: str | None, response: Response) -> None:
    if token:
        db.query(Sesion).filter(Sesion.token_hash == _hash_token(token)).delete()
        db.commit()
    response.delete_cookie(COOKIE, path="/")


def revocar_sesiones(db: Session, usuario_id: int) -> None:
    db.query(Sesion).filter(Sesion.usuario_id == usuario_id).delete()
    db.commit()


def usuario_desde_token(db: Session, token: str | None) -> Usuario | None:
    if not token:
        return None
    sesion = db.get(Sesion, _hash_token(token))
    if sesion is None or sesion.expira_en < ahora():
        return None
    usuario = db.get(Usuario, sesion.usuario_id)
    if usuario is None or not usuario.activo:
        return None
    return usuario


# ---------- Dependencias FastAPI ----------
def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario = usuario_desde_token(db, request.cookies.get(COOKIE))
    if usuario is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return usuario


def requiere_roles(*roles: str):
    def dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status_code=403, detail="No autorizado para esta accion")
        return usuario

    return dependencia


def exigir_funcion(usuario: Usuario, funcion: str) -> None:
    """403 si el puesto del alumno dentro de su bando no tiene esa funcion (ver engine/puestos.py)."""
    if puestos.puede(usuario.puesto, funcion):
        return
    quien = " o ".join(f"{p.nombre} ({p.sigla})" for p in puestos.responsables(funcion)) or "el Estado Mayor"
    raise HTTPException(
        status_code=403,
        detail=f"Esa accion corresponde al puesto {quien} de su bando; usted ocupa {puestos.obtener(usuario.puesto).nombre}",
    )


def usuario_ws(websocket: WebSocket, db: Session) -> Usuario | None:
    """Autentica un WebSocket. Rechaza origenes distintos al host (CSWSH)."""
    origen = websocket.headers.get("origin")
    if origen:
        host = websocket.headers.get("host", "")
        if origen.split("://", 1)[-1] != host:
            return None
    return usuario_desde_token(db, websocket.cookies.get(COOKIE))


# ---------- Acceso a escenarios ----------
def escenario_accesible(db: Session, escenario_id: int, usuario: Usuario) -> Escenario:
    """Escenario si existe y el usuario tiene acceso; si no, 404 (no revela su existencia)."""
    escenario = db.get(Escenario, escenario_id)
    if escenario is None:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    if usuario.rol != "instructor" and db.get(Asignacion, (usuario.id, escenario_id)) is None:
        raise HTTPException(status_code=404, detail="Escenario no encontrado")
    return escenario


def escenario_dep(
    escenario_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_actual)
) -> Escenario:
    return escenario_accesible(db, escenario_id, usuario)
