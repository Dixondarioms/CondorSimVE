from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app import auth, schemas
from app.db import get_db
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
