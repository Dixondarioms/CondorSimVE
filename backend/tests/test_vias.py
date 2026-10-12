"""Carreteras reales (tools/preparar_vias.py): las unidades terrestres van mas rapido y cruzan rios por sus puentes."""

import zlib

import pytest

from app import terreno as terreno_mod
from app.engine import movimiento
from tests.conftest import TerrenoFalso


class TerrenoConVia(TerrenoFalso):
    """Rio entre lat 0.10 y 0.11, bosque al norte; una carretera principal por el meridiano 0 (|lon| < 0.005)."""

    def __init__(self, nivel=2):
        super().__init__(lambda lat, lon: "rio" if 0.10 <= lat <= 0.11 else "bosque" if lat > 0.11 else "llano")
        self.nivel = nivel

    def via(self, lat, lon):
        return self.nivel if abs(lon) < 0.005 else 0


def _unidad(clase="blindado", lon=0.0):
    return type("U", (), dict(tipo="terrestre", clase=clase, lat=0.0, lon=lon, velocidad_kmh=60, autonomia_km=300,
                              combustible=100))()


def test_el_blindado_cruza_el_rio_por_el_puente_de_la_carretera_y_no_fuera_de_ella():
    t = TerrenoConVia()
    m = movimiento.simular(_unidad(lon=0.0), [[1.0, 0.0]], t)
    assert m.lat > 0.11 and "rio" not in m.nota
    m = movimiento.simular(_unidad(lon=0.2), [[1.0, 0.2]], t)  # lejos de la carretera: sin puente
    assert m.lat < 0.10 and "rio sin puente ni vado" in m.nota


def test_por_carretera_se_avanza_mas_que_campo_traviesa():
    con_via = movimiento.simular(_unidad("infanteria", 0.0), [[1.0, 0.0]], TerrenoConVia())
    sin_via = movimiento.simular(_unidad("infanteria", 0.0), [[1.0, 0.0]], TerrenoConVia(nivel=0))
    assert con_via.lat > sin_via.lat + 0.1  # el bosque frena a la que va campo traviesa


def test_la_grilla_de_vias_se_carga_y_se_consulta():
    meta = {"id": "t", "z": 9, "x0": 0, "y0": 0, "ancho": 256, "alto": 256, "bbox": [-180, -85, 180, 85]}
    vias = bytearray(256 * 256)
    g = terreno_mod.Grilla(meta, bytes(256 * 256), None, bytes(vias))
    t = terreno_mod.Terreno(grillas=[g])
    i = g.indice(85.02, -179.5)
    assert i is not None
    vias[i] = 2
    t2 = terreno_mod.Terreno(grillas=[terreno_mod.Grilla(meta, bytes(256 * 256), None, bytes(vias))])
    assert t.via(85.02, -179.5) == 0 and t2.via(85.02, -179.5) == 2
    assert terreno_mod.Terreno().via(0, 0) == 0  # sin datos de vias: ninguna


@pytest.mark.skipif(not (terreno_mod.DATA_DIR / "venezuela" / "vias.bin.z").exists(), reason="sin vias.bin.z")
def test_los_datos_reales_tienen_la_autopista_regional_del_centro():
    real = terreno_mod.cargar()
    datos = zlib.decompress((terreno_mod.DATA_DIR / "venezuela" / "vias.bin.z").read_bytes())
    assert sum(1 for b in datos[::97] if b) > 100
    # entre Maracay y Valencia: alguna celda con carretera principal en un entorno de ~1 km
    assert any(real.via(10.22 + d / 100, -67.80 + e / 100) == 2 for d in range(-2, 3) for e in range(-2, 3))


# ---------- seleccion de rutas por carreteras ----------
from app.engine import rutas  # noqa: E402


def test_la_ruta_rodea_el_rio_por_el_puente_de_la_carretera():
    """Un blindado al este de la carretera (lon 0.2) que debe cruzar el rio: la ruta pasa por el puente (lon ~0)."""
    t = TerrenoConVia()
    u = _unidad(lon=0.2)
    r = rutas.ruta(u, [0.3, 0.2], t)
    assert r["waypoints"][-1] == [0.3, 0.2] and len(r["waypoints"]) <= rutas.MAX_WAYPOINTS
    puntos = [[u.lat, u.lon]] + r["waypoints"]
    cruce = [p for p in puntos if 0.09 <= p[0] <= 0.12]
    assert any(abs(p[1]) < 0.02 for p in cruce) or any(
        a[0] < 0.10 < b[0] and abs((a[1] + b[1]) / 2) < 0.05 for a, b in zip(puntos, puntos[1:]))
    m = movimiento.simular(u, r["waypoints"], t)
    assert "rio sin puente" not in m.nota


def test_sin_camino_o_si_no_es_terrestre_la_ruta_es_directa():
    agua = TerrenoFalso(lambda lat, lon: "agua" if lat > 0.1 else "llano")
    r = rutas.ruta(_unidad(), [0.5, 0.0], agua)
    assert r["waypoints"] == [[0.5, 0.0]] and "intransitable" in r["nota"]
    avion = type("U", (), dict(tipo="aerea", clase="caza", lat=0.0, lon=0.0))()
    assert rutas.ruta(avion, [1.0, 1.0], TerrenoConVia())["waypoints"] == [[1.0, 1.0]]


def test_la_api_traza_la_ruta_de_una_unidad_propia(api):
    from tests.test_api import _preparar
    prof, base, a, r1, r2 = _preparar(api)
    alfa = api("alfa")
    r = alfa.post(f"{base}/ordenes/ruta", json={"unidad_id": a["id"], "destino": [0.3, 0.1]})
    assert r.status_code == 200, r.text
    assert r.json()["waypoints"][-1] == [0.3, 0.1]
    assert alfa.post(f"{base}/ordenes/ruta", json={"unidad_id": r1["id"], "destino": [0.3, 0.1]}).status_code == 404
