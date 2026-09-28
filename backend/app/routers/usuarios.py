from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth, schemas
from app.db import get_db
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
        username=username, password_hash=auth.hash_password(payload.password), rol=payload.rol
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
        pierde_acceso = True
    if payload.rol is not None and payload.rol != usuario.rol:
        usuario.rol = payload.rol
        pierde_acceso = True
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
