"""Descarga una capa de imagenes satelitales (foto real) para el mismo area del mapa (BBOX de
preparar_terreno.py), como alternativa al relieve coloreado por clase de terreno.

Fuente: "Sentinel-2 cloudless" de EOX IT Services GmbH (https://cloudless.eox.at), servida por su WMTS publico
(tiles.maps.eox.at). La version del 2016 esta bajo licencia Creative Commons Attribution 4.0 (CC BY 4.0):
uso libre, incluso comercial, con atribucion. Version original de datos: Copernicus Sentinel (ESA).
Resolucion real 10 m/pixel (igual que ESA WorldCover, que ya se usa para la cobertura terrestre): tiene
detalle util hasta ~zoom 12-13; mas alla el servidor solo interpola (no hay mas informacion real), por eso el
zoom maximo por defecto es 12.

Se ejecuta UNA vez con internet, como preparar_terreno.py (y no toca esa capa ni la grilla que usa el motor:
esto es solo la imagen de fondo que se ve, no cambia el terreno de juego). Genera:
  frontend/static/tiles_sat/{z}/{x}/{y}.jpg
  frontend/static/tiles_sat/CREDITOS.md

Uso:
    python tools/preparar_satelite.py                        # zoom 5 a 12 (~30 000 teselas, unos 300 MB)
    python tools/preparar_satelite.py --hasta-zoom 13         # zoom 13 agrega ~88 000 teselas mas (~800 MB)
    python tools/preparar_satelite.py --capa s2cloudless-2023_3857 --anio 2023   # otro año (CC BY-NC-SA)

Es reanudable: si se corta, se puede volver a correr y solo baja las teselas que falten.
"""

import argparse
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from preparar_terreno import BBOX  # mismo area que el relieve

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "frontend" / "static" / "tiles_sat"
WMTS = "http://tiles.maps.eox.at/wmts/1.0.0/{capa}/default/GoogleMapsCompatible/{z}/{y}/{x}.jpg"
UA = {"User-Agent": "SimuladorFenix/1.0 (educational, offline military academy training tool)"}

CREDITOS = """# Imágenes satelitales (capa "Satélite")

`tiles_sat/{{z}}/{{x}}/{{y}}.jpg` son teselas de la capa **"{capa}"** de **EOxCloudless**
(https://cloudless.eox.at), un mosaico global sin nubes hecho con datos Copernicus Sentinel-2 (ESA),
servido por EOX IT Services GmbH (https://eox.at) vía su WMTS público (https://tiles.maps.eox.at).

- **Licencia:** {licencia}
- **Atribución exigida:** "EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH
  (Contains modified Copernicus Sentinel data {anio})" — ya incluida en el control de atribución del mapa
  (`frontend/static/js/app.js`, `initMapa()`); no la quite si cambia de capa.
- **Resolución real:** ~10 m/píxel (igual que ESA WorldCover). Se descargó hasta el zoom {hasta_zoom}; más
  allá el servidor solo interpola, así que no aporta información real.
- **Regenerar/ampliar:** `python tools/preparar_satelite.py --hasta-zoom N` (reanuda: no vuelve a bajar lo
  que ya está). No toca `frontend/static/tiles/` (relieve) ni `backend/data/terreno/` (grilla del motor):
  esto es solo la imagen de fondo alternativa, no cambia las reglas de movimiento ni la niebla de guerra.
"""


def tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    lat_r = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2.0 * n
    return int(x), int(y)


def descargar_tesela(capa: str, z: int, x: int, y: int, reintentos: int = 4) -> bool:
    """True si la descargo (o ya existia); False si fallo tras los reintentos."""
    destino = DESTINO / str(z) / str(x) / f"{y}.jpg"
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
    ap.add_argument("--desde-zoom", type=int, default=5)
    ap.add_argument("--hasta-zoom", type=int, default=12, help="12 = ~30 000 teselas; 13 agrega ~88 000 mas")
    ap.add_argument("--capa", default="s2cloudless_3857", help="id de capa WMTS (ver WMTSCapabilities.xml)")
    ap.add_argument("--anio", default="2016")
    ap.add_argument("--licencia", default="Creative Commons Attribution 4.0 (CC BY 4.0) — "
                     "https://creativecommons.org/licenses/by/4.0/")
    ap.add_argument("--workers", type=int, default=16)
    args = ap.parse_args()

    pendientes = []
    for z in range(args.desde_zoom, args.hasta_zoom + 1):
        xa, ya = tile_xy(BBOX[0], BBOX[3], z)
        xb, yb = tile_xy(BBOX[2], BBOX[1], z)
        for x in range(xa, xb + 1):
            for y in range(ya, yb + 1):
                pendientes.append((z, x, y))
    print(f"Capa {args.capa!r}: {len(pendientes)} teselas entre zoom {args.desde_zoom} y {args.hasta_zoom}.")

    ok = fallidas = 0
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futuros = {ex.submit(descargar_tesela, args.capa, z, x, y): (z, x, y) for z, x, y in pendientes}
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
    (DESTINO / "CREDITOS.md").write_text(
        CREDITOS.format(capa=args.capa, licencia=args.licencia, anio=args.anio, hasta_zoom=args.hasta_zoom),
        encoding="utf-8",
    )
    print(f"Listo: {ok} teselas ok, {fallidas} fallidas (correr de nuevo para reintentarlas).")


if __name__ == "__main__":
    main()
