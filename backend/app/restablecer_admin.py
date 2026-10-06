"""Restablece la cuenta del administrador (`admin`) con la contrasena inicial, desde la consola del servidor.

    python -m app.restablecer_admin                       # recuperar el acceso (crea `admin` si no existe)
    python -m app.restablecer_admin --si-no-hay-usuarios  # solo en una base vacia (lo usa el instalador)

`admin` queda como instructor activo y debe cambiar la contrasena al entrar. No toca a los demas usuarios.
"""

import argparse
import sys

from app import auth
from app.db import SessionLocal, init_db


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--si-no-hay-usuarios", action="store_true", help="no hacer nada si la base ya tiene usuarios")
    args = ap.parse_args()

    init_db()
    with SessionLocal() as db:
        usuario = auth.crear_admin_si_no_hay_usuarios(db) if args.si_no_hay_usuarios else auth.restablecer_admin(db)
    if usuario is None:
        print("La base ya tiene usuarios: no se cambio nada.")
        return 0
    print(f"Usuario: {auth.ADMIN_INICIAL}   Contrasena inicial: {auth.CLAVE_INICIAL}")
    print("Se pedira cambiar la contrasena al entrar por primera vez.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
