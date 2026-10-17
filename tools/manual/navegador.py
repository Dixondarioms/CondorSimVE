"""Chrome sin ventana manejado por su protocolo de depuracion (CDP), para las capturas del manual de usuario.

Usa solo la libreria `websockets` (viene con el servidor: uvicorn[standard]) y el Chrome instalado. Permite navegar,
ejecutar JavaScript, hacer clic en elementos o en un punto del mapa (lat, lon), pasar el cursor y capturar la
pantalla entera o el recuadro de un elemento. Las capturas se pueden anotar con numeros sobre las zonas que se
explican (anotar()). Tambien graba video (grabar(): Chrome envia cada cuadro que cambia; ver video_demo.py).
"""

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if not Path(CHROME).exists():  # Linux (p. ej. el Chromium de Playwright) o la variable SIETE_CHROME
    CHROME = (os.environ.get("SIETE_CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
              or shutil.which("chromium-browser") or "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")


def _puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Navegador:
    def __init__(self, ancho=1440, alto=900, escala=1):
        """`escala`: pixeles fisicos por pixel CSS (2 con 1920x1080 da capturas 4K)."""
        self.ancho, self.alto, self.escala = ancho, alto, escala
        self.puerto = _puerto_libre()
        self.perfil = tempfile.TemporaryDirectory()
        self.proceso = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
             f"--remote-debugging-port={self.puerto}", "--remote-allow-origins=*", f"--user-data-dir={self.perfil.name}",
             f"--window-size={ancho},{alto}", f"--force-device-scale-factor={escala}",
             *(["--no-sandbox"] if hasattr(os, "geteuid") and os.geteuid() == 0 else []), "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.puerto}/json", timeout=1) as r:
                    paginas = [p for p in json.loads(r.read()) if p.get("type") == "page"]
                if paginas:
                    break
            except OSError:
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError("Chrome no abrio el puerto de depuracion")
        self.ws = connect(paginas[0]["webSocketDebuggerUrl"], max_size=None, open_timeout=20)
        self._id = 0
        self.cuadros: list[tuple[float, bytes]] = []  # (segundos desde el inicio de la grabacion, jpeg)
        self._t0 = None
        self.enviar("Emulation.setDeviceMetricsOverride", {"width": ancho, "height": alto, "deviceScaleFactor": escala, "mobile": False})

    # ---------------------------------------------------------------- protocolo
    def _evento(self, msj: dict) -> None:
        """Cuadros de la grabacion: se guardan y se confirman (Chrome no manda el siguiente sin confirmacion)."""
        if msj.get("method") == "Page.screencastFrame":
            p = msj["params"]
            if self._t0 is not None:
                self.cuadros.append((time.time() - self._t0, base64.b64decode(p["data"])))
            self._id += 1
            self.ws.send(json.dumps({"id": self._id, "method": "Page.screencastFrameAck", "params": {"sessionId": p["sessionId"]}}))

    def pausa(self, segundos: float) -> None:
        """Espera atendiendo los eventos de Chrome (durante una grabacion, sigue recibiendo cuadros)."""
        limite = time.time() + segundos
        while (falta := limite - time.time()) > 0:
            try:
                self._evento(json.loads(self.ws.recv(timeout=falta)))
            except TimeoutError:
                break

    def grabar(self, calidad=82) -> None:
        self.cuadros, self._t0 = [], time.time()
        self.enviar("Page.startScreencast", {"format": "jpeg", "quality": calidad, "everyNthFrame": 1})

    def detener_grabacion(self) -> float:
        self.enviar("Page.stopScreencast")
        duracion = time.time() - self._t0
        self._t0 = None
        return duracion

    def enviar(self, metodo: str, params: dict | None = None, espera=60):
        self._id += 1
        mio = self._id
        self.ws.send(json.dumps({"id": mio, "method": metodo, "params": params or {}}))
        limite = time.time() + espera
        while time.time() < limite:
            msj = json.loads(self.ws.recv(timeout=espera))
            self._evento(msj)
            if msj.get("id") == mio:
                if "error" in msj:
                    raise RuntimeError(f"{metodo}: {msj['error']}")
                return msj.get("result", {})
        raise TimeoutError(metodo)

    def js(self, expresion: str):
        r = self.enviar("Runtime.evaluate", {"expression": expresion, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            raise RuntimeError(f"JS: {r['exceptionDetails'].get('exception', {}).get('description', r['exceptionDetails'])}\n{expresion[:200]}")
        return r.get("result", {}).get("value")

    def esperar(self, condicion: str, segundos=20, pausa=0.25):
        limite = time.time() + segundos
        while time.time() < limite:
            try:
                if self.js(f"!!({condicion})"):
                    return
            except RuntimeError:
                pass
            self.pausa(pausa)
        raise TimeoutError(condicion)

    def ir(self, url: str, listo: str, extra=1.5):
        self.enviar("Page.navigate", {"url": url})
        self.pausa(0.5)
        self.esperar("document.readyState === 'complete'")
        self.esperar(listo, 30)
        self.pausa(extra)

    # ---------------------------------------------------------------- acciones
    def clic(self, selector: str, ctrl=False):
        """Clic de JavaScript sobre el elemento (botones, pestañas, elementos de lista)."""
        self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) throw new Error('no existe ' + {json.dumps(selector)});"
                f" e.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, ctrlKey: {str(ctrl).lower()} }})); }})()")
        self.pausa(0.4)

    def valor(self, selector: str, valor):
        """Fija el valor de un campo o lista y avisa con 'input' y 'change'."""
        self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); e.value = {json.dumps(str(valor))};"
                f" e.dispatchEvent(new Event('input', {{ bubbles: true }})); e.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()")
        self.pausa(0.3)

    def punto_mapa(self, lat: float, lon: float) -> tuple[float, float]:
        return tuple(self.js(
            f"(() => {{ const p = __mapa.latLngToContainerPoint([{lat}, {lon}]); const r = __mapa.getContainer().getBoundingClientRect();"
            f" return [r.left + p.x, r.top + p.y]; }})()"))

    def raton(self, tipo: str, x: float, y: float, **extra):
        self.enviar("Input.dispatchMouseEvent", {"type": tipo, "x": x, "y": y, **extra})

    def clic_mapa(self, lat: float, lon: float, dobles=False):
        x, y = self.punto_mapa(lat, lon)
        self.raton("mouseMoved", x, y)
        for n in (1, 2) if dobles else (1,):
            self.raton("mousePressed", x, y, button="left", clickCount=n)
            self.raton("mouseReleased", x, y, button="left", clickCount=n)
        self.pausa(0.45)

    def cursor_mapa(self, lat: float, lon: float):
        x, y = self.punto_mapa(lat, lon)
        self.raton("mouseMoved", x, y)
        self.pausa(0.8)

    def vista(self, lat: float, lon: float, zoom: int, espera=2.5):
        self.js(f"void __mapa.setView([{lat}, {lon}], {zoom}, {{ animate: false }})")  # sin devolver el mapa (no se serializa)
        self.pausa(espera)

    def rect(self, selector: str) -> dict:
        r = self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); if (!e) return null;"
                    f" const b = e.getBoundingClientRect(); return {{ x: b.left, y: b.top, w: b.width, h: b.height }}; }})()")
        if not r:
            raise RuntimeError(f"no existe {selector}")
        return r

    # ---------------------------------------------------------------- capturas
    def captura(self, salida: Path, recorte: dict | None = None, margen=6) -> Path:
        params = {"format": "png"}
        if recorte:
            x = max(0, recorte["x"] - margen)
            y = max(0, recorte["y"] - margen)
            params["clip"] = {"x": x, "y": y, "width": min(self.ancho - x, recorte["w"] + 2 * margen),
                              "height": min(self.alto - y, recorte["h"] + 2 * margen), "scale": 1}
        datos = self.enviar("Page.captureScreenshot", params)["data"]
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_bytes(base64.b64decode(datos))
        return salida

    def cerrar(self):
        try:
            self.ws.close()
        finally:
            self.proceso.terminate()
            try:
                self.proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proceso.kill()
            self.perfil.cleanup()


def anotar(ruta: Path, marcas: list[tuple[float, float, str]], origen=(0, 0), escala=1) -> Path:
    """Dibuja circulos numerados (x, y, texto) sobre la captura. `origen`: esquina de la captura en la pagina (en px
    CSS); `escala`: pixeles de la captura por px CSS (2 si el navegador captura al doble de resolucion)."""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(ruta).convert("RGB")
    d = ImageDraw.Draw(im)
    fuente = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", round(17 * escala))
    for x, y, texto in marcas:
        cx, cy, r, b = (x - origen[0]) * escala, (y - origen[1]) * escala, 15 * escala, 2 * escala
        d.ellipse([cx - r - b, cy - r - b, cx + r + b, cy + r + b], fill="#ffffff")
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#d62828")
        d.text((cx, cy), texto, fill="#ffffff", font=fuente, anchor="mm")
    im.save(ruta)
    return ruta
