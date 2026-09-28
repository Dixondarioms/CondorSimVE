"""La interfaz debe ser autosuficiente y sin internet: todo recurso citado por index.html existe en disco y se
sirve, y no se referencia ningun origen externo."""

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def _recursos(html: str) -> list[str]:
    return re.findall(r'(?:src|href)="([^"#]+)"', html)


def test_index_solo_cita_recursos_locales_que_existen():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    recursos = _recursos(html)
    assert any(r.endswith("videowall.js") for r in recursos)
    assert any(r.endswith("leaflet.draw.js") for r in recursos)
    for r in recursos:
        assert not r.startswith(("http:", "https:", "//")), f"recurso externo (no funciona sin internet): {r}"
        if r.startswith("/static/"):
            assert (FRONTEND / r.lstrip("/")).is_file(), f"falta {r}"


def test_los_recursos_de_index_se_sirven(api):
    cliente = api()  # los estaticos son publicos: no hace falta iniciar sesion
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    for r in _recursos(html):
        if r.startswith("/static/"):
            respuesta = cliente.get(r)
            assert respuesta.status_code == 200, r
            assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_el_arnes_de_pruebas_es_coherente_con_index():
    arnes = FRONTEND / "static" / "pruebas" / "arnes.html"
    if not arnes.exists():  # se genera con tools/generar_arnes.py
        return
    contenido = arnes.read_text(encoding="utf-8")
    base = (FRONTEND / "index.html").read_text(encoding="utf-8")
    # el arnes solo agrega su script antes de app.js: si cambia index.html hay que regenerarlo
    assert contenido.count("<script") == base.count("<script") + 1, "regenere el arnes: tools/generar_arnes.py"


def test_las_bases_aereas_de_venezuela_son_validas():
    import json

    datos = json.loads((FRONTEND / "static" / "geo" / "bases_aereas.geojson").read_text(encoding="utf-8"))
    bases = datos["features"]
    assert len(bases) == 8
    icao = [b["properties"]["icao"] for b in bases]
    assert len(set(icao)) == 8 and {"SVBL", "SVFM", "SVMC", "SVBC", "SVBM", "SVBS", "SVPR", "SVPA"} == set(icao)
    for b in bases:
        lon, lat = b["geometry"]["coordinates"]
        # dentro del area que cubren los tiles de Venezuela (ver LIMITES en app.js)
        assert 0.6 <= lat <= 12.4 and -73.4 <= lon <= -59.6, b["properties"]["nombre"]
        p = b["properties"]
        assert p["nombre"].startswith("Base A") and p["ciudad"] and p["estado"] and p["elevacion_m"] >= 0


def test_las_bases_se_pueden_colocar_como_unidad_en_su_posicion(api):
    """El boton 'Base Azul/Roja' de la capa crea una unidad base_aerea con las coordenadas de la base."""
    import json

    from tests.test_api import _preparar

    prof, base, *_ = _preparar(api)
    feat = json.loads((FRONTEND / "static" / "geo" / "bases_aereas.geojson").read_text(encoding="utf-8"))["features"][0]
    lon, lat = feat["geometry"]["coordinates"]
    r = prof.post(f"{base}/unidades", json=dict(nombre="BA Libertador", bando="azul", clase="base_aerea", lat=lat, lon=lon))
    assert r.status_code == 200, r.text
    assert (r.json()["clase"], r.json()["tipo"], r.json()["lat"], r.json()["lon"]) == ("base_aerea", "base", lat, lon)


def test_estan_las_48_imagenes_de_los_modelos_3d_y_ningun_glb_en_el_proyecto():
    from PIL import Image

    raiz = FRONTEND.parent
    carpeta = FRONTEND / "static" / "aeronaves"
    for modelo in ("f16", "su30"):
        for rumbo in range(0, 360, 15):
            ruta = carpeta / f"{modelo}_{rumbo:03d}.png"
            assert ruta.is_file(), f"falta {ruta.name}"
            with Image.open(ruta) as im:
                assert im.size == (160, 160) and im.mode == "RGBA"
                assert im.getchannel("A").getextrema()[0] == 0, f"{ruta.name} debe tener fondo transparente"
                assert im.getbbox() is not None, f"{ruta.name} esta vacia"
    assert (carpeta / "CREDITOS.md").is_file()
    # licencia Sketchfab Standard: los modelos originales no se redistribuyen con el proyecto
    ignorados = ("node_modules", "venv", "tools/cache", ".git")
    encontrados = [str(p.relative_to(raiz)) for p in raiz.rglob("*.glb") if not any(i in p.as_posix() for i in ignorados)]
    assert encontrados == [], f"no incluya los .glb en el proyecto: {encontrados}"


def test_las_dos_orientaciones_extremas_de_un_sprite_son_distintas():
    """Rumbo 0 (proa al norte) y 180 (proa al sur) no pueden ser la misma imagen."""
    from PIL import Image, ImageChops

    carpeta = FRONTEND / "static" / "aeronaves"
    for modelo in ("f16", "su30"):
        a, b = Image.open(carpeta / f"{modelo}_000.png"), Image.open(carpeta / f"{modelo}_180.png")
        assert ImageChops.difference(a, b).getbbox() is not None
