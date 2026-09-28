"""Crea un usuario o restablece su contrasena desde la consola del servidor.

    python -m app.crear_usuario <usuario> --rol instructor
"""

import argparse
import getpass
import sys

from app import auth
from app.db import SessionLocal, init_db
from app.models.usuario import Usuario


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("username")
    ap.add_argument("--rol", choices=auth.ROLES, default="instructor")
    args = ap.parse_args()

    password = getpass.getpass("Contrasena: ")
    if password != getpass.getpass("Repita la contrasena: "):
        print("Las contrasenas no coinciden.")
        return 1
    try:
        auth.validar_password(password)
    except Exception as e:  # HTTPException con el detalle
        print(getattr(e, "detail", e))
        return 1

    init_db()
    username = args.username.strip().lower()
    with SessionLocal() as db:
        usuario = db.query(Usuario).filter(Usuario.username == username).first()
        if usuario:
            usuario.password_hash = auth.hash_password(password)
            usuario.rol = args.rol
            usuario.activo = True
            accion = "actualizado"
        else:
            db.add(Usuario(username=username, password_hash=auth.hash_password(password), rol=args.rol))
            accion = "creado"
        db.commit()
    print(f"Usuario '{username}' {accion} con rol {args.rol}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
