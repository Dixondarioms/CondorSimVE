"""Empaqueta los datos de mapa (teselas, vectores y grilla de terreno) en un zip aparte del codigo.

Los datos de mapa pesan ~550 MB (la foto satelital, ~490 MB). Este script los deja en
`dist/siete_datos_<fecha>.zip` (mas su `.sha256`) para publicarlos como *release* de GitHub y que un
equipo nuevo los descargue con `tools/instalar_datos.py` (o `instalar.cmd`) en lugar de clonarlos.

    python tools/empaquetar_datos.py                    # dist/siete_datos_<AAAAMMDD>.zip
    python tools/empaquetar_datos.py --sin-satelite     # paquete ligero (sin tiles_sat, ~60 MB)
    python tools/empaquetar_datos.py --nombre siete_datos   # nombre fijo (el que espera instalar.ps1)

Dentro del zip va MANIFIESTO.json (fecha, regiones, carpetas, tamano). Solo usa la libreria estandar.
"""

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "dist"

# Rutas relativas a la raiz del proyecto. tiles_sat es la foto satelital (la pesada, opcional).
CARPETAS = ("frontend/static/tiles", "frontend/static/tiles_sat", "frontend/static/geo", "backend/data/terreno")
CARPETA_SATELITE = "frontend/static/tiles_sat"
TERRENO = "backend/data/terreno"
MANIFIESTO = "MANIFIESTO.json"
# Las imagenes ya vienen comprimidas: guardarlas tal cual es mucho mas rapido y ocupa lo mismo.
SIN_COMPRIMIR = {".png", ".jpg", ".jpeg", ".webp", ".z", ".gz"}
BLOQUE = 1024 * 1024


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for trozo in iter(lambda: f.read(BLOQUE), b""):
            h.update(trozo)
    return h.hexdigest()


def regiones_de(raiz: Path) -> list[dict]:
    """Lee backend/data/terreno/<region>/meta.json de cada region generada."""
    regiones = []
    for meta in sorted((raiz / TERRENO).glob("*/meta.json")):
        try:
            datos = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        regiones.append({"id": datos.get("id", meta.parent.name), "nombre": datos.get("nombre", meta.parent.name),
                         "bbox": datos.get("bbox"), "zoom": datos.get("z"),
                         "satelite": (raiz / CARPETA_SATELITE / meta.parent.name).is_dir()})
    return regiones


def carpetas_a_incluir(raiz: Path, sin_satelite: bool) -> list[str]:
    carpetas = [c for c in CARPETAS if not (sin_satelite and c == CARPETA_SATELITE)]
    return [c for c in carpetas if (raiz / c).is_dir()]


def empaquetar(raiz: Path = RAIZ, salida: Path = SALIDA, sin_satelite: bool = False,
               nombre: str | None = None, fecha: date | None = None, avisar=print) -> tuple[Path, Path, dict]:
    """Crea el zip y su .sha256 en `salida`. Devuelve (zip, sha256, manifiesto)."""
    fecha = fecha or date.today()
    carpetas = carpetas_a_incluir(raiz, sin_satelite)
    if not any(c == TERRENO for c in carpetas):
        raise SystemExit(f"No hay datos de terreno en {raiz / TERRENO}: nada que empaquetar.")
    if nombre is None:
        nombre = ("siete_datos_ligero_" if sin_satelite else "siete_datos_") + fecha.strftime("%Y%m%d")
    salida.mkdir(parents=True, exist_ok=True)
    ruta_zip, ruta_sha = salida / f"{nombre}.zip", salida / f"{nombre}.sha256"

    manifiesto = {"paquete": "siete_datos", "fecha": fecha.isoformat(), "satelite": not sin_satelite,
                  "carpetas": carpetas, "regiones": regiones_de(raiz), "archivos": 0, "tamano_bytes": 0}
    with zipfile.ZipFile(ruta_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for carpeta in carpetas:
            base = raiz / carpeta
            archivos = sorted(p for p in base.rglob("*") if p.is_file())
            avisar(f"  {carpeta}: {len(archivos)} archivos")
            for p in archivos:
                relativo = carpeta + "/" + p.relative_to(base).as_posix()
                tipo = zipfile.ZIP_STORED if p.suffix.lower() in SIN_COMPRIMIR else zipfile.ZIP_DEFLATED
                z.write(p, relativo, compress_type=tipo)
                manifiesto["archivos"] += 1
                manifiesto["tamano_bytes"] += p.stat().st_size
        z.writestr(MANIFIESTO, json.dumps(manifiesto, ensure_ascii=False, indent=1))

    manifiesto["zip"] = ruta_zip.name
    manifiesto["zip_bytes"] = ruta_zip.stat().st_size
    manifiesto["sha256"] = sha256_de(ruta_zip)
    # Formato de sha256sum: "<hash>  <archivo>" (lo verifica instalar_datos.py o `sha256sum -c`).
    ruta_sha.write_text(f"{manifiesto['sha256']}  {ruta_zip.name}\n", encoding="ascii", newline="\n")
    # Copia del manifiesto fuera del zip (con el hash) para la pagina del release.
    (salida / f"{nombre}.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    return ruta_zip, ruta_sha, manifiesto


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-satelite", action="store_true", help="no incluir frontend/static/tiles_sat (paquete ligero)")
    ap.add_argument("--nombre", help="nombre base del zip (por defecto siete_datos_<fecha>)")
    ap.add_argument("--salida", type=Path, default=SALIDA, help="carpeta de destino (por defecto dist/)")
    args = ap.parse_args(argv)

    print(f"Empaquetando los datos de mapa de {RAIZ}")
    ruta_zip, ruta_sha, m = empaquetar(RAIZ, args.salida, args.sin_satelite, args.nombre)
    print(f"Regiones: {', '.join(r['id'] for r in m['regiones']) or '(ninguna)'}")
    print(f"Zip: {ruta_zip} ({m['zip_bytes'] / 1e6:.1f} MB, {m['archivos']} archivos)")
    print(f"SHA-256: {m['sha256']}  -> {ruta_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
