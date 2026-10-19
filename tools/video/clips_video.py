"""Clips del simulador en marcha para el video tutorial (tools/video/guion_tutorial.py): graba el S.I.E.T.E. funcionando
sobre el arnes de pruebas (datos de ejemplo), cuadro a cuadro, con el tiempo virtual de Chrome: cada cuadro es 1/30 s
exacto, asi que los vuelos del mapa, el desplazamiento animado de las unidades y el replay salen fluidos aunque la
captura sea lenta. Resolucion 2560x1440 (2K). Un circulo rojo marca el cursor y cada clic.

Deja en salida/clips/<nombre>/ los cuadros JPEG numerados y meta.json (fps, cuadros, ancho, alto).

Requiere el servidor en marcha en 127.0.0.1:8000.

    backend\\venv\\Scripts\\python tools/video/clips_video.py                 # todos
    backend\\venv\\Scripts\\python tools/video/clips_video.py clip_terreno    # algunos (por nombre)
"""

import base64
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "manual"))
import capturas_guia as guia  # noqa: E402
from navegador import Navegador  # noqa: E402

SALIDA = AQUI / "salida" / "clips"
FPS = 30
ANCHO, ALTO, ESCALA = 1920, 1080, 4 / 3  # 1920x1080 CSS a escala 4/3 = 2560x1440
LISTA = guia.LISTA_APP
# el rotulo del arnes no sale en el video y el ejercicio de ejemplo lleva nombre
LIMPIAR = """(() => {
  for (const e of [...document.body.children]) if ((e.textContent || '').startsWith('ARNÉS DE PRUEBAS')) e.remove();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = w.nextNode(); t; t = w.nextNode())
    if (t.nodeValue.includes('Ejercicio de ejemplo: piedemonte andino')) t.nodeValue = t.nodeValue.replace('Ejercicio de ejemplo: piedemonte andino', 'Ejercicio Centinela del Llano');
  if (!document.getElementById('cursor-clip')) {
    const c = document.createElement('div'); c.id = 'cursor-clip';
    c.style.cssText = 'position:fixed;left:-100px;top:-100px;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;'
      + 'border:4px solid #ff3b30;box-shadow:0 0 0 3px rgba(255,255,255,.85),0 0 18px rgba(255,59,48,.8);z-index:99999;pointer-events:none;';
    document.body.appendChild(c);
  }
})()"""


def suave(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


class NavegadorClip(Navegador):
    """Chrome con el tiempo detenido: solo avanza cuando se pide el siguiente cuadro."""

    def __init__(self):
        super().__init__(ANCHO, ALTO, ESCALA)
        self.ultimo: bytes | None = None
        self.nuevos = 0

    def _evento(self, m: dict) -> None:
        if m.get("method") == "Page.screencastFrame":
            p = m["params"]
            self.ultimo = base64.b64decode(p["data"])
            self.nuevos += 1
            self._id += 1
            self.ws.send(json.dumps({"id": self._id, "method": "Page.screencastFrameAck", "params": {"sessionId": p["sessionId"]}}))
        else:
            super()._evento(m)

    def ir(self, url, listo=LISTA, extra=1.5):
        # como Navegador.ir, con mas paciencia: el servidor puede estar ocupado con otras capturas
        self.enviar("Page.navigate", {"url": url})
        self.pausa(0.5)
        self.esperar("document.readyState === 'complete'", 120)
        self.esperar(listo, 120)
        self.pausa(extra)
        self.js(LIMPIAR)

    def detener_tiempo(self):
        self.enviar("Emulation.setVirtualTimePolicy", {"policy": "pause"})
        self.enviar("Page.startScreencast", {"format": "jpeg", "quality": 92, "everyNthFrame": 1})

    def cerrar(self):
        try:
            super().cerrar()
        except PermissionError:  # Windows: algun proceso hijo de Chrome aun tiene abierto un archivo del perfil temporal
            pass

    def js_sin_esperar(self, expresion: str) -> None:
        """Envia JavaScript sin esperar el resultado: lo que desplaza un panel solo termina cuando corre el tiempo."""
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": "Runtime.evaluate", "params": {"expression": expresion, "returnByValue": True}}))

    def cuadro(self, ms: float, espera=1.2) -> bytes:
        """Avanza el tiempo virtual `ms` milisegundos y devuelve el cuadro que produce la pantalla (o el anterior, si
        nada cambio)."""
        self.nuevos = 0
        self._id += 1
        mio = self._id
        self.ws.send(json.dumps({"id": mio, "method": "Emulation.setVirtualTimePolicy",
                                 "params": {"policy": "advance", "budget": ms, "maxVirtualTimeTaskStarvationCount": 100000}}))
        ok = expiro = False
        limite = time.time() + espera
        while time.time() < limite:
            try:
                m = json.loads(self.ws.recv(timeout=max(0.01, limite - time.time())))
            except TimeoutError:
                break
            if m.get("id") == mio:
                ok = True
            elif m.get("method") == "Emulation.virtualTimeBudgetExpired":
                expiro = True
            else:
                self._evento(m)
            if ok and expiro and self.nuevos:
                break
        if self.ultimo is None:
            datos = self.enviar("Page.captureScreenshot", {"format": "jpeg", "quality": 92})["data"]
            self.ultimo = base64.b64decode(datos)
        return self.ultimo


class Clip:
    """Un clip: acumula cuadros mientras se actua sobre la pagina."""

    def __init__(self, n: NavegadorClip, nombre: str):
        self.n, self.nombre = n, nombre
        self.carpeta = SALIDA / nombre
        self.carpeta.mkdir(parents=True, exist_ok=True)
        for viejo in self.carpeta.glob("*.jpg"):
            viejo.unlink()
        self.k = 0
        self.cursor = (-100.0, -100.0)
        n.detener_tiempo()

    def _guardar(self, jpg: bytes):
        self.k += 1
        (self.carpeta / f"{self.k:05d}.jpg").write_bytes(jpg)

    def avanzar(self, segundos: float):
        """Deja correr el tiempo (animaciones, vuelos, replay) grabando cada cuadro."""
        for _ in range(round(segundos * FPS)):
            self._guardar(self.n.cuadro(1000 / FPS))

    def quieto(self, segundos: float):
        """Pantalla fija: un solo cuadro repetido (mucho mas rapido que grabarlos)."""
        jpg = self.n.cuadro(1000 / FPS)
        for _ in range(round(segundos * FPS)):
            self._guardar(jpg)

    def js_con_tiempo(self, expresion: str, segundos=0.15):
        """JavaScript que necesita que corra el tiempo para terminar (desplazar un panel): se graba mientras tanto."""
        self.n.js_sin_esperar(expresion)
        self.avanzar(segundos)

    def _poner_cursor(self, x: float, y: float):
        self.cursor = (x, y)
        self.n.js(f"(() => {{ const c = document.getElementById('cursor-clip'); c.style.left = '{x:.1f}px'; c.style.top = '{y:.1f}px'; }})()")

    def mover_cursor(self, x: float, y: float, segundos=0.7):
        """Desliza el cursor hasta (x, y) en px CSS, cuadro a cuadro."""
        x0, y0 = self.cursor
        if x0 < 0:
            x0, y0 = x, y + 160
        cuadros = max(1, round(segundos * FPS))
        for i in range(1, cuadros + 1):
            k = suave(i / cuadros)
            self._poner_cursor(x0 + (x - x0) * k, y0 + (y - y0) * k)
            self._guardar(self.n.cuadro(1000 / FPS))

    def _pulsar(self):
        self.n.js("(() => { const c = document.getElementById('cursor-clip'); c.style.transform = 'scale(.6)'; })()")
        self.avanzar(0.15)
        self.n.js("(() => { const c = document.getElementById('cursor-clip'); c.style.transform = ''; })()")

    def clic(self, selector: str, despues=0.8):
        r = self.n.rect(selector)
        if r["y"] < 0 or r["y"] + r["h"] > ALTO:  # fuera de la vista: el panel se desplaza hasta mostrarlo
            self.js_con_tiempo(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{ block: 'center', behavior: 'instant' }})", 0.3)
            r = self.n.rect(selector)
        self.mover_cursor(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
        self._pulsar()
        self.n.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) throw new Error('no existe ' + {json.dumps(selector)});"
                  " e.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); })()")
        self.avanzar(despues)

    def clic_mapa(self, lat: float, lon: float, despues=0.6):
        x, y = self.n.punto_mapa(lat, lon)
        self.mover_cursor(x, y)
        self._pulsar()
        self.n.raton("mouseMoved", x, y)
        self.n.raton("mousePressed", x, y, button="left", clickCount=1)
        self.n.raton("mouseReleased", x, y, button="left", clickCount=1)
        self.avanzar(despues)

    def volar(self, lat: float, lon: float, zoom: int, segundos: float):
        self.n.js(f"void __mapa.flyTo([{lat}, {lon}], {zoom}, {{ duration: {segundos} }})")
        self.avanzar(segundos + 0.4)

    def desplazar(self, selector: str, px: int, segundos: float):
        """Desplaza el contenido de un panel o dialogo poco a poco."""
        cuadros = max(1, round(segundos * FPS))
        for i in range(1, cuadros + 1):
            # el selector puede abarcar varios elementos (p. ej. un dialogo y su cuerpo): se desplaza el que pueda
            self.n.js_sin_esperar(f"document.querySelectorAll({json.dumps(selector)}).forEach((e) => e.scrollTo({{ top: {px * suave(i / cuadros):.0f}, behavior: 'instant' }}))")
            self._guardar(self.n.cuadro(1000 / FPS))

    def cerrar(self) -> float:
        duracion = self.k / FPS
        (self.carpeta / "meta.json").write_text(json.dumps({"fps": FPS, "cuadros": self.k, "ancho": round(ANCHO * ESCALA),
                                                            "alto": round(ALTO * ESCALA), "duracion": duracion}), encoding="utf-8")
        return duracion


# ------------------------------------------------------------------ los clips
def clip_terreno(n: NavegadorClip) -> Clip:
    """De toda America al area del ejercicio, en vuelo."""
    n.ir(guia.arnes("instructor", lat=6, lon=-72, zoom=4), LISTA, 5)
    c = Clip(n, "clip_terreno")
    c.quieto(1.2)
    c.volar(7.6, -66.2, 6, 3.0)
    c.quieto(1.0)
    c.volar(8.62, -70.5, 10, 3.5)
    c.quieto(1.5)
    return c


def clip_orden_mover(n: NavegadorClip) -> Clip:
    """El alumno selecciona una unidad, marca los puntos de paso y emite la orden."""
    n.ir(guia.arnes("azul", "comandante", 8.56, -70.6, 11), LISTA, 2.5)
    c = Clip(n, "clip_orden_mover")
    c.quieto(0.8)
    c.clic('#oob .oob-item[data-id="2"]', 1.0)
    n.js("void __mapa.setView([8.54, -70.6], 11, { animate: false })")
    c.avanzar(0.6)
    c.clic('[data-modo="mover"]', 0.8)
    c.js_con_tiempo("document.getElementById('sec-orden').scrollIntoView({ block: 'start', behavior: 'instant' })", 0.4)
    for lat, lon in [(8.53, -70.66), (8.5, -70.6), (8.48, -70.54)]:
        c.clic_mapa(lat, lon, 0.7)
    c.quieto(1.2)
    c.clic("#btn-emitir", 1.2)
    c.js_con_tiempo("document.querySelector('.cola').scrollIntoView({ block: 'start', behavior: 'instant' })", 0.4)
    c.quieto(2.0)
    return c


def clip_resolver_turno(n: NavegadorClip) -> Clip:
    """El instructor resuelve el turno y las unidades se desplazan animadas."""
    n.ir(guia.arnes("instructor", lat=8.6, lon=-70.56, zoom=11), LISTA, 3)
    # el arnes no mueve las unidades al resolver: se desplazan las que tienen orden de mover (y una roja) al llegar
    # el estado nuevo, y la interfaz las anima por su ruta
    n.js("""(() => {
      const MOV = { 2: [8.62, -70.55], 1: [8.625, -70.53], 11: [8.655, -70.505], 13: [8.64, -70.47] };
      const P = window.WebSocket.prototype, original = P._emit;
      P._emit = function (obj) {
        if (obj && obj.tipo === 'estado' && window.__movido) for (const u of obj.unidades) if (MOV[u.id]) { u.lat = MOV[u.id][0]; u.lon = MOV[u.id][1]; }
        return original.call(this, obj);
      };
    })()""")
    c = Clip(n, "clip_resolver_turno")
    c.quieto(1.0)
    r = n.rect("#btn-avanzar")
    c.mover_cursor(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2, 1.0)
    c.quieto(0.4)
    n.js("window.__movido = true")
    c._pulsar()
    n.js("document.getElementById('btn-avanzar').click()")
    c.avanzar(7.0)
    c.quieto(1.0)
    return c


def clip_mision(n: NavegadorClip) -> Clip:
    """El A-3 planifica una mision aerea: grupo, rol y ruta."""
    n.ir(guia.arnes("azul", "a3", 8.66, -70.5, 11), LISTA, 2.5)
    c = Clip(n, "clip_mision")
    c.quieto(0.8)
    c.clic("#btn-planificar-mision", 0.8)
    n.esperar("!document.getElementById('panel-mision').hidden", 5)
    n.js("document.getElementById('pm-origen-grupo').click()")
    c.avanzar(0.5)
    n.valor("#pm-grupo", "8")
    c.avanzar(0.6)
    n.valor("#pm-rol", "INTERDICCION")
    c.avanzar(0.8)
    n.js("void __mapa.setView([8.66, -70.5], 11, { animate: false })")
    c.avanzar(0.4)
    for lat, lon in [(8.68, -70.55), (8.662, -70.6)]:
        c.clic_mapa(lat, lon, 0.8)
    c.quieto(2.5)
    return c


def clip_replay(n: NavegadorClip) -> Clip:
    """El replay del informe posterior: el ejercicio entero animado."""
    n.ir(guia.arnes("instructor", lat=8.6, lon=-70.57, zoom=10, extra="&abrir=replay"),
         LISTA + " && !document.getElementById('replay-anim').hidden", 3)
    c = Clip(n, "clip_replay")
    c.quieto(0.8)
    n.valor("#ra-velocidad", "1")
    c.clic("#ra-play", 0.3)
    c.avanzar(11.0)
    return c


def clip_tiem(n: NavegadorClip) -> Clip:
    """La pestaña TIEM: la lista de documentos y una apreciacion abierta."""
    n.ir(guia.arnes("azul", "a3"), LISTA, 2.5)
    c = Clip(n, "clip_tiem")
    c.quieto(0.6)
    c.clic('[data-pestana="pmo"]', 0.8)
    n.esperar("document.querySelectorAll('#tiem-docs button').length >= 14", 8)
    c.desplazar("#panel-izq", 520, 2.0)
    c.quieto(0.8)
    c.js_con_tiempo("document.querySelectorAll('#tiem-docs button')[3].scrollIntoView({ block: 'center', behavior: 'instant' })", 0.3)
    r = n.js("(() => { const b = document.querySelectorAll('#tiem-docs button')[3].getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()")
    c.mover_cursor(r[0], r[1])
    c._pulsar()
    n.js("document.querySelectorAll('#tiem-docs button')[3].click()")
    n.esperar("document.getElementById('dlg-tiem').open", 5)
    c.avanzar(1.0)
    c.desplazar("#dlg-tiem, .tiem-dialogo, #tiem-cuerpo", 700, 3.5)
    c.quieto(1.5)
    return c


CLIPS = [clip_terreno, clip_orden_mover, clip_resolver_turno, clip_mision, clip_replay, clip_tiem]


def grabar_uno(nombre: str) -> None:
    f = next(f for f in CLIPS if f.__name__ == nombre)
    inicio = time.time()
    n = NavegadorClip()
    try:
        c = f(n)
        d = c.cerrar()
        print(f"  {nombre}: {d:.1f} s de video ({time.time() - inicio:.0f} s de grabación)", flush=True)
    finally:
        n.cerrar()


def main() -> None:
    if len(sys.argv) > 2 and sys.argv[1] == "--uno":
        return grabar_uno(sys.argv[2])
    pedidos = set(sys.argv[1:])
    SALIDA.mkdir(parents=True, exist_ok=True)
    fallos = []
    for f in CLIPS:
        if pedidos and f.__name__ not in pedidos:
            continue
        # cada clip en un proceso aparte: tras un clip con el tiempo virtual detenido, un Chrome nuevo del mismo
        # proceso no termina de cargar la pagina siguiente; y se reintenta una vez
        for intento in (1, 2):
            r = subprocess.run([sys.executable, __file__, "--uno", f.__name__])
            if r.returncode == 0:
                break
            print(f"  {f.__name__}: fallo el intento {intento}", flush=True)
        else:
            fallos.append(f.__name__)
    print(f"{len(fallos)} fallo(s): {', '.join(fallos)}" if fallos else "Todos los clips listos.")


if __name__ == "__main__":
    main()
