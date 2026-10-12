"""Fotos de referencia (tools/fotos/fotos_referencia.py y catalogo.aplicar_referencias): sin red."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.engine import catalogo

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture
def herramienta():
    spec = importlib.util.spec_from_file_location("fotos_referencia", RAIZ / "tools" / "fotos" / "fotos_referencia.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def catalogo_limpio(monkeypatch):
    monkeypatch.setattr(catalogo, "MODELOS", dict(catalogo.MODELOS))
    monkeypatch.setattr(catalogo, "FOTOS_CLASE", {})
    return catalogo


def _entrada(foto, **extra):
    return {"foto": foto, "obra": "Mi-35M de la AMB", "autor": "Fulano", "licencia": "CC BY-SA 4.0",
            "url_licencia": "https://creativecommons.org/licenses/by-sa/4.0",
            "pagina": "https://commons.wikimedia.org/wiki/File:X.jpg", **extra}


def test_aplica_fotos_a_modelos_y_clases_e_ignora_lo_invalido(tmp_path, catalogo_limpio):
    static = tmp_path / "static"
    (static / "fotos").mkdir(parents=True)
    (static / "fotos" / "ref_helo_ataque.jpg").write_bytes(b"jpg")
    (static / "fotos" / "ref_fragata.jpg").write_bytes(b"jpg")
    manifiesto = tmp_path / "referencias.json"
    manifiesto.write_text(json.dumps({
        "modelos": {"helo_ataque": _entrada("/static/fotos/ref_helo_ataque.jpg"),
                    "uav_reco": _entrada("/static/fotos/no_existe.jpg"),
                    "mig99": _entrada("/static/fotos/ref_helo_ataque.jpg")},
        "clases": {"fragata": _entrada("/static/fotos/ref_fragata.jpg"),
                   "destructor": _entrada("/static/fotos/ref_fragata.jpg", pagina="http://inseguro"),
                   "submarino": {"foto": "/static/fotos/ref_fragata.jpg"}},
    }), encoding="utf-8")
    ilustracion = catalogo.MODELOS["uav_reco"].foto

    resumen = catalogo.aplicar_referencias(manifiesto, static)

    assert resumen == {"modelos": ["helo_ataque"], "clases": ["fragata"]}
    helo = catalogo.MODELOS["helo_ataque"]
    assert helo.foto == "/static/fotos/ref_helo_ataque.jpg" and helo.credito["obra"] == "Mi-35M de la AMB"
    assert helo.velocidad_kmh == 280  # solo cambia la imagen, no los valores de juego
    assert catalogo.MODELOS["uav_reco"].foto == ilustracion
    fragata = catalogo.como_dict(catalogo.CLASES["fragata"])
    assert fragata["foto"] == "/static/fotos/ref_fragata.jpg" and fragata["credito"]["autor"] == "Fulano"
    assert catalogo.como_dict(catalogo.CLASES["destructor"])["foto"] is None


def test_sin_manifiesto_no_cambia_nada(tmp_path, catalogo_limpio):
    assert catalogo.aplicar_referencias(tmp_path / "no.json", tmp_path) == {"modelos": [], "clases": []}
    assert catalogo.como_dict(catalogo.CLASES["fragata"])["foto"] is None


def test_el_manifiesto_del_repositorio_es_valido():
    """Si ya se descargaron fotos, todas las entradas deben aplicarse (archivo presente y credito completo)."""
    ruta = catalogo.RUTA_REFERENCIAS
    if not ruta.is_file():
        pytest.skip("todavia no hay fotos de referencia descargadas")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    for seccion in ("modelos", "clases"):
        for id_, e in (datos.get(seccion) or {}).items():
            assert catalogo._referencia_valida(e, id_, catalogo.RUTA_FOTOS), id_


def test_la_herramienta_cubre_todas_las_aeronaves_y_buques(herramienta):
    claves = {(s, c) for s, c, _, _ in herramienta.UNIDADES}
    # los que tienen ilustracion o ya la cambiaron por una foto de referencia (los del catalogo propio no van)
    sin_foto_real = {("modelos", m.id) for m in catalogo.MODELOS.values() if not m.id.startswith("u_")
                     and (m.foto.endswith(".svg") or m.foto.startswith("/static/fotos/ref_"))}
    buques = {("clases", c.id) for c in catalogo.CLASES.values() if c.tipo == "naval"}
    assert claves == sin_foto_real | buques


def test_solo_acepta_licencias_libres(herramienta):
    for libre in ("CC BY-SA 4.0", "CC BY 2.0", "CC0", "Public domain", "PD-USGov-Military-Navy", "cc-by-sa-3.0"):
        assert herramienta.licencia_libre(libre), libre
    for no in ("CC BY-NC 2.0", "CC BY-ND 4.0", "CC BY-NC-SA 2.0", "Fair use", ""):
        assert not herramienta.licencia_libre(no), no


def test_lee_candidata_de_commons_y_descarta_formatos_y_licencias(herramienta):
    pagina = {"title": "File:Mi-35M AMB.jpg", "imageinfo": [{
        "mime": "image/jpeg", "url": "https://upload.wikimedia.org/x.jpg", "thumburl": "https://upload.wikimedia.org/t.jpg",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Mi-35M_AMB.jpg", "width": 3000, "height": 2000,
        "extmetadata": {"Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:X">Juan &amp; Ana</a>'},
                        "LicenseShortName": {"value": "CC BY-SA 4.0"},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}}]}
    c = herramienta._candidata(pagina)
    assert c["autor"] == "Juan & Ana" and c["obra"] == "Mi-35M AMB" and c["miniatura"].endswith("t.jpg")
    pagina["imageinfo"][0]["extmetadata"]["LicenseShortName"]["value"] = "CC BY-NC 2.0"
    assert herramienta._candidata(pagina) is None
    pagina["imageinfo"][0].update(mime="image/svg+xml")
    assert herramienta._candidata(pagina) is None


def test_reescribe_solo_su_bloque_de_creditos(herramienta, tmp_path, monkeypatch):
    creditos = tmp_path / "CREDITOS.md"
    creditos.write_text("# Créditos\n\nTexto previo.\n", encoding="utf-8")
    monkeypatch.setattr(herramienta, "CREDITOS", creditos)
    m = {"modelos": {"helo_ataque": _entrada("/static/fotos/ref_helo_ataque.jpg")}, "clases": {}}
    herramienta.escribir_creditos(m)
    herramienta.escribir_creditos(m)  # dos veces: no se duplica
    texto = creditos.read_text(encoding="utf-8")
    assert texto.startswith("# Créditos\n\nTexto previo.") and texto.count(herramienta.INICIO_TABLA) == 1
    assert "`ref_helo_ataque.jpg` | `helo_ataque`" in texto and "Fulano" in texto


def test_el_encuadre_deja_solo_la_pieza_principal(herramienta):
    pytest.importorskip("scipy")
    from PIL import Image, ImageDraw
    alfa = Image.new("L", (200, 100), 0)
    d = ImageDraw.Draw(alfa)
    d.rectangle([10, 10, 150, 60], fill=255)   # el buque
    d.rectangle([170, 70, 185, 80], fill=255)  # una lancha suelta
    limpia = herramienta.solo_lo_principal(alfa)
    assert limpia.getpixel((50, 30)) == 255 and limpia.getpixel((178, 75)) == 0
    assert herramienta.fondo().size == (herramienta.ANCHO, herramienta.ALTO)
