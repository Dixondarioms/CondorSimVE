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

    def __init__(self, ruta, titulo="S.I.E.T.E. · Manual de referencia", **kw):
        self.titulo = titulo
        super().__init__(ruta, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.2 * cm, bottomMargin=2 * cm,
                         title=titulo, author="S.I.E.T.E. - Sistema Integral de Entrenamiento Táctico y Estratégico", **kw)
        marco = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal")
        self.addPageTemplates([PageTemplate(id="portada", frames=[marco], onPage=lambda c, d: None),
                               PageTemplate(id="normal", frames=[marco], onPage=self._decorar)])

    def _decorar(self, c, doc):
        c.saveState()
        c.setFont("Texto", 8.5)
        c.setFillColor(GRIS)
        c.drawString(self.leftMargin, A4[1] - 1.4 * cm, self.titulo)
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


# ------------------------------------------------------------------ autoria (portada y creditos de ambos manuales)
# escudo sin el fondo gris (tools/recortar_logo_dida.py); si falta, el original
LOGO_DIDA = next((x for x in (RAIZ / "frontend" / "static" / "img" / "dida_logo_recortado.png",
                              RAIZ / "frontend" / "static" / "img" / "dida_logo.jpg") if x.exists()),
                 RAIZ / "frontend" / "static" / "img" / "dida_logo.jpg")
CREADOR = "Cap. Dixon Malpica"
UNIDAD = "División de Ingeniería y Desarrollo Aeroespacial (DIDA)"


def credito_portada() -> list:
    """Escudo de la DIDA, unidad que creo el simulador, y el credito de su creador, para la portada."""
    texto = Paragraph(f"Desarrollado por la <b>{UNIDAD}</b><br/>Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana<br/>"
                      f"Creador del simulador: <b>{CREADOR}</b>",
                      ParagraphStyle("cred", parent=S["pc"], fontSize=10.5, leading=15, textColor=GRIS))
    if not LOGO_DIDA.exists():
        return [texto]
    im = Image(str(LOGO_DIDA))
    im.drawWidth, im.drawHeight = 3.0 * cm, 3.0 * cm * im.imageHeight / im.imageWidth
    t = Table([[im, texto]], colWidths=[3.4 * cm, 10.6 * cm], hAlign="CENTER")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    return [t]


def seccion_creditos(titulo: str) -> list:
    """Pagina de creditos: escudo de la DIDA, el creador del simulador y la unidad."""
    h = H1(titulo)
    if LOGO_DIDA.exists():
        im = Image(str(LOGO_DIDA))
        im.drawWidth, im.drawHeight = 7.5 * cm, 7.5 * cm * im.imageHeight / im.imageWidth
        h += [im, Spacer(1, 10)]
    centrado = ParagraphStyle("credc", parent=S["p"], alignment=TA_CENTER, fontSize=11, leading=16)
    h += [Paragraph(f"S.I.E.T.E. (Sistema Integral de Entrenamiento Táctico y Estratégico) fue concebido, diseñado y desarrollado por el "
                    f"<b>{CREADOR}</b>, de la <b>{UNIDAD}</b> de la Aviación Militar Bolivariana.", centrado),
          Spacer(1, 6), Paragraph("<i>«El infinito es el límite»</i>", centrado), Spacer(1, 14)]
    filas = [["Creador del simulador", CREADOR], ["Unidad", UNIDAD],
             ["Componente", "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana"]]
    t = Table([[Paragraph(f"<b>{a}</b>", S["celda"]), Paragraph(b, S["celda"])] for a, b in filas],
              colWidths=[5.0 * cm, ANCHO_TEXTO - 5.0 * cm], hAlign="CENTER")
    t.setStyle(TableStyle([("ROWBACKGROUNDS", (0, 0), (-1, -1), [CLARO, colors.white]), ("GRID", (0, 0), (-1, -1), 0.4, LINEA),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return h + [t]


# ------------------------------------------------------------------ el manual
def construir(salida: Path, img: Path) -> None:
    S["h2"].keepWithNext = 1  # un titulo nunca queda solo al pie de una pagina
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
        im.drawWidth, im.drawHeight = 12 * cm, 12 * cm * im.imageHeight / im.imageWidth
        h += [im, Spacer(1, 14)]
    h += [Paragraph("S.I.E.T.E.", S["titulo"]), Spacer(1, 6),
          Paragraph("Sistema Integral de Entrenamiento Táctico y Estratégico", S["subtitulo"]),
          Paragraph("Simulador de conducción militar para el adiestramiento táctico y estratégico", S["subtitulo"]), Spacer(1, 26),
          Paragraph("MANUAL DE REFERENCIA", ParagraphStyle("mu", parent=S["subtitulo"], fontName="Texto-B", fontSize=18, textColor=AZUL)),
          Spacer(1, 8), Paragraph("Qué es · cómo se hizo · instalación · cómo funciona", S["subtitulo"]), Spacer(1, 28)]
    h += credito_portada()
    h += [Spacer(1, 10), Paragraph(f"{fecha} · versión del manual 1.6", S["subtitulo"])]
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
            "evalúa; los <b>alumnos</b>, organizados por bando (azul y rojo) y por repartición del Estado Mayor (TIEM), aprecian la situación, "
            "redactan órdenes y ven sus consecuencias turno a turno."),
          P("Es una aplicación <b>web multiusuario</b> que se instala en un solo equipo del aula y se usa desde cualquier "
            "navegador de la red local. <b>No necesita internet</b>: el mapa satelital, el relieve, los planos de las bases "
            "aéreas, el catálogo de unidades y las librerías se sirven desde el propio servidor."),
          H2("1.1 Para qué sirve"),
          Bul(["Practicar el ciclo de conducción: apreciación de situación, decisión, emisión de órdenes, ejecución y evaluación.",
               "Ejercitar el trabajo de Estado Mayor según el TIEM: cada bando es el Estado Mayor de un componente aéreo (Comandante, JEM, "
               "A-1, A-2, A-3, A-3 D/A, A-4 y C-E) que parte de un Problema Militar Operativo, con calendario D/H, cadena de objetivos, "
               "niebla de guerra y comunicaciones simuladas.",
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
              ["Participantes", "Instructor (director), bando azul, bando rojo (varios alumnos por bando, cada uno en una repartición del TIEM) y observadores."],
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
            "director de ejercicio, reparticiones del Estado Mayor, turnos, niebla de guerra e informe posterior). No utiliza código, "
            "datos ni mapas de ningún producto de terceros."),
          H2("2.1 Arquitectura")]
    h += Img(img, "diag_arquitectura.png", "Esquema 1. Arquitectura: estaciones del aula, servidor y datos.")
    h += [Tbl(["Componente", "Tecnología", "Función"], [
        ["Servidor", "Python 3, FastAPI, Uvicorn", "API REST y WebSocket; sirve la interfaz y todos los datos."],
        ["Motor de simulación", "Python (paquete engine/)", "Catálogo, movimiento, visión, combate, aeronaves, misiones, misiles, guerra electrónica, logística, objetivos, informe."],
        ["Base de datos", "SQLite (por defecto) o PostgreSQL; SQLAlchemy + Alembic", "Escenarios, unidades, órdenes, usuarios, instantáneas de cada turno; migraciones automáticas."],
        ["Interfaz", "HTML, CSS y JavaScript sin frameworks; Leaflet; milsymbol", "Mapa táctico, paneles, órdenes, misiones, informe, videowall. Miniaturas 3D propias."],
        ["Seguridad", "Sesiones HttpOnly, PBKDF2-SHA256, CSP", "Roles y reparticiones verificados en el servidor; sin recursos externos; HTTPS opcional."],
        ["Pruebas", "pytest (motor, API, migraciones) y Node (lógica del cliente)", "Más de 550 pruebas automatizadas; arnés visual con datos simulados."],
    ], [3.0 * cm, 5.0 * cm, ANCHO_TEXTO - 8.0 * cm])]
    h += [H2("2.2 Datos y licencias"),
          P("Todo el material geográfico proviene de fuentes abiertas y se preparó una sola vez con internet mediante scripts "
            "del proyecto (carpeta <font face='Mono'>tools/</font>); después queda en el servidor para uso sin conexión."),
          Tbl(["Dato", "Fuente", "Licencia"], [
              ["Imagen satelital", "Sentinel-2 cloudless (EOX, Copernicus/ESA), hasta zoom 13", "CC BY 4.0"],
              ["Relieve y clases de terreno", "AWS Terrain Tiles (SRTM/GMTED), ESA WorldCover 2021", "Abierto / CC BY 4.0"],
              ["Fronteras, ríos, ciudades", "Natural Earth", "Dominio público"],
              ["Planos de aeródromos", "OpenStreetMap (pistas, rodajes, plataformas, hangares)", "ODbL 1.0"],
              ["Bases aéreas de la AMB", "Wikipedia y OurAirports (coordenadas, OACI, elevación)", "CC BY-SA / dominio público"],
              ["Aeródromos de América", "OurAirports (~1 260 aeropuertos y bases militares)", "Dominio público"],
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
            "<font face='Mono'>instalar.cmd</font> en la carpeta del proyecto: crea el entorno, instala las dependencias, crea la "
            "cuenta del administrador (<b>admin</b>, contraseña inicial <b>siete1234</b>; ver 3.4) y deja en el Escritorio el acceso directo <b>S.I.E.T.E.</b> que arranca el "
            "servidor y abre el navegador. Opciones: <font face='Mono'>instalar.cmd -Demo</font> (crea el escenario de demostración), "
            "<font face='Mono'>-Servicio</font> como administrador (arranque automático al encender el equipo) y <font face='Mono'>-Desinstalar</font>. "
            "<font face='Mono'>iniciar.cmd</font> y <font face='Mono'>detener.cmd</font> arrancan y detienen el servidor a mano."),
          P("Si la carpeta no trae los <b>datos de mapa</b> (unos 550 MB, la mayor parte la foto satelital), el instalador ofrece "
            "descargarlos, previa confirmación, del paquete <font face='Mono'>siete_datos.zip</font> publicado en GitHub; en un equipo sin "
            "internet se instalan desde un zip llevado en un pendrive. Otras opciones:"),
          Tbl(["Opción", "Efecto"], [
              ["-Datos &lt;zip o URL&gt;", "Instala los datos de mapa desde un zip ya descargado (siete_datos_*.zip) o desde una URL."],
              ["-SinDatos", "No pregunta ni descarga los datos de mapa (el mapa sale vacío hasta instalarlos)."],
              ["-Actualizar", "Actualiza una instalación existente (atajo: <font face='Mono'>actualizar.cmd</font>; ver 3.7)."],
              ["-Postgres &lt;url&gt;", "Usa PostgreSQL: guarda la conexión en backend\\.env, la prueba y aplica las migraciones; la clave no se muestra."],
              ["-Https", "Genera un certificado autofirmado y deja el arranque con HTTPS en el puerto 8443."],
              ["-Usuario (con SIETE_CONTRASENA)", "Instalación desatendida: crea ese instructor con esa contraseña en lugar de la cuenta admin."],
              ["-SinUsuario, -SinAccesoDirecto, -Destino", "No crear usuarios (el servidor crea admin al arrancar igualmente) y dónde (o si) crear el acceso directo."],
          ], [4.6 * cm, ANCHO_TEXTO - 4.6 * cm]),
          Code("instalar.cmd -Datos D:\\siete_datos_20260930.zip\ninstalar.cmd -Https -Servicio\nactualizar.cmd"),
          H3("Sin instalar Python: carpeta portátil con SIETE.exe"),
          P("Otra forma de llevar el simulador a un equipo es la <b>carpeta portátil</b> (<font face='Mono'>SIETE_portable_&lt;fecha&gt;.zip</font>): "
            "se descomprime en el servidor (por ejemplo en <font face='Mono'>C:\\SIETE</font>) y basta un <b>doble clic en SIETE.exe</b>. No hace "
            "falta instalar Python ni ningún otro programa: el ejecutable los lleva dentro. Se abre una ventana con las direcciones para las "
            "estaciones del aula y, a los pocos segundos, el navegador; cerrar esa ventana detiene el servidor. Si Windows pregunta por el "
            "cortafuegos, permita el acceso en redes privadas. La base de datos y los respaldos quedan en "
            "<font face='Mono'>SIETE\\backend</font>; para pasar a una versión nueva basta copiar <font face='Mono'>simulador_fenix.db</font> "
            "a la carpeta nueva. <font face='Mono'>Restablecer admin.cmd</font> recupera la cuenta del administrador. La carpeta se genera con "
            "<font face='Mono'>python tools/construir_ejecutable.py</font>."),
          H2("3.3 Instalación paso a paso (manual)"),
          Num([
              "Copie la carpeta del proyecto (<font face='Mono'>simulador_fenix</font>) al servidor, por ejemplo en <font face='Mono'>C:\\simulador_fenix</font>. "
              "Debe incluir <font face='Mono'>frontend/static/tiles_sat</font> (satélite), <font face='Mono'>tiles</font> (relieve) y <font face='Mono'>geo</font> (vectores y aeródromos).",
              ["Abra una consola (PowerShell o cmd) en la carpeta <font face='Mono'>backend</font> y cree el entorno con sus dependencias:",
               Code("cd C:\\simulador_fenix\\backend\npython -m venv venv\nvenv\\Scripts\\python -m pip install -r requirements.txt")],
              ["(Opcional) Cree el escenario de demostración para probar:", Code("venv\\Scripts\\python -m app.crear_demo")],
              ["Arranque el servidor. La base de datos se crea y se migra sola, y se respalda en cada arranque y cada 6 horas. "
               "La primera vez crea la cuenta <b>admin</b> con la contraseña inicial <b>siete1234</b>:",
               Code("venv\\Scripts\\python -m app.servidor --host 0.0.0.0 --port 8000")],
              "Desde cualquier estación abra <font face='Mono'>http://&lt;ip-del-servidor&gt;:8000/</font> e inicie sesión. "
              "Para conocer la IP del servidor: <font face='Mono'>ipconfig</font>.",
          ]),
          *Img(img, "cap_login.jpg", "Figura 1. Inicio de sesión, con el enlace «Solicitar una cuenta». Tras 5 intentos fallidos la cuenta se bloquea 5 minutos.", ancho=9.5 * cm),
          Nota("Deje la consola del servidor abierta mientras dure el ejercicio. Para detenerlo, Ctrl+C. Para que arranque solo al encender el "
               "equipo, cree una tarea programada de Windows que ejecute el comando de arranque."),
          H2("3.4 Usuarios, roles y reparticiones"),
          P("<b>Primer acceso del administrador.</b> Entre con el usuario <b>admin</b> y la contraseña inicial <b>siete1234</b>. El "
            "simulador pide de inmediato elegir una contraseña nueva (mínimo 8 caracteres) y no deja hacer nada más hasta "
            "cambiarla. Si alguna vez se pierde, en la carpeta <font face='Mono'>backend</font> del servidor:"),
          Code("venv\\Scripts\\python -m app.restablecer_admin"),
          P("devuelve <b>admin</b> a la contraseña inicial (con la misma obligación de cambiarla), sin tocar a los demás usuarios."),
          P("<b>Cuentas de los alumnos.</b> Cada alumno pide su cuenta en la pantalla de acceso con <b>Solicitar una cuenta</b>: elige "
            "usuario y contraseña, el rol (alumno azul o rojo, observador o instructor) y su repartición. La cuenta queda <b>pendiente</b> y no "
            "permite entrar hasta que el instructor la aprueba en <i>Consola → Usuarios → Solicitudes de cuenta pendientes</i>, con el rol "
            "y la repartición pedidos o con los que él decida; también puede rechazarla. El título <b>Usuarios</b> muestra cuántas hay pendientes "
            "y el simulador avisa cuando llega una nueva."),
          P("El instructor también puede crear cuentas directamente en el panel <b>Usuarios</b>, o ponerle una contraseña nueva a quien la "
            "olvidó (botón <b>Clave</b>): en ambos casos es <b>provisional</b> y el alumno debe cambiarla al entrar. Cualquier usuario cambia la "
            "suya desde el menú del perfil (<i>Cambiar contraseña</i>). Cada alumno tiene un rol (azul, rojo u observador) y, dentro del "
            "bando, una repartición del TIEM (comandante por defecto, o jem, a1, a2, a3, a3da, a4, ce). Por consola también se crean "
            "cuentas, ya aprobadas:"),
          Code("venv\\Scripts\\python -m app.crear_usuario da_azul --rol azul --puesto a3da\n"
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
               "<b>Actualizar a una versión nueva</b>: doble clic en <font face='Mono'>actualizar.cmd</font>. Respalda la base de datos en "
               "<font face='Mono'>backend/respaldos</font>, trae el código nuevo (<font face='Mono'>git pull</font> si la carpeta es un repositorio; si no, "
               "descarga el zip de GitHub y sobrescribe todo salvo la base de datos, los respaldos, los certificados, <font face='Mono'>.env</font> y los datos de mapa), "
               "reinstala las dependencias, aplica las migraciones y reinicia la tarea programada si existe.",
               "Sin internet en el servidor: detenga el servidor, haga un respaldo, reemplace la carpeta del proyecto "
               "(conservando <font face='Mono'>backend/simulador_fenix.db</font>, <font face='Mono'>backend/respaldos</font> y los datos de mapa) y arranque: las migraciones se aplican solas.",
               "<b>Datos de mapa aparte del código</b>: <font face='Mono'>python tools/empaquetar_datos.py</font> los deja en "
               "<font face='Mono'>dist/siete_datos_&lt;fecha&gt;.zip</font> (con su suma SHA-256; <font face='Mono'>--sin-satelite</font> hace un paquete ligero de ~60 MB) "
               "y <font face='Mono'>python tools/instalar_datos.py</font> o <font face='Mono'>instalar.cmd -Datos</font> los instala en otro equipo.",
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
            "<font face='Mono'>preparar_satelite.py --region &lt;id&gt;</font> (foto satelital de una región: Venezuela hasta el zoom 13 y América hasta el 8 ya incluidas), "
            "<font face='Mono'>preparar_aerodromos.py</font> (planos de las bases) y <font face='Mono'>generar_bases_aereas.py</font>."),
          P("<b>Mapa ficticio</b> (región <font face='Mono'>teatro_ficticio</font>): dos repúblicas inventadas, País Azul y País Rojo, en el "
            "Atlántico (6 a 12,5° N, 27,5 a 20° O), a ~300 m por píxel. Lo genera sin internet "
            "<font face='Mono'>python tools/generar_mapa_ficticio.py</font> a partir de una semilla fija (siempre el mismo mapa): tierra con "
            "ruido fractal, cordilleras de crestas, mesetas escalonadas y llanos; drenaje por relleno de depresiones y acumulación de "
            "flujo (ríos con nombre, lago y embalses detrás de represas); cobertura por humedad; ciudades donde se asientan las reales; "
            "carreteras por el camino de menor costo sobre el terreno (árbol de expansión mínima entre ciudades más enlaces vecinos); "
            "frontera, provincias, infraestructura y la plantilla <i>País Azul contra País Rojo</i> "
            "(<font face='Mono'>backend/data/plantillas_sistema/teatro_ficticio.json</font>). Escribe lo mismo que una región real: "
            "teselas de relieve y satelitales, capas vectoriales y las grillas del motor (clases, alturas y vías).")]

    # ---- 4 roles
    h += H1("4. Roles, reparticiones y acceso")
    h += Img(img, "diag_puestos.png", "Esquema 2. Roles del ejercicio y reparticiones del Estado Mayor de cada bando (TIEM).")
    h += [Tbl(["Rol", "Ve", "Puede"], [
        ["Instructor", "Todo, sin niebla; puede «ver como» un bando", "Crear y editar escenarios, ubicar unidades, clima, eventos, ajustes, usuarios, resolver turnos, informe"],
        ["Azul / Rojo", "Sus unidades, los enemigos detectados, los últimos contactos y su Problema Militar", "Emitir y cancelar órdenes y misiones de su repartición, gráficos, chat, marcar «listo» (Comandante o JEM); informe al finalizar"],
        ["Observador", "Todo", "Solo lectura, incluido el informe"],
    ], [2.4 * cm, 5.6 * cm, ANCHO_TEXTO - 8.0 * cm]),
          Tbl(["Repartición", "Conduce (función)", "Confirma «listo»"], [
              ["comandante · CMDTE", "Todo el bando (todas las funciones); por defecto para un solo alumno", "Sí"],
              ["jem · Jefe de Estado Mayor", "Todas las funciones; coordina a las reparticiones", "Sí"],
              ["a1 · A-1 Personal", "Ninguna orden a unidades: efectivos, bajas y apreciación de personal", "No"],
              ["a2 · A-2 Inteligencia", "reconocimiento: unidades y drones de reconocimiento", "No"],
              ["a3 · A-3 Operaciones", "superficie (terrestres, navales, lanzadores), aereo (ataque, helicópteros, drones armados, cisternas), "
               "caza y despegar (bases y portaaviones)", "No"],
              ["a3da · A-3 D/A Defensa Aérea", "defensa_aerea (radares, antiaérea, alerta temprana), caza y despegar", "No"],
              ["a4 · A-4 Logística", "logistica: convoyes, depósitos, ingenieros y toda orden de construir", "No"],
              ["ce · C-E Comunicaciones y Electrónica", "guerra_electronica: escucha e interferencia terrestres y aviones de GE", "No"],
          ], [4.4 * cm, ANCHO_TEXTO - 7.2 * cm, 2.8 * cm]),
          P("La función de cada orden la decide <font face='Mono'>engine/puestos.py</font> (<font face='Mono'>funcion_de_orden</font>) "
            "por la clase de la unidad y el tipo de orden; el servidor rechaza toda orden fuera de la repartición explicando a quién "
            "corresponde, y la interfaz solo muestra las herramientas de cada una. Los ids anteriores al TIEM (mando, inteligencia, "
            "operaciones, logistica, planificacion) se traducen solos (migración 0025: mando → comandante, inteligencia → a2, "
            "operaciones y planificacion → a3, logistica → a4). Los alumnos y observadores solo ven los escenarios que el instructor "
            "les asigna.")]

    # ---- 5 pantalla
    h += H1("5. La pantalla")
    h += Img(img, "cap_azul.jpg", "Figura 2. Pantalla de un alumno del bando azul (Comandante) con datos de ejemplo.")
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
               "<b>Usuarios</b>: crear alumnos y observadores, asignar su repartición y asignarlos al escenario.",
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
              ["Construir", "Ingenieros (A-4)", "Vado o puente, clic sobre un río", "Cruce para vehículos pesados; dura 4 o 12 turnos."],
              ["Despegar", "Bases aéreas y portaaviones (A-3, A-3 D/A)", "«Enviar aeronaves o drones…»: modelo, cantidad, indicativo", "El grupo nace junto a la base al resolverse; recibe órdenes el turno siguiente."],
              ["Patrullar", "Aeronaves (A-3; caza también A-3 D/A)", "Clic en el punto de patrulla", "Se mantiene en la zona e intercepta aviones enemigos al alcance."],
              ["Aterrizar", "Aeronaves en vuelo (su repartición)", "Base o portaaviones propio con plazas", "Estaciona, reabastece y rearma en 2 turnos."],
              ["Interferir", "Guerra electrónica (C-E)", "Clic en el centro de la zona", "Degrada sensores, antiaérea y enlaces de drones enemigos; delata al emisor."],
              ["Lanzar misiles", "Fragata, destructor, submarino, batería (A-3)", "Blanco detectado en tierra o mar y 1–4 misiles", "Salva de misiles de crucero guiada; puede ser interceptada."],
              ["Misión aérea", "Grupos (su repartición) o despegues programados (A-3, A-3 D/A)", "«Planificar misión…»: rol y ruta con puntos", "El grupo ejecuta solo la misión turno tras turno."],
          ], [2.2 * cm, 3.2 * cm, 4.6 * cm, ANCHO_TEXTO - 10.0 * cm]),
          H2("7.2 Acciones inmediatas desde la ficha de la unidad"),
          Bul(["<b>Radar</b> (radares, antiaérea guiada por radar, destructores): encender o apagar. Apagado ve solo 5 km, pero la escucha enemiga no lo localiza.",
               "<b>Fuego automático</b> (antiaérea, destructores): libre o retenido.",
               "Estas acciones rigen de inmediato, no esperan al turno."]),
          H2("7.3 Confirmar y resolver"),
          P("Cuando el bando termina, pulsa <b>Estoy listo</b> (lo confirman el Comandante o el JEM). El turno se resuelve cuando el instructor pulsa "
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
               "<b>Antiaérea automática</b>: con el fuego libre dispara sola cada turno contra la aeronave enemiga más cercana a su alcance que el bando detecte; la guiada por radar necesita el radar encendido (apagado, solo tira por orden y a ojo, ×0,3). La portátil infrarroja no depende del radar, pero debe desplegarse un turno y recarga otro."]),
          H2("8.5 Relieve, línea de vista y perfil de vuelo"),
          P("Ningún sensor detecta lo que no tiene en su <b>línea de vista</b>. El simulador conoce la altura del terreno en cada punto y la de "
            "cada unidad (el suelo más su antena: radar 25 m, destructor 30 m, infantería 3 m…; o la cota de vuelo de las aeronaves). Si una "
            "montaña se interpone, el objetivo queda en la <b>sombra de radar</b>; y la curvatura de la Tierra (con la refracción normal del radar) "
            "pone un <b>horizonte</b>: dos buques se ven a unos 43 km y un avión rasante sobre el llano o el mar se pierde a unos 54 km."),
          Tbl(["Perfil de vuelo", "Cota", "Ventajas", "Costos"], [
              ["Alto", "6 000 m", "Fuera del techo de la antiaérea portátil; gasta 15 % menos combustible.", "Lo ven los radares desde muy lejos, por encima del relieve."],
              ["Medio", "1 500 m", "Equilibrado (el perfil por defecto de aviones y drones).", "Lo ocultan solo las montañas altas que tenga delante."],
              ["Rasante", "60 m", "Se esconde tras el relieve y bajo el horizonte del radar.", "Gasta 30 % más; la antiaérea portátil le hace ×1,25 de daño."],
          ], [2.6 * cm, 1.8 * cm, 6.3 * cm, ANCHO_TEXTO - 10.7 * cm]),
          Bul(["Los helicópteros vuelan medio o rasante (por defecto rasante); los misiles de crucero, siempre rasantes (30 m).",
               "Un radar en una cumbre ve detrás de ella; en un valle queda casi ciego a baja cota. La escucha electrónica también necesita "
               "línea de vista, y la antiaérea no dispara a lo que el relieve le oculta.",
               "Al seleccionar un sensor, el mapa dibuja su <b>cobertura</b> real contra aeronaves a cota media (turquesa) y a baja cota (naranja)."]),
          H2("8.6 Ciclo de día y noche"),
          P("Con el ciclo activo (<i>Consola → Dirección del ejercicio</i>; campo <font face='Mono'>dia_noche</font>), cada turno cae en un "
            "periodo según su hora simulada (hora de inicio + una hora por turno): <b>día</b> de 07:00 a 17:59, <b>crepúsculo</b> a las 06:00 y "
            "a las 18:00 y <b>noche</b> el resto (Venezuela está cerca de los 10° N: el sol sale hacia las 06:00 y se pone hacia las 18:30). El "
            "radio de detección del sensor se multiplica por:"),
          Tbl(["Sensor", "Día", "Crepúsculo", "Noche"], [
              ["Radares y emisores (radar de vigilancia, antiaérea guiada, destructor, alerta temprana) y escucha electrónica", "×1,0", "×1,0", "×1,0"],
              ["Cámaras (aviones, helicópteros, drones, reconocimiento terrestre)", "×1,0", "×0,9", "×0,8"],
              ["A simple vista (el resto: tropas, vehículos, bases, buques sin radar)", "×1,0", "×0,75", "×0,5"],
          ], [ANCHO_TEXTO - 6.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm]),
          P("El factor se aplica después del clima, el terreno y la firma radar del objetivo, y vale igual para ambos bandos y para el "
            "adversario automático. La tarjeta <b>Estado del escenario</b> muestra la hora y el periodo, y el fondo del mapa se oscurece de "
            "noche (las unidades y los gráficos no). Las plantillas contra la IA y la del 3 de enero traen el ciclo encendido "
            "(<font face='Mono'>backend/app/engine/clima.py</font>, <font face='Mono'>periodo_del_dia</font> y <font face='Mono'>factor_nocturno</font>)."),
          H2("8.7 Adversario automático (combate contra la IA)"),
          P("El adversario automático (<font face='Mono'>backend/app/adversario.py</font>) conduce uno o los dos bandos "
            "(<i>Consola → Dirección del ejercicio</i>; campos <font face='Mono'>ia_azul</font>, <font face='Mono'>ia_rojo</font> e "
            "<font face='Mono'>ia_nivel</font>). Al abrirse cada turno, y en el turno en curso al encenderlo, da las órdenes de su bando y lo "
            "marca listo; el pie de pantalla muestra «IA · LISTO». Sus órdenes pasan por la misma validación que las de los alumnos y "
            "<b>solo usa lo que su bando sabe</b>: sus unidades, las enemigas que detecta (posición, tipo y clase; nunca su fuerza ni su "
            "logística), los últimos contactos, sus objetivos y la ubicación de las bases enemigas."),
          Bul(["<b>Aeronaves</b>: vuelven a una base con plazas libres con poco combustible o munición; atacan el mejor blanco a su alcance o se "
               "acercan a uno que puedan batir y del que puedan volver. Las que no llevan armas (alerta temprana, cisterna, guerra electrónica) "
               "se mantienen fuera del alcance de la antiaérea que ven; las de guerra electrónica interfieren.",
               "<b>Bases y portaaviones</b>: lanzan cazas si el enemigo tiene aviación a la vista y no hay suficientes cazas propios en vuelo.",
               "<b>Unidades terrestres</b>: se reabastecen, atacan si la relación de fuerzas es favorable, persiguen blancos cercanos y van a sus "
               "objetivos (ocupar, destruir, proteger). Los convoyes reabastecen a las unidades necesitadas y recargan en los depósitos.",
               "<b>Buques y baterías</b>: lanzan salvas de misiles. Radares, antiaérea e ingenieros quedan en posición."]),
          Tbl(["Parámetro (tabla NIVELES)", "Prudente", "Normal", "Agresiva"], [
              ["Relación mínima ataque / defensa para atacar", "0,9", "0,6", "0,35"],
              ["Persecución de un blanco terrestre", "30 km", "60 km", "150 km"],
              ["Distancia de aproximación (fracción de su alcance)", "0,9", "0,8", "0,7"],
              ["Combustible para regresar (puntos sobre el umbral)", "+10", "0", "−10"],
              ["Evita entrar en la antiaérea conocida con aeronaves armadas", "sí", "no", "no"],
              ["Cazas propios en vuelo por avión enemigo antes de dejar de lanzar", "1", "1", "2"],
          ], [ANCHO_TEXTO - 6.6 * cm, 2.2 * cm, 2.2 * cm, 2.2 * cm]),
          P("<b>Modo demostración</b>: el botón de la misma sección activa la IA en los dos bandos con un límite de decisión de 15 s, de modo "
            "que el ejercicio avanza solo. La biblioteca trae tres plantillas <b>contra la IA</b> (defensa aérea de la región central, "
            "interdicción en los llanos y defensa de la costa oriental), con el bando rojo conducido por el simulador; la lista de "
            "<i>Desde plantilla…</i> las distingue con una etiqueta. Es una conducta didáctica y legible, no óptima: sirve de oponente, no "
            "reemplaza al análisis del instructor.")]
    h += [H2("8.8 Infraestructura no militar"),
          P("Cinco clases fijas de un bando (<font face='Mono'>backend/app/engine/infraestructura.py</font>): central termoeléctrica, "
            "central hidroeléctrica, refinería, centro de comunicaciones y puente estratégico. No se mueven, no combaten ni detectan y no "
            "tienen personal militar; se las ataca como a una base y pueden ser objetivo. La <b>capacidad</b> de cada categoría es la fuerza "
            "media de las instalaciones del bando (destruida = 0); si el bando no tiene ninguna, la categoría no le afecta."),
          Tbl(["Categoría", "Efecto con capacidad c (0 a 1)", "Mínimo"], [
              ["Energía (centrales)", "Alcance de los radares de vigilancia fijos × (0,5 + 0,5·c)", "×0,5"],
              ["Combustible (refinerías)", "Reposición de combustible de los depósitos × (0,25 + 0,75·c)", "×0,25"],
              ["Comunicaciones", "Probabilidad de demora de cada orden + 30·(1 − c) puntos (se suma a la del instructor)", "+30 %"],
              ["Puentes", "Con fuerza < 50 el puente queda cortado en su radio: la carretera no da paso sobre río o agua", "cortado"],
          ], [3.8 * cm, ANCHO_TEXTO - 5.8 * cm, 2.0 * cm]),
          P("Los cambios de capacidad de 5 puntos o más y cada puente que se corta se informan al bando al cerrar el turno. La capa "
            "<b>Infraestructura</b> del mapa trae 40 instalaciones reales de Venezuela ubicadas con OpenStreetMap "
            "(<font face='Mono'>tools/preparar_infraestructura.py</font>): 21 centrales, 4 refinerías, 4 centros de comunicaciones y 11 "
            "puentes, con su capacidad y, en los puentes, el largo; el instructor las coloca en el ejercicio con un clic."),
          H2("8.9 Personal"),
          P("Cada unidad tiene una dotación (<font face='Mono'>engine/personal.py</font>): la que fija el instructor o, por defecto, por "
            "escalón en las terrestres (compañía 120, batallón 500, brigada 3 500…), por tripulación en las aeronaves (caza 1, ataque 2, "
            "helicóptero 4, alerta temprana 15) y por buque o instalación (fragata 180, destructor 280, portaaviones 4 500, base aérea "
            "600). Los efectivos actuales siguen a la fuerza; la diferencia son las bajas. Los drones, los misiles y la infraestructura "
            "civil no llevan personal. La pestaña Situación resume efectivos, bajas y porcentaje operativo por rama; los del enemigo no se "
            "conocen."),
          H2("8.10 Cuadro radar y aviso de contactos"),
          P("Para cada sensor activo del bando (clases con radar, vigilancia aérea o escucha) el estado incluye lo que detecta en ese "
            "momento con las mismas reglas de la niebla de guerra: distancia, rumbo desde el sensor, cota si vuela y si lo localizó por su "
            "emisión. Al cerrar cada turno, cada sensor informa al bando los enemigos que este no tenía a la vista el turno anterior "
            "(evento «radar»). La previsualización de una orden de mover también da el <b>tiempo de todo el recorrido</b> (mismas "
            "reglas de terreno, carreteras, ríos, clima y peso), los turnos y la hora simulada de llegada.")]
    h += [H2("8.11 El TIEM en el simulador (etapa 1)"),
          P("El simulador se reorienta al <b>Trabajo Integral de Estado Mayor</b> (TIEM): cada bando es el Estado Mayor del componente "
            "aéreo de un Teatro de Operaciones. La etapa 1 incorpora los cimientos sobre los que se apoyarán la apreciación, el plan y la "
            "supervisión de las etapas siguientes:"),
          Bul(["<b>Reparticiones</b> (<font face='Mono'>engine/puestos.py</font>): funciones superficie, aereo, caza, despegar, "
               "defensa_aerea, reconocimiento, logistica, guerra_electronica y listo; la matriz del capítulo 4 se aplica en el servidor "
               "(<font face='Mono'>auth.exigir_funcion</font>) y se refleja en la interfaz (<font face='Mono'>logica.js</font>).",
               "<b>Problema Militar Operativo</b> (<font face='Mono'>engine/pmo.py</font>, tabla <font face='Mono'>problemas_militares</font>, "
               "API <font face='Mono'>/api/escenarios/{id}/pmo</font>): diez párrafos por bando; la misión se guarda por partes (tarea, qué, "
               "dónde, cuándo, propósito) y se valida con las reglas del TIEM. El generador usa los países, las unidades (las enemigas en "
               "cantidades aproximadas y por zona, nunca con su posición exacta), los objetivos (postura ofensiva o defensiva), las "
               "ciudades de las capas <font face='Mono'>lugares.geojson</font> (<font face='Mono'>engine/lugares.py</font>) y el calendario. "
               "Lo redactado por el instructor no se reemplaza salvo pedido expreso.",
               "<b>Calendario</b> (<font face='Mono'>engine/calendario.py</font>): fecha del turno 1, turno de la hora H, último turno y "
               "fases; cada turno se nombra D±n y H±n. Si faltan, el generador fija la fecha (día siguiente a la creación), H tres turnos "
               "después del actual y 24 turnos de duración.",
               "<b>Conducción de cada bando</b>: <font face='Mono'>conduce_azul/rojo</font> (alumnos o instructor) más el adversario "
               "automático (<font face='Mono'>ia_azul/rojo</font>, con prioridad). El instructor conduce enviando la cabecera "
               "<font face='Mono'>X-Conduce-Bando</font> (dependencia <font face='Mono'>auth.conductor</font>): para el servidor es el "
               "Comandante de ese bando; sus órdenes cuentan para el bando pero no en la evaluación por alumno.",
               "<b>Cadena de objetivos</b> (<font face='Mono'>engine/objetivos.py</font>): nivel (ulterior, asignado, material), "
               "<font face='Mono'>padre_id</font>, efecto deseado, indicador y umbral. «neutralizar» se cumple cuando la fuerza baja al "
               "umbral (50 %); «efecto» cuando se cumple el umbral (100 %) de sus dependientes y falla cuando ya no puede; "
               "<font face='Mono'>hasta_turno</font> es un plazo para todos menos proteger. El generador agrupa los objetivos materiales "
               "en asignados (superioridad aérea, sostenimiento, superficie, terreno, capacidad propia) bajo un ulterior.",
               "Migraciones 0025 (reparticiones) y 0026 (PMO, calendario, conducción y cadena). Las plantillas, la copia y la "
               "exportación de escenarios guardan todo lo anterior."]),
          H2("8.12 El TIEM en el simulador (etapa 2): la apreciación inicial"),
          Bul(["<b>Documentos</b> (<font face='Mono'>engine/tiem.py</font>, tabla <font face='Mono'>documentos_tiem</font>, API "
               "<font face='Mono'>/api/escenarios/{id}/tiem</font>): análisis de la misión, concepto del comandante, guía de "
               "planeamiento y formas de acción, con los párrafos del formato guía del TIEM. Campos de texto, misión por partes, "
               "tablas (tareas, COG con CC/RC/VC, objetivos, efectos, capacidades del enemigo, suposiciones, cronograma, PRC) y F/A "
               "con el criterio APA.",
               "<b>Permisos</b>: cada documento lo redactan las reparticiones del TIEM (concepto: CMDTE y JEM; guía: JEM; F/A: A-3, "
               "A-3 D/A, A-2); el bando entero lo lee; el instructor ve y edita todos.",
               "<b>Estados</b>: borrador → presentado (bloqueado; solo si no falta nada: <font face='Mono'>tiem.revisar</font>) → "
               "aprobado o devuelto con observaciones; cada paso avisa al bando (evento «tiem») y la revisión queda en el informe.",
               "<b>Ayudas</b> (<font face='Mono'>/sugerencias</font>): transcriben el PMO, la cadena de objetivos y el calendario y "
               "agregan el Poder Relativo de Combate; solo llenan campos vacíos. El análisis (COG, tareas deducidas, F/A, APA) "
               "queda a cargo de los alumnos.",
               "<b>PRC preliminar</b> (<font face='Mono'>/prc</font>): por factor, poder de cada unidad = fuerza × aeronaves × "
               "(mejor ataque + defensa) / 2; los sensores sin armas valen 1; lo enemigo, con un error fijo de hasta ±15 %. "
               "Relación ≥ 1,5 favorable, 0,67 a 1,5 equilibrado, menor desfavorable.",
               "<b>Archivos adjuntos</b> (tabla <font face='Mono'>archivos_tiem</font>): .doc, .docx, .odt, .rtf o .pdf hasta "
               "10 MB, hasta 5 por documento, guardados en la base (viajan con sus respaldos). Migración 0027."]),
          H2("8.13 El TIEM en el simulador (etapa 3): apreciaciones de Estado Mayor y juego de guerra"),
          Bul(["<b>Seis apreciaciones</b> (Fase I, Paso 2) con sus formatos guía: Inteligencia (A-2: situación del enemigo, "
               "capacidades, su practicabilidad y aceptabilidad, conclusiones), Operaciones (A-3) y Defensa Aérea (A-3 D/A): "
               "situación, PRC, fortalezas y debilidades, <b>confrontación</b>, comparación y F/A recomendada; Personal (A-1), "
               "Logística (A-4) y Comunicaciones y Electrónica (C-E): situación del área, análisis de cada F/A operacional y "
               "conclusiones.",
               "<b>Matriz de confrontación</b> (campo de tipo matriz): celdas {F/A, capacidad, efecto (no afecta, degrada, anula), "
               "análisis}. Filas y columnas salen del contexto del bando (<font face='Mono'>tiem.contexto</font>): las F/A del "
               "documento de Formas de Acción y las capacidades de la Apreciación de Inteligencia o de la Guía.",
               "<b>Ayudas de cada área</b>: situación de personal (<font face='Mono'>engine/personal.py</font>), logística "
               "(existencias, convoyes, refinación, puentes), comunicaciones (centros, energía, guerra electrónica, red degradada) y "
               "defensa aérea (radares, antiaérea, caza y amenaza aérea estimada).",
               "<b>Juego de guerra</b> (<font face='Mono'>app/ensayos.py</font>, <font face='Mono'>POST /tiem/{bando}/ensayos</font>): "
               "copia del escenario en su estado actual (unidades con todas sus columnas y referencias reasignadas, objetivos con su "
               "cadena, calendario, PMO y contactos del bando), con la IA conduciendo al enemigo, resolución automática y solo los "
               "alumnos del bando asignados. Hasta 3 por bando; no se ensaya un ensayo. El resumen (turnos, objetivos, puntos, "
               "unidades perdidas) se lista en la pestaña TIEM. Campos <font face='Mono'>ensayo_de</font>, "
               "<font face='Mono'>ensayo_bando</font>, <font face='Mono'>ensayo_fa</font> y <font face='Mono'>ensayo_desde</font> "
               "del escenario (migración 0028)."]),
          H2("8.14 El TIEM en el simulador (etapa 4): decisión, plan y órdenes"),
          Bul(["<b>Decisión del Comandante</b> (Fase I, Paso 3; solo el Comandante), <b>Análisis previo al plan</b> (Fase II, "
               "Paso 1; JEM y A-3) y <b>Plan de Operaciones</b> (Fase II, Paso 2; JEM, A-3 y A-3 D/A), con sus formatos guía. Las "
               "ayudas traen la F/A recomendada por la A-3, la organización de la fuerza (unidades propias por categoría), los "
               "objetivos materiales de la cadena y las aeronaves por esfuerzo (ofensivo, defensivo, apoyo).",
               "<b>Tareas del plan</b> (campo de tipo tareas): {id, unidad, acción (mover, atacar, patrullar, apoyar, aterrizar, "
               "interferir), turno, objetivo o destino («o:&lt;id&gt;» objetivo del bando, «u:&lt;id&gt;» unidad) y detalle}. Las "
               "opciones del editor salen de <font face='Mono'>GET /tiem</font> (<font face='Mono'>opciones_tarea</font>): unidades "
               "propias, objetivos y unidades enemigas conocidas (vistas o con contacto).",
               "<b>Orden de Operaciones</b> (<font face='Mono'>POST /tiem/{bando}/emitir</font>): las tareas que vencen hasta el turno "
               "en curso y no se emitieron se traducen a órdenes y pasan por <font face='Mono'>ordenes._crear_orden</font>, la "
               "misma validación de una orden manual, con la repartición de quien las emite; la posición de un enemigo sale de lo "
               "que el bando ve o de su último contacto. Cada resultado queda en la tabla <font face='Mono'>ejecuciones_tarea</font> "
               "(emitida con su orden, o rechazada con el motivo, que se puede reintentar). Migración 0029."]),
          H2("8.15 El TIEM en el simulador (etapa 5): supervisión de la ejecución"),
          Bul(["<b>Cuadro de supervisión</b> (<font face='Mono'>engine/supervision.py</font>, en <font face='Mono'>GET /tiem</font>): "
               "renglones objetivo, resultado, diferencia, estado (conforme, en curso, desvío, fallido) y causa sugerida, a partir "
               "de las tareas vencidas (su ejecución y el estado y resultado de su orden), los objetivos del bando (estado, "
               "progreso y plazos que vencen en 2 turnos) y las unidades propias destruidas o con menos del 50 % de fuerza. Solo "
               "usa información propia: nunca el estado real del enemigo.",
               "<b>Parte del turno</b>: órdenes del turno anterior cumplidas y rechazadas, eventos de objetivos y pérdidas propias.",
               "<b>Documento de Supervisión</b> (Fase III): registro de causas y acciones correctivas, apreciaciones rápidas y "
               "<b>órdenes fragmentarias</b> (campo de tipo tareas), que <font face='Mono'>POST /tiem/{bando}/emitir</font> emite "
               "junto con las del Plan de Operaciones aunque el plan esté aprobado."]),
          H2("8.16 El TIEM en el simulador (etapa 6): evaluación y exportación"),
          Bul(["<b>Evaluación</b> (<font face='Mono'>engine/tiem_evaluacion.py</font>, <font face='Mono'>GET /tiem/evaluacion</font> "
               "y la clave <font face='Mono'>tiem</font> de cada bando en la rúbrica): indicadores documentos (aprobados 1, "
               "presentados 0,5, sobre 13), forma (sin faltantes ni avisos), oportunidad (Fase I presentada hasta H), ejecución "
               "(tareas vencidas emitidas) y supervisión (desvíos con causa y acción); nota automática = 1 + 19 × promedio / 100; "
               "nota del instructor = promedio de las notas (1 a 20) puestas al revisar cada documento (columna "
               "<font face='Mono'>nota</font>, migración 0030); calificación = promedio de ambas.",
               "<b>Exportación</b> (<font face='Mono'>app/legajo.py</font>): bloques independientes del formato (títulos, párrafos, "
               "viñetas, misión y tablas: COG, matriz de confrontación, F/A con su APA, tareas) que se escriben como .docx "
               "(WordprocessingML en un zip, sin dependencias; tablas con fila de títulos repetida) o como página HTML "
               "imprimible. Rutas <font face='Mono'>/tiem/{bando}/legajo.docx</font>, <font face='Mono'>legajo.html</font>, "
               "<font face='Mono'>/tiem/{bando}/{tipo}/documento.docx</font> y <font face='Mono'>documento.html</font>."])]
    h += [H2("8.17 Sistemas de defensa aérea con sus armas"),
          Bul(["<b>Datos</b> (<font face='Mono'>engine/defensa_aerea.py</font>): ZU-23-2 (clase nueva <font face='Mono'>artilleria_antiaerea</font>, "
               "sin emisión), S-125 Pechora-2M y Buk-M2E (modelos de <font face='Mono'>antiaerea</font>). Cada sistema: armas (misil "
               "guiado por radar, infrarrojo o cañón) con alcance mínimo y máximo, franja de altura, pk por misil, misiles por "
               "salva, velocidad, cargados y reserva, y tiempo de recarga; radar de vigilancia y de tiro, reacción, canales, "
               "despliegue, repliegue, movilidad, vehículos y personal. Valores de referencia de fuentes abiertas, ajustables.",
               "<b>Enfrentamiento</b> (<font face='Mono'>enfrentar</font>, fase 2c de <font face='Mono'>orders.py</font>): por cada "
               "aeronave detectada por el bando y en línea de vista, arma elegida (la del operador o la de mayor pk que alcance), "
               "factor de aspecto 0,775 + 0,225·cos θ sobre el alcance (1 de frente, 0,55 alejándose), exposición = cuerda de la "
               "trayectoria del turno dentro del alcance útil, salvas = tiempo disponible / (reacción + vuelo del misil + 10 s) "
               "limitadas por canales y misiles; recarga desde la reserva con su tiempo de inoperatividad. Probabilidad por salva "
               "1 − (1 − pk)^n; derribos esperados por grupo (× azar si está activo) que restan fuerza a la aeronave. Modificadores: "
               "interferencia (pk ×0,6 y radar de tiro ×0,6), evasión de tripuladas (×0,8 misiles, ×0,7 cañón; su ataque ×0,85 ese "
               "turno), firma radar (×(0,5 + 0,5·firma)), cota < 100 m para guiados por radar (×0,85), noche para cañones (×0,6), y "
               "factor por tipo de blanco (helicópteros y drones más fáciles, misiles de crucero más difíciles).",
               "<b>Estado</b>: columnas <font face='Mono'>cargas_json</font> (listos y reserva de cada arma) y "
               "<font face='Mono'>arma_elegida</font> (migración 0031); la munición de la unidad es el total de la reserva y el "
               "reabastecimiento se reparte entre las armas a las que les falta. <font face='Mono'>POST /unidades/{id}/defensa</font> "
               "acepta <font face='Mono'>arma</font>; <font face='Mono'>GET /api/catalogo</font> trae <font face='Mono'>sistemas_da</font>."])]
    h += Img(img, "cap_ia_noche.jpg", "Figura 4. Un alumno del bando azul contra la IA a las 23:00: el mapa oscurecido, la hora y el periodo en Estado del escenario y el bando rojo «IA · LISTO».")

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
            "(la repartición que lo conduce) o un grupo que despegará de una base en un turno programado, hasta 24 turnos después (A-3 o A-3 D/A). Mientras se traza, el servidor estima "
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
        h += [t, Paragraph("Figura 5. Ilustraciones de los modelos genéricos (generadas de sus miniaturas 3D). El F-16 y el Su-30 usan fotografías reales.", S["cap"])]
    h += [H2("9.4 Portaaviones"),
          P("Un portaaviones es una <b>base aérea móvil</b>: lanza y recibe aeronaves como una base, con 10 plazas y existencias propias (1500) que "
            "repone junto a un puerto propio (100 puntos por turno). Solo operan desde él las aeronaves <b>embarcables</b>: helicópteros, drones, "
            "munición merodeadora y el modelo Caza embarcado; el F-16, el Su-30, el avión de ataque ligero y el de guerra electrónica solo desde bases "
            "terrestres. Las aeronaves a bordo navegan con él, sufren parte del daño que recibe y se hunden si lo hunden. Sus armas propias son "
            "débiles: necesita escolta.")]
    h += Img(img, "cap_naval.jpg", "Figura 6. Grupo naval del bando azul: portaaviones con un helicóptero a bordo, destructor, submarino y una salva de misiles en vuelo.")

    # ---- 10 bases en detalle
    h += H1("10. Las bases aéreas en detalle")
    h += [P("Al acercar el mapa (zoom 11 en adelante) cada base aérea de la AMB se dibuja con su <b>plano real</b> tomado de OpenStreetMap: el "
            "perímetro, las pistas con su largo, ancho y orientación reales (bordes, umbrales, eje, zona de toma de contacto y la numeración de "
            "cada cabecera), las calles de rodaje con su eje amarillo, las plataformas, los helipuertos y los hangares y edificios con su sombra. "
            "Bases incluidas: El Libertador (SVBL), Mariscal Sucre (SVBS), La Carlota (SVFM), Rafael Urdaneta (SVMC), Luis del Valle García (SVBC), "
            "Landaeta Gil (SVBM), Teófilo Luis Méndez (SVPR) y José Antonio Páez (SVPA)."),
          P("Lo mismo vale para los <b>aeródromos de los países vecinos y de toda América</b> de la capa de bases: cada uno que OpenStreetMap "
            "tiene cartografiado se ve con su plano real al acercarse y se puede ocupar con una base del ejercicio igual que una venezolana. "
            "El simulador solo descarga del servidor el plano de los aeródromos que quedan a la vista, así que tener más de mil no hace más "
            "lento el mapa.")]
    h += Img(img, "cap_base_plano.jpg", "Figura 7. Aeropuerto de Barinas (SVBI, civil) al zoom 15, ocupado por una base aérea del ejercicio: pistas 03/21 y 13/31, rodajes, plataforma con los F-16 estacionados y cráteres por el daño recibido.")
    h += [Bul(["Una unidad <b>base aérea</b> del ejercicio a menos de 4 km del aeródromo lo «ocupa»: al acercarse, su miniatura se reduce a una ficha «BA» y sus aeronaves estacionadas se dibujan sobre la plataforma real.",
               "<b>Daños</b>: con la base dañada aparecen cráteres en la pista (uno cada 7 % de fuerza perdida); por debajo del 25 %, cuando ya no puede lanzar ni recibir aviones, se pintan las cruces amarillas de pista cerrada y el rótulo «PISTA INOPERATIVA». El enemigo no ve el daño de una base ajena.",
               "El detalle depende de lo mapeado en OpenStreetMap: en algunas bases militares hay pocas construcciones cargadas y el simulador no las inventa."])]
    h += Img(img, "cap_base_cerca.jpg", "Figura 8. Zoom 17 sobre la pista: marcas, cráteres y la ficha de la base.")
    h += Img(img, "cap_carlota.jpg", "Figura 9. Base Aérea La Carlota (Caracas) con sus edificios, rodajes y helipuertos.")

    # ---- 11 catalogo
    h += H1("11. Catálogo de unidades")
    h += [P(f"Las {n_clases} clases del catálogo y sus valores de juego (ataque T / A / N = efectividad contra objetivos terrestres, aéreos y "
            "navales; 0 = no puede atacarlos). Son parámetros didácticos ajustables en <font face='Mono'>backend/app/engine/catalogo.py</font>.")]
    h.append(tabla_catalogo())

    # ---- 12 seguimiento
    h += H1("12. Seguimiento, videowall e informe")
    h += Img(img, "cap_videowall.jpg", "Figura 10. Modo videowall para la pantalla del centro de operaciones (tecla V o botón Videowall).")
    h += Img(img, "cap_america.jpg", "Figura 11. Región «América» con foto satelital (~600 m por píxel) y Venezuela en detalle encima; cualquier punto del continente sirve para ambientar un ejercicio.")
    h += [Bul(["<b>Eventos y alertas</b>: despegues, combates, bases sin existencias, misiles derribados, objetivos cumplidos… llegan al bando correspondiente; el instructor puede inyectar eventos propios.",
               "<b>Videowall</b>: el mapa ocupa toda la pantalla con un HUD (turno, hora, reloj, estado de los bandos, marcador, últimas alertas). URL directa: <font face='Mono'>?modo=videowall&amp;escenario=ID&amp;vista=azul|rojo|completa</font>. También <font face='Mono'>?lat=&amp;lon=&amp;zoom=</font> abre el mapa sobre un lugar.",
               "<b>Gráficos tácticos</b>: líneas de fase, ejes de avance, zonas de reunión y puntos de control, compartidos con el bando (o con todos, si los traza el instructor).",
               "<b>Chat</b> del bando o «al mando», con latencia, jitter y pérdida simulados por el instructor.",
               "<b>Informe posterior al ejercicio (AAR)</b>: botón <b>Informe</b>: repetición turno a turno sobre el mapa (trayectorias, combates, novedades) y <b>replay animado</b> continuo con estelas, resumen por bando, marcador y objetivos, informe imprimible, CSV de combates y exportación JSON. Los alumnos lo ven al finalizar el escenario.",
               "<b>Línea de tiempo</b>: combustible y munición de cada unidad turno a turno, con caídas abruptas, niveles críticos y reabastecimientos cruzados con los combates."]),
          H2("12.1 Replay animado"),
          P("El botón <b>Replay</b> de la repetición abre un reproductor continuo para la sesión de análisis: recorre los turnos con las unidades "
            "moviéndose entre posiciones (con arranque y frenado suaves), destellos y líneas atacante → defensor en cada combate, las unidades "
            "destruidas que se desvanecen y las nuevas que se materializan. Un rótulo muestra el turno, la hora simulada, el clima, el marcador "
            "acumulado y las novedades del turno. Controles: reproducir y pausa, velocidad (0,5×, 1×, 2×, 4×), barra de progreso arrastrable, ir "
            "al inicio o al final y la casilla <b>Estela</b>, que deja el recorrido de cada unidad en el color de su bando. El instructor y el "
            "observador lo ven siempre; los alumnos, al finalizar el escenario.")]
    h += Img(img, "cap_replay.jpg", "Figura 12. Replay animado detenido a mitad del ejercicio: estelas, combate en curso y rótulo con hora, clima, marcador y novedades.")
    h += [H2("12.2 Rúbrica por bando, por repartición y por alumno"),
          P("<i>Informe → Rúbrica</i> resume la actuación de cada bando y de cada repartición responsable (A-2, A-3, A-3 D/A, A-4 y C-E): órdenes emitidas, resueltas y "
            "rechazadas con su motivo, turnos con órdenes frente a turnos pasivos, logística, pérdidas, objetivos y misiones, con <b>observaciones "
            "automáticas</b>. Como cada orden y misión registra <b>quién la emitió y en qué repartición</b> (la cola de órdenes lo muestra), la sección "
            "<b>Evaluación por alumno</b> hace lo mismo para cada usuario, y el botón <b>CSV por alumno</b> la descarga para la planilla de "
            "calificaciones. Las órdenes automáticas del motor no se atribuyen a nadie, y las anteriores a la versión 1.3 figuran como "
            "«sin autor registrado». La rúbrica también va en el informe imprimible y en las diapositivas.")]
    h += Img(img, "cap_rubrica.jpg", "Figura 13. Rúbrica del ejercicio con la evaluación por bando, por repartición y por alumno.")

    # ---- 13 limitaciones
    h += H1("13. Limitaciones conocidas")
    h += [Bul(["El modelo de combate es una abstracción didáctica; los valores del catálogo son ajustables.",
               "El terreno no distingue cultivos; las carreteras son las principales y secundarias, y sus puentes se deducen de dónde cruzan un río o el agua.",
               "El transporte logístico es terrestre (convoyes); los buques de desembarco y los helicópteros solo llevan tropas, no abastecimientos.",
               "La identidad nacional es solo un nombre: no se modela el orden de batalla real de los países vecinos.",
               "Las comunicaciones simuladas afectan al chat y pueden demorar órdenes, pero no a la niebla de guerra.",
               "El adversario automático da órdenes turno a turno: no planifica misiones aéreas de varios turnos ni lee el chat o los eventos inyectados.",
               "Un solo servidor por aula: el WebSocket y el temporizador viven en el proceso."]),
          H2("Hoja de ruta prevista"),
          Bul(["El TIEM ya está completo en el simulador (8.11 a 8.16); los próximos pasos son anexos del Plan de Operaciones "
               "(inteligencia, logística, comunicaciones, defensa aérea) y plantillas de ejercicios con su Problema Militar.",
               "Más plantillas de escenario por curso.", "Carreteras terciarias y puentes etiquetados de OpenStreetMap."])]

    # ---- 14 novedades
    h += H1("14. Novedades de las versiones 1.1 a 1.7")
    h += [P("Resumen de lo incorporado después de la primera edición del manual; cada punto está explicado en su capítulo."),
          Tbl(["Novedad", "Dónde", "Qué aporta"], [
              ["Meteorología por zonas", "Consola → Meteorología por zonas; capa Meteorología",
               "Frentes de nublado, lluvia o tormenta con radio, deriva y duración. El clima efectivo en cada punto rige detección, movimiento y ataques aéreos."],
              ["Mapa de toda América (y del mundo, opcional)", "Tarjeta Capas → botones de región; tools/preparar_terreno.py",
               "Regiones superpuestas: Venezuela en detalle (~300 m) sobre América entera (~1,2 km), ambas con foto satelital; el mundo o un recuadro a medida se generan con un comando."],
              ["Aeródromos de los países vecinos", "Capa Bases aéreas y aeródromos",
               "Bases y aeropuertos de Colombia, Brasil, Guyana y Trinidad dentro del mapa, con su plano real, colocables como base del ejercicio."],
              ["Aeródromos de toda América y catálogo de naciones", "Capa Bases aéreas y aeródromos; Consola → Identidad nacional",
               "Unos 1 260 aeropuertos y bases militares del continente (OurAirports), por niveles de zoom, con país y origen en su ventana; los 29 estados de América como identidad de un bando."],
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
              ["Autor de cada orden y rúbrica por alumno", "Cola de órdenes; Informe → Rúbrica → Evaluación por alumno; CSV por alumno",
               "Cada orden y misión registra quién la emitió y su puesto; la rúbrica evalúa a cada alumno (órdenes, rechazos, turnos activos y pasivos, misiones) con observaciones automáticas. Lo anterior a esta versión figura como «sin autor registrado»."],
              ["Replay animado del ejercicio", "Informe → Replay",
               "Animación continua de los turnos sobre el mapa: movimientos interpolados, destellos de combate, unidades que se desvanecen, estela por unidad, velocidad 0,5×–4×, barra arrastrable y rótulo con hora, clima, marcador y novedades."],
              ["Instalador de un clic", "instalar.cmd, iniciar.cmd, detener.cmd", "Instalación guiada, acceso directo en el Escritorio y arranque automático opcional."],
              ["Actualizador y paquete de datos", "actualizar.cmd; instalar.cmd -Datos; tools/empaquetar_datos.py",
               "Actualización con respaldo previo y migraciones automáticas; los datos de mapa (~550 MB) se distribuyen en un zip aparte del código."],
              ["Relieve y línea de vista; perfil de vuelo", "Ficha de las aeronaves; cobertura al seleccionar un sensor",
               "Las montañas y el horizonte ocultan a los radares; las aeronaves vuelan alto, medio o rasante, con sus ventajas y costos."],
              ["Plano real de los aeródromos de toda América", "Capa Plano de los aeródromos; tools/preparar_aerodromos.py",
               "Pistas, rodajes, plataformas y edificios de OpenStreetMap también en los aeródromos de los demás países, cargados solo al acercarse."],
              ["Carpeta portátil con SIETE.exe", "SIETE_portable_&lt;fecha&gt;.zip; tools/construir_ejecutable.py",
               "El simulador funciona en cualquier PC con Windows sin instalar Python: doble clic en SIETE.exe arranca el servidor del aula y abre el navegador."],
              ["Solicitud de cuentas y administrador inicial", "Pantalla de acceso → Solicitar una cuenta; Consola → Usuarios; menú del perfil",
               "Los alumnos piden su cuenta y el instructor la aprueba o rechaza; la cuenta admin trae una contraseña inicial que se cambia al primer acceso; contraseñas provisionales y cambio de contraseña para todos."],
              ["Valores de juego editables", "backend/data/ajustes_catalogo.json",
               "El instructor ajusta velocidades, alcances, efectividades y topes sin tocar el código (requiere reiniciar el servidor)."],
              ["Escenario del 3 de enero de 2026 (reconstrucción)", "Desde plantilla… → «3 de enero de 2026: Operación Resolución Absoluta»",
               "Reconstrucción con fuentes abiertas: 73 aeronaves de EE. UU. en 31 grupos, sus buques y las defensas venezolanas de Caracas, Miranda y La Guaira, con objetivos para ambos bandos."],
              ["Aeronaves de EE. UU., alerta temprana y cisternas", "Catálogo (capítulos 9.3 y 11)",
               "20 modelos nuevos con miniatura 3D; firma radar por modelo (los furtivos se detectan mucho más cerca); clases de alerta temprana (radar en vuelo) y avión cisterna (reabastece en vuelo)."],
              ["Fotos de referencia", "Ficha de la unidad; tools/fotos/fotos_referencia.py",
               "Fotos de Wikimedia Commons de aeronaves, drones y buques (venezolanos donde existen), con el mismo encuadre y fondo, y su crédito en la ficha."],
              ["Adversario automático", "Consola → Dirección del ejercicio",
               "El simulador conduce un bando con las mismas reglas que un alumno y solo con lo que ese bando ve: ataca, se reabastece, va a sus objetivos, protege sus aviones sin armas y lanza cazas. Un solo bando de alumnos puede entrenar sin contraparte. Tres niveles (prudente, normal, agresiva) y modo demostración (la IA juega los dos bandos)."],
              ["Biblioteca de escenarios contra la IA", "Desde plantilla… (etiqueta «Contra la IA»)",
               "Defensa aérea de la región central, interdicción en los llanos y defensa de la costa oriental, con el bando rojo conducido por el simulador."],
              ["Ciclo de día y noche", "Consola → Dirección del ejercicio; tarjeta Estado del escenario",
               "Cada turno es una hora: de noche la detección a simple vista baja a la mitad y la de cámaras térmicas al 80 %; el radar no cambia. La tarjeta Estado del escenario muestra la hora y el periodo y el mapa se oscurece."],
              ["Órdenes que no llegan a tiempo", "Consola → Comunicaciones simuladas",
               "Un porcentaje de las órdenes se demora y se cumple el turno siguiente (más dentro de una interferencia enemiga); el bando recibe el aviso."],
              ["Carreteras, puentes y rutas", "Capa de carreteras; orden Mover → Seguir carreteras",
               "Carreteras reales (OpenStreetMap y Natural Earth): las unidades terrestres van más rápido por ellas y cruzan ríos por sus puentes; el botón traza el camino más rápido."],
              ["Catálogo propio", "Consola → Catálogo propio",
               "El instructor define los tipos de unidad de la AMB (nombre, clase y valores de juego) y los usa al instante al agregar unidades."],
              ["Indicadores doctrinales y calificación", "Informe → Rúbrica; Comparar con otros ejercicios",
               "Reacción, conocimiento del enemigo, logística, coordinación, economía de fuerzas, objetivos e iniciativa, con nota de 1 a 20 y comparación entre ejercicios y por alumno."],
              ["Infraestructura no militar", "Capa Infraestructura; pestaña Situación; plantillas contra la IA",
               "Centrales, refinerías, centros de comunicaciones y puentes reales que se atacan o protegen y pesan en la operación: radares, combustible, órdenes y movilidad."],
              ["Personal", "Pestaña Situación; ficha de la unidad; Agregar unidad → Efectivos",
               "Dotación de cada unidad, efectivos actuales y bajas por rama."],
              ["Cuadro radar y aviso automático", "Pestaña Situación; alertas",
               "Lo que detecta cada sensor, con distancia y rumbo; los contactos nuevos se informan solos al bando y se pueden difundir a la red."],
              ["Porcentaje de objetivos y tiempo de recorrido", "Tarjeta Objetivos y puntaje; vista previa de Mover",
               "Objetivos cumplidos sobre asignados de cada bando; duración total, turnos y hora de llegada de una ruta."],
              ["Mapa ficticio: País Azul y País Rojo", "Capas → Teatro ficticio; Desde plantilla…; tools/generar_mapa_ficticio.py",
               "Un país inventado en dos repúblicas, con relieve, ríos, embalses, bosques, ciudades, carreteras, infraestructura y su ejercicio, para ejercitar sin ningún país real."],
              ["TIEM, etapa 1: reparticiones del Estado Mayor", "Usuarios; Mi repartición; engine/puestos.py",
               "Comandante, JEM, A-1, A-2, A-3, A-3 D/A, A-4 y C-E reemplazan a los puestos EM, A2, A3, A4 y A5 (8.11)."],
              ["TIEM, etapa 1: Problema Militar Operativo", "Pestaña TIEM; engine/pmo.py",
               "El PMO de cada bando, redactado por el instructor o generado a partir del escenario, con la misión en la forma tarea «a fin de» propósito (8.11)."],
              ["Defensa aérea: ZU-23-2, S-125 Pechora-2M y Buk-M2E", "Consola → Agregar (tipo); ficha de la batería",
               "Armas con alcance, techo y probabilidad; radar de vigilancia y de tiro; reacción, canales, recarga con "
               "inoperatividad, despliegue y vehículos; elección del arma; tiro según el rumbo y el tiempo en alcance; "
               "interferencia y maniobra evasiva (8.17)."],
              ["Águila animada en la pantalla de acceso", "Pantalla de acceso; js/aguila.js; tools/manual/aguila_video.py",
               "Al ingresar, el águila posada abre las alas, bate dos veces y vuela hacia la pantalla (video WebM con transparencia, "
               "cargado en memoria); luego aparece el simulador. Ningún formulario se envía sin JavaScript (CSP form-action 'none')."],
              ["TIEM, etapa 6: evaluación y exportación", "Pestaña TIEM → Evaluación y legajo; Informe → Rúbrica",
               "Evaluación del trabajo de Estado Mayor con nota de 1 a 20 y legajo de documentos en Word o PDF (8.16)."],
              ["TIEM, etapa 5: supervisión de la ejecución", "Pestaña TIEM → Supervisión de la ejecución; engine/supervision.py",
               "Parte del turno, cuadro de diferencias con el plan, registro de causas y acciones correctivas y órdenes fragmentarias (8.15)."],
              ["TIEM, etapa 4: decisión, Plan de Operaciones y órdenes", "Pestaña TIEM → Paso 3 y Fase II; Orden de Operaciones",
               "Decisión del Comandante, análisis previo y Plan de Operaciones cuyas tareas se emiten como órdenes del simulador (8.14)."],
              ["TIEM, etapa 3: apreciaciones de EM y juego de guerra", "Pestaña TIEM → Paso 2; Juego de guerra; app/ensayos.py",
               "Las seis apreciaciones de Estado Mayor con la confrontación de las F/A y ensayos de F/A contra la IA en una copia del ejercicio (8.13)."],
              ["TIEM, etapa 2: apreciación inicial", "Pestaña TIEM → Fase I · Paso 1; engine/tiem.py",
               "Análisis de la misión, concepto del comandante, guía de planeamiento y formas de acción con APA; PRC calculado, revisión del instructor y Word adjunto (8.12)."],
              ["TIEM, etapa 1: calendario, conducción y cadena de objetivos", "Consola → Calendario; Dirección del ejercicio; Objetivos",
               "Día D, hora H y fases; cada bando lo conduce un grupo de alumnos, el instructor o la IA; objetivos ulterior, asignados y materiales con efecto, indicador, plazo y «neutralizar» (8.11)."],
              ["Satélite de Venezuela a zoom 13", "Capa Satélite; tools/preparar_satelite.py",
               "El doble de nitidez al acercar el mapa (unos 19 m por píxel): calles, pistas y plataformas se distinguen mejor."],
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
        ["Informe", "Botón Informe; Línea de tiempo y Replay animado dentro de la repetición"],
        ["Rúbrica y CSV por alumno", "Informe → Rúbrica → CSV por alumno"],
        ["Actualizar el simulador", "Doble clic en actualizar.cmd (respalda la base antes)"],
        ["Respaldo manual", "backend: venv\\Scripts\\python -m app.respaldo"],
        ["Primer acceso", "Usuario admin, contraseña inicial siete1234 (se cambia al entrar)"],
        ["Pedir una cuenta", "Pantalla de acceso → Solicitar una cuenta; el instructor la aprueba en Consola → Usuarios"],
        ["Cambiar la propia contraseña", "Menú del perfil → Cambiar contraseña"],
        ["Recuperar la cuenta admin", "backend: venv\\Scripts\\python -m app.restablecer_admin"],
        ["Crear usuario", "Consola → Usuarios, o backend: venv\\Scripts\\python -m app.crear_usuario &lt;nombre&gt; --rol azul|rojo|observador|instructor [--puesto comandante|jem|a1|a2|a3|a3da|a4|ce]"],
        ["Problema Militar y calendario", "Pestaña TIEM → Crear la situación automáticamente / Redactar; Consola → Calendario de la operación"],
        ["Documentos de la apreciación", "Pestaña TIEM → Fase I · Paso 1 → Abrir; Presentar al instructor / Aprobar / Devolver"],
        ["Conducir un bando como instructor", "Consola → Dirección del ejercicio → Conduce el bando: El instructor; cabecera → Conducir Rojo/Azul"],
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
          P(f"Simulador concebido, diseñado y desarrollado por el <b>{CREADOR}</b>, {UNIDAD}, Aviación Militar Bolivariana. "
            "Datos y componentes de terceros:"),
          P("Satélite: EOxCloudless (EOX IT Services GmbH), Copernicus Sentinel-2 (ESA), CC BY 4.0. Relieve: AWS Terrain Tiles (SRTM/GMTED/ETOPO1 "
            "vía Mapzen). Cobertura terrestre: ESA WorldCover 2021, CC BY 4.0. Vectores: Natural Earth (dominio público). Planos de aeródromos: "
            "© colaboradores de OpenStreetMap, ODbL 1.0. Bases aéreas: Wikipedia (CC BY-SA) y OurAirports (dominio público). Fotos: F-16 venezolano "
            "(Veronidae, CC BY-SA 3.0) y Sukhoi Su-30MK2 de Venezuela (Carlos E. Perez S.L, CC BY-SA 4.0), Wikimedia Commons. Imágenes 3D: modelos "
            "F16A (amf1re) y Su-33 (helijah) de Sketchfab, licencia Sketchfab Standard. Miniaturas 3D e ilustraciones de los modelos genéricos: "
            "propias del proyecto, CC0. Librerías: Leaflet (BSD-2), Leaflet.draw (MIT), milsymbol (MIT), FastAPI, SQLAlchemy, Alembic, reportlab."),
          P("Los créditos deben conservarse si el proyecto se redistribuye. Las cifras y reglas del simulador son parámetros de juego y no "
            "representan datos técnicos oficiales de ningún sistema real.")]

    h += seccion_creditos("Créditos")
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
