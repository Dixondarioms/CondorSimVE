"""Arma el paquete del Cóndor para una tablet Android (Termux): dist/Condor_Android.zip.

Lleva todo lo que el servidor necesita para funcionar solo en la tablet, sin la PC ni internet: el programa
(backend/app y sus migraciones), las plantillas y operaciones históricas, el terreno, los mapas (callejero, satélite y
capas geo), las fotos y la pantalla, más el instalador de android/. No lleva el entorno de Python de la PC (venv), los
respaldos ni archivos de pruebas.

    backend\\venv\\Scripts\\python tools/empaquetar_android.py              # con una COPIA de la base de esta PC
    backend\\venv\\Scripts\\python tools/empaquetar_android.py --sin-base   # la tablet empieza con una base nueva

La base se copia con la API de respaldo de SQLite (sirve aunque el Cóndor esté abierto): la tablet queda con los
mismos ejercicios y cuentas que la PC en este momento; después cada una sigue por su lado.
Instrucciones para la tablet: android/LEEME_ANDROID.md.
"""

import argparse
import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "dist" / "Condor_Android.zip"
CARPETA = "Condor_Android"
# lo que va en el paquete (relativo a la raiz del repositorio)
INCLUIR = ["backend/app", "backend/migrations", "backend/alembic.ini", "backend/data", "frontend", "android"]
# nombres de carpeta o archivo que nunca van
EXCLUIR_NOMBRES = {"__pycache__", "venv", "respaldos", "tests", "pruebas", "maqueta", ".pytest_cache", "certs"}
EXCLUIR_SUFIJOS = {".pyc", ".db", ".db-wal", ".db-shm", ".log", ".bak"}
YA_COMPRIMIDOS = {".jpg", ".jpeg", ".png", ".webp", ".webm", ".mp4", ".zip", ".gz", ".z", ".pbf", ".mbtiles"}
TEXTO_LF = {".sh"}  # bash en Android: saltos de linea LF aunque el archivo se haya editado en Windows
CRLF, LF = bytes([13, 10]), bytes([10])


def archivos() -> list[Path]:
    out = []
    for rel in INCLUIR:
        p = RAIZ / rel
        if p.is_file():
            out.append(p)
            continue
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            partes = set(f.relative_to(RAIZ).parts)
            if partes & EXCLUIR_NOMBRES or f.suffix.lower() in EXCLUIR_SUFIJOS:
                continue
            out.append(f)
    return sorted(out)


def agregar(z: zipfile.ZipFile, f: Path, nombre: str) -> None:
    """Agrega un archivo al paquete: los scripts de bash con saltos LF y ejecutables; fotos y mapas sin recomprimir
    (ya vienen comprimidos)."""
    if f.suffix.lower() in TEXTO_LF:
        info = zipfile.ZipInfo(nombre)
        info.external_attr = 0o755 << 16  # ejecutable
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, f.read_bytes().replace(CRLF, LF))
    else:
        metodo = zipfile.ZIP_STORED if f.suffix.lower() in YA_COMPRIMIDOS else zipfile.ZIP_DEFLATED
        z.write(f, nombre, compress_type=metodo)


def copiar_base(destino: Path) -> Path:
    """Copia consistente de la base de esta PC (API de respaldo de SQLite, solo lectura sobre la original)."""
    origen = Path(os.environ.get("SIMULADOR_DB") or RAIZ / "backend" / "simulador_fenix.db")
    if not origen.is_file():
        raise SystemExit(f"No encuentro la base {origen}; use --sin-base para una base nueva.")
    src = sqlite3.connect(f"file:{origen.as_posix()}?mode=ro", uri=True)
    dst = sqlite3.connect(destino)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()
    return destino


def armar(salida: Path, con_base: bool) -> dict:
    salida.parent.mkdir(parents=True, exist_ok=True)
    lista = archivos()
    total = 0
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(salida, "w", allowZip64=True) as z:
        for f in lista:
            agregar(z, f, f"{CARPETA}/{f.relative_to(RAIZ).as_posix()}")
            total += f.stat().st_size
        if con_base:
            base = copiar_base(Path(tmp) / "simulador_fenix.db")
            z.write(base, f"{CARPETA}/backend/simulador_fenix.db", compress_type=zipfile.ZIP_DEFLATED)
            total += base.stat().st_size
    return {"archivos": len(lista) + (1 if con_base else 0), "mb": round(total / 1e6), "zip_mb": round(salida.stat().st_size / 1e6)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sin-base", action="store_true", help="no copiar la base de esta PC (la tablet empieza vacía)")
    ap.add_argument("--salida", default=str(SALIDA))
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    r = armar(Path(args.salida), not args.sin_base)
    # junto al paquete, el script que lo instala sin descomprimirlo a mano (android/instalar_desde_zip.sh)
    lado = Path(args.salida).parent / "instalar_desde_zip.sh"
    lado.write_bytes((RAIZ / "android" / "instalar_desde_zip.sh").read_bytes().replace(CRLF, LF))
    print(f"{args.salida}: {r['archivos']} archivos, {r['mb']} MB ({r['zip_mb']} MB comprimido)"
          f"{'' if args.sin_base else ', con una copia de la base de esta PC'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
