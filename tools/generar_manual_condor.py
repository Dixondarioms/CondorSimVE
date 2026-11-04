"""Genera el manual de usuario del Cóndor en PDF (docs/Manual_Usuario_Condor.pdf): guía, con capturas, de cada parte de
la interfaz para el director del ejercicio y los alumnos de cada repartición.

Las capturas salen de tools/manual/capturas_condor.py (interfaz real sobre una copia de la base). El aspecto (fuentes,
colores, tablas, créditos) es el de los manuales del SIETE (tools/generar_manual.py), del que se reusan las piezas. El
catálogo del anexo se lee del código (backend/app/engine/catalogo.py), así que siempre coincide con el simulador.

    backend\\venv\\Scripts\\python tools/generar_manual_condor.py
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_manual import (ANCHO_TEXTO, AZUL, CLARO, LINEA, LOGO_DIDA, RAIZ, UNIDAD, S, Bul, H1, H2, Manual, Nota, Num, P,  # noqa: E402
                            Tbl, credito_portada)
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle  # noqa: E402
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from app.engine import catalogo  # noqa: E402  (generar_manual ya agrega backend/ a la ruta)
from crear_ejercicio_tutorial import PRACTICAS as PRACTICAS_TUTORIAL  # noqa: E402  (la misma lista que el ejercicio)

from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402

# los botones del Cóndor usan simbolos que Arial no tiene (◀ ▶ ✕ ■): van con la fuente de simbolos de Windows
pdfmetrics.registerFont(TTFont("Simbolos", r"C:\Windows\Fonts\seguisym.ttf"))
SIMBOLOS = "◀▶✕■"

IMG = RAIZ / "tools" / "manual" / "salida" / "condor"
FIG = [0]
S["h2"].keepWithNext = S["h3"].keepWithNext = 1
VERSION = "1.0"


def figura(nombre: str, pie: str, ancho=ANCHO_TEXTO, alto_max=21 * cm, celda=False) -> list:
    """Captura con su pie numerado (a lo ancho o al ancho indicado, sin pasar de alto_max). `celda`: para ponerla en una
    tabla junto al texto (reportlab no sabe partir un KeepTogether dentro de una celda)."""
    ruta = IMG / f"{nombre}.jpg"
    if not ruta.exists():
        return [Paragraph(f"[captura no disponible: {nombre}]", S["cap"])]
    FIG[0] += 1
    im = Image(str(ruta))
    k = min(ancho / im.imageWidth, alto_max / im.imageHeight)
    im.drawWidth, im.drawHeight = im.imageWidth * k, im.imageHeight * k
    pie = Paragraph(f"Figura {FIG[0]}. {pie}", S["cap"])
    return [im, pie] if celda else [KeepTogether([im, pie])]


def titulos_con_su_figura(h: list) -> list:
    """Un subtitulo seguido de una figura o una tabla va en el mismo bloque (para que no quede solo al pie de pagina)."""
    salida = []
    for f in h:
        while (salida and isinstance(f, (KeepTogether, Table)) and isinstance(salida[-1], Paragraph)
               and salida[-1].style.name in ("h1", "h2", "h3")):
            # sin anidar KeepTogether: reportlab calcula mal el alto de los anidados y dejaba el titulo solo en su pagina
            f = KeepTogether([salida.pop()] + (list(f._content) if isinstance(f, KeepTogether) else [f]))
        salida.append(f)
    return salida


def B(t: str) -> str:
    return f"<b>{t}</b>"


def tabla_catalogo() -> list:
    """Anexo: todos los modelos del catalogo, agrupados por clase de unidad."""
    por_clase: dict[str, list] = {}
    for m in catalogo.MODELOS.values():
        por_clase.setdefault(m.clase, []).append(m)
    h = []
    for clase_id, modelos in sorted(por_clase.items(), key=lambda kv: catalogo.CLASES[kv[0]].nombre if kv[0] in catalogo.CLASES else kv[0]):
        nombre = catalogo.CLASES[clase_id].nombre if clase_id in catalogo.CLASES else clase_id
        filas = [[m.nombre, m.pais or "-", m.funcion or "-"] for m in sorted(modelos, key=lambda m: m.nombre)]
        h += [Paragraph(f"{nombre} ({len(modelos)})", S["h3"]),
              Tbl(["Modelo", "País", "Función"], filas, [6.2 * cm, 3.4 * cm, ANCHO_TEXTO - 9.6 * cm], tam=8.2)]
    return h


def creditos() -> list:
    h = H1("Créditos")
    if LOGO_DIDA.exists():
        im = Image(str(LOGO_DIDA))
        im.drawWidth, im.drawHeight = 7.0 * cm, 7.0 * cm * im.imageHeight / im.imageWidth
        h += [im, Spacer(1, 10)]
    centrado = ParagraphStyle("credc", parent=S["p"], alignment=TA_CENTER, fontSize=11, leading=16)
    h += [Paragraph(f"El simulador Cóndor fue concebido, diseñado y desarrollado en la <b>{UNIDAD}</b> de la Aviación "
                    "Militar Bolivariana, a partir de la experiencia del S.I.E.T.E. y de las recomendaciones del personal del "
                    "CODAI, de logística de la AMB, de pilotos instructores y de usuarios de simuladores de juegos de guerra.",
                    centrado), Spacer(1, 6), Paragraph("<i>«El infinito es el límite»</i>", centrado), Spacer(1, 14)]
    filas = [["Unidad", UNIDAD], ["Componente", "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana"],
             ["Imágenes", "Fotos de referencia de Wikimedia Commons con licencias libres (autor y licencia en cada ficha); "
                          "satélite Sentinel-2 cloudless (EOX, CC BY 4.0); relieve SRTM/GMTED; cobertura ESA WorldCover; "
                          "vectores Natural Earth; aeródromos y carreteras © colaboradores de OpenStreetMap (ODbL)."]]
    t = Table([[Paragraph(f"<b>{a}</b>", S["celda"]), Paragraph(b, S["celda"])] for a, b in filas],
              colWidths=[3.6 * cm, ANCHO_TEXTO - 3.6 * cm], hAlign="CENTER")
    t.setStyle(TableStyle([("ROWBACKGROUNDS", (0, 0), (-1, -1), [CLARO, colors.white]), ("GRID", (0, 0), (-1, -1), 0.4, LINEA),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return h + [t]


def construir(salida: Path) -> None:
    doc = Manual(str(salida), titulo="Cóndor · Manual de usuario")
    doc.author = UNIDAD
    hoy = date.today()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha = f"{meses[hoy.month - 1].capitalize()} de {hoy.year}"
    ancho_medio = ANCHO_TEXTO * 0.62
    h = []

    # ---------------------------------------------------------------- portada
    h += [Spacer(1, 0.6 * cm)]
    logo = RAIZ / "frontend" / "static" / "img" / "condor_posado.png"
    if logo.exists():
        im = Image(str(logo))
        im.drawWidth, im.drawHeight = 7.5 * cm, 7.5 * cm * im.imageHeight / im.imageWidth
        h += [im, Spacer(1, 10)]
    h += [Paragraph("CÓNDOR", S["titulo"]), Spacer(1, 6),
          Paragraph("Simulador de entrenamiento táctico y estratégico en tiempo real", S["subtitulo"]), Spacer(1, 24),
          Paragraph("MANUAL DE USUARIO", ParagraphStyle("mu", parent=S["subtitulo"], fontName="Texto-B", fontSize=20, textColor=AZUL)),
          Spacer(1, 8), Paragraph("Guía para el director del ejercicio y los alumnos de cada repartición", S["subtitulo"]),
          Spacer(1, 24)]
    h += credito_portada()
    h += [Spacer(1, 10), Paragraph(f"{fecha} · versión {VERSION}", S["subtitulo"]), PageBreak()]

    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    h += [Paragraph("Contenido", ParagraphStyle("h1toc", parent=S["h1"])), toc]

    # ---------------------------------------------------------------- 1 introduccion
    h += H1("1. Introducción")
    h += [H2("1.1 Qué es el Cóndor"),
          P("El Cóndor es un simulador de entrenamiento táctico y estratégico <b>en tiempo real</b>: las unidades se mueven, "
            "detectan y combaten mientras corre el reloj, y las órdenes se cumplen en el acto, sin esperar al fin de un turno. "
            "Se enfrentan dos bandos, <b>Azul</b> y <b>Rojo</b>; cada bando es un Estado Mayor en el que cada persona entra con "
            "la cuenta de su repartición y ordena solo las unidades que le corresponden."),
          P("El simulador trae un catálogo de cerca de 200 modelos reales (aviones, helicópteros, drones, misiles, vehículos, "
            "defensa antiaérea, radares y buques de muchos ejércitos), cada uno con su ficha y foto de referencia, y mapas "
            "propios que funcionan sin internet: Venezuela con detalle, el continente americano, el mundo entero y un teatro "
            "ficticio para ejercicios sin geografía real."),
          H2("1.2 Quién hace qué"),
          Tbl(["Rol", "Qué hace", "Capítulos"], [
              ["Director del ejercicio", "Prepara el escenario, maneja el reloj, ve a los dos bandos, inyecta eventos y administra las cuentas.", "2, 3, 13"],
              ["Comandante y JEM", "Conducen todo su bando: reúnen las funciones de todas las reparticiones y fijan la doctrina.", "2 a 12"],
              ["Reparticiones (A-1 a C-E)", "Cada una ordena las unidades de su función (ver 2.8).", "2 a 12"],
              ["Observador", "Sigue el ejercicio sin dar órdenes.", "2, 10, 12"],
          ], [4.2 * cm, ANCHO_TEXTO - 6.0 * cm, 1.8 * cm]),
          H2("1.3 Qué se necesita"),
          Bul(["<b>Una PC servidor</b> con el Cóndor (la versión portable se abre con el acceso directo <b>Condor</b>). Su "
               "ventana negra es el servidor: debe quedar abierta mientras dure el ejercicio.",
               "<b>Una PC por puesto</b> con Chrome o Edge, en la misma red que el servidor. No hace falta instalar nada.",
               "La <b>dirección</b> del servidor, que da el director: es la de su PC y termina en <b>:8001</b> "
               "(por ejemplo, <font face='Mono'>http://192.168.1.10:8001</font>).",
               "Una <b>cuenta</b> por puesto (usuario y contraseña), que entrega el director."]),
          Nota("Este manual se lee junto al simulador. Dentro del Cóndor, el botón <b>Ayuda</b> (o la tecla <b>F1</b>) responde "
               "preguntas sobre cada tema y ofrece un recorrido guiado por la pantalla.")]

    # ---------------------------------------------------------------- 2 primeros pasos
    h += H1("2. Primeros pasos")
    h += [H2("2.1 Entrar y elegir el ejercicio")]
    h += figura("acceso", "Pantalla de acceso.", ancho=6.5 * cm)
    h += [Num(["Abra Chrome o Edge y escriba la dirección que le dio el director (termina en <b>:8001</b>).",
               "Escriba su <b>usuario</b> y su <b>contraseña</b> tal como figuran en su tarjeta, respetando mayúsculas y guiones, "
               "y pulse <b>Ingresar</b>.",
               "Arriba, en la lista <b>Escenario</b>, elija el ejercicio (una cuenta puede tener más de uno)."]),
          P("Si no tiene cuenta, <b>Solicitar una cuenta</b> envía el pedido al director, que lo aprueba. Para cambiar la "
            "contraseña o salir, use el botón del usuario (arriba a la derecha) → <b>Cambiar contraseña</b> o <b>Cerrar sesión</b>. "
            "Use una sola cuenta por vez en cada navegador.")]
    h += [H2("2.2 Las partes de la pantalla")]
    h += figura("pantalla", "La pantalla del Cóndor con una unidad seleccionada. Los números se explican en la tabla siguiente.")
    h += [Tbl(["N.º", "Parte", "Qué contiene"], [
        ["1", "Cabecera", "Escenario, botones del director, conexión, reloj de tiempo real, Videowall, Ayuda, Informe y usuario."],
        ["2", "Panel izquierdo", "Pestañas FUERZAS (orden de batalla, doctrina, aviación, misiones, nueva orden y cola), SITUACIÓN, "
                                 "TIEM y, para el director, CONSOLA."],
        ["3", "Mapa", "Unidades, rutas, zonas, contactos, gráficos tácticos y herramientas (regla y convertidor)."],
        ["4", "Panel derecho", "Estado del escenario (hora, clima, reloj), objetivos y puntaje, capas, comunicaciones y alertas."],
        ["5", "Unidad seleccionada", "Foto, misión, estado, capacidades y armamento de la unidad elegida."],
        ["6", "Reloj del ejercicio", "Hora, velocidad, botones del reloj (director) y quién conduce cada bando."],
    ], [1.2 * cm, 3.4 * cm, ANCHO_TEXTO - 4.6 * cm])]
    h += [H2("2.3 Paneles que se esconden"),
          P("Las pestañitas <b><font face='Simbolos'>◀</font></b> y <b><font face='Simbolos'>▶</font></b> en los bordes del mapa esconden el panel izquierdo y las tarjetas de la derecha "
            "para ver el mapa más grande; con otro clic vuelven a aparecer. El panel de la unidad seleccionada se reduce con "
            "<b>▼ Esconder</b> y se cierra con <b><font face='Simbolos'>✕</font></b>. El Cóndor recuerda en cada PC qué paneles dejó escondidos.")]
    h += figura("paneles_escondidos", "Los paneles laterales escondidos: el mapa ocupa casi toda la pantalla.")
    h += [H2("2.4 La cabecera")]
    h += figura("cabecera", "Cabecera.")
    h += [Tbl(["Control", "Para qué sirve"], [
        ["Escenario", "Elige el ejercicio. «archivados» muestra también los ejercicios terminados."],
        ["Nuevo · Desde plantilla… · Guardar como plantilla…", "Solo el director: crear ejercicios y reutilizarlos (capítulo 13)."],
        ["Punto de conexión", "Verde: conectado. Rojo: se perdió la conexión (recargue con F5)."],
        ["Tiempo real", "Estado del reloj: DETENIDO o EN MARCHA."],
        ["Videowall", "Mapa a pantalla completa para un proyector (10.5)."],
        ["Ayuda", "Preguntas y respuestas sobre el simulador y recorrido guiado (2.9). También con F1."],
        ["Informe", "Resumen, línea de tiempo, repetición y rúbrica (capítulo 12)."],
        ["Usuario", "Cambiar contraseña o cerrar sesión."],
    ], [5.4 * cm, ANCHO_TEXTO - 5.4 * cm])]
    h += [H2("2.5 El orden de batalla")]
    h += [Table([[figura("orden_batalla", "Orden de batalla (pestaña FUERZAS).", ancho=6.3 * cm, alto_max=14 * cm, celda=True),
                  [P("En la pestaña <b>FUERZAS</b>, el <b>orden de batalla</b> lista las unidades de su bando (el director ve los "
                     "dos), agrupadas por tipo: infantería, artillería, aviación, bases y logística, infraestructura y buques."),
                   P("Cada fila muestra el nombre, el símbolo y el estado (Operativa, En base · lista, En vuelo, Dañada…). Con un "
                     "clic se elige la unidad: el mapa la marca y abajo aparecen sus datos. El buscador de arriba filtra por "
                     "nombre, clase o modelo."),
                   P("Con <b>Ctrl+clic</b> se suman varias unidades propias para darles la misma orden (4.6).")]]],
                colWidths=[6.6 * cm, ANCHO_TEXTO - 6.6 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("2.6 La unidad seleccionada")]
    h += figura("panel_unidad", "Datos de una aeronave seleccionada: foto, misión, estado, capacidades y armamento.")
    h += [P("Al elegir una unidad, en la parte inferior de la pantalla aparecen sus datos en cuatro columnas:"),
          Bul(["<b>Foto de referencia</b> del modelo, con su fabricante, país, autor y licencia.",
               "<b>Nombre, bando y estado</b>; la <b>misión</b> en curso (la orden que cumple o lo que hace por su cuenta: «En tierra, "
               "a la espera de órdenes», «Sin orden: mantiene su posición»…) y las barras de <b>fuerza</b>, <b>combustible</b> y munición.",
               "<b>Capacidades</b>: clase, terreno donde está, velocidad, alcance de armas, detección, autonomía, personal y movilidad.",
               "<b>Armamento y notas</b>: lo que lleva y, según la unidad, controles propios (perfil de vuelo, armas de la defensa "
               "antiaérea, emisión del radar)."]),
          P("De una unidad enemiga solo se ve lo que su bando sabe de ella (capítulo 7).")]
    h += figura("panel_unidad_da", "Datos de un sistema de defensa antiaérea: armas, alcances y probabilidad de impacto.")
    h += [H2("2.7 El catálogo de modelos"),
          P("Cada unidad puede ser un <b>modelo real</b> con su ficha: cazas (F-16, Su-30, Rafale, Gripen, Kfir…), ataque "
            "(A-29 Super Tucano, AT-27 Tucano, K-8W, Su-25…), helicópteros, drones, misiles, tanques, artillería, defensa "
            "antiaérea, radares y buques. La ficha aparece al pasar el cursor sobre una unidad en el mapa y en la unidad "
            "seleccionada. La lista completa está en el <b>Anexo A</b>."),
          Nota("Las cifras del catálogo son didácticas: sirven para comparar plataformas entre sí, no son datos oficiales.")]
    h += [H2("2.8 Qué ordena cada repartición"),
          Tbl(["Repartición", "Qué conduce"], [
              ["Comandante y JEM", "Todo: reúnen las funciones de todas las reparticiones y fijan la doctrina del bando."],
              ["A-1 Personal", "Sigue efectivos, bajas y moral. No ordena unidades."],
              ["A-2 Inteligencia", "Sigue al enemigo y conduce el reconocimiento (unidades y drones de reconocimiento)."],
              ["A-3 Operaciones", "La maniobra: despegues, caza, ataque, helicópteros, drones armados, cisternas, fuerzas de superficie "
                                  "y lanzadores de misiles."],
              ["A-3 D/A Defensa Aérea", "Radares, antiaérea, alerta temprana y la caza de intercepción con sus despegues."],
              ["A-4 Logística", "Convoyes, depósitos e ingenieros (puentes y vados)."],
              ["C-E Comunicaciones y Electrónica", "Guerra electrónica: escucha e interferencia desde tierra y aviones de guerra electrónica."],
          ], [4.6 * cm, ANCHO_TEXTO - 4.6 * cm]),
          P("Si una orden «corresponde a otra repartición», pídasela a quien la conduce, al Comandante o al JEM.")]
    h += [H2("2.9 La ayuda y el recorrido guiado")]
    h += figura("ayuda", "Ventana de ayuda: se escribe la pregunta y aparecen los temas que la responden.")
    h += [P("El botón <b>Ayuda</b> (o <b>F1</b>) abre la ayuda del Cóndor. Escriba la pregunta con sus palabras («cómo despego "
            "un avión», «por qué no veo al enemigo») y elija el tema; a la izquierda están todos los temas por sección. "
            "<b>Recorrido guiado paso a paso</b> señala cada parte de la pantalla y explica para qué sirve: las tres pestañas "
            "(y la CONSOLA del director), la aviación con su carga de armamento, las órdenes de aviación (Patrullar, "
            "Interceptar, Rumbo) y las navales (Torpedo, Sonoboyas, Sonar de inmersión, Minar, Barrer minas, Lanzar misiles), "
            "las áreas y zonas, el daño por sistemas, las comunicaciones, las alertas y el informe. Los pasos de lo que su "
            "cuenta no ve se saltan solos.")]
    h += figura("recorrido_naval", "Recorrido guiado: el paso de las órdenes navales y de los misiles.")
    h += [H2("2.10 Practicar solo: el Tutorial del Cóndor"),
          P("El ejercicio <b>Tutorial del Cóndor</b> enseña todo el simulador a <b>una sola persona</b>: el alumno conduce el "
            "Azul y el adversario automático el Rojo, sobre el mapa ficticio (País Azul y País Rojo). El director lo crea desde "
            "CONSOLA → <b>Desde plantilla…</b>, marca la cuenta del alumno en <b>Usuarios con acceso</b> y pone el reloj en "
            "marcha (10×; 1× para ir con calma). Para que el alumno no pierda todo antes de aprender, el adversario es "
            "«prudente», el Rojo no tiene aviación propia y las armas azules contra aeronaves empiezan restringidas (hay "
            "vuelos civiles).")]
    h += figura("tutorial", "Tutorial del Cóndor: el Azul junto a Capital Azul, con su fragata, submarino y cazaminas en el "
                            "mar, el Área de patrulla Norte, el Área de búsqueda Oeste y la zona de no vuelo ya dibujadas.")
    h += [P("Los <b>eventos automáticos</b> hacen de instructor: a cada hora le mandan al alumno, por <b>Comunicaciones</b> y "
            "<b>Alertas</b>, la práctica que sigue (08:00 tierra y aire, 09:30 antisubmarina, 10:30 minas, 11:30 salva de "
            "misiles, 12:00 ataque balístico rojo, 14:00 cierre) y, según lo que hace, lo felicitan, le dan puntos o le "
            "inyectan una situación: un dron enemigo cuando su patrulla llega al área, refuerzos rojos cuando cae la brigada "
            "blindada roja. Las prácticas, en orden:"),
          Num(PRACTICAS_TUTORIAL)]
    h += figura("recorrido_practica", "El último paso del recorrido guiado: la práctica en el Tutorial del Cóndor.",
                ancho=9 * cm)

    # ---------------------------------------------------------------- 3 reloj
    h += H1("3. El reloj y las alertas")
    h += [H2("3.1 El reloj: tiempo real y velocidades")]
    h += figura("reloj", "Reloj del ejercicio detenido, con los controles del director.")
    h += [P("El ejercicio corre en tiempo simulado. La velocidad puede ser <b>1×</b> (igual que la realidad), <b>10×</b> o "
            "<b>60×</b> (un minuto simulado por segundo). El reloj lo ponen en marcha y lo detienen el director (y, en el ensayo "
            "de una forma de acción, el Comandante y el JEM); <b>+1 h</b> adelanta una hora de una vez, como si hubiera corrido."),
          P("Arriba se ven la <b>hora simulada</b> y el <b>calendario</b> de la operación (día D, hora H, fase). Con el reloj "
            "detenido se pueden dar órdenes: se cumplen al ponerlo en marcha.")]
    h += figura("reloj_en_marcha", "Reloj en marcha a 60×: el botón cambia a DETENER EL RELOJ.")
    h += [H2("3.2 Alertas y pausa automática"),
          P("Las <b>alertas</b> avisan al instante lo importante para su bando: contacto nuevo, ataque a una unidad propia, "
            "unidad perdida, combustible crítico y misión terminada. Aparecen como aviso sobre el mapa y quedan en la tarjeta "
            "<b>Alertas</b> (derecha); con un clic en el lugar, el mapa va hasta allí.")]
    h += figura("alertas", "Tarjeta de alertas.", ancho=7 * cm)
    h += [P("El director elige en CONSOLA → <b>Reloj y configuración</b> qué causas <b>detienen el reloj solas</b>. Cuando "
            "pasa, arriba aparece la franja roja <b>PAUSA AUTOMÁTICA</b> con el motivo, <b>Ver en el mapa</b> y, para el "
            "director, <b>Reanudar</b>.")]

    # ---------------------------------------------------------------- 4 ordenes
    h += H1("4. Órdenes")
    h += [H2("4.1 Cómo dar una orden")]
    h += [Table([[figura("orden_nueva", "Panel Nueva orden.", ancho=6.3 * cm, alto_max=12 * cm, celda=True),
                  [Num(["Elija la unidad en el <b>orden de batalla</b> o con un clic en el mapa.",
                        "En <b>Nueva orden</b>, elija el tipo (Mover, Atacar, Apoyar…). Solo aparecen los que esa unidad puede cumplir.",
                        "Complete lo que pide: los puntos de la ruta (clic en el mapa), el blanco o el lugar. <b>Seguir carreteras</b> "
                        "ajusta la ruta a las vías; <b>Limpiar waypoints</b> la borra.",
                        "Pulse <b>Emitir orden</b>. La unidad empieza en el acto."]),
                   P("Una orden nueva <b>reemplaza</b> a la que estaba cumpliendo: una aeronave en vuelo se desvía al momento.")]]],
                colWidths=[6.6 * cm, ANCHO_TEXTO - 6.6 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += figura("orden_ruta", "Ruta marcada en el mapa antes de emitir la orden.")
    h += [H2("4.2 Los tipos de orden"),
          Tbl(["Orden", "Qué hace"], [
              ["Mover", "Va por los puntos marcados (por carretera cuando conviene)."],
              ["Atacar", "Ataca a un enemigo detectado; si hace falta, se acerca hasta tenerlo a su alcance."],
              ["Apoyar", "Acompaña y apoya con fuego a otra unidad propia."],
              ["Construir", "Ingenieros: puente o vado sobre un río."],
              ["Patrullar", "Aeronaves: orbitan sobre una zona e interceptan lo que entre."],
              ["Aterrizar", "Aeronaves en vuelo: vuelven a una base."],
              ["Rumbo", "Aeronaves en vuelo: viran unos grados a un lado o toman un rumbo y lo mantienen (5.3)."],
              ["Interceptar", "Aeronaves y buques: salen al encuentro de una aeronave o un buque enemigo (5.4)."],
              ["Torpedo, Sonoboyas, Sonar", "Guerra antisubmarina (6.6)."],
              ["Minar, Barrer minas", "Minas navales (6.5)."],
              ["Interferir", "Guerra electrónica: degrada al enemigo en una zona."],
              ["Lanzar misiles", "Buques y baterías con misiles de crucero; lanzadores balísticos (6.4)."],
              ["Embarcar / Desembarcar", "Tropas a bordo de un buque de desembarco o un helicóptero de transporte."],
          ], [4.2 * cm, ANCHO_TEXTO - 4.2 * cm])]
    h += [H2("4.3 La cola de órdenes")]
    h += figura("cola", "Cola de órdenes con una orden en curso.", ancho=7.5 * cm)
    h += [P("La <b>Cola de órdenes</b> muestra las órdenes del bando, quién las dio, a qué hora y su estado (pendiente, en "
            "curso, cumplida). El botón <b><font face='Simbolos'>■</font></b> detiene una orden: la unidad se queda donde está.")]
    h += [H2("4.4 Mover: terreno, ríos y combustible"),
          P("La velocidad depende del tipo de unidad, del <b>terreno</b> y del <b>clima</b>. Las unidades de tierra aprovechan "
            "las carreteras. Los <b>vehículos pesados solo cruzan los ríos por un puente o un vado</b> (obra de ingenieros); si no "
            "hay paso, la unidad busca otro camino y, si no lo encuentra, se detiene y avisa. Moverse gasta combustible: sin "
            "combustible la unidad no avanza hasta que la reabastezcan (capítulo 8)."),
          H2("4.5 Atacar y el combate"),
          P("Solo se puede atacar a un enemigo <b>detectado</b> por su bando. La unidad se acerca hasta tenerlo a su alcance y "
            "combate mientras dure la orden: el daño se reparte poco a poco y depende de las armas, la defensa, el terreno, el "
            "clima y el azar. Cada ataque gasta munición; una unidad con poca fuerza queda casi sin capacidad de combate. Según "
            "la <b>doctrina</b>, las unidades también pueden tirar solas contra lo que tengan a su alcance (6.1)."),
          H2("4.6 Varias unidades a la vez"),
          P("Con <b>Ctrl+clic</b> en el orden de batalla o en el mapa se suman varias unidades propias: la orden va a todas. Con "
            "<b>formación</b>, cada una conserva su lugar respecto de las demás durante la marcha.")]

    # ---------------------------------------------------------------- 5 aviacion
    h += H1("5. Aviación")
    h += [H2("5.1 Despegar aviones y drones")]
    h += figura("aviacion", "Panel Aviación (pestaña FUERZAS).", ancho=8 * cm)
    h += [Num(["En FUERZAS, panel <b>Aviación</b>, pulse <b>Enviar aeronaves o drones…</b>.",
               "Busque el modelo por nombre, país o fabricante, o filtre por tipo (caza, ataque, dron, guerra electrónica…). Cada "
               "tarjeta muestra la foto y los datos principales del modelo.",
               "Elija la <b>base de origen</b> y cuántas <b>aeronaves</b> forman el grupo; si quiere, un indicativo (ej. «Halcón 1»).",
               "Pulse <b>Enviar a despegar</b>. El grupo despega en el acto y espera órdenes en el aire."])]
    h += figura("despegue", "Ventana para despegar: búsqueda «Tucano» con el AT-27 y el A-29.")
    h += [P("Los despegues los ordenan A-3 y A-3 D/A (y el Comandante o el JEM). Cada bando tiene un <b>tope</b> de aeronaves y "
            "de drones, que muestra el panel. Una aeronave que acaba de aterrizar necesita tiempo para reabastecer y rearmar "
            "antes de volver a salir.")]
    h += [P("<b>Carga de armamento.</b> En la misma ventana se elige la carga según el modelo: aire-aire, ataque, antibuque, "
            "SEAD (antirradiación) o reconocimiento, cada una con una cantidad real de misiles y bombas por aeronave. También se "
            "elige en el planificador de misiones y, para una aeronave en tierra, en la Nueva orden. Cada pasada gasta armas "
            "reales (un misil por aeronave, o la mitad de las bombas) y se tira con el arma que sirve contra ese blanco y desde "
            "su alcance; el daño sale de la misma tabla de combate. Las armas salen de las <b>existencias</b> de la base o del "
            "pañol del portaaviones, que el director puede cambiar en el panel de abajo.")]
    h += figura("carga_panel", "Panel de abajo de un grupo con su carga: cada arma con su alcance, su probabilidad de impacto y "
                "lo que le queda.")
    h += [H2("5.2 Patrullar, aterrizar y el combustible"),
          Bul(["<b>Patrullar</b>: la aeronave vuela a la zona, orbita (gasta cerca de 8 % de combustible por hora) e intercepta a "
               "los aviones enemigos que detecte a su alcance.",
               "<b>Aterrizar</b>: vuelve a la base elegida. En tierra tarda unas <b>2 horas</b> en reabastecer y rearmar. Cada base "
               "tiene un número de plazas.",
               "Con poco combustible (por defecto 25 %) o sin armamento, la aeronave <b>regresa sola</b> a la base más cercana; "
               "esos valores se cambian en la doctrina (6.1)."])]
    h += [H2("5.3 Desviar una aeronave: waypoints o rumbo"),
          P("Una orden nueva reemplaza en el acto a la que cumplía la aeronave. Hay dos formas de desviarla:"),
          Bul(["<b>Mover</b> con waypoints: clic en el mapa en cada punto de la nueva ruta; la aeronave gira enseguida hacia el primero.",
               "<b>Rumbo</b>, como el control de tránsito aéreo. En <b>Instrucción</b> elija <i>Virar … grados</i> («vire a la "
               "derecha 25 grados») o <i>Tomar el rumbo …</i> («tome rumbo 270»); escriba los <b>grados</b> y el <b>sentido</b>: "
               "a la derecha, a la izquierda o, para un rumbo, por el lado más corto."]),
          P("Antes de emitir, el panel muestra el rumbo actual, hacia qué lado vira y cuántos grados, y el mapa dibuja en "
            "amarillo la recta que seguirá. La aeronave vira 3° por segundo (el viraje estándar) y mantiene el rumbo hasta otra "
            "orden; con combustible crítico regresa sola a la base."),
          H2("5.4 Interceptar una aeronave o un buque")]
    h += [Table([[figura("interceptar", "Orden Interceptar con la estimación y el curso al punto de encuentro.", ancho=6.6 * cm,
                         alto_max=12 * cm, celda=True),
                  [P("Elija la aeronave (en vuelo o lista en tierra) o el buque, pulse <b>Interceptar</b>, elija el <b>blanco</b> "
                     "(una aeronave en vuelo o un buque enemigo detectado) y <b>qué hacer</b>:"),
                   Bul(["<b>Identificar y seguir</b>: lo identifica a la vista y lo sigue a unos kilómetros, sin tirar.",
                        "<b>Identificar y neutralizar</b>: lo identifica y lo ataca.",
                        "<b>Neutralizar sin esperar la identificación</b>: lo ataca apenas lo tiene a su alcance; con las armas "
                        "<i>restringidas</i> (6.1) igual lo identifica antes."]),
                   P("Antes de emitir, el panel dice si lo alcanza, en cuánto tiempo, con cuánto combustible llega y cuánto le "
                     "quedaría para volver; el mapa dibuja en amarillo el curso al <b>punto de encuentro</b> (puntería "
                     "adelantada: hacia donde estará el blanco).")]]],
                colWidths=[6.9 * cm, ANCHO_TEXTO - 6.9 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [P("Cada fase llega como alerta: vectoreo, contacto, identificación, seguimiento o ataque. Si se pierde el contacto "
            "sigue la estima del rumbo y la velocidad del blanco, busca sobre el último punto y, si no lo encuentra, aborta. "
            "Una aeronave en tierra despega en 5 minutos (alerta en tierra). Un buque solo intercepta buques. El planificador "
            "de misiones tiene también el rol <b>Interceptación</b>."),
          H2("5.5 Misiones aéreas planificadas")]
    h += [Table([[figura("mision_planificar", "Planificar una misión aérea.", ancho=6.6 * cm, alto_max=12 * cm, celda=True),
                  [P("El panel <b>Misiones aéreas</b> → <b>Planificar misión</b> arma misiones completas:"),
                   Bul(["un grupo que ya existe o uno que despega de una base;",
                        "el <b>rol</b> (patrulla aérea de combate, ataque, escolta, reconocimiento…);",
                        "la ruta, con sus puntos de paso, órbitas y blanco (clic en el mapa);",
                        "la base de aterrizaje y los datos de la <b>OTA</b> (paquete, armamento, IFF, hora sobre el blanco)."]),
                   P("Al llegar la hora, las aeronaves despegan y cumplen la misión solas; al terminar llega la alerta «misión "
                     "terminada».")]]],
                colWidths=[6.9 * cm, ANCHO_TEXTO - 6.9 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += figura("cronograma", "Cronograma de misiones (flow sheet).")
    h += [P("El <b>Cronograma</b> (flow sheet) muestra todas las misiones en el tiempo: cada fila es una misión, de color según "
            "su rol, con una línea roja en la hora actual.")]

    # ---------------------------------------------------------------- 6 defensa aerea y doctrina
    h += [H2("5.6 Apresto: alerta en tierra y rearme"),
          P("Cada aeronave tiene su <b>apresto</b>: cuánto tarda en despegar desde que recibe una orden de vuelo estando en "
            "tierra. Se elige en el panel de abajo de la unidad: <b>Alerta 5</b>, <b>15</b>, <b>30</b> o <b>60</b> minutos, o "
            "<b>Mantenimiento</b> (no despega). Si no se cambia, es alerta 5; la interceptación desde tierra también lo "
            "respeta. Mientras carretea, el panel dice en cuánto despega; si se detiene la orden, se queda en tierra."),
          P("Después de aterrizar, el <b>reabastecimiento y rearme</b> depende de la carga: aire-aire 45 min, reconocimiento "
            "30 min, antibuque, SEAD o antisubmarina 1 h 30 y ataque (bombas) 2 h; en un punto de recobre (PRO), la mitad.")]
    h += [H2("5.7 Velocidad y altura de cada tramo"),
          Bul(["<b>Velocidad</b> (aeronaves y buques, en el panel de abajo; rige de inmediato): <b>Económica</b> (75 %, rinde "
               "más kilómetros), <b>Crucero</b> (la normal) o <b>Máxima</b> (30 % más rápido, con postcombustión en los "
               "aviones, pero más del doble de combustible por kilómetro).",
               "<b>Altura</b>: perfil alto, medio o rasante (también abajo). Rasante se esconde del radar detrás del relieve, "
               "pero gasta más.",
               "<b>Por tramo</b>: en la orden <b>Mover</b>, elija «Velocidad del tramo» y «Altura del tramo» <b>antes</b> de "
               "marcar cada punto. Al pasar cada punto, la unidad toma los del tramo siguiente (por ejemplo: crucero y alto "
               "hasta la costa; máxima y rasante hasta el blanco)."])]

    h += H1("6. Defensa aérea y doctrina")
    h += [H2("6.1 Doctrina y reglas de enfrentamiento")]
    h += [Table([[figura("doctrina", "Doctrina y reglas de enfrentamiento.", ancho=6.4 * cm, alto_max=12 * cm, celda=True),
                  [P("En FUERZAS → <b>Doctrina y reglas de enfrentamiento</b> se decide cómo actúan las unidades por su cuenta:"),
                   Bul(["<b>Contra aeronaves</b> y <b>contra superficie</b>: <i>Libre</i> (tiran contra cualquier enemigo "
                        "detectado), <i>Solo identificados</i> o <i>Solo con orden</i>.",
                        "<b>Misiles por blanco</b> de la defensa aérea y <b>a qué distancia abren fuego</b> (100, 75 o 50 % del "
                        "alcance: más cerca, más probable el impacto).",
                        "Aeronaves: con qué <b>combustible regresan</b> y si vuelven al quedarse <b>sin armamento</b>."]),
                   P("La doctrina del bando la fijan el Comandante y el JEM (y el director); se aplica con <b>Aplicar doctrina</b>. "
                     "Cada unidad puede tener la suya; lo que quede en «Del bando» se toma de la doctrina del bando. Por "
                     "defecto: contra aeronaves libre, contra superficie solo con orden.")]]],
                colWidths=[6.7 * cm, ANCHO_TEXTO - 6.7 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("6.2 Radares y defensa antiaérea"),
          P("Los <b>radares</b> y la antiaérea guiada detectan aeronaves según su alcance, el relieve (las montañas tapan) y la "
            "altura a la que vuelan. La antiaérea dispara sola contra las aeronaves enemigas a su alcance, según la doctrina. "
            "En la unidad seleccionada de un sistema antiaéreo se ven sus armas con el alcance, la altura y la probabilidad de "
            "impacto (figura del punto 2.6), y se puede apagar o encender su radar. Los conduce A-3 D/A.")]
    h += [H2("6.3 Salvas de misiles y defensa de punto")]
    h += [P("Cada misil de una salva (de crucero, antibuque o los que tiran los aviones con la carga «antibuque») "
            "<b>vuela por separado</b> y se ve en el mapa. Al llegar impacta con su probabilidad (0,8 a 0,85) y hace su parte "
            "del daño de la salva completa."),
          P("Los buques tienen <b>defensa de punto</b> que tira sola contra los misiles enemigos a su alcance: destructores 4 "
            "canales a 12 km, fragatas 2 a 8 km, portaaviones 2 a 6 km, patrulleros y buques de desembarco 1 a 4 km. Cada "
            "canal tira una vez cada 10 segundos: una <b>salva grande satura</b> los canales y pasan más misiles.")]
    h += figura("salvas", "Salva de 4 misiles de crucero recién lanzada desde un submarino: cada misil vuela por separado.")
    h += [H2("6.4 Misiles balísticos y defensa antimisil")]
    h += [Table([[figura("balisticos", "Salva balística en vuelo: trayectoria y punto de impacto previsto.", ancho=7.2 * cm,
                         alto_max=9 * cm, celda=True),
                  [P("El <b>lanzador de misiles balísticos</b> (tipo Iskander) lanza contra un blanco de superficie a 500 km o "
                     "menos. Cada misil vuela por separado con trayectoria alta (unos 6 minutos) y cae <b>donde estaba el blanco "
                     "al lanzar</b>. El bando del blanco recibe la <b>alerta temprana</b> con la hora del impacto."),
                   P("Solo los <b>sistemas antimisil</b> (S-300VM, S-400, Patriot, HQ-9 y los destructores Arleigh Burke y "
                     "Ticonderoga) los derriban, en su fase final y con el radar encendido; la antiaérea común no puede."),
                   P("El <b>adversario automático</b> también los usa: su lanzador tira solo contra lo que su bando ve a su "
                     "alcance, primero las instalaciones fijas, y vuelve a tirar al terminar de recargar (30 minutos).")]]],
                colWidths=[7.5 * cm, ANCHO_TEXTO - 7.5 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("6.5 Minas navales")]
    h += [Bul(["<b>Minar</b>: patrulleros, fragatas, submarinos, buques de desembarco y aviones de ataque siembran sobre el "
               "punto un campo de 20 minas en 3 km (el buque tarda media hora; el avión, una pasada).",
               "Todo buque que navega dentro (también los propios) puede <b>chocar una mina</b>; el riesgo crece con lo que "
               "navega adentro y las minas que quedan.",
               "Quien sembró el campo lo ve en el mapa; el otro bando, cuando choca una mina o un <b>cazaminas</b> lo detecta "
               "a 5 km. <b>Barrer minas</b>: el cazaminas limpia el campo (unas 5 minas por hora) con poco riesgo."])]
    h += figura("minas", "Campo de minas propio en el mapa y la orden Minar.")
    h += [H2("6.6 Guerra antisubmarina")]
    h += [Table([[figura("asw", "Submarino con su profundidad y la orden Torpedo.", ancho=6.4 * cm, alto_max=11 * cm, celda=True),
                  [P("Un submarino sumergido solo se detecta con <b>sonar</b>; al atacar se delata unos 10 minutos."),
                   Bul(["<b>Profundidad</b> (panel de abajo): a cota periscópica un radar lo ve a menos de 8 km y puede lanzar "
                        "misiles; a profundidad solo lo oye el sonar, al 60 % de su alcance.",
                        "<b>Sonar de casco</b>: fragatas 25 km, destructores 30 km, submarinos 35 km.",
                        "<b>Sonoboyas</b> (P-3, P-8): 4 boyas sobre el punto que escuchan a 10 km durante 4 horas.",
                        "<b>Sonar de inmersión</b> (NH90): en vuelo estacionario sobre el punto, escucha a 12 km.",
                        "<b>Torpedo</b>: de submarinos (30 km), fragatas y destructores (10 km) y aeronaves antisubmarinas (8 km) "
                        "contra un buque o submarino detectado; navega a unos 40 nudos y golpea al llegar."])]]],
                colWidths=[6.7 * cm, ANCHO_TEXTO - 6.7 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("6.7 Daño por sistemas y control de averías")]
    h += [Table([[figura("sistemas", "Panel de abajo: sistemas de una unidad dañada.", ancho=6.4 * cm, alto_max=9 * cm, celda=True),
                  [P("Los buques y las unidades de tierra tienen cuatro <b>sistemas</b> que se dañan por separado (panel de abajo):"),
                   Bul(["<b>Sensores</b>: con daño detecta menos; sin ellos, solo a ojo.",
                        "<b>Armas</b>: su fuego y su defensa aérea pierden efecto en proporción.",
                        "<b>Propulsión</b> o movilidad: va más lento; fuera de servicio, queda inmóvil.",
                        "<b>Comunicaciones</b>: sus órdenes tardan más en llegar."]),
                   P("Cada punto de fuerza perdido puede causar un impacto crítico en un sistema (unos 25 puntos dañan uno en "
                     "promedio); al 75 % queda <b>fuera de servicio</b> y llega una alerta. El <b>control de averías</b> repara "
                     "unos 10 puntos por hora; las averías graves solo se terminan de reparar junto a un puerto o base propia.")]]],
                colWidths=[6.7 * cm, ANCHO_TEXTO - 6.7 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("6.8 Áreas de patrulla y zonas de exclusión o de no vuelo")]
    h += [Table([[figura("zonas", "Tarjeta «Áreas y zonas».", ancho=5.4 * cm, alto_max=11 * cm, celda=True),
                  [P("En la tarjeta <b>Áreas y zonas</b> (panel derecho) elija el tipo, escriba un nombre y pulse <b>Dibujar en "
                     "el mapa</b>: clic en cada vértice y, para terminar, clic en el primero. El director las dibuja para todos o "
                     "para un bando; cada bando, las suyas."),
                   Bul(["<b>Área de patrulla</b>: con la orden <b>Patrullar</b> y el área elegida en «Dónde», la unidad (aeronave, "
                        "buque o tropa) la recorre de vértice en vértice y ataca lo que entra si su doctrina lo permite.",
                        "<b>Zona de exclusión</b>: nadie ajeno debe entrar. <b>Zona de no vuelo</b>: ninguna aeronave ajena.",
                        "Quien cruza una de ellas dispara una alerta (y la pausa automática, si el director la eligió). Con "
                        "<b>«Las armas propias tiran contra quien entre»</b> se le tira aunque la doctrina restrinja las armas."])]]],
                colWidths=[5.7 * cm, ANCHO_TEXTO - 5.7 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += figura("zonas_mapa", "Área de patrulla (amarillo, elegida para la orden), zona de exclusión con armas libres "
                "(naranja) y zona de no vuelo de la dirección (rojo).")

    h += [P("<b>Zonas que acompañan a una unidad</b>: seleccione una unidad propia y marque <b>Que acompañe a la unidad "
            "seleccionada</b> antes de dibujar, o escriba un <b>Radio</b> y pulse <b>Círculo alrededor de la unidad</b> (por "
            "ejemplo, una zona de exclusión de 20 km alrededor de una fragata). La zona se mueve con la unidad; si la unidad "
            "se pierde, queda donde estaba.")]
    h += [H2("6.9 Contramedidas: bengalas, chaff y señuelos"),
          P("Las aeronaves tripuladas llevan <b>bengalas y chaff</b> (4 por avión del grupo) y los buques <b>señuelos</b> "
            "(fragata 8, destructor y portaaviones 12, patrullero 4). Cuando a una aeronave le tiran un misil antiaéreo o "
            "aire-aire, o a un buque le llega un misil, suelta una: ese misil tiene 30 % menos de probabilidad de pegar. Se "
            "gastan; las aeronaves las reponen al rearmar y los buques al reabastecerse. Lo que le queda a cada unidad se "
            "ve en su panel. Los misiles antirradiación solo atacan radares encendidos: apagar el radar a tiempo (botón "
            "<b>Emisión</b>) lo protege, pero mientras tanto no ve.")]

    # ---------------------------------------------------------------- 7 inteligencia
    h += H1("7. Inteligencia y contactos")
    h += [H2("7.1 La niebla de guerra")]
    h += figura("bando_azul", "Lo que ve el Comandante Azul: sus unidades y solo los enemigos que su bando detecta.")
    h += [P("Cada bando ve solo lo que detectan sus unidades. La detección depende del alcance de cada sensor, del terreno "
            "(bosques y ciudades ocultan), del relieve, del clima y de la noche. Para ver más: acerque unidades de "
            "reconocimiento o drones (A-2), use radares y patrullas, o la escucha electrónica (C-E).")]
    h += [H2("7.2 Contactos: desconocido, clasificado e identificado"),
          P("Un enemigo recién detectado aparece como <b>desconocido</b> (solo se sabe si está en el aire o en superficie). "
            "Mientras se lo sigue, pasa a <b>clasificado</b> (se sabe qué clase de unidad es) y luego a <b>identificado</b> (se sabe "
            "cuál es). Es más rápido de cerca y con radar; solo por escucha electrónica es lento y no pasa de clasificado. A "
            "menos de 8 km se identifica a ojo; las bases se conocen de antemano."),
          P("El <b>círculo amarillo</b> alrededor de un contacto muestra dónde puede estar en realidad. Si se pierde el contacto, "
            "queda su último lugar conocido y el círculo crece con lo que pudo moverse. Las armas en <i>Solo identificados</i> no "
            "tiran contra desconocidos.")]
    h += [H2("7.3 Puntos medios de impacto (PMI) sobre las pistas"),
          P("Para dejar fuera de servicio una pista hay que cortarla en tramos más cortos de lo que necesita un caza para "
            "despegar. Esos cortes son los <b>puntos medios de impacto (PMI)</b>, y los prepara Inteligencia para Operaciones:"),
          Num(["<b>A-3</b> (o el Comandante o el JEM), en FUERZAS → <b>Puntos medios de impacto</b>, elige la base aérea "
               "enemiga y pulsa <b>Pedir a Inteligencia</b>.",
               "<b>A-2</b> ve el pedido y pulsa <b>Preparar los PMI…</b>: el sistema propone los cortes sobre el eje de la pista "
               "real del aerodromo, con sus coordenadas, de modo que ningún tramo sano llegue a 800 m. Puede arrastrar cada "
               "punto en el mapa para correrlo.",
               "<b>Entregar a Operaciones</b>: desde ese momento el ataque a la pista de esa base hace todo su daño."]),
          P("Sin los PMI, las bombas caen dispersas y el ataque a la pista hace <b>la mitad</b> del daño; la orden Atacar avisa "
            "si el bando los tiene. Los PMI entregados se ven en el mapa al acercarse a la base."),
          H2("7.4 El cuadro radar")]
    h += [Table([[figura("cuadro_radar", "Cuadro radar (pestaña SITUACIÓN).", ancho=6.0 * cm, alto_max=12 * cm, celda=True),
                  [P("En SITUACIÓN → <b>Cuadro radar</b> se ve qué detecta ahora cada sensor del bando: los radares, la "
                     "antiaérea, el reconocimiento y la escucha electrónica, con la distancia y el rumbo de cada contacto."),
                   P("<b>Difundir el cuadro a la red del bando</b> comparte lo detectado con todas las reparticiones.")]]],
                colWidths=[6.3 * cm, ANCHO_TEXTO - 6.3 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]

    # ---------------------------------------------------------------- 8 logistica
    h += [H2("7.5 Imagen común por enlace de datos"),
          P("Si el director enciende <b>Imagen común por enlace de datos</b> (CONSOLA → Dirección del ejercicio), lo que "
            "detecta una unidad solo aparece en la pantalla de su bando si está <b>en la red</b>. La red nace en las bases, "
            "puertos, depósitos, centros de comunicaciones, radares, aviones de alerta temprana, portaaviones y destructores, "
            "y se extiende de unidad en unidad: un avión enlaza hasta 350 km, un buque 250 km, una base 150 km y una tropa "
            "60 km."),
          P("Queda <b>sin enlace</b> la unidad lejos de la red, dentro de una interferencia enemiga o con las comunicaciones "
            "destruidas: se sigue defendiendo con sus sensores, pero su bando no ve lo que ella detecta ni puede tirarle a eso "
            "desde otra unidad. El panel de cada unidad propia dice si está en la red. Aviones y buques sirven de "
            "repetidores para llevar la red lejos.")]

    h += H1("8. Logística, ingenieros y transporte")
    h += [H2("8.1 Combustible, munición y abastecimiento"),
          P("Las unidades gastan combustible al moverse y munición al combatir. Se reabastecen solas, poco a poco, cerca de las "
            "<b>bases</b>, los <b>depósitos</b> y los <b>convoyes</b> propios, que llevan su carga a donde se los mande. Las "
            "aeronaves pueden reabastecer en vuelo junto a un <b>avión cisterna</b>. Conduce A-4."),
          H2("8.2 Ingenieros: puentes y vados"),
          P("Elija la unidad de ingenieros → orden <b>Construir</b> → clic sobre un río a menos de 5 km. La obra tarda un tiempo; "
            "cuando está lista, los vehículos pesados pueden cruzar por allí."),
          H2("8.3 Embarcar y desembarcar tropas"),
          P("<b>Embarcar</b>: la unidad sube a un buque de desembarco o a un helicóptero de transporte propio que esté a menos de "
            "3 km. A bordo viaja con el transporte, no se la ve ni ataca por separado y sufre la mitad del daño que reciba el "
            "transporte (se pierde si lo hunden o derriban). <b>Desembarcar</b>: elija el transporte y marque la ruta; el último "
            "punto es el lugar de desembarco, en tierra firme."),
          H2("8.4 Misiles de crucero"),
          P("Buques y baterías con misiles de crucero: orden <b>Lanzar misiles</b> sobre un blanco. La salva vuela sola (unos "
            "850 km/h) hacia donde estaba el blanco; la antiaérea y las patrullas enemigas pueden derribarla antes. Cada misil "
            "gasta el 25 % de la munición del lanzador.")]

    # ---------------------------------------------------------------- 9 guerra electronica
    h += [H2("8.5 Reabastecimiento en el mar"),
          P("El <b>buque logístico</b> (petrolero de flota) es el convoy de la flota: llévelo con la orden <b>Mover</b> a 5 km "
            "o menos de los buques que necesitan combustible o munición. Les da +40 % por hora y les repone los señuelos. Se "
            "recarga junto a un puerto propio. Lo conduce A-4; tiene armas débiles y necesita escolta.")]

    h += H1("9. Guerra electrónica")
    h += [P("<b>Interferir</b>: con la unidad o el avión de guerra electrónica, orden <b>Interferir</b> y clic en el centro de la "
            "zona, dentro de su alcance. Mientras dure la orden, allí el enemigo detecta mucho menos, su antiaérea guiada por "
            "radar pierde efecto y sus drones pierden el enlace. Pero al emitir, <b>el enemigo localiza al interferidor</b>."),
          P("La <b>escucha</b> electrónica localiza de lejos a los radares enemigos encendidos. Un radar apagado no se oye, pero "
            "tampoco ve. Conduce C-E.")]

    # ---------------------------------------------------------------- 10 mapa
    h += H1("10. El mapa")
    h += [H2("10.1 Regiones, satélite y relieve"),
          P("El Cóndor trae sus mapas en la propia PC, sin internet. En la tarjeta <b>Capas</b>, los botones de región llevan la "
            "vista a cada una:"),
          Bul(["<b>Venezuela y vecinos</b>: el área de más detalle, para ejercicios tácticos.",
               "<b>América</b>: todo el continente, de Alaska a Tierra del Fuego.",
               "<b>Mundo</b>: el planeta entero, hasta el Ártico.",
               "<b>Teatro ficticio</b>: País Azul y País Rojo, para ejercicios sin geografía real."]),
          P("<b>Satélite</b> muestra la foto satelital real y <b>Relieve</b> el terreno coloreado por clase (llano, bosque, montaña, "
            "pantano, ciudad, agua). Al alejarse, el mapa muestra solo las ciudades grandes y sin nombre; los nombres aparecen "
            "al acercarse.")]
    h += figura("mapa_mundo", "Región Mundo, vista satelital.")
    h += figura("mapa_venezuela", "Región Venezuela y vecinos, con ciudades, aeródromos y unidades.")
    h += [H2("10.2 Capas, estelas y símbolos")]
    h += [Table([[figura("capas", "Tarjeta Capas.", ancho=5.0 * cm, alto_max=14 * cm, celda=True),
                  [P("En la tarjeta <b>Capas</b> se enciende o apaga lo que muestra el mapa: terreno, cobertura de detección, "
                     "niebla de guerra, unidades, alcances (al acercarse), últimos contactos, gráficos tácticos, objetivos, "
                     "infraestructura, aeródromos, guerra electrónica, meteorología y misiones."),
                   Bul(["<b>Estelas de movimiento</b>: la línea por donde pasó cada unidad, más tenue cuanto más vieja. Su largo va "
                        "de 10 minutos a 3 horas simuladas.",
                        "<b>Símbolos militares (APP-6)</b> en lugar de las miniaturas.",
                        "<b>Tramos aptos para PRO</b>: tramos de carretera que sirven de pista."])]]],
                colWidths=[5.3 * cm, ANCHO_TEXTO - 5.3 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("10.3 Clima, lluvia, tormentas y noche"),
          P("Además del clima general, el director puede poner <b>zonas</b> de nubosidad, lluvia o tormenta, que se desplazan de "
            "forma continua. Dentro de ellas se detecta menos, se avanza más lento y el ataque aéreo pierde efecto. De noche "
            "también se detecta menos. En Capas → <b>Vista del clima</b>: <i>Solo el radio</i> (el círculo con su rótulo y la "
            "flecha de hacia dónde va) o <i>Satélite meteorológico</i> (las nubes como en una imagen de satélite).")]
    h += [H2("10.4 Gráficos tácticos y herramientas")]
    h += [Table([[figura("graficos", "Gráficos tácticos.", ancho=5.4 * cm, celda=True),
                  [P("En el cuadro <b>Gráficos tácticos</b> (sobre el mapa) se dibujan líneas de fase, ejes de avance, zonas de "
                     "reunión y puntos de control. Elija la herramienta, escriba la etiqueta si quiere y trace sobre el mapa "
                     "(doble clic o clic en el último punto para terminar). Lo verá todo su bando; el director elige si lo ve "
                     "todo el ejercicio o un solo bando."),
                   P("<b>▲ Esconder</b> reduce el cuadro a su título y <b>▼ Mostrar</b> lo vuelve a abrir.")]]],
                colWidths=[5.7 * cm, ANCHO_TEXTO - 5.7 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += figura("graficos_plegado", "El cuadro escondido, con la regla y el convertidor arriba.", ancho=8 * cm)
    h += [P("La <b>Regla</b> mide distancias y rumbos (clic en cada punto; doble clic o Esc para terminar) y <b>Convertir</b> "
            "pasa distancias, velocidades, alturas, masas y volúmenes de una unidad a otra. Arriba a la izquierda, el mapa "
            "muestra las coordenadas y la clase de terreno bajo el cursor.")]
    h += [H2("10.5 Videowall (pantalla completa)")]
    h += figura("videowall", "Videowall: el mapa a pantalla completa con el reloj, el clima y el marcador.")
    h += [P("El botón <b>Videowall</b> (o la tecla <b>V</b>) muestra el mapa a pantalla completa, sin paneles, para un proyector "
            "o un centro de operaciones. Con <b>Esc</b> se vuelve.")]

    # ---------------------------------------------------------------- 11 situacion y TIEM
    h += H1("11. Situación y Estado Mayor")
    h += [Table([[figura("situacion", "Pestaña SITUACIÓN.", ancho=5.4 * cm, alto_max=12.5 * cm, celda=True),
                  figura("tiem", "Pestaña TIEM.", ancho=5.4 * cm, alto_max=12.5 * cm, celda=True)]],
                colWidths=[ANCHO_TEXTO / 2] * 2, style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("11.1 La pestaña SITUACIÓN"),
          P("Reúne el estado del bando: <b>cuadro radar</b> (7.4), personal y bajas, apresto, organización, esfuerzo aéreo, "
            "rescate, transmisiones, alerta temprana, inteligencia e <b>infraestructura crítica</b> (centrales, refinerías, "
            "centros de comunicaciones y puentes)."),
          H2("11.2 Trabajo de Estado Mayor (pestaña TIEM)"),
          P("La pestaña <b>TIEM</b> guía el trabajo del Estado Mayor: el <b>calendario</b> de la operación (día D, hora H y fases), "
            "el <b>Problema Militar Operativo</b> del bando, las apreciaciones de cada repartición, las formas de acción y su "
            "<b>ensayo</b> (juego de guerra), la <b>Orden de Operaciones</b>, la <b>supervisión</b> de la ejecución y la "
            "<b>evaluación</b>, con el legajo en Word o PDF."),
          H2("11.3 Comunicaciones del bando"),
          P("En la tarjeta <b>Comunicaciones</b> (derecha) se escriben mensajes al resto del bando. Las comunicaciones pueden "
            "tener demoras o pérdidas si el director las simula.")]

    # ---------------------------------------------------------------- 12 informe
    h += H1("12. Informe y repetición")
    h += figura("informe", "Barra de la repetición con sus vistas.")
    h += [P("El botón <b>Informe</b> abre el análisis del ejercicio:"),
          Bul(["<b>Resumen</b> de cada bando y <b>línea de tiempo</b> de combates y logística;",
               "<b>repetición</b> del ejercicio sobre el mapa (con <b>Replay</b>, animada, con estelas y marcador);",
               "<b>rúbrica</b> de evaluación por repartición y comparación entre ejercicios;",
               "versión <b>imprimible</b>, <b>diapositivas</b> y exportación a <b>CSV</b>."]),
          P("En el resumen están las <b>pérdidas y gastos</b> de cada bando: aeronaves (por avión), buques, unidades de tierra "
            "e instalaciones perdidas; el combustible consumido, en tanques llenos; y cada arma gastada (misiles y bombas de "
            "las aeronaves, misiles antiaéreos, interceptores antimisil, defensa de punto, misiles de crucero y balísticos, "
            "torpedos, sonoboyas, minas, bengalas y señuelos).")]

    # ---------------------------------------------------------------- 13 direccion
    h += H1("13. Dirección del ejercicio")
    h += [Nota("Este capítulo es para el director del ejercicio: las funciones descritas no aparecen en las cuentas de los bandos.")]
    h += [H2("13.1 Preparar un ejercicio")]
    h += [Table([[figura("consola", "Pestaña CONSOLA.", ancho=5.6 * cm, alto_max=13 * cm, celda=True),
                  [Bul(["<b>Nuevo</b> o <b>Desde plantilla…</b> (arriba) crea el escenario; <b>Guardar como plantilla…</b> guarda el "
                        "actual para reutilizarlo.",
                        "En CONSOLA: <b>Agregar unidad</b> (con el buscador del catálogo), <b>Objetivos y puntaje</b>, <b>Editar el "
                        "escenario</b>, meteorología por zonas, calendario de la operación, identidad nacional, apresto y personal "
                        "de cada bando.",
                        "CONSOLA → <b>Escenario</b> → <b>Usuarios con acceso</b>: marque las cuentas que entran a este ejercicio."])]]],
                colWidths=[5.9 * cm, ANCHO_TEXTO - 5.9 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("13.2 Conducir el ejercicio"),
          Bul(["Abajo: <b>PONER EN MARCHA / DETENER EL RELOJ</b>, la velocidad y <b>+1 h</b>.",
               "CONSOLA → <b>Reloj y configuración</b>: qué causas detienen el reloj solas (pausa automática), clima y hora.",
               "CONSOLA → <b>Eventos e informes inyectados</b>: mensajes para un bando (con lugar en el mapa si quiere) y el ajuste "
               "manual de una unidad, que queda en el informe.",
               "CONSOLA → <b>Dirección del ejercicio</b>: interruptores del motor (niebla de guerra, fuego automático, clima, "
               "noche, azar…) y el <b>adversario automático</b> para el bando que no tenga alumnos.",
               "<b>Conducir Azul / Rojo</b> (arriba): dar órdenes como el comandante de un bando sin alumnos; <b>Dejar de conducir</b> "
               "vuelve a la vista del director.",
               "<b>Finalizar</b> cierra el ejercicio; <b>Duplicar</b> y <b>Archivar</b> están en CONSOLA → Escenario."]),
          H2("13.3 Tráfico civil, neutrales y daño colateral")]
    h += [Table([[figura("trafico", "CONSOLA → Tráfico civil y neutral.", ancho=5.6 * cm, alto_max=11 * cm, celda=True),
                  [P("En CONSOLA → <b>Tráfico civil y neutral</b> el director pide aviones comerciales, buques mercantes y "
                     "pesqueros en la zona que se ve en el mapa. Los aviones vuelan por <b>aerovías</b> (líneas verdes "
                     "punteadas), los mercantes cruzan por el mar y los pesqueros van de un caladero a otro; el que sale de la "
                     "zona se retira y entra otro."),
                   P("Para cada bando son contactos desconocidos hasta clasificarlos. Con las armas <i>libres</i> se les puede "
                     "tirar por error; con las <i>restringidas</i>, nunca. Tirarle a una unidad neutral es <b>daño colateral</b>: "
                     "alerta, penalización en el puntaje (10 puntos por unidad y uno más cada 5 de fuerza) y una sección en el "
                     "informe. Para un país que no participa, agregue unidades con el bando <b>Neutral</b>.")]]],
                colWidths=[5.9 * cm, ANCHO_TEXTO - 5.9 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("13.4 Eventos automáticos")]
    h += [Table([[figura("eventos_auto", "CONSOLA → Eventos automáticos.", ancho=6.2 * cm, alto_max=13 * cm, celda=True),
                  [P("Reglas que el simulador cumple solo, con un <b>cuando</b> y uno o varios <b>entonces</b>:"),
                   Bul(["<b>Cuando</b>: una unidad entra a un área (una zona dibujada; de un bando o una unidad concreta), llega "
                        "una hora del ejercicio, se destruye una unidad, o se cumple o falla un objetivo.",
                        "<b>Entonces</b>: enviar un mensaje (llega a Comunicaciones, firmado «Director», y como alerta), "
                        "hacer aparecer unidades (bando, clase, cantidad y el punto en el mapa), cambiar el clima, dar o "
                        "quitar puntos, pausar el reloj o <b>lanzar misiles</b>: un lanzador (batería, buque o lanzador "
                        "balístico) tira una salva contra la unidad elegida aunque su bando no la vea, si la tiene a su "
                        "alcance (un ataque programado)."]),
                   P("Cada regla se dispara una vez, salvo que se marque <b>Repetir</b>. En la lista se activan, se desactivan "
                     "y se borran. Se guardan con el escenario y con las plantillas, junto con las áreas y zonas, el tráfico "
                     "civil, los campos de minas, la doctrina, el nivel del adversario y el enlace de datos. El <b>Tutorial del Cóndor</b> (2.10) "
                     "es un ejemplo completo.")]]],
                colWidths=[6.5 * cm, ANCHO_TEXTO - 6.5 * cm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]
    h += [H2("13.5 Cuentas y usuarios"),
          P("CONSOLA → <b>Usuarios</b>: crear cuentas, cambiar su repartición, restablecer contraseñas y aprobar las solicitudes "
            "de cuenta pendientes. Para que una cuenta vea un ejercicio, márquela en CONSOLA → Escenario → <b>Usuarios con "
            "acceso a este escenario</b>."),
          Nota("Entregue las contraseñas en papel o en un documento aparte; no las publique en el aula ni en mensajes.")]

    # ---------------------------------------------------------------- 14 problemas
    h += H1("14. Problemas frecuentes")
    h += [Tbl(["Problema", "Qué hacer"], [
        ["«Esa acción corresponde a otra repartición»", "Cada repartición ordena solo sus unidades (2.8). Pídasela a quien la conduce, "
                                                       "al Comandante o al JEM."],
        ["No aparece el tipo de orden", "Esa unidad no puede cumplirla (por ejemplo, solo las aeronaves patrullan)."],
        ["No aparece el blanco", "El enemigo no está detectado por su bando (capítulo 7)."],
        ["La unidad no recibe órdenes", "Está embarcada, destruida o sin enlace (drones interferidos)."],
        ["El reloj no avanza", "Si abajo dice RELOJ DETENIDO, el director debe ponerlo en marcha. Si arriba hay una franja PAUSA "
                               "AUTOMÁTICA, el director lo reanuda. El reloj solo corre mientras alguien está conectado."],
        ["La unidad no se mueve", "Puede estar sin combustible, varada ante un río sin paso o esperando en tierra: revise sus datos."],
        ["La página no abre", "Revise la dirección: es la de la PC del Cóndor y termina en :8001. La PC debe estar en la misma red."],
        ["Se desconectó", "El punto de conexión (arriba) en rojo indica que se perdió la conexión: recargue con F5."],
        ["Se cerró el servidor", "El director lo vuelve a abrir con el acceso directo Condor; no se pierde lo hecho."],
        ["Los cambios no se ven", "Recargue la página con Ctrl+F5."],
    ], [5.2 * cm, ANCHO_TEXTO - 5.2 * cm])]

    # ---------------------------------------------------------------- anexos
    h += H1("Anexo A. Catálogo de modelos")
    h += [P(f"Los {len(catalogo.MODELOS)} modelos del catálogo del Cóndor, agrupados por clase de unidad. Cada uno tiene su ficha "
            "con foto de referencia, armamento y capacidades, que se ve en el simulador.")]
    h += tabla_catalogo()
    h += H1("Anexo B. Glosario")
    h += [Tbl(["Término", "Significado"], [
        ["APP-6", "Norma de simbología militar; alternativa a las miniaturas en el mapa."],
        ["CAP", "Patrulla aérea de combate: aeronaves que orbitan una zona para interceptar."],
        ["Clasificado / identificado", "Grados de conocimiento de un contacto enemigo (7.2)."],
        ["Cuadro radar", "Lo que detecta ahora cada sensor del bando (7.4)."],
        ["Doctrina / ROE", "Reglas con que las unidades actúan por su cuenta (6.1)."],
        ["Estela", "Línea por donde pasó una unidad en el mapa."],
        ["Flow sheet", "Cronograma de las misiones aéreas (5.5)."],
        ["JEM", "Jefe de Estado Mayor."],
        ["Niebla de guerra", "Cada bando solo ve lo que detecta."],
        ["OTA", "Orden de tareas aéreas: datos de paquete, armamento, IFF y hora de cada misión."],
        ["PMI", "Punto medio de impacto: dónde deben caer las bombas para cortar una pista (7.3)."],
        ["PRO", "Pista de recuperación operacional: tramo de carretera apto para operar aeronaves."],
        ["TIEM", "Trabajo Integral de Estado Mayor (11.2)."],
        ["TOT", "Hora sobre el blanco."],
        ["Waypoint", "Punto de paso de una ruta."],
    ], [4.6 * cm, ANCHO_TEXTO - 4.6 * cm])]
    h += creditos()
    doc.multiBuild(titulos_con_su_figura(h))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=str(RAIZ / "docs" / "Manual_Usuario_Condor.pdf"))
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    construir(salida)
    print(f"{salida} ({salida.stat().st_size // 1024} KB, {FIG[0]} figuras)")


if __name__ == "__main__":
    main()
