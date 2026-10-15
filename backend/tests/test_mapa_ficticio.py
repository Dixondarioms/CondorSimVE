"""Mapa ficticio (tools/generar_mapa_ficticio.py): la region "teatro_ficticio" con la Republica de Valdoria y la
Republica de Ostrania, sus capas y la plantilla "Valdoria contra Ostrania"."""

import json
import zlib
from pathlib import Path

import pytest

from app import terreno
from app.engine import catalogo, naciones, plantillas

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "backend" / "data" / "terreno" / "teatro_ficticio"
GEO = RAIZ / "frontend" / "static" / "geo" / "teatro_ficticio"

pytestmark = pytest.mark.skipif(not (DATOS / "meta.json").exists(), reason="mapa ficticio no generado")


def _grilla():
    return next(g for g in terreno.cargar().grillas if g.id == "teatro_ficticio")


def test_la_region_ficticia_esta_en_pleno_atlantico_y_no_pisa_a_ninguna_otra():
    meta = json.loads((DATOS / "meta.json").read_text(encoding="utf-8"))
    assert meta["ficticio"] is True and meta["z"] == 9
    oeste, sur, este, norte = meta["bbox"]
    for g in terreno.cargar().grillas:
        if g.id == "teatro_ficticio":
            continue
        o, s, e, n = g.meta["bbox"]
        assert e < oeste or o > este or n < sur or s > norte, g.id  # no se superponen
    # el borde del recuadro es mar abierto: la tierra nunca queda cortada
    t = terreno.cargar()
    for lat in (sur + 0.05, norte - 0.05):
        for lon in (oeste + 0.05, (oeste + este) / 2, este - 0.05):
            assert t.clase(lat, lon) == "agua"


def test_tiene_la_geografia_de_un_pais():
    g = _grilla()
    clases = zlib.decompress((DATOS / "clases.bin.z").read_bytes())
    cuenta = {nombre: clases.count(bytes([k])) / len(clases) for k, nombre in terreno.NOMBRES.items()}
    for nombre in ("llano", "bosque", "montana", "pantano", "rio", "urbano"):
        assert cuenta[nombre] > 0.001, nombre
    assert 0.35 < cuenta["agua"] < 0.65
    alturas = [g.altura(lat / 10, lon / 10) for lat in range(65, 125, 3) for lon in range(-270, -200, 3)]
    alturas = [a for a in alturas if a is not None]
    assert max(alturas) > 2500 and min(alturas) < -100  # cumbres y fondo marino
    vias = zlib.decompress((DATOS / "vias.bin.z").read_bytes())
    assert vias.count(b"\x02") > 1000 and vias.count(b"\x01") > 1000  # troncales y carreteras secundarias


def test_capas_vectoriales():
    capas = {n: json.loads((GEO / f"{n}.geojson").read_text(encoding="utf-8"))["features"]
             for n in ("fronteras", "estados", "rios", "lagos", "lugares", "carreteras")}
    assert any(f["properties"].get("name") == "Frontera Valdoria – Ostrania" for f in capas["fronteras"])
    assert sum(1 for f in capas["rios"] if f["properties"]["name"]) >= 4  # rios principales con nombre
    lagos = {f["properties"]["name"] for f in capas["lagos"]}
    assert any(n.startswith("Embalse") for n in lagos) and any(n.startswith(("Lago", "Laguna")) for n in lagos)
    capitales = [f["properties"] for f in capas["lugares"] if f["properties"]["capital"]]
    assert {c["name"] for c in capitales} == {"Valdora", "Nueva Ostria"}
    assert {f["properties"]["nivel"] for f in capas["carreteras"]} == {1, 2}
    infra = json.loads((GEO / "infraestructura.json").read_text(encoding="utf-8"))["instalaciones"]
    assert {i["clase"] for i in infra} >= {"hidroelectrica", "termoelectrica", "refineria", "centro_comunicaciones", "puente"}
    assert all(i["clase"] in catalogo.CLASES for i in infra)


def test_naciones_ficticias():
    assert naciones.NACIONES["valdoria"].capital == "Valdora"
    assert naciones.NACIONES["ostrania"].iso == "XO"


def test_la_plantilla_ubica_cada_unidad_donde_corresponde(db_session):
    p = plantillas.PLANTILLAS["teatro_ficticio"]
    assert p.origen == "codigo" and p.nacion_azul == "valdoria" and p.nacion_rojo == "ostrania"
    t = terreno.cargar()
    for u in p.unidades:
        clase = catalogo.CLASES[u.clase]
        sitio = t.clase(u.lat, u.lon)
        if clase.tipo == "naval":
            assert sitio == "agua", u.nombre
        elif u.clase != "puente":
            assert sitio != "agua", (u.nombre, sitio)
    bandos = {u.bando for u in p.unidades}
    assert bandos == {"azul", "rojo"}
    esc = plantillas.crear_desde_plantilla(db_session, "teatro_ficticio")
    assert esc.nacion_azul == "valdoria" and esc.dia_noche
    from app.models.objetivo import Objetivo
    from app.models.unidad import Unidad
    unidades = db_session.query(Unidad).filter(Unidad.escenario_id == esc.id).all()
    assert len(unidades) == len(p.unidades)
    assert any(u.en_tierra and u.base_id for u in unidades)  # aviones estacionados en su base
    assert any(u.clase == "puente" and u.radio_km for u in unidades)
    assert db_session.query(Objetivo).filter(Objetivo.escenario_id == esc.id).count() == len(p.objetivos)
