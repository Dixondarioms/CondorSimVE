"""Video tutorial de S.I.E.T.E. (MP4 2560x1440 o 1920x1080): graba un ejercicio REAL en el simulador, con Chrome manejado
por CDP (navegador.py), mientras una voz natural explica paso a paso como se usa: entrar, crear el escenario, ubicar
unidades y objetivos, dirigir el ejercicio, dar ordenes como alumno, planificar misiones, resolver el turno, el
informe y el videowall. Cada paso del guion lleva su locucion; la grabacion espera a que termine cada frase, asi la
voz y la accion en pantalla van sincronizadas. Un circulo rojo marca el cursor y cada clic.

Requiere: el servidor en marcha (SIETE_URL, por defecto http://127.0.0.1:8002), ffmpeg en el PATH, edge-tts
(voces neuronales de Microsoft; internet solo para la voz) y un archivo JSON con las cuentas de prueba
(SIETE_CUENTAS): {"instructor": {"usuario": "...", "clave": "..."}, "alumno": {"usuario": "...", "clave": "..."}}.
El instructor crea un escenario nuevo desde la plantilla de demostracion; el alumno debe ser del bando azul.
Las contrasenas nunca se muestran ni se escriben en el video (el campo las oculta).

    set SIETE_URL=http://127.0.0.1:8002& set SIETE_CUENTAS=C:\\ruta\\cuentas.json
    backend\\venv\\Scripts\\python tools/manual/video_tutorial.py                 # 2K -> dist/video/2K/SIETE_3_tutorial_2K.mp4
    backend\\venv\\Scripts\\python tools/manual/video_tutorial.py --1080          # 1920x1080
    backend\\venv\\Scripts\\python tools/manual/video_tutorial.py --solo=acceso,crear --rapido --sin-voz   # prueba
    backend\\venv\\Scripts\\python tools/manual/video_tutorial.py --voz=es-MX-JorgeNeural --velocidad=+10%
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from navegador import Navegador  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
BASE = os.environ.get("SIETE_URL", "http://127.0.0.1:8002")
CUENTAS = Path(os.environ.get("SIETE_CUENTAS") or RAIZ / "backend" / "cuentas_video.json")
DESTINO = RAIZ / "dist" / "video"
TRABAJO = DESTINO / "trabajo" / "tutorial"
VOCES = TRABAJO / "voces"
IMG = RAIZ / "frontend" / "static" / "img"
FUENTES = Path(r"C:\Windows\Fonts")
FFMPEG = shutil.which("ffmpeg") or str(next(Path.home().glob(
    "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/*/bin/ffmpeg.exe"), "ffmpeg"))

# cuadro: el navegador (1920 x 945 px CSS) ocupa lo de arriba; abajo, una banda limpia para los subtitulos
VISTA_W, VISTA_H, BANDA = 1920, 930, 150
FPS = 25
E = 4 / 3  # 2K; --1080: 1
ANCHO, ALTO = 2560, 1440
AMBAR = (255, 196, 0)
VOZ = "es-VE-SebastianNeural"
VELOCIDAD = "+8%"
RAPIDO = False
SIN_VOZ = False
# como se pronuncian las siglas (solo en la voz; el subtitulo conserva la escritura)
PRONUNCIACION = {"S.I.E.T.E.": "Siete", "SIETE": "Siete", "TIEM": "Tiem", "PRO": "pe erre o", "OTA": "ota",
                 "PMO": "pe eme o", "A-3": "A tres", "A-2": "A dos", "A-4": "A cuatro", "A-1": "A uno", "CAP": "cap",
                 "DIDA": "Dida", "IA": "inteligencia artificial", "Su-30": "Sujói treinta", "F-16": "efe dieciséis",
                 "km": "kilómetros", "2K": "dos ka"}
LISTA_APP = "!document.getElementById('app').hidden && window.__mapa && document.querySelectorAll('#oob .oob-item').length > 0"
LLANOS = (8.62, -70.6)


def px(v: float) -> int:
    return round(v * E)


def fuente(tam, negrita=False):
    return ImageFont.truetype(str(FUENTES / ("arialbd.ttf" if negrita else "arial.ttf")), px(tam))


# ------------------------------------------------------------------ voz
def hablado(texto: str) -> str:
    for escrito, dicho in PRONUNCIACION.items():
        texto = re.sub(rf"(?<![\w-]){re.escape(escrito)}(?![\w-])", dicho, texto)
    return texto


def _firma(texto: str) -> str:
    return hashlib.sha1(f"{VOZ}|{VELOCIDAD}|{hablado(texto)}".encode()).hexdigest()[:16]


def _duracion_wav(ruta: Path) -> float:
    with wave.open(str(ruta)) as w:
        return w.getnframes() / w.getframerate()


async def _sintetizar(textos: list[str]) -> None:
    import edge_tts

    VOCES.mkdir(parents=True, exist_ok=True)
    limite = asyncio.Semaphore(4)

    async def una(texto: str) -> None:
        f = _firma(texto)
        wav, meta = VOCES / f"{f}.wav", VOCES / f"{f}.json"
        if wav.exists() and meta.exists():
            return
        mp3 = VOCES / f"{f}.mp3"
        async with limite:
            for intento in range(4):
                try:
                    com = edge_tts.Communicate(hablado(texto), VOZ, rate=VELOCIDAD, boundary="SentenceBoundary")
                    audio, limites = bytearray(), []
                    async for trozo in com.stream():
                        if trozo["type"] == "audio":
                            audio += trozo["data"]
                        elif trozo["type"] in ("SentenceBoundary", "WordBoundary"):
                            limites.append({"inicio": trozo["offset"] / 1e7, "duracion": trozo["duration"] / 1e7,
                                            "texto": trozo["text"]})
                    mp3.write_bytes(bytes(audio))
                    break
                except Exception:  # cortes de red: se reintenta
                    if intento == 3:
                        raise
                    await asyncio.sleep(2 + 3 * intento)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(wav)], check=True)
        meta.write_text(json.dumps({"texto": texto, "frases": limites}, ensure_ascii=False), encoding="utf-8")

    await asyncio.gather(*(una(t) for t in dict.fromkeys(textos)))


class Locucion:
    """Las frases sintetizadas: duracion y audio de cada texto (o estimadas, con --sin-voz)."""

    def __init__(self, textos: list[str]):
        self.textos = list(dict.fromkeys(textos))
        if not SIN_VOZ:
            asyncio.run(_sintetizar(self.textos))

    def duracion(self, texto: str) -> float:
        if SIN_VOZ:
            return max(1.5, len(texto) / 16.5)
        return _duracion_wav(VOCES / f"{_firma(texto)}.wav")

    def audio(self, texto: str) -> np.ndarray:
        if SIN_VOZ:
            return np.zeros(int(self.duracion(texto) * 44100), dtype=np.int16)
        with wave.open(str(VOCES / f"{_firma(texto)}.wav")) as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)

    def subtitulos(self, texto: str) -> list[tuple[float, float, str]]:
        """(inicio, fin, frase) dentro del audio: una entrada por oracion, segun los limites que da la voz."""
        total = self.duracion(texto)
        frases = [p for p in re.split(r"(?<=[.:;?!])\s+(?=[A-ZÁÉÍÓÚÑ¿¡«])", texto.strip()) if p]
        meta = VOCES / f"{_firma(texto)}.json"
        limites = json.loads(meta.read_text(encoding="utf-8")).get("frases", []) if meta.exists() and not SIN_VOZ else []
        if len(limites) == len(frases) and len(frases) > 1:
            out = []
            for i, (f, l) in enumerate(zip(frases, limites)):
                fin = limites[i + 1]["inicio"] if i + 1 < len(limites) else total
                out.append((l["inicio"], fin, f))
            return out
        if len(frases) > 1:  # sin limites: proporcional al largo
            out, t = [], 0.0
            n = sum(len(f) for f in frases)
            for f in frases:
                d = total * len(f) / n
                out.append((t, t + d, f))
                t += d
            return out
        return [(0.0, total, texto)]


# ------------------------------------------------------------------ navegador que guarda los cuadros en disco
class Grabador(Navegador):
    """Como Navegador, pero cada cuadro de la grabacion va a un archivo (la RAM no alcanza para 2K)."""

    def __init__(self, carpeta: Path, *a, **k):
        self.carpeta = carpeta
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self._n = 0
        super().__init__(*a, **k)
        # la aplicacion real no expone el mapa: igual que el arnes, un gancho de Leaflet lo deja en window.__mapa
        self.enviar("Page.enable")  # sin esto, el guion no se inyecta en las paginas nuevas
        self.enviar("Page.addScriptToEvaluateOnNewDocument", {"source": """(() => { let _L;
          Object.defineProperty(window, 'L', { configurable: true, get() { return _L; }, set(v) { _L = v;
            try { if (v && v.Map && v.Map.addInitHook) v.Map.addInitHook(function () { window.__mapa = this; }); } catch (e) {} } }); })()"""})

    def _evento(self, msj: dict) -> None:
        if msj.get("method") == "Page.screencastFrame":
            p = msj["params"]
            if self._t0 is not None:
                ruta = self.carpeta / f"c{self._n:06d}.jpg"
                ruta.write_bytes(__import__("base64").b64decode(p["data"]))
                self.cuadros.append((time.time() - self._t0, ruta))
                self._n += 1
            self._id += 1
            self.ws.send(json.dumps({"id": self._id, "method": "Page.screencastFrameAck", "params": {"sessionId": p["sessionId"]}}))
        else:
            super()._evento(msj)

    def grabar(self, calidad=80) -> None:
        for viejo in self.carpeta.glob("c*.jpg"):
            viejo.unlink()
        self._n = 0
        self.cuadros, self._t0 = [], time.time()
        self.enviar("Page.startScreencast", {"format": "jpeg", "quality": calidad, "everyNthFrame": 2})

    def tiempo(self) -> float:
        return time.time() - self._t0 if self._t0 is not None else 0.0


# ------------------------------------------------------------------ tarjetas (portada, separadores, cierre)
def fondo() -> Image.Image:
    im = Image.new("RGB", (ANCHO, ALTO))
    d = ImageDraw.Draw(im)
    for y in range(ALTO):
        k = y / ALTO
        d.line([(0, y), (ANCHO, y)], fill=(int(12 + 18 * k), int(18 + 22 * k), int(36 + 40 * k)))
    return im


def logo(nombre: str, alto: int) -> Image.Image:
    im = Image.open(IMG / nombre)
    im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
    alto = px(alto)
    return im.resize((int(im.width * alto / im.height), alto), Image.LANCZOS)


def pegar(fondo_im: Image.Image, im: Image.Image, xy) -> None:
    fondo_im.paste(im, xy, im if im.mode == "RGBA" else None)


def centrado(d, y, texto, f, color=(255, 255, 255)):
    d.text((ANCHO / 2, px(y)), texto, font=f, fill=color, anchor="mm")


def portada() -> Image.Image:
    im = fondo()
    aguila = logo("siete_aguila.png", 330)
    pegar(im, aguila, ((ANCHO - aguila.width) // 2, px(36)))
    d = ImageDraw.Draw(im)
    centrado(d, 435, "S.I.E.T.E.", fuente(80, True))
    centrado(d, 510, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(38), (200, 214, 235))
    centrado(d, 572, "Tutorial: cómo se usa el simulador, paso a paso", fuente(40, True), AMBAR)
    dida = logo("dida_logo_redondo.png", 180)
    x = ANCHO // 2 - px(470)
    pegar(im, dida, (x, px(640)))
    xt = x + dida.width + px(36)
    d.text((xt, px(668)), "División de Ingeniería y Desarrollo Aeroespacial (DIDA)", font=fuente(30, True), fill=(255, 255, 255))
    d.text((xt, px(714)), "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana", font=fuente(28), fill=(200, 214, 235))
    d.text((xt, px(760)), "Grabado sobre un ejercicio real del simulador", font=fuente(30, True), fill=AMBAR)
    return im


def cierre() -> Image.Image:
    im = fondo()
    aguila = logo("siete_aguila.png", 300)
    dida = logo("dida_logo_redondo.png", 300)
    hueco = px(70)
    x = (ANCHO - aguila.width - dida.width - hueco) // 2
    pegar(im, aguila, (x, px(50)))
    pegar(im, dida, (x + aguila.width + hueco, px(50)))
    d = ImageDraw.Draw(im)
    centrado(d, 450, "S.I.E.T.E.", fuente(72, True))
    centrado(d, 518, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(36), (200, 214, 235))
    centrado(d, 600, "Desarrollado en la División de Ingeniería y Desarrollo Aeroespacial (DIDA)", fuente(38, True), AMBAR)
    centrado(d, 655, "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana", fuente(30))
    centrado(d, 730, "«El infinito es el límite»", fuente(34, True), (200, 214, 235))
    return im


def separador(numero: int, titulo: str, subtitulo: str) -> Image.Image:
    im = fondo()
    aguila = logo("siete_aguila.png", 200)
    pegar(im, aguila, ((ANCHO - aguila.width) // 2, px(100)))
    d = ImageDraw.Draw(im)
    centrado(d, 350, f"PARTE {numero}", fuente(30, True), AMBAR)
    centrado(d, 420, titulo, fuente(66, True))
    centrado(d, 500, subtitulo, fuente(36), (200, 214, 235))
    d.line([(ANCHO / 2 - px(240), px(555)), (ANCHO / 2 + px(240), px(555))], fill=AMBAR, width=px(4))
    return im


# ------------------------------------------------------------------ composicion de cada cuadro
SUB_FUENTE, SUB_LINEA, SUB_ANCHO = 34, 44, 105


def banda_base(capitulo: str) -> Image.Image:
    """La banda inferior sin el subtitulo: fondo, linea ambar, icono y el nombre de la parte."""
    im = Image.new("RGB", (ANCHO, px(BANDA)), (14, 22, 44))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, ANCHO, px(3)], fill=AMBAR)
    icono = logo("siete_icono_128.png", 40)
    pegar(im, icono, (px(28), px(14)))
    d.text((px(78), px(34)), capitulo, font=fuente(22, True), fill=AMBAR, anchor="lm")
    d.text((ANCHO - px(30), px(34)), "S.I.E.T.E. · DIDA", font=fuente(20), fill=(170, 186, 210), anchor="rm")
    return im


def componer(cuadro: Image.Image | None, banda: Image.Image, subtitulo: str | None) -> Image.Image:
    im = Image.new("RGB", (ANCHO, ALTO), (10, 14, 26))
    if cuadro is not None:
        if cuadro.size != (ANCHO, ALTO - px(BANDA)):
            cuadro = cuadro.resize((ANCHO, ALTO - px(BANDA)), Image.LANCZOS)
        im.paste(cuadro, (0, 0))
    im.paste(banda, (0, ALTO - px(BANDA)))
    if subtitulo:
        d = ImageDraw.Draw(im)
        lineas = textwrap.wrap(subtitulo, width=SUB_ANCHO)[:2]
        f = fuente(SUB_FUENTE)
        y0 = ALTO - px(BANDA) + px(54)
        for i, linea in enumerate(lineas):
            d.text((ANCHO / 2, y0 + px(SUB_LINEA) * i + px(SUB_LINEA // 2)), linea, font=f, fill=(255, 255, 255), anchor="mm")
    return im


def tarjeta_con_subtitulo(tarjeta: Image.Image, subtitulo: str | None) -> Image.Image:
    im = tarjeta.copy()
    if subtitulo:
        d = ImageDraw.Draw(im, "RGBA")
        lineas = textwrap.wrap(subtitulo, width=SUB_ANCHO)[:3]
        f = fuente(SUB_FUENTE)
        alto = px(24 + SUB_LINEA * len(lineas))
        y0 = ALTO - px(40) - alto
        d.rounded_rectangle([px(90), y0, ANCHO - px(90), ALTO - px(40)], radius=px(14), fill=(0, 0, 0, 190))
        for i, linea in enumerate(lineas):
            d.text((ANCHO / 2, y0 + px(12 + SUB_LINEA // 2 + SUB_LINEA * i)), linea, font=f, fill=(255, 255, 255), anchor="mm")
    return im


# ------------------------------------------------------------------ el guion en marcha
class Tutorial:
    """Primera pasada (recolectar): solo reune los textos. Segunda (grabar): graba cada escena y la codifica.

    Las escenas usan g.paso(texto, accion) y g.hacer(accion); todo lo que toca el navegador va dentro de las acciones,
    que en la primera pasada no se ejecutan."""

    def __init__(self, modo: str, locucion: Locucion | None = None):
        self.modo = modo
        self.loc = locucion
        self.textos: list[str] = []
        self.clips: list[Path] = []
        self.ni: Grabador | None = None  # navegador del instructor
        self.na: Grabador | None = None  # navegador del alumno
        self.n: Grabador | None = None  # el que se esta grabando
        self.capitulo = ""
        self.escena_actual = ""
        self.pasos: list[tuple[float, str]] = []
        self.datos: dict = {}  # lo que una escena deja para otra (id del escenario...)
        self.numero = 0
        self.cuentas: dict = {}

    # --- navegadores
    @property
    def grabando(self) -> bool:
        return self.modo == "grabar"

    def instructor(self) -> Grabador:
        if self.ni is None:
            self.ni = Grabador(TRABAJO / "cuadros_i", VISTA_W, VISTA_H, escala=E)
        return self.ni

    def alumno(self) -> Grabador:
        if self.na is None:
            self.na = Grabador(TRABAJO / "cuadros_a", VISTA_W, VISTA_H, escala=E)
        return self.na

    def cerrar(self) -> None:
        for n in (self.ni, self.na):
            if n is not None:
                n.cerrar()

    # --- escenas
    def comenzar(self, nombre: str, quien: str, sesion: bool = True) -> None:
        """Empieza a grabar una escena en el navegador del instructor ("i") o del alumno ("a"). Con `sesion`, antes se
        asegura (sin grabar) de que ese navegador tenga la sesion abierta y el escenario del tutorial elegido."""
        self.escena_actual = nombre
        self.pasos = []
        if not self.grabando:
            return
        self.n = self.instructor() if quien == "i" else self.alumno()
        if sesion:
            self.asegurar_sesion(quien)
        self.n.grabar()
        print(f"  grabando {nombre}...", flush=True)

    def asegurar_sesion(self, quien: str) -> None:
        n = self.n
        if not n.js("!!(document.getElementById('app') && !document.getElementById('app').hidden && window.__mapa)"):
            self.entrar(self.cuentas["instructor" if quien == "i" else "alumno"], mostrar=False)
        self.escenario(self.id_escenario())

    def id_escenario(self) -> int:
        """El escenario del tutorial: el que creo la parte 2 o, si se graba una parte suelta, el ultimo de demostracion."""
        if "escenario" not in self.datos:
            valor = self.n.js("""(() => { const os = [...document.getElementById('escenario').options].filter((o) => /demo/i.test(o.textContent));
              return os.length ? String(Math.max(...os.map((o) => parseInt(o.value, 10)))) : null; })()""")
            if not valor:
                raise SystemExit("No hay un escenario de demostración: grabe antes la parte 2 (crear)")
            self.datos["escenario"] = int(valor)
        return self.datos["escenario"]

    def terminar(self) -> None:
        if not self.grabando:
            return
        self.n.pausa(0.8)
        duracion = self.n.detener_grabacion()
        self.codificar(self.escena_actual, list(self.n.cuadros), duracion, self.pasos)

    def tarjeta(self, nombre: str, imagen_fn, textos: list[str], antes=0.8, despues=0.8) -> None:
        self.textos += textos
        self.escena_actual = nombre
        if not self.grabando:
            return
        t, pasos = antes, []
        for texto in textos:
            pasos.append((t, texto))
            t += self.loc.duracion(texto) + 0.5
        ruta = TRABAJO / f"{nombre}.jpg"
        imagen_fn().save(ruta, "JPEG", quality=92)
        self.codificar(nombre, [(0.0, ruta)], t + despues, pasos, tarjeta=True)

    def paso(self, texto: str, accion=None, extra: float = 0.4) -> None:
        """Narra `texto` mientras se ejecuta `accion`; sigue cuando terminaron las dos."""
        self.textos.append(texto)
        if not self.grabando:
            return
        inicio = self.n.tiempo()
        self.pasos.append((inicio, texto))
        if accion:
            accion()
        fin = inicio + self.loc.duracion(texto) + extra
        if (falta := fin - self.n.tiempo()) > 0:
            self.n.pausa(falta)

    def hacer(self, accion, espera: float = 0.0) -> None:
        if self.grabando:
            accion()
            if espera:
                self.n.pausa(espera)

    # --- ayudas de pantalla (solo dentro de acciones)
    def cursor_listo(self) -> None:
        self.n.js("""(() => {
          if (document.getElementById('cursor-demo')) return;
          const c = document.createElement('div'); c.id = 'cursor-demo';
          c.style.cssText = 'position:fixed;left:-100px;top:-100px;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;'
            + 'border:4px solid #ff3b30;box-shadow:0 0 0 3px rgba(255,255,255,.85),0 0 18px rgba(255,59,48,.8);z-index:99999;'
            + 'pointer-events:none;transition:left .45s ease,top .45s ease,transform .15s;';
          document.body.appendChild(c);
        })()""")

    def apuntar(self, x: float, y: float, espera=0.55) -> None:
        self.cursor_listo()
        self.n.js(f"(() => {{ const c = document.getElementById('cursor-demo'); c.style.left = '{x}px'; c.style.top = '{y}px'; }})()")
        self.n.pausa(espera)

    def pulsar(self) -> None:
        self.n.js("(() => { const c = document.getElementById('cursor-demo'); c.style.transform = 'scale(.55)'; setTimeout(() => c.style.transform = '', 180); })()")
        self.n.pausa(0.2)

    def clic(self, selector: str, ctrl=False, espera=0.5) -> None:
        r = self.n.rect(selector)
        self.apuntar(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
        self.pulsar()
        self.n.clic(selector, ctrl)
        self.n.pausa(espera)

    def clic_texto(self, selector_lista: str, texto: str, espera=0.5) -> None:
        """Clic en el primer elemento de `selector_lista` cuyo texto contiene `texto`."""
        sel = self.n.js(f"""(() => {{
          const es = [...document.querySelectorAll({json.dumps(selector_lista)})];
          const i = es.findIndex((e) => e.textContent.trim().toLowerCase().includes({json.dumps(texto.lower())}));
          if (i < 0) throw new Error('no hay ' + {json.dumps(texto)});
          es[i].setAttribute('data-video', 'x'); return true; }})()""")
        assert sel
        self.clic("[data-video='x']", espera=espera)
        self.n.js("document.querySelectorAll('[data-video]').forEach((e) => e.removeAttribute('data-video'))")

    def clic_mapa(self, lat: float, lon: float, espera=0.5) -> None:
        """Clic en un punto del mapa. Se dispara como evento de Leaflet (con la escala 2K del navegador, el raton de
        CDP no llega al mapa); el circulo del cursor muestra el clic."""
        x, y = self.n.punto_mapa(lat, lon)
        self.apuntar(x, y)
        self.pulsar()
        self.n.js(f"""(() => {{ const ll = L.latLng({lat}, {lon}); const cp = __mapa.latLngToContainerPoint(ll);
          __mapa.fire('click', {{ latlng: ll, containerPoint: cp, layerPoint: __mapa.containerPointToLayerPoint(cp),
            originalEvent: new MouseEvent('click', {{ bubbles: true, clientX: {x}, clientY: {y} }}) }}); }})()""")
        self.n.pausa(espera)

    def escribir(self, selector: str, texto: str, por_letra=True) -> None:
        """Escribe en un campo (letra a letra, para que se vea) y avisa a la pagina."""
        r = self.n.rect(selector)
        self.apuntar(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2, 0.3)
        self.n.js(f"document.querySelector({json.dumps(selector)}).focus()")
        if por_letra:
            for i in range(1, len(texto) + 1):
                self.n.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); e.value = {json.dumps(texto[:i])};"
                          f" e.dispatchEvent(new Event('input', {{ bubbles: true }})); }})()")
                self.n.pausa(0.045)
        self.n.valor(selector, texto)

    def elegir(self, selector: str, valor) -> None:
        r = self.n.rect(selector)
        self.apuntar(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2, 0.35)
        self.pulsar()
        self.n.valor(selector, valor)
        self.n.pausa(0.4)

    def volar(self, lat: float, lon: float, zoom: float, segundos: float = 2.5) -> None:
        self.n.js(f"void __mapa.flyTo([{lat}, {lon}], {zoom}, {{ duration: {segundos} }})")
        self.n.pausa(segundos + 0.5)

    def encuadrar_unidades(self, segundos: float = 2.5, zoom_max: int = 10) -> None:
        """Vuela hasta abarcar todas las unidades dibujadas en el mapa."""
        self.n.js(f"""(() => {{ const ps = []; __mapa.eachLayer((l) => {{ if (l instanceof L.Marker) ps.push(l.getLatLng()); }});
          if (ps.length) __mapa.flyToBounds(L.latLngBounds(ps), {{ padding: [60, 60], maxZoom: {zoom_max}, duration: {segundos} }}); }})()""")
        self.n.pausa(segundos + 0.6)

    def desplazar_panel(self, selector: str, bloque="start") -> None:
        self.n.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (e) e.scrollIntoView({{ block: '{bloque}', behavior: 'smooth' }}); }})()")
        self.n.pausa(0.7)

    def consola(self, *secciones: str) -> None:
        """Pestaña Consola con solo esas secciones desplegadas (por el inicio de su titulo)."""
        self.clic('[data-pestana="consola"]', espera=0.3)
        nombres = [s.lower() for s in secciones]
        self.n.js("(() => { const ns = %s; document.querySelectorAll('#pest-consola details').forEach((d) => {"
                  " const t = d.querySelector('summary').textContent.trim().toLowerCase(); d.open = ns.some((s) => t.startsWith(s)); });"
                  " document.getElementById('panel-izq').scrollTop = 0;"
                  " const abierta = document.querySelector('#pest-consola details[open]');"
                  " if (abierta) abierta.scrollIntoView({ block: 'start' }); })()" % json.dumps(nombres))
        self.n.pausa(0.6)

    def entrar(self, cuenta: dict, mostrar=True) -> None:
        """Inicia sesion con la cuenta (la contraseña va al campo oculto, sin mostrarse)."""
        n = self.n
        n.ir(f"{BASE}/", "!document.getElementById('login').hidden", 1.0)
        self.cursor_listo()
        if mostrar:
            self.escribir("#l-user", cuenta["usuario"])
            r = n.rect("#l-pass")
            self.apuntar(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2, 0.3)
            n.valor("#l-pass", cuenta["clave"])
            n.pausa(0.6)
            self.clic("#login-form button[type=submit]", espera=0.2)
        else:
            n.valor("#l-user", cuenta["usuario"])
            n.valor("#l-pass", cuenta["clave"])
            n.js("document.getElementById('login-form').requestSubmit()")
        n.esperar("!document.getElementById('app').hidden && window.__mapa", 30)
        n.pausa(1.5)

    def escenario(self, id_: int) -> None:
        """Elige el escenario en la cabecera y espera a que cargue (el orden de batalla cambia)."""
        if self.n.js("document.getElementById('escenario').value") == str(id_):
            return
        firma = self.n.js("document.getElementById('oob').textContent.length + ':' + document.getElementById('h-turno').textContent")
        self.elegir("#escenario", str(id_))
        self.n.esperar(f"document.getElementById('oob').textContent.length + ':' + document.getElementById('h-turno').textContent !== {json.dumps(firma)}", 15)
        self.n.esperar(LISTA_APP, 30)
        self.n.pausa(1.2)

    # --- codificacion de una escena
    def codificar(self, nombre: str, cuadros: list, duracion: float, pasos: list, tarjeta=False) -> None:
        self.numero += 1
        clip = TRABAJO / f"clip_{self.numero:03d}_{nombre}.mp4"
        subt: list[tuple[float, float, str]] = []
        for inicio, texto in pasos:
            for a, b, frase in self.loc.subtitulos(texto):
                subt.append((inicio + a, inicio + b, frase))
        # audio: silencio con cada frase en su momento
        audio = np.zeros(int(duracion * 44100) + 44100, dtype=np.int32)
        for inicio, texto in pasos:
            a = self.loc.audio(texto)
            i = int(inicio * 44100)
            audio[i:i + len(a)] += a[:max(0, len(audio) - i)]
        audio = np.clip(audio, -32768, 32767).astype(np.int16)[:int(duracion * 44100)]
        wav = TRABAJO / f"clip_{self.numero:03d}.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(audio.tobytes())
        banda = None if tarjeta else banda_base(self.capitulo)
        ff = subprocess.Popen(
            [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-framerate", str(FPS),
             "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast" if RAPIDO else "medium",
             "-crf", "28" if RAPIDO else "21", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "160k",
             "-shortest", str(clip)], stdin=subprocess.PIPE)
        total = int(duracion * FPS)
        k, clave_cache, datos = 0, None, None
        for i in range(total):
            t = i / FPS
            while k + 1 < len(cuadros) and cuadros[k + 1][0] <= t:
                k += 1
            frase = next((f for a, b, f in subt if a <= t < b), None)
            clave = (k, frase)
            if clave != clave_cache:
                base = Image.open(cuadros[k][1]).convert("RGB") if cuadros else None
                im = tarjeta_con_subtitulo(base, frase) if tarjeta else componer(base, banda, frase)
                datos, clave_cache = im.tobytes(), clave
            ff.stdin.write(datos)
        ff.stdin.close()
        if ff.wait() != 0:
            raise SystemExit(f"ffmpeg fallo al codificar {clip.name}")
        self.clips.append(clip)
        for _, ruta in cuadros:
            if not tarjeta:
                Path(ruta).unlink(missing_ok=True)
        print(f"  {clip.name}: {duracion:.0f} s, {len(cuadros)} cuadros, {len(pasos)} frases", flush=True)


# ------------------------------------------------------------------ el guion
def parte(g: Tutorial, numero: int, titulo: str, subtitulo: str, textos: list[str]) -> None:
    g.capitulo = f"PARTE {numero} · {titulo.upper()}"
    g.tarjeta(f"parte{numero}", lambda: separador(numero, titulo, subtitulo), textos)


def esc_portada(g: Tutorial, cuentas: dict) -> None:
    g.tarjeta("portada", portada, [
        "Bienvenidos. En este tutorial veremos, paso a paso, cómo se usa el SIETE: el Sistema Integral de "
        "Entrenamiento Táctico y Estratégico, desarrollado en la División de Ingeniería y Desarrollo Aeroespacial.",
        "Todo lo que verán está grabado sobre un ejercicio real del simulador. Primero el instructor prepara el "
        "escenario; después un alumno da sus órdenes; y al final el instructor resuelve el turno y revisa el informe.",
    ])


def esc_acceso(g: Tutorial, cuentas: dict) -> None:
    parte(g, 1, "Entrar al simulador", "Cuentas, roles y la pantalla principal", [
        "Empecemos por el acceso.",
    ])
    g.comenzar("acceso", "i", sesion=False)
    g.paso("El SIETE se usa desde el navegador de cada estación del aula, sin internet. Se escribe la dirección del "
           "servidor y aparece la pantalla de acceso.",
           lambda: (g.n.ir(f"{BASE}/", "!document.getElementById('login').hidden", 1.0), g.cursor_listo()))
    g.paso("Quien no tiene cuenta pulsa «Solicitar una cuenta»: elige su usuario, su contraseña, su bando y la "
           "repartición que ocupará en el Estado Mayor. El instructor aprueba la solicitud desde su consola.",
           lambda: (g.clic("#btn-ir-registro", espera=0.8), g.escribir("#r-user", "carlos.perez"),
                    g.elegir("#r-rol", "azul"), g.elegir("#r-puesto", "a3")))
    g.paso("Nosotros ya tenemos cuenta. Volvemos al acceso y entramos como instructor: usuario, contraseña e Ingresar.",
           lambda: (g.clic("#btn-volver-login", espera=0.8), g.entrar(cuentas["instructor"])))
    g.paso("Esta es la pantalla principal. Arriba, la cabecera: el escenario en curso y los botones para crear uno "
           "nuevo, abrir el videowall o el informe.",
           lambda: g.apuntar(*_centro(g, "#escenario")))
    g.paso("A la izquierda, el panel de trabajo con cuatro pestañas: Fuerzas, Situación, TIEM y Consola. La "
           "Consola solo la ve el instructor.",
           lambda: (g.apuntar(*_centro(g, '[data-pestana="fuerzas"]')), g.n.pausa(0.8),
                    g.apuntar(*_centro(g, '[data-pestana="consola"]'))))
    g.paso("En el centro, el mapa: imagen satelital real, relieve, carreteras y las unidades de ambos bandos. "
           "Se acerca y se aleja con la rueda del ratón.",
           lambda: (g.apuntar(*_centro(g, "#map")), g.encuadrar_unidades(3), g.n.pausa(0.5)))
    g.paso("A la derecha, el estado del escenario: el clima, la hora simulada, los objetivos y el puntaje de cada "
           "bando, y las capas del mapa que se pueden encender o apagar.",
           lambda: g.apuntar(*_centro(g, "#panel-der")))
    g.paso("Y abajo, la barra de control del turno: el instructor resuelve y avanza el turno desde aquí, y ve si "
           "cada bando ya confirmó sus órdenes.",
           lambda: g.apuntar(*_centro(g, "#btn-avanzar")))
    g.terminar()


def _centro(g: Tutorial, selector: str, dx=0.5, dy=0.5):
    r = g.n.rect(selector)
    return r["x"] + r["w"] * dx, r["y"] + r["h"] * dy


def esc_crear(g: Tutorial, cuentas: dict) -> None:
    parte(g, 2, "Preparar el escenario", "Plantillas, unidades, objetivos y dirección del ejercicio", [
        "Ahora el instructor prepara el ejercicio.",
    ])
    g.comenzar("plantilla", "i", sesion=False)
    g.hacer(lambda: g.asegurar_sesion("i") if "escenario" in g.datos or not g.n.js("!!(window.__mapa)") else None)
    g.paso("Un escenario se crea desde cero con «Nuevo», o desde una plantilla con las unidades y los objetivos ya "
           "cargados. Vamos a usar una plantilla.",
           lambda: (g.cursor_listo(), g.apuntar(*_centro(g, "#btn-nuevo-escenario")), g.n.pausa(0.6), g.clic("#btn-plantillas", espera=1.2)))
    g.paso("Hay plantillas sobre Venezuela, ejercicios contra la inteligencia artificial y el teatro ficticio del País "
           "Azul y el País Rojo. Cada una dice cuántas unidades y objetivos trae.",
           lambda: g.n.pausa(1.0))
    g.paso("Elegimos la demostración de los llanos y pulsamos Crear. El escenario nuevo queda seleccionado en la "
           "cabecera y el mapa se centra en sus unidades.",
           lambda: (_crear_desde_plantilla(g, "demo"), g.volar(LLANOS[0], LLANOS[1], 10, 3)))
    g.paso("Cada escenario es independiente: se puede pausar, duplicar, archivar o guardar como una plantilla nueva "
           "para repetirlo en otro curso.",
           lambda: g.consola("escenario"))
    g.terminar()

    g.comenzar("unidades", "i")
    g.paso("Para agregar unidades, en la Consola abrimos «Agregar unidad». Primero el nombre, el bando y la clase: "
           "infantería, blindados, artillería, antiaérea, radares, aviación, buques o bases.",
           lambda: (g.cursor_listo(), g.consola("agregar unidad"), g.escribir("#u-nombre", "Batería Buk Barinas"),
                    g.elegir("#u-bando", "azul"), g.elegir("#u-clase", "antiaerea")))
    g.paso("En las clases de tierra y mar se puede elegir el tipo concreto, por ejemplo el Buk-M2E. Los valores de "
           "juego se llenan solos y se pueden ajustar: velocidad, alcance, detección y autonomía.",
           lambda: g.elegir("#u-tipo", "buk_m2e"))
    g.paso("Pulsamos «Ubicar en mapa» y hacemos clic en el lugar. La unidad aparece allí, con su símbolo, y ya "
           "está en el orden de batalla.",
           lambda: (g.clic("#btn-modo-agregar", espera=0.5), g.clic_mapa(8.575, -70.5, 1.5)))
    g.paso("Para las aeronaves se elige el modelo con fotos y datos reales: cazas, aviones de ataque, cisternas, "
           "helicópteros y drones, incluidos los de la Aviación Militar Bolivariana.",
           lambda: (g.escribir("#u-nombre", "Escuadrón Su-30"), g.elegir("#u-clase", "caza"),
                    g.clic("#btn-elegir-modelo", espera=1.2)))
    g.paso("Cada ficha muestra la foto, las prestaciones y el armamento. Elegimos el Su-30 con cuatro aeronaves.",
           lambda: _elegir_aeronave(g, "su30"))
    g.paso("Y lo ubicamos en su base aérea. Un grupo aéreo empieza en tierra, listo para despegar cuando reciba "
           "una misión.",
           lambda: (g.clic("#btn-modo-agregar", espera=0.5), g.volar(8.62, -70.21, 11, 2), g.clic_mapa(8.622, -70.212, 1.5)))
    g.paso("Las unidades se pueden mover arrastrándolas por el mapa mientras el escenario está en edición, y "
           "ajustar su fuerza, combustible o munición desde «Ajuste manual».",
           lambda: g.volar(LLANOS[0], LLANOS[1], 10, 2))
    g.terminar()

    g.comenzar("objetivos", "i")
    g.paso("Ahora los objetivos. En «Objetivos y puntaje» se define qué debe lograr cada bando: ocupar una zona, "
           "destruir, neutralizar o proteger una unidad, o un efecto que agrupa a otros objetivos.",
           lambda: (g.cursor_listo(), g.consola("objetivos y puntaje")))
    g.paso("Creamos uno para el bando azul: ocupar una zona, con su nombre y sus puntos.",
           lambda: (g.elegir("#ob-tipo", "ocupar"), g.elegir("#ob-bando", "azul"),
                    g.escribir("#ob-nombre", "Ocupar el cruce de Barinitas"), g.escribir("#ob-puntos", "30", False)))
    g.paso("Con «Ubicar la zona en el mapa» marcamos el centro, y pulsamos Crear objetivo. El bando azul lo verá "
           "en su panel y el puntaje se actualizará solo cuando lo cumpla.",
           lambda: (g.clic("#btn-ob-ubicar", espera=0.4), g.clic_mapa(8.56, -70.72, 0.8), g.clic("#btn-ob-crear", espera=1.2)))
    g.paso("Cada bando ve solo sus objetivos y su avance. Los objetivos se organizan como un árbol: el objetivo "
           "ulterior, los asignados y los materiales, igual que en el TIEM.",
           lambda: g.desplazar_panel("#ob-lista"))
    g.terminar()

    g.comenzar("situacion", "i")
    g.paso("En la pestaña TIEM está el Problema Militar Operativo de cada bando. Con «Crear la situación "
           "automáticamente», el simulador redacta el PMO, fija el calendario de la operación y arma la cadena de "
           "objetivos a partir de los que ya existen.",
           lambda: (g.cursor_listo(), g.clic('[data-pestana="pmo"]', espera=0.8), g.desplazar_panel("#sec-pmo"),
                    g.clic("#btn-pmo-generar", espera=2.5)))
    g.paso("El instructor puede corregir cualquier campo con «Editar»: la situación, la misión del escalón superior y "
           "la misión del componente aéreo, escrita como tarea, a fin de, propósito.",
           lambda: g.desplazar_panel("#pmo-doc"))
    g.paso("En la Consola, «Calendario de la operación» fija la fecha, el turno de la hora H, la duración y las "
           "fases.",
           lambda: g.consola("calendario de la operación"))
    g.terminar()

    g.comenzar("direccion", "i")
    g.paso("En «Dirección del ejercicio» están los interruptores del motor: niebla de guerra, consumo de "
           "combustible y munición, clima, fuego automático, ciclo de día y noche y fallas de las aeronaves.",
           lambda: (g.cursor_listo(), g.consola("dirección del ejercicio")))
    g.paso("Y quién conduce cada bando: un grupo de alumnos, el propio instructor o el adversario automático. Para "
           "este ejercicio, el bando rojo lo conducirá la inteligencia artificial en nivel normal.",
           lambda: (g.elegir("#dir-cond-rojo", "ia"), g.elegir("#dir-ia-nivel", "normal"), g.clic("#btn-direccion", espera=1.2)))
    g.paso("En «Usuarios» el instructor aprueba las solicitudes de cuenta, crea usuarios y asigna a cada alumno su "
           "bando y su repartición: comandante, jefe de Estado Mayor, A-1, A-2, A-3, defensa aérea, A-4 o "
           "comunicaciones y electrónica.",
           lambda: g.consola("usuarios"))
    g.paso("Y en «Escenario» marca qué alumnos y observadores tienen acceso a este ejercicio: solo ellos lo verán "
           "en su cabecera. Marcamos al comandante del bando azul.",
           lambda: (g.consola("escenario"), _asignar_alumno(g, cuentas["alumno"]["usuario"])))
    g.paso("También puede inyectar eventos e informes de inteligencia, cambiar el clima por zonas y configurar las "
           "comunicaciones simuladas. El escenario ya está listo para los alumnos.",
           lambda: (g.consola("eventos e informes"), g.n.pausa(1.5), g.consola("meteorología")))
    g.terminar()


def _asignar_alumno(g: Tutorial, usuario: str) -> None:
    n = g.n
    n.esperar("document.querySelectorAll('#lista-asignados li').length > 0", 15)
    n.js("document.getElementById('lista-asignados').scrollIntoView({ block: 'center' })")
    n.pausa(0.4)
    falta = n.js(f"""(() => {{ const li = [...document.querySelectorAll('#lista-asignados li')].find((l) => l.textContent.includes({json.dumps(usuario)}));
      if (!li) throw new Error('no esta el alumno ' + {json.dumps(usuario)}); const c = li.querySelector('input'); c.setAttribute('data-video', 'x'); return !c.checked; }})()""")
    if falta:
        g.clic("[data-video='x']", espera=1.0)
    n.js("document.querySelectorAll('[data-video]').forEach((e) => e.removeAttribute('data-video'))")


def _crear_desde_plantilla(g: Tutorial, texto: str) -> None:
    n = g.n
    n.esperar("document.getElementById('dlg-plantillas').open && document.querySelectorAll('#plantilla-lista li').length > 0")
    n.js(f"""(() => {{
      const li = [...document.querySelectorAll('#plantilla-lista li')].find((l) => l.querySelector('b').textContent.trim().toLowerCase().startsWith({json.dumps(texto)}));
      if (!li) throw new Error('sin plantilla'); li.scrollIntoView({{ block: 'center' }}); li.querySelector('button').setAttribute('data-video', 'x'); }})()""")
    n.pausa(0.5)
    antes = n.js("document.getElementById('escenario').value")
    g.clic("[data-video='x']", espera=0.3)
    n.esperar(f"document.getElementById('escenario').value !== {json.dumps(antes)} && " + LISTA_APP, 40)
    n.pausa(1.5)
    g.datos["escenario"] = int(n.js("document.getElementById('escenario').value"))


def _elegir_aeronave(g: Tutorial, modelo: str, cantidad: str = "4") -> None:
    n = g.n
    n.esperar("document.getElementById('dlg-aeronaves').open && document.querySelectorAll('#aer-tarjetas .tarjeta-modelo').length > 0")
    n.js(f"document.querySelector('#aer-tarjetas .tarjeta-modelo[data-modelo=\"{modelo}\"]').scrollIntoView({{ block: 'center' }})")
    n.pausa(0.6)
    g.clic(f'#aer-tarjetas .tarjeta-modelo[data-modelo="{modelo}"]', espera=0.8)
    if n.js(f"[...document.getElementById('aer-cantidad').options].some((o) => o.value === '{cantidad}')"):
        g.elegir("#aer-cantidad", cantidad)
    g.clic("#aer-confirmar", espera=0.6)
    n.esperar("!document.getElementById('dlg-aeronaves').open", 10)
    n.pausa(0.5)


def esc_alumno(g: Tutorial, cuentas: dict) -> None:
    parte(g, 3, "El alumno conduce su bando", "Órdenes, misiones aéreas, situación y TIEM", [
        "Veamos ahora el ejercicio desde el puesto de un alumno del bando azul.",
    ])
    g.comenzar("alumno_entra", "a", sesion=False)
    g.paso("El alumno entra con su cuenta en otra estación. Entra como comandante del bando azul, que reúne las "
           "funciones de todas las reparticiones.",
           lambda: g.entrar(cuentas["alumno"]))
    g.paso("En la cabecera elige el escenario que preparó el instructor.",
           lambda: g.escenario(g.id_escenario()))
    g.paso("Su pantalla es parecida, pero solo ve su propio bando: la niebla de guerra oculta al enemigo hasta que "
           "un sensor lo detecta. Sus unidades están en el orden de batalla, a la izquierda.",
           lambda: (g.cursor_listo(), g.volar(LLANOS[0], LLANOS[1], 10, 2.5), g.apuntar(*_centro(g, "#oob"))))
    g.paso("Al hacer clic en una unidad se abre su ficha: fuerza, combustible, munición, alcance, radio de detección, "
           "personal y su foto o miniatura. En el mapa se marca con su anillo de alcance.",
           lambda: (_seleccionar_oob(g, "1ra brigada"), g.desplazar_panel("#detalle-contenido")))
    g.paso("Las capas del panel derecho permiten ver el relieve, la cobertura de los radares, las carreteras, los "
           "aeródromos con su plano real o la infraestructura.",
           lambda: (g.apuntar(*_centro(g, "#panel-der")), g.n.pausa(1.0)))
    g.terminar()

    g.comenzar("orden_mover", "a")
    g.paso("Para dar una orden, se selecciona la unidad y se elige el tipo en «Nueva orden»: mover, atacar, apoyar, "
           "construir, patrullar y, según la clase, interferir, lanzar misiles, embarcar o desembarcar.",
           lambda: (g.cursor_listo(), _seleccionar_oob(g, "grupo blindado"), g.desplazar_panel("#sec-orden"),
                    g.apuntar(*_centro(g, '[data-modo="mover"]'))))
    g.paso("Con «Mover», cada clic en el mapa agrega un punto de paso. El simulador dibuja la ruta y muestra dónde "
           "llegará la unidad al final del turno y cuánto tardará.",
           lambda: (g.clic('[data-modo="mover"]', espera=0.4), g.volar(8.6, -70.55, 11, 2),
                    g.clic_mapa(8.6, -70.52, 0.6), g.clic_mapa(8.585, -70.6, 0.6)))
    g.paso("«Seguir carreteras» traza el camino más rápido por las vías reales: las unidades terrestres van más "
           "rápido por carretera y cruzan los ríos por sus puentes.",
           lambda: (g.desplazar_panel("#sec-orden"), g.clic("#btn-ruta-vias", espera=2.0)))
    g.paso("Pulsamos «Emitir orden». Queda en la cola de órdenes del turno, con quién la dio y desde qué "
           "repartición. Hasta que se resuelva el turno se puede cancelar.",
           lambda: (g.clic("#btn-emitir", espera=1.2), g.desplazar_panel(".cola")))
    g.paso("Se pueden seleccionar varias unidades con la tecla Control y moverlas juntas, manteniendo la "
           "formación. Damos también una orden de mover a la brigada de infantería hacia el objetivo.",
           lambda: (_seleccionar_oob(g, "1ra brigada"), g.clic('[data-modo="mover"]', espera=0.4),
                    g.volar(8.58, -70.66, 11, 2), g.clic_mapa(8.57, -70.7, 0.6), g.clic("#btn-emitir", espera=1.0)))
    g.terminar()

    g.comenzar("aviacion", "a")
    g.paso("La aviación se maneja desde la pestaña Fuerzas. «Enviar aeronaves o drones» despacha un grupo desde "
           "una base, eligiendo el modelo con su foto, sus prestaciones y su armamento.",
           lambda: (g.cursor_listo(), g.n.js("document.getElementById('panel-izq').scrollTop = 0"),
                    g.clic("#btn-enviar-caza", espera=1.5)))
    g.paso("Cada aeronave tiene su radio de acción, su velocidad, su techo y su carga de armas. Cerramos este "
           "cuadro y planificamos una misión completa.",
           lambda: (g.n.pausa(1.5), g.n.js("document.getElementById('dlg-aeronaves').close()"), g.n.pausa(0.5)))
    g.paso("«Planificar misión» abre el planificador: se elige el grupo o la base de origen, el rol de la misión, "
           "y se marca la ruta en el mapa punto por punto.",
           lambda: (_seleccionar_oob(g, "ala de caza"), g.clic("#btn-planificar-mision", espera=1.2)))
    g.paso("Los roles siguen la doctrina: patrulla aérea de combate, interdicción, apoyo aéreo cercano, supresión de "
           "defensas, reconocimiento, escolta, reabastecimiento en vuelo, alerta temprana o rescate.",
           lambda: (_elegir_origen_grupo(g), g.elegir("#pm-rol", "CAP")))
    g.paso("Marcamos el punto de patrulla sobre el frente y el aterrizaje de regreso en la base. El cronograma "
           "muestra cada fase del vuelo, el combustible y las armas que lleva.",
           lambda: (g.volar(8.66, -70.5, 10, 2), g.clic_mapa(8.62, -70.7, 0.8), g.clic_mapa(8.62, -70.21, 0.8)))
    g.paso("Si falta combustible, la pista es corta o faltan escoltas, el planificador lo avisa antes de emitir. "
           "Emitimos la misión: el grupo despegará y la cumplirá solo, turno a turno.",
           lambda: _emitir_mision(g))
    g.paso("Cada grupo en vuelo tiene además su perfil: alto, medio o rasante. A baja cota se esconde tras el relieve, "
           "pero gasta más combustible y queda expuesto a la antiaérea portátil.",
           lambda: g.n.pausa(0.5))
    g.terminar()

    g.comenzar("situacion_alumno", "a")
    g.paso("La pestaña Situación reúne los cuadros del Estado Mayor: el cuadro radar con lo que detecta cada sensor, "
           "el personal, el apresto operacional, el esfuerzo aéreo, los puntos de recobre y la infraestructura.",
           lambda: (g.cursor_listo(), g.clic('[data-pestana="situacion"]', espera=1.0), g.n.js("document.getElementById('panel-izq').scrollTop = 0")))
    g.paso("Cada cuadro se actualiza solo en cada turno. Aquí el A-1 sigue las bajas, el A-4 las existencias y el "
           "jefe de defensa aérea la cobertura de sus radares.",
           lambda: (g.desplazar_panel("#sec-personal"), g.n.pausa(1.5), g.desplazar_panel("#cuadro-pro")))
    g.paso("La pestaña TIEM es el corazón del método: el Problema Militar Operativo, el calendario y los documentos "
           "de las tres fases: apreciación, decisión y plan, y supervisión.",
           lambda: (g.clic('[data-pestana="pmo"]', espera=1.0), g.n.js("document.getElementById('panel-izq').scrollTop = 0")))
    g.paso("Cada repartición redacta su documento dentro del simulador, lo presenta al instructor y este lo aprueba o "
           "lo devuelve con observaciones. Todo se exporta a Word o PDF con el formato del TIEM.",
           lambda: (g.desplazar_panel("#sec-apreciacion"), g.n.pausa(0.5), _abrir_documento(g, 0), g.n.pausa(2.5),
                    g.n.js("document.getElementById('dlg-tiem').close()")))
    g.paso("Las comunicaciones del bando van por el chat, en la red del bando o con el mando. El instructor puede "
           "simular demoras y pérdidas de mensajes.",
           lambda: (g.clic('[data-pestana="fuerzas"]', espera=0.5), g.desplazar_panel("#tarjeta-chat", "center"),
                    g.escribir("#chat-texto", "Brigada en marcha hacia Barinitas. Solicito cobertura aérea."),
                    g.clic("#chat-form button[type=submit]", espera=1.2)))
    g.paso("Cuando el bando terminó de dar sus órdenes, el comandante pulsa «Estoy listo». El instructor ve que el "
           "bando confirmó y puede resolver el turno.",
           lambda: g.clic("#btn-listo", espera=1.5))
    g.terminar()


def _seleccionar_oob(g: Tutorial, texto: str) -> None:
    g.n.js("document.getElementById('panel-izq').scrollTop = 0")
    g.n.pausa(0.2)
    g.clic_texto("#oob .oob-item", texto, espera=0.8)


def _elegir_origen_grupo(g: Tutorial) -> None:
    n = g.n
    n.esperar("!document.getElementById('panel-mision').hidden", 10)
    if n.js("!!document.getElementById('pm-origen-grupo')"):
        n.js("document.getElementById('pm-origen-grupo').click()")
        n.pausa(0.4)
        n.js("""(() => { const s = document.getElementById('pm-grupo'); if (!s) return;
          const o = [...s.options].find((x) => /ala de caza/i.test(x.textContent)); if (o) { s.value = o.value; s.dispatchEvent(new Event('change', { bubbles: true })); } })()""")
        n.pausa(0.4)


def _emitir_mision(g: Tutorial) -> None:
    n = g.n
    n.js("document.getElementById('pm-crear').scrollIntoView({ block: 'center' })")
    n.pausa(0.4)
    if n.js("!document.getElementById('pm-crear').disabled"):
        g.clic("#pm-crear", espera=1.5)
    else:
        n.pausa(1.5)


def _abrir_documento(g: Tutorial, indice: int) -> None:
    n = g.n
    n.esperar("document.querySelectorAll('#tiem-docs button').length > 0", 10)
    n.js(f"document.querySelectorAll('#tiem-docs button')[{indice}].setAttribute('data-video', 'x')")
    g.clic("[data-video='x']", espera=0.8)
    n.js("document.querySelectorAll('[data-video]').forEach((e) => e.removeAttribute('data-video'))")
    n.esperar("document.getElementById('dlg-tiem').open", 10)


def esc_turno(g: Tutorial, cuentas: dict) -> None:
    parte(g, 4, "Resolver el turno", "Movimientos, detecciones y combates a la vez", [
        "Volvemos a la pantalla del instructor para resolver el turno.",
    ])
    g.comenzar("resolver", "i")
    g.paso("Abajo, la barra muestra que el bando azul ya confirmó. El rojo lo conduce la inteligencia artificial, así "
           "que no hace falta esperarlo. El instructor pulsa «Resolver y avanzar turno».",
           lambda: (g.cursor_listo(), g.clic('[data-pestana="fuerzas"]', espera=0.3), g.volar(8.62, -70.62, 10, 2),
                    g.apuntar(*_centro(g, "#estado-azul")), g.n.pausa(1.0)))
    g.paso("El motor resuelve todo a la vez: los movimientos por las carreteras, los despegues, las detecciones de "
           "cada sensor, los combates y la logística. Cada turno es una hora simulada.",
           lambda: _avanzar_turno(g))
    g.paso("Las unidades se deslizan por el camino que recorrieron y dejan su rastro. Los eventos del turno "
           "aparecen en la tarjeta de novedades: contactos nuevos, combates, aterrizajes.",
           lambda: g.n.pausa(2.0))
    g.paso("El instructor ve todo: ambos bandos, sin niebla de guerra. Con «Ver como» puede mirar la pantalla tal "
           "como la ve cada bando.",
           lambda: g.n.pausa(0.5))
    g.terminar()

    g.comenzar("alumno_turno", "a")
    g.paso("En la estación del alumno, el nuevo turno llega solo. Sus unidades avanzaron, el grupo aéreo despegó y "
           "los contactos que detectaron sus sensores aparecen en rojo.",
           lambda: (g.cursor_listo(), g.clic('[data-pestana="fuerzas"]', espera=0.3), g.volar(8.62, -70.62, 10, 2.5)))
    g.paso("El alumno revisa las alertas, ajusta sus órdenes y vuelve a confirmar. Así, turno a turno, se conduce "
           "la operación.",
           lambda: g.n.pausa(1.0))
    g.terminar()


def _avanzar_turno(g: Tutorial) -> None:
    n = g.n
    antes = n.js("document.getElementById('h-turno').textContent")
    g.clic("#btn-avanzar", espera=0.3)
    n.esperar(f"document.getElementById('h-turno').textContent !== {json.dumps(antes)}", 120)
    n.pausa(4.5)  # la animacion del desplazamiento y el rastro


def esc_informe(g: Tutorial, cuentas: dict) -> None:
    parte(g, 5, "Informe, videowall y más", "El análisis posterior y las herramientas del instructor", [
        "Para terminar, las herramientas del análisis posterior.",
    ])
    g.comenzar("informe", "i")
    g.paso("El botón «Informe» abre el informe posterior: la repetición animada del ejercicio turno a turno, con "
           "los movimientos, las estelas y los combates de cada unidad.",
           lambda: (g.cursor_listo(), g.clic("#btn-informe", espera=2.0)))
    g.paso("Se puede reproducir, ir turno por turno y ver el resumen, los combates, la línea de tiempo y la "
           "rúbrica: los indicadores doctrinales de cada bando, cada repartición y cada alumno, con nota de uno a "
           "veinte.",
           lambda: (_pulsar_si_existe(g, "#rp-play"), g.n.pausa(4.0), _pulsar_si_existe(g, "#rp-rubrica"), g.n.pausa(2.5)))
    g.paso("El informe se imprime, se exporta a diapositivas y a hoja de cálculo. Cerramos el informe.",
           lambda: (g.n.js("document.getElementById('dlg-rubrica') && document.getElementById('dlg-rubrica').open && document.getElementById('dlg-rubrica').close()"),
                    _pulsar_si_existe(g, "#rp-cerrar"), g.n.pausa(1.0)))
    g.terminar()

    g.comenzar("videowall", "i")
    g.paso("Para la pantalla grande del centro de operaciones está el videowall: el mapa a pantalla completa, con "
           "el turno, el reloj y el marcador. Se sale con la tecla V.",
           lambda: (g.cursor_listo(), g.clic("#btn-videowall", espera=1.0), g.volar(8.62, -70.6, 10, 3), g.n.pausa(1.0),
                    _pulsar_si_existe(g, "#btn-vw-salir"), g.n.pausa(1.0)))
    g.paso("En la Consola, «Catálogo propio» permite definir tipos de unidad propios y subir la foto de cualquier "
           "tipo: el simulador la recorta y la encuadra como las demás.",
           lambda: g.consola("catálogo propio"))
    g.paso("Y «Guardar como plantilla» conserva la situación actual para repetir el ejercicio en otro curso.",
           lambda: (g.apuntar(*_centro(g, "#btn-guardar-plantilla")), g.n.pausa(1.0)))
    g.terminar()


def _pulsar_si_existe(g: Tutorial, selector: str) -> None:
    if g.n.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); return !!(e && !e.hidden && e.offsetParent !== null); }})()"):
        g.clic(selector, espera=0.5)


def esc_cierre(g: Tutorial, cuentas: dict) -> None:
    g.tarjeta("cierre", cierre, [
        "Esto es el SIETE: un ejercicio que se prepara, se conduce y se evalúa en el aula, con el Trabajo Integral de "
        "Estado Mayor como guía. Los manuales de usuario y de referencia tienen el detalle de cada función.",
        "Desarrollado en la División de Ingeniería y Desarrollo Aeroespacial de la Aviación Militar Bolivariana. "
        "Muchas gracias.",
    ], antes=1.0, despues=2.0)


ESCENAS = [("portada", esc_portada), ("acceso", esc_acceso), ("crear", esc_crear), ("alumno", esc_alumno),
           ("turno", esc_turno), ("informe", esc_informe), ("cierre", esc_cierre)]


# ------------------------------------------------------------------ armado
def main() -> None:
    global E, ANCHO, ALTO, VOZ, VELOCIDAD, RAPIDO, SIN_VOZ
    opciones = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    if "--1080" in sys.argv:
        E, ANCHO, ALTO = 1, 1920, 1080
    VOZ = opciones.get("voz", VOZ)
    VELOCIDAD = opciones.get("velocidad", VELOCIDAD)
    RAPIDO = "--rapido" in sys.argv
    SIN_VOZ = "--sin-voz" in sys.argv
    solo = [s for s in opciones.get("solo", "").split(",") if s]
    escenas = [(k, f) for k, f in ESCENAS if not solo or k in solo]
    if not CUENTAS.is_file():
        raise SystemExit(f"Falta el archivo de cuentas de prueba (SIETE_CUENTAS): {CUENTAS}")
    cuentas = json.loads(CUENTAS.read_text(encoding="utf-8"))
    TRABAJO.mkdir(parents=True, exist_ok=True)
    for viejo in TRABAJO.glob("clip_*"):
        viejo.unlink()

    # 1) textos y voz
    rec = Tutorial("recolectar")
    rec.cuentas = cuentas
    for _, f in escenas:
        f(rec, cuentas)
    print(f"{len(rec.textos)} frases; voz {VOZ} {VELOCIDAD}" + (" (sin voz: borrador)" if SIN_VOZ else ""), flush=True)
    loc = Locucion(rec.textos)
    print(f"locución: {sum(loc.duracion(t) for t in rec.textos) / 60:.1f} min", flush=True)

    # 2) grabacion y codificacion escena por escena
    g = Tutorial("grabar", loc)
    g.cuentas = cuentas
    inicio = time.time()
    try:
        for nombre, f in escenas:
            f(g, cuentas)
    finally:
        g.cerrar()
    print(f"grabado en {(time.time() - inicio) / 60:.1f} min; uniendo {len(g.clips)} clips...", flush=True)

    # 3) union y normalizacion del audio
    lista = TRABAJO / "lista.txt"
    lista.write_text("".join(f"file '{c.as_posix()}'\n" for c in g.clips), encoding="utf-8")
    nombre = "SIETE_3_tutorial" + ("_2K" if E > 1 else "") + ("_borrador" if RAPIDO or SIN_VOZ else "") + ".mp4"
    salida = (DESTINO / "2K" / nombre) if E > 1 else DESTINO / nombre
    salida.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(salida)], check=True)
    ffprobe = shutil.which("ffprobe") or str(Path(FFMPEG).with_name("ffprobe.exe"))
    dur = float(subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(salida)], capture_output=True, text=True).stdout.strip() or 0)
    print(f"{salida} ({salida.stat().st_size // (1024 * 1024)} MB, {dur / 60:.1f} min)")


if __name__ == "__main__":
    main()
