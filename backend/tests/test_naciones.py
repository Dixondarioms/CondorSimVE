"""Identidad nacional de cada bando (Venezuela, sus vecinos y el resto de America): catalogo, configuracion, niebla de guerra,
duplicado, exportacion y datos de referencia de los paises vecinos en el terreno."""

import json
from pathlib import Path

from app.engine import naciones
from tests.test_api import _preparar

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


# ---------- catalogo ----------
def test_el_catalogo_tiene_venezuela_y_sus_tres_vecinos_terrestres():
    assert {"venezuela", "colombia", "brasil", "guyana"} <= set(naciones.NACIONES)
    for n in naciones.NACIONES.values():
        assert n.nombre and n.gentilicio and n.capital
        assert len(n.colores) in (2, 3) and all(c.startswith("#") and len(c) == 7 for c in n.colores)


def test_el_catalogo_cubre_todos_los_estados_de_america_ordenados_con_venezuela_primero():
    import re
    import unicodedata

    esperados = {"venezuela", "colombia", "brasil", "guyana", "trinidad_tobago", "estados_unidos", "mexico", "guatemala", "belice",
                 "honduras", "el_salvador", "nicaragua", "costa_rica", "panama", "cuba", "republica_dominicana", "haiti", "jamaica",
                 "bahamas", "barbados", "surinam", "ecuador", "peru", "bolivia", "paraguay", "uruguay", "argentina", "chile", "canada"}
    assert esperados <= set(naciones.NACIONES)
    ids = list(naciones.NACIONES)
    assert ids[0] == "venezuela"
    sin_tildes = lambda t: unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    resto = [n.nombre for n in list(naciones.NACIONES.values())[1:]]
    assert resto == sorted(resto, key=sin_tildes)
    for n in naciones.NACIONES.values():
        assert re.fullmatch(r"[a-z_]+", n.id), n.id  # snake_case sin tildes
        assert re.fullmatch(r"[A-Z]{2}", n.iso) and naciones.PAISES_AMERICA[n.iso] == n.nombre
    assert len({n.iso for n in naciones.NACIONES.values()}) == len(naciones.NACIONES)
    assert naciones.NACIONES["mexico"].capital == "Ciudad de México" and naciones.NACIONES["chile"].gentilicio == "chileno"
    # territorios sin estado propio: solo nombre en español para los datos geograficos
    assert naciones.PAISES_AMERICA["GF"].startswith("Guayana Francesa") and naciones.PAISES_AMERICA["PR"].startswith("Puerto Rico")
    assert "GF" not in {n.iso for n in naciones.NACIONES.values()}


def test_obtener_devuelve_none_para_vacio_o_desconocido():
    assert naciones.obtener("venezuela").nombre == "Venezuela"
    assert naciones.obtener("") is None
    assert naciones.obtener(None) is None
    assert naciones.obtener("marte") is None


def test_endpoint_naciones_publico_para_cualquier_rol(api):
    for rol in ("prof", "alfa", "bravo", "obs"):
        r = api(rol).get("/api/naciones")
        assert r.status_code == 200, rol
        lista = r.json()["naciones"]
        ids = {n["id"] for n in lista}
        assert {"venezuela", "colombia", "brasil", "guyana", "trinidad_tobago", "estados_unidos", "mexico", "argentina", "canada"} <= ids
        assert lista[0]["id"] == "venezuela" and len(lista) == len(naciones.NACIONES)  # mismo orden que el catalogo
        assert lista[0]["iso"] == "VE" and lista[0]["colores"] == ["#FFCC00", "#00247D", "#CF142B"]
    assert api().get("/api/naciones").status_code == 401


# ---------- configuracion del escenario ----------
def test_un_escenario_nuevo_es_venezuela_contra_sin_identidad(api):
    prof, base, *_ = _preparar(api)
    esc = prof.get(base).json()["escenario"]
    assert (esc["nacion_azul"], esc["nacion_rojo"]) == ("venezuela", "")


def test_el_instructor_asigna_una_nacion_a_cada_bando(api):
    prof, base, *_ = _preparar(api)
    r = prof.patch(f"{base}/config", json={"nacion_rojo": "colombia"})
    assert r.status_code == 200, r.text
    assert r.json()["escenario"]["nacion_rojo"] == "colombia"
    r = prof.patch(f"{base}/config", json={"nacion_azul": "brasil", "nacion_rojo": "guyana"})
    assert (r.json()["escenario"]["nacion_azul"], r.json()["escenario"]["nacion_rojo"]) == ("brasil", "guyana")
    # quitar la identidad: vuelve a "Bando Azul"/"Bando Rojo"
    r = prof.patch(f"{base}/config", json={"nacion_rojo": ""})
    assert r.json()["escenario"]["nacion_rojo"] == ""
    ajustes = prof.get(f"{base}/aar").json()["turnos"][0]["eventos"]
    assert any("Brasil" in e["descripcion"] for e in ajustes if e["tipo"] == "ajuste")


def test_una_nacion_desconocida_se_rechaza_y_no_alumnos(api):
    prof, base, *_ = _preparar(api)
    r = prof.patch(f"{base}/config", json={"nacion_azul": "marte"})
    assert r.status_code == 400 and "Marte" not in r.json()["detail"] and "marte" in r.json()["detail"]
    assert api("alfa").patch(f"{base}/config", json={"nacion_rojo": "colombia"}).status_code == 403


def test_ambos_bandos_pueden_representar_al_mismo_pais(api):
    """No se obliga a que Venezuela intervenga: dos vecinos pueden enfrentarse entre si."""
    prof, base, *_ = _preparar(api)
    r = prof.patch(f"{base}/config", json={"nacion_azul": "colombia", "nacion_rojo": "colombia"})
    assert r.status_code == 200
    assert (r.json()["escenario"]["nacion_azul"], r.json()["escenario"]["nacion_rojo"]) == ("colombia", "colombia")


def test_la_identidad_nacional_no_es_secreta_para_ningun_bando(api):
    """No es informacion militar del ejercicio (niebla de guerra): ambos bandos la ven, a diferencia de com_*."""
    prof, base, *_ = _preparar(api)
    prof.patch(f"{base}/config", json={"nacion_azul": "venezuela", "nacion_rojo": "guyana"})
    for rol in ("alfa", "bravo", "obs"):
        esc = api(rol).get(base).json()["escenario"]
        assert (esc["nacion_azul"], esc["nacion_rojo"]) == ("venezuela", "guyana")


def test_duplicar_copia_la_identidad_nacional(api):
    prof, base, *_ = _preparar(api)
    prof.patch(f"{base}/config", json={"nacion_azul": "venezuela", "nacion_rojo": "brasil"})
    copia = prof.post(f"{base}/duplicar").json()
    assert (copia["nacion_azul"], copia["nacion_rojo"]) == ("venezuela", "brasil")


def test_exportar_incluye_la_identidad_nacional(api):
    prof, base, *_ = _preparar(api)
    prof.patch(f"{base}/config", json={"nacion_rojo": "guyana"})
    datos = prof.get(f"{base}/exportar").json()
    assert (datos["escenario"]["nacion_azul"], datos["escenario"]["nacion_rojo"]) == ("venezuela", "guyana")


# ---------- terreno de referencia de los paises vecinos ----------
def test_las_fronteras_incluyen_venezuela_y_sus_vecinos_recortadas_al_mapa():
    datos = json.loads((FRONTEND / "static" / "geo" / "venezuela" / "fronteras.geojson").read_text(encoding="utf-8"))
    paises = {f["properties"]["pais"]: f["properties"]["name"] for f in datos["features"]}
    assert paises == {"VEN": "Venezuela", "COL": "Colombia", "BRA": "Brasil", "GUY": "Guyana", "TTO": "Trinidad y Tobago"}
    # LIMITES del mapa en app.js: recortadas ahi, no el contorno completo de cada pais
    LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = -73.5, 0.5, -59.5, 12.5
    for f in datos["features"]:
        anillos = f["geometry"]["coordinates"] if f["geometry"]["type"] == "MultiPolygon" else [f["geometry"]["coordinates"]]
        for poli in anillos:
            for lon, lat in poli[0]:
                assert LON_MIN - 0.01 <= lon <= LON_MAX + 0.01 and LAT_MIN - 0.01 <= lat <= LAT_MAX + 0.01, f["properties"]


def test_los_estados_de_los_vecinos_fronterizos_estan_presentes():
    datos = json.loads((FRONTEND / "static" / "geo" / "venezuela" / "estados.geojson").read_text(encoding="utf-8"))
    por_pais = {}
    for f in datos["features"]:
        por_pais.setdefault(f["properties"]["pais"], set()).add(f["properties"]["name"])
    assert "Táchira" in por_pais["VEN"] and len(por_pais["VEN"]) >= 20  # Venezuela sigue completa, sin cambios
    assert "Norte de Santander" in por_pais["COL"] and "Táchira" not in por_pais["COL"]
    assert "Roraima" in por_pais["BRA"]
    assert por_pais["GUY"]
    assert por_pais["TTO"]


def test_ciudades_de_los_vecinos_marcan_su_pais_y_las_venezolanas_no(api):
    datos = json.loads((FRONTEND / "static" / "geo" / "venezuela" / "lugares.geojson").read_text(encoding="utf-8"))
    por_nombre = {f["properties"]["name"]: f["properties"] for f in datos["features"]}
    assert por_nombre["Cúcuta"]["pais"] == "Colombia"
    assert por_nombre["Boa Vista"]["pais"] == "Brasil"
    assert "pais" not in por_nombre["Caracas"]
    assert "pais" not in por_nombre["Maracaibo"]
