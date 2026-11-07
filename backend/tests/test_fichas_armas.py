"""Fichas de las armas (engine/fichas_armas.py) y sus fotos (seccion "armas" de tools/fotos/fotos_referencia.py)."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.engine import armas, catalogo, defensa_aerea, fichas_armas, misiles, ota

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def herramienta():
    spec = importlib.util.spec_from_file_location("fotos_referencia", RAIZ / "tools" / "fotos" / "fotos_referencia.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_cada_ficha_tiene_sus_datos_y_su_foto_compartida_existe():
    for f in fichas_armas.FICHAS.values():
        for campo in ("nombre", "tipo", "pais", "fabricante", "guia", "alcance", "velocidad", "ojiva", "peso",
                      "descripcion"):
            assert getattr(f, campo), (f.id, campo)
        if f.foto_de:
            seccion, id_ = f.foto_de
            assert id_ in {"modelos": catalogo.MODELOS, "clases": catalogo.CLASES, "armas": fichas_armas.FICHAS}[seccion], f.id


def test_todas_las_armas_del_simulador_tienen_ficha():
    assert set(ota.ARMAMENTO) <= set(fichas_armas.DE_OTA)
    assert all(v in fichas_armas.FICHAS for v in fichas_armas.DE_OTA.values())
    for s in defensa_aerea.SISTEMAS.values():
        for a in s.armas:
            assert fichas_armas.DE_DA.get(a.id) in fichas_armas.FICHAS, (s.modelo, a.id)
    misiles_modelos = {m.id for m in catalogo.MODELOS.values() if m.clase == "misil_crucero"}
    assert misiles_modelos <= set(fichas_armas.DE_MISIL)
    assert {misiles.MODELO, *misiles.MISIL_DEL_LANZADOR.values()} <= set(fichas_armas.DE_MISIL)
    for ids in [*fichas_armas.POR_MODELO.values(), *fichas_armas.POR_CLASE.values()]:
        assert all(i in fichas_armas.FICHAS for i in ids)


def test_las_repetidas_comparten_ficha():
    """AIM-120, AIM-9X, Igla-S y Stinger: la misma ficha en la aeronave y en la antiaerea."""
    assert fichas_armas.DE_DA["amraam"] == fichas_armas.DE_OTA["M120"] == "aim120"
    assert fichas_armas.DE_DA["aim9x"] == fichas_armas.DE_OTA["M9X"] == "aim9x"
    assert fichas_armas.DE_DA["igla_s"] == fichas_armas.DE_DA["9m342"]
    assert fichas_armas.DE_DA["fim92"] == fichas_armas.DE_DA["fim92_ms"]
    assert fichas_armas.DE_OTA["HPN"] == fichas_armas.DE_MISIL["harpoon"]


def test_armas_de_cada_equipo():
    assert fichas_armas.de_modelo("helo_ataque") == ["gsh23", "s8", "ataka"]  # Mi-35M de la AMB
    assert "agm114" in fichas_armas.de_modelo("ah64e") and "m230" in fichas_armas.de_modelo("ah64e")
    assert fichas_armas.de_modelo("ka52")[:2] == ["vikhr", "ataka"] and "2a42" in fichas_armas.de_modelo("ka52")
    assert fichas_armas.de_modelo("s400") == ["48n6", "9m96"]
    assert fichas_armas.de_modelo("kilo636") == ["kalibr", "mk48"]
    assert fichas_armas.de_modelo("bastion_p") == ["oniks"]
    assert fichas_armas.de_modelo("harpoon") == ["harpoon"]
    assert fichas_armas.de_modelo("s75_sa2") == ["v750"]
    assert fichas_armas.de_modelo("shahed136") == []  # la municion merodeadora es el arma misma
    assert fichas_armas.de_clase("misil_balistico") == ["9m723"] and fichas_armas.de_clase("torpedo") == ["mk48"]
    assert fichas_armas.ficha_ota("CKL", "mi171sh") == "s8" and fichas_armas.ficha_ota("CKL", "uh60l") == "hydra70"
    assert fichas_armas.ficha_ota("ALP", "mh60m") == "m134" and fichas_armas.ficha_ota("CKH", "t129") == "m197"


def test_las_aeronaves_armadas_llevan_su_armamento_real():
    """Ningun modelo del catalogo (salvo las municiones merodeadoras, que son el arma misma) toma el armamento
    occidental por defecto de su clase: un Su-35 o un Ka-52 no llevan AIM-120."""
    for m in catalogo.MODELOS.values():
        clase = catalogo.CLASES[m.clase]
        if clase.tipo != "aerea" or m.id.startswith("u_") or m.clase in ("misil_crucero", "municion_merodeadora"):
            continue
        if ota.armas_de(m.id, clase):
            assert m.id in ota.ARMAMENTO_POR_MODELO, m.id
    for rusos in ("su35", "mig29", "ka52", "mi28ne", "mi171sh"):
        assert not {"M120", "M9X", "HPN"} & set(ota.armas_de(rusos)), rusos


def test_cargas_con_los_misiles_antitanque_nuevos():
    assert armas.cargas_de("ka52")["ataque"] == {"VKR": 4, "ATK": 4, "CKL": 4, "CKH": 6}
    assert armas.cargas_de("tb2")["ataque"] == {"MAM": 4}
    assert armas.cargas_de("rafale")["antibuque"] == {"EXO": 2}


def test_publico_para_la_pantalla():
    p = fichas_armas.publico()
    json.dumps(p)
    assert p["fichas"]["aim120"]["nombre"] == "AIM-120 AMRAAM"
    assert p["por_modelo"]["s400"] == ["48n6", "9m96"] and p["por_clase"]["torpedo"] == ["mk48"]
    assert p["ota_modelo"]["mi171sh"] == {"CKL": "s8", "ALP": "pkt"}
    assert all(catalogo.CLASES[catalogo.MODELOS[m].clase].tipo == "aerea" for m in p["ota_modelo"])
    # la ficha que comparte la foto de un modelo la toma de alli
    assert p["fichas"]["harpoon"]["foto"] == catalogo.MODELOS["harpoon"].foto


def test_aplica_las_fotos_propias_e_ignora_lo_invalido(tmp_path):
    static = tmp_path / "static"
    (static / "fotos").mkdir(parents=True)
    (static / "fotos" / "ref_arma_aim120.jpg").write_bytes(b"jpg")
    entrada = {"foto": "/static/fotos/ref_arma_aim120.jpg", "obra": "AIM-120", "autor": "USAF", "licencia": "Public domain",
               "url_licencia": "https://x", "pagina": "https://commons.wikimedia.org/wiki/File:X.jpg"}
    manifiesto = tmp_path / "referencias.json"
    manifiesto.write_text(json.dumps({"armas": {"aim120": entrada, "no_existe": entrada,
                                                "r77": {**entrada, "foto": "/static/fotos/falta.jpg"}}}), encoding="utf-8")
    previas = dict(fichas_armas.FOTOS_ARMAS)
    try:
        assert fichas_armas.aplicar_fotos(manifiesto, static) == ["aim120"]
        assert fichas_armas.foto("aim120")["credito"]["autor"] == "USAF"
        assert fichas_armas.foto("r77") is None
    finally:
        fichas_armas.FOTOS_ARMAS.clear()
        fichas_armas.FOTOS_ARMAS.update(previas)


def test_la_herramienta_busca_las_armas_sin_foto_compartida(herramienta):
    armas_tool = {c for s, c, _, _ in herramienta.UNIDADES if s == "armas"}
    propias = {i for i, f in fichas_armas.FICHAS.items() if f.foto_de is None and i != "natak"}
    assert armas_tool == propias
    claves = [c for _, c, _, _ in herramienta.UNIDADES]
    assert len(claves) == len(set(claves))  # sin claves repetidas entre secciones
    assert herramienta.leer_manifiesto().keys() >= {"modelos", "clases", "armas"}


def test_el_manifiesto_de_armas_es_valido():
    datos = json.loads(catalogo.RUTA_REFERENCIAS.read_text(encoding="utf-8"))
    for id_, e in (datos.get("armas") or {}).items():
        assert id_ in fichas_armas.FICHAS, id_
        assert catalogo._referencia_valida(e, id_, catalogo.RUTA_FOTOS), id_
