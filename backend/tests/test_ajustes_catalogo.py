"""Ajustes del instructor sobre el catalogo (backend/data/ajustes_catalogo.json)."""

import json
import logging
from pathlib import Path

import pytest

from app.engine import catalogo

TOPES = ("MAX_AERONAVES_GRUPO", "MAX_AERONAVES_BANDO", "MAX_DRONES_BANDO")


@pytest.fixture(autouse=True)
def catalogo_intacto():
    """Guarda y restaura CLASES, MODELOS y los topes para que los ajustes no se filtren a otras pruebas."""
    clases, modelos = dict(catalogo.CLASES), dict(catalogo.MODELOS)
    topes = {n: getattr(catalogo, n) for n in TOPES}
    try:
        yield
    finally:
        catalogo.CLASES.clear()
        catalogo.CLASES.update(clases)
        catalogo.MODELOS.clear()
        catalogo.MODELOS.update(modelos)
        for n, v in topes.items():
            setattr(catalogo, n, v)


def _escribir(tmp_path: Path, datos) -> Path:
    ruta = tmp_path / "ajustes.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


def test_sin_archivo_no_cambia_nada(tmp_path):
    antes = dict(catalogo.CLASES)
    resumen = catalogo.aplicar_ajustes(tmp_path / "no_existe.json")
    assert resumen == {"clases": {}, "modelos": {}, "topes": []}
    assert catalogo.CLASES == antes


def test_aplica_clases_modelos_y_topes(tmp_path):
    caza_defensa = catalogo.CLASES["caza"].defensa
    ruta = _escribir(tmp_path, {
        "_comentario": "se ignora",
        "clases": {"caza": {"velocidad_kmh": 950, "ataque_vs": {"aerea": 1.4}, "recarga_turnos": 2}},
        "modelos": {"f16": {"alcance_km": 90, "ataque_vs": {"naval": 0.9}}},
        "topes": {"MAX_AERONAVES_BANDO": 32},
    })
    resumen = catalogo.aplicar_ajustes(ruta)

    caza = catalogo.CLASES["caza"]
    assert caza.velocidad_kmh == 950 and isinstance(caza.velocidad_kmh, float)
    assert caza.recarga_turnos == 2
    assert caza.ataque_vs == {"terrestre": 0.7, "aerea": 1.4, "naval": 0.7}  # fusion por clave
    assert caza.defensa == caza_defensa  # lo no indicado se conserva
    f16 = catalogo.MODELOS["f16"]
    assert f16.alcance_km == 90
    assert f16.ataque_vs == {"terrestre": 0.85, "aerea": 1.3, "naval": 0.9}
    assert f16.foto == "/static/fotos/f16.jpg"
    assert catalogo.MAX_AERONAVES_BANDO == 32
    assert resumen == {"clases": {"caza": ["ataque_vs", "recarga_turnos", "velocidad_kmh"]},
                       "modelos": {"f16": ["alcance_km", "ataque_vs"]}, "topes": ["MAX_AERONAVES_BANDO"]}


def test_ignora_desconocidos_y_tipos_incorrectos(tmp_path, caplog):
    antes_caza = catalogo.CLASES["caza"]
    ruta = _escribir(tmp_path, {
        "clases": {
            "no_existe": {"velocidad_kmh": 1},
            "caza": {"nombre": "Otro", "velocidad_kmh": "rapido", "despliegue_turnos": 1.5,
                     "defensa": -1, "firma": True, "ataque_vs": {"base": 2, "aerea": "x"}},
            "blindado": "texto",
        },
        "modelos": {"f99": {"alcance_km": 1}, "f16": {"foto": "/otra.jpg"}},
        "topes": {"MAX_AERONAVES_BANDO": 0, "OTRO_TOPE": 3, "MAX_DRONES_BANDO": "muchos"},
        "otra_seccion": {},
    })
    with caplog.at_level(logging.WARNING, logger="simulador.catalogo"):
        resumen = catalogo.aplicar_ajustes(ruta)

    assert resumen == {"clases": {}, "modelos": {}, "topes": []}
    assert catalogo.CLASES["caza"] == antes_caza
    assert catalogo.MODELOS["f16"].foto == "/static/fotos/f16.jpg"
    assert catalogo.MAX_AERONAVES_BANDO == 24 and catalogo.MAX_DRONES_BANDO == 16
    avisos = "\n".join(r.getMessage() for r in caplog.records)
    for texto in ("'no_existe'", "'nombre'", "velocidad_kmh", "despliegue_turnos", "defensa", "firma",
                  "'base'", "aerea", "'f99'", "'foto'", "MAX_AERONAVES_BANDO", "'OTRO_TOPE'",
                  "MAX_DRONES_BANDO", "'otra_seccion'", "clases.blindado"):
        assert texto in avisos, texto


def test_json_invalido_se_ignora_con_aviso(tmp_path, caplog):
    ruta = tmp_path / "roto.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    antes = dict(catalogo.CLASES)
    with caplog.at_level(logging.WARNING, logger="simulador.catalogo"):
        catalogo.aplicar_ajustes(ruta)
    assert catalogo.CLASES == antes
    assert "no se pudo leer" in caplog.text


def test_variable_de_entorno_elige_el_archivo(tmp_path, monkeypatch):
    ruta = _escribir(tmp_path, {"topes": {"MAX_AERONAVES_GRUPO": 6}})
    monkeypatch.setenv(catalogo.VAR_AJUSTES, str(ruta))
    catalogo.aplicar_ajustes()
    assert catalogo.MAX_AERONAVES_GRUPO == 6


def test_el_archivo_de_ejemplo_es_valido(caplog):
    ejemplo = Path(catalogo.RUTA_AJUSTES).with_name("ajustes_catalogo.ejemplo.json")
    assert ejemplo.is_file()
    with caplog.at_level(logging.WARNING, logger="simulador.catalogo"):
        resumen = catalogo.aplicar_ajustes(ejemplo)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], caplog.text
    assert "caza" in resumen["clases"] and "f16" in resumen["modelos"]


def test_el_endpoint_refleja_los_ajustes(tmp_path, api):
    ruta = _escribir(tmp_path, {
        "clases": {"infanteria": {"velocidad_kmh": 33}},
        "modelos": {"su30": {"deteccion_km": 95}},
        "topes": {"MAX_DRONES_BANDO": 20},
    })
    catalogo.aplicar_ajustes(ruta)
    datos = api("prof").get("/api/catalogo").json()
    clases = {c["id"]: c for c in datos["clases"]}
    modelos = {m["id"]: m for m in datos["modelos"]}
    assert clases["infanteria"]["velocidad_kmh"] == 33
    assert modelos["su30"]["deteccion_km"] == 95
    assert datos["aeronaves"]["max_drones"] == 20


def test_perfil_usa_los_valores_ajustados(tmp_path):
    from types import SimpleNamespace

    ruta = _escribir(tmp_path, {"modelos": {"f16": {"defensa": 1.5}}, "clases": {"caza": {"alcance_km": 99}}})
    catalogo.aplicar_ajustes(ruta)
    perfil = catalogo.perfil(SimpleNamespace(tipo="aerea", clase="caza", modelo="f16"))
    assert perfil.defensa == 1.5 and perfil.alcance_km == 99
