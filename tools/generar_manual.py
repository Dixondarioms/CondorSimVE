"""Genera el manual de usuario en PDF (docs/Manual_SIETE.pdf) con reportlab.

Las capturas de pantalla y los esquemas se toman de un directorio de imagenes (--imagenes), generadas con Chrome
headless a partir del arnes de pruebas (ver el propio manual, "Como se hizo"). El catalogo de unidades se lee del
codigo (backend/app/engine/catalogo.py) para que las cifras del manual sean las del simulador.

    backend\\venv\\Scripts\\python tools/generar_manual.py --imagenes <carpeta> [--salida docs/Manual_SIETE.pdf]
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus.tableofcontents import TableOfContents

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))
from app.engine import catalogo  # noqa: E402

# ------------------------------------------------------------------ fuentes y estilos
FUENTES = Path(r"C:\Windows\Fonts")
pdfmetrics.registerFont(TTFont("Texto", str(FUENTES / "arial.ttf")))
pdfmetrics.registerFont(TTFont("Texto-B", str(FUENTES / "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Texto-I", str(FUENTES / "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Texto-BI", str(FUENTES / "arialbi.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FUENTES / "consola.ttf")))
pdfmetrics.registerFontFamily("Texto", normal="Texto", bold="Texto-B", italic="Texto-I", boldItalic="Texto-BI")

AZUL = colors.HexColor("#1f4e8c")
GRIS = colors.HexColor("#3d4a57")
CLARO = colors.HexColor("#eef2f7")
LINEA = colors.HexColor("#c9d2dc")

S = {
    "titulo": ParagraphStyle("titulo", fontName="Texto-B", fontSize=30, leading=36, textColor=AZUL, alignment=TA_CENTER),
    "subtitulo": ParagraphStyle("subtitulo", fontName="Texto", fontSize=15, leading=20, textColor=GRIS, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName="Texto-B", fontSize=20, leading=25, textColor=AZUL, spaceBefore=6, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="Texto-B", fontSize=14, leading=18, textColor=AZUL, spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Texto-B", fontSize=11.5, leading=15, textColor=GRIS, spaceBefore=8, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Texto", fontSize=10.2, leading=14.2, alignment=TA_JUSTIFY, spaceAfter=6),
    "pc": ParagraphStyle("pc", fontName="Texto", fontSize=10.2, leading=14.2, spaceAfter=4),
    "li": ParagraphStyle("li", fontName="Texto", fontSize=10.2, leading=14, spaceAfter=2),
    "cap": ParagraphStyle("cap", fontName="Texto-I", fontSize=8.8, leading=11.5, textColor=GRIS, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.8, leading=11.5, backColor=CLARO, borderPadding=(5, 6, 5, 6),
                           leftIndent=4, spaceBefore=4, spaceAfter=8),
    "celda": ParagraphStyle("celda", fontName="Texto", fontSize=8.6, leading=10.8),
    "celdab": ParagraphStyle("celdab", fontName="Texto-B", fontSize=8.6, leading=10.8, textColor=colors.white),
    "nota": ParagraphStyle("nota", fontName="Texto-I", fontSize=9.4, leading=13, textColor=GRIS, backColor=CLARO,
                           borderPadding=(6, 8, 6, 8), leftIndent=4, spaceBefore=4, spaceAfter=10),
    "toc1": ParagraphStyle("toc1", fontName="Texto-B", fontSize=11, leading=16, leftIndent=0),
    "toc2": ParagraphStyle("toc2", fontName="Texto", fontSize=10, leading=14, leftIndent=16),
}
ANCHO_TEXTO = A4[0] - 4 * cm


class Manual(BaseDocTemplate):
    """Documento con encabezado, pie y tabla de contenido automatica."""

    def __init__(self, ruta, **kw):
        super().__init__(ruta, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.2 * cm, bottomMargin=2 * cm,
                         title="S.I.E.T.E. · Manual de usuario", author="S.I.E.T.E. - Sistema Integral de Entrenamiento Táctico y Estratégico", **kw)
        marco = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates([PageTemplate(id="portada", frames=[marco], onPage=lambda c, d: None),
                               PageTemplate(id="normal", frames=[marco], onPage=self._decorar)])

    def _decorar(self, c, doc):
        c.saveState()
        c.setFont("Texto", 8.5)
        c.setFillColor(GRIS)
        c.drawString(self.leftMargin, A4[1] - 1.4 * cm, "S.I.E.T.E. · Manual de usuario")
        c.drawRightString(A4[0] - self.rightMargin, A4[1] - 1.4 * cm, getattr(self, "seccion_actual", ""))
        c.setStrokeColor(LINEA)
        c.line(self.leftMargin, A4[1] - 1.55 * cm, A4[0] - self.rightMargin, A4[1] - 1.55 * cm)
        c.drawCentredString(A4[0] / 2, 1.2 * cm, f"Página {doc.page}")
        c.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            nivel = 0 if flowable.style.name == "h1" else 1
            texto = flowable.getPlainText()
            if nivel == 0:
                self.seccion_actual = texto
            clave = f"s{self.seq.nextf('sec')}"
            self.canv.bookmarkPage(clave)
            self.canv.addOutlineEntry(texto, clave, level=nivel, closed=False)
            self.notify("TOCEntry", (nivel, texto, self.page, clave))


# ------------------------------------------------------------------ ayudas de contenido
def P(t, estilo="p"):
    return Paragraph(t, S[estilo])


def H1(t):
    return [PageBreak(), Paragraph(t, S["h1"])]


def H2(t):
    return Paragraph(t, S["h2"])


def H3(t):
    return Paragraph(t, S["h3"])


def Bul(items):
    return ListFlowable([ListItem(Paragraph(i, S["li"]), leftIndent=12, value="•") for i in items],
                        bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8, spaceAfter=6)


def Num(items):
    """Lista numerada; cada elemento es un texto o una lista de flowables (p. ej. texto + bloque de codigo)."""
    def item(i):
        if isinstance(i, (list, tuple)):
            return ListItem([Paragraph(i[0], S["li"])] + list(i[1:]), leftIndent=14)
        return ListItem(Paragraph(i, S["li"]), leftIndent=14)
    return ListFlowable([item(i) for i in items], bulletType="1", leftIndent=14, spaceAfter=6)


def Code(t):
    return Paragraph(t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>"), S["code"])


def Nota(t):
    return Paragraph(t, S["nota"])


def Img(carpeta, nombre, caption, ancho=ANCHO_TEXTO):
    ruta = carpeta / nombre
    if not ruta.exists():
        return [Paragraph(f"[imagen no disponible: {nombre}]", S["cap"])]
    im = Image(str(ruta))
    k = ancho / im.imageWidth
    im.drawWidth, im.drawHeight = ancho, im.imageHeight * k
    return [KeepTogether([im, Paragraph(caption, S["cap"])])]


def Tbl(cabecera, filas, anchos=None, tam=8.6):
    est = ParagraphStyle("c", parent=S["celda"], fontSize=tam, leading=tam + 2.2)
    estb = ParagraphStyle("cb", parent=S["celdab"], fontSize=tam, leading=tam + 2.2)
    datos = [[Paragraph(str(c), estb) for c in cabecera]] + [[Paragraph(str(c), est) for c in f] for f in filas]
    t = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CLARO]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINEA), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    t.spaceAfter = 8
    return t


def tabla_catalogo():
    tipo_nombre = {"terrestre": "Terrestre", "aerea": "Aérea", "naval": "Naval", "base": "Base"}
    filas = []
    for c in catalogo.CLASES.values():
        notas = []
        if c.emisor:
            notas.append("radar")
        if c.defensa_aerea:
            notas.append("fuego AA automático")
        if c.dron:
            notas.append("dron")
        if c.se_consume:
            notas.append("un solo ataque")
        if c.lanza_misiles:
            notas.append("lanza misiles")
        if c.plazas_aeronaves:
            notas.append(f"{c.plazas_aeronaves} plazas de aeronaves")
        if c.construye:
            notas.append("construye")
        if c.nodo_movil_km:
            notas.append("reabastece")
        if c.escucha_km:
            notas.append(f"escucha {c.escucha_km:.0f} km")
        if c.interferencia_km:
            notas.append(f"interfiere {c.interferencia_km:.0f} km")
        if c.despliegue_turnos:
            notas.append(f"despliegue {c.despliegue_turnos} t")
        if c.recarga_turnos:
            notas.append(f"recarga {c.recarga_turnos} t")
        if c.firma != 1.0:
            notas.append(f"firma ×{c.firma:g}")
        if c.stock_max:
            notas.append(f"existencias {c.stock_max:.0f}")
        atk = c.ataque_vs
        filas.append([c.nombre, tipo_nombre[c.tipo], f"{c.velocidad_kmh:g}", f"{c.alcance_km:g}", f"{c.deteccion_km:g}",
                      f"{c.autonomia_km:g}" if c.autonomia_km else "–",
                      f"{atk['terrestre']:g} / {atk['aerea']:g} / {atk['naval']:g}", f"{c.defensa:g}", ", ".join(notas) or "–"])
    return Tbl(["Clase", "Tipo", "Vel. km/h", "Alcance km", "Detección km", "Autonomía km", "Ataque T / A / N", "Def.", "Particularidades"],
               filas, [3.3 * cm, 1.5 * cm, 1.3 * cm, 1.4 * cm, 1.6 * cm, 1.6 * cm, 2.2 * cm, 0.9 * cm, 3.2 * cm], tam=7.6)


def tabla_modelos():
    filas = []
    for m in catalogo.MODELOS.values():
        atk = m.ataque_vs
        filas.append([m.nombre, catalogo.CLASES[m.clase].nombre, m.pais, f"{m.velocidad_kmh:g}", f"{m.alcance_km:g}", f"{m.deteccion_km:g}",
                      f"{m.autonomia_km:g}", f"{atk['terrestre']:g} / {atk['aerea']:g} / {atk['naval']:g}",
                      "sí" if catalogo.modelo_embarcable(m) else "no"])
    return Tbl(["Modelo", "Clase", "Origen", "Vel.", "Alcance", "Detecc.", "Auton.", "Ataque T / A / N", "Embarcable"], filas,
               [4.2 * cm, 3.0 * cm, 1.8 * cm, 1.1 * cm, 1.4 * cm, 1.4 * cm, 1.4 * cm, 2.1 * cm, 1.6 * cm], tam=7.6)


# ------------------------------------------------------------------ el manual
def construir(salida: Path, img: Path) -> None:
    doc = Manual(str(salida))
    hoy = date.today()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha = f"{meses[hoy.month - 1].capitalize()} de {hoy.year}"
    n_clases, n_modelos = len(catalogo.CLASES), len(catalogo.MODELOS)
    h = []

    # ---- portada
    h += [Spacer(1, 1.2 * cm)]
    logo = RAIZ / "frontend" / "static" / "img" / "siete_logo_recortado.jpg"
    if logo.exists():
        im = Image(str(logo))
        im.drawWidth, im.drawHeight = 15 * cm, 15 * cm * im.imageHeight / im.imageWidth
        h += [im, Spacer(1, 18)]
    h += [Paragraph("S.I.E.T.E.", S["titulo"]), Spacer(1, 6),
          Paragraph("Sistema Integral de Entrenamiento Táctico y Estratégico", S["subtitulo"]),
          Paragraph("Simulador de conducción militar para el adiestramiento táctico y estratégico", S["subtitulo"]), Spacer(1, 26),
          Paragraph("MANUAL DE USUARIO", ParagraphStyle("mu", parent=S["subtitulo"], fontName="Texto-B", fontSize=18, textColor=AZUL)),
          Spacer(1, 8), Paragraph("Qué es · cómo se hizo · instalación · cómo funciona", S["subtitulo"]), Spacer(1, 28)]
    h += [Paragraph(f"Fuerza Armada Nacional Bolivariana · Aviación Militar Bolivariana · DIDA<br/>{fecha} · versión del manual 1.2", S["subtitulo"])]
    h.append(PageBreak())

    # ---- indice
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    toc.dotsMinLevel = 0
    h += [Paragraph("Contenido", ParagraphStyle("h1toc", parent=S["h1"])), toc]

    # ---- 1 que es
    h += H1("1. Qué es S.I.E.T.E.")
    h += [P("S.I.E.T.E. (Sistema Integral de Entrenamiento Táctico y Estratégico) es un <b>juego de guerra (wargame) de conducción</b> para el aula: una herramienta de "
            "adiestramiento en el <b>proceso de conducción</b> de operaciones terrestres, aéreas y navales sobre el terreno "
            "real de Venezuela y su entorno. Un <b>instructor o director de ejercicio</b> arma la situación, controla el reloj y "
            "evalúa; los <b>alumnos</b>, organizados por bando (azul y rojo) y por puesto de estado mayor, aprecian la situación, "
            "redactan órdenes y ven sus consecuencias turno a turno."),
          P("Es una aplicación <b>web multiusuario</b> que se instala en un solo equipo del aula y se usa desde cualquier "
            "navegador de la red local. <b>No necesita internet</b>: el mapa satelital, el relieve, los planos de las bases "
            "aéreas, el catálogo de unidades y las librerías se sirven desde el propio servidor."),
          H2("1.1 Para qué sirve"),
          Bul(["Practicar el ciclo de conducción: apreciación de situación, decisión, emisión de órdenes, ejecución y evaluación.",
               "Ejercitar el trabajo de un estado mayor: puestos A2 (inteligencia), A3 (operaciones), A4 (logística) y A5 (planificación) "
               "trabajando a la vez sobre el mismo bando, con la niebla de guerra y las comunicaciones simuladas.",
               "Ensayar operaciones aéreas (bases, ciclo de vuelo, misiones con roles, drones, guerra electrónica, defensa antiaérea), "
               "navales (buques, portaaviones, submarinos, misiles de crucero) y terrestres (terreno, ríos, ingenieros, logística).",
               "Revisar el ejercicio después (informe AAR): repetición turno a turno, combates, logística y puntaje."]),
          H2("1.2 Qué no es"),
          P("No es una simulación física ni un modelo de armas real: el combate, la detección y la logística son "
            "<b>abstracciones didácticas</b> con parámetros ajustables, pensadas para que el énfasis esté en las decisiones y no en las "
            "cifras. Los valores del catálogo son relativos entre unidades y no datos técnicos oficiales. El simulador tampoco "
            "modela el orden de batalla real de ningún país."),
          H2("1.3 En una página"),
          Tbl(["Aspecto", "Cómo lo resuelve el simulador"], [
              ["Tiempo", "Por turnos: 1 turno = 1 hora simulada. Fase de decisión (órdenes) y fase de resolución automática."],
              ["Participantes", "Instructor (director), bando azul, bando rojo (varios alumnos por bando, por puesto) y observadores."],
              ["Unidades", f"{n_clases} clases (terrestres, aéreas, navales y bases) y {n_modelos} modelos de aeronave y misil, con miniaturas 3D en el mapa."],
              ["Terreno", "Venezuela y países vecinos: satélite Sentinel-2, relieve, clases de terreno (bosque, pantano, urbano, montaña, agua), ríos."],
              ["Bases aéreas", "Las 9 bases de la AMB con su plano real (pistas, rodajes, hangares) y daños visibles."],
              ["Niebla de guerra", "Cada bando ve solo lo que detecta; de lo enemigo conoce posición, clase y bando."],
              ["Evaluación", "Objetivos y puntaje, eventos, informe posterior al ejercicio, línea de tiempo logística, exportación."],
              ["Instalación", "Python 3.11 o superior en un equipo; los clientes solo necesitan un navegador. Sin internet."],
          ], [3.2 * cm, ANCHO_TEXTO - 3.2 * cm])]

    # ---- 2 como se hizo
    h += H1("2. Cómo se hizo")
    h += [P("El simulador fue desarrollado como un proyecto propio, en código abierto y con datos abiertos, tomando como "
            "referencia funcional y doctrinal los simuladores de conducción de uso en escuelas militares (el concepto de "
            "director de ejercicio, puestos por función, turnos, niebla de guerra e informe posterior). No utiliza código, "
            "datos ni mapas de ningún producto de terceros."),
          H2("2.1 Arquitectura")]
    h += Img(img, "diag_arquitectura.png", "Esquema 1. Arquitectura: estaciones del aula, servidor y datos.")
    h += [Tbl(["Componente", "Tecnología", "Función"], [
        ["Servidor", "Python 3, FastAPI, Uvicorn", "API REST y WebSocket; sirve la interfaz y todos los datos."],
        ["Motor de simulación", "Python (paquete engine/)", "Catálogo, movimiento, visión, combate, aeronaves, misiones, misiles, guerra electrónica, logística, objetivos, informe."],
        ["Base de datos", "SQLite (por defecto) o PostgreSQL; SQLAlchemy + Alembic", "Escenarios, unidades, órdenes, usuarios, instantáneas de cada turno; migraciones automáticas."],
        ["Interfaz", "HTML, CSS y JavaScript sin frameworks; Leaflet; milsymbol", "Mapa táctico, paneles, órdenes, misiones, informe, videowall. Miniaturas 3D propias."],
        ["Seguridad", "Sesiones HttpOnly, PBKDF2-SHA256, CSP", "Roles y puestos verificados en el servidor; sin recursos externos; HTTPS opcional."],
        ["Pruebas", "pytest (motor, API, migraciones) y Node (lógica del cliente)", "Más de 440 pruebas automatizadas; arnés visual con datos simulados."],
    ], [3.0 * cm, 5.0 * cm, ANCHO_TEXTO - 8.0 * cm])]
    h += [H2("2.2 Datos y licencias"),
          P("Todo el material geográfico proviene de fuentes abiertas y se preparó una sola vez con internet mediante scripts "
            "del proyecto (carpeta <font face='Mono'>tools/</font>); después queda en el servidor para uso sin conexión."),
          Tbl(["Dato", "Fuente", "Licencia"], [
              ["Imagen satelital", "Sentinel-2 cloudless (EOX, Copernicus/ESA), hasta zoom 12", "CC BY 4.0"],
              ["Relieve y clases de terreno", "AWS Terrain Tiles (SRTM/GMTED), ESA WorldCover 2021", "Abierto / CC BY 4.0"],
              ["Fronteras, ríos, ciudades", "Natural Earth", "Dominio público"],
              ["Planos de aeródromos", "OpenStreetMap (pistas, rodajes, plataformas, hangares)", "ODbL 1.0"],
              ["Bases aéreas de la AMB", "Wikipedia y OurAirports (coordenadas, OACI, elevación)", "CC BY-SA / dominio público"],
              ["Fotos F-16 y Su-30", "Wikimedia Commons", "CC BY-SA 3.0 / 4.0"],
              ["Imágenes 3D F-16 y Su-30", "Modelos de Sketchfab renderizados a 24 rumbos", "Sketchfab Standard"],
              ["Miniaturas 3D del resto de unidades e ilustraciones", "Propias del proyecto (procedurales)", "CC0"],
              ["Librerías", "Leaflet, Leaflet.draw, milsymbol", "BSD / MIT"],
          ], [4.2 * cm, 8.3 * cm, ANCHO_TEXTO - 12.5 * cm]),
          H2("2.3 Método de desarrollo"),
          Bul(["Desarrollo incremental por funciones (turnos, niebla, aviación, guerra electrónica, misiones, logística, buques...), cada una con sus pruebas automatizadas y su documentación.",
               "Las reglas del motor son deterministas (con azar opcional y reproducible), lo que permite probarlas y explicarlas en clase.",
               "La interfaz se verifica con un arnés que ejecuta la aplicación real contra datos simulados, sin tocar la base de datos del aula.",
               "El código está versionado en Git; cada versión de la base de datos tiene su migración."])]

    # ---- 3 instalacion
    h += H1("3. Instalación y puesta en marcha")
    h += [H2("3.1 Requisitos"),
          Tbl(["Elemento", "Requisito"], [
              ["Servidor", "Un PC con Windows 10/11 (o Linux), 8 GB de RAM, 3 GB libres en disco (la imagen satelital pesa varios cientos de MB). Python 3.11 o superior."],
              ["Estaciones", "Cualquier equipo con un navegador moderno (Chrome, Edge o Firefox). No instalan nada."],
              ["Red", "Red local del aula (cableada o Wi-Fi). Sin internet. Puerto 8000 (HTTP) u 8443 (HTTPS) abierto en el cortafuegos del servidor."],
              ["Pantalla", "1366×768 como mínimo; el videowall se adapta a cualquier tamaño. Pantallas estrechas usan paneles plegables."],
          ], [3.0 * cm, ANCHO_TEXTO - 3.0 * cm]),
          H2("3.2 Instalación con un clic (Windows)"),
          P("Con Python 3.11 o superior instalado (python.org, marcando «Add python.exe to PATH»), haga doble clic en "
            "<font face='Mono'>instalar.cmd</font> en la carpeta del proyecto: crea el entorno, instala las dependencias, pide el "
            "usuario y la contraseña del primer instructor, y deja en el Escritorio el acceso directo <b>S.I.E.T.E.</b> que arranca el "
            "servidor y abre el navegador. Opciones: <font face='Mono'>instalar.cmd -Demo</font> (crea el escenario de demostración), "
            "<font face='Mono'>-Servicio</font> como administrador (arranque automático al encender el equipo) y <font face='Mono'>-Desinstalar</font>. "
            "<font face='Mono'>iniciar.cmd</font> y <font face='Mono'>detener.cmd</font> arrancan y detienen el servidor a mano."),
          H2("3.3 Instalación paso a paso (manual)"),
          Num([
              "Copie la carpeta del proyecto (<font face='Mono'>simulador_fenix</font>) al servidor, por ejemplo en <font face='Mono'>C:\\simulador_fenix</font>. "
              "Debe incluir <font face='Mono'>frontend/static/tiles_sat</font> (satélite), <font face='Mono'>tiles</font> (relieve) y <font face='Mono'>geo</font> (vectores y aeródromos).",
              ["Abra una consola (PowerShell o cmd) en la carpeta <font face='Mono'>backend</font> y cree el entorno con sus dependencias:",
               Code("cd C:\\simulador_fenix\\backend\npython -m venv venv\nvenv\\Scripts\\python -m pip install -r requirements.txt")],
              ["Cree el primer usuario instructor (pide la contraseña, mínimo 8 caracteres):",
               Code("venv\\Scripts\\python -m app.crear_usuario instructor --rol instructor")],
              ["(Opcional) Cree el escenario de demostración para probar:", Code("venv\\Scripts\\python -m app.crear_demo")],
              ["Arranque el servidor. La base de datos se crea y se migra sola, y se respalda en cada arranque y cada 6 horas:",
               Code("venv\\Scripts\\python -m app.servidor --host 0.0.0.0 --port 8000")],
              "Desde cualquier estación abra <font face='Mono'>http://&lt;ip-del-servidor&gt;:8000/</font> e inicie sesión. "
              "Para conocer la IP del servidor: <font face='Mono'>ipconfig</font>.",
          ]),
          *Img(img, "cap_login.jpg", "Figura 1. Inicio de sesión. Tras 5 intentos fallidos la cuenta se bloquea 5 minutos.", ancho=9.5 * cm),
          Nota("Deje la consola del servidor abierta mientras dure el ejercicio. Para detenerlo, Ctrl+C. Para que arranque solo al encender el "
               "equipo, cree una tarea programada de Windows que ejecute el comando de arranque."),
          H2("3.4 Usuarios, roles y puestos"),
          P("Los usuarios se crean desde el panel <b>Usuarios</b> del instructor o por consola. Cada alumno tiene un rol (azul, rojo u "
            "observador) y, dentro del bando, un puesto (EM por defecto, o A2, A3, A4, A5):"),
          Code("venv\\Scripts\\python -m app.crear_usuario a5azul --rol azul --puesto planificacion\n"
               "venv\\Scripts\\python -m app.crear_usuario obs1 --rol observador"),
          H2("3.5 HTTPS (opcional)"),
          P("Con <font face='Mono'>--https</font> en lugar de <font face='Mono'>--port 8000</font> el servidor genera un certificado "
            "autofirmado y escucha en 8443; los navegadores avisarán hasta que se instale <font face='Mono'>backend/certs/cert.pem</font> "
            "como certificado de confianza en cada estación. En una red de aula aislada, HTTP es suficiente."),
          H2("3.6 PostgreSQL (opcional, varias aulas)"),
          P("Por defecto se usa SQLite (un archivo). Para varias aulas o más concurrencia, defina la variable "
            "<font face='Mono'>SIMULADOR_DATABASE_URL</font> con la conexión a PostgreSQL; el mismo código migra y respalda "
            "(<font face='Mono'>python -m app.migrar_a_postgres</font> copia los datos existentes)."),
          H2("3.7 Respaldos y actualización"),
          Bul(["Los respaldos automáticos quedan en <font face='Mono'>backend/respaldos/</font> (se conservan los 14 últimos). "
               "<font face='Mono'>python -m app.respaldo</font> hace uno manual. Restaurar = detener el servidor y copiar el archivo sobre "
               "<font face='Mono'>backend/simulador_fenix.db</font>.",
               "Para actualizar a una versión nueva: detenga el servidor, haga un respaldo, reemplace la carpeta del proyecto "
               "(conservando <font face='Mono'>backend/simulador_fenix.db</font>, <font face='Mono'>backend/respaldos</font> y los datos de mapa) y arranque: las migraciones se aplican solas.",
               "Para comprobar la instalación: <font face='Mono'>venv\\Scripts\\python -m pytest</font> en <font face='Mono'>backend</font> ejecuta las pruebas del motor y la API."]),
          H2("3.8 Datos de mapa: regiones (Venezuela, América, mundo)"),
          P("El mapa está formado por <b>regiones superpuestas</b>, cada una con su resolución: <b>Venezuela y vecinos</b> (~300 m por píxel, "
            "el área de detalle con foto satelital y planos de aeródromos) y <b>América</b> entera (~1,2 km por píxel), ambas incluidas. "
            "La más detallada se dibuja encima y el motor consulta el terreno en la más fina que cubra cada punto, así que se pueden "
            "ambientar ejercicios en cualquier lugar del continente. Los botones de la tarjeta <b>Capas</b> encajan la vista en cada región."),
          P("Si se quiere el <b>mundo entero</b> (~2,4 km por píxel) o un teatro concreto con más detalle, se genera una vez con internet: "
            "<font face='Mono'>python tools/preparar_terreno.py --region mundo</font> (unos 250 MB de descarga, ~270 MB de RAM en el servidor) o "
            "<font face='Mono'>python tools/preparar_terreno.py --id caribe --nombre \"Caribe\" --bbox -90 8 -58 27 --zoom 8</font> "
            "(recuadro en grados: lon. mín., lat. mín., lon. máx., lat. máx.; zoom 9 = ~300 m, 8 = ~600 m, 7 = ~1,2 km). Al reiniciar el servidor "
            "la región nueva aparece sola. Los demás scripts de <font face='Mono'>tools/</font> también necesitan internet una sola vez: "
            "<font face='Mono'>preparar_satelite.py --region &lt;id&gt;</font> (foto satelital de una región: Venezuela hasta el zoom 12 y América hasta el 8 ya incluidas), "
            "<font face='Mono'>preparar_aerodromos.py</font> (planos de las bases) y <font face='Mono'>generar_bases_aereas.py</font>.")]

    # ---- 4 roles
    h += H1("4. Roles, puestos y acceso")
    h += Img(img, "diag_puestos.png", "Esquema 2. Roles del ejercicio y puestos de cada bando.")
    h += [Tbl(["Rol", "Ve", "Puede"], [
        ["Instructor", "Todo, sin niebla; puede «ver como» un bando", "Crear y editar escenarios, ubicar unidades, clima, eventos, ajustes, usuarios, resolver turnos, informe"],
        ["Azul / Rojo", "Sus unidades, los enemigos detectados y los últimos contactos", "Emitir y cancelar órdenes y misiones de su puesto, gráficos, chat, marcar «listo»; informe al finalizar"],
        ["Observador", "Todo", "Solo lectura, incluido el informe"],
    ], [2.4 * cm, 5.6 * cm, ANCHO_TEXTO - 8.0 * cm]),
          Tbl(["Puesto", "Conduce", "Confirma «listo»"], [
              ["EM · Estado Mayor", "Todo (un solo alumno por bando)", "Sí"],
              ["A2 · Inteligencia", "Radares (control de emisiones) y guerra electrónica terrestre; sigue contactos y dibuja gráficos de blancos", "No"],
              ["A3 · Operaciones", "Aeronaves ya creadas: rutas, patrullas, ataques, aterrizajes, misiones de grupos existentes", "No"],
              ["A4 · Logística", "Ingenieros (puentes y vados) y convoyes de abastecimiento", "No"],
              ["A5 · Planificación", "Unidades terrestres y navales, antiaérea, lanzamiento de misiles, envío de grupos desde bases y portaaviones, misiones programadas", "Sí"],
          ], [3.4 * cm, ANCHO_TEXTO - 6.4 * cm, 3.0 * cm]),
          P("El servidor rechaza toda orden fuera del puesto explicando a quién corresponde, y la interfaz solo muestra las "
            "herramientas de cada puesto. Los alumnos y observadores solo ven los escenarios que el instructor les asigna.")]

    # ---- 5 pantalla
    h += H1("5. La pantalla")
    h += Img(img, "cap_azul.jpg", "Figura 2. Pantalla de un alumno del bando azul (puesto EM) con datos de ejemplo.")
    h += [Tbl(["Zona", "Contenido"], [
        ["Cabecera", "Escenario activo, indicador de conexión, reloj de la fase (cuenta regresiva si el instructor fijó un límite), botones Videowall, Informe y sesión."],
        ["Panel izquierdo · Fuerzas", "Orden de batalla por rama (infantería, blindados, artillería, aviación, naval, bases), con el estado de cada unidad y buscador. Al elegir una unidad, su ficha (clase, modelo, fuerza, combustible, munición, situación) y las acciones (radar, fuego, misiles, despegue)."],
        ["Panel izquierdo · Consola (instructor)", "Agregar unidades, elegir aeronave, clima, eventos, objetivos, identidad nacional, comunicaciones simuladas, editar el escenario, ajustes manuales, usuarios."],
        ["Mapa táctico", "Fondo satelital o relieve; unidades como miniaturas 3D (o símbolos APP-6, a elección); anillos de alcance y detección; rutas, ataques, zonas de interferencia, misiones, gráficos tácticos, planos de bases. Regla y coordenadas al pie."],
        ["Panel derecho", "Estado del escenario (clima, fase, modo), objetivos y puntaje, capas, chat del bando, alertas."],
        ["Panel de órdenes (alumnos)", "Nueva orden para la unidad seleccionada (modo, waypoints, objetivo, previsualización), cola de órdenes del turno, misiones aéreas y cronograma."],
        ["Barra inferior", "«Estoy listo» (alumnos) o «Resolver y avanzar turno» (instructor); estado de ambos bandos."],
    ], [4.2 * cm, ANCHO_TEXTO - 4.2 * cm]),
          H2("5.1 Capas y herramientas del mapa"),
          Bul(["<b>Satélite / Relieve</b>: foto real (Sentinel-2; ~10 m sobre Venezuela, ~600 m sobre el resto de América) o relieve coloreado por clase de terreno (distingue mejor bosque, pantano, montaña).",
               "<b>Regiones del mapa</b>: botones «Venezuela y vecinos», «América» (y «Mundo» si se generó) para encajar la vista en cada una.",
               "<b>Terreno, Cobertura (detección), Niebla de guerra, Unidades, Últimos contactos, Gráficos tácticos, Límites y poblaciones, Bases aéreas de Venezuela, Plano de los aeródromos, Objetivos, Guerra electrónica, Misiones aéreas</b>.",
               "<b>Símbolos militares (APP-6) en lugar de miniaturas</b>: preferencia de cada puesto (se recuerda en el navegador).",
               "<b>Regla</b>: distancia y rumbo por tramos. <b>Búsqueda</b> de unidades por nombre, clase o modelo. Zoom hasta el nivel 17 sobre las bases aéreas.",
               "Al pasar el cursor sobre una unidad se ve su ficha resumida; al hacer clic se selecciona (y en modo atacar o lanzar, se toma como objetivo)."])]
    h += Img(img, "cap_miniaturas.jpg", "Figura 3. Miniaturas 3D de todas las clases (azul y rojo). Las aeronaves llevan las derivas del color del bando; lo que está en tierra o en el agua, una peana.")

    # ---- 6 preparar ejercicio
    h += H1("6. Preparar un ejercicio (instructor)")
    h += [Num(["<b>Crear el escenario</b>: botón <b>Nuevo</b> (vacío) o <b>Desde plantilla…</b> (escenarios precargados: demostración en los Llanos y "
               "«defensa del litoral central», con unidades, objetivos y clima ya definidos).",
               "<b>Ubicar unidades</b>: <i>Consola → Agregar unidad</i>: nombre, bando, clase, escalón y clic en el mapa. Para aeronaves, "
               "<b>Elegir aeronave…</b> abre el selector de modelos con foto y datos. Las <b>bases aéreas de Venezuela</b> se colocan con un clic desde su "
               "capa de referencia (popup «Base azul / Base roja»). Las unidades navales solo pueden ir sobre el agua.",
               "<b>Clima</b> (despejado, nublado, lluvia, tormenta): afecta detección, velocidad y ataques aéreos.",
               "<b>Objetivos y puntaje</b>: ocupar una zona N turnos, destruir una unidad o proteger una unidad propia, cada uno con sus puntos y para un bando.",
               "<b>Identidad nacional</b>: cada bando puede representar a Venezuela, Colombia, Brasil, Guyana o Trinidad y Tobago (solo nombre para la interfaz).",
               "<b>Comunicaciones simuladas</b>: latencia, jitter y pérdida del chat de cada bando.",
               "<b>Usuarios</b>: crear alumnos y observadores, asignar puesto y asignarlos al escenario.",
               "<b>Modo de resolución</b>: manual (el instructor resuelve), automática al estar ambos bandos listos, o con límite de tiempo por fase; "
               "azar reproducible opcional.",
               "<b>Ajustes durante el ejercicio</b>: arrastrar unidades (<i>Editar el escenario</i>), ajuste manual de fuerza, combustible, munición y existencias, "
               "eventos inyectados a un bando o a todos, pausa, «ver como» un bando para mostrarlo en clase."]),
          Nota("Duplicar un escenario copia el despliegue inicial, los objetivos y los modelos de aeronave; archivar lo saca de la lista sin borrarlo; "
               "exportar produce un JSON con la definición y el informe.")]

    # ---- 7 jugar un turno
    h += H1("7. Jugar un turno (alumnos)")
    h += Img(img, "diag_ciclo.png", "Esquema 3. Ciclo de un turno: decisión, resolución por fases y difusión del estado.")
    h += [H2("7.1 Emitir órdenes"),
          P("Seleccione una unidad propia (en el orden de batalla o en el mapa), elija el modo y complete la orden. Una unidad "
            "recibe <b>una orden por turno</b>: la nueva reemplaza a la pendiente. Emitir o cancelar una orden anula el «listo» del bando."),
          Tbl(["Orden", "Quién", "Cómo", "Qué hace"], [
              ["Mover", "Toda unidad móvil", "Clics en el mapa (waypoints); se previsualiza dónde termina el turno", "Avanza según velocidad, terreno, ríos, clima, peso y combustible."],
              ["Atacar", "Unidades con armas", "Objetivo enemigo detectado (lista o clic en el mapa)", "Combate en la fase 3 si el blanco está al alcance; gasta munición."],
              ["Apoyar", "Unidades con armas", "Otra unidad propia a su alcance", "+30 % (hasta +60 %) al ataque y la defensa de la apoyada; 10 % de munición."],
              ["Construir", "Ingenieros (A4)", "Vado o puente, clic sobre un río", "Cruce para vehículos pesados; dura 4 o 12 turnos."],
              ["Despegar", "Bases aéreas y portaaviones (A5)", "«Enviar aeronaves o drones…»: modelo, cantidad, indicativo", "El grupo nace junto a la base al resolverse; recibe órdenes el turno siguiente."],
              ["Patrullar", "Aeronaves (A3)", "Clic en el punto de patrulla", "Se mantiene en la zona e intercepta aviones enemigos al alcance."],
              ["Aterrizar", "Aeronaves en vuelo (A3)", "Base o portaaviones propio con plazas", "Estaciona, reabastece y rearma en 2 turnos."],
              ["Interferir", "Guerra electrónica (A2 / A3)", "Clic en el centro de la zona", "Degrada sensores, antiaérea y enlaces de drones enemigos; delata al emisor."],
              ["Lanzar misiles", "Fragata, destructor, submarino, batería (A5)", "Blanco detectado en tierra o mar y 1–4 misiles", "Salva de misiles de crucero guiada; puede ser interceptada."],
              ["Misión aérea", "Grupos (A3) o despegues programados (A5)", "«Planificar misión…»: rol y ruta con puntos", "El grupo ejecuta solo la misión turno tras turno."],
          ], [2.2 * cm, 3.2 * cm, 4.6 * cm, ANCHO_TEXTO - 10.0 * cm]),
          H2("7.2 Acciones inmediatas desde la ficha de la unidad"),
          Bul(["<b>Radar</b> (radares, antiaérea guiada por radar, destructores): encender o apagar. Apagado ve solo 5 km, pero la escucha enemiga no lo localiza.",
               "<b>Fuego automático</b> (antiaérea, destructores): libre o retenido.",
               "Estas acciones rigen de inmediato, no esperan al turno."]),
          H2("7.3 Confirmar y resolver"),
          P("Cuando el bando termina, pulsa <b>Estoy listo</b> (lo confirman el EM o A5). El turno se resuelve cuando el instructor pulsa "
            "<b>Resolver y avanzar turno</b>, o solo al estar ambos listos, o al agotarse el tiempo de la fase. Cada orden resuelta muestra "
            "su resultado en la cola (por ejemplo «Ataque a Infantería Roja: pérdidas 12 % / 27 %») y los sucesos importantes llegan como alertas."),
          H2("7.4 Lo que ve cada bando"),
          P("De las unidades enemigas solo se conocen posición, clase y bando mientras estén dentro del radio de detección de alguna unidad "
            "propia (reducido por clima, terreno, firma radar e interferencia). Al perderlas de vista queda su <b>último contacto</b>. Un caza enemigo "
            "se ve como caza genérico: su modelo y tamaño son desconocidos. Las órdenes, los gráficos, el chat y los eventos también se filtran por bando.")]

    # ---- 8 reglas
    h += H1("8. Reglas del motor")
    h += [H2("8.1 Terreno y clima"),
          Tbl(["Terreno", "Velocidad terrestre", "Defensa", "Radio de detección enemigo"], [
              ["Llano", "×1,0", "×1,0", "×1,0"], ["Bosque / selva", "×0,6", "×1,3", "×0,6"], ["Pantano / humedal", "×0,5", "×1,0", "×0,9"],
              ["Urbano", "×0,7", "×1,5", "×0,7"], ["Montaña", "×0,4", "×1,6", "×0,75"], ["Agua", "intransitable (solo naval)", "–", "–"],
          ], [4.0 * cm, 4.5 * cm, 3.0 * cm, ANCHO_TEXTO - 11.5 * cm]),
          Bul(["Las unidades <b>ligeras</b> (infantería) vadean los ríos a media velocidad; las <b>pesadas</b> (vehículos) solo cruzan por un puente o vado tendido por ingenieros. Los tramos anchos del Orinoco son obstáculo.",
               "<b>Clima</b>: lluvia ×0,7 y tormenta ×0,5 en la detección; también reducen la velocidad y la efectividad de los ataques aéreos.",
               "<b>Cobertura aérea</b> (aeronave propia a ≤ 40 km): un blanco terrestre atacado desde el aire sin cobertura defiende ×0,7; un atacante terrestre con cobertura frente a uno sin ella ataca ×1,15."]),
          H2("8.2 Combate"),
          P("Todos los combates de un turno se calculan <b>a la vez</b> con las fuerzas del inicio de la fase: el resultado no depende del orden en "
            "que se dieron las órdenes. La relación de fuerzas (con los factores de clase, terreno, apoyo, cobertura, clima, munición, sorpresa, "
            "cadencia y tamaño del grupo aéreo) determina las pérdidas de ambos por una curva continua. El <b>azar</b> es opcional y reproducible "
            "(semilla del escenario + turno + unidades) y queda registrado en cada combate. Un atacante no detectado por el defensor logra "
            "<b>sorpresa</b> (×1,2; ×1,5 contra convoyes). La munición merodeadora y los misiles pueden ser derribados <b>antes</b> de impactar."),
          H2("8.3 Logística"),
          Bul(["Moverse gasta combustible según la distancia real y la autonomía de la clase; atacar gasta munición (25 % terrestre, 34 % aérea, 20 % naval); con munición escasa el ataque pierde fuerza.",
               "Las <b>bases</b> reabastecen +50 % por turno a las unidades propias de su tipo dentro de su radio, desde sus <b>existencias</b> (bases aéreas y puertos hasta 2000 puntos; depósitos hasta 3000 y reponen 150 por turno). Cada despegue consume 25 de combustible y 25 de munición de la base.",
               "Los <b>convoyes</b> reabastecen en marcha (+40 %, radio 3 km), se recargan en los depósitos y descargan en bases aéreas y puertos. Son muy vulnerables a emboscadas.",
               "Una aeronave solo se reabastece <b>en tierra</b>; sin combustible lejos de una base se pierde. Con combustible crítico (≤ 25 %) una patrulla regresa sola.",
               "El bando recibe un aviso cuando una base se queda sin existencias."]),
          H2("8.4 Sensores y guerra electrónica"),
          Bul(["<b>Radar de vigilancia</b>: ve aeronaves en vuelo hasta 150 km, pero lo que está en tierra solo a 8 km. Mientras emite, la escucha enemiga lo localiza hasta 120 km (GE terrestre) o 200 km (avión de GE).",
               "<b>Interferencia</b> (orden Interferir): en la zona, el enemigo detecta al 30 % (radares al 20 %), su antiaérea guiada por radar pierde el 60 % de efecto y sus drones pierden el enlace. Rige durante ese turno y la planificación del siguiente; delata al emisor.",
               "<b>Drones</b>: firma radar pequeña (se detectan a la mitad o menos de distancia); tope propio de 16 por bando. <b>Munición merodeadora</b>: un solo ataque.",
               "<b>Antiaérea automática</b>: con el fuego libre dispara sola cada turno contra la aeronave enemiga más cercana a su alcance que el bando detecte; la guiada por radar necesita el radar encendido (apagado, solo tira por orden y a ojo, ×0,3). La portátil infrarroja no depende del radar, pero debe desplegarse un turno y recarga otro."])]

    # ---- 9 aviacion
    h += H1("9. Aviación")
    h += [H2("9.1 Bases aéreas y ciclo de vuelo"),
          Bul(["<b>Enviar aeronaves</b>: desde una base aérea (o portaaviones) propia, <i>Aviación → Enviar aeronaves o drones…</i>: modelo, número (1 a 8), indicativo. Tope de 24 aeronaves tripuladas y 16 drones por bando. Una base muy dañada (&lt; 25 %) o sin existencias no lanza.",
               "<b>Grupos</b>: la efectividad crece con la raíz del tamaño (4 aeronaves = ×1,0; 8 = ×1,41; 2 = ×0,71); al perder fuerza pierde aeronaves operativas.",
               "<b>Aterrizar</b>: en una base propia con plazas (12 en una base, 10 en un portaaviones). En tierra tarda 2 turnos en reabastecer y rearmar; después, cualquier orden de vuelo es el despegue. Los aviones estacionados cuentan como blancos terrestres y sufren el 60 % del daño de su base.",
               "<b>Patrullar</b>: misión persistente sobre un punto (8 % de combustible por turno) que intercepta al avión enemigo detectado más cercano."]),
          H2("9.2 Misiones aéreas con roles"),
          P("Además de las órdenes turno a turno, un grupo puede recibir una <b>misión</b> (<i>Planificar misión…</i>): un rol y una ruta de puntos "
            "(<b>paso</b>, <b>órbita</b> de N turnos, <b>blanco</b>, <b>aterrizaje</b>) que el motor ejecuta solo. Puede volarla un grupo existente "
            "(A3) o un grupo que despegará de una base en un turno programado, hasta 24 turnos después (A5). Mientras se traza, el servidor estima "
            "la hora de llegada y el combustible en cada punto."),
          Tbl(["Rol", "Comportamiento"], [
              ["CAP", "En la órbita intercepta aviones enemigos."],
              ["Interdicción", "Ataca el blanco; si se movió y se lo sigue viendo, lo persigue."],
              ["CAS", "En la órbita ataca cada turno al enemigo de superficie más cercano."],
              ["SEAD", "Prioriza radares y antiaérea que emiten."],
              ["Reconocimiento", "Vuela la ruta sin atacar (drones de reconocimiento)."],
              ["Guerra electrónica", "Interfiere desde la órbita (avión de GE)."],
              ["Traslado", "Vuela a otra base y aterriza."],
          ], [3.4 * cm, ANCHO_TEXTO - 3.4 * cm]),
          P("Una orden directa al grupo reemplaza la misión; con combustible crítico regresa a la base más cercana; si su base de aterrizaje está "
            "fuera de servicio se desvía. El <b>Cronograma</b> muestra una fila por misión con vuelo, órbitas, ataques y aterrizajes sobre la línea de tiempo."),
          H2("9.3 Modelos de aeronave y misil")]
    h.append(tabla_modelos())
    fila = []
    for nombre, cap in [("ilus_caza_embarcado.png", "Caza embarcado"), ("ilus_helo_ataque.png", "Helicóptero de ataque"),
                        ("ilus_helo_transporte.png", "Helicóptero de transporte artillado"), ("ilus_ataque_ligero.png", "Avión de ataque ligero"),
                        ("ilus_crucero.png", "Misil de crucero"), ("ilus_dron_armado.png", "Dron armado")]:
        ruta = img / nombre
        if ruta.exists():
            im = Image(str(ruta))
            im.drawWidth, im.drawHeight = 5.4 * cm, 5.4 * cm * im.imageHeight / im.imageWidth
            fila.append([im, Paragraph(cap, S["cap"])])
    if fila:
        t = Table([[f[0] for f in fila[:3]], [f[1] for f in fila[:3]], [f[0] for f in fila[3:6]], [f[1] for f in fila[3:6]]],
                  colWidths=[5.6 * cm] * 3, hAlign="CENTER")
        t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        h += [t, Paragraph("Figura 4. Ilustraciones de los modelos genéricos (generadas de sus miniaturas 3D). El F-16 y el Su-30 usan fotografías reales.", S["cap"])]
    h += [H2("9.4 Portaaviones"),
          P("Un portaaviones es una <b>base aérea móvil</b>: lanza y recibe aeronaves como una base, con 10 plazas y existencias propias (1500) que "
            "repone junto a un puerto propio (100 puntos por turno). Solo operan desde él las aeronaves <b>embarcables</b>: helicópteros, drones, "
            "munición merodeadora y el modelo Caza embarcado; el F-16, el Su-30, el avión de ataque ligero y el de guerra electrónica solo desde bases "
            "terrestres. Las aeronaves a bordo navegan con él, sufren parte del daño que recibe y se hunden si lo hunden. Sus armas propias son "
            "débiles: necesita escolta.")]
    h += Img(img, "cap_naval.jpg", "Figura 5. Grupo naval del bando azul: portaaviones con un helicóptero a bordo, destructor, submarino y una salva de misiles en vuelo.")

    # ---- 10 bases en detalle
    h += H1("10. Las bases aéreas en detalle")
    h += [P("Al acercar el mapa (zoom 11 en adelante) cada base aérea de la AMB se dibuja con su <b>plano real</b> tomado de OpenStreetMap: el "
            "perímetro, las pistas con su largo, ancho y orientación reales (bordes, umbrales, eje, zona de toma de contacto y la numeración de "
            "cada cabecera), las calles de rodaje con su eje amarillo, las plataformas, los helipuertos y los hangares y edificios con su sombra. "
            "Bases incluidas: El Libertador (SVBL), Mariscal Sucre (SVBS), La Carlota (SVFM), Rafael Urdaneta (SVMC), Luis del Valle García (SVBC), "
            "Landaeta Gil (SVBM), Teófilo Luis Méndez (SVPR), José Antonio Páez (SVPA) y Barinas (SVBI).")]
    h += Img(img, "cap_base_plano.jpg", "Figura 6. Base Aérea Barinas al zoom 15: pistas 03/21 y 13/31, rodajes, plataforma con los F-16 estacionados y cráteres por el daño recibido.")
    h += [Bul(["Una unidad <b>base aérea</b> del ejercicio a menos de 4 km del aeródromo lo «ocupa»: al acercarse, su miniatura se reduce a una ficha «BA» y sus aeronaves estacionadas se dibujan sobre la plataforma real.",
               "<b>Daños</b>: con la base dañada aparecen cráteres en la pista (uno cada 7 % de fuerza perdida); por debajo del 25 %, cuando ya no puede lanzar ni recibir aviones, se pintan las cruces amarillas de pista cerrada y el rótulo «PISTA INOPERATIVA». El enemigo no ve el daño de una base ajena.",
               "El detalle depende de lo mapeado en OpenStreetMap: en algunas bases militares hay pocas construcciones cargadas y el simulador no las inventa."])]
    h += Img(img, "cap_base_cerca.jpg", "Figura 7. Zoom 17 sobre la pista: marcas, cráteres y la ficha de la base.")
    h += Img(img, "cap_carlota.jpg", "Figura 8. Base Aérea La Carlota (Caracas) con sus edificios, rodajes y helipuertos.")

    # ---- 11 catalogo
    h += H1("11. Catálogo de unidades")
    h += [P(f"Las {n_clases} clases del catálogo y sus valores de juego (ataque T / A / N = efectividad contra objetivos terrestres, aéreos y "
            "navales; 0 = no puede atacarlos). Son parámetros didácticos ajustables en <font face='Mono'>backend/app/engine/catalogo.py</font>.")]
    h.append(tabla_catalogo())

    # ---- 12 seguimiento
    h += H1("12. Seguimiento, videowall e informe")
    h += Img(img, "cap_videowall.jpg", "Figura 9. Modo videowall para la pantalla del centro de operaciones (tecla V o botón Videowall).")
    h += Img(img, "cap_america.jpg", "Figura 10. Región «América» con foto satelital (~600 m por píxel) y Venezuela en detalle encima; cualquier punto del continente sirve para ambientar un ejercicio.")
    h += [Bul(["<b>Eventos y alertas</b>: despegues, combates, bases sin existencias, misiles derribados, objetivos cumplidos… llegan al bando correspondiente; el instructor puede inyectar eventos propios.",
               "<b>Videowall</b>: el mapa ocupa toda la pantalla con un HUD (turno, hora, reloj, estado de los bandos, marcador, últimas alertas). URL directa: <font face='Mono'>?modo=videowall&amp;escenario=ID&amp;vista=azul|rojo|completa</font>. También <font face='Mono'>?lat=&amp;lon=&amp;zoom=</font> abre el mapa sobre un lugar.",
               "<b>Gráficos tácticos</b>: líneas de fase, ejes de avance, zonas de reunión y puntos de control, compartidos con el bando (o con todos, si los traza el instructor).",
               "<b>Chat</b> del bando o «al mando», con latencia, jitter y pérdida simulados por el instructor.",
               "<b>Informe posterior al ejercicio (AAR)</b>: botón <b>Informe</b>: repetición turno a turno sobre el mapa (trayectorias, combates, novedades), resumen por bando, marcador y objetivos, informe imprimible, CSV de combates y exportación JSON. Los alumnos lo ven al finalizar el escenario.",
               "<b>Línea de tiempo</b>: combustible y munición de cada unidad turno a turno, con caídas abruptas, niveles críticos y reabastecimientos cruzados con los combates."])]

    # ---- 13 limitaciones
    h += H1("13. Limitaciones conocidas")
    h += [Bul(["El modelo de combate es una abstracción didáctica; los valores del catálogo son ajustables.",
               "El terreno no distingue cultivos ni carreteras; los ríos se detectan en una grilla de ~300 m y los puentes reales no están cargados (solo los que construyen los ingenieros).",
               "No hay unidades anfibias ni aerotransportadas; el transporte logístico es terrestre.",
               "La identidad nacional es solo un nombre: no se modela el orden de batalla real de los países vecinos.",
               "Las comunicaciones simuladas afectan al chat, no a las órdenes ni a la niebla de guerra.",
               "Cada orden se da a una unidad (no hay selección múltiple).",
               "Un solo servidor por aula: el WebSocket y el temporizador viven en el proceso."]),
          H2("Hoja de ruta prevista"),
          Bul(["Selección de rutas por carreteras y puentes reales.", "Más plantillas de escenario por curso.",
               "Registro del autor de cada orden para una rúbrica por alumno."])]

    # ---- 14 novedades
    h += H1("14. Novedades de las versiones 1.1 y 1.2")
    h += [P("Resumen de lo incorporado después de la primera edición del manual; cada punto está explicado en su capítulo."),
          Tbl(["Novedad", "Dónde", "Qué aporta"], [
              ["Meteorología por zonas", "Consola → Meteorología por zonas; capa Meteorología",
               "Frentes de nublado, lluvia o tormenta con radio, deriva y duración. El clima efectivo en cada punto rige detección, movimiento y ataques aéreos."],
              ["Mapa de toda América (y del mundo, opcional)", "Tarjeta Capas → botones de región; tools/preparar_terreno.py",
               "Regiones superpuestas: Venezuela en detalle (~300 m) sobre América entera (~1,2 km), ambas con foto satelital; el mundo o un recuadro a medida se generan con un comando."],
              ["Aeródromos de los países vecinos", "Capa Bases aéreas y aeródromos",
               "Bases y aeropuertos de Colombia, Brasil, Guyana y Trinidad dentro del mapa, con su plano real, colocables como base del ejercicio."],
              ["Daño por partes de la base", "Panel de órdenes → «Qué se ataca de la base»; ficha de la base",
               "Pista, plataforma y depósito con daño propio; pista inoperativa al 60 %; refugios reforzados; reparación con ingenieros."],
              ["Escolta y paquetes de ataque", "Planificar misión → rol ESCOLTA o «Escolta del paquete»",
               "Un grupo acompaña a la misión escoltada, intercepta lo que la amenace y regresa al terminar."],
              ["Unidades anfibias y helitransportadas", "Órdenes Embarcar / Desembarcar",
               "Tropas a bordo de un buque de desembarco (3) o helicóptero de transporte (1 ligera), ocultas, con desembarco en un punto."],
              ["Selección múltiple y formaciones", "Ctrl+clic en el orden de batalla o el mapa",
               "La misma orden a varias unidades; con «Mantener la formación» cada una conserva su posición relativa."],
              ["Dirección del ejercicio", "Consola → Dirección del ejercicio; Eventos e informes inyectados; Informe → Diapositivas",
               "Interruptores del motor (niebla, logística, clima, fuego automático), informes con posición en el mapa y diapositivas automáticas del AAR."],
              ["Guardar como plantilla", "Cabecera → Guardar como plantilla…",
               "El escenario actual (con o sin su estado) queda como plantilla reutilizable, junto a las del sistema."],
              ["Rúbrica de evaluación", "Informe → Rúbrica; informe imprimible",
               "Indicadores por bando y por puesto responsable (órdenes, rechazos, turnos pasivos, logística, pérdidas, objetivos, misiones) con observaciones automáticas."],
              ["Instalador de un clic", "instalar.cmd, iniciar.cmd, detener.cmd", "Instalación guiada, acceso directo en el Escritorio y arranque automático opcional."],
              ["Valores de juego editables", "backend/data/ajustes_catalogo.json",
               "El instructor ajusta velocidades, alcances, efectividades y topes sin tocar el código (requiere reiniciar el servidor)."],
          ], [3.6 * cm, 5.2 * cm, ANCHO_TEXTO - 8.8 * cm])]

    # ---- anexos
    h += H1("Anexo A. Referencia rápida")
    h += [Tbl(["Acción", "Dónde"], [
        ["Iniciar sesión", "http://&lt;ip-del-servidor&gt;:8000/"],
        ["Crear escenario", "Cabecera: Nuevo / Desde plantilla… (instructor)"],
        ["Agregar unidad", "Consola → Agregar unidad; clic en el mapa"],
        ["Colocar una base aérea real", "Capa «Bases aéreas de Venezuela» → clic en la base → Base azul / Base roja"],
        ["Enviar aeronaves o drones", "Ficha de la base o portaaviones → Enviar aeronaves o drones…"],
        ["Planificar una misión", "Panel Misiones aéreas → Planificar misión…; Cronograma"],
        ["Encender/apagar radar; retener fuego", "Ficha de la unidad"],
        ["Lanzar misiles de crucero", "Panel de órdenes → Lanzar misiles (fragata, destructor, submarino, batería)"],
        ["Interferir", "Panel de órdenes → Interferir (unidades de GE); clic en el mapa"],
        ["Confirmar el turno", "Estoy listo (alumnos) · Resolver y avanzar turno (instructor)"],
        ["Ver como un bando", "Estado del escenario → Vista (instructor)"],
        ["Videowall", "Botón Videowall o tecla V; Esc para salir"],
        ["Regla", "Botón Regla sobre el mapa; doble clic o Esc para terminar"],
        ["Informe", "Botón Informe; Línea de tiempo dentro de la repetición"],
        ["Respaldo manual", "backend: venv\\Scripts\\python -m app.respaldo"],
        ["Crear usuario", "backend: venv\\Scripts\\python -m app.crear_usuario &lt;nombre&gt; --rol azul|rojo|observador|instructor [--puesto ...]"],
        ["Pruebas", "backend: venv\\Scripts\\python -m pytest · raíz: node --test \"frontend/tests/*.test.js\""],
    ], [5.2 * cm, ANCHO_TEXTO - 5.2 * cm])]
    h += [H2("Anexo B. Estructura del proyecto"),
          Code("simulador_fenix/\n  backend/            servidor FastAPI, motor (app/engine), API (app/routers), modelos, migraciones, pruebas\n"
               "    simulador_fenix.db  base de datos SQLite del aula (respaldos en backend/respaldos/)\n"
               "  frontend/           index.html, static/js (app.js, logica.js, modelo3d.js, miniaturas.js, aerodromos.js...), css\n"
               "    static/tiles_sat  imagen satelital offline     static/tiles  relieve     static/geo  vectores y aeródromos\n"
               "    static/pruebas    arnés visual y galería de miniaturas\n"
               "  tools/              scripts de preparación de datos (terreno, satélite, aeródromos, bases, arnés, manual)\n"
               "  docs/               este manual\n  README.md           documentación técnica completa"),
          H2("Anexo C. Créditos y licencias"),
          P("Satélite: EOxCloudless (EOX IT Services GmbH), Copernicus Sentinel-2 (ESA), CC BY 4.0. Relieve: AWS Terrain Tiles (SRTM/GMTED/ETOPO1 "
            "vía Mapzen). Cobertura terrestre: ESA WorldCover 2021, CC BY 4.0. Vectores: Natural Earth (dominio público). Planos de aeródromos: "
            "© colaboradores de OpenStreetMap, ODbL 1.0. Bases aéreas: Wikipedia (CC BY-SA) y OurAirports (dominio público). Fotos: F-16 venezolano "
            "(Veronidae, CC BY-SA 3.0) y Sukhoi Su-30MK2 de Venezuela (Carlos E. Perez S.L, CC BY-SA 4.0), Wikimedia Commons. Imágenes 3D: modelos "
            "F16A (amf1re) y Su-33 (helijah) de Sketchfab, licencia Sketchfab Standard. Miniaturas 3D e ilustraciones de los modelos genéricos: "
            "propias del proyecto, CC0. Librerías: Leaflet (BSD-2), Leaflet.draw (MIT), milsymbol (MIT), FastAPI, SQLAlchemy, Alembic, reportlab."),
          P("Los créditos deben conservarse si el proyecto se redistribuye. Las cifras y reglas del simulador son parámetros de juego y no "
            "representan datos técnicos oficiales de ningún sistema real.")]

    doc.multiBuild(h)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--imagenes", required=True, help="carpeta con las capturas (cap_*.png), esquemas (diag_*.png) e ilustraciones (ilus_*.png)")
    ap.add_argument("--salida", default=str(RAIZ / "docs" / "Manual_SIETE.pdf"))
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    construir(salida, Path(args.imagenes))
    print(f"{salida} ({salida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
