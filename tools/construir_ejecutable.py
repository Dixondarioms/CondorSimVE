"""Construye la carpeta portatil de S.I.E.T.E. con SIETE.exe: se copia a cualquier PC con Windows y funciona sin
instalar Python ni nada mas (doble clic en SIETE.exe arranca el servidor para el aula y abre el navegador).

    backend\\venv\\Scripts\\python tools/construir_ejecutable.py                  # dist/SIETE + dist/SIETE_portable_<fecha>.zip
    backend\\venv\\Scripts\\python tools/construir_ejecutable.py --sin-satelite   # sin la foto satelital (~490 MB menos)
    backend\\venv\\Scripts\\python tools/construir_ejecutable.py --sin-datos-mapa # sin datos de mapa (se instalan aparte)
    backend\\venv\\Scripts\\python tools/construir_ejecutable.py --sin-zip        # solo la carpeta

Requiere PyInstaller en el entorno del servidor (backend\\venv\\Scripts\\python -m pip install pyinstaller): el .exe
lleva Python y las dependencias de requirements.txt. El codigo del simulador (backend/app, migraciones, datos) y la
interfaz (frontend) van como archivos junto al .exe, con la misma estructura que el repositorio, de modo que las
rutas del codigo no cambian y la base de datos y los respaldos quedan en SIETE/backend. Ver tools/ejecutable/siete.py.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "tools"))
from empaquetar_datos import CARPETA_SATELITE, CARPETAS, SIN_COMPRIMIR, sha256_de  # noqa: E402

DIST = RAIZ / "dist"
TRABAJO = DIST / "_construccion"
LANZADOR = RAIZ / "tools" / "ejecutable" / "siete.py"
ICONO_PNG = RAIZ / "frontend" / "static" / "img" / "icono_escritorio.png"

# Lo que no viaja en la carpeta portatil: datos del aula de este equipo, pruebas y caches.
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "*.log", "plantillas_usuario")

SPEC = r'''
# Generado por tools/construir_ejecutable.py: no editar a mano.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, get_package_paths

BACKEND = {backend!r}
sys.path.insert(0, BACKEND)

ocultos = ["logging.config", "multipart"]
datos, binarios = [], []
# uvicorn y websockets cargan sus protocolos por nombre; alembic y los dialectos de SQLAlchemy, igual.
for paquete in ("uvicorn", "websockets", "sqlalchemy.dialects", "app"):
    ocultos += collect_submodules(paquete)
ocultos += collect_submodules("alembic", filter=lambda n: ".testing" not in n)
# PostgreSQL (opcional): psycopg y su modulo compilado psycopg_binary, que no se puede importar suelto para
# analizarlo; se agregan sus modulos y las DLL de psycopg_binary.libs (las busca junto al paquete).
d, b, h = collect_all("psycopg")
datos += d; binarios += b; ocultos += h
sitio = Path(get_package_paths("psycopg")[0])
ocultos += ["psycopg_binary", "psycopg_binary._psycopg", "psycopg_binary.pq", "psycopg_binary._uuid", "psycopg_binary.version"]
binarios += [(str(p), "psycopg_binary.libs") for p in (sitio / "psycopg_binary.libs").glob("*.dll")]

a = Analysis([{lanzador!r}], pathex=[BACKEND], binaries=binarios, datas=datos, hiddenimports=ocultos,
             excludes=["tkinter", "pytest", "IPython", "matplotlib", "numpy", "scipy", "rasterio"])
# El paquete `app` se analiza para descubrir sus dependencias, pero no se congela: se usa la copia en
# SIETE/backend/app, cuyas rutas (frontend, datos, migraciones) son las de siempre.
a.pure = [m for m in a.pure if not (m[0] == "app" or m[0].startswith("app."))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SIETE", console=True, icon={icono!r}, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="SIETE", upx=False)
'''

LEEME = """S.I.E.T.E. - Sistema Integral de Entrenamiento Tactico y Estrategico
Carpeta portatil generada el {fecha}

PUESTA EN MARCHA
  1. Copie esta carpeta SIETE completa al equipo que hara de servidor (por ejemplo C:\\SIETE).
     No hace falta instalar Python ni ningun otro programa.
  2. Doble clic en SIETE.exe. Se abre una ventana negra (el servidor) y, a los pocos segundos, el navegador.
     Si Windows pregunta por el cortafuegos, permita el acceso en "redes privadas" para que entren las
     estaciones del aula. Cerrar la ventana negra detiene el servidor.
  3. Las estaciones del aula abren en su navegador la direccion que muestra la ventana negra
     (http://<ip-de-este-equipo>:8000/).

PRIMER ACCESO
  Usuario: admin      Contrasena inicial: siete1234
  Al entrar por primera vez se pide elegir una contrasena nueva.
  Los alumnos piden su cuenta con "Solicitar una cuenta" en la pantalla de acceso y el instructor la
  aprueba en Consola > Usuarios.
  Si se pierde la contrasena de admin: doble clic en "Restablecer admin.cmd".

OPCIONES (en una consola, dentro de esta carpeta)
  SIETE.exe --sin-navegador        solo el servidor
  SIETE.exe --puerto 8080          otro puerto
  SIETE.exe --https                HTTPS con certificado autofirmado (puerto 8443)
  SIETE.exe --solo-este-equipo     sin acceso desde la red local
  SIETE.exe --demo                 crea el escenario de demostracion
  SIETE.exe --restablecer-admin    devuelve admin a la contrasena inicial

DATOS
  La base de datos queda en backend\\simulador_fenix.db y los respaldos automaticos en backend\\respaldos.
  Para pasar a una version nueva, copie esos dos elementos a la carpeta nueva.
{nota_datos}
Manual de usuario (paso a paso, con capturas): docs\\Manual_Usuario_SIETE.pdf
Manual de referencia (instalacion y reglas del motor): docs\\Manual_SIETE.pdf

S.I.E.T.E. fue creado por el Cap. Dixon Malpica, Division de Ingenieria y Desarrollo Aeroespacial (DIDA),
Aviacion Militar Bolivariana.
"""


def paso(texto: str) -> None:
    print(f"\n== {texto}", flush=True)


def tamano(ruta: Path) -> int:
    return sum(p.stat().st_size for p in ruta.rglob("*") if p.is_file()) if ruta.is_dir() else ruta.stat().st_size


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:,.0f} MB".replace(",", ".")


def crear_icono(destino: Path) -> Path:
    from PIL import Image

    Image.open(ICONO_PNG).save(destino, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return destino


def congelar() -> Path:
    """PyInstaller: SIETE.exe + _internal (Python y dependencias) en TRABAJO/dist/SIETE."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit("Falta PyInstaller: backend\\venv\\Scripts\\python -m pip install pyinstaller")
    TRABAJO.mkdir(parents=True, exist_ok=True)
    spec = TRABAJO / "SIETE.spec"
    spec.write_text(SPEC.format(backend=str(RAIZ / "backend"), lanzador=str(LANZADOR),
                                icono=str(crear_icono(TRABAJO / "siete.ico"))), encoding="utf-8")
    subprocess.run([sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm", "--log-level", "WARN",
                    "--distpath", str(TRABAJO / "dist"), "--workpath", str(TRABAJO / "build")], check=True)
    return TRABAJO / "dist" / "SIETE"


def excluidas(sin_satelite: bool, sin_datos_mapa: bool) -> set[str]:
    if sin_datos_mapa:
        return set(CARPETAS)
    return {CARPETA_SATELITE} if sin_satelite else set()


def copiar_proyecto(destino: Path, fuera: set[str]) -> None:
    """Codigo, migraciones, datos e interfaz con la estructura del repositorio (sin base, respaldos ni certificados)."""
    def ignorar(carpeta, nombres):
        rel = Path(carpeta).resolve().relative_to(RAIZ).as_posix()
        saltar = {n for n in nombres if f"{rel}/{n}" in fuera}
        return saltar | set(IGNORAR(carpeta, nombres))

    backend = destino / "backend"
    for nombre in ("app", "migrations", "data"):
        if (RAIZ / "backend" / nombre).is_dir():
            shutil.copytree(RAIZ / "backend" / nombre, backend / nombre, ignore=ignorar)
    shutil.copy2(RAIZ / "backend" / "alembic.ini", backend / "alembic.ini")
    (destino / "frontend").mkdir(parents=True, exist_ok=True)
    shutil.copy2(RAIZ / "frontend" / "index.html", destino / "frontend" / "index.html")
    shutil.copytree(RAIZ / "frontend" / "static", destino / "frontend" / "static", ignore=ignorar)
    for manual in (RAIZ / "docs" / "Manual_Usuario_SIETE.pdf", RAIZ / "docs" / "Manual_SIETE.pdf"):
        if manual.exists():
            (destino / "docs").mkdir(exist_ok=True)
            shutil.copy2(manual, destino / "docs" / manual.name)


def escribir_ayudas(destino: Path, fuera: set[str]) -> None:
    if set(CARPETAS) <= fuera:
        nota = ("  Esta carpeta NO trae los datos de mapa: el mapa saldra vacio. Descomprima el paquete siete_datos.zip\n"
                "  dentro de esta carpeta SIETE (crea frontend\\static\\tiles, tiles_sat, geo y backend\\data\\terreno).\n")
    elif CARPETA_SATELITE in fuera:
        nota = ("  Esta carpeta no trae la foto satelital (capa Satelite vacia). Para agregarla, descomprima el paquete\n"
                "  siete_datos.zip dentro de esta carpeta SIETE.\n")
    else:
        nota = ""
    (destino / "LEEME.txt").write_text(LEEME.format(fecha=date.today().strftime("%d/%m/%Y"), nota_datos=nota),
                                       encoding="utf-8-sig", newline="\r\n")
    (destino / "Restablecer admin.cmd").write_text(
        "@echo off\r\nrem Devuelve la cuenta admin a la contrasena inicial (siete1234); se pide cambiarla al entrar.\r\n"
        "\"%~dp0SIETE.exe\" --restablecer-admin\r\npause\r\n", encoding="ascii")


def probar(carpeta: Path) -> None:
    """Arranca SIETE.exe con una base temporal y comprueba que sirve la interfaz y la API."""
    with socket.socket() as s:  # un puerto libre: otro programa del equipo puede estar usando cualquiera fijo
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    with tempfile.TemporaryDirectory() as tmp:
        entorno = dict(os.environ, SIMULADOR_DB=str(Path(tmp) / "prueba.db"), SIMULADOR_RESPALDO_HORAS="0")
        entorno.pop("SIMULADOR_DATABASE_URL", None)
        proceso = subprocess.Popen([str(carpeta / "SIETE.exe"), "--sin-navegador", "--solo-este-equipo", "--puerto", str(puerto)],
                                   env=entorno, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        try:
            for _ in range(120):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/", timeout=2) as r:
                        assert r.status == 200 and b"S.I.E.T.E." in r.read()
                    break
                except OSError:
                    if proceso.poll() is not None:
                        raise SystemExit("SIETE.exe se cerro al arrancar:\n" + proceso.stdout.read().decode(errors="replace"))
                    time.sleep(0.5)
            else:
                raise SystemExit("SIETE.exe no respondio en 60 s")
            # la base vacia se migro y trae la cuenta admin con la contrasena inicial, que exige cambiarla
            pedido = urllib.request.Request(f"http://127.0.0.1:{puerto}/api/auth/login", method="POST",
                                            data=json.dumps({"username": "admin", "password": "siete1234"}).encode(),
                                            headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(pedido, timeout=10) as r:
                assert json.loads(r.read())["debe_cambiar_clave"] is True
            print("  la interfaz responde y admin entra con la contrasena inicial (y debe cambiarla)")
        except Exception:
            proceso.terminate()
            print(proceso.communicate(timeout=20)[0].decode(errors="replace"))
            raise
        proceso.terminate()
        proceso.wait(timeout=20)


def comprimir(carpeta: Path, ruta_zip: Path) -> Path:
    with zipfile.ZipFile(ruta_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for p in sorted(carpeta.rglob("*")):
            if p.is_file():
                tipo = zipfile.ZIP_STORED if p.suffix.lower() in SIN_COMPRIMIR else zipfile.ZIP_DEFLATED
                z.write(p, Path("SIETE") / p.relative_to(carpeta), compress_type=tipo)
    ruta_zip.with_suffix(".sha256").write_text(f"{sha256_de(ruta_zip)}  {ruta_zip.name}\n", encoding="ascii")
    return ruta_zip


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sin-satelite", action="store_true", help="no incluir la foto satelital (tiles_sat)")
    ap.add_argument("--sin-datos-mapa", action="store_true", help="no incluir ningun dato de mapa")
    ap.add_argument("--sin-zip", action="store_true", help="dejar solo la carpeta dist/SIETE")
    ap.add_argument("--sin-prueba", action="store_true", help="no arrancar SIETE.exe para comprobarlo")
    args = ap.parse_args()
    fuera = excluidas(args.sin_satelite, args.sin_datos_mapa)

    paso("Congelando Python y dependencias con PyInstaller (unos minutos)")
    congelado = congelar()

    paso("Armando la carpeta portatil")
    destino = DIST / "SIETE"
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(congelado, destino)
    copiar_proyecto(destino, fuera)
    escribir_ayudas(destino, fuera)
    print(f"  {destino} ({mb(tamano(destino))})")

    if not args.sin_prueba:
        paso("Probando SIETE.exe")
        probar(destino)

    if not args.sin_zip:
        paso("Comprimiendo")
        sufijo = "_sin_datos" if args.sin_datos_mapa else "_sin_satelite" if args.sin_satelite else ""
        ruta_zip = comprimir(destino, DIST / f"SIETE_portable{sufijo}_{date.today():%Y%m%d}.zip")
        print(f"  {ruta_zip} ({mb(ruta_zip.stat().st_size)})")
    print("\nListo.")


if __name__ == "__main__":
    main()
