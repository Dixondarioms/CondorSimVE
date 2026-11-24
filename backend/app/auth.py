"""Autenticacion por sesion (cookie HttpOnly) y control de acceso por rol."""

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
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

# Cuenta del administrador que se crea sola en una base sin usuarios; la contrasena inicial es conocida
# (manual y README) y por eso se exige cambiarla al primer acceso.
ADMIN_INICIAL = "admin"
CLAVE_INICIAL = "siete1234"
MAX_SOLICITUDES_PENDIENTES = 50
# Lo unico que puede hacer quien debe cambiar la contrasena (ademas de cerrar la sesion)
RUTAS_CON_CLAVE_VENCIDA = ("/api/auth/yo", "/api/auth/cambiar-clave")


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
    # Solo se revela que la solicitud esta pendiente a quien conoce la contrasena.
    if not usuario.aprobado:
        raise HTTPException(
            status_code=403, detail="Su solicitud de cuenta aun no fue aprobada por el instructor. Intente mas tarde."
        )
    return usuario


def cambiar_clave(db: Session, usuario: Usuario, actual: str, nueva: str) -> None:
    if not verificar_password(actual, usuario.password_hash):
        raise HTTPException(status_code=400, detail="La contrasena actual no es correcta")
    validar_password(nueva)
    if nueva == actual:
        raise HTTPException(status_code=400, detail="La contrasena nueva debe ser distinta de la actual")
    usuario.password_hash = hash_password(nueva)
    usuario.debe_cambiar_clave = False
    db.commit()


def restablecer_admin(db: Session) -> Usuario:
    """Deja la cuenta `admin` como instructor activo con la contrasena inicial y obligacion de cambiarla
    (la crea si no existe). Para la primera puesta en marcha y para recuperar el acceso desde la consola."""
    usuario = db.query(Usuario).filter(Usuario.username == ADMIN_INICIAL).first()
    if usuario is None:
        usuario = Usuario(username=ADMIN_INICIAL, password_hash="", rol="instructor")
        db.add(usuario)
    usuario.password_hash = hash_password(CLAVE_INICIAL)
    usuario.rol = "instructor"
    usuario.puesto = puestos.POR_DEFECTO
    usuario.activo = True
    usuario.aprobado = True
    usuario.debe_cambiar_clave = True
    db.commit()
    db.refresh(usuario)
    db.query(IntentoLogin).filter(IntentoLogin.clave == ADMIN_INICIAL).delete()
    db.query(Sesion).filter(Sesion.usuario_id == usuario.id).delete()
    db.commit()
    return usuario


def crear_admin_si_no_hay_usuarios(db: Session) -> Usuario | None:
    if db.query(Usuario).count():
        return None
    return restablecer_admin(db)


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


def revocar_sesiones(db: Session, usuario_id: int, salvo_token: str | None = None) -> None:
    """Cierra las sesiones del usuario (todas, o todas salvo la del token indicado)."""
    consulta = db.query(Sesion).filter(Sesion.usuario_id == usuario_id)
    if salvo_token:
        consulta = consulta.filter(Sesion.token_hash != _hash_token(salvo_token))
    consulta.delete()
    db.commit()


def usuario_desde_token(db: Session, token: str | None) -> Usuario | None:
    if not token:
        return None
    sesion = db.get(Sesion, _hash_token(token))
    if sesion is None or sesion.expira_en < ahora():
        return None
    usuario = db.get(Usuario, sesion.usuario_id)
    if usuario is None or not usuario.activo or not usuario.aprobado:
        return None
    return usuario


# ---------- Dependencias FastAPI ----------
def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    usuario = usuario_desde_token(db, request.cookies.get(COOKIE))
    if usuario is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    if usuario.debe_cambiar_clave and request.url.path not in RUTAS_CON_CLAVE_VENCIDA:
        raise HTTPException(status_code=403, detail="Debe cambiar su contrasena antes de continuar")
    return usuario


def requiere_roles(*roles: str):
    def dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status_code=403, detail="No autorizado para esta accion")
        return usuario

    return dependencia


CABECERA_CONDUCE = "X-Conduce-Bando"
# La reparticion desde la que conduce (ventana de pantallas del director): sin ella es el Comandante.
CABECERA_PUESTO = "X-Conduce-Puesto"
# Ventana del director abierta en solo lectura (pantalla de una reparticion): no escribe nada.
CABECERA_SOLO_LECTURA = "X-Solo-Lectura"


@dataclass(frozen=True)
class InstructorConductor:
    """El instructor dando ordenes por un bando que el escenario le encarga conducir (conduccion "instructor").

    Se comporta como un alumno de ese bando en la reparticion `puesto` (Comandante por defecto, o la que pide la
    cabecera X-Conduce-Puesto: asi la PC del director puede operar como cualquier reparticion). El resto del codigo
    usa `rol`, `puesto`, `id` y `username` igual que con un alumno."""

    id: int
    username: str
    rol: str
    puesto: str = puestos.POR_DEFECTO
    instructor: bool = True


def conductor(escenario_id: int, request: Request, db: Session = Depends(get_db),
              usuario: Usuario = Depends(usuario_actual)):
    """Quien da ordenes por un bando: el alumno, por el suyo, o el instructor, por el bando que indica en la cabecera
    X-Conduce-Bando cuando el escenario se lo encarga (y desde la reparticion que fija X-Conduce-Puesto)."""
    if usuario.rol in puestos.BANDOS:
        return usuario
    bando = request.headers.get(CABECERA_CONDUCE, "")
    if usuario.rol == "instructor" and bando in puestos.BANDOS:
        esc = db.get(Escenario, escenario_id)
        if esc is not None and esc.conduccion(bando) == "instructor":
            return InstructorConductor(id=usuario.id, username=usuario.username, rol=bando,
                                       puesto=puestos.normalizar(request.headers.get(CABECERA_PUESTO)))
        raise HTTPException(status_code=403, detail=f"El bando {bando} no esta a cargo del instructor en este escenario")
    raise HTTPException(status_code=403, detail="No autorizado para esta accion")


def exigir_funcion(usuario: Usuario, funcion: str) -> None:
    """403 si la reparticion del alumno dentro de su bando no tiene esa funcion (ver engine/puestos.py)."""
    if puestos.puede(usuario.puesto, funcion):
        return
    quien = " o ".join(f"{p.nombre} ({p.sigla})" for p in puestos.responsables(funcion)) or "el Comandante"
    raise HTTPException(
        status_code=403,
        detail=f"Esa accion corresponde a la reparticion {quien} de su bando; usted ocupa {puestos.obtener(usuario.puesto).nombre}",
    )


def usuario_ws(websocket: WebSocket, db: Session) -> Usuario | None:
    """Autentica un WebSocket. Rechaza origenes distintos al host (CSWSH)."""
    origen = websocket.headers.get("origin")
    if origen:
        host = websocket.headers.get("host", "")
        if origen.split("://", 1)[-1] != host:
            return None
    usuario = usuario_desde_token(db, websocket.cookies.get(COOKIE))
    if usuario is not None and usuario.debe_cambiar_clave:
        return None
    return usuario


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
