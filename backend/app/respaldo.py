"""Copias de seguridad de la base de datos.

- SQLite: API de backup (consistente aunque el servidor este escribiendo).
- PostgreSQL: `pg_dump` en formato personalizado (requiere tenerlo instalado; se restaura con `pg_restore`).

    python -m app.respaldo [--mantener 14]
"""

import argparse
import asyncio
import logging
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.db import DATABASE_URL, DB_PATH, es_sqlite

# Las copias van junto a la base que respaldan (asi una base alternativa no mezcla las suyas).
RESPALDOS = DB_PATH.parent / "respaldos"
log = logging.getLogger("uvicorn.error")


def _rotar(destino_dir: Path, patron: str, mantener: int) -> None:
    copias = sorted(destino_dir.glob(patron))
    for vieja in copias[: max(0, len(copias) - mantener)]:
        vieja.unlink()


def hacer_respaldo(origen: Path = DB_PATH, destino_dir: Path = RESPALDOS, mantener: int = 14) -> Path | None:
    """Respaldo de una base SQLite."""
    if not Path(origen).exists():
        return None
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"simulador_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    con_origen, con_destino = sqlite3.connect(origen), sqlite3.connect(destino)
    try:
        con_origen.backup(con_destino)
    finally:
        con_destino.close()
        con_origen.close()
    _rotar(destino_dir, "simulador_*.db", mantener)  # solo las `mantener` copias mas recientes
    return destino


def respaldar_postgres(url: str = DATABASE_URL, destino_dir: Path = RESPALDOS, mantener: int = 14) -> Path | None:
    """Respaldo de una base PostgreSQL con pg_dump; None si pg_dump no esta instalado."""
    exe = shutil.which("pg_dump")
    if exe is None:
        log.warning("pg_dump no esta instalado: no se hizo el respaldo de PostgreSQL.")
        return None
    u = make_url(url)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"simulador_pg_{datetime.now():%Y%m%d_%H%M%S_%f}.dump"
    comando = [exe, "-Fc", "-f", str(destino), "-h", u.host or "localhost", "-p", str(u.port or 5432),
               "-U", u.username or "postgres", u.database or "postgres"]
    subprocess.run(comando, check=True, env={**os.environ, "PGPASSWORD": u.password or ""}, capture_output=True)
    _rotar(destino_dir, "simulador_pg_*.dump", mantener)
    return destino


def hacer_respaldo_configurado(mantener: int = 14) -> Path | None:
    """Respalda la base que usa el servidor, sea SQLite o PostgreSQL."""
    if es_sqlite():
        return hacer_respaldo(mantener=mantener)
    return respaldar_postgres(mantener=mantener)


async def respaldar_periodicamente(horas: float, mantener: int = 14) -> None:
    while True:
        await asyncio.sleep(horas * 3600)
        try:
            await asyncio.to_thread(hacer_respaldo_configurado, mantener)
        except Exception:
            log.exception("Fallo el respaldo automatico de la base de datos")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mantener", type=int, default=14)
    args = ap.parse_args()
    destino = hacer_respaldo_configurado(mantener=args.mantener)
    print(f"Respaldo creado: {destino}" if destino else "No se pudo respaldar (no hay base o falta pg_dump).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
