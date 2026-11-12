"""Cóndor en una tablet Android (android/ y tools/empaquetar_android.py): sin red y sin armar el paquete completo."""

import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _modulo():
    spec = importlib.util.spec_from_file_location("empaquetar_android", RAIZ / "tools" / "empaquetar_android.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_el_paquete_lleva_lo_necesario_y_nada_de_la_pc():
    m = _modulo()
    rel = {f.relative_to(RAIZ).as_posix() for f in m.archivos()}
    for necesario in ("backend/app/main.py", "backend/app/servidor.py", "backend/alembic.ini", "frontend/index.html",
                      "frontend/static/manifest.json", "android/instalar_condor.sh", "android/condor.sh",
                      "android/requirements-android.txt", "android/LEEME_ANDROID.md"):
        assert necesario in rel, necesario
    assert any(r.startswith("backend/migrations/versions/") for r in rel)
    assert any(r.startswith("backend/data/plantillas_sistema/") for r in rel)
    for r in rel:
        partes = set(r.split("/"))
        assert not partes & {"venv", "__pycache__", "respaldos", "tests"}, r
        assert not r.endswith((".db", ".pyc", ".log")), r


def test_los_paquetes_de_la_tablet_son_los_del_servidor_sin_lo_que_no_se_usa():
    req = lambda p: {l.split("==")[0].split(">=")[0].split("[")[0].strip().lower()  # noqa: E731
                     for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}
    servidor = req(RAIZ / "backend" / "requirements.txt")
    tablet = req(RAIZ / "android" / "requirements-android.txt")
    assert tablet - {"websockets"} <= servidor  # websockets: lo trae uvicorn[standard] en la PC
    assert {"fastapi", "uvicorn", "sqlalchemy", "alembic", "pydantic", "websockets"} <= tablet
    assert not tablet & {"psycopg", "pytest", "httpx"}


def test_los_scripts_van_con_saltos_lf_y_ejecutables(tmp_path):
    """bash en Android no acepta CRLF (git en Windows puede dejarlo en la copia de trabajo): el paquete lo corrige."""
    import zipfile
    m = _modulo()
    sh = tmp_path / "x.sh"
    sh.write_bytes(b"#!/bin/bash\r\necho hola\r\n")
    foto = tmp_path / "f.jpg"
    foto.write_bytes(b"jpg")
    with zipfile.ZipFile(tmp_path / "p.zip", "w") as z:
        m.agregar(z, sh, "C/x.sh")
        m.agregar(z, foto, "C/f.jpg")
    with zipfile.ZipFile(tmp_path / "p.zip") as z:
        assert z.read("C/x.sh") == b"#!/bin/bash\necho hola\n"
        assert (z.getinfo("C/x.sh").external_attr >> 16) & 0o111
        assert z.getinfo("C/f.jpg").compress_type == zipfile.ZIP_STORED


def test_la_pantalla_se_instala_como_aplicacion():
    manifiesto = json.loads((RAIZ / "frontend" / "static" / "manifest.json").read_text(encoding="utf-8"))
    assert manifiesto["display"] == "standalone" and manifiesto["start_url"] == "/"
    for icono in manifiesto["icons"]:
        assert (RAIZ / "frontend" / icono["src"].lstrip("/")).is_file(), icono["src"]
    assert 'rel="manifest"' in (RAIZ / "frontend" / "index.html").read_text(encoding="utf-8")
