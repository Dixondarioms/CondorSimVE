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


def _bases_aereas():
    import json

    return json.loads((FRONTEND / "static" / "geo" / "bases_aereas.geojson").read_text(encoding="utf-8"))["features"]


def test_las_bases_aereas_de_venezuela_y_vecinos_son_validas():
    """Las 18 curadas a mano siguen intactas (mismos OACI, nombres y propiedades) dentro del area de detalle."""
    bases = [b for b in _bases_aereas() if b["properties"]["origen"] == "curado"]
    ven = [b for b in bases if b["properties"]["pais"] == "Venezuela"]
    vecinos = [b for b in bases if b["properties"]["pais"] != "Venezuela"]
    assert len(ven) == 8 and len(vecinos) == 10
    assert {"SVBL", "SVFM", "SVMC", "SVBC", "SVBM", "SVBS", "SVPR", "SVPA"} == {b["properties"]["icao"] for b in ven}
    assert {b["properties"]["icao"] for b in vecinos} == {"SKUA", "SKYP", "SKCC", "SKUC", "SKPC", "SKRH", "SKVP", "SBBV", "SYLT", "TTPP"}
    assert {b["properties"]["pais"] for b in vecinos} == {"Colombia", "Brasil", "Guyana", "Trinidad y Tobago"}
    por_icao = {b["properties"]["icao"]: b for b in bases}
    assert por_icao["SVBL"]["properties"] == {"icao": "SVBL", "nombre": "Base Aérea El Libertador", "ciudad": "Maracay (Palo Negro)", "estado": "Aragua",
                                              "elevacion_m": 442, "pais": "Venezuela", "tipo": "base aérea", "origen": "curado"}
    assert por_icao["SVBL"]["geometry"]["coordinates"] == [-67.56111, 10.18056]
    assert por_icao["SBBV"]["properties"]["nombre"] == "Base Aérea de Boa Vista (Ala 7, FAB)" and por_icao["SBBV"]["properties"]["elevacion_m"] is None
    for b in bases:
        lon, lat = b["geometry"]["coordinates"]
        # dentro del area de detalle (region "venezuela"), donde tambien tienen su plano OSM
        assert 0.6 <= lat <= 12.4 and -73.4 <= lon <= -59.6, b["properties"]["nombre"]
        p = b["properties"]
        assert p["nombre"] and p["ciudad"] and p["estado"] and p["tipo"] in ("base aérea", "aeropuerto")
        if p["pais"] == "Venezuela":
            assert p["nombre"].startswith("Base A") and p["elevacion_m"] >= 0


def test_los_aerodromos_de_ourairports_cubren_toda_america_sin_repetir_oaci():
    bases = _bases_aereas()
    nuevos = [b for b in bases if b["properties"]["origen"] == "ourairports"]
    assert 800 <= len(nuevos) <= 1500 and len(bases) == len(nuevos) + 18
    icao = [b["properties"]["icao"] for b in bases]
    assert len(set(icao)) == len(icao)
    paises = {b["properties"]["pais"] for b in nuevos}
    assert {"Estados Unidos", "Canadá", "México", "Argentina", "Chile", "Perú", "Cuba", "Panamá", "Guayana Francesa (Francia)"} <= paises
    assert all(not (p.isupper() and len(p) == 2) for p in paises), "todo codigo ISO debe traducirse a un nombre en español"
    militares = [b for b in nuevos if b["properties"]["tipo"] == "base aérea"]
    assert len(militares) >= 100 and any(b["properties"]["pais"] == "Paraguay" for b in militares)
    for b in nuevos:
        lon, lat = b["geometry"]["coordinates"]
        assert -56 <= lat <= 72 and -170 <= lon <= -30, b["properties"]["nombre"]  # recuadro de la region "america"
        p = b["properties"]
        assert set(p) == {"icao", "nombre", "ciudad", "estado", "elevacion_m", "pais", "tipo", "origen"}
        assert p["icao"] and p["nombre"] and p["estado"] and p["tipo"] in ("base aérea", "aeropuerto")
        assert p["elevacion_m"] is None or isinstance(p["elevacion_m"], int)
        assert not p["nombre"].startswith("[Duplicate]")


def test_el_criterio_de_inclusion_de_ourairports_es_el_documentado():
    import sys

    sys.path.insert(0, str(FRONTEND.parent / "tools"))
    import generar_bases_aereas as g

    fila = lambda **k: {"continent": "SA", "type": "medium_airport", "name": "Aeropuerto X", "latitude_deg": "10", "longitude_deg": "-67",
                        "icao_code": "SVXX", "scheduled_service": "yes", "gps_code": "", "ident": "SVXX", **k}
    assert g.incluir(fila())
    assert not g.incluir(fila(scheduled_service="no"))  # mediano sin servicio regular
    assert g.incluir(fila(scheduled_service="no", type="large_airport"))
    assert not g.incluir(fila(icao_code=""))
    assert g.incluir(fila(icao_code="", type="small_airport", name="Base Aérea Capitán Manuel Ríos"))  # militar por nombre
    assert g.incluir(fila(type="small_airport", name="Whiteman Air Force Base", continent="NA"))
    assert not g.incluir(fila(type="heliport", name="Base Aérea Helipuerto"))
    assert not g.incluir(fila(continent="EU"))
    assert not g.incluir(fila(longitude_deg="-20"))  # fuera del recuadro de America
    assert not g.incluir(fila(name="[Duplicate] Aeropuerto X"))
    assert g.es_militar("Naval Air Station Oceana") and g.es_militar("Base de la Fuerza Aérea Paraguaya") and not g.es_militar("Nashville International Airport")
    assert g.identificador({"icao_code": "", "gps_code": "KNMM", "ident": "KNMM"}) == "KNMM"
    assert g.identificador({"icao_code": "", "gps_code": "", "ident": "PY-0035"}) == "PY-0035"


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


def test_los_planos_de_aerodromos_son_coherentes_con_su_indice():
    """Cada entrada del indice tiene su archivo (formato compacto: rodajes como ejes, sin marcas de pista) y las bases
    de Venezuela, sus vecinos y el aeropuerto de Barinas (plantillas) conservan su plano."""
    import json

    import pytest

    carpeta = FRONTEND / "static" / "geo" / "aerodromos"
    if not (carpeta / "indice.json").exists():  # datos de mapa (paquete siete_datos o tools/preparar_aerodromos.py)
        pytest.skip("sin planos de aerodromos instalados")
    indice = json.loads((carpeta / "indice.json").read_text(encoding="utf-8"))
    assert "OpenStreetMap" in indice["fuente"]
    por_icao = {b["icao"]: b for b in indice["bases"]}
    curadas = {b["properties"]["icao"] for b in _bases_aereas() if b["properties"]["origen"] == "curado"}
    assert curadas | {"SVBI"} <= set(por_icao)
    capa = {b["properties"]["icao"] for b in _bases_aereas()} | {"SVBI"}
    for icao, b in por_icao.items():
        assert icao in capa and (b["pistas"] or b["limite"])
        plano = json.loads((carpeta / b["archivo"]).read_text(encoding="utf-8"))
        assert plano["bases"][0]["icao"] == icao
        tipos = {f["properties"]["tipo"] for f in plano["features"]}
        assert not tipos & {"marca", "eje_rodaje"}, icao
        for f in plano["features"]:
            assert f["properties"]["base"] == icao
            if f["properties"]["tipo"] == "rodaje":
                assert f["geometry"]["type"] == "LineString" and f["properties"]["ancho_m"] > 0
            if f["properties"]["tipo"] == "pista":
                assert len(f["properties"]["extremos"]) == 2 and f["properties"]["largo_m"] >= 300
