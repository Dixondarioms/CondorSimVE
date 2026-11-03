"""Capturas del manual del Cóndor (tools/generar_manual_condor.py): recorre la interfaz real de un ejercicio con Chrome
manejado por CDP (navegador.py) y deja las imagenes en tools/manual/salida/condor/ (JPG).

Pone el reloj en marcha, da ordenes y despega aeronaves: correrlo SIEMPRE contra un servidor con una COPIA de la base,
nunca contra el del aula. Las cuentas se leen de un JSON local que no va al repositorio:
[{"usuario": "director", "clave": "..."}, {"usuario": "az.cmdte", ...}, ...]

    set SIMULADOR_DB=C:\\ruta\\copia.db & set SIMULADOR_RESPALDO_HORAS=0
    backend\\venv\\Scripts\\python -m app.servidor --port 8130
    set CONDOR_URL=http://127.0.0.1:8130 & set CONDOR_CUENTAS=C:\\ruta\\cuentas.json
    backend\\venv\\Scripts\\python tools/manual/capturas_condor.py            # todas
    backend\\venv\\Scripts\\python tools/manual/capturas_condor.py despegue   # algunas (por nombre)
"""

import json
import os
import sys
import traceback
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from navegador import Navegador, anotar  # noqa: E402

BASE = os.environ.get("CONDOR_URL", "http://127.0.0.1:8130")
ESCENARIO = int(os.environ.get("CONDOR_ESCENARIO", "15"))  # Operación Guri: dos bandos completos en Bolívar
# lista [{usuario, clave}] o {nombre: {usuario, clave}}
_cuentas = json.loads(Path(os.environ["CONDOR_CUENTAS"]).read_text(encoding="utf-8"))
CUENTAS = {c["usuario"]: c["clave"] for c in (_cuentas.values() if isinstance(_cuentas, dict) else _cuentas)}
SALIDA = Path(os.environ.get("CONDOR_CAPTURAS") or Path(__file__).resolve().parent / "salida" / "condor")
LISTO = "!document.getElementById('app').hidden && document.querySelectorAll('#oob .oob-item').length > 0 && window.__mapa"
GURI = (7.76, -62.99)


class Nav(Navegador):
    usuario = None

    def como(self, usuario: str) -> None:
        """Entra con esa cuenta si no es la de ahora (las ordenes y los despegues los da un bando, no el director)."""
        if self.usuario != usuario:
            self.entrar(usuario)

    def entrar(self, usuario: str) -> None:
        self.usuario = usuario
        self.enviar("Network.clearBrowserCookies")
        self.ir(f"{BASE}/", "document.readyState === 'complete'", 1)
        cuerpo = json.dumps({"username": usuario, "password": CUENTAS[usuario]})
        estado = self.js(f"fetch('/api/auth/login', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: {json.dumps(cuerpo)}}})"
                         ".then((r) => r.status)")
        if estado != 200:
            raise RuntimeError(f"no se pudo entrar como {usuario} ({estado})")
        self.js(f"localStorage.clear()")
        self.enviar("Page.navigate", {"url": f"{BASE}/?escenario={ESCENARIO}"})
        self.esperar(LISTO, 150)  # la primera carga tras arrancar el servidor puede tardar
        self.pausa(4)

    def unidad(self, nombre: str) -> dict:
        """Datos de una unidad del ejercicio (lat, lon, id) por su nombre exacto."""
        u = self.js(f"fetch('/api/escenarios/{ESCENARIO}').then((r) => r.json()).then((e) => (e.unidades || []).find((u) => u.nombre === {json.dumps(nombre)}))")
        if not u:
            raise RuntimeError(f"no existe la unidad {nombre}")
        return u

    def elegir(self, nombre: str) -> None:
        ok = self.js(f"(() => {{ const b = [...document.querySelectorAll('#oob .oob-item')].find((x) => x.textContent.includes({json.dumps(nombre)}));"
                     " if (!b) return false; b.scrollIntoView({block: 'center'}); b.click(); return true; })()")
        if not ok:
            raise RuntimeError(f"no esta en el orden de batalla: {nombre}")
        self.pausa(1.5)

    def pestana(self, nombre: str) -> None:
        self.clic(f"[role=tab][data-pestana={nombre}]")
        self.pausa(1)

    def tecla(self, tecla: str, codigo: int) -> None:
        for tipo in ("keyDown", "keyUp"):
            self.enviar("Input.dispatchKeyEvent", {"type": tipo, "key": tecla, "code": tecla, "windowsVirtualKeyCode": codigo})
        self.pausa(0.6)

    def cerrar_dialogos(self) -> None:
        self.js("document.querySelectorAll('dialog[open]').forEach((d) => d.close())")
        self.pausa(0.5)

    def sin_seleccion(self) -> None:
        if self.js("document.body.classList.contains('con-unidad')"):
            self.clic("#btn-cerrar-unidad")
            self.pausa(0.8)


def guardar(n: Nav, nombre: str, recorte=None, marcas=None, margen=6) -> None:
    ruta = n.captura(SALIDA / f"{nombre}.png", recorte, margen)
    if marcas:
        origen = (max(0, recorte["x"] - margen), max(0, recorte["y"] - margen)) if recorte else (0, 0)
        anotar(ruta, marcas, origen)
    Image.open(ruta).convert("RGB").save(ruta.with_suffix(".jpg"), "JPEG", quality=88)
    ruta.unlink()
    print("  ", nombre)


def centro(r: dict, dx=0.5, dy=0.5) -> tuple[float, float]:
    return r["x"] + r["w"] * dx, r["y"] + r["h"] * dy


def union(*rects: dict) -> dict:
    x0, y0 = min(r["x"] for r in rects), min(r["y"] for r in rects)
    x1, y1 = max(r["x"] + r["w"] for r in rects), max(r["y"] + r["h"] for r in rects)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def tarjeta(n: Nav, titulo: str) -> dict:
    """Recuadro de una tarjeta del panel derecho por su titulo."""
    r = n.js(f"(() => {{ const t = [...document.querySelectorAll('#panel-der .tarjeta')].find((s) => (s.querySelector('h2') || {{}}).textContent"
             f" && s.querySelector('h2').textContent.trim().startsWith({json.dumps(titulo)})); if (!t) return null; t.scrollIntoView({{block: 'start'}});"
             " const b = t.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height}; })()")
    if not r:
        raise RuntimeError(f"no hay tarjeta {titulo}")
    return r


# ------------------------------------------------------------------ capturas
def acceso(n: Nav) -> None:
    n.enviar("Network.clearBrowserCookies")
    n.ir(f"{BASE}/", "document.readyState === 'complete' && !document.getElementById('login').hidden", 2)
    guardar(n, "acceso", n.rect("#login > *"), margen=24)


def pantalla(n: Nav) -> None:
    n.elegir("A-29 Super Tucano 1 (Hotel)")
    n.vista(*GURI, 8, 4)
    marcas = [(*centro(n.rect("#cabecera"), 0.3), "1"), (*centro(n.rect("#panel-izq"), 0.5, 0.3), "2"),
              (*centro(n.rect("#map"), 0.45, 0.35), "3"), (*centro(n.rect("#panel-der"), 0.5, 0.3), "4"),
              (*centro(n.rect("#panel-unidad"), 0.5, 0.15), "5"), (*centro(n.rect("#control-turno"), 0.08), "6")]
    guardar(n, "pantalla", marcas=marcas)


def cabecera(n: Nav) -> None:
    guardar(n, "cabecera", n.rect("#cabecera"), margen=0)


def panel_unidad(n: Nav) -> None:
    n.elegir("A-29 Super Tucano 1 (Hotel)")
    n.pausa(3)
    guardar(n, "panel_unidad", n.rect("#panel-unidad"), margen=0)
    n.elegir("S-300VM Antey-2500 1 (Aves)")
    n.pausa(3)
    guardar(n, "panel_unidad_da", n.rect("#panel-unidad"), margen=0)


def orden_batalla(n: Nav) -> None:
    n.pestana("fuerzas")
    n.js("document.getElementById('panel-izq').scrollTop = 0")
    guardar(n, "orden_batalla", n.rect("#panel-izq"), margen=0)


def pliegues(n: Nav) -> None:
    n.clic("#btn-pliegue-izq")
    n.clic("#btn-pliegue-der")
    n.pausa(2)
    guardar(n, "paneles_escondidos")
    n.clic("#btn-pliegue-izq")
    n.clic("#btn-pliegue-der")
    n.pausa(1)


def reloj(n: Nav) -> None:
    guardar(n, "reloj", n.rect("#control-turno"), margen=0)


def despegue(n: Nav) -> None:
    n.como("az.cmdte")
    n.pestana("fuerzas")
    n.js("document.getElementById('sec-aviacion').scrollIntoView({block: 'start'})")
    n.pausa(0.5)
    guardar(n, "aviacion", n.rect("#sec-aviacion"))
    n.clic("#btn-enviar-caza")
    n.pausa(1.5)
    n.valor("#aer-buscar", "Tucano")
    n.js("document.getElementById('aer-buscar').dispatchEvent(new Event('input', {bubbles: true}))")
    n.pausa(2)
    guardar(n, "despegue", n.rect("#dlg-aeronaves"), margen=2)
    n.clic("#aer-cancelar")
    n.pausa(0.5)


def orden_mover(n: Nav) -> None:
    n.como("az.cmdte")
    nombre = "1.er Batallón de Asalto Aéreo (Echo)"
    u = n.unidad(nombre)
    n.elegir(nombre)
    n.vista(u["lat"], u["lon"], 10, 4)
    n.js("document.getElementById('sec-orden').scrollIntoView({block: 'start'})")
    n.pausa(0.5)
    for dlat, dlon in ((0.05, 0.08), (0.11, 0.15)):
        n.clic_mapa(u["lat"] + dlat, u["lon"] + dlon)
    n.pausa(1.5)
    guardar(n, "orden_nueva", n.rect("#sec-orden"))
    guardar(n, "orden_ruta", n.rect("#map"), margen=0)
    n.clic("#btn-emitir")
    n.pausa(2.5)
    n.js("[...document.querySelectorAll('#pest-fuerzas h2')].find((h) => h.textContent.startsWith('Cola')).scrollIntoView({block: 'start'})")
    n.pausa(0.5)
    titulo = n.js("(() => { const h = [...document.querySelectorAll('#pest-fuerzas h2')].find((h) => h.textContent.startsWith('Cola'));"
                  " const b = h.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height}; })()")
    guardar(n, "cola", union(titulo, n.rect("#cola")))


def _post(n: Nav, ruta: str, cuerpo: dict):
    return n.js(f"fetch('/api/escenarios/{ESCENARIO}{ruta}', {{method: 'POST', headers: {{'Content-Type': 'application/json'}},"
                f" body: {json.dumps(json.dumps(cuerpo))}}}).then((r) => r.json())")


def interceptar(n: Nav) -> None:
    """Un caza en alerta en tierra intercepta a un bandido que el director hace aparecer (en la COPIA de la base)."""
    n.como("director")
    bandido = _post(n, "/unidades", {"nombre": "Bandido (captura)", "bando": "rojo", "tipo": "aerea", "clase": "caza",
                                     "lat": 5.9, "lon": -67.3})
    n.como("ro.cmdte")
    _post(n, "/ordenes", {"unidad_id": bandido["id"], "tipo": "mover", "waypoints": [[5.9, -65.0]]})
    n.como("az.cmdte")
    nombre = "Escuadrón F-16 Block 70 1 (Echo)"
    u = n.unidad(nombre)
    n.elegir(nombre)
    n.vista(u["lat"] - 0.1, u["lon"] + 0.9, 8, 4)
    n.clic("[data-modo=interceptar]")
    n.pausa(1)
    n.js(f"const s = document.getElementById('o-objetivo'); s.value = '{bandido['id']}'; s.dispatchEvent(new Event('change'))")
    n.pausa(3)
    n.js("document.getElementById('sec-orden').scrollIntoView({block: 'start'})")
    n.pausa(0.5)
    guardar(n, "interceptar", n.rect("#sec-orden"))
    guardar(n, "interceptar_mapa", n.rect("#map"), margen=0)


def zonas(n: Nav) -> None:
    """Areas de patrulla y zonas de exclusion y no vuelo (en la COPIA de la base) y la orden Patrullar sobre un area."""
    n.como("director")
    _post(n, "/zonas", {"tipo": "no_vuelo", "nombre": "Puerto Ayacucho", "bando": "todos",
                        "puntos": [[5.55, -67.75], [5.75, -67.75], [5.75, -67.5], [5.55, -67.5]]})
    n.como("az.cmdte")
    _post(n, "/zonas", {"tipo": "patrulla", "nombre": "Sector Orinoco", "puntos": [[6.0, -67.6], [6.3, -67.2], [6.0, -66.8], [5.8, -67.2]]})
    _post(n, "/zonas", {"tipo": "exclusion", "nombre": "Represa", "armas": True,
                        "puntos": [[5.85, -67.0], [5.95, -66.85], [5.8, -66.75], [5.7, -66.9]]})
    n.como("az.cmdte")  # recarga para ver las zonas nuevas
    nombre = "Escuadrón Kfir 1 (Echo)"
    u = n.unidad(nombre)
    n.elegir(nombre)
    n.vista(u["lat"] + 0.25, u["lon"] + 0.4, 9, 4)
    n.clic("[data-modo=patrullar]")
    n.pausa(1)
    n.js("const s = document.getElementById('o-patrulla-area'); s.value = s.options[s.options.length - 1].value; s.dispatchEvent(new Event('change'))")
    n.pausa(2)
    n.js("document.getElementById('sec-orden').scrollIntoView({block: 'start'})")
    guardar(n, "patrulla_area", n.rect("#sec-orden"))
    guardar(n, "zonas_mapa", n.rect("#map"), margen=0)
    guardar(n, "zonas", tarjeta(n, "Áreas y zonas"))
    n.js("document.getElementById('panel-der').scrollTop = 0")


def carga(n: Nav) -> None:
    """Carga de armamento: la ventana de despegue con la carga y el panel de abajo de un grupo armado (en la COPIA)."""
    n.como("az.cmdte")
    n.pestana("fuerzas")
    n.clic("#btn-enviar-caza")
    n.pausa(1.5)
    n.valor("#aer-buscar", "F-16")
    n.js("document.getElementById('aer-buscar').dispatchEvent(new Event('input', {bubbles: true}))")
    n.pausa(1.5)
    n.js("const t = document.querySelector('#aer-tarjetas .tarjeta-modelo'); if (t) t.click();")
    n.pausa(1)
    n.js("const s = document.getElementById('aer-carga'); s.value = 'ataque'; s.dispatchEvent(new Event('change'));"
         " document.getElementById('aer-carga-fila').scrollIntoView({block: 'center'})")
    n.pausa(1)
    guardar(n, "despegue_carga", n.rect("#dlg-aeronaves"), margen=2)
    n.clic("#aer-cancelar")
    n.pausa(0.5)
    nombre = "Escuadrón F-16 Block 70 2 (Echo)"
    u = n.unidad(nombre)
    _post(n, "/ordenes", {"unidad_id": u["id"], "tipo": "mover", "waypoints": [[u["lat"] + 0.2, u["lon"] + 0.2]], "carga": "ataque"})
    n.pausa(2)
    n.elegir(nombre)
    n.pausa(2)
    guardar(n, "carga_panel", n.rect("#panel-unidad"), margen=0)
    n.como("director")
    base = next((x for x in n.js(f"fetch('/api/escenarios/{ESCENARIO}').then((r) => r.json()).then((e) => e.unidades)")
                 if x.get("existencias_armas")), None)
    if base:
        n.elegir(base["nombre"])
        n.pausa(2)
        n.js("const t = document.querySelector('.pu-notas'); if (t) t.scrollTop = t.scrollHeight;")
        guardar(n, "existencias_armas", n.rect("#panel-unidad"), margen=0)


def trafico(n: Nav) -> None:
    """Trafico civil sobre la costa (en la COPIA de la base): el reloj corre un rato para que aparezca."""
    n.como("director")
    n.sin_seleccion()
    n.pestana("consola")
    n.vista(10.9, -64.3, 8, 4)
    n.js("const d = document.getElementById('sec-trafico'); d.open = true; d.scrollIntoView({block: 'start'})")
    n.valor("#tr-aviones", 10)
    n.valor("#tr-mercantes", 6)
    n.valor("#tr-pesqueros", 6)
    n.clic("#btn-trafico")
    n.pausa(2)
    n.clic("#control-turno [data-vel='60']")
    n.clic("#btn-marcha")
    n.pausa(25)
    n.clic("#btn-marcha")  # detener
    n.pausa(3)
    guardar(n, "trafico", n.rect("#sec-trafico"))
    guardar(n, "trafico_mapa", n.rect("#map"), margen=0)
    n.pestana("fuerzas")


def doctrina(n: Nav) -> None:
    n.pestana("fuerzas")
    n.js("const d = document.getElementById('sec-doctrina'); d.querySelectorAll('details').forEach((x) => x.open = true); d.scrollIntoView({block: 'start'})")
    n.pausa(1)
    guardar(n, "doctrina", n.rect("#sec-doctrina"))


def misiones(n: Nav) -> None:
    n.como("az.cmdte")
    n.pestana("fuerzas")
    n.js("document.getElementById('sec-misiones').scrollIntoView({block: 'start'})")
    n.clic("#btn-planificar-mision")
    n.pausa(2)
    guardar(n, "mision_planificar", n.rect("#panel-mision"))
    n.clic("#pm-cerrar")
    n.pausa(0.5)
    n.clic("#btn-cronograma")
    n.pausa(2)
    guardar(n, "cronograma", n.rect("#dlg-cronograma"), margen=2)
    n.cerrar_dialogos()
    n.como("director")


def situacion(n: Nav) -> None:
    n.pestana("situacion")
    n.js("document.getElementById('panel-izq').scrollTop = 0")
    guardar(n, "situacion", n.rect("#panel-izq"), margen=0)


def tiem(n: Nav) -> None:
    n.pestana("pmo")
    n.js("document.getElementById('panel-izq').scrollTop = 0")
    guardar(n, "tiem", n.rect("#panel-izq"), margen=0)


def consola(n: Nav) -> None:
    n.pestana("consola")
    n.js("document.getElementById('panel-izq').scrollTop = 0")
    guardar(n, "consola", n.rect("#panel-izq"), margen=0)
    n.pestana("fuerzas")


def capas(n: Nav) -> None:
    guardar(n, "capas", tarjeta(n, "Capas"))
    n.js("document.getElementById('panel-der').scrollTop = 0")


def graficos(n: Nav) -> None:
    guardar(n, "graficos", n.rect("#barra-graficos"))
    n.clic("#btn-plegar-graficos")
    guardar(n, "graficos_plegado", union(n.rect("#barra-graficos"), n.rect("#barra-herramientas")))
    n.clic("#btn-plegar-graficos")


def mapas(n: Nav) -> None:
    n.sin_seleccion()
    for region, nombre in (("Mundo", "mapa_mundo"), ("Venezuela", "mapa_venezuela")):
        n.js(f"[...document.querySelectorAll('#mapas-ir button')].find((b) => b.textContent.includes({json.dumps(region)})).click()")
        n.pausa(14)
        guardar(n, nombre, n.rect("#map"), margen=0)
    n.vista(*GURI, 8, 6)


def ayuda(n: Nav) -> None:
    n.clic("#btn-ayuda")
    n.pausa(1.5)
    n.js("const q = document.querySelector('#dlg-ayuda input[type=search]'); if (q) { q.value = 'despegar aviones'; q.dispatchEvent(new Event('input', {bubbles: true})); }")
    n.pausa(1.5)
    guardar(n, "ayuda", n.rect("#dlg-ayuda"), margen=2)
    n.cerrar_dialogos()


def informe(n: Nav) -> None:
    n.cerrar_dialogos()
    n.clic("#btn-informe")
    n.pausa(3)
    visible = n.js("(() => { const d = [...document.querySelectorAll('dialog[open], #replay:not([hidden])')]; return d.length ? (d[0].id || 'replay') : null; })()")
    if visible:
        guardar(n, "informe", n.rect(f"#{visible}"), margen=2)
    n.cerrar_dialogos()
    n.js("const c = document.getElementById('rp-cerrar'); if (c && c.offsetParent) c.click();")


def en_marcha(n: Nav) -> None:
    """Reloj en marcha a 60x unos minutos: aeronaves en vuelo, alertas y estelas (en la COPIA de la base)."""
    n.clic("#control-turno [data-vel='60']")
    n.clic("#btn-marcha")
    n.pausa(45)
    guardar(n, "reloj_en_marcha", n.rect("#control-turno"), margen=0)
    guardar(n, "alertas", tarjeta(n, "Alertas"))
    n.js("document.getElementById('panel-der').scrollTop = 0")
    if n.js("!document.getElementById('banner-pausa').hidden"):
        guardar(n, "pausa_automatica", union(n.rect("#banner-pausa"), n.rect("#cabecera")), margen=0)
    n.sin_seleccion()
    n.vista(*GURI, 8, 4)
    guardar(n, "mapa_en_marcha", n.rect("#map"), margen=0)
    if not n.js("document.getElementById('banner-pausa').hidden"):
        n.clic("#banner-pausa-reanudar")
    else:
        n.clic("#btn-marcha")  # detener
    n.pausa(1)


def bando(n: Nav) -> None:
    """Lo que ve un bando: niebla de guerra y contactos con su circulo de incertidumbre."""
    n.como("az.cmdte")
    n.sin_seleccion()
    n.vista(*GURI, 8, 6)
    guardar(n, "bando_azul", marcas=None)
    n.pestana("situacion")
    n.js("document.getElementById('sec-radar').scrollIntoView({block: 'start'})")
    n.pausa(1)
    guardar(n, "cuadro_radar", n.rect("#sec-radar"))


def videowall(n: Nav) -> None:
    n.como("director")
    n.sin_seleccion()
    n.vista(*GURI, 8, 4)
    n.clic("#btn-videowall")
    n.pausa(3)
    guardar(n, "videowall")
    n.tecla("Escape", 27)


ORDEN = [acceso, pantalla, cabecera, panel_unidad, orden_batalla, pliegues, reloj, despegue, orden_mover, interceptar, zonas, carga, trafico, doctrina, misiones,
         situacion, tiem, consola, capas, graficos, mapas, ayuda, informe, en_marcha, bando, videowall]


def main() -> int:
    pedidas = set(sys.argv[1:])
    n = Nav(1600, 900, 1)
    fallas = []
    try:
        n.entrar("director")
        for f in ORDEN:
            if pedidas and f.__name__ not in pedidas:
                continue
            try:
                if f not in (acceso, despegue, orden_mover, interceptar, zonas, carga, misiones, bando):
                    n.como("director")
                f(n)
                if f is acceso:
                    n.entrar("director")
            except Exception as e:  # una captura que falla no frena a las demas
                fallas.append(f.__name__)
                print(f"!! {f.__name__}: {e}")
                traceback.print_exc(limit=1)
    finally:
        n.cerrar()
    print("fallaron:", ", ".join(fallas) or "ninguna")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
