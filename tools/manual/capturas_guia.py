"""Capturas del manual de usuario (tools/generar_manual_usuario.py): recorre cada parte de la interfaz en el arnes de
pruebas (datos de ejemplo, sin sesion ni base de datos) con Chrome manejado por CDP (navegador.py), haciendo los
clics que muestran cada pantalla, y deja las imagenes en tools/manual/salida/guia/ (PNG y JPG).

Requiere el servidor en marcha en 127.0.0.1:8000 (la pantalla de acceso es la real; todo lo demas, el arnes).

    backend\\venv\\Scripts\\python tools/manual/capturas_guia.py            # todas
    backend\\venv\\Scripts\\python tools/manual/capturas_guia.py orden_mover # algunas (por nombre)
"""

import os
import sys
import time
import traceback
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from navegador import Navegador, anotar  # noqa: E402

BASE = os.environ.get("SIETE_URL", "http://127.0.0.1:8000")  # otro puerto: SIETE_URL=http://127.0.0.1:8002
SALIDA = Path(__file__).resolve().parent / "salida" / "guia"
LISTA_APP = "!document.getElementById('app').hidden && document.querySelectorAll('#oob .oob-item').length > 0 && window.__mapa"
LLANOS = (8.6, -70.57)  # despliegue de ejemplo en el piedemonte andino
CARIBE = (10.66, -67.98)  # grupo naval frente a Puerto Cabello
# ejercicio contra la IA: el rojo lo conduce el adversario automatico, con el ciclo de dia y noche y de noche (23:00)
CONTRA_IA = "&ia=rojo&nivel=prudente&noche=1&hora=1260"


def arnes(rol="instructor", puesto=None, lat=LLANOS[0], lon=LLANOS[1], zoom=11, extra=""):
    p = f"&puesto={puesto}" if puesto else ""
    return f"{BASE}/static/pruebas/arnes.html?rol={rol}{p}&lat={lat}&lon={lon}&zoom={zoom}{extra}"


def guardar(n: Navegador, nombre: str, recorte=None, marcas=None, margen=6) -> None:
    ruta = n.captura(SALIDA / f"{nombre}.png", recorte, margen)
    if marcas:
        origen = (max(0, recorte["x"] - margen), max(0, recorte["y"] - margen)) if recorte else (0, 0)
        anotar(ruta, marcas, origen)
    Image.open(ruta).convert("RGB").save(ruta.with_suffix(".jpg"), "JPEG", quality=86)


def centro(r: dict, dx=0.5, dy=0.5) -> tuple[float, float]:
    return r["x"] + r["w"] * dx, r["y"] + r["h"] * dy


def union(*rects: dict) -> dict:
    x0 = min(r["x"] for r in rects)
    y0 = min(r["y"] for r in rects)
    x1 = max(r["x"] + r["w"] for r in rects)
    y1 = max(r["y"] + r["h"] for r in rects)
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def rect_mapa(n: Navegador) -> dict:
    """Recuadro del mapa sin el panel derecho, que se superpone a su borde."""
    r = n.rect("#map")
    der = n.rect("#panel-der")
    if der["w"] > 0 and r["x"] < der["x"] < r["x"] + r["w"]:
        r["w"] = der["x"] - r["x"]
    return r


def seleccionar(n: Navegador, uid: int, ctrl=False):
    n.clic(f'#oob .oob-item[data-id="{uid}"]', ctrl=ctrl)
    time.sleep(0.6)


def al_panel(n: Navegador, selector: str):
    """Desplaza el panel lateral para que se vea ese bloque arriba."""
    n.js(f"document.querySelector({selector!r}).scrollIntoView({{ block: 'start' }})")
    time.sleep(0.4)


def consola(n: Navegador, *secciones: str):
    """Abre la pestaña Consola con solo esas secciones desplegadas (por el texto de su titulo)."""
    n.clic('[data-pestana="consola"]')
    nombres = [s.lower() for s in secciones]
    n.js("(() => { const ns = %s; document.querySelectorAll('#pest-consola details').forEach((d) => {"
         " const t = d.querySelector('summary').textContent.trim().toLowerCase(); d.open = ns.some((s) => t.startsWith(s)); });"
         " document.getElementById('panel-izq').scrollTop = 0;"
         " const abierta = document.querySelector('#pest-consola details[open]');"
         " if (abierta) abierta.scrollIntoView({ block: 'start' }); })()" % nombres)
    time.sleep(0.5)


# ------------------------------------------------------------------ acceso
def acceso_login(n):
    n.ir(f"{BASE}/", "!document.getElementById('login').hidden", 1.5)
    guardar(n, "acceso_login", n.rect("#login-form"), margen=14)


def acceso_registro(n):
    n.ir(f"{BASE}/", "!document.getElementById('login').hidden", 1)
    n.clic("#btn-ir-registro")
    n.valor("#r-user", "carlos.perez")
    n.valor("#r-rol", "azul")
    n.valor("#r-puesto", "operaciones")
    guardar(n, "acceso_registro", n.rect("#registro-form"), margen=14)


def acceso_clave(n):
    n.ir(arnes("azul"), LISTA_APP, 1)
    n.clic("#btn-perfil")
    n.clic("#btn-cambiar-clave")
    n.js("document.getElementById('c-motivo').textContent = 'Hola carlos.perez: su contraseña es provisional (inicial o puesta por el instructor). Elija una nueva para continuar.'")
    n.js("document.getElementById('btn-clave-salir').textContent = 'Cerrar sesión'")
    guardar(n, "acceso_clave", n.rect("#clave-form"), margen=14)


def menu_perfil(n):
    n.ir(arnes("azul"), LISTA_APP, 1)
    n.clic("#btn-perfil")
    r = union(n.rect("#btn-perfil"), n.rect("#menu-perfil"))
    r["x"] -= 230
    r["w"] += 230
    guardar(n, "menu_perfil", r, margen=10)


# ------------------------------------------------------------------ la pantalla
def pantalla_general(n):
    n.ir(arnes("instructor"), LISTA_APP, 3)
    graf = n.rect("#barra-graficos")
    der = n.rect("#panel-der")
    marcas = [
        (24, 28, "1"),
        (*centro(n.rect("#panel-izq"), 0.5, 0.42), "2"),
        (*centro(n.rect("#map"), 0.6, 0.85), "3"),
        (der["x"] + der["w"] - 22, der["y"] + 20, "4"),
        (*centro(n.rect("#control-turno"), 0.25, 0.5), "5"),
        (*centro(n.rect("#barra-herramientas"), 1.25, 0.5), "6"),
        (graf["x"] + graf["w"] + 4, graf["y"] + 4, "7"),
    ]
    guardar(n, "pantalla_general", marcas=marcas)


def cabecera(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    r = n.rect("#cabecera")
    # una franja oscura debajo de la cabecera para poner cada numero bajo su boton, sin tapar los rotulos
    n.js("(() => { const d = document.createElement('div'); d.id = 'franja-manual'; d.style.cssText ="
         " 'position:fixed;left:0;right:0;top:' + document.getElementById('cabecera').getBoundingClientRect().bottom +"
         " 'px;height:40px;background:#141826;z-index:5000'; document.body.appendChild(d); })()")
    abajo = r["y"] + r["h"] + 20

    def bajo(sel, dx=0.5):
        b = n.rect(sel)
        return (b["x"] + b["w"] * dx, abajo)
    marcas = [(*bajo("#escenario", 0.5), "1"), (*bajo("#btn-nuevo-escenario"), "2"), (*bajo("#btn-plantillas"), "3"),
              (*bajo("#btn-guardar-plantilla"), "4"), (*bajo("#estado-conexion"), "5"), (*bajo("#reloj"), "6"),
              (*bajo("#btn-videowall"), "7"), (*bajo("#btn-informe"), "8"), (*bajo("#btn-perfil"), "9")]
    r["h"] += 40
    guardar(n, "cabecera", r, marcas, margen=4)


def alumno_pantalla(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 3)
    marcas = [
        (*centro(n.rect("#cabecera"), 0.12, 0.5), "1"),
        (*centro(n.rect("#oob-titulo"), 0.85, 0.5), "2"),
        (*centro(n.rect("#map"), 0.5, 0.55), "3"),
        (*centro(n.rect("#panel-der"), 0.85, 0.2), "4"),
        (*centro(n.rect("#btn-listo"), 0.06, 0.5), "5"),
    ]
    guardar(n, "alumno_pantalla", marcas=marcas)


def alumno_secciones(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 1.5)
    seleccionar(n, 2)
    al_panel(n, "#sec-puesto")
    r = n.rect("#panel-izq")
    marcas = [(*centro(n.rect("#sec-puesto h2"), 0.95, 0.5), "1"), (*centro(n.rect("#sec-aviacion h2"), 0.95, 0.5), "2"),
              (*centro(n.rect("#sec-misiones h2"), 0.95, 0.5), "3"), (*centro(n.rect("#sec-orden h2"), 0.95, 0.5), "4")]
    guardar(n, "alumno_secciones", r, marcas, margen=0)


def oob_ficha(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 1.5)
    seleccionar(n, 2)
    n.js("document.getElementById('panel-izq').scrollTop = 0")
    time.sleep(0.3)
    guardar(n, "oob", n.rect("#panel-izq"), margen=0)
    al_panel(n, "#detalle-contenido")
    n.js("document.getElementById('panel-izq').scrollTop -= 40")
    guardar(n, "ficha_unidad", n.rect("#panel-izq"), margen=0)


def ficha_acciones(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 1.5)
    seleccionar(n, 19)
    al_panel(n, "#detalle-contenido")
    n.js("document.getElementById('panel-izq').scrollTop -= 40")
    guardar(n, "ficha_acciones", n.rect("#panel-izq"), margen=0)


# ------------------------------------------------------------------ ordenes
def orden_mover(n):
    n.ir(arnes("azul", "mando", 8.6, -70.55, 11), LISTA_APP, 2)
    seleccionar(n, 2)
    n.clic('[data-modo="mover"]')
    n.vista(8.54, -70.6, 11, 1.5)
    # puntos de paso al sur, en terreno libre (un clic sobre otra unidad la seleccionaria)
    for lat, lon in [(8.53, -70.66), (8.5, -70.6), (8.48, -70.54)]:
        n.clic_mapa(lat, lon)
    al_panel(n, "#sec-orden")
    time.sleep(1)
    guardar(n, "orden_mover")


def orden_atacar(n):
    n.ir(arnes("azul", "mando", 8.62, -70.6, 12), LISTA_APP, 2)
    seleccionar(n, 3)
    n.clic('[data-modo="atacar"]')
    n.valor("#o-objetivo", "11")
    n.vista(8.62, -70.61, 12, 1.5)
    al_panel(n, "#sec-orden")
    time.sleep(1)
    guardar(n, "orden_atacar")


def seleccion_multiple(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 2)
    seleccionar(n, 1)
    seleccionar(n, 2, ctrl=True)
    seleccionar(n, 3, ctrl=True)
    n.clic('[data-modo="mover"]')
    n.vista(8.55, -70.61, 11, 1.5)
    for lat, lon in [(8.53, -70.63), (8.495, -70.58)]:
        n.clic_mapa(lat, lon)
    al_panel(n, "#sec-orden")
    time.sleep(1)
    guardar(n, "seleccion_multiple")


def orden_construir(n):
    n.ir(arnes("azul", "logistica"), LISTA_APP, 2)
    seleccionar(n, 4)
    n.clic('[data-modo="construir"]')
    al_panel(n, "#sec-orden")
    guardar(n, "orden_construir", n.rect("#panel-izq"), margen=0)


def cola_y_listo(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 2)
    al_panel(n, ".cola")
    guardar(n, "cola_ordenes", n.rect(".cola"), margen=8)
    guardar(n, "barra_inferior", n.rect("#control-turno"), margen=0)


# ------------------------------------------------------------------ aviacion
def aviacion_enviar(n):
    n.ir(arnes("azul", "planificacion"), LISTA_APP, 2)
    n.clic("#btn-enviar-caza")
    n.esperar("document.getElementById('dlg-aeronaves').open")
    time.sleep(1)
    guardar(n, "aviacion_enviar", n.rect("#dlg-aeronaves"), margen=4)


def orden_patrullar(n):
    n.ir(arnes("azul", "operaciones", 8.68, -70.45, 10), LISTA_APP, 2)
    seleccionar(n, 8)
    n.clic('[data-modo="patrullar"]')
    n.vista(8.68, -70.45, 10, 1.5)
    n.clic_mapa(8.78, -70.42)
    al_panel(n, "#sec-orden")
    time.sleep(1)
    guardar(n, "orden_patrullar")


def mision_planificar(n):
    n.ir(arnes("azul", "operaciones", 8.66, -70.5, 11), LISTA_APP, 2)
    n.clic("#btn-planificar-mision")
    n.esperar("!document.getElementById('panel-mision').hidden")
    n.js("document.getElementById('pm-origen-grupo').click()")
    time.sleep(0.4)
    n.valor("#pm-grupo", "8")
    n.valor("#pm-rol", "INTERDICCION")
    n.vista(8.66, -70.5, 11, 1.5)
    for lat, lon in [(8.68, -70.55), (8.662, -70.6)]:
        n.clic_mapa(lat, lon)
    time.sleep(1.5)
    guardar(n, "mision_planificar")


def perfil_vuelo(n):
    n.ir(arnes("azul", "operaciones"), LISTA_APP, 2)
    seleccionar(n, 10)
    n.js("document.querySelector('.perfil-vuelo').scrollIntoView({ block: 'center' })")
    time.sleep(0.4)
    guardar(n, "perfil_vuelo", n.rect("#panel-izq"), margen=0)


def cobertura_radar(n):
    n.ir(arnes("instructor", lat=8.72, lon=-70.56, zoom=9), LISTA_APP, 2)
    seleccionar(n, 18)
    n.vista(8.68, -70.56, 9, 3)
    guardar(n, "cobertura_radar", rect_mapa(n), margen=0)


def cronograma(n):
    n.ir(arnes("azul", "operaciones"), LISTA_APP, 2)
    n.clic("#btn-cronograma")
    n.esperar("document.getElementById('dlg-cronograma').open")
    time.sleep(1)
    guardar(n, "cronograma", n.rect("#dlg-cronograma"), margen=4)


def misiones_lista(n):
    n.ir(arnes("azul", "operaciones"), LISTA_APP, 2)
    al_panel(n, "#sec-misiones")
    guardar(n, "misiones_lista", n.rect("#sec-misiones"), margen=6)


# ------------------------------------------------------------------ naval, guerra electronica
def naval_misiles(n):
    n.ir(arnes("azul", "mando", *CARIBE, 10), LISTA_APP, 2)
    seleccionar(n, 20)
    n.clic('[data-modo="lanzar"]')
    n.valor("#o-objetivo", "23")
    n.vista(10.69, -67.92, 10, 1.5)
    al_panel(n, "#sec-orden")
    time.sleep(1)
    guardar(n, "naval_misiles")


def naval_desembarcar(n):
    n.ir(arnes("azul", "mando", *CARIBE, 11), LISTA_APP, 2)
    seleccionar(n, 26)
    n.clic('[data-modo="desembarcar"]')
    n.vista(10.55, -68.08, 11, 1.5)
    for lat, lon in [(10.56, -68.07), (10.505, -68.03)]:
        n.clic_mapa(lat, lon)
    al_panel(n, "#sec-orden")
    time.sleep(1)
    guardar(n, "naval_desembarcar")


def orden_interferir(n):
    n.ir(arnes("azul", "inteligencia", 8.62, -70.62, 10), LISTA_APP, 2)
    seleccionar(n, 16)
    n.clic('[data-modo="interferir"]')
    n.vista(8.64, -70.62, 10, 1.5)
    n.clic_mapa(8.7, -70.58)
    al_panel(n, "#sec-orden")
    time.sleep(1)
    guardar(n, "orden_interferir")


# ------------------------------------------------------------------ mapa
def panel_derecho(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 2)
    n.js("document.getElementById('panel-der').scrollTop = 0")
    guardar(n, "panel_der_arriba", n.rect("#panel-der"), margen=0)
    n.js("document.getElementById('tarjeta-chat').scrollIntoView({ block: 'start' })")
    time.sleep(0.4)
    guardar(n, "panel_der_abajo", n.rect("#panel-der"), margen=0)


def capas(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    n.js("document.querySelector('.capas').closest('.tarjeta').scrollIntoView({ block: 'start' })")
    time.sleep(0.4)
    tarjeta = n.js("(() => { const b = document.querySelector('.capas').closest('.tarjeta').getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; })()")
    guardar(n, "capas", tarjeta, margen=4)


def mapa_relieve(n):
    n.ir(arnes("instructor", lat=8.65, lon=-70.7, zoom=9), LISTA_APP, 2)
    n.clic("#base-relieve")
    time.sleep(2.5)
    guardar(n, "mapa_relieve", rect_mapa(n), margen=0)


def mapa_zoom(n):
    n.ir(arnes("instructor", lat=9.4, lon=-69.4, zoom=7), LISTA_APP, 3)
    guardar(n, "mapa_lejos", rect_mapa(n), margen=0)
    n.vista(8.6, -70.57, 10, 3)
    guardar(n, "mapa_cerca", rect_mapa(n), margen=0)


def mapa_regla(n):
    n.ir(arnes("instructor", lat=8.48, lon=-70.55, zoom=10), LISTA_APP, 2)
    n.clic("#btn-regla")
    for lat, lon in [(8.40, -70.80), (8.47, -70.44), (8.37, -70.33)]:  # puntos sin unidades (un clic en una unidad la selecciona)
        n.clic_mapa(lat, lon)
    n.cursor_mapa(8.37, -70.33)
    time.sleep(0.8)
    guardar(n, "mapa_regla", rect_mapa(n), margen=0)


def mapa_graficos(n):
    n.ir(arnes("azul", "mando", 8.64, -70.6, 11), LISTA_APP, 2)
    n.js("document.getElementById('zona-mapa').classList.add('ver-graficos')")
    n.clic('[data-grafico="eje_avance"]')
    n.valor("#graf-etiqueta", "EJE BRAVO")
    for lat, lon in [(8.6, -70.62), (8.63, -70.6), (8.66, -70.57)]:
        n.clic_mapa(lat, lon)
    time.sleep(0.8)
    guardar(n, "mapa_graficos", rect_mapa(n), margen=0)


def mapa_ficha(n):
    n.ir(arnes("azul", "mando", 8.62, -70.52, 11), LISTA_APP, 2)
    n.cursor_mapa(8.650, -70.500)
    x, y = n.punto_mapa(8.650, -70.500)
    guardar(n, "mapa_ficha", {"x": x - 260, "y": y - 250, "w": 520, "h": 330}, margen=0)


def mapa_aerodromo(n):
    n.ir(arnes("instructor", lat=8.6165, lon=-70.2175, zoom=15), LISTA_APP, 4)
    guardar(n, "mapa_aerodromo", rect_mapa(n), margen=0)


def mapa_meteo(n):
    n.ir(arnes("instructor", lat=8.6, lon=-70.6, zoom=8), LISTA_APP, 3)
    guardar(n, "mapa_meteo", rect_mapa(n), margen=0)


# ------------------------------------------------------------------ instructor
def consola_turno(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "turno y configuración")
    guardar(n, "consola_turno", n.rect("#panel-izq"), margen=0)


def consola_meteo(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "meteorología")
    guardar(n, "consola_meteo", n.rect("#panel-izq"), margen=0)


def consola_identidad(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "identidad nacional", "comunicaciones simuladas")
    guardar(n, "consola_identidad", n.rect("#panel-izq"), margen=0)


def consola_agregar(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "agregar unidad")
    n.valor("#u-nombre", "Escuadrón Centauro")
    n.valor("#u-clase", "caza")
    guardar(n, "consola_agregar", n.rect("#panel-izq"), margen=0)
    n.clic("#btn-elegir-modelo")
    n.esperar("document.getElementById('dlg-aeronaves').open")
    time.sleep(1)
    guardar(n, "elegir_aeronave", n.rect("#dlg-aeronaves"), margen=4)


def consola_objetivos(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "objetivos y puntaje")
    guardar(n, "consola_objetivos", n.rect("#panel-izq"), margen=0)


def consola_direccion(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "editar el escenario", "dirección del ejercicio")
    guardar(n, "consola_direccion", n.rect("#panel-izq"), margen=0)


def consola_eventos(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "eventos e informes")
    n.valor("#ev-desc", "Columna de vehículos blindados avistada por pobladores en la carretera Barinas - Guanare")
    n.valor("#ev-bando", "azul")
    n.valor("#ev-fuente", "Población")
    guardar(n, "consola_eventos", n.rect("#panel-izq"), margen=0)


def consola_escenario(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "escenario")
    guardar(n, "consola_escenario", n.rect("#panel-izq"), margen=0)


def consola_usuarios(n):
    n.ir(arnes("instructor"), LISTA_APP, 2)
    consola(n, "usuarios")
    time.sleep(1)
    guardar(n, "consola_usuarios", n.rect("#panel-izq"), margen=0)


def plantillas(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    n.clic("#btn-plantillas")
    n.esperar("document.getElementById('dlg-plantillas').open")
    time.sleep(1)
    guardar(n, "plantillas", n.rect("#dlg-plantillas"), margen=4)
    n.js("document.getElementById('dlg-plantillas').close()")
    n.clic("#btn-guardar-plantilla")
    n.esperar("document.getElementById('dlg-guardar-plantilla').open")
    n.valor("#gp-nombre", "Defensa de Barinas, situación al turno 3")
    time.sleep(0.5)
    guardar(n, "guardar_plantilla", n.rect("#dlg-guardar-plantilla"), margen=4)


def ver_como(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "turno y configuración")
    r = n.rect("#cfg-vista")
    guardar(n, "ver_como", {"x": r["x"] - 6, "y": r["y"] - 26, "w": r["w"] + 12, "h": r["h"] + 32}, margen=4)


def videowall(n):
    n.ir(arnes("instructor", lat=8.62, lon=-70.5, zoom=10, extra="&modo=videowall&vista=completa"), LISTA_APP, 3)
    guardar(n, "videowall")


def observador(n):
    n.ir(arnes("observador"), LISTA_APP, 3)
    guardar(n, "observador")


# ------------------------------------------------------------------ combate contra la IA, dia y noche
def ia_pantalla(n):
    n.ir(arnes("azul", "mando", extra=CONTRA_IA), LISTA_APP, 3)
    marcas = [
        (*centro(n.rect("#esc-hora"), -0.25, 0.5), "1"),
        (*centro(n.rect("#map"), 0.25, 0.8), "2"),
        (*centro(n.rect("#estado-rojo"), 1.1, 0.5), "3"),
        (*centro(n.rect("#btn-listo"), 0.06, 0.5), "4"),
    ]
    guardar(n, "ia_pantalla", marcas=marcas)


def consola_ia(n):
    n.ir(arnes("instructor", extra=CONTRA_IA), LISTA_APP, 1.5)
    # panel mas ancho para que los numeros queden a la derecha sin tapar los rotulos
    n.js("document.documentElement.style.setProperty('--ancho-izq', '440px')")
    time.sleep(0.5)
    consola(n, "dirección del ejercicio")
    r = n.rect("#panel-izq")
    der = r["x"] + r["w"] - 16
    marcas = [(der, n.rect("#dir-noche")["y"] + 10, "1"), (der, n.rect("#dir-ia-azul")["y"] + 10, "2"),
              (der, n.rect("#dir-ia-nivel")["y"] - 10, "3"), (*centro(n.rect("#btn-demo"), 1.12, 0.5), "4")]
    guardar(n, "consola_ia", r, marcas, margen=0)


def plantillas_ia(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    n.clic("#btn-plantillas")
    n.esperar("document.getElementById('dlg-plantillas').open && document.querySelector('[data-plantilla-id=\"defensa_aerea_central\"]')")
    n.js("document.querySelector('[data-plantilla-id=\"defensa_aerea_central\"]').scrollIntoView({ block: 'start' })")
    time.sleep(0.6)
    guardar(n, "plantillas_ia", n.rect("#dlg-plantillas"), margen=4)


def barra_inferior_ia(n):
    n.ir(arnes("azul", "mando", extra=CONTRA_IA), LISTA_APP, 2)
    guardar(n, "barra_inferior_ia", n.rect("#control-turno"), margen=0)


def mapa_dia_noche(n):
    for nombre, extra in (("mapa_dia", "&noche=1&hora=480"), ("mapa_crepusculo", "&noche=1&hora=960"), ("mapa_noche", "&noche=1&hora=1260")):
        n.ir(arnes("azul", "mando", 8.6, -70.58, 11, extra=extra), LISTA_APP, 3)
        r = rect_mapa(n)
        guardar(n, nombre, {"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"]}, margen=0)
    tarjeta = n.js("(() => { const b = document.getElementById('esc-hora').closest('.tarjeta').getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; })()")
    guardar(n, "estado_noche", tarjeta, margen=4)


def mapa_carreteras(n):
    n.ir(arnes("instructor", lat=8.62, lon=-70.24, zoom=12), LISTA_APP, 4)
    guardar(n, "mapa_carreteras", rect_mapa(n), margen=0)


def consola_catalogo(n):
    n.ir(arnes("instructor"), LISTA_APP, 1.5)
    consola(n, "catálogo propio")
    n.valor("#mp-clase", "radar")
    n.js("document.getElementById('mp-clase').dispatchEvent(new Event('change'))")
    n.valor("#mp-tipo-nombre", "JY-27A")
    n.valor("#mp-corto", "JY-27A")
    n.valor("#mp-pais", "China")
    n.js("document.activeElement.blur()")
    time.sleep(0.3)
    n.js("(() => { const d = document.querySelector('#pest-consola details[open]'); const p = document.getElementById('panel-izq');"
         " p.scrollTop += d.getBoundingClientRect().top - p.getBoundingClientRect().top - 40; })()")
    time.sleep(0.4)
    guardar(n, "consola_catalogo", n.rect("#panel-izq"), margen=0)


# ------------------------------------------------------------------ situacion: radar, personal, infraestructura
def situacion(n):
    n.ir(arnes("azul", "mando"), LISTA_APP, 2)
    n.clic('[data-pestana="situacion"]')
    time.sleep(0.6)
    n.js("document.getElementById('panel-izq').scrollTop = 0")
    time.sleep(0.3)
    guardar(n, "situacion_radar", n.rect("#panel-izq"), margen=0)
    n.js("document.getElementById('sec-personal').scrollIntoView({ block: 'start' })")
    time.sleep(0.4)
    guardar(n, "situacion_personal", n.rect("#panel-izq"), margen=0)


def mapa_infraestructura(n):
    n.ir(arnes("instructor", lat=8.72, lon=-70.45, zoom=10), LISTA_APP, 3)
    guardar(n, "mapa_infraestructura", rect_mapa(n), margen=0)
    # ficha de una instalacion real de la capa (Hidroelectrica Masparro, en el piedemonte)
    n.js("(() => { const m = []; window.__mapa.eachLayer((l) => { if (l.getPopup && l.getPopup() && l.getTooltip && l.getTooltip()"
         " && /Masparro/.test(l.getTooltip().getContent())) m.push(l); }); if (m[0]) m[0].openPopup(); })()")
    time.sleep(1.2)
    guardar(n, "ficha_infraestructura", n.rect(".leaflet-popup"), margen=8)


def ficha_puente(n):
    n.ir(arnes("azul", "mando", 8.6055, -70.585, 13), LISTA_APP, 2)
    seleccionar(n, 31)
    al_panel(n, "#detalle-contenido")
    n.js("document.getElementById('panel-izq').scrollTop -= 40")
    guardar(n, "ficha_puente", n.rect("#panel-izq"), margen=0)


def objetivos_avance(n):
    n.ir(arnes("instructor"), LISTA_APP, 2)
    guardar(n, "objetivos_avance", n.rect("#tarjeta-objetivos"), margen=4)


# ------------------------------------------------------------------ informe
def informe_repeticion(n):
    n.ir(arnes("instructor", extra="&abrir=informe"), LISTA_APP + " && !document.getElementById('replay').hidden", 3)
    guardar(n, "informe_repeticion")
    guardar(n, "informe_barra", n.rect("#replay .fila-replay"), margen=6)


def informe_dialogos(n):
    n.ir(arnes("instructor", extra="&abrir=informe"), LISTA_APP + " && !document.getElementById('replay').hidden", 2)
    n.clic("#rp-resumen")
    n.esperar("document.getElementById('dlg-resumen').open")
    time.sleep(0.8)
    guardar(n, "informe_resumen", n.rect("#dlg-resumen"), margen=4)
    n.js("document.getElementById('dlg-resumen').close()")
    n.clic("#rp-timeline")
    n.esperar("document.getElementById('dlg-timeline').open")
    time.sleep(1.2)
    guardar(n, "informe_timeline", n.rect("#dlg-timeline"), margen=4)


def informe_rubrica(n):
    n.ir(arnes("instructor", extra="&abrir=rubrica"), LISTA_APP + " && document.getElementById('dlg-rubrica').open", 2)
    n.js("document.querySelector('#dlg-rubrica').scrollTop = 0")
    guardar(n, "informe_rubrica", n.rect("#dlg-rubrica"), margen=4)


def informe_doctrina(n):
    n.ir(arnes("instructor", extra="&abrir=rubrica"), LISTA_APP + " && document.getElementById('dlg-rubrica').open", 2)
    n.js("(() => { const h = [...document.querySelectorAll('#dlg-rubrica h4')].find((x) => x.textContent.startsWith('Indicadores doctrinales'));"
         " const d = document.getElementById('dlg-rubrica'); d.scrollTop = h.offsetTop - 10; })()")
    time.sleep(0.5)
    guardar(n, "informe_doctrina", n.rect("#dlg-rubrica"), margen=4)


def comparar(n):
    n.ir(arnes("instructor", extra="&abrir=rubrica"), LISTA_APP + " && document.getElementById('dlg-rubrica').open", 2)
    n.clic("#rb-comparar")
    n.esperar("document.getElementById('dlg-comparar').open")
    # el arnes tiene un solo escenario: se suman dos ejercicios anteriores a la lista para mostrar la comparacion
    n.js("(() => { const c = document.getElementById('cmp-lista'); for (const [id, t] of [[2, 'Interdicción en los llanos (contra la IA) (finalizado, turno 7)'],"
         " [3, 'Defensa aérea de la región central (contra la IA) (finalizado, turno 7)']]) { const l = document.createElement('label');"
         " l.className = 'chk'; const i = document.createElement('input'); i.type = 'checkbox'; i.value = id; i.checked = true;"
         " const s = document.createElement('span'); s.textContent = id + ' · ' + t; l.append(i, s); c.appendChild(l); } })()")
    n.clic("#cmp-ver")
    time.sleep(1.2)
    guardar(n, "comparar", n.rect("#dlg-comparar"), margen=4)


def informe_replay(n):
    n.ir(arnes("instructor", extra="&abrir=replay&instante=2.5"), LISTA_APP + " && !document.getElementById('replay-anim').hidden", 4)
    guardar(n, "informe_replay")


CAPTURAS = [
    acceso_login, acceso_registro, acceso_clave, menu_perfil,
    pantalla_general, cabecera, alumno_pantalla, alumno_secciones, oob_ficha, ficha_acciones,
    orden_mover, orden_atacar, seleccion_multiple, orden_construir, cola_y_listo,
    aviacion_enviar, orden_patrullar, perfil_vuelo, mision_planificar, cronograma, misiones_lista, cobertura_radar,
    naval_misiles, naval_desembarcar, orden_interferir,
    panel_derecho, capas, mapa_relieve, mapa_zoom, mapa_regla, mapa_graficos, mapa_ficha, mapa_aerodromo, mapa_meteo,
    consola_turno, consola_meteo, consola_identidad, consola_agregar, consola_objetivos, consola_direccion, consola_eventos,
    consola_escenario, consola_usuarios, plantillas, ver_como, videowall, observador,
    ia_pantalla, consola_ia, plantillas_ia, barra_inferior_ia, mapa_dia_noche, mapa_carreteras, consola_catalogo,
    situacion, mapa_infraestructura, ficha_puente, objetivos_avance,
    informe_repeticion, informe_dialogos, informe_rubrica, informe_doctrina, comparar, informe_replay,
]


def main() -> None:
    pedidas = set(sys.argv[1:])
    n = Navegador()
    fallos = []
    try:
        for f in CAPTURAS:
            if pedidas and f.__name__ not in pedidas:
                continue
            inicio = time.time()
            try:
                f(n)
                print(f"  {f.__name__} ({time.time() - inicio:.0f} s)", flush=True)
            except Exception:  # noqa: BLE001
                fallos.append(f.__name__)
                print(f"  {f.__name__}: ERROR\n{traceback.format_exc()}", flush=True)
    finally:
        n.cerrar()
    print(f"{len(fallos)} fallo(s): {', '.join(fallos)}" if fallos else "Todas las capturas listas.")


if __name__ == "__main__":
    main()
