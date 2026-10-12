"""Descarga la capa de imagenes satelitales (foto real) de una REGION del mapa (las mismas de preparar_terreno.py),
que se superpone al relieve coloreado por clase de terreno.

Fuente: "Sentinel-2 cloudless" de EOX IT Services GmbH (https://cloudless.eox.at), servida por su WMTS publico
(tiles.maps.eox.at). La version del 2016 esta bajo licencia Creative Commons Attribution 4.0 (CC BY 4.0):
uso libre, incluso comercial, con atribucion. Version original de datos: Copernicus Sentinel (ESA).
Resolucion real 10 m/pixel (igual que ESA WorldCover, que ya se usa para la cobertura terrestre): tiene
detalle util hasta ~zoom 13-14; mas alla el servidor solo interpola (no hay mas informacion real).

Cada region tiene su propio zoom maximo por defecto, porque el numero de teselas se multiplica por 4 con cada
nivel: Venezuela hasta el 12 (~30 000 teselas, ~350 MB) y America hasta el 8 (~17 000 teselas, ~150 MB;
el zoom 9 agregaria ~51 000 mas y el 10, ~200 000). El mundo entero hasta el 7 (~22 000 teselas).

Se ejecuta UNA vez con internet por region, como preparar_terreno.py (y no toca esa capa ni la grilla que usa
el motor: esto es solo la imagen de fondo que se ve, no cambia el terreno de juego). Genera:
  frontend/static/tiles_sat/<region>/{z}/{x}/{y}.jpg
  frontend/static/tiles_sat/CREDITOS.md
El servidor detecta solo que zooms tiene cada region (GET /api/terreno/mapas) y el frontend dibuja la foto de
cada una recortada a su recuadro, la mas detallada encima.

Uso:
    python tools/preparar_satelite.py                          # venezuela, zoom 5 a 13
    python tools/preparar_satelite.py --region america         # zoom 3 a 8
    python tools/preparar_satelite.py --region america --hasta-zoom 9   # mas detalle (~460 MB mas)
    python tools/preparar_satelite.py --region mundo           # zoom 2 a 7
    python tools/preparar_satelite.py --region caribe --hasta-zoom 10    # una region a medida ya generada
    python tools/preparar_satelite.py --capa s2cloudless-2023_3857 --anio 2023   # otro año (CC BY-NC-SA)

Es reanudable: si se corta, se puede volver a correr y solo baja las teselas que falten.
"""

import argparse
import json
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from preparar_terreno import DATA_OUT, REGIONES, tile_xy

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "frontend" / "static" / "tiles_sat"
WMTS = "https://tiles.maps.eox.at/wmts/1.0.0/{capa}/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg"
UA = {"User-Agent": "SimuladorFenix/1.0 (educational, offline military academy training tool)"}

# zoom maximo por defecto de cada region predefinida (las regiones a medida: su zoom nativo)
HASTA_ZOOM = {"venezuela": 13, "america": 8, "mundo": 7}

CREDITOS = """# Imágenes satelitales (capa "Satélite")

`tiles_sat/<region>/{{z}}/{{x}}/{{y}}.jpg` son teselas de la capa **"{capa}"** de **EOxCloudless**
(https://cloudless.eox.at), un mosaico global sin nubes hecho con datos Copernicus Sentinel-2 (ESA),
servido por EOX IT Services GmbH (https://eox.at) vía su WMTS público (https://tiles.maps.eox.at).

- **Licencia:** {licencia}
- **Atribución exigida:** "EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH
  (Contains modified Copernicus Sentinel data {anio})" — ya incluida en el control de atribución del mapa
  (`frontend/static/js/app.js`, `initMapa()`); no la quite si cambia de capa.
- **Resolución real:** ~10 m/píxel (igual que ESA WorldCover). Cada región se descargó hasta un zoom distinto
  (Venezuela 13, América 8, el mundo 7 si se generó): más allá el mapa amplía la tesela más cercana.
- **Regenerar/ampliar:** `python tools/preparar_satelite.py --region <id> --hasta-zoom N` (reanuda: no vuelve a
  bajar lo que ya está). No toca `frontend/static/tiles/` (relieve) ni `backend/data/terreno/` (grilla del
  motor): esto es solo la imagen de fondo alternativa, no cambia las reglas de movimiento ni la niebla de guerra.
"""


def region_de(id_):
    """bbox y zoom minimo de la region: predefinida o ya generada por preparar_terreno.py (meta.json)."""
    meta = DATA_OUT / id_ / "meta.json"
    if meta.is_file():
        m = json.loads(meta.read_text(encoding="utf-8"))
        return tuple(m["bbox"]), int(m["z_min"]), int(m["z"])
    if id_ in REGIONES:
        r = REGIONES[id_]
        return r.bbox, r.z_min, r.z
    raise SystemExit(f"Region desconocida: {id_!r}. Generela antes con preparar_terreno.py o use una predefinida: "
                     f"{', '.join(REGIONES)}")


def descargar_tesela(carpeta: Path, capa: str, z: int, x: int, y: int, reintentos: int = 4) -> bool:
    """True si la descargo (o ya existia); False si fallo tras los reintentos."""
    destino = carpeta / str(z) / str(x) / f"{y}.jpg"
    if destino.exists() and destino.stat().st_size > 0:
        return True
    destino.parent.mkdir(parents=True, exist_ok=True)
    url = WMTS.format(capa=capa, z=z, y=y, x=x)
    for intento in range(reintentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                datos = r.read()
            destino.write_bytes(datos)
            return True
        except Exception:  # noqa: BLE001
            if intento == reintentos - 1:
                return False
            time.sleep(1.5 * (intento + 1))
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="venezuela", help="id de la region (predefinida o generada): venezuela, america, mundo, ...")
    ap.add_argument("--desde-zoom", type=int, help="por defecto, el zoom minimo de la region")
    ap.add_argument("--hasta-zoom", type=int, help="por defecto: venezuela 12, america 8, mundo 7, a medida su zoom nativo")
    ap.add_argument("--capa", default="s2cloudless_3857", help="id de capa WMTS (ver WMTSCapabilities.xml)")
    ap.add_argument("--anio", default="2016")
    ap.add_argument("--licencia", default="Creative Commons Attribution 4.0 (CC BY 4.0) — "
                     "https://creativecommons.org/licenses/by/4.0/")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    bbox, z_min, z_nativo = region_de(args.region)
    desde = args.desde_zoom if args.desde_zoom is not None else z_min
    hasta = args.hasta_zoom if args.hasta_zoom is not None else HASTA_ZOOM.get(args.region, z_nativo)
    carpeta = DESTINO / args.region

    pendientes = []
    for z in range(desde, hasta + 1):
        xa, ya = tile_xy(bbox[0], bbox[3], z)
        xb, yb = tile_xy(bbox[2], bbox[1], z)
        for x in range(xa, xb + 1):
            for y in range(ya, yb + 1):
                pendientes.append((z, x, y))
    print(f"Region {args.region!r}, capa {args.capa!r}: {len(pendientes)} teselas entre zoom {desde} y {hasta}.")

    ok = fallidas = 0
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futuros = {ex.submit(descargar_tesela, carpeta, args.capa, z, x, y): (z, x, y) for z, x, y in pendientes}
        for i, fut in enumerate(as_completed(futuros), 1):
            if fut.result():
                ok += 1
            else:
                fallidas += 1
                print("  fallo:", futuros[fut])
            if i % 2000 == 0 or i == len(pendientes):
                transcurrido = time.time() - t0
                print(f"  {i}/{len(pendientes)} ({100 * i / len(pendientes):.0f} %) "
                      f"· {transcurrido:.0f} s · {fallidas} fallidas")

    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / "CREDITOS.md").write_text(CREDITOS.format(capa=args.capa, licencia=args.licencia, anio=args.anio), encoding="utf-8")
    print(f"Listo: {ok} teselas ok, {fallidas} fallidas (correr de nuevo para reintentarlas).")


if __name__ == "__main__":
    main()
