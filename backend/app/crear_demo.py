"""Crea un escenario a partir de una plantilla precargada (ver engine/plantillas.py).

    python -m app.crear_demo                       # plantilla por defecto (demo generica)
    python -m app.crear_demo defensa_3_enero_2026   # otra plantilla, por su id

Lo mismo se puede hacer desde la aplicacion (Consola -> Nuevo escenario -> "Desde una plantilla"),
sin pasar por la linea de comandos.
"""

import sys

from app.db import SessionLocal, init_db
from app.engine import plantillas


def main() -> None:
    plantilla_id = sys.argv[1] if len(sys.argv) > 1 else "demo_llanos"
    if plantillas.obtener(plantilla_id) is None:
        disponibles = ", ".join(plantillas.todas())
        raise SystemExit(f"Plantilla desconocida: {plantilla_id!r}. Disponibles: {disponibles}")
    init_db()
    with SessionLocal() as db:
        esc = plantillas.crear_desde_plantilla(db, plantilla_id)
        print(f"Escenario {esc.id} ({esc.nombre!r}) creado desde la plantilla {plantilla_id!r}.")


if __name__ == "__main__":
    main()
