"""Instala el paquete de datos de mapa (siete_datos_*.zip) en su sitio dentro del proyecto.

    python tools/instalar_datos.py https://.../siete_datos.zip     # descarga (reanudable) e instala
    python tools/instalar_datos.py                                 # URL de la variable SIETE_DATOS_URL
    python tools/instalar_datos.py --zip dist/siete_datos_20260930.zip   # un zip ya descargado

Verifica el SHA-256 si existe un `.sha256` junto al zip (o junto a la URL: siete_datos.sha256) y
descomprime frontend/static/tiles, tiles_sat, geo y backend/data/terreno sin borrar lo que ya haya:
solo anade o reemplaza archivos. Descarga con barra de progreso y reanuda una descarga cortada si el
servidor admite `Range`. Solo usa la libreria estandar (funciona con el Python del sistema, sin venv).
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parent.parent
DESCARGAS = RAIZ / "dist" / "descargas"
VARIABLE_URL = "SIETE_DATOS_URL"
CARPETAS = ("frontend/static/tiles", "frontend/static/tiles_sat", "frontend/static/geo", "backend/data/terreno")
MANIFIESTO = "MANIFIESTO.json"
BLOQUE = 256 * 1024
AGENTE = "SIETE-instalar_datos/1.0"


class ErrorDatos(Exception):
    """Error de uso, descarga o contenido del paquete."""


class ErrorVerificacion(ErrorDatos):
    """El SHA-256 del zip no coincide con el esperado."""


# ------------------------------------------------------------------ descarga
def _mb(n: int) -> str:
    return f"{n / 1e6:.1f} MB"


class Progreso:
    """Barra de progreso en la consola (stderr); no imprime nada si no hay terminal."""

    def __init__(self, total: int | None, inicial: int = 0, salida=None, activo: bool | None = None):
        self.total, self.hecho, self.salida = total, inicial, salida or sys.stderr
        self.activo = activo if activo is not None else bool(getattr(self.salida, "isatty", lambda: False)())
        self._ultimo = 0.0

    def avanzar(self, n: int, forzar: bool = False) -> None:
        self.hecho += n
        ahora = time.monotonic()
        if not self.activo or (ahora - self._ultimo < 0.2 and not forzar):
            return
        self._ultimo = ahora
        if self.total:
            frac = min(1.0, self.hecho / self.total)
            barra = "#" * int(frac * 30)
            self.salida.write(f"\r  {frac * 100:5.1f} % [{barra:<30}] {_mb(self.hecho)} / {_mb(self.total)}")
        else:
            self.salida.write(f"\r  {_mb(self.hecho)} descargados")
        self.salida.flush()

    def terminar(self) -> None:
        if self.activo:
            self.avanzar(0, forzar=True)
            self.salida.write("\n")
            self.salida.flush()


def _abrir(url: str, cabeceras: dict | None = None, tiempo: float = 60):
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE, **(cabeceras or {})})
    return urllib.request.urlopen(peticion, timeout=tiempo)


def descargar(url: str, destino: Path, avisar=print, progreso: bool | None = None) -> Path:
    """Descarga `url` en `destino`, reanudando `destino.parcial` si existe y el servidor admite Range."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    inicial = parcial.stat().st_size if parcial.exists() else 0
    cabeceras = {"Range": f"bytes={inicial}-"} if inicial else {}
    try:
        respuesta = _abrir(url, cabeceras)
    except urllib.error.HTTPError as e:
        if e.code == 416 and inicial:  # el parcial ya esta completo
            parcial.replace(destino)
            return destino
        raise ErrorDatos(f"No se pudo descargar {url}: HTTP {e.code} {e.reason}") from e
    except (urllib.error.URLError, OSError) as e:
        raise ErrorDatos(f"No se pudo descargar {url}: {getattr(e, 'reason', e)}") from e

    with respuesta:
        reanuda = inicial > 0 and respuesta.status == 206
        if inicial and not reanuda:
            avisar("  El servidor no admite reanudar: se descarga desde el principio.")
            inicial = 0
        largo = respuesta.headers.get("Content-Length")
        total = (int(largo) + inicial) if largo and largo.isdigit() else None
        avisar(f"  {'Reanudando' if reanuda else 'Descargando'} {url}" + (f" ({_mb(total)})" if total else ""))
        barra = Progreso(total, inicial, activo=progreso)
        with open(parcial, "ab" if reanuda else "wb") as f:
            for trozo in iter(lambda: respuesta.read(BLOQUE), b""):
                f.write(trozo)
                barra.avanzar(len(trozo))
        barra.terminar()
    if total is not None and parcial.stat().st_size != total:
        raise ErrorDatos(f"Descarga incompleta ({_mb(parcial.stat().st_size)} de {_mb(total)}); "
                         "vuelva a ejecutar el comando para reanudarla.")
    parcial.replace(destino)
    return destino


# ------------------------------------------------------------------ verificacion
def _url_sha256(url: str) -> str:
    base = url.split("?", 1)[0]
    return re.sub(r"\.zip$", "", base) + ".sha256"


def _leer_hash(texto: str) -> str | None:
    m = re.search(r"\b([0-9a-fA-F]{64})\b", texto)
    return m.group(1).lower() if m else None


def hash_esperado(url: str | None = None, zip_local: Path | None = None) -> str | None:
    """SHA-256 publicado junto al paquete (archivo .sha256), o None si no hay."""
    if zip_local is not None:
        ruta = zip_local.with_suffix(".sha256")
        if ruta.exists():
            return _leer_hash(ruta.read_text(encoding="utf-8", errors="replace"))
    if url:
        try:
            with _abrir(_url_sha256(url), tiempo=30) as r:
                return _leer_hash(r.read(4096).decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError, ValueError):
            return None
    return None


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(1024 * 1024), b""):
            h.update(trozo)
    return h.hexdigest()


def verificar(ruta_zip: Path, esperado: str) -> None:
    real = sha256_de(ruta_zip)
    if real != esperado.lower():
        raise ErrorVerificacion(f"El SHA-256 de {ruta_zip.name} no coincide (esperado {esperado[:12]}..., "
                                f"obtenido {real[:12]}...). El archivo esta danado o no es el publicado.")


# ------------------------------------------------------------------ instalacion
def _ruta_segura(nombre: str) -> PurePosixPath | None:
    """Solo se aceptan rutas relativas dentro de las carpetas de datos (sin '..', ni absolutas)."""
    if "\\" in nombre or nombre.startswith("/") or re.match(r"^[A-Za-z]:", nombre):
        return None
    p = PurePosixPath(nombre)
    if ".." in p.parts or not any(nombre == c or nombre.startswith(c + "/") for c in CARPETAS):
        return None
    return p


def instalar_zip(ruta_zip: Path, raiz: Path = RAIZ, avisar=print) -> dict:
    """Descomprime las carpetas de datos en `raiz` (anade/reemplaza; nunca borra). Devuelve un resumen."""
    resumen = {"nuevos": 0, "reemplazados": 0, "omitidos": [], "manifiesto": None}
    try:
        z = zipfile.ZipFile(ruta_zip)
    except zipfile.BadZipFile as e:
        raise ErrorDatos(f"{ruta_zip} no es un zip valido: {e}") from e
    with z:
        nombres = z.namelist()
        if MANIFIESTO in nombres:
            try:
                resumen["manifiesto"] = json.loads(z.read(MANIFIESTO).decode("utf-8"))
            except ValueError:
                pass
        if not any(_ruta_segura(n) for n in nombres):
            raise ErrorDatos("El zip no contiene ninguna de las carpetas de datos "
                             f"({', '.join(CARPETAS)}): no parece un paquete siete_datos.")
        for info in z.infolist():
            if info.is_dir() or info.filename == MANIFIESTO:
                continue
            relativo = _ruta_segura(info.filename)
            if relativo is None:
                resumen["omitidos"].append(info.filename)
                continue
            destino = raiz.joinpath(*relativo.parts)
            existia = destino.exists()
            destino.parent.mkdir(parents=True, exist_ok=True)
            temporal = destino.with_name(destino.name + ".tmp")
            with z.open(info) as origen, open(temporal, "wb") as salida:
                shutil.copyfileobj(origen, salida, BLOQUE)
            temporal.replace(destino)  # reemplazo atomico: nunca queda un archivo a medias
            resumen["reemplazados" if existia else "nuevos"] += 1
    if resumen["omitidos"]:
        avisar(f"  Omitidos {len(resumen['omitidos'])} archivos fuera de las carpetas de datos.")
    return resumen


def obtener_zip(url: str | None, zip_local: Path | None, descargas: Path, verificar_hash: bool, avisar=print) -> Path:
    """Devuelve la ruta del zip listo para instalar (descargado si hace falta), ya verificado."""
    if zip_local is not None:
        if not zip_local.is_file():
            raise ErrorDatos(f"No existe el archivo {zip_local}")
        ruta = zip_local
    else:
        nombre = os.path.basename(url.split("?", 1)[0]) or "siete_datos.zip"
        ruta = descargas / nombre
        if ruta.exists():
            avisar(f"  Ya existe {ruta}: no se vuelve a descargar (borrelo para forzar la descarga).")
        else:
            descargar(url, ruta, avisar)
    if not verificar_hash:
        return ruta
    esperado = hash_esperado(url, ruta)  # primero el .sha256 junto al zip; si no, el publicado junto a la URL
    if esperado is None:
        avisar("  AVISO: no hay archivo .sha256 junto al paquete; no se verifica la integridad.")
        return ruta
    avisar("  Verificando el SHA-256 del paquete...")
    verificar(ruta, esperado)
    avisar("  SHA-256 correcto.")
    return ruta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?", help=f"URL del zip (o variable de entorno {VARIABLE_URL})")
    ap.add_argument("--zip", type=Path, help="zip local ya descargado (no descarga nada)")
    ap.add_argument("--destino", type=Path, default=RAIZ, help="raiz del proyecto (por defecto, la de este script)")
    ap.add_argument("--descargas", type=Path, default=DESCARGAS, help="carpeta donde guardar la descarga")
    ap.add_argument("--sin-verificar", action="store_true", help="no comprobar el SHA-256")
    args = ap.parse_args(argv)

    url = None if args.zip else (args.url or os.environ.get(VARIABLE_URL))
    if not url and not args.zip:
        ap.error(f"indique la URL del paquete, --zip <archivo> o la variable {VARIABLE_URL}")
    try:
        ruta = obtener_zip(url, args.zip, args.descargas, not args.sin_verificar)
        print(f"  Instalando {ruta.name} en {args.destino} ...")
        r = instalar_zip(ruta, args.destino)
    except ErrorVerificacion as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except ErrorDatos as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nDescarga interrumpida: vuelva a ejecutar el comando para reanudarla.", file=sys.stderr)
        return 130
    m = r["manifiesto"] or {}
    regiones = ", ".join(x.get("id", "?") for x in m.get("regiones", [])) or "(sin manifiesto)"
    print(f"  Datos de mapa instalados: {r['nuevos']} archivos nuevos, {r['reemplazados']} reemplazados. "
          f"Regiones: {regiones}" + (f" (paquete del {m['fecha']})" if m.get("fecha") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
