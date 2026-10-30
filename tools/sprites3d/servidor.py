"""Servidor local para renderizar los modelos 3D de aeronaves a imagenes (sprites) para el mapa.

Sirve esta carpeta (render.html, render.mjs y node_modules/three), los modelos .glb indicados y recibe por POST
las imagenes que dibuja el navegador. Solo escucha en 127.0.0.1.

    cd tools/sprites3d && npm install
    python servidor.py --modelo f16=C:\\ruta\\f16a.glb --modelo su30=C:\\ruta\\su33.glb --salida ..\\..\\frontend\\static\\aeronaves

Luego abra http://127.0.0.1:8766/render.html?modelo=f16 (y modelo=su30). La pagina genera 24 rumbos por modelo y los
guarda en --salida. Los .glb NO se copian al repositorio: sus licencias (Sketchfab Standard) no permiten redistribuirlos.
"""

import argparse
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
NOMBRE_OK = re.compile(r"^[a-z0-9_]+\.png$")


def crear_manejador(modelos: dict[str, Path], salida: Path):
    class Manejador(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(AQUI), **kw)

        def do_GET(self):
            ruta = urlparse(self.path).path
            if ruta.startswith("/partes/"):  # partes de un modelo: [{"url", "ext"}] (render.mjs las carga y las junta)
                clave = ruta[len("/partes/"):]
                cuerpo = json.dumps([{"url": f"/modelos/{clave}/{i}", "ext": p.suffix.lower().lstrip(".")}
                                     for i, p in enumerate(modelos.get(clave, []))]).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
                return
            if ruta.startswith("/modelos/"):
                clave, _, n = ruta[len("/modelos/"):].removesuffix(".glb").partition("/")
                partes = modelos.get(clave, [])
                archivo = partes[int(n)] if n.isdigit() and int(n) < len(partes) else (partes[0] if partes and not n else None)
                if archivo is None or not archivo.is_file():
                    return self.send_error(404, "modelo no configurado")
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(archivo.stat().st_size))
                self.end_headers()
                with archivo.open("rb") as f:
                    while trozo := f.read(1 << 20):
                        self.wfile.write(trozo)
                return
            super().do_GET()

        def do_POST(self):
            q = parse_qs(urlparse(self.path).query)
            nombre = (q.get("nombre") or [""])[0]
            if urlparse(self.path).path != "/guardar" or not NOMBRE_OK.match(nombre):
                return self.send_error(400, "nombre no valido")
            cuerpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            salida.mkdir(parents=True, exist_ok=True)
            (salida / nombre).write_bytes(cuerpo)
            self.send_response(204)
            self.end_headers()

        def log_message(self, formato, *args):  # silencioso: se guardan muchos archivos
            if "/guardar" not in (args[0] if args else ""):
                super().log_message(formato, *args)

    return Manejador


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", action="append", default=[], help="id=ruta (glb, stl u obj; varias partes separadas por ;) (repetible)")
    ap.add_argument("--salida", default=str(AQUI / "salida"), help="carpeta donde se guardan los PNG")
    ap.add_argument("--puerto", type=int, default=8766)
    a = ap.parse_args()
    modelos = {}
    for m in a.modelo:
        clave, _, ruta = m.partition("=")
        modelos[clave] = [Path(r) for r in ruta.split(";") if r]
    servidor = ThreadingHTTPServer(("127.0.0.1", a.puerto), crear_manejador(modelos, Path(a.salida)))
    print(f"Servidor en http://127.0.0.1:{a.puerto}/render.html  (salida: {a.salida})")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
