"""Video de demostracion de S.I.E.T.E. (MP4, 1920x1080): graba el simulador funcionando con Chrome manejado por CDP
(navegador.py) sobre el arnes de pruebas (datos de ejemplo), con rotulos que explican cada parte, un circulo que marca
cada clic, portada y cierre con el escudo de la DIDA. Se codifica con ffmpeg.

Requiere el servidor en marcha en 127.0.0.1:8000 y ffmpeg en el PATH.

    backend\\venv\\Scripts\\python tools/manual/video_demo.py     # -> dist/video/SIETE_demostracion.mp4
"""

import io
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from navegador import Navegador  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "dist" / "video" / "SIETE_demostracion.mp4"
BASE = "http://127.0.0.1:8000"
ANCHO, ALTO, FPS = 1920, 1080, 25
LISTA = "!document.getElementById('app').hidden && document.querySelectorAll('#oob .oob-item').length > 0 && window.__mapa"
IMG = RAIZ / "frontend" / "static" / "img"
FUENTES = Path(r"C:\Windows\Fonts")
AZUL = (31, 78, 140)


def fuente(tam, negrita=False):
    return ImageFont.truetype(str(FUENTES / ("arialbd.ttf" if negrita else "arial.ttf")), tam)


# ------------------------------------------------------------------ guion
class Guion:
    """Segmentos del video: tarjetas (imagen fija) y grabaciones (cuadros con sus rotulos)."""

    def __init__(self, n: Navegador):
        self.n = n
        self.segmentos = []
        self._rotulos = []

    # --- grabacion
    def escena(self, url: str, listo: str = LISTA, preparar=None):
        self.n.ir(url, listo, 2.5)
        self.n.js("""(() => {
          document.querySelectorAll('body > div').forEach((d) => { if ((d.textContent || '').startsWith('ARNÉS DE PRUEBAS')) d.remove(); });
          const c = document.createElement('div'); c.id = 'cursor-demo';
          c.style.cssText = 'position:fixed;left:-100px;top:-100px;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;'
            + 'border:4px solid #ff3b30;box-shadow:0 0 0 3px rgba(255,255,255,.85),0 0 18px rgba(255,59,48,.8);z-index:99999;'
            + 'pointer-events:none;transition:left .45s ease,top .45s ease,transform .15s;';
          document.body.appendChild(c);
        })()""")
        if preparar:
            preparar()
        self._rotulos = []
        self.n.grabar()

    def rotulo(self, titulo: str, texto: str = ""):
        t = time.time() - self.n._t0
        if self._rotulos:
            self._rotulos[-1][1] = t
        self._rotulos.append([t, None, titulo, texto])

    def corte(self):
        duracion = self.n.detener_grabacion()
        if self._rotulos:
            self._rotulos[-1][1] = duracion
        self.segmentos.append(("grabacion", list(self.n.cuadros), duracion, [tuple(r) for r in self._rotulos]))

    def pausa(self, s):
        self.n.pausa(s)

    # --- cursor visible y clics
    def apuntar(self, x, y, espera=0.55):
        self.n.js(f"(() => {{ const c = document.getElementById('cursor-demo'); c.style.left = '{x}px'; c.style.top = '{y}px'; }})()")
        self.n.pausa(espera)

    def pulsar(self):
        self.n.js("(() => { const c = document.getElementById('cursor-demo'); c.style.transform = 'scale(.6)'; setTimeout(() => c.style.transform = '', 160); })()")

    def clic(self, selector, ctrl=False):
        r = self.n.rect(selector)
        self.apuntar(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
        self.pulsar()
        self.n.clic(selector, ctrl)

    def clic_mapa(self, lat, lon):
        x, y = self.n.punto_mapa(lat, lon)
        self.apuntar(x, y)
        self.pulsar()
        self.n.clic_mapa(lat, lon)

    def volar(self, lat, lon, zoom, segundos):
        self.n.js(f"void __mapa.flyTo([{lat}, {lon}], {zoom}, {{ duration: {segundos} }})")
        self.n.pausa(segundos + 0.6)

    # --- tarjetas
    def tarjeta(self, imagen: Image.Image, segundos: float):
        self.segmentos.append(("tarjeta", imagen, segundos, []))


def arnes(rol="instructor", puesto=None, lat=8.6, lon=-70.57, zoom=10, extra=""):
    p = f"&puesto={puesto}" if puesto else ""
    return f"{BASE}/static/pruebas/arnes.html?rol={rol}{p}&lat={lat}&lon={lon}&zoom={zoom}{extra}"


# ------------------------------------------------------------------ tarjetas (portada y cierre)
def fondo() -> Image.Image:
    im = Image.new("RGB", (ANCHO, ALTO))
    d = ImageDraw.Draw(im)
    for y in range(ALTO):
        k = y / ALTO
        d.line([(0, y), (ANCHO, y)], fill=(int(12 + 18 * k), int(18 + 22 * k), int(36 + 40 * k)))
    return im


def logo(nombre: str, alto: int) -> Image.Image:
    im = Image.open(IMG / nombre).convert("RGB")
    return im.resize((int(im.width * alto / im.height), alto), Image.LANCZOS)


def centrado(d, y, texto, f, color=(255, 255, 255)):
    d.text((ANCHO / 2, y), texto, font=f, fill=color, anchor="mm")


def portada() -> Image.Image:
    im = fondo()
    siete = logo("siete_logo_recortado.jpg", 430)
    im.paste(siete, ((ANCHO - siete.width) // 2, 70))
    d = ImageDraw.Draw(im)
    centrado(d, 560, "S.I.E.T.E.", fuente(86, True))
    centrado(d, 640, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(40), (200, 214, 235))
    centrado(d, 712, "Demostración del simulador", fuente(36, True), (255, 196, 0))
    dida = logo("dida_logo.jpg", 210)
    x = ANCHO // 2 - 470
    im.paste(dida, (x, 800))
    d.text((x + dida.width + 36, 850), "Desarrollado por la División de Ingeniería y Desarrollo Aeroespacial (DIDA)", font=fuente(30, True), fill=(255, 255, 255))
    d.text((x + dida.width + 36, 900), "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana", font=fuente(28), fill=(200, 214, 235))
    return im


def cierre() -> Image.Image:
    im = fondo()
    dida = logo("dida_logo.jpg", 470)
    im.paste(dida, ((ANCHO - dida.width) // 2, 90))
    d = ImageDraw.Draw(im)
    centrado(d, 640, "S.I.E.T.E.", fuente(72, True))
    centrado(d, 712, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(36), (200, 214, 235))
    centrado(d, 800, "Concebido, diseñado y desarrollado en la DIDA", fuente(38, True), (255, 196, 0))
    centrado(d, 858, "División de Ingeniería y Desarrollo Aeroespacial (DIDA) · Aviación Militar Bolivariana", fuente(30), (255, 255, 255))
    centrado(d, 930, "«El infinito es el límite»", fuente(30), (200, 214, 235))
    return im


def separador(titulo: str, subtitulo: str) -> Image.Image:
    im = fondo()
    d = ImageDraw.Draw(im)
    centrado(d, 480, titulo, fuente(70, True))
    centrado(d, 570, subtitulo, fuente(36), (200, 214, 235))
    d.line([(ANCHO / 2 - 220, 625), (ANCHO / 2 + 220, 625)], fill=(255, 196, 0), width=4)
    return im


# ------------------------------------------------------------------ escenas
def escena_acceso(g: Guion):
    g.escena(f"{BASE}/", "!document.getElementById('login').hidden")
    g.rotulo("Acceso al simulador", "Se usa desde el navegador de cada estación del aula, sin internet; cada uno entra con su cuenta.")
    g.pausa(2.5)
    g.clic("#btn-ir-registro")
    g.rotulo("Solicitar una cuenta", "El alumno elige su usuario, su contraseña, su bando y su puesto; el instructor aprueba la solicitud.")
    g.n.valor("#r-user", "carlos.perez")
    g.pausa(0.8)
    g.n.valor("#r-rol", "azul")
    g.n.valor("#r-puesto", "operaciones")
    g.pausa(2.5)
    g.corte()


def escena_mapa(g: Guion):
    g.escena(arnes(lat=4, lon=-75, zoom=4))
    g.rotulo("El terreno de toda América", "Foto satelital, relieve, ríos, fronteras y más de 1 200 aeródromos, servidos por el propio simulador.")
    g.pausa(2.5)
    g.volar(8.9, -69.5, 7, 3.5)
    g.rotulo("Ejercicio en curso", "Unidades de los bandos azul y rojo sobre el terreno real de Venezuela. De lejos, el mapa queda limpio.")
    g.pausa(2)
    g.volar(8.6, -70.55, 10, 3)
    g.rotulo("Al acercarse", "Aparecen los nombres y el anillo de alcance de cada unidad desplegada (azul propias, rojo enemigas).")
    g.pausa(3.5)
    g.corte()


def escena_ordenes(g: Guion):
    g.escena(arnes("azul", "comandante", 8.56, -70.6, 11))
    g.rotulo("El alumno da órdenes", "Selecciona una unidad en el orden de batalla: su ficha muestra fuerza, combustible, munición y alcances.")
    g.clic('#oob .oob-item[data-id="2"]')
    g.n.vista(8.54, -70.6, 11, 1.2)
    g.pausa(1.5)
    g.rotulo("Orden de mover", "Marca los puntos de paso en el mapa; el simulador muestra dónde llegará al final del turno.")
    g.clic('[data-modo="mover"]')
    g.n.js("document.getElementById('sec-orden').scrollIntoView({ block: 'start' })")
    for lat, lon in [(8.545, -70.63), (8.505, -70.6), (8.48, -70.54)]:
        g.clic_mapa(lat, lon)
        g.pausa(0.5)
    g.pausa(1)
    g.clic("#btn-emitir")
    g.rotulo("Orden emitida", "Queda en la cola de órdenes del turno, con quién la dio y desde qué puesto del estado mayor.")
    g.pausa(2.5)
    g.clic('#oob .oob-item[data-id="3"]')
    g.n.vista(8.62, -70.61, 11, 1)
    g.clic('[data-modo="atacar"]')
    g.n.valor("#o-objetivo", "11")
    g.n.js("document.getElementById('sec-orden').scrollIntoView({ block: 'start' })")
    g.rotulo("Orden de atacar", "La artillería elige como objetivo a la infantería enemiga detectada, dentro de su alcance.")
    g.pausa(3.5)
    g.corte()


def escena_aviacion(g: Guion):
    g.escena(arnes("azul", "a3", 8.62, -70.45, 10))
    g.rotulo("Aviación", "El puesto A5 envía aeronaves o drones desde una base: cada modelo con su foto, prestaciones y armamento.")
    g.clic("#btn-enviar-caza")
    g.pausa(4)
    g.n.js("document.getElementById('dlg-aeronaves').close()")
    g.corte()
    g.escena(arnes("azul", "a3", 8.66, -70.5, 11))
    g.rotulo("Misiones aéreas", "El A3 planifica una misión: rol (CAP, interdicción, CAS, SEAD…) y ruta; el grupo la cumple solo, turno a turno.")
    g.clic("#btn-planificar-mision")
    g.n.js("document.getElementById('pm-origen-grupo').click()")
    g.n.valor("#pm-grupo", "8")
    g.n.valor("#pm-rol", "INTERDICCION")
    g.n.vista(8.66, -70.5, 11, 1)
    for lat, lon in [(8.68, -70.55), (8.662, -70.6)]:
        g.clic_mapa(lat, lon)
        g.pausa(0.6)
    g.pausa(3)
    g.corte()


def escena_relieve(g: Guion):
    g.escena(arnes("instructor", lat=8.72, lon=-70.56, zoom=9))
    g.rotulo("El relieve importa", "Las montañas y el horizonte ocultan: un radar solo ve lo que tiene en su línea de vista.")
    g.clic('#oob .oob-item[data-id="18"]')
    g.n.vista(8.68, -70.56, 9, 2)
    g.rotulo("Cobertura real del radar", "Turquesa: hasta dónde ve aviones a 1 500 m; naranja: a baja cota. Este radar, en un valle, queda casi ciego.")
    g.pausa(5)
    g.corte()
    g.escena(arnes("azul", "a3", 8.62, -70.4, 10))
    g.clic('#oob .oob-item[data-id="10"]')
    g.n.js("document.querySelector('.perfil-vuelo').scrollIntoView({ block: 'center' })")
    g.rotulo("Perfil de vuelo", "Alto, medio o rasante: a baja cota se esconde tras el relieve, pero gasta más y queda expuesto a la antiaérea portátil.")
    g.pausa(1.5)
    g.clic('[data-perfil="rasante"]')
    g.pausa(3.5)
    g.corte()


def escena_aerodromos(g: Guion):
    g.escena(arnes("instructor", lat=8.62, lon=-70.3, zoom=10))
    g.rotulo("Aeródromos con su plano real", "Al acercarse, cada aeródromo de América muestra sus pistas, rodajes, plataformas y edificios.")
    g.volar(8.6165, -70.2175, 15, 3.5)
    g.rotulo("Daños visibles", "La base del ejercicio en Barinas: aviones estacionados en la plataforma y cráteres en la pista dañada.")
    g.pausa(3)
    g.corte()
    g.escena(arnes("instructor", lat=4.7016, lon=-74.1469, zoom=12))
    g.rotulo("Cualquier aeropuerto del continente", "El Dorado (Bogotá): el plano se descarga solo al acercarse, así que el mapa sigue siendo ágil.")
    g.volar(4.7016, -74.1469, 14, 2.5)
    g.pausa(2)
    g.corte()


def escena_naval(g: Guion):
    g.escena(arnes("azul", "comandante", 10.66, -67.98, 10))
    g.rotulo("Fuerzas navales", "Grupo naval frente a Puerto Cabello: portaaviones, destructor, submarino y buque de desembarco.")
    g.pausa(2)
    g.clic('#oob .oob-item[data-id="20"]')
    g.clic('[data-modo="lanzar"]')
    g.n.valor("#o-objetivo", "23")
    g.n.vista(10.69, -67.92, 10, 1)
    g.n.js("document.getElementById('sec-orden').scrollIntoView({ block: 'start' })")
    g.rotulo("Misiles de crucero", "El destructor lanza una salva contra la fragata enemiga; la antiaérea y los cazas pueden derribarla.")
    g.pausa(4)
    g.corte()


def escena_instructor(g: Guion):
    g.escena(arnes("instructor", lat=8.6, lon=-70.57, zoom=10))
    g.rotulo("La consola del instructor", "Dirige el ejercicio: clima y zonas meteorológicas, objetivos, eventos, reglas del motor y usuarios.")
    g.clic('[data-pestana="consola"]')
    for titulo in ("meteorología", "objetivos y puntaje", "eventos e informes", "usuarios"):
        g.n.js("(() => { document.querySelectorAll('#pest-consola details').forEach((d) => {"
               f" d.open = d.querySelector('summary').textContent.trim().toLowerCase().startsWith({titulo!r}); }});"
               " const a = document.querySelector('#pest-consola details[open]'); if (a) a.scrollIntoView({ block: 'start' }); })()")
        g.pausa(1.8)
    g.rotulo("Resolver el turno", "Cuando los bandos confirman sus órdenes, el instructor resuelve: movimientos, detecciones y combates a la vez.")
    r = g.n.rect("#btn-avanzar")
    g.apuntar(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
    g.pausa(2.5)
    g.corte()
    g.escena(arnes("instructor", lat=8.62, lon=-70.5, zoom=10, extra="&modo=videowall&vista=completa"))
    g.rotulo("Videowall", "El mapa a pantalla completa para la pantalla grande del centro de operaciones, con turno, reloj y marcador.")
    g.pausa(4.5)
    g.corte()


def escena_informe(g: Guion):
    g.escena(arnes("instructor", lat=8.6, lon=-70.57, zoom=10, extra="&abrir=replay"),
             LISTA + " && !document.getElementById('replay-anim').hidden")
    g.rotulo("Informe posterior (AAR)", "Replay animado del ejercicio: movimientos, combates, estelas de cada unidad y el marcador turno a turno.")
    g.n.valor("#ra-velocidad", "1")
    g.clic("#ra-play")
    g.pausa(7)
    g.corte()
    g.escena(arnes("instructor", extra="&abrir=rubrica"), LISTA + " && document.getElementById('dlg-rubrica').open")
    g.rotulo("Rúbrica de evaluación", "Indicadores por bando, por puesto y por alumno, con observaciones automáticas para la sesión de análisis.")
    g.pausa(2)
    g.n.js("document.getElementById('dlg-rubrica').scrollBy({ top: 500, behavior: 'smooth' })")
    g.pausa(3)
    g.corte()


ESCENAS = [
    ("Acceso", "Cuentas, roles y puestos", escena_acceso),
    ("El mapa", "Terreno real, sin internet", escena_mapa),
    ("Órdenes", "El alumno conduce sus unidades", escena_ordenes),
    ("Aviación", "Envío de aeronaves y misiones", escena_aviacion),
    ("Relieve y sensores", "Línea de vista y perfil de vuelo", escena_relieve),
    ("Aeródromos", "El plano real de cada base", escena_aerodromos),
    ("Fuerzas navales", "Buques y misiles de crucero", escena_naval),
    ("Dirección del ejercicio", "Consola del instructor y videowall", escena_instructor),
    ("Análisis posterior", "Replay y evaluación", escena_informe),
]


# ------------------------------------------------------------------ montaje
def banda(im: Image.Image, titulo: str, texto: str) -> Image.Image:
    """Rotulo inferior: banda oscura translucida con el titulo y la explicacion."""
    im = im.convert("RGB")
    if im.size != (ANCHO, ALTO):
        im = im.resize((ANCHO, ALTO))
    capa = Image.new("RGBA", (ANCHO, 150), (10, 16, 32, 215))
    d = ImageDraw.Draw(capa)
    d.rectangle([0, 0, 10, 150], fill=(255, 196, 0, 255))
    d.text((48, 24), titulo, font=fuente(42, True), fill=(255, 255, 255, 255))
    d.text((48, 86), texto, font=fuente(30), fill=(214, 226, 245, 255))
    im.paste(capa, (0, ALTO - 150), capa)
    return im


def jpeg(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, "JPEG", quality=88)
    return b.getvalue()


def fundido(desde: Image.Image, hasta: Image.Image, n: int):
    for i in range(1, n + 1):
        yield Image.blend(desde, hasta, i / (n + 1))


def montar(segmentos, salida: Path) -> float:
    salida.parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen(
        [shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(salida)],
        stdin=subprocess.PIPE)
    negro = Image.new("RGB", (ANCHO, ALTO))
    total = 0
    ultimo = negro
    for tipo, contenido, duracion, rotulos in segmentos:
        if tipo == "tarjeta":
            for im in fundido(ultimo, contenido, 10):
                ff.stdin.write(jpeg(im))
                total += 1
            fijo = jpeg(contenido)
            for _ in range(int(duracion * FPS)):
                ff.stdin.write(fijo)
                total += 1
            ultimo = contenido
            continue
        cuadros = contenido
        cache = {}
        k = 0
        for i in range(int(duracion * FPS)):
            t = i / FPS
            while k + 1 < len(cuadros) and cuadros[k + 1][0] <= t:
                k += 1
            rot = next(((a, b, c, d) for a, b, c, d in rotulos if a <= t < (b or duracion + 1)), None)
            clave = (k, rot[2] if rot else None)
            if clave not in cache:
                cache.clear()
                base = Image.open(io.BytesIO(cuadros[k][1])) if cuadros else negro
                im = banda(base, rot[2], rot[3]) if rot else base.convert("RGB")
                if i == 0:  # fundido de entrada desde la tarjeta anterior
                    for f in fundido(ultimo, im, 8):
                        ff.stdin.write(jpeg(f))
                        total += 1
                cache[clave] = (im, jpeg(im))
            ultimo, datos = cache[clave]
            ff.stdin.write(datos)
            total += 1
    for im in fundido(ultimo, negro, 15):
        ff.stdin.write(jpeg(im))
        total += 1
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg fallo al codificar el video")
    return total / FPS


def main() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("Falta ffmpeg en el PATH (winget install Gyan.FFmpeg)")
    n = Navegador(ANCHO, ALTO)
    g = Guion(n)
    try:
        g.tarjeta(portada(), 5)
        for titulo, subtitulo, escena in ESCENAS:
            g.tarjeta(separador(titulo, subtitulo), 1.8)
            inicio = time.time()
            escena(g)
            print(f"  {titulo}: {time.time() - inicio:.0f} s", flush=True)
        g.tarjeta(cierre(), 6)
    finally:
        n.cerrar()
    print("Codificando...", flush=True)
    segundos = montar(g.segmentos, SALIDA)
    print(f"{SALIDA} ({SALIDA.stat().st_size // (1024 * 1024)} MB, {segundos / 60:.1f} min)")


if __name__ == "__main__":
    main()
