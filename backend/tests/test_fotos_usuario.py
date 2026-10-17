"""Fotos que carga el instructor para un tipo de unidad o una clase (engine/fotos_usuario.py)."""

import base64
import io
import types

import pytest
from PIL import Image

from app.engine import catalogo, fotos_usuario


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(fotos_usuario, "CARPETA", tmp_path / "fotos_usuario")
    monkeypatch.setattr(fotos_usuario, "_rembg", lambda: None)  # sin recorte: rapido y sin modelos descargados
    yield tmp_path
    fotos_usuario.aplicar()


def _imagen(ancho=800, alto=500, formato="JPEG"):
    img = Image.new("RGB", (ancho, alto), (40, 90, 40))
    for x in range(200, 600):
        for y in range(150, 350):
            img.putpixel((x, y), (200, 200, 60))
    buf = io.BytesIO()
    img.save(buf, formato)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def test_guarda_encuadra_y_pone_la_foto_de_un_modelo_y_de_una_clase(carpeta):
    r = fotos_usuario.guardar("modelos", "su30", _imagen(), autor="AMB")
    assert r["metodo"] == "marco" and r["foto"].startswith("/api/catalogo/fotos/archivo/modelos_su30_")
    nombre = r["foto"].rsplit("/", 1)[1]
    ruta = fotos_usuario.archivo(nombre)
    assert ruta is not None and Image.open(ruta).size == (fotos_usuario.ANCHO, fotos_usuario.ALTO)
    d = catalogo.modelo_dict(catalogo.MODELOS["su30"])
    assert d["foto"] == r["foto"] and d["foto_propia"] and d["credito"]["autor"] == "AMB"
    fotos_usuario.guardar("clases", "infanteria", _imagen(formato="PNG"))
    assert catalogo.como_dict(catalogo.CLASES["infanteria"])["foto_propia"]
    # una nueva foto reemplaza a la anterior y borra su archivo
    r2 = fotos_usuario.guardar("modelos", "su30", _imagen())
    assert fotos_usuario.archivo(nombre) is None and catalogo.modelo_dict(catalogo.MODELOS["su30"])["foto"] == r2["foto"]
    # al quitarla vuelve la de referencia
    assert fotos_usuario.quitar("modelos", "su30")
    assert not catalogo.modelo_dict(catalogo.MODELOS["su30"])["foto_propia"]
    assert not fotos_usuario.quitar("modelos", "su30")


def test_con_rembg_recorta_la_unidad(carpeta, monkeypatch):
    def quitar_fondo(img, session=None, post_process_mask=True):
        rgba = img.convert("RGBA")
        alfa = Image.new("L", img.size, 0)
        alfa.paste(255, (200, 150, 600, 350))
        rgba.putalpha(alfa)
        return rgba
    monkeypatch.setattr(fotos_usuario, "_rembg", lambda: (types.SimpleNamespace(remove=quitar_fondo), None))
    r = fotos_usuario.guardar("modelos", "f16", _imagen())
    assert r["metodo"] == "recorte"
    assert fotos_usuario.guardar("modelos", "f16", _imagen(), recortar=False)["metodo"] == "marco"


def test_rechaza_lo_que_no_sirve(carpeta):
    with pytest.raises(fotos_usuario.FotoInvalida):
        fotos_usuario.guardar("modelos", "no_existe", _imagen())
    with pytest.raises(fotos_usuario.FotoInvalida):
        fotos_usuario.guardar("modelos", "su30", "data:image/png;base64," + base64.b64encode(b"no es imagen").decode())
    with pytest.raises(fotos_usuario.FotoInvalida):
        fotos_usuario.guardar("modelos", "su30", "%%%")
    assert fotos_usuario.archivo("../../etc/passwd") is None and fotos_usuario.archivo("x.jpg") is None


def test_api_solo_el_instructor_sube_y_cualquiera_ve_la_foto(api, carpeta):
    prof, alfa = api("prof"), api("alfa")
    cuerpo = {"seccion": "modelos", "id": "buk_m2e", "imagen": _imagen(), "autor": "DIDA", "recortar": False}
    assert alfa.post("/api/catalogo/fotos", json=cuerpo).status_code == 403
    r = prof.post("/api/catalogo/fotos", json=cuerpo)
    assert r.status_code == 200, r.text
    foto = r.json()["foto"]
    assert alfa.get(foto).status_code == 200 and alfa.get(foto).headers["content-type"] == "image/jpeg"
    buk = next(m for m in alfa.get("/api/catalogo").json()["modelos"] if m["id"] == "buk_m2e")
    assert buk["foto"] == foto and buk["foto_propia"]
    assert prof.post("/api/catalogo/fotos", json={**cuerpo, "id": "nada"}).status_code == 400
    assert prof.delete("/api/catalogo/fotos/modelos/buk_m2e").status_code == 200
    assert prof.delete("/api/catalogo/fotos/modelos/buk_m2e").status_code == 404
