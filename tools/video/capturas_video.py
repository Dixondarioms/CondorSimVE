"""Capturas 4K (3840x2160) de la interfaz para el video de presentacion (tools/video/generar_video.py).

Reutiliza los recorridos del manual de usuario (tools/manual/capturas_guia.py) sobre el arnes de pruebas, pero toma
siempre la pantalla entera a escala 2 (1920x1080 CSS -> 4K) y guarda, en vez de recortar, el recuadro que el manual
recortaba: el video lo usa como "foco" para acercar la camara (salida/capturas/focos.json). Quita el rotulo
"ARNES DE PRUEBAS" y le da un nombre al ejercicio de ejemplo.

Requiere el servidor en marcha en 127.0.0.1:8000.

    backend\\venv\\Scripts\\python tools/video/capturas_video.py              # todas
    backend\\venv\\Scripts\\python tools/video/capturas_video.py videowall    # algunas (por nombre de funcion)
"""

import json
import sys
import time
import traceback
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "manual"))
import capturas_guia as guia  # noqa: E402
from navegador import Navegador  # noqa: E402

SALIDA = AQUI / "salida" / "capturas"
FOCOS = SALIDA / "focos.json"
ANCHO, ALTO, ESCALA = 1920, 1080, 2
NOMBRE_EJERCICIO = "Ejercicio Centinela del Llano"

LIMPIAR = """(() => {
  for (const e of [...document.body.children]) if ((e.textContent || '').startsWith('ARNÉS DE PRUEBAS')) e.remove();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = w.nextNode(); t; t = w.nextNode())
    if (t.nodeValue.includes('Ejercicio de ejemplo: piedemonte andino')) t.nodeValue = t.nodeValue.replace('Ejercicio de ejemplo: piedemonte andino', %s);
})()""" % json.dumps(NOMBRE_EJERCICIO)


class NavegadorVideo(Navegador):
    def ir(self, url, listo, extra=1.5):
        super().ir(url, listo, extra)
        self.js(LIMPIAR)


focos: dict = json.loads(FOCOS.read_text(encoding="utf-8")) if FOCOS.exists() else {}


def guardar(n, nombre, recorte=None, marcas=None, margen=6):
    """Pantalla entera en 4K; el recorte del manual queda como foco (en pixeles de la captura)."""
    n.js(LIMPIAR)
    n.captura(SALIDA / f"{nombre}.png")
    if recorte:
        x, y = max(0, recorte["x"] - margen), max(0, recorte["y"] - margen)
        focos[nombre] = [round(v * ESCALA) for v in (x, y, min(ANCHO - x, recorte["w"] + 2 * margen),
                                                     min(ALTO - y, recorte["h"] + 2 * margen))]
    else:
        focos.pop(nombre, None)


guia.guardar = guardar


# ------------------------------------------------------------------ capturas propias del video
def acceso(n):
    n.ir(f"{guia.BASE}/", "!document.getElementById('login').hidden", 2)
    guardar(n, "v_acceso")


def instructor_general(n):
    n.ir(guia.arnes("instructor", lat=8.62, lon=-70.5, zoom=10), guia.LISTA_APP, 4)
    guardar(n, "v_instructor")


def america(n):
    n.ir(guia.arnes("instructor", lat=6, lon=-72, zoom=4), guia.LISTA_APP, 5)
    guardar(n, "v_america")


def venezuela(n):
    n.ir(guia.arnes("instructor", lat=7.6, lon=-66.2, zoom=6), guia.LISTA_APP, 5)
    guardar(n, "v_venezuela")


def bases(n):
    n.ir(guia.arnes("instructor", lat=10.4855, lon=-66.8425, zoom=15), guia.LISTA_APP, 5)
    guardar(n, "v_carlota")


def naval(n):
    n.ir(guia.arnes("azul", "mando", 10.66, -68.0, 11), guia.LISTA_APP, 4)
    guardar(n, "v_naval")


def replay(n):
    for i, instante in enumerate((0.6, 1.4, 2.2, 3.0)):
        n.ir(guia.arnes("instructor", extra=f"&abrir=replay&instante={instante}"),
             guia.LISTA_APP + " && !document.getElementById('replay-anim').hidden", 4)
        guardar(n, f"v_replay_{i}")


PROPIAS = [acceso, instructor_general, america, venezuela, bases, naval, replay]
DEL_MANUAL = [
    guia.pantalla_general, guia.alumno_pantalla, guia.oob_ficha, guia.orden_mover, guia.orden_atacar,
    guia.seleccion_multiple, guia.aviacion_enviar, guia.orden_patrullar, guia.mision_planificar, guia.perfil_vuelo,
    guia.cobertura_radar, guia.cronograma, guia.naval_misiles, guia.naval_desembarcar, guia.orden_interferir,
    guia.mapa_relieve, guia.mapa_graficos, guia.mapa_meteo, guia.consola_agregar, guia.consola_objetivos,
    guia.consola_eventos, guia.consola_usuarios, guia.plantillas, guia.videowall, guia.informe_repeticion,
    guia.informe_dialogos, guia.informe_rubrica, guia.mapa_aerodromo, guia.consola_direccion, guia.acceso_registro,
]


def main() -> None:
    pedidas = set(sys.argv[1:])
    SALIDA.mkdir(parents=True, exist_ok=True)
    n = NavegadorVideo(ANCHO, ALTO, ESCALA)
    fallos = []
    try:
        for f in PROPIAS + DEL_MANUAL:
            if pedidas and f.__name__ not in pedidas:
                continue
            inicio = time.time()
            try:
                f(n)
                print(f"  {f.__name__} ({time.time() - inicio:.0f} s)", flush=True)
            except Exception:  # noqa: BLE001
                fallos.append(f.__name__)
                print(f"  {f.__name__}: ERROR\n{traceback.format_exc()}", flush=True)
            FOCOS.write_text(json.dumps(focos, indent=1), encoding="utf-8")
    finally:
        n.cerrar()
    print(f"{len(fallos)} fallo(s): {', '.join(fallos)}" if fallos else "Todas las capturas listas.")


if __name__ == "__main__":
    main()
