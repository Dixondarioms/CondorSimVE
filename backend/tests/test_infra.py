"""Respaldo, certificados TLS, migracion de datos existentes y simbolos militares."""

import json
import shutil
import sqlite3
import ssl
import subprocess
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from app import gen_cert, respaldo
from app.db import config_alembic, migrar
from app.engine import catalogo

RAIZ = Path(__file__).resolve().parents[2]


def test_respaldo_consistente_y_con_rotacion(tmp_path):
    origen = tmp_path / "datos.db"
    con = sqlite3.connect(origen)
    con.execute("CREATE TABLE t (x INTEGER)")
    con.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(50)])
    con.commit()
    con.close()

    destino = tmp_path / "copias"
    copias = [respaldo.hacer_respaldo(origen, destino, mantener=2) for _ in range(4)]
    assert [c.exists() for c in copias] == [False, False, True, True]  # rotacion: quedan las 2 ultimas
    restantes = sorted(destino.glob("simulador_*.db"))
    assert restantes == copias[2:]
    assert sqlite3.connect(restantes[-1]).execute("SELECT COUNT(*) FROM t").fetchone()[0] == 50


def test_respaldo_sin_base_no_falla(tmp_path):
    assert respaldo.hacer_respaldo(tmp_path / "no_existe.db", tmp_path / "copias") is None


def test_certificado_autofirmado_valido(tmp_path):
    from cryptography import x509

    cert, clave = gen_cert.generar(["aula.local", "10.1.2.3"], tmp_path)
    ssl.create_default_context(ssl.Purpose.CLIENT_AUTH).load_cert_chain(cert, clave)  # par cert/clave coherente
    c = x509.load_pem_x509_certificate(cert.read_bytes())
    san = c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "localhost" in san.get_values_for_type(x509.DNSName)
    assert "aula.local" in san.get_values_for_type(x509.DNSName)
    ips = {str(i) for i in san.get_values_for_type(x509.IPAddress)}
    assert {"127.0.0.1", "10.1.2.3"} <= ips
    assert (c.not_valid_after_utc - c.not_valid_before_utc).days >= 700


def test_migrar_conserva_los_datos_y_completa_los_nuevos_campos(tmp_path):
    url = f"sqlite:///{tmp_path / 'vieja.db'}"
    command.upgrade(config_alembic(url), "0001")
    motor = create_engine(url)
    with motor.begin() as con:
        con.execute(text("INSERT INTO escenarios (id, nombre, turno_actual, fase, estado, creado_en) "
                         "VALUES (1, 'Viejo', 3, 'decision', 'activo', '2026-01-01')"))
        for uid, tipo in ((1, "terrestre"), (2, "aerea")):
            con.execute(text(
                "INSERT INTO unidades (id, escenario_id, nombre, bando, tipo, echelon, lat, lon, fuerza, "
                "velocidad_kmh, alcance_km, deteccion_km, sidc, estado) VALUES "
                f"({uid}, 1, 'U{uid}', 'azul', '{tipo}', '', 8.0, -70.0, 80, 30, 10, 8, 'SFGP------', 'activa')"))
        for uid, nombre, rol in ((1, "prof", "instructor"), (2, "alfa", "azul"), (3, "obs", "observador")):
            con.execute(text("INSERT INTO usuarios (id, username, password_hash, rol, activo, creado_en) "
                             f"VALUES ({uid}, '{nombre}', 'x', '{rol}', 1, '2026-01-01')"))
    migrar(url)
    with motor.connect() as con:
        esc = con.execute(text("SELECT nombre, turno_actual, clima, azar, semilla, archivado FROM escenarios")).one()
        assert esc[:4] == ("Viejo", 3, "despejado", 0) and esc.semilla > 0 and not esc.archivado
        u = {r.id: r for r in con.execute(text("SELECT id, clase, autonomia_km, combustible, municion, fuerza FROM unidades"))}
        assert (u[1].clase, u[1].autonomia_km) == ("infanteria", 300)
        assert (u[2].clase, u[2].autonomia_km) == ("caza", 1800)
        assert (u[1].combustible, u[1].municion, u[1].fuerza) == (100, 100, 80)
        asignados = {r[0] for r in con.execute(text("SELECT usuario_id FROM asignaciones"))}
        assert asignados == {2, 3}  # los no instructores conservan el acceso que tenian


@pytest.mark.skipif(shutil.which("node") is None, reason="Node no esta instalado")
def test_todos_los_simbolos_del_catalogo_son_validos_en_milsymbol():
    codigos = {
        f"{c.id}/{b}/{e or '-'}": catalogo.generar_sidc(b, c, e)
        for c in catalogo.CLASES.values() for b in ("azul", "rojo") for e in ("", "brigada")
    }
    script = (
        "const ms=require(process.argv[1]);const c=JSON.parse(process.argv[2]);"
        "const malos=Object.entries(c).filter(([k,v])=>!new ms.Symbol(v,{size:20}).isValid(false)).map(([k])=>k);"
        "console.log(JSON.stringify(malos));"
    )
    ms = str(RAIZ / "frontend" / "static" / "vendor" / "milsymbol.js")
    salida = subprocess.run(["node", "-e", script, ms, json.dumps(codigos)], capture_output=True, text=True, check=True)
    assert json.loads(salida.stdout) == []
