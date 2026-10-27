"""Lanzador del Cóndor en la carpeta portatil (Condor.exe; se construye con tools/construir_ejecutable.py).

    Condor.exe                       arranca el servidor para la red del aula y abre el navegador
    Condor.exe --sin-navegador       solo el servidor (tarea programada, arranque automatico)
    Condor.exe --puerto 8080         otro puerto (tambien SIETE_PUERTO); --https usa un certificado autofirmado
    Condor.exe --solo-este-equipo    no acepta conexiones de la red local
    Condor.exe --restablecer-admin   devuelve la cuenta admin a la contrasena inicial (recuperar el acceso)
    Condor.exe --demo                crea el escenario de demostracion

El codigo del simulador va como fuentes en backend\\app, junto al .exe y no dentro de el: la base de datos,
los respaldos y los certificados quedan en backend\\, igual que en una instalacion con Python, y las rutas del
codigo (frontend, datos de terreno, migraciones) no cambian. Lee SIETE_PUERTO, SIETE_HOST y SIETE_HTTPS de
backend\\.env como iniciar.cmd (sin pisar las variables ya definidas).
"""

import argparse
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path


def carpeta_raiz() -> Path:
    if getattr(sys, "frozen", False):  # Condor.exe
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]  # en el repositorio: python tools/ejecutable/siete.py


def leer_env(ruta: Path) -> None:
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        clave, _, valor = linea.strip().partition("=")
        if clave.upper() in ("SIETE_PUERTO", "SIETE_HOST", "SIETE_HTTPS") and not linea.lstrip().startswith("#"):
            os.environ.setdefault(clave.upper(), valor.strip())


def puerto_en_uso(puerto: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def ips_locales() -> list[str]:
    try:
        datos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return sorted({d[4][0] for d in datos if not d[4][0].startswith("127.")})


def abrir_navegador_al_responder(url: str, puerto: int) -> None:
    def esperar():
        for _ in range(240):  # hasta 2 minutos (la primera vez se migra la base y se carga el terreno)
            if puerto_en_uso(puerto):
                webbrowser.open(url)
                return
            time.sleep(0.5)

    threading.Thread(target=esperar, daemon=True).start()


def main() -> int:
    raiz = carpeta_raiz()
    backend = raiz / "backend"
    leer_env(backend / ".env")
    ap = argparse.ArgumentParser(prog="Condor", description="Condor - Simulador de entrenamiento tactico y estrategico en tiempo real")
    ap.add_argument("--puerto", type=int, default=None)
    ap.add_argument("--https", action="store_true", default=os.environ.get("SIETE_HTTPS") == "1")
    ap.add_argument("--solo-este-equipo", action="store_true", help="escuchar solo en 127.0.0.1")
    ap.add_argument("--sin-navegador", action="store_true")
    ap.add_argument("--restablecer-admin", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if not (backend / "app" / "main.py").exists():
        print(f"No se encuentra el codigo del simulador en {backend / 'app'}.")
        print("Condor.exe debe quedar en la carpeta Condor junto a las carpetas backend y frontend.")
        return 1
    sys.path.insert(0, str(backend))
    os.chdir(backend)

    if args.restablecer_admin:
        from app import restablecer_admin

        sys.argv = ["restablecer_admin"]
        return restablecer_admin.main()
    if args.demo:
        from app import crear_demo

        crear_demo.main()
        return 0

    puerto = args.puerto or int(os.environ.get("SIETE_PUERTO") or (8443 if args.https else 8001))
    host = "127.0.0.1" if args.solo_este_equipo else os.environ.get("SIETE_HOST") or "0.0.0.0"
    esquema = "https" if args.https else "http"
    url = f"{esquema}://localhost:{puerto}/"

    if puerto_en_uso(puerto):
        print(f"El servidor ya esta en marcha en el puerto {puerto}.")
        if not args.sin_navegador:
            webbrowser.open(url)
        return 0

    print("Condor - Simulador de entrenamiento tactico y estrategico en tiempo real")
    print(f"Servidor en {url}")
    if host != "127.0.0.1":
        for ip in ips_locales():
            print(f"  desde la red del aula: {esquema}://{ip}:{puerto}/")
        print("  (si Windows pregunta por el cortafuegos, permita el acceso en redes privadas)")
    if args.https:
        print("HTTPS con certificado autofirmado: el navegador avisara la primera vez.")
    print("Cierre esta ventana para detener el servidor.")
    print()
    if not args.sin_navegador:
        abrir_navegador_al_responder(url, puerto)

    from app import servidor

    sys.argv = ["Condor", "--host", host, "--port", str(puerto)] + (["--https"] if args.https else [])
    return servidor.main()


if __name__ == "__main__":
    try:
        codigo = main()
    except SystemExit as e:
        codigo = e.code if isinstance(e.code, int) else 0
    except Exception:
        traceback.print_exc()
        codigo = 1
    if codigo and getattr(sys, "frozen", False) and "--sin-navegador" not in sys.argv:
        # con doble clic la ventana se cerraria sin dejar leer el error
        print()
        input(f"El Condor termino con un error (codigo {codigo}). Pulse Enter para cerrar.")
    sys.exit(codigo)
