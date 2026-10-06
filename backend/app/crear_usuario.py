"""Crea un usuario o restablece su contrasena desde la consola del servidor.

    python -m app.crear_usuario <usuario> --rol instructor
    python -m app.crear_usuario a5azul --rol azul --puesto planificacion
    echo <contrasena> | python -m app.crear_usuario <usuario> --password-stdin   # sin consola (instalador)
"""

import argparse
import getpass
import sys

from app import auth
from app.db import SessionLocal, init_db
from app.engine import puestos
from app.models.usuario import Usuario


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("username")
    ap.add_argument("--rol", choices=auth.ROLES, default="instructor")
    ap.add_argument("--puesto", choices=list(puestos.PUESTOS), default=puestos.POR_DEFECTO,
                    help="puesto dentro del bando (solo alumnos azul/rojo)")
    ap.add_argument("--password-stdin", action="store_true",
                    help="leer la contrasena de la entrada estandar (una linea) en vez de pedirla por consola")
    args = ap.parse_args()
    puesto = args.puesto if args.rol in puestos.BANDOS else puestos.POR_DEFECTO

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
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
            usuario.puesto = puesto
            usuario.activo = True
            usuario.aprobado = True  # una solicitud pendiente queda aprobada
            usuario.debe_cambiar_clave = False  # quien la pone en la consola ya conoce la contrasena
            accion = "actualizado"
        else:
            db.add(Usuario(username=username, password_hash=auth.hash_password(password), rol=args.rol, puesto=puesto))
            accion = "creado"
        db.commit()
    detalle = f" (puesto {puestos.obtener(puesto).nombre})" if args.rol in puestos.BANDOS else ""
    print(f"Usuario '{username}' {accion} con rol {args.rol}{detalle}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
