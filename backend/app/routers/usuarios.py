from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas
from app.db import get_db
from app.engine import puestos
from app.models.usuario import Usuario
from app.ws_manager import manager

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])
solo_instructor = auth.requiere_roles("instructor")


@router.get("", response_model=list[schemas.UsuarioOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    return db.query(Usuario).order_by(Usuario.username).all()


@router.post("", response_model=schemas.UsuarioOut)
def crear(
    payload: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_instructor),
):
    auth.validar_password(payload.password)
    username = payload.username.lower()
    if db.query(Usuario).filter(Usuario.username == username).first():
        raise HTTPException(status_code=409, detail="El usuario ya existe")
    usuario = Usuario(
        username=username, password_hash=auth.hash_password(payload.password), rol=payload.rol,
        # el puesto solo tiene sentido dentro de un bando
        puesto=payload.puesto if payload.rol in puestos.BANDOS else puestos.POR_DEFECTO,
        # la contrasena la eligio el instructor: el usuario la cambia al entrar por primera vez
        debe_cambiar_clave=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch("/{usuario_id}", response_model=schemas.UsuarioOut)
async def actualizar(
    usuario_id: int,
    payload: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    actual: Usuario = Depends(solo_instructor),
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    pierde_acceso = False
    if payload.password is not None:
        auth.validar_password(payload.password)
        usuario.password_hash = auth.hash_password(payload.password)
        # contrasena puesta por el instructor (olvido, alta): el usuario la cambia al volver a entrar
        usuario.debe_cambiar_clave = usuario.id != actual.id
        pierde_acceso = True
    if payload.rol is not None and payload.rol != usuario.rol:
        usuario.rol = payload.rol
        pierde_acceso = True
    if payload.puesto is not None and payload.puesto != usuario.puesto:
        usuario.puesto = payload.puesto
        pierde_acceso = True  # la interfaz y los permisos cambian: que vuelva a entrar
    if usuario.rol not in puestos.BANDOS:
        usuario.puesto = puestos.POR_DEFECTO
    if payload.activo is not None and payload.activo != usuario.activo:
        usuario.activo = payload.activo
        pierde_acceso = True

    # Nunca dejar el sistema sin un instructor activo.
    if usuario.id == actual.id and (usuario.rol != "instructor" or not usuario.activo):
        db.rollback()
        raise HTTPException(
            status_code=400, detail="No puede quitarse a si mismo el rol de instructor ni desactivarse"
        )

    db.commit()
    if pierde_acceso and usuario.id != actual.id:
        auth.revocar_sesiones(db, usuario.id)
        await manager.expulsar(usuario.id)
    db.refresh(usuario)
    return usuario


def _solicitud(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or usuario.aprobado:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return usuario


@router.post("/{usuario_id}/aprobar", response_model=schemas.UsuarioOut)
def aprobar(
    usuario_id: int,
    payload: schemas.AprobacionIn | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(solo_instructor),
):
    """Aprueba una solicitud de cuenta, con el rol y el puesto pedidos o los que decida el instructor."""
    usuario = _solicitud(db, usuario_id)
    if payload is not None and payload.rol is not None:
        usuario.rol = payload.rol
    if payload is not None and payload.puesto is not None:
        usuario.puesto = payload.puesto
    if usuario.rol not in puestos.BANDOS:
        usuario.puesto = puestos.POR_DEFECTO
    usuario.aprobado = True
    usuario.activo = True
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}/solicitud")
def rechazar(usuario_id: int, db: Session = Depends(get_db), _: Usuario = Depends(solo_instructor)):
    """Rechaza (borra) una solicitud pendiente; el nombre de usuario queda libre."""
    db.delete(_solicitud(db, usuario_id))
    db.commit()
    return {"ok": True}
