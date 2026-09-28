"""Copia los datos de una base SQLite del simulador a una base PostgreSQL.

    python -m app.migrar_a_postgres --destino postgresql://usuario:clave@localhost:5432/simulador
    python -m app.migrar_a_postgres --origen sqlite:///C:/ruta/simulador_fenix.db --destino <url> --forzar

Pasos que hace: aplica las migraciones al destino (crea las tablas), comprueba que este vacio
(o, con --forzar, lo vacia), copia todas las tablas respetando las claves foraneas y reajusta las
secuencias de los identificadores para que los registros nuevos no choquen con los copiados.
El origen no se modifica salvo por las migraciones pendientes (las mismas que aplica el servidor).
"""

import argparse
import sys

from sqlalchemy import create_engine, func, insert, select, text

from app import models  # noqa: F401  (registra todos los modelos)
from app.db import DB_PATH, Base, crear_motor, es_sqlite, migrar, normalizar_url

LOTE = 1000


def _contar(con, tablas) -> dict[str, int]:
    return {t.name: con.execute(select(func.count()).select_from(t)).scalar_one() for t in tablas}


def copiar(origen_url: str, destino_url: str, forzar: bool = False) -> dict[str, int]:
    """Devuelve las filas copiadas por tabla."""
    origen_url, destino_url = normalizar_url(origen_url), normalizar_url(destino_url)
    if es_sqlite(destino_url):
        raise ValueError("El destino debe ser PostgreSQL (use SIMULADOR_DB / SQLite para bases locales)")

    migrar(origen_url)  # el origen debe estar en la version actual del esquema
    migrar(destino_url)
    tablas = list(Base.metadata.sorted_tables)  # padres antes que hijos

    origen, destino = crear_motor(origen_url), crear_motor(destino_url)
    try:
        with destino.begin() as dst:
            existentes = {k: v for k, v in _contar(dst, tablas).items() if v}
            if existentes and not forzar:
                raise RuntimeError(
                    f"El destino ya tiene datos ({existentes}). Use --forzar para vaciarlo antes de copiar."
                )
            if existentes:
                dst.execute(text("TRUNCATE " + ", ".join(f'"{t.name}"' for t in tablas) + " RESTART IDENTITY CASCADE"))

            copiadas: dict[str, int] = {}
            with origen.connect() as src:
                for t in tablas:
                    filas = [dict(r) for r in src.execute(select(t)).mappings()]
                    for i in range(0, len(filas), LOTE):
                        dst.execute(insert(t), filas[i:i + LOTE])
                    copiadas[t.name] = len(filas)

            for t in tablas:  # que el siguiente INSERT sin id no reutilice uno copiado
                pk = list(t.primary_key.columns)
                if len(pk) == 1 and pk[0].name == "id":
                    dst.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('\"{t.name}\"', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{t.name}\"), 1), "
                        f"(SELECT MAX(id) FROM \"{t.name}\") IS NOT NULL)"
                    ))
        with destino.connect() as dst:
            despues = _contar(dst, tablas)
        for nombre, n in copiadas.items():
            if despues[nombre] != n:
                raise RuntimeError(f"La tabla {nombre} quedo con {despues[nombre]} filas y se copiaron {n}")
        return copiadas
    finally:
        origen.dispose()
        destino.dispose()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", default=f"sqlite:///{DB_PATH}", help="URL SQLite de origen (por defecto la del servidor)")
    ap.add_argument("--destino", required=True, help="URL PostgreSQL de destino")
    ap.add_argument("--forzar", action="store_true", help="vaciar el destino si ya tiene datos")
    args = ap.parse_args()
    try:
        copiadas = copiar(args.origen, args.destino, args.forzar)
    except (RuntimeError, ValueError) as e:
        print(f"Error: {e}")
        return 1
    for tabla, n in copiadas.items():
        print(f"  {tabla:22s} {n:6d} filas")
    print("Copia terminada. Arranque el servidor con SIMULADOR_DATABASE_URL apuntando al destino.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
