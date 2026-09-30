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


def test_las_bases_aereas_de_venezuela_y_vecinos_son_validas():
    import json

    datos = json.loads((FRONTEND / "static" / "geo" / "bases_aereas.geojson").read_text(encoding="utf-8"))
    bases = datos["features"]
    ven = [b for b in bases if b["properties"]["pais"] == "Venezuela"]
    vecinos = [b for b in bases if b["properties"]["pais"] != "Venezuela"]
    assert len(ven) == 8 and len(vecinos) >= 10
    icao = [b["properties"]["icao"] for b in bases]
    assert len(set(icao)) == len(icao)
    assert {"SVBL", "SVFM", "SVMC", "SVBC", "SVBM", "SVBS", "SVPR", "SVPA"} == {b["properties"]["icao"] for b in ven}
    assert {b["properties"]["pais"] for b in vecinos} == {"Colombia", "Brasil", "Guyana", "Trinidad y Tobago"}
    for b in bases:
        lon, lat = b["geometry"]["coordinates"]
        # dentro del area que cubren los tiles (ver LIMITES en app.js)
        assert 0.6 <= lat <= 12.4 and -73.4 <= lon <= -59.6, b["properties"]["nombre"]
        p = b["properties"]
        assert p["nombre"] and p["ciudad"] and p["estado"] and p["tipo"] in ("base aérea", "aeropuerto")
        if p["pais"] == "Venezuela":
            assert p["nombre"].startswith("Base A") and p["elevacion_m"] >= 0


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


def test_hay_una_capa_satelital_real_ademas_del_relieve():
    """No exhaustivo (la descarga completa son ~30 000 teselas): solo confirma que la capa satelital
    existe, tiene creditos y cubre al menos los zooms bajos (rapidos de generar)."""
    tiles_sat = FRONTEND / "static" / "tiles_sat" / "venezuela"
    creditos = tiles_sat.parent / "CREDITOS.md"
    assert creditos.is_file() and "EOxCloudless" in creditos.read_text(encoding="utf-8")
    assert "CC BY 4.0" in creditos.read_text(encoding="utf-8") or "Attribution" in creditos.read_text(encoding="utf-8")
    for z in (5, 6, 7):  # rapidos: deben estar completos incluso si la descarga a mayor zoom sigue en curso
        carpeta = tiles_sat / str(z)
        assert carpeta.is_dir() and any(carpeta.rglob("*.jpg")), f"faltan teselas satelitales en zoom {z}"


def test_index_usa_dos_capas_base_y_cita_ambas_fuentes():
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "tiles_sat" in html or "tiles_sat" in (FRONTEND / "static" / "js" / "app.js").read_text(encoding="utf-8")
    app_js = (FRONTEND / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "/static/tiles_sat/${m.id}/{z}/{x}/{y}.jpg" in app_js and "/static/tiles/${m.id}/{z}/{x}/{y}.jpg" in app_js
    assert "Sentinel-2 cloudless" in app_js and "CC BY 4.0" in app_js
