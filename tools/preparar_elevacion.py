"""Grilla de alturas del motor (linea de vista de radares y sensores) para cada region del mapa.

Lee las teselas de elevacion Terrarium que tools/preparar_terreno.py ya dejo en tools/cache/terrarium/<z>/ (no
descarga nada) y escribe backend/data/terreno/<region>/elevacion.bin.z: metros sobre el nivel del mar en enteros de
16 bits, a menor resolucion que la grilla de clases para no ocupar mucha memoria en el servidor. Cada celda guarda
el punto MAS ALTO de su bloque, para que una cresta no se pierda al reducir (la linea de vista es conservadora).
En meta.json se anotan elev_paso (celdas de la grilla de clases por celda de altura) y elev_ancho/elev_alto.

    python tools/preparar_elevacion.py                 # todas las regiones generadas
    python tools/preparar_elevacion.py --region venezuela
"""

import argparse
import json
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
TERRENO = RAIZ / "backend" / "data" / "terreno"
CACHE = RAIZ / "tools" / "cache" / "terrarium"
MAX_CELDAS = 16_000_000  # ~32 MB en memoria por region como mucho
MINIMO_M, MAXIMO_M = -500, 9000


def paso_para(ancho: int, alto: int) -> int:
    """Reduccion (potencia de 2 que divide a 256) para que la grilla no supere MAX_CELDAS."""
    paso = 1
    while (ancho // paso) * (alto // paso) > MAX_CELDAS and paso < 256:
        paso *= 2
    return paso


def tesela(z: int, x: int, y: int) -> np.ndarray | None:
    ruta = CACHE / str(z) / str(x) / f"{y}.png"
    if not ruta.exists():
        return None
    a = np.asarray(Image.open(ruta).convert("RGB"), dtype=np.float32)
    return a[..., 0] * 256.0 + a[..., 1] + a[..., 2] / 256.0 - 32768.0


def generar(carpeta: Path) -> dict:
    meta_ruta = carpeta / "meta.json"
    meta = json.loads(meta_ruta.read_text(encoding="utf-8"))
    z, x0, y0, ancho, alto = meta["z"], meta["x0"], meta["y0"], meta["ancho"], meta["alto"]
    paso = paso_para(ancho, alto)
    w, h = ancho // paso, alto // paso
    salida = np.zeros((h, w), dtype=np.int16)
    faltan = 0
    filas = 256 // paso
    for ty in range(alto // 256):
        franja = np.zeros((256, ancho), dtype=np.float32)
        for tx in range(ancho // 256):
            e = tesela(z, x0 + tx, y0 + ty)
            if e is None:
                faltan += 1  # sin dato: nivel del mar
                continue
            franja[:, tx * 256:(tx + 1) * 256] = e
        bloques = franja.reshape(filas, paso, w, paso).max(axis=(1, 3))
        salida[ty * filas:(ty + 1) * filas] = np.clip(np.rint(bloques), MINIMO_M, MAXIMO_M).astype(np.int16)
    (carpeta / "elevacion.bin.z").write_bytes(zlib.compress(salida.astype("<i2").tobytes(), 6))
    meta.update(elev_paso=paso, elev_ancho=w, elev_alto=h)
    meta_ruta.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return {"region": carpeta.name, "paso": paso, "celdas": w * h, "metros_por_celda": meta.get("metros_por_pixel", 0) * paso,
            "min": int(salida.min()), "max": int(salida.max()), "teselas_sin_dato": faltan,
            "kb": (carpeta / "elevacion.bin.z").stat().st_size // 1024}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--region", help="id de la region (carpeta de backend/data/terreno); por defecto, todas")
    args = ap.parse_args()
    carpetas = sorted(p for p in TERRENO.iterdir() if (p / "meta.json").exists())
    if args.region:
        carpetas = [p for p in carpetas if p.name == args.region]
    for c in carpetas:
        r = generar(c)
        print(f"{r['region']}: {r['celdas']:,} celdas de ~{r['metros_por_celda']} m, alturas {r['min']}..{r['max']} m, "
              f"{r['kb']} KB" + (f", {r['teselas_sin_dato']} teselas sin dato (nivel del mar)" if r["teselas_sin_dato"] else ""), flush=True)


if __name__ == "__main__":
    main()
