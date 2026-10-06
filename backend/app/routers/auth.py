from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app import auth, schemas
from app.db import get_db
from app.engine import puestos
from app.models.usuario import Usuario

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.UsuarioOut)
def login(payload: schemas.LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    usuario = auth.autenticar(db, payload.username, payload.password)
    auth.crear_sesion(db, usuario, response, secure=request.url.scheme == "https")
    return usuario


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth.cerrar_sesion(db, request.cookies.get(auth.COOKIE), response)
    return {"ok": True}


@router.get("/yo", response_model=schemas.UsuarioOut)
def yo(usuario: Usuario = Depends(auth.usuario_actual)):
    return usuario


@router.post("/cambiar-clave", response_model=schemas.UsuarioOut)
def cambiar_clave(
    payload: schemas.CambioClaveIn,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(auth.usuario_actual),
):
    auth.cambiar_clave(db, usuario, payload.actual, payload.nueva)
    # las demas sesiones abiertas con la contrasena anterior se cierran; esta sigue
    auth.revocar_sesiones(db, usuario.id, salvo_token=request.cookies.get(auth.COOKIE))
    db.refresh(usuario)
    return usuario


@router.post("/solicitar", status_code=201)
def solicitar_cuenta(payload: schemas.SolicitudCuentaIn, db: Session = Depends(get_db)):
    """Solicitud de cuenta desde la pantalla de acceso: queda pendiente hasta que un instructor la apruebe."""
    auth.validar_password(payload.password)
    username = payload.username.lower()
    if db.query(Usuario).filter(Usuario.username == username).first():
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya existe o ya fue solicitado")
    if db.query(Usuario).filter(Usuario.aprobado.is_(False)).count() >= auth.MAX_SOLICITUDES_PENDIENTES:
        raise HTTPException(status_code=429, detail="Hay demasiadas solicitudes pendientes. Avise al instructor.")
    db.add(Usuario(
        username=username, password_hash=auth.hash_password(payload.password), rol=payload.rol,
        puesto=payload.puesto if payload.rol in puestos.BANDOS else puestos.POR_DEFECTO, aprobado=False,
    ))
    db.commit()
    return {"ok": True, "detalle": "Solicitud enviada. Podra ingresar cuando el instructor la apruebe."}
