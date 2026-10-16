"""Ejercicio de demostracion de las reparticiones del Estado Mayor (TIEM) y sus cuentas de alumno.

Crea en la base del servidor:
  - el escenario "Demostracion de reparticiones: Pais Azul contra Pais Rojo", desde la plantilla del mapa ficticio,
    con tres unidades mas del Pais Azul para que todas las reparticiones tengan algo que conducir (una compania
    de guerra electronica y un avion de guerra electronica para la C-E, y drones de reconocimiento para la A-2);
    el Pais Rojo lo conduce el adversario automatico (prudente) y el Problema Militar, el calendario D/H y la
    cadena de objetivos se generan solos;
  - una cuenta de alumno del bando azul por reparticion (azul.comandante, azul.jem, azul.a1 ... azul.ce), ya
    aprobada y asignada al escenario, con una contrasena al azar;
y escribe usuarios y contrasenas en un archivo de texto (por omision, en el Escritorio) para entregarlos.
Si las cuentas ya existen, se les pone una contrasena nueva y se asignan al escenario nuevo.

    backend\\venv\\Scripts\\python tools/crear_demo_reparticiones.py [--salida ruta.txt] [--direccion http://ip:8000/]
"""

import argparse
import dataclasses
import os
import secrets
import socket
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.chdir(RAIZ / "backend")
sys.path.insert(0, str(RAIZ / "backend"))

from app import auth  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.engine import plantillas, pmo, puestos  # noqa: E402
from app.models.asignacion import Asignacion  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

PLANTILLA = "teatro_ficticio"
NOMBRE = "Demostración de reparticiones: País Azul contra País Rojo"
BASE = "Base Aérea de Capital Azul"
EXTRA = [  # lo que la plantilla no trae: guerra electronica (C-E) y drones de reconocimiento (A-2)
    dict(nombre="Compañía de Guerra Electrónica azul", bando="azul", clase="guerra_electronica", lat=9.47, lon=-24.18),
    dict(nombre="Avión de guerra electrónica azul", bando="azul", clase="avion_ge", modelo="ge_aereo", aeronaves=1,
         en_tierra=True, base=BASE),
    dict(nombre="Drones de reconocimiento azules", bando="azul", clase="dron_reconocimiento", modelo="uav_reco",
         aeronaves=2, en_tierra=True, base=BASE),
]
PALABRAS = ["Halcon", "Condor", "Aguila", "Radar", "Orion", "Andes", "Llanos", "Caribe", "Sabana", "Relampago",
            "Trueno", "Cumbre", "Horizonte", "Vector", "Rumbo", "Escudo"]


def clave() -> str:
    return f"{secrets.choice(PALABRAS)}-{secrets.randbelow(9000) + 1000}-{secrets.choice(PALABRAS)}"


def ip_local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 80))  # no envia nada: solo elige la interfaz de la red local
            return s.getsockname()[0]
    except OSError:
        return "localhost"


def crear_escenario(db):
    base = plantillas.obtener(PLANTILLA)
    pos = next(u for u in base.unidades if u.nombre == BASE)
    extra = [plantillas.UnidadPlantilla(**{"lat": pos.lat, "lon": pos.lon, **e}) for e in EXTRA]
    demo = dataclasses.replace(base, id="demo_reparticiones", nombre=NOMBRE, unidades=tuple(base.unidades) + tuple(extra),
                               ia_rojo=True, conduce_azul="alumnos")
    plantillas.PLANTILLAS[demo.id] = demo  # solo en este proceso: no queda como plantilla del simulador
    try:
        esc = plantillas.crear_desde_plantilla(db, demo.id)
    finally:
        plantillas.PLANTILLAS.pop(demo.id, None)
    esc.ia_nivel = "prudente"
    pmo.generar(db, esc, ("azul", "rojo"), sobrescribir=True, calendario_auto=True, cadena=True)
    db.commit()
    return esc


def crear_cuentas(db, esc) -> list[tuple[str, str, str]]:
    cuentas = []
    for p in puestos.PUESTOS.values():
        usuario = f"azul.{p.id}"
        contrasena = clave()
        u = db.query(Usuario).filter(Usuario.username == usuario).first()
        if u is None:
            u = Usuario(username=usuario, password_hash=auth.hash_password(contrasena), rol="azul", puesto=p.id)
            db.add(u)
        else:
            u.password_hash, u.rol, u.puesto, u.activo, u.aprobado = auth.hash_password(contrasena), "azul", p.id, True, True
        u.debe_cambiar_clave = False
        db.flush()
        if not db.query(Asignacion).filter_by(usuario_id=u.id, escenario_id=esc.id).first():
            db.add(Asignacion(usuario_id=u.id, escenario_id=esc.id))
        cuentas.append((usuario, contrasena, f"{p.sigla} · {p.nombre}"))
    db.commit()
    return cuentas


def escribir(salida: Path, direccion: str, esc, cuentas) -> None:
    lineas = [
        "S.I.E.T.E. - Ejercicio de demostración de las reparticiones del Estado Mayor",
        f"Creado el {datetime.now():%d/%m/%Y %H:%M}",
        "",
        f"Dirección para entrar desde otra PC:  {direccion}",
        f"Escenario:  {esc.nombre}  (n.º {esc.id})",
        "Bando: Azul (los alumnos). El bando Rojo lo conduce el simulador (adversario automático, nivel prudente).",
        "",
        "Entre con una cuenta por vez. Para pasar a la siguiente: menú del usuario (arriba a la derecha) -> Cerrar sesión.",
        "Si al entrar no aparece el ejercicio, elíjalo en la lista Escenario de la parte superior.",
        "",
        f"{'Repartición':<36}{'Usuario':<20}Contraseña",
        "-" * 76,
    ]
    lineas += [f"{rep:<36}{usuario:<20}{contrasena}" for usuario, contrasena, rep in cuentas]
    lineas += [
        "",
        "Qué mostrar con cada una:",
        "  Comandante y JEM: todas las funciones; deciden, aprueban el plan y confirman el turno (Estoy listo).",
        "  A-1 Personal: efectivos y bajas (pestaña Situación); no ordena unidades.",
        "  A-2 Inteligencia: reconocimiento y drones; apreciación de inteligencia y capacidades del enemigo.",
        "  A-3 Operaciones: aviación de combate, helicópteros y fuerzas de superficie; misiones aéreas.",
        "  A-3 D/A Defensa Aérea: radares, antiaérea e intercepción.",
        "  A-4 Logística: depósito, convoy e ingenieros; apreciación logística.",
        "  C-E Comunicaciones y Electrónica: guerra electrónica (escucha e interferencia).",
        "  En la pestaña TIEM cada uno ve los documentos que le toca redactar.",
        "",
        "Estas contraseñas son solo para la demostración. Para cambiarlas o quitar las cuentas: consola del instructor -> Usuarios.",
    ]
    salida.write_text("\r\n".join(lineas) + "\r\n", encoding="utf-8-sig")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--salida", default=str(Path.home() / "Desktop" / "SIETE - usuarios de demostracion.txt"))
    ap.add_argument("--direccion", default=None, help="direccion del servidor para las otras PC")
    args = ap.parse_args()
    init_db()
    with SessionLocal() as db:
        esc = crear_escenario(db)
        cuentas = crear_cuentas(db, esc)
        direccion = args.direccion or f"http://{ip_local()}:{os.environ.get('SIETE_PUERTO', '8000')}/"
        escribir(Path(args.salida), direccion, esc, cuentas)
        print(f"Escenario {esc.id}: {esc.nombre}; {len(cuentas)} cuentas; detalle en {args.salida}")


if __name__ == "__main__":
    main()
