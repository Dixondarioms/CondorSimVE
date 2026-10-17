"""Regiones superpuestas del mapa (Venezuela en detalle, America, mundo opcional, recuadros a medida): el motor
consulta la mas detallada que cubra el punto y el frontend recibe la lista por GET /api/terreno/mapas."""

import json
import math
from pathlib import Path

from app import terreno as terreno_mod
from app.routers import terreno as router_terreno
from app.terreno import AGUA, BOSQUE, Grilla, Terreno

RAIZ = Path(__file__).resolve().parents[2]


def _grilla(id_, z, bbox, clase):
    """Grilla uniforme (todas las celdas de la misma clase) que cubre exactamente las teselas del recuadro."""
    n = 2 ** z

    def tile(lon, lat):
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
        return x, y

    xa, ya = tile(bbox[0], bbox[3])
    xb, yb = tile(bbox[2], bbox[1])
    meta = {"id": id_, "nombre": id_.capitalize(), "bbox": list(bbox), "z": z, "z_min": z - 2, "x0": xa, "y0": ya,
            "ancho": (xb - xa + 1) * 256, "alto": (yb - ya + 1) * 256, "metros_por_pixel": 100}
    return Grilla(meta, bytes([clase]) * (meta["ancho"] * meta["alto"]))


def test_gana_la_region_mas_detallada_y_fuera_de_todas_es_llano():
    gruesa = _grilla("continente", 5, (-100.0, -30.0, -30.0, 30.0), AGUA)
    fina = _grilla("detalle", 8, (-70.0, 5.0, -65.0, 10.0), BOSQUE)
    t = Terreno(grillas=[gruesa, fina])
    assert [g.id for g in t.grillas] == ["detalle", "continente"]  # de mas a menos detallada
    assert t.clase(7.5, -67.0) == "bosque"  # cubierto por las dos: manda la fina
    assert t.clase(-20.0, -50.0) == "agua"  # solo la gruesa
    assert t.clase(50.0, 10.0) == "llano"  # fuera de todas
    assert t.disponible and t.meta["id"] == "detalle"


def test_constructor_de_una_sola_region_sigue_funcionando():
    g = _grilla("x", 6, (-10.0, -10.0, 10.0, 10.0), BOSQUE)
    t = Terreno(g.meta, g.clases)
    assert t.clase(0.0, 0.0) == "bosque" and t.regiones()[0]["id"] == "x"
    assert not Terreno().disponible and Terreno().clase(0.0, 0.0) == "llano"


def test_los_datos_reales_tienen_venezuela_y_america_en_carpetas_por_region():
    for region in ("venezuela", "america"):
        carpeta = terreno_mod.DATA_DIR / region
        meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
        assert meta["id"] == region and len(meta["bbox"]) == 4 and meta["z_min"] < meta["z"]
        assert (carpeta / "clases.bin.z").stat().st_size > 1000
        # teselas del zoom nativo y del minimo, y vectores de referencia
        tiles = RAIZ / "frontend" / "static" / "tiles" / region
        assert (tiles / str(meta["z"])).is_dir() and (tiles / str(meta["z_min"])).is_dir()
        assert (RAIZ / "frontend" / "static" / "geo" / region / "fronteras.geojson").is_file()
    real = terreno_mod.cargar()
    ids = [r["id"] for r in real.regiones()]
    # foto satelital por region: Venezuela hasta el zoom 13, America hasta el 8 (tools/preparar_satelite.py)
    sat = {r["id"]: r["satelite"] for r in real.regiones()}
    assert sat["venezuela"]["z_min"] == 5 and sat["venezuela"]["z_max"] >= 12
    assert sat["america"] and sat["america"]["z_min"] == 3 and sat["america"]["z_max"] >= 8
    assert ids.index("venezuela") < ids.index("america")
    assert real.clase(10.5, -66.9) == "urbano"  # Caracas (Venezuela)
    assert real.clase(-34.6, -58.4) == "urbano"  # Buenos Aires (America)
    assert real.clase(25.0, -90.0) == "agua"  # golfo de Mexico
    assert real.clase(45.0, 10.0) == "llano" or "mundo" in ids  # Europa: sin mundo, fuera del mapa


def test_endpoint_mapas_lista_las_regiones_de_mas_a_menos_detallada(api, monkeypatch):
    gruesa = _grilla("continente", 5, (-100.0, -30.0, -30.0, 30.0), AGUA)
    fina = _grilla("detalle", 8, (-70.0, 5.0, -65.0, 10.0), BOSQUE)
    monkeypatch.setattr(router_terreno, "get_terreno", lambda: Terreno(grillas=[gruesa, fina]))
    for rol in ("prof", "alfa", "obs"):
        r = api(rol).get("/api/terreno/mapas")
        assert r.status_code == 200
        mapas = r.json()["mapas"]
        assert [m["id"] for m in mapas] == ["detalle", "continente"]
        assert mapas[0] == {"id": "detalle", "nombre": "Detalle", "bbox": [-70.0, 5.0, -65.0, 10.0], "z": 8, "z_min": 6, "metros_por_pixel": 100, "satelite": None}
    assert api(None).get("/api/terreno/mapas").status_code in (401, 403)
