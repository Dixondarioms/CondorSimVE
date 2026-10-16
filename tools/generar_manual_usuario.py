"""Genera el manual de usuario en PDF (docs/Manual_Usuario_SIETE.pdf): guia paso a paso, con capturas, de cada parte
de la interfaz para el instructor, los alumnos de cada repartición y el observador.

Las capturas salen de tools/manual/capturas_guia.py (arnes de pruebas manejado con Chrome). El aspecto (fuentes,
colores, tablas) es el del manual de referencia (tools/generar_manual.py), del que se reusan las piezas.

    backend\\venv\\Scripts\\python tools/manual/capturas_guia.py        # con el servidor en marcha en el puerto 8000
    backend\\venv\\Scripts\\python tools/generar_manual_usuario.py
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generar_manual import (ANCHO_TEXTO, AZUL, RAIZ, S, Bul, H1, H2, H3, Manual, Nota, Num, P, Tbl,  # noqa: E402
                            credito_portada, seccion_creditos)
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle  # noqa: E402
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

IMG = RAIZ / "tools" / "manual" / "salida" / "guia"
FIG = [0]
# un titulo nunca queda solo al pie de una pagina: va con lo que le sigue
S["h2"].keepWithNext = S["h3"].keepWithNext = 1


def figura(nombre: str, pie: str, ancho=ANCHO_TEXTO) -> list:
    """Captura a lo ancho (o al ancho indicado) con su pie numerado."""
    ruta = IMG / f"{nombre}.jpg"
    if not ruta.exists():
        return [Paragraph(f"[captura no disponible: {nombre}]", S["cap"])]
    FIG[0] += 1
    im = Image(str(ruta))
    k = min(ancho / im.imageWidth, (22 * cm) / im.imageHeight)
    im.drawWidth, im.drawHeight = im.imageWidth * k, im.imageHeight * k
    return [KeepTogether([im, Paragraph(f"Figura {FIG[0]}. {pie}", S["cap"])])]


def al_lado(nombre: str, pie: str, contenido: list, ancho_img=6.2 * cm) -> list:
    """Captura angosta (un panel) a la izquierda y la explicacion a la derecha."""
    ruta = IMG / f"{nombre}.jpg"
    if not ruta.exists():
        return [Paragraph(f"[captura no disponible: {nombre}]", S["cap"])] + contenido
    FIG[0] += 1
    im = Image(str(ruta))
    k = min(ancho_img / im.imageWidth, (19 * cm) / im.imageHeight)
    im.drawWidth, im.drawHeight = im.imageWidth * k, im.imageHeight * k
    izquierda = [im, Paragraph(f"Figura {FIG[0]}. {pie}", S["cap"])]
    t = Table([[izquierda, contenido]], colWidths=[ancho_img + 0.4 * cm, ANCHO_TEXTO - ancho_img - 0.4 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (0, 0), 10), ("RIGHTPADDING", (1, 0), (1, 0), 0)]))
    t.spaceAfter = 8
    return [t]


def dos_figuras(a: tuple[str, str], b: tuple[str, str]) -> list:
    """Dos capturas lado a lado, cada una con su pie numerado (por ejemplo, el mismo mapa de dia y de noche)."""
    celdas = []
    ancho = (ANCHO_TEXTO - 0.4 * cm) / 2
    for nombre, pie in (a, b):
        ruta = IMG / f"{nombre}.jpg"
        if not ruta.exists():
            celdas.append([Paragraph(f"[captura no disponible: {nombre}]", S["cap"])])
            continue
        FIG[0] += 1
        im = Image(str(ruta))
        k = ancho / im.imageWidth
        im.drawWidth, im.drawHeight = im.imageWidth * k, im.imageHeight * k
        celdas.append([im, Paragraph(f"Figura {FIG[0]}. {pie}", S["cap"])])
    t = Table([celdas], colWidths=[ancho + 0.2 * cm, ancho + 0.2 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    t.spaceAfter = 8
    return [KeepTogether([t])]


def leyenda(filas: list[tuple[str, str, str]]) -> Table:
    """Tabla de referencias numeradas de una figura: (numero, zona, para que sirve)."""
    return Tbl(["N.º", "Zona", "Para qué sirve"], [list(f) for f in filas], [1.0 * cm, 4.0 * cm, ANCHO_TEXTO - 5.0 * cm])


def pasos(*items) -> object:
    return Num(list(items))


def B(t: str) -> str:
    """Nombre de un boton o control, en negrita."""
    return f"<b>{t}</b>"


def construir(salida: Path) -> None:
    doc = Manual(str(salida), titulo="S.I.E.T.E. · Manual de usuario")
    hoy = date.today()
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    fecha = f"{meses[hoy.month - 1].capitalize()} de {hoy.year}"
    h = []

    # ---------------------------------------------------------------- portada
    h += [Spacer(1, 1.2 * cm)]
    logo = RAIZ / "frontend" / "static" / "img" / "siete_logo_recortado.jpg"
    if logo.exists():
        im = Image(str(logo))
        im.drawWidth, im.drawHeight = 12 * cm, 12 * cm * im.imageHeight / im.imageWidth
        h += [im, Spacer(1, 14)]
    h += [Paragraph("S.I.E.T.E.", S["titulo"]), Spacer(1, 6),
          Paragraph("Sistema Integral de Entrenamiento Táctico y Estratégico", S["subtitulo"]), Spacer(1, 26),
          Paragraph("MANUAL DE USUARIO", ParagraphStyle("mu", parent=S["subtitulo"], fontName="Texto-B", fontSize=20, textColor=AZUL)),
          Spacer(1, 8), Paragraph("Guía paso a paso para el instructor, los alumnos de cada repartición y el observador", S["subtitulo"]),
          Spacer(1, 24)]
    h += credito_portada()
    h += [Spacer(1, 10), Paragraph(f"{fecha} · versión 1.2", S["subtitulo"]), PageBreak()]

    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    h += [Paragraph("Contenido", ParagraphStyle("h1toc", parent=S["h1"])), toc]

    # ---------------------------------------------------------------- 1
    h += H1("1. Cómo usar este manual")
    h += [P("Este manual explica, pantalla por pantalla, cómo se usa S.I.E.T.E. Está pensado para leerse junto al simulador: cada "
            "capítulo muestra una parte de la interfaz con una captura y los pasos para usarla. La instalación, el funcionamiento "
            "interno y las reglas del motor (combate, logística, sensores) están en el <b>Manual de referencia</b> "
            "(<font face='Mono'>docs/Manual_SIETE.pdf</font>)."),
          H2("1.1 Quién hace qué"),
          Tbl(["Rol", "Qué hace en el ejercicio", "Capítulos"], [
              ["Instructor (director del ejercicio)", "Prepara el escenario, ubica las unidades, fija objetivos, clima y reglas, aprueba las cuentas, "
               "resuelve los turnos, inyecta eventos y conduce el análisis posterior.", "2 a 5, 7 a 9"],
              ["Alumno del bando azul o rojo", "Integra el Estado Mayor de su bando en una repartición del TIEM (Comandante, JEM, A-1, A-2, "
               "A-3, A-3 D/A, A-4 o C-E): lee el Problema Militar, da órdenes a las unidades de su repartición, coordina por la red "
               "de comunicaciones y confirma el turno.", "2 a 6, 8, 9"],
              ["Observador", "Ve todo el ejercicio sin poder cambiar nada (evaluadores, visitas).", "2 a 5, 9, 10"],
          ], [4.0 * cm, ANCHO_TEXTO - 6.0 * cm, 2.0 * cm]),
          H2("1.2 Convenciones"),
          Bul(["Los nombres de botones, pestañas y casillas van en <b>negrita</b>, tal como aparecen en pantalla.",
               "Los <b>círculos rojos numerados</b> de las capturas señalan las zonas que se explican en la tabla que las acompaña.",
               "Las capturas usan un <b>ejercicio de ejemplo</b> (unidades en el piedemonte andino y un grupo naval frente a Puerto Cabello): "
               "sus nombres y cifras no son datos reales.",
               "Un <b>turno</b> equivale a una hora simulada. Cada turno tiene una fase de <b>decisión</b> (los bandos dan órdenes) y una de "
               "<b>resolución</b> (el simulador calcula movimientos, detecciones y combates de todos a la vez).",
               "La <b>IA</b> (adversario automático) es el simulador conduciendo un bando: no hay alumnos detrás de esas unidades (capítulo 8)."]),
          H2("1.3 Novedades de esta versión"),
          Tbl(["Novedad", "Dónde se explica"], [
              ["El simulador sigue el TIEM: los puestos pasan a ser las reparticiones del Estado Mayor (Comandante, JEM, A-1, A-2, "
               "A-3, A-3 D/A, A-4 y C-E)", "6.2"],
              ["Pestaña TIEM: el Problema Militar Operativo de cada bando, redactado por el instructor o creado automáticamente", "6.15 y 7.15"],
              ["Evaluación del trabajo de Estado Mayor (nota de 1 a 20 y nota del instructor por documento) y legajo del TIEM "
               "en Word o para imprimir como PDF", "6.20 y 9.4"],
              ["Supervisión de la ejecución (Fase III): cuadro automático de diferencias con el plan, parte del turno, registro "
               "de causas y acciones correctivas, apreciaciones rápidas y órdenes fragmentarias", "6.19"],
              ["Decisión del Comandante, análisis previo y Plan de Operaciones con tareas que se emiten como órdenes del "
               "simulador desde la Orden de Operaciones", "6.18"],
              ["Apreciaciones de Estado Mayor (Fase I, Paso 2) de A-1, A-2, A-3, A-3 D/A, A-4 y C-E, confrontación de las F/A "
               "con las capacidades del enemigo y juego de guerra contra la IA", "6.17"],
              ["Apreciación inicial (Fase I, Paso 1): análisis de la misión, concepto del comandante, guía de planeamiento y "
               "formas de acción con el criterio APA, con Poder Relativo de Combate calculado y Word adjunto", "6.16 y 7.18"],
              ["Calendario de la operación: día D, hora H y fases (alistamiento, concentración y despliegue, ejecución, repliegue)", "6.15 y 7.16"],
              ["Quién conduce cada bando, a elección del instructor: un grupo de alumnos, el instructor o la IA", "7.17"],
              ["Cadena de objetivos: ulterior, asignados y materiales, con efecto deseado, indicador, plazo y «neutralizar»", "5.2 y 7.5"],
              ["Combate contra la IA: ejercicios listos, tres niveles del adversario y modo demostración", "Capítulo 8"],
              ["Ciclo de día y noche: de noche se detecta menos a simple vista y el mapa se oscurece", "8.6"],
              ["Hora simulada y periodo del día en la tarjeta Estado del escenario", "5.1"],
              ["Carreteras reales y botón «Seguir carreteras»", "4.10 y 6.5"],
              ["Catálogo propio: tipos de unidad de la AMB definidos por el instructor", "7.4"],
              ["Órdenes que no llegan a tiempo (comunicaciones degradadas)", "7.7"],
              ["Indicadores doctrinales, calificación de 1 a 20 y comparación de ejercicios", "9.4 y 9.5"],
              ["Fotos reales de las aeronaves, drones y buques, con el mismo encuadre", "6.3"],
              ["Satélite de Venezuela más nítido al acercar el mapa", "4.1"],
              ["Escenario del 3 de enero de 2026 (reconstrucción)", "7.2"],
              ["Infraestructura no militar: centrales, refinerías, comunicaciones y puentes que pesan en la operación", "4.11 y 7.14"],
              ["Pestaña Situación: cuadro radar con aviso automático de contactos, personal e infraestructura", "6.14"],
              ["Porcentaje de objetivos cumplidos de cada bando", "5.2"],
              ["Tiempo de todo el recorrido y hora de llegada de las órdenes de mover", "6.5"],
              ["Mapa ficticio con dos países inventados, País Azul y País Rojo, y su ejercicio", "4.12 y 7.2"],
          ], [ANCHO_TEXTO - 3.2 * cm, 3.2 * cm])]

    # ---------------------------------------------------------------- 2 acceso
    h += H1("2. Entrar al simulador")
    h += [H2("2.1 Abrir el simulador"),
          P("S.I.E.T.E. se usa desde el navegador (Chrome, Edge o Firefox). En el equipo que hace de servidor, el instructor lo pone en "
            "marcha con el acceso directo <b>S.I.E.T.E.</b> del Escritorio o con <b>SIETE.exe</b> de la carpeta portátil: se abre una "
            "ventana negra que muestra las direcciones del servidor. Cada estación del aula escribe esa dirección en su navegador, por "
            "ejemplo <font face='Mono'>http://192.168.1.10:8000/</font>. No hace falta internet."),
          Nota("La ventana negra del servidor debe quedar abierta mientras dure el ejercicio: al cerrarla, el simulador se detiene para todos.")]
    h += al_lado("acceso_login", "Pantalla de acceso.", [
        H2("2.2 Iniciar sesión"),
        pasos("Escriba su <b>Usuario</b> y su <b>Contraseña</b>.", f"Pulse {B('Ingresar')} (o Intro)."),
        P("Si la contraseña es incorrecta aparece un aviso en rojo. Tras <b>5 intentos fallidos</b> la cuenta se bloquea 5 minutos."),
        P("Al aprobarse el ingreso, el águila del S.I.E.T.E., posada con las alas recogidas, las abre, levanta el vuelo con dos "
          "batidas y viene hacia la pantalla (unos 3 segundos); cuando desaparece se muestra el simulador. Si en Windows está "
          "desactivada la opción <i>Efectos de animación</i>, se entra directo."),
        P("<b>Primer uso del simulador.</b> El administrador entra con el usuario <b>admin</b> y la contraseña inicial <b>siete1234</b>; "
          "el simulador le pedirá cambiarla de inmediato (2.4)."),
    ])
    h += al_lado("acceso_registro", "Solicitar una cuenta.", [
        H2("2.3 Solicitar una cuenta"),
        P("Los alumnos no necesitan que el instructor les cree la cuenta: la piden ellos mismos."),
        pasos(f"En la pantalla de acceso pulse {B('Solicitar una cuenta')}.",
              "Elija un <b>usuario</b> (letras, números, punto o guion, sin espacios) y escriba la <b>contraseña</b> dos veces (mínimo 8 caracteres).",
              "Elija el <b>rol</b> que le corresponde (alumno del bando azul o rojo, observador o instructor) y, si es alumno, su <b>repartición</b> (6.2).",
              f"Pulse {B('Enviar solicitud')}."),
        P("La cuenta queda <b>pendiente</b>: hasta que el instructor la apruebe (7.11) el simulador responde «Su solicitud de cuenta aún no "
          "fue aprobada». El instructor puede aprobarla con otro rol o repartición."),
    ])
    h += al_lado("acceso_clave", "Cambio de contraseña.", [
        H2("2.4 Primer acceso: cambiar la contraseña"),
        P("Cuando la contraseña es <b>provisional</b> (la inicial del administrador, o una que le puso el instructor al crear la cuenta o "
          "por un olvido), el simulador muestra esta pantalla al entrar y no deja hacer nada más hasta cambiarla."),
        pasos("Escriba la <b>contraseña actual</b> (la provisional).", "Escriba dos veces la <b>contraseña nueva</b> (mínimo 8 caracteres, distinta de la actual).",
              f"Pulse {B('Guardar contraseña')}: el simulador se abre normalmente."),
        P(f"{B('Cerrar sesión')} vuelve a la pantalla de acceso sin cambiarla."),
    ])
    h += al_lado("menu_perfil", "Menú del perfil.", [
        H2("2.5 Menú del perfil"),
        P("El botón redondo de la esquina superior derecha abre el menú del perfil: muestra su usuario, su rol y su repartición."),
        Bul([f"{B('Cambiar contraseña')}: la misma pantalla de 2.4; aquí se puede cancelar. Al cambiarla se cierran sus otras sesiones abiertas.",
             f"{B('Cerrar sesión')}: sale del simulador en ese equipo. Use siempre esta opción en equipos compartidos."]),
    ], ancho_img=7.5 * cm)
    h += [H2("2.6 Si no puede entrar"),
          Tbl(["Mensaje o situación", "Qué hacer"], [
              ["«Usuario o contraseña incorrectos»", "Revise mayúsculas y el teclado. Tras 5 intentos espere 5 minutos."],
              ["«Su solicitud de cuenta aún no fue aprobada»", "Avise al instructor: debe aprobarla en Consola → Usuarios."],
              ["«Demasiados intentos fallidos»", "La cuenta está bloqueada 5 minutos; luego vuelva a intentarlo."],
              ["Olvidó su contraseña", "El instructor le pone una nueva (provisional) en Consola → Usuarios → Clave; al entrar la cambia."],
              ["El administrador perdió la contraseña de admin", "En el servidor: doble clic en «Restablecer admin.cmd» (carpeta portátil) o "
               "<font face='Mono'>python -m app.restablecer_admin</font>; vuelve a ser siete1234."],
              ["La página no carga", "Compruebe la dirección y que la ventana del servidor siga abierta; el cortafuegos del servidor debe permitir el puerto 8000."],
          ], [6.0 * cm, ANCHO_TEXTO - 6.0 * cm])]

    # ---------------------------------------------------------------- 3 pantalla
    h += H1("3. La pantalla principal")
    h += [P("Todos los roles comparten la misma disposición. Lo que cambia es qué se ve y qué se puede hacer: el instructor tiene además la "
            "pestaña <b>Consola</b>; el alumno, los bloques para dar órdenes de su repartición.")]
    h += figura("pantalla_general", "Pantalla del instructor con el ejercicio de ejemplo.")
    h += [leyenda([
        ("1", "Cabecera", "Escenario activo, botones de escenario, conexión, reloj, videowall, informe y perfil (3.1)."),
        ("2", "Panel izquierdo", "Pestaña Fuerzas (orden de batalla, ficha de la unidad, órdenes, misiones, cola), pestaña Situación "
                                    "(cuadro radar, personal e infraestructura, 6.14) y, para el instructor, Consola."),
        ("3", "Mapa táctico", "Terreno, unidades, rutas, ataques, gráficos, objetivos, zonas de clima y de interferencia (capítulo 4)."),
        ("4", "Panel derecho", "Estado del escenario, objetivos y puntaje, capas, comunicaciones y alertas (capítulo 5)."),
        ("5", "Barra inferior", "«Estoy listo» (alumnos) o «Resolver y avanzar turno» (instructor) y el estado de cada bando (3.2)."),
        ("6", "Regla", "Mide distancias y rumbos sobre el mapa (4.5)."),
        ("7", "Gráficos tácticos", "Líneas de fase, ejes de avance, zonas de reunión y puntos de control (4.6)."),
    ])]
    h += [H2("3.1 La cabecera")]
    h += figura("cabecera", "Cabecera del instructor.")
    h += [leyenda([
        ("1", "Escenario", "Lista de escenarios a los que tiene acceso: elija con cuál trabajar. La casilla «archivados» muestra también los archivados."),
        ("2", "Nuevo", "Crea un escenario vacío (instructor)."),
        ("3", "Desde plantilla…", "Crea un escenario con unidades y objetivos ya cargados (7.2)."),
        ("4", "Guardar como plantilla…", "Guarda la situación actual para reutilizarla (7.2)."),
        ("5", "Conexión", "Punto verde: conectado y recibiendo cambios al instante. Rojo: sin conexión (se reconecta solo)."),
        ("6", "Reloj", "Hora del turno o, si el instructor fijó un límite, la cuenta regresiva de la fase de decisión."),
        ("7", "Videowall", "Mapa a pantalla completa para la pantalla grande del aula (7.13). Tecla V."),
        ("8", "Informe", "Informe posterior al ejercicio (capítulo 9)."),
        ("9", "Perfil", "Usuario, rol y repartición; cambiar contraseña y cerrar sesión (2.5)."),
    ]),
          P("En pantallas anchas (más de 1 450 píxeles) la barra de título también muestra el <b>turno</b>, la <b>hora simulada</b>, el "
            "<b>calendario de la operación</b> (por ejemplo «D+1 · H+5 · Ejecución», 6.15) y el <b>bando</b> con que trabaja. En cualquier "
            "pantalla, la hora, el periodo del día y el calendario están en la tarjeta <b>Estado del escenario</b> (5.1).")]
    h += [H2("3.2 La barra inferior")]
    h += figura("barra_inferior", "Barra inferior de un alumno: botón para confirmar el turno y estado de ambos bandos.")
    h += [Bul([f"<b>Alumnos:</b> {B('Estoy listo - confirmar órdenes')} avisa que su bando terminó de dar órdenes (lo pueden pulsar el "
               "Comandante y el JEM). Si después emite o cancela una orden, el «listo» se anula y hay que volver a confirmarlo.",
               f"<b>Instructor:</b> {B('Resolver y avanzar turno')} resuelve el turno aunque algún bando no esté listo (7.12).",
               "A la derecha, el estado de cada bando: <b>PENDIENTE</b> (dando órdenes) o <b>LISTO</b>. <b>IA · LISTO</b> indica que ese bando "
               "lo conduce el simulador y ya dio sus órdenes del turno (capítulo 8)."])]

    # ---------------------------------------------------------------- 4 mapa
    h += H1("4. El mapa")
    h += [H2("4.1 Moverse por el mapa"),
          Bul(["<b>Desplazar:</b> arrastre el mapa con el ratón.", "<b>Acercar o alejar:</b> rueda del ratón o los botones <b>+</b> y <b>−</b> de la esquina inferior derecha.",
               "<b>Coordenadas y terreno:</b> el recuadro de la esquina superior izquierda muestra la latitud, la longitud y el tipo de terreno bajo el cursor.",
               "<b>Ir a una unidad:</b> haga clic en su nombre en el orden de batalla; el mapa se centra en ella.",
               "<b>Ir a una región:</b> en la tarjeta Capas, los botones «Venezuela y vecinos» y «América» encuadran cada región del mapa.",
               "<b>Nitidez:</b> sobre Venezuela la foto satelital llega a unos 19 m por píxel: al acercar se distinguen calles, pistas y plataformas."]),
          H2("4.2 Las unidades según el zoom"),
          P("Para que las unidades no se encimen ni tapen el mapa, su tamaño depende de lo cerca que se mire. De lejos se ven pequeñas y sin "
            "nombre (el nombre aparece al pasar el cursor); al acercar crecen, aparecen los nombres (zoom 8) y cada unidad desplegada muestra "
            "el <b>anillo de su alcance</b> (zoom 9): azul las propias, rojo las enemigas a la vista. Los anillos se pueden ocultar en "
            "Capas → «Alcance de las unidades»."),
          ]
    h += figura("mapa_lejos", "El mapa de lejos: unidades pequeñas y sin rótulos.", ancho=ANCHO_TEXTO * 0.82)
    h += figura("mapa_cerca", "Al acercar: nombres, miniaturas más grandes y anillos de alcance.", ancho=ANCHO_TEXTO * 0.82)
    h += [P("Cada unidad se dibuja con una <b>miniatura 3D</b> de su clase (las aeronaves y los buques giran según su rumbo) con el color de "
            "su bando. Al seleccionar una unidad se ven, a cualquier zoom, tres anillos: <b>alcance de fuego</b> (amarillo), <b>detección</b> "
            "(turquesa punteado) y <b>avance máximo en un turno</b> (celeste).")]
    h += al_lado("mapa_ficha", "Ficha rápida al pasar el cursor.", [
        H2("4.3 Ficha rápida"),
        P("Al pasar el cursor sobre una unidad aparece una ficha con su nombre, clase, terreno, fuerza y, en las aeronaves, la foto del modelo. "
          "Un clic la <b>selecciona</b>: su ficha completa aparece en el panel izquierdo (6.3)."),
    ], ancho_img=8.0 * cm)
    h += al_lado("capas", "Tarjeta Capas.", [
        H2("4.4 Capas"),
        P("En la tarjeta <b>Capas</b> del panel derecho se elige qué se dibuja:"),
        Bul([f"{B('Satélite')} / {B('Relieve')}: fondo con foto satelital o con el relieve coloreado por tipo de terreno (bosque, pantano, montaña, agua).",
             "<b>Venezuela y vecinos</b>, <b>América</b>: encuadran cada región.",
             "<b>Terreno</b>, <b>Cobertura (detección)</b>, <b>Niebla de guerra</b>, <b>Unidades</b>, <b>Alcance de las unidades</b>, "
             "<b>Últimos contactos</b>, <b>Gráficos tácticos</b>, <b>Límites y poblaciones</b>, <b>Bases aéreas y aeródromos</b>, "
             "<b>Plano de los aeródromos</b>, <b>Objetivos</b>, <b>Guerra electrónica</b>, <b>Meteorología</b> y <b>Misiones aéreas</b>: "
             "cada casilla muestra u oculta esa información.",
             "<b>Cobertura (detección)</b> dibuja lo que ve cada sensor del bando. Los radares (y los sensores que emiten) "
             "muestran su alcance real según el relieve: el área azul es hasta dónde ven una aeronave a cota media y la "
             "línea naranja, a baja cota (rasante); las entradas son las sombras de las montañas. El resto, con un círculo.",
             "<b>Símbolos militares (APP-6) en lugar de miniaturas</b>: cambia las miniaturas por la simbología militar; se recuerda en ese equipo."]),
    ])
    h += figura("mapa_relieve", "Fondo de relieve: el color indica el tipo de terreno, que afecta al movimiento, la defensa y la detección.", ancho=ANCHO_TEXTO * 0.82)
    h += [H2("4.5 Regla: distancias y rumbos"),
          pasos(f"Pulse {B('Regla')} (arriba a la izquierda del mapa).", "Haga clic en el punto de partida y en cada punto siguiente.",
                "La regla muestra la distancia y el rumbo de cada tramo y el total.", "Doble clic o Esc para terminar; <b>Limpiar</b> la borra.")]
    h += figura("mapa_regla", "Regla con dos tramos.", ancho=ANCHO_TEXTO * 0.82)
    h += [H2("4.6 Gráficos tácticos"),
          P("La barra <b>Gráficos tácticos</b> permite trazar sobre el mapa los elementos del plan, que ve todo su bando (los del instructor, "
            "quien él elija)."),
          pasos("Escriba la <b>etiqueta</b> (por ejemplo «LF ALFA»).",
                f"Elija la herramienta: {B('Línea de fase')}, {B('Eje de avance')} (flecha), {B('Zona de reunión')} (polígono) o {B('Punto de control')}.",
                "Haga clic en el mapa para cada punto; doble clic o clic en el último punto para terminar (Esc cancela).")]
    h += figura("mapa_graficos", "Trazado de un eje de avance.", ancho=ANCHO_TEXTO * 0.82)
    h += [H2("4.7 Meteorología en el mapa"),
          P("El clima general aparece en la tarjeta Estado del escenario. Además, el instructor puede colocar <b>zonas</b> de nubes, lluvia o "
            "tormenta, que ambos bandos ven en el mapa con su nombre y una flecha si se desplazan. En cada punto rige el peor clima entre el "
            "general y las zonas que lo cubren: reduce la detección, la velocidad y la eficacia de los ataques aéreos.")]
    h += figura("mapa_meteo", "Una tormenta sobre los Andes y un frente de lluvia que se desplaza al este.", ancho=ANCHO_TEXTO * 0.82)
    h += [H2("4.8 Bases aéreas y aeródromos"),
          P("La capa <b>Bases aéreas y aeródromos</b> muestra las bases de Venezuela, las de los países vecinos y unos 1 300 aeródromos de toda "
            "América. Al acercarse (zoom 11 en adelante) cada uno se dibuja con su <b>plano real</b>: pistas con su numeración y marcas, calles "
            "de rodaje, plataformas, hangares y edificios. Si una base del ejercicio ocupa el aeródromo, sus aviones se ven estacionados en la "
            "plataforma y los daños aparecen como cráteres en la pista y, si queda inutilizada, cruces amarillas y el rótulo «PISTA INOPERATIVA»."),
          P("Al hacer clic en un aeródromo se ven sus datos; el instructor puede colocar allí una base azul o roja con un clic.")]
    h += figura("mapa_aerodromo", "Aeropuerto de Barinas al zoom 15, ocupado por una base del ejercicio: aviones en la plataforma y cráteres en la pista.", ancho=ANCHO_TEXTO * 0.82)
    h += [H2("4.9 El relieve: lo que ven los sensores"),
          P("Las montañas y la curvatura de la Tierra <b>ocultan</b>: un radar, un buque o un observador solo detectan lo que tienen en su "
            "línea de vista. Una aeronave que vuela baja detrás de una sierra no aparece en el radar enemigo, y lo mismo vale para la "
            "escucha electrónica y para la antiaérea, que no dispara a lo que no ve. Un radar en una cumbre ve mucho; uno en un valle, poco."),
          P("Al <b>seleccionar un sensor</b> (radar, antiaérea con radar, buque) el mapa dibuja su <b>cobertura real</b>: en turquesa, hasta "
            "dónde ve aeronaves a cota media (1 500 m); en naranja, a baja cota (rasante, 60 m). Las entradas del contorno son las sombras "
            "de las montañas. Úsela para ubicar los radares propios y para planificar por dónde entrar sin ser visto.")]
    h += figura("cobertura_radar", "Cobertura del «Radar Rojo», en un valle al pie de los Andes: a cota media ve lejos hacia el llano, pero la "
                "montaña le corta la vista al norte y al oeste; a baja cota apenas ve unos kilómetros.", ancho=ANCHO_TEXTO * 0.82)
    h += [H2("4.10 Carreteras"),
          P("Al acercar el mapa aparecen las <b>carreteras reales</b> de Venezuela (OpenStreetMap y Natural Earth), en amarillo: las troncales "
            "más gruesas y las locales más finas. No son un adorno: por carretera las unidades terrestres avanzan más rápido (×1,25 en las "
            "locales y ×1,5 en las troncales) y cruzan los ríos por sus <b>puentes</b>, aunque un vehículo pesado no podría vadearlos."),
          P(f"Para aprovecharlas al mover, use {B('Seguir carreteras')} (6.5): el simulador traza el camino más rápido por la red vial.")]
    h += figura("mapa_carreteras", "Carreteras alrededor de Barinas: la troncal que cruza la ciudad y las vías que salen hacia el piedemonte.",
                ancho=ANCHO_TEXTO * 0.82)
    h += [H2("4.11 Infraestructura en el mapa"),
          P("La capa <b>Infraestructura</b> muestra con un icono de color la infraestructura crítica real de Venezuela, ubicada con "
            "OpenStreetMap: las principales <b>centrales termoeléctricas</b> (rayo naranja) e <b>hidroeléctricas</b> (gota celeste) —Guri, "
            "Caruachi, Macagua, Tocoma, Planta Centro, Tacoa, Termozulia…—, las <b>refinerías</b> (llama) de Amuay, Cardón, El Palito y "
            "Puerto La Cruz, los <b>centros de comunicaciones</b> (antena) como el cerro El Volcán y las estaciones terrenas de control "
            "satelital, y los <b>puentes estratégicos</b> (puente gris): el Rafael Urdaneta, los del Orinoco y del Caroní, el María "
            "Nieves y los pasos fronterizos con Colombia."),
          P("Es una capa de referencia: la instalación solo forma parte del ejercicio si el instructor la coloca (7.14). Ya en el "
            "ejercicio se ve con su miniatura (central con chimeneas, presa, refinería, antena o puente) en el color de su bando.")]
    h += [H2("4.12 El mapa ficticio: País Azul y País Rojo"),
          P("Para ejercicios que no deben involucrar a ningún país real, el simulador trae un <b>mapa ficticio</b> completo: la "
            "<b>País Azul</b> (al oeste) y la <b>País Rojo</b> (al este) comparten una masa de tierra del tamaño "
            "de un país, ubicada en pleno océano Atlántico para que no se cruce con ningún mapa real. Tiene todo lo que el motor usa de "
            "un mapa verdadero, con la misma resolución que el de Venezuela (unos 300 m por píxel):"),
          Bul(["<b>Relieve</b>: una cordillera de más de 3 500 m al oeste, una serranía costera al norte, un macizo con mesetas "
               "escalonadas al sureste, llanos en el centro, costas con golfos, penínsulas e islas, y el fondo marino.",
               "<b>Agua</b>: ríos que nacen en las montañas y bajan por el relieve hasta el mar (los grandes, con nombre), un lago "
               "natural, lagunas y tres <b>embalses</b> con su represa y su central hidroeléctrica.",
               "<b>Cobertura</b>: bosques, sabanas, pantanos en las zonas bajas y las costas, y 28 ciudades con su población.",
               "<b>Carreteras</b>: troncales y carreteras secundarias entre las ciudades, con puentes donde cruzan los ríos y pasos "
               "de frontera; las unidades las aprovechan igual que en el mapa real.",
               "<b>Frontera y provincias</b>, <b>infraestructura</b> (centrales, refinerías, centros de comunicaciones y puentes, en la "
               "capa Infraestructura) y foto satelital sintética además del relieve."]),
          P("Para ir al mapa, use el botón <b>Teatro ficticio (País Azul y País Rojo)</b> de la tarjeta Capas. Para ejercitar en él, "
            f"cree el escenario {B('Desde plantilla…')} → <b>País Azul contra País Rojo (mapa ficticio)</b> (7.2), o coloque unidades "
            "allí como en cualquier otra región. En <i>Identidad nacional</i> (7.7) están las dos repúblicas ficticias.")]
    h += figura("mapa_ficticio", "El mapa ficticio completo en relieve: País Azul al oeste y País Rojo al este, con su frontera, "
                "ciudades, carreteras, ríos, lagos y la cordillera occidental.", ancho=ANCHO_TEXTO * 0.9)
    h += figura("mapa_ficticio_cerca", "Vista satelital sintética cerca de Capital Azul, la capital de País Azul.", ancho=ANCHO_TEXTO * 0.82)
    h += figura("mapa_infraestructura", "Infraestructura en el piedemonte andino: la hidroeléctrica José Antonio Páez y un puente del bando azul "
                "y una central del bando rojo en el ejercicio; a la derecha, iconos de la capa (Masparro y otras centrales).",
                ancho=ANCHO_TEXTO * 0.82)

    # ---------------------------------------------------------------- 5 panel derecho
    h += H1("5. El panel derecho")
    h += al_lado("panel_der_arriba", "Estado del escenario, objetivos y capas.", [
        H2("5.1 Estado del escenario"),
        P("Clima general y su visibilidad, la <b>hora simulada</b>, el <b>calendario</b> de la operación (día D, hora H y fase, si el "
          "instructor lo fijó; 6.15) (con el ciclo de día y noche, también si es de <b>día</b>, "
          "<b>crepúsculo</b> o <b>noche</b>, 8.6), cómo afecta el clima al movimiento terrestre y a los ataques aéreos, la <b>fase</b> del turno (Decisión o "
          "Resolución, y si el escenario está activo, en pausa o finalizado) y el <b>modo</b>: con o sin azar en los combates, y resolución "
          "manual (la decide el instructor) o automática (cuando ambos bandos están listos)."),
        H2("5.2 Objetivos y puntaje"),
        P("El marcador de cada bando (puntos por objetivos más un punto por cada 10 de fuerza infligida al enemigo) y la lista de "
          "objetivos de su bando con su avance: ocupar una zona varios turnos, destruir o <b>neutralizar</b> una unidad (bajar su fuerza "
          "hasta un porcentaje), proteger una propia o lograr un <b>efecto</b>. Cada bando ve solo los suyos."),
        P("Los objetivos forman la <b>cadena del TIEM</b> y se muestran como un árbol: arriba el <b>objetivo ulterior</b> (el del Teatro "
          "de Operaciones), debajo los <b>objetivos asignados</b> al componente aéreo y, dentro de cada uno, los <b>objetivos materiales</b> "
          "que se atacan o protegen en el terreno. Un objetivo asignado se cumple cuando se cumple el porcentaje indicado de los que "
          "dependen de él («1/2 cumplidos»). Bajo cada objetivo se leen su <b>efecto deseado</b> y el <b>indicador</b> con que se mide; "
          "si tiene <b>plazo</b>, falla al llegar ese turno sin haberse cumplido."),
    ])
    h += al_lado("objetivos_avance", "Objetivos y puntaje, con el porcentaje cumplido.", [
        P("Debajo del marcador, una barra muestra el <b>porcentaje de objetivos cumplidos</b>: «1 de 3 cumplidos (33 %)». El alumno ve "
          "la de su bando; el instructor y el observador, la de los dos. Al pasar el cursor se ven también los fallidos y los pendientes. "
          "El mismo porcentaje está en el informe y en el indicador doctrinal «Cumplimiento de objetivos» (9.4)."),
    ], ancho_img=6.6 * cm)
    h += al_lado("panel_der_abajo", "Comunicaciones y alertas.", [
        H2("5.3 Comunicaciones"),
        P("Chat de texto del ejercicio. El alumno elige el canal: <b>Red del bando</b> (todas las reparticiones de su bando) o <b>Al mando "
          "(instructor)</b>. El instructor escribe a todos o a un bando."),
        pasos("Elija el canal.", f"Escriba el mensaje y pulse {B('Enviar')} (o Intro)."),
        P("Si el instructor activó las <b>comunicaciones simuladas</b>, los mensajes llegan con demora y algunos se pierden, como en una red "
          "real degradada; el aviso bajo el chat lo indica."),
        H2("5.4 Alertas"),
        P("Los sucesos importantes del turno para su bando: combates, despegues y aterrizajes, objetivos cumplidos, bases sin existencias, "
          "misiles derribados, informes de inteligencia y eventos del instructor. El contador indica las nuevas."),
    ])

    # ---------------------------------------------------------------- 6 alumno
    h += H1("6. Guía del alumno")
    h += [H2("6.1 Su pantalla")]
    h += figura("alumno_pantalla", "Pantalla de un alumno del bando azul (Comandante).")
    h += [leyenda([
        ("1", "Escenario y bando", "El escenario en el que participa y su bando. Solo ve los escenarios que el instructor le asignó."),
        ("2", "Orden de batalla", "Sus unidades por rama y las enemigas que su bando detecta."),
        ("3", "Mapa", "Sus unidades, el enemigo detectado (niebla de guerra) y los últimos contactos."),
        ("4", "Panel derecho", "Estado, objetivos de su bando, capas, comunicaciones y alertas."),
        ("5", "Estoy listo", "Confirma las órdenes de su bando para el turno (6.12)."),
    ])]
    h += [H2("6.2 Su repartición del Estado Mayor"),
          P("Como lo establece el TIEM (Trabajo Integral de Estado Mayor), cada bando trabaja como el Estado Mayor de un componente aéreo "
            "y cada alumno ocupa una <b>repartición</b>. Todos ven lo mismo (la misma niebla de guerra, la misma red y el mismo Problema "
            "Militar); cambia <b>qué unidades conducen</b>. El bloque <b>Mi repartición</b> lo recuerda y el simulador rechaza (explicando a "
            "quién corresponde) cualquier orden fuera de su área, lo que obliga a coordinar como en un Estado Mayor real."),
          Tbl(["Repartición", "Conduce", "Confirma «listo»"], [
              ["CMDTE · Comandante", "Todo el bando: decide y puede dar cualquier orden", "Sí"],
              ["JEM · Jefe de Estado Mayor", "Coordina a las reparticiones; reúne sus funciones (puede dar cualquier orden)", "Sí"],
              ["A-1 · Personal", "No ordena unidades: sigue los efectivos, las bajas y los reemplazos (pestaña Situación) y prepara la "
               "apreciación de personal", "No"],
              ["A-2 · Inteligencia", "El reconocimiento: unidades y drones de reconocimiento; sigue los contactos, el cuadro radar y las "
               "capacidades del enemigo", "No"],
              ["A-3 · Operaciones", "La maniobra: despegues desde las bases, caza, ataque, helicópteros, drones armados, cisternas, fuerzas "
               "de superficie (terrestres y navales) y lanzadores de misiles", "No"],
              ["A-3 D/A · Defensa Aérea", "Radares (encender o apagar), artillería y misiles antiaéreos, alerta temprana y la caza de "
               "intercepción con sus despegues", "No"],
              ["A-4 · Logística", "Convoyes de abastecimiento, depósitos e ingenieros (puentes y vados)", "No"],
              ["C-E · Comunicaciones y Electrónica", "La guerra electrónica: escucha e interferencia desde tierra y aviones de guerra "
               "electrónica", "No"],
          ], [4.0 * cm, ANCHO_TEXTO - 6.8 * cm, 2.8 * cm]),
          P("La caza la pueden conducir la A-3 (escolta, superioridad aérea) y la A-3 D/A (intercepción). Si el bando tiene un solo alumno, "
            "ese alumno es el Comandante y conduce todo. Las cuentas creadas antes de esta versión pasaron solas a la repartición "
            "equivalente: EM → Comandante, A2 → A-2, A3 y A5 → A-3, A4 → A-4.")]
    h += al_lado("alumno_secciones", "Bloques del panel izquierdo de un alumno.", [
        P("En la pestaña de su panel izquierdo, debajo del orden de batalla y de la ficha de la unidad, encuentra:"),
        leyenda([("1", "Mi repartición", "Su repartición y lo que puede conducir."),
                 ("2", "Aviación", "Enviar aeronaves o drones desde una base o un portaaviones (6.9)."),
                 ("3", "Misiones aéreas", "Planificar misiones y ver las del bando (6.9)."),
                 ("4", "Nueva orden", "La orden para la unidad seleccionada (6.4).")]),
    ])
    h += al_lado("oob", "Orden de batalla.", [
        H2("6.3 Orden de batalla y ficha de la unidad"),
        P("El <b>orden de batalla</b> agrupa las unidades por rama (infantería, blindados, artillería, aviación, naval, bases) con su estado: "
          "Operativa, Orden: mover, En base, Patrullando, A bordo… El buscador filtra por nombre, clase o modelo."),
        P("Un clic en una unidad la selecciona y centra el mapa en ella. Las unidades enemigas aparecen solo mientras su bando las detecta."),
    ])
    h += al_lado("ficha_unidad", "Ficha de la unidad seleccionada.", [
        P("La <b>ficha</b> de la unidad seleccionada muestra:"),
        Bul(["Una <b>foto de referencia</b> de la aeronave, el dron o el buque (con su autor y licencia), o su ilustración.",
             "<b>Fuerza</b>, <b>combustible</b> y <b>munición</b> en barras (en rojo cuando están bajos).",
             "Clase, terreno donde está, velocidad, alcance de fuego, detección, autonomía, movilidad y el clima local.",
             "La orden pendiente, si tiene una.",
             "En bases y depósitos, sus <b>existencias</b>; en las bases aéreas, el daño de pista, plataforma y depósito."]),
        P("De una unidad enemiga solo se ve lo que su bando sabe: posición, clase y bando."),
    ])
    h += al_lado("ficha_acciones", "Acciones inmediatas en la ficha.", [
        P("<b>Acciones inmediatas.</b> Algunas unidades tienen botones en la ficha que rigen al instante, sin esperar el turno:"),
        Bul([f"{B('Apagar radar')} / {B('Encender radar')} (radares, antiaérea guiada por radar, destructores): apagado solo ve 5 km, pero la "
             "escucha enemiga no lo puede localizar (A-3 D/A).",
             f"{B('Retener el fuego')} / {B('Fuego libre')} (antiaérea, destructores): con fuego libre dispara sola contra la aeronave enemiga "
             "más cercana a su alcance."]),
    ])
    h += [H2("6.4 Dar una orden: los pasos de siempre"),
          pasos("Seleccione la unidad (en el orden de batalla o con un clic en el mapa).",
                "En <b>Nueva orden</b>, elija el tipo de orden: los botones que aparecen dependen de la unidad y de su repartición.",
                "Complete la orden (puntos en el mapa, objetivo, base, etc.). El simulador le muestra una vista previa.",
                f"Pulse {B('Emitir orden')}. La orden aparece en la <b>cola de órdenes</b> como PENDIENTE."),
          Nota("Cada unidad tiene una sola orden por turno: si emite otra, reemplaza a la anterior. Las órdenes se cumplen al resolverse el turno."),
          Tbl(["Orden", "Unidades", "Cómo se completa"], [
              ["Mover", "Toda unidad que se mueve", "Clics en el mapa para cada punto de paso (waypoint)."],
              ["Atacar", "Unidades con armas", "Elegir el objetivo enemigo detectado en la lista o con un clic sobre él."],
              ["Apoyar", "Unidades con armas", "Elegir una unidad propia a su alcance: mejora su ataque y su defensa."],
              ["Construir", "Ingenieros", "Elegir vado o puente y hacer clic sobre un río a menos de 5 km."],
              ["Patrullar", "Aeronaves", "Clic en el punto de patrulla."],
              ["Aterrizar", "Aeronaves en vuelo", "Elegir la base o portaaviones propio de destino."],
              ["Interferir", "Guerra electrónica", "Clic en el centro de la zona a interferir."],
              ["Lanzar misiles", "Buques y baterías con misiles", "Elegir el blanco y cuántos misiles."],
              ["Embarcar / Desembarcar", "Tropas y transportes", "Elegir el transporte / marcar la ruta hasta el punto de desembarco."],
          ], [3.2 * cm, 4.6 * cm, ANCHO_TEXTO - 7.8 * cm])]
    h += [H2("6.5 Mover")]
    h += figura("orden_mover", "Orden de mover con tres puntos de paso: la línea muestra la ruta y el círculo, dónde termina el turno.")
    h += [pasos("Seleccione la unidad y pulse <b>Mover</b>.", "Haga clic en el mapa para cada punto de paso (W1, W2…).",
                "Lea la vista previa: hasta dónde llega en este turno según el terreno, los ríos, el clima y el combustible.",
                f"Pulse {B('Emitir orden')}. {B('Limpiar waypoints')} empieza de nuevo."),
          P(f"{B('Seguir carreteras')} toma el último punto como destino y traza solo el camino más rápido por las carreteras y sus "
            "puentes (en la capa de carreteras, al acercar el mapa). Por carretera las unidades terrestres avanzan más y cruzan los ríos "
            "por los puentes reales."),
          P("<b>Tiempo del recorrido.</b> Además de dónde termina este turno, la vista previa calcula <b>cuánto tarda la unidad en hacer "
            "toda la ruta</b> —con el mismo terreno, carreteras, ríos, clima y peso que el movimiento real—, cuántos turnos le lleva y a qué "
            "hora simulada llega: «Recorrido completo: 87 km en 3 h 20 min (4 turnos); llegada estimada 14:20h». En el mapa, el último "
            "punto lleva el rótulo «ETA». Si en la ruta hay un río que la unidad no puede cruzar, lo avisa; si el combustible no alcanza, "
            "indica para cuántos kilómetros da."),
          P("Si la ruta es más larga que lo que la unidad avanza en un turno, sigue en los turnos siguientes. Los vehículos pesados solo cruzan "
            "los ríos por un puente o vado.")]
    h += [H2("6.6 Atacar y apoyar")]
    h += figura("orden_atacar", "Orden de atacar: la artillería elige como objetivo a la infantería roja.")
    h += [pasos("Seleccione la unidad y pulse <b>Atacar</b>.", "Elija el objetivo en la lista (solo aparecen los enemigos detectados) o haga clic sobre él en el mapa.",
                "Compruebe en la ayuda si está a su alcance.", f"Pulse {B('Emitir orden')}."),
          P("Al atacar una base aérea se puede elegir <b>qué se ataca de la base</b>: la pista, la plataforma o el depósito. <b>Apoyar</b> funciona "
            "igual, pero eligiendo una unidad propia cercana.")]
    h += [H2("6.7 Varias unidades a la vez")]
    h += figura("seleccion_multiple", "Tres unidades seleccionadas con Ctrl+clic reciben la misma orden de mover en formación.")
    h += [Bul(["Mantenga <b>Ctrl</b> (o Mayúsculas) y haga clic en otras unidades propias, en el orden de batalla o en el mapa, para sumarlas o quitarlas.",
               "La orden que emita se da a todas las seleccionadas.",
               "Con <b>Mantener la formación</b>, al moverse cada una conserva su posición relativa a las demás.",
               f"{B('Dejar solo una')} vuelve a la selección normal."])]
    h += al_lado("orden_construir", "Orden de construir (ingenieros).", [
        H2("6.8 Ingenieros: puentes y vados"),
        pasos("Seleccione los ingenieros y pulse <b>Construir</b>.", "Elija <b>Vado</b> (4 turnos, precario) o <b>Puente</b> (12 turnos).",
              "Haga clic sobre el río, a menos de 5 km de los ingenieros.", f"Pulse {B('Emitir orden')}."),
        P("Mientras dura la obra los ingenieros quedan trabajando. Terminada, los vehículos pesados de ambos bandos pueden cruzar por ella."),
    ])
    h += [H2("6.9 Aviación")]
    h += figura("aviacion_enviar", "Enviar aeronaves: fichas de los modelos con foto, prestaciones y armamento.")
    h += [P("<b>Enviar aeronaves o drones</b> (A-3 o A-3 D/A):"),
          pasos(f"Pulse {B('Enviar aeronaves o drones…')} en el bloque Aviación.", "Elija el modelo en las fichas (foto, velocidad, alcances, autonomía, armamento).",
                "Elija la <b>base de origen</b> (o un portaaviones), la <b>cantidad</b> (1 a 8) y, si quiere, un <b>indicativo</b>.",
                f"Pulse {B('Enviar a despegar')}: el grupo aparece junto a la base al resolverse el turno y recibe órdenes desde el siguiente."),
          P("Una base muy dañada o sin existencias no puede lanzar aviones. Desde un portaaviones solo despegan helicópteros, drones y cazas embarcados.")]
    h += figura("orden_patrullar", "Patrulla: el grupo vuela al punto, se mantiene en la zona e intercepta a los aviones enemigos que detecte.")
    h += [Bul(["<b>Patrullar</b> (la repartición que conduce la aeronave): clic en el punto de patrulla. Gasta combustible cada turno y, con combustible crítico, regresa sola.",
               "<b>Aterrizar</b>: elija la base o portaaviones de destino. En tierra tarda 2 turnos en reabastecer y rearmar; después cualquier orden de vuelo es el despegue."]),
          ]
    h += al_lado("perfil_vuelo", "Perfil de vuelo en la ficha de una aeronave.", [
        H3("Perfil de vuelo"),
        P("Cada aeronave vuela en un <b>perfil</b>, que se elige en su ficha con los botones <b>Alto</b>, <b>Medio</b> o <b>Rasante</b> "
          "(la repartición que conduce la aeronave). El cambio rige de inmediato, y el mapa anota «alto» o «rasante» bajo el avión."),
        Tbl(["Perfil", "Ventajas", "Costos"], [
            ["Alto (6 000 m)", "Fuera del alcance de la antiaérea portátil; gasta 15 % menos.", "Lo ven los radares desde muy lejos."],
            ["Medio (1 500 m)", "Equilibrado; es el de siempre.", "Lo ocultan solo las montañas altas."],
            ["Rasante (60 m)", "Se esconde tras el relieve y bajo el horizonte del radar.", "Gasta 30 % más; la antiaérea portátil le pega más."],
        ], [2.6 * cm, 3.6 * cm, 3.6 * cm], tam=7.8),
        P("Los helicópteros vuelan medio o rasante; los misiles de crucero, siempre rasantes. Vea la cobertura de los radares en 4.9."),
    ], ancho_img=6.0 * cm)
    h += [H3("Misiones aéreas"),
          P("Una <b>misión</b> es un plan que el grupo cumple solo, turno tras turno, sin que haya que darle órdenes cada vez: un rol y una ruta de puntos.")]
    h += figura("mision_planificar", "Planificador de misiones: interdicción con un grupo existente; la ruta se marca con clics en el mapa.")
    h += [pasos(f"Pulse {B('Planificar misión…')}.", "Elija quién la vuela: <b>un grupo existente</b> (solo aparecen los que su repartición conduce) o un <b>despegue desde una base</b> en un turno futuro (A-3 o A-3 D/A), con modelo y cantidad.",
                "Elija el <b>rol</b>: CAP, interdicción, CAS, SEAD, reconocimiento, guerra electrónica, traslado o escolta.",
                "Haga clic en el mapa para cada punto de la ruta y elija su tipo: <b>paso</b>, <b>órbita</b> (N turnos) o <b>blanco</b>.",
                "Elija dónde aterriza al final y, si quiere, una <b>escolta del paquete</b>.",
                f"Revise la estimación de horario y combustible y los avisos; pulse {B('Crear misión')}."),
          Tbl(["Rol", "Qué hace"], [
              ["CAP", "Patrulla aérea de combate: en la órbita intercepta aviones enemigos."],
              ["Interdicción", "Ataca el blanco; si se movió y se lo sigue viendo, lo persigue."],
              ["CAS", "Apoyo aéreo cercano: en la órbita ataca cada turno al enemigo de superficie más cercano."],
              ["SEAD", "Supresión de defensas: prioriza radares y antiaérea que emiten."],
              ["Reconocimiento", "Vuela la ruta sin atacar."], ["Guerra electrónica", "Interfiere desde la órbita."],
              ["Traslado", "Vuela a otra base y aterriza."], ["Escolta", "Acompaña a otra misión y la protege de los cazas enemigos."],
          ], [3.4 * cm, ANCHO_TEXTO - 3.4 * cm])]
    h += al_lado("misiones_lista", "Lista de misiones del bando.", [
        P("La lista <b>Misiones aéreas</b> muestra cada misión de su bando con su estado (programada, en curso, cumplida, abortada) y lo que "
          "está haciendo. Una orden directa al grupo reemplaza la misión; la «×» la cancela."),
        P(f"{B('Cronograma')} abre el horario de todas las misiones."),
    ], ancho_img=7.0 * cm)
    h += figura("cronograma", "Cronograma (flow sheet): vuelo, órbitas, ataques y aterrizajes de cada misión; la línea roja es el turno actual.")
    h += [H2("6.10 Fuerzas navales y misiles")]
    h += figura("naval_misiles", "Lanzar misiles: el destructor elige como blanco la fragata enemiga y la cantidad de misiles de la salva.")
    h += [pasos("Seleccione el buque (fragata, destructor, submarino) o la batería costera y pulse <b>Lanzar misiles</b>.",
                "Elija el blanco (en tierra o en el mar, detectado) y cuántos misiles tiene la salva (cada uno gasta el 25 % de la munición).",
                f"Pulse {B('Emitir orden')}. La salva vuela sola hacia el blanco; la antiaérea y los cazas enemigos pueden derribarla."),
          P("Las unidades navales se mueven solo por el agua. El portaaviones funciona como una base aérea móvil.")]
    h += figura("naval_desembarcar", "Desembarco: el buque lleva la infantería de marina hasta la costa; el último punto es el lugar de desembarco.")
    h += [Bul(["<b>Embarcar:</b> seleccione la tropa, pulse <b>Embarcar</b> y elija un buque de desembarco o helicóptero de transporte propio a menos de 3 km. "
               "A bordo viaja con el transporte, no se la ve y no recibe órdenes.",
               "<b>Desembarcar:</b> seleccione el transporte, pulse <b>Desembarcar</b> y marque la ruta; el último punto, en tierra firme, es el lugar de desembarco."])]
    h += [H2("6.11 Guerra electrónica")]
    h += figura("orden_interferir", "Interferir: la zona violeta muestra dónde se degradarán los sensores enemigos.")
    h += [pasos("Seleccione la unidad de guerra electrónica (C-E) y pulse <b>Interferir</b>.",
                "Haga clic en el centro de la zona, dentro del alcance del interferidor.", f"Pulse {B('Emitir orden')}."),
          P("Durante ese turno y la planificación del siguiente, en la zona el enemigo detecta mucho menos, su antiaérea guiada por radar pierde "
            "efecto y sus drones pierden el enlace. Pero al emitir, el enemigo localiza al interferidor.")]
    h += al_lado("cola_ordenes", "Cola de órdenes del turno.", [
        H2("6.12 La cola de órdenes y el «listo»"),
        P("La <b>cola de órdenes</b> lista las órdenes del turno de su bando, con quién las dio y su repartición:"),
        Bul(["<b>PENDIENTE</b>: se cumplirá al resolverse el turno. La «×» la cancela.",
             "<b>RESUELTA</b>: ya se cumplió; muestra el resultado (por ejemplo las pérdidas de un ataque).",
             "<b>RECHAZADA</b>: no se pudo cumplir, con el motivo (fuera de alcance, sin combustible…)."]),
        P(f"Cuando su bando terminó, el Comandante o el JEM pulsan {B('Estoy listo - confirmar órdenes')}. El turno se resuelve cuando el instructor lo "
          "decide, cuando ambos bandos están listos (si así lo configuró) o al agotarse el tiempo."),
    ], ancho_img=7.0 * cm)
    h += [H2("6.13 Lo que ve su bando"),
          Bul(["De las unidades enemigas solo se conoce posición, clase y bando mientras alguna unidad propia las detecte. La detección "
               "disminuye con el mal clima, el terreno (bosque, montaña, ciudad), la interferencia y, con el ciclo de día y noche, la "
               "oscuridad (8.6).",
               "Al perder de vista a un enemigo queda su <b>último contacto</b>, en gris translúcido, con el turno en que se lo vio.",
               "Un caza enemigo se ve como caza genérico: su modelo exacto no se conoce.",
               "Las órdenes, gráficos, mensajes y alertas del otro bando nunca se ven."])]
    h += al_lado("situacion_radar", "Pestaña Situación: cuadro radar.", [
        H2("6.14 La pestaña Situación"),
        P("La pestaña <b>Situación</b>, junto a Fuerzas, reúne lo que el bando sabe de un vistazo: lo que detectan sus radares, su personal "
          "y su infraestructura. La ven todas las reparticiones; el instructor y el observador, la de los dos bandos."),
        H3("Cuadro radar"),
        P("Cada radar y sensor del bando —radares de vigilancia, antiaérea guiada por radar, buques con radar, aviones de alerta "
          "temprana y unidades de escucha electrónica— con su estado (emitiendo, en silencio, interferido, con energía de respaldo) y "
          "<b>lo que detecta ahora</b>: cada contacto con su distancia y su rumbo desde el sensor y, si vuela, su cota (alta, media o "
          "rasante). «Por su emisión» indica que la escucha lo localizó por el radar que tiene encendido."),
        Bul(["Un clic en un contacto lo selecciona y lo muestra en el mapa; un clic en el sensor, lo mismo con el sensor.",
             "<b>Aviso automático:</b> al cerrar cada turno, cada sensor que detecta un enemigo que el bando no tenía a la vista lo "
             "informa solo, como alerta: «Radar Norte informa 1 contacto(s) nuevo(s): caza rasante a 85 km, rumbo 040°».",
             f"{B('Difundir el cuadro a la red del bando')} envía al chat del bando un resumen de todos los contactos (para que la A-2 "
             "informe al Comandante y a las demás reparticiones)."]),
    ], ancho_img=6.4 * cm)
    h += al_lado("situacion_personal", "Pestaña Situación: personal e infraestructura.", [
        H3("Personal"),
        P("Los efectivos de cada rama al inicio y los que quedan, las <b>bajas</b> y el porcentaje operativo. Cada unidad tiene su "
          "dotación: por escalón en las terrestres (una compañía, 120; un batallón, 500; una brigada, 3 500), por tripulación en las "
          "aeronaves (un caza, 1; un helicóptero, 4) y por buque o instalación en el resto. El instructor puede fijar otra al agregar la "
          "unidad (campo <b>Efectivos</b>, 7.4). Los efectivos siguen a la fuerza: una compañía al 60 % conserva 72 de sus 120 hombres. "
          "La ficha de cada unidad propia muestra los suyos; los del enemigo no se conocen."),
        H3("Infraestructura"),
        P("Cada categoría de infraestructura que el bando tiene en el ejercicio —energía, refinación, comunicaciones, puentes—, con su "
          "capacidad y lo que significa en ese momento (por ejemplo «radares fijos al 80 % de su alcance» o «1 cortado»). Ver 7.14."),
    ], ancho_img=6.4 * cm)

    # ---------------------------------------------------------------- 7 instructor
    h += [H2("6.15 La pestaña TIEM: el Problema Militar y el calendario")]
    h += al_lado("pmo_calendario", "Pestaña TIEM de un alumno: calendario de la operación y Problema Militar Operativo.", [
        P("El trabajo de Estado Mayor empieza, como en el TIEM, con el <b>Problema Militar Operativo</b> (PMO) que emite el escalón "
          "superior. La pestaña <b>TIEM</b> del panel izquierdo lo muestra para su bando, junto con el <b>calendario de la operación</b> "
          "y los documentos de la apreciación (6.16)."),
        H3("Calendario de la operación"),
        Bul(["<b>Día D</b> y <b>hora H</b>: el momento en que empieza la operación (la H cae en un turno).",
             "<b>Ahora</b>: el turno en curso contado desde D y H («D+1 · H+20») y la fase en que está la operación.",
             "Las <b>fases</b> (alistamiento, concentración y despliegue, ejecución y repliegue) con sus turnos; la que está en curso "
             "aparece resaltada.",
             "El mismo dato está en la cabecera y en la tarjeta Estado del escenario."]),
    ], ancho_img=6.4 * cm)
    h += al_lado("pmo_mision", "La misión del bando, enunciada como la pide el TIEM.", [
        H3("El Problema Militar Operativo"),
        P("El documento tiene los párrafos de siempre: situación general, fuerzas enemigas (lo que estima la inteligencia, sin la "
          "posición exacta de cada unidad), fuerzas propias, misión del Comando del Teatro de Operaciones, idea general de la operación "
          "conjunta, <b>misión del Componente Aéreo</b> (su bando), medios asignados, área de operaciones, limitaciones (restricciones y "
          "coacciones) e instrucciones de coordinación."),
        P("La misión se muestra completa y por partes, como la enseña el TIEM: <b>TAREA</b> (qué, dónde, cuándo) <b>«a fin de» "
          "PROPÓSITO</b>. Es el punto de partida del análisis de la misión y de la apreciación de su Estado Mayor."),
        P("Cuando el instructor emite o corrige el PMO, su bando recibe una alerta y la pestaña se actualiza sola."),
    ], ancho_img=6.4 * cm)

    h += [H2("6.16 La apreciación inicial: los documentos del Estado Mayor")]
    h += al_lado("tiem_lista", "Pestaña TIEM: los documentos de la apreciación inicial con su estado.", [
        P("Con el Problema Militar en la mano, el Estado Mayor del bando cumple la <b>Fase I, Paso 1</b> del TIEM: la "
          "<b>apreciación inicial</b>. La pestaña TIEM lista sus cuatro documentos, quién los redacta y en qué estado están:"),
        Tbl(["Documento", "Lo redactan"], [
            ["Análisis de la misión", "Comandante y JEM"],
            ["Concepto del Comandante", "Comandante y JEM"],
            ["Guía de Planeamiento", "JEM y Comandante"],
            ["Formas de Acción operacionales", "A-3, A-3 D/A y A-2 (y Comandante o JEM)"],
        ], [4.2 * cm, 3.0 * cm], tam=7.8),
        P("Todas las reparticiones leen todos los documentos; solo los editan las que figuran. Estados: <b>Sin empezar</b>, "
          "<b>Borrador</b>, <b>Presentado</b> (bloqueado hasta que el instructor lo revise), <b>Aprobado</b> o <b>Devuelto</b> "
          "(con las observaciones del instructor arriba del documento)."),
    ], ancho_img=6.4 * cm)
    h += figura("tiem_analisis", "Análisis de la misión: situación, Poder Relativo de Combate preliminar, tareas y misión específica.",
                ancho=ANCHO_TEXTO)
    h += [pasos(f"En la pestaña <b>TIEM</b>, pulse {B('Abrir')} en el documento.",
                f"Pulse {B('Redactar')} (o {B('Editar')}).",
                f"Pulse {B('Traer datos del PMO y del escenario')}: el simulador completa solo los campos <b>vacíos</b> que son "
                "transcripción o cálculo (la situación y la misión del PMO, el calendario, los objetivos de la cadena y el "
                "<b>Poder Relativo de Combate</b> preliminar). Lo que usted ya escribió no se toca.",
                "Complete el análisis: tareas deducidas, centros de gravedad (COG con sus capacidades, requerimientos y "
                "vulnerabilidades críticas), efecto deseado e indicadores, capacidades del enemigo (qué, dónde, con qué, desde "
                "dónde, cuándo y cómo), criterios, suposiciones, cronograma y las Formas de Acción.",
                f"Pulse {B('Guardar')}. Debajo aparece lo que falta para poder presentarlo y las observaciones de forma del TIEM "
                "(misión con verbo en infinitivo y sin condiciones, F/A que empiezan con un verbo…).",
                f"Cuando esté completo, pulse {B('Presentar al instructor')}."),
          P("El <b>Poder Relativo de Combate</b> se calcula por factor (aviación de combate, defensa aérea, fuerzas de superficie, "
            "guerra electrónica y reconocimiento): lo propio con exactitud y lo enemigo como lo estimaría la inteligencia (con un "
            "error de hasta 15 %). La relación y la conclusión (favorable, equilibrado, desfavorable) orientan el análisis; las "
            "fortalezas y debilidades se pueden corregir."),
          P(f"<b>Adjuntar un Word:</b> {B('Adjuntar un Word o PDF…')} sube un documento (.doc, .docx, .odt, .rtf o .pdf, hasta 10 MB) "
            "al documento del TIEM, por ejemplo la versión con firma o un anexo. Todo el bando y el instructor lo descargan con un clic.")]
    h += figura("tiem_formas", "Formas de Acción: cada una con qué, dónde, cuándo y quién, y el resumen de su análisis APA.", ancho=ANCHO_TEXTO)
    h += al_lado("tiem_editar_fa", "Redactar una F/A: cada conclusión del APA junto a su fundamento.", [
        H3("Las Formas de Acción y el criterio APA"),
        P("Se necesitan <b>al menos dos</b>. Cada una responde <b>qué</b> (verbo en infinitivo), <b>dónde</b>, <b>cuándo</b>, "
          "<b>quién</b> y <b>cómo</b>, y se analiza con el criterio APA:"),
        Bul(["<b>Adaptabilidad</b>: naturaleza (¿contribuye a la tarea?), integridad o alcance (¿la cumple entera?) y oportunidad "
             "(¿a tiempo?): sí, parcial o no, con su fundamento.",
             "<b>Practicabilidad</b>: medios propios, capacidades del enemigo y ambiente operacional (apoyado en el PRC): "
             "practicable, parcialmente practicable o no practicable.",
             "<b>Aceptabilidad</b>: resultados frente a costos: alta, media o baja."]),
        P("Al leerlas, cada F/A muestra el resumen («Naturaleza Sí · Integridad Parcial · Practicable…») y, al desplegarlo, el "
          "análisis completo."),
    ], ancho_img=7.4 * cm)

    h += [H2("6.17 Las apreciaciones de Estado Mayor y el juego de guerra")]
    h += al_lado("tiem_paso2", "Paso 2: una apreciación por repartición.", [
        P("Con la Guía de Planeamiento y las Formas de Acción, cada repartición elabora su <b>apreciación</b> (Fase I, Paso 2 "
          "del TIEM) para recomendar al Comandante la mejor F/A. Están en la misma pestaña TIEM, bajo «Paso 2»:"),
        Tbl(["Apreciación", "La redacta", "Qué concluye"], [
            ["Inteligencia", "A-2", "Capacidades del enemigo, su análisis y su orden de peligrosidad"],
            ["Operaciones", "A-3", "Confrontación de las F/A, comparación y F/A recomendada"],
            ["Defensa Aérea", "A-3 D/A", "Lo mismo, desde las operaciones defensivas"],
            ["Personal", "A-1", "Necesidades de personal de cada F/A"],
            ["Logística", "A-4", "Si la logística sostiene cada F/A"],
            ["Comunicaciones y Electrónica", "C-E", "Cómo apoyar cada F/A con comunicaciones y guerra electrónica"],
        ], [2.8 * cm, 1.5 * cm, 3.6 * cm], tam=7.4),
        P("El Comandante y el JEM pueden redactar o corregir cualquiera. " + B("Traer datos del PMO y del escenario") + " transcribe "
          "la misión específica y las capacidades de la Guía, calcula el Poder Relativo de Combate y la situación de cada área "
          "(efectivos y bajas para la A-1; existencias, convoyes y refinación para la A-4; comunicaciones, energía y guerra "
          "electrónica para la C-E; la defensa aérea y la amenaza aérea para la A-3 D/A) y arma las filas de cada F/A."),
    ], ancho_img=6.4 * cm)
    h += figura("tiem_matriz", "Apreciación de Operaciones: confrontación de cada F/A con cada capacidad del enemigo, comparación y "
                "F/A recomendada.", ancho=ANCHO_TEXTO)
    h += [H3("La confrontación de las F/A con las capacidades del enemigo"),
          P("En las apreciaciones de Operaciones y de Defensa Aérea, la <b>matriz de confrontación</b> pone las Formas de Acción en "
            "las filas y las capacidades del enemigo en las columnas (las de la Apreciación de Inteligencia o, si aún no está, las "
            "de la Guía de Planeamiento). En cada cruce, dándolas a ambas como ejecutadas, se elige si la capacidad <b>no afecta</b>, "
            "<b>degrada</b> o <b>anula</b> la F/A y se escribe el análisis. Luego se comparan las F/A (ventajas, desventajas, "
            "principios de la guerra aérea que cumplen y riesgos) y se recomienda la mejor, con su justificación y sus factores "
            "limitantes.")]
    h += al_lado("tiem_ensayos", "Juego de guerra: ensayos de F/A y su resultado.", [
        H3("Juego de guerra: ensayar una F/A en el simulador"),
        P("Para fundamentar la confrontación, el bando puede <b>ensayar</b> una F/A en el propio simulador (lo pueden hacer el "
          "Comandante, el JEM, la A-3, la A-3 D/A y la A-2):"),
        pasos("En la sección <b>Juego de guerra</b> de la pestaña TIEM, elija la F/A.",
              f"Pulse {B('Ensayar en el simulador')}: se crea una <b>copia del ejercicio en su estado actual</b> (unidades con su "
              "fuerza, combustible y posición; objetivos; calendario), en la que <b>la IA conduce al enemigo</b>. Solo los alumnos de "
              "su bando la ven.",
              f"Pulse {B('Ir al ensayo')} y conduzca la F/A como en el ejercicio. El turno se resuelve en cuanto su bando pulsa "
              "«Estoy listo».",
              f"Vuelva con {B('Volver al ejercicio')}: el ensayo figura en la lista con su resultado (turnos jugados, objetivos, "
              "puntos y unidades perdidas de cada bando), para citarlo en la matriz."),
        P("Cada bando puede tener hasta tres ensayos por ejercicio. Lo que pasa en un ensayo no cambia el ejercicio original."),
    ], ancho_img=6.4 * cm)

    h += [H2("6.18 La decisión, el Plan de Operaciones y la Orden de Operaciones")]
    h += figura("tiem_decision", "Decisión del Comandante: F/A adoptada, fundamentación, idea de la maniobra, acciones inmediatas y "
                "organización de la fuerza.", ancho=ANCHO_TEXTO)
    h += [P("Oídas las apreciaciones, el <b>Comandante</b> decide (Fase I, Paso 3): redacta la <b>Decisión del Comandante</b> con la "
            "F/A adoptada (la ayuda trae la que recomendó la A-3), su fundamentación, la idea general de la maniobra, las acciones "
            "inmediatas, las limitaciones y la organización de la fuerza (la ayuda la arma con las unidades del bando)."),
          P("Empieza la <b>Fase II</b>: el JEM y la A-3 redactan el <b>Análisis previo al plan</b> (estudio de la información, "
            "suposiciones, objetivos materiales con su APA, distribución del poder combativo con las aeronaves por esfuerzo, "
            "despliegues y planes alternos) y luego el <b>Plan de Operaciones</b>: situación, misión, concepto de la operación, "
            "instrucciones de coordinación, logística, comando y, sobre todo, las <b>tareas de las unidades subordinadas</b>.")]
    h += figura("tiem_plan_editar", "Tareas del Plan de Operaciones: turno (con su referencia a H), unidad, acción, objetivo o destino "
                "y el detalle en infinitivo.", ancho=ANCHO_TEXTO)
    h += [H3("Las tareas del plan son órdenes del simulador"),
          P("Cada tarea es una actividad de una unidad, como la pide el TIEM («Atacar el día D a la hora H el radar…»), y a la vez "
            "una orden que el simulador sabe cumplir:"),
          Bul(["<b>Turno</b>: cuándo se cumple; al lado se ve su referencia a la hora H (H, H+2…).",
               "<b>Unidad</b>: cualquiera de las propias.",
               "<b>Acción</b>: desplazar, atacar, patrullar, apoyar, aterrizar o interferir.",
               "<b>Objetivo o destino</b>: un objetivo del bando (una zona a ocupar o una unidad), una unidad enemiga ya conocida "
               "(vista o con último contacto) o una unidad o base propia. Atacar, apoyar y aterrizar necesitan una unidad.",
               "<b>Detalle</b>: la tarea redactada en infinitivo, para el documento."])]
    h += al_lado("tiem_orden", "Orden de Operaciones: lo que vence en el turno y lo de las próximas 24 horas.", [
        H3("La Orden de Operaciones"),
        P("En la pestaña TIEM, la sección <b>Orden de Operaciones</b> muestra las tareas del plan que <b>vencen en este turno</b> "
          "(y las de turnos anteriores que no se emitieron) y las de las <b>próximas 24 horas</b>, cada una con su estado."),
        pasos(f"Al empezar cada turno, revise lo que vence y pulse {B('Emitir las tareas de este turno como órdenes')}.",
              "Cada tarea se convierte en una orden de la cola, con la <b>misma validación</b> que una orden dada a mano y con la "
              "repartición de quien la emite (cada repartición emite las de las unidades que conduce).",
              "Si una orden no se puede cumplir (sin combustible, objetivo no localizado, fuera de su repartición…), la tarea queda "
              "<b>Rechazada</b> con el motivo; corrija la situación o el plan y vuelva a emitirla.",
              "Las órdenes emitidas se pueden ajustar o reemplazar a mano como cualquier otra, y el bando confirma el turno con "
              "«Estoy listo»."),
        P("Así se ve en el propio ejercicio si el plan era ejecutable y dónde hubo que apartarse de él."),
    ], ancho_img=6.4 * cm)

    h += [H2("6.19 La supervisión de la ejecución")]
    h += al_lado("tiem_supervision", "Supervisión de la ejecución: parte del turno y cuadro de diferencias con el plan.", [
        P("Emitidas las órdenes, empieza la <b>Fase III</b> del TIEM: el Estado Mayor sigue la ejecución con el ciclo "
          "<b>objetivo → resultado → diferencia → causa → acción correctiva</b>. La sección <b>Supervisión de la ejecución</b> "
          "de la pestaña TIEM hace la primera parte sola, con lo que su bando sabe:"),
        Bul(["El <b>parte del turno</b> anterior: órdenes cumplidas y rechazadas, objetivos cumplidos o fallidos y pérdidas.",
             "Un <b>cuadro</b> con cada tarea del plan ya vencida (¿se emitió?, ¿cómo terminó su orden?), cada objetivo (cumplido, "
             "fallido o con el plazo por vencer) y las unidades propias destruidas o con menos del 50 % de fuerza.",
             "Cada renglón tiene su estado: <b>Conforme</b>, <b>En curso</b>, <b>Desvío</b> o <b>Fallido</b>, con la "
             "<b>diferencia</b> respecto de lo previsto y, cuando se la conoce, la causa (por ejemplo, el motivo del rechazo)."]),
        P(f"{B('Al registro')} lleva un desvío al <b>registro de supervisión</b> para escribir su causa y la acción correctiva."),
    ], ancho_img=6.4 * cm)
    h += figura("tiem_supervision_doc", "Documento de Supervisión: registro, apreciaciones rápidas y órdenes fragmentarias.",
                ancho=ANCHO_TEXTO)
    h += [P("El documento <b>Supervisión de la ejecución</b> (Fase III; lo redactan el Comandante, el JEM, la A-3, la A-3 D/A y la "
            "A-2) tiene tres partes, todas opcionales porque se completan a lo largo del ejercicio:"),
          Bul(["<b>Registro de supervisión</b>: turno, objetivo, resultado, diferencia, <b>causa</b>, <b>acción correctiva</b>, "
               "responsable y si quedó abierta o cerrada.",
               "<b>Apreciaciones rápidas</b>: ante una situación nueva, las formas de acción consideradas y la decisión.",
               "<b>Órdenes fragmentarias</b>: tareas nuevas o que reemplazan a las del plan (con la misma forma que las del Plan "
               "de Operaciones). Se suman a la <b>Orden de Operaciones</b> y se emiten como órdenes aunque el plan ya esté "
               "aprobado."]),
          P("Así la corrección queda documentada y se puede evaluar después: qué se previó, qué pasó, por qué y qué se hizo.")]

    h += [H2("6.20 Evaluación del trabajo de Estado Mayor y legajo")]
    h += al_lado("tiem_evaluacion", "Evaluación y legajo: indicadores, notas y descarga del legajo.", [
        P("La sección <b>Evaluación y legajo</b> de la pestaña TIEM evalúa el trabajo de Estado Mayor del bando con cinco "
          "indicadores de 0 a 100 (pase el cursor por cada uno para ver cómo se calcula):"),
        Bul(["<b>Documentos del TIEM</b>: aprobados y presentados de los 13 de las fases I y II.",
             "<b>Forma según el TIEM</b>: documentos sin faltantes ni observaciones de forma.",
             "<b>Oportunidad</b>: documentos de la Fase I presentados a más tardar en el turno de la hora H.",
             "<b>Ejecución del plan</b>: tareas vencidas que se emitieron como órdenes.",
             "<b>Supervisión</b>: desvíos registrados con su causa y su acción correctiva."]),
        P("La <b>nota automática</b> (1 a 20) promedia los indicadores que aplican. El instructor puede poner una <b>nota a cada "
          "documento</b> al revisarlo; su promedio es la nota del instructor y la <b>calificación</b> promedia ambas. La misma "
          "evaluación figura en la rúbrica del informe (9.4)."),
    ], ancho_img=6.4 * cm)
    h += al_lado("legajo_word", "Un documento del TIEM exportado a Word, con el formato de toda apreciación escrita.", [
        H3("Word y PDF"),
        Bul([f"Cada documento tiene {B('Descargar en Word')} e {B('Imprimir o PDF')} en su ventana.",
             f"{B('Descargar el legajo en Word')} baja en un solo archivo .docx la portada, el Problema Militar y todos los "
             "documentos redactados, cada uno en su página.",
             f"{B('Legajo para imprimir o PDF')} abre el mismo legajo en una pestaña; con {B('Imprimir o guardar como PDF')} "
             "se imprime o se guarda como PDF."]),
        P("El formato es el del TIEM para toda apreciación escrita: <b>encabezamiento</b> (clasificación arriba y abajo, "
          "Cuartel General que la prepara, lugar, fecha y hora, nombre clave de la operación y número de copia), "
          "<b>cuerpo</b> con los párrafos del documento y <b>final</b> (firma, nombre, grado y cargo, anexos y distribución). "
          "El archivo se abre con Word, LibreOffice o WPS y se puede completar y firmar."),
    ], ancho_img=7.4 * cm)

    h += H1("7. Guía del instructor")
    h += [H2("7.1 Preparar un ejercicio: lista de pasos"),
          pasos("Cree el escenario: vacío con <b>Nuevo</b> o <b>Desde plantilla…</b> (7.2).",
                "Ubique las unidades de ambos bandos (7.4) y, si corresponde, las bases aéreas reales desde su capa.",
                "Fije el clima, la hora inicial y el modo de resolución (7.3); si quiere, zonas de meteorología (7.6).",
                "Cree los objetivos de cada bando (7.5).",
                "Elija quién conduce cada bando (7.17) y cree la situación: el Problema Militar Operativo y el calendario D/H, "
                "redactados por usted o creados automáticamente (7.15 y 7.16).",
                "Apruebe o cree las cuentas de los alumnos y asígnelos al escenario (7.10 y 7.11).",
                "Explique la situación y deje que los bandos den órdenes; resuelva los turnos (7.12).",
                "Al terminar, finalice el escenario y conduzca el análisis con el informe (capítulo 9)."),
          Nota("Si no tiene alumnos para uno de los bandos, deje que lo conduzca el simulador: vea el capítulo 8, «Combate contra la IA»."),
          H2("7.2 Crear un escenario")]
    h += figura("plantillas", "Nuevo escenario desde una plantilla.", ancho=ANCHO_TEXTO * 0.8)
    h += [Bul([f"{B('Nuevo')} crea un escenario vacío y le pide el nombre.",
               f"{B('Desde plantilla…')} crea un escenario nuevo con unidades, objetivos y clima ya cargados. Hay plantillas del sistema y las que "
               "guardaron los instructores. Entre las del sistema está «3 de enero de 2026: Operación Resolución Absoluta», que reconstruye "
               "el ataque con las aeronaves y los buques de EE. UU. que se informaron y las defensas venezolanas del litoral central.",
               "Las plantillas con la etiqueta amarilla <b>Contra la IA</b> crean un ejercicio en el que el simulador ya conduce al bando rojo "
               "(capítulo 8).",
               "<b>País Azul contra País Rojo (mapa ficticio)</b> crea un ejercicio sobre el mapa ficticio (4.12), sin ningún país real: cada "
               "república con su base aérea, cazas, ataque y helicópteros, antiaérea, radar, depósito, una fuerza de maniobra cerca de la "
               "frontera y su infraestructura; objetivos: el paso de frontera central, la base aérea enemiga y la infraestructura del otro "
               "bando. Lo pueden jugar dos grupos de alumnos o, activando la IA (8.3), uno solo."])]
    h += figura("guardar_plantilla", "Guardar el escenario actual como plantilla.", ancho=ANCHO_TEXTO * 0.62)
    h += [P(f"{B('Guardar como plantilla…')} guarda las unidades tal como están ahora (sin las destruidas), los objetivos, el clima y la "
            "identidad nacional. Marque <b>Conservar la fuerza, el combustible…</b> para guardar la situación con su desgaste (por ejemplo "
            "«situación al turno 4»); si no, todo arranca al 100 %.")]
    h += al_lado("consola_turno", "Consola: turno y configuración.", [
        H2("7.3 Consola: turno y configuración"),
        P("La pestaña <b>Consola</b> (junto a Fuerzas) reúne las herramientas del director. Sus secciones se despliegan con un clic en el título."),
        Bul([f"{B('Pausar')} / {B('Reanudar')}: congela el ejercicio (nadie puede dar órdenes).",
             f"{B('Finalizar')}: termina el escenario; ya no se dan órdenes y el informe se abre a los alumnos.",
             "<b>Clima</b>, <b>hora simulada inicial</b> y <b>límite de decisión</b> en segundos (0 = sin límite; con límite, el turno se "
             "resuelve solo al agotarse).",
             "<b>Azar en los combates</b> (reproducible) y <b>Resolver solo cuando ambos bandos estén listos</b>.",
             f"Pulse {B('Aplicar configuración')} para guardar los cambios.",
             "<b>Ver como</b>: muestra la pantalla como la ve un bando (con su niebla de guerra), útil para explicar en clase."]),
    ])
    h += al_lado("consola_agregar", "Consola: agregar unidad.", [
        H2("7.4 Agregar unidades"),
        pasos("Despliegue <b>Agregar unidad</b>.", "Escriba el nombre y elija el <b>bando</b>, la <b>clase</b> y el <b>escalón</b>.",
              "Los valores (velocidad, alcance, detección, autonomía) se llenan con los de la clase; puede ajustarlos.",
              f"Para aeronaves, {B('Elegir aeronave…')} abre las fichas de los modelos; para las demás clases, la lista "
              "<b>Tipo</b> ofrece los del catálogo propio.",
              "Opcional: <b>Efectivos</b>, si la unidad no tiene la dotación de su escalón (vacío = la de la tabla, 6.14).",
              f"Pulse {B('Ubicar en mapa')} y haga clic en el lugar: la unidad aparece allí."),
        P("Las unidades navales solo pueden ir sobre el agua. Para colocar una <b>base aérea real</b>, haga clic en el aeródromo en el mapa "
          "(capa Bases aéreas y aeródromos) y elija «Base azul» o «Base roja»."),
    ])
    h += al_lado("consola_catalogo", "Consola: catálogo propio.", [
        H3("Catálogo propio"),
        P("Cree los tipos de unidad de la AMB que no estén en el catálogo —por ejemplo «Buk-M2E», «VN-16» o el radar «JY-27A»— sin tocar "
          "el programa:"),
        pasos("Despliegue <b>Catálogo propio</b> en la Consola.",
              "Elija la <b>clase</b> (da el símbolo, la miniatura y las reglas): los valores se llenan con los de la clase.",
              "Escriba el <b>nombre</b>, la abreviatura que se verá en el mapa y el país.",
              "Ajuste la velocidad, los alcances, la autonomía, el ataque contra blancos terrestres, aéreos y navales y la defensa.",
              f"Pulse {B('Guardar tipo')}: ya aparece en la lista <b>Tipo</b> al agregar unidades."),
        P(f"La lista de abajo muestra los tipos propios con {B('Editar')} y {B('Eliminar')}. Las unidades que ya usan un tipo conservan "
          f"sus valores aunque se elimine. {B('Nuevo')} limpia el formulario."),
    ])
    h += figura("elegir_aeronave", "Elegir el modelo de aeronave: foto, prestaciones y armamento de cada uno.", ancho=ANCHO_TEXTO * 0.85)
    h += al_lado("consola_objetivos", "Consola: objetivos y puntaje.", [
        H2("7.5 Objetivos y puntaje"),
        pasos("Elija el tipo: <b>Ocupar una zona</b>, <b>Destruir</b> o <b>Neutralizar una unidad</b> enemiga, <b>Proteger una unidad</b> "
              "propia o <b>Efecto</b> (un objetivo ulterior o asignado que agrupa a otros).",
              "Elija para qué bando es, el nombre y los puntos.",
              "Ocupar: radio y turnos seguidos; con " + B("Ubicar la zona en el mapa") + " marque el centro. Destruir, neutralizar o "
              "proteger: la unidad (y, para proteger, hasta qué turno). Neutralizar: la fuerza a la que debe quedar (50 % si no indica otra). "
              "Efecto: su nivel (ulterior o asignado) y qué porcentaje de los objetivos que dependen de él debe cumplirse.",
              "Opcional: el <b>objetivo superior</b> al que contribuye, el <b>efecto deseado</b>, el <b>indicador</b> con que se mide y un "
              "<b>plazo</b> (turno).", f"Pulse {B('Crear objetivo')}."),
        P("Cada bando ve solo sus objetivos y su avance, como un árbol (5.2). Además de los objetivos, cada 10 de fuerza infligida al "
          "enemigo vale 1 punto. «Crear la situación automáticamente» (7.15) arma sola la cadena a partir de los objetivos que ya existen."),
    ])
    h += al_lado("consola_meteo", "Consola: meteorología por zonas.", [
        H2("7.6 Meteorología por zonas"),
        pasos("Elija el tipo (nublado, lluvia, tormenta), el radio, la deriva (rumbo y velocidad, para que el frente se desplace) y la duración.",
              f"Pulse {B('Colocar en el mapa')} y haga clic en el centro de la zona."),
        P("Las zonas aparecen en la lista con su botón para quitarlas. Ambos bandos las ven en el mapa (4.7)."),
    ])
    h += al_lado("consola_identidad", "Consola: identidad nacional y comunicaciones.", [
        H2("7.7 Identidad nacional y comunicaciones simuladas"),
        P("<b>Identidad nacional</b>: qué país representa cada bando (Venezuela, sus vecinos o cualquier país de América). Cambia el nombre y "
          "el color en la interfaz y el informe; no cambia las unidades ni sus valores."),
        P("<b>Comunicaciones simuladas</b>: <b>latencia</b>, <b>variación</b> y <b>pérdida</b> de mensajes del chat de los alumnos, para ejercitar "
          "el trabajo con una red degradada. El instructor ve todo al instante y sabe qué mensaje llegó a quién. Con "
          "<b>Órdenes que no llegan a tiempo</b>, ese porcentaje de las órdenes se cumple un turno después (más dentro de una "
          "interferencia enemiga) y el bando recibe el aviso."),
    ])
    h += al_lado("consola_direccion", "Consola: edición e interruptores.", [
        H2("7.8 Editar el escenario y dirección del ejercicio"),
        P("<b>Editar el escenario</b>: con la casilla marcada, las unidades se reubican <b>arrastrándolas</b> en el mapa (queda registrado). Para "
          "quitar una unidad, selecciónela y use «Eliminar unidad» en su ficha."),
        P("<b>Dirección del ejercicio</b>: interruptores para simplificar con fines didácticos: niebla de guerra, consumo de combustible y "
          f"munición, efectos del clima y fuego automático. Pulse {B('Aplicar interruptores')}; cada cambio queda en el informe."),
        P("En la misma sección están el <b>ciclo de día y noche</b>, <b>quién conduce cada bando</b> (7.17), el <b>nivel</b> del adversario "
          f"automático y el botón {B('Modo demostración')}: se explican en el capítulo 8, «Combate contra la IA»."),
    ])
    h += al_lado("consola_eventos", "Consola: eventos e informes inyectados.", [
        H2("7.9 Eventos, informes y ajustes manuales"),
        pasos("Escriba el texto del evento o informe y elija el destinatario (todos o un bando) y la <b>fuente</b> (Inteligencia, Población…).",
              f"Opcional: {B('Marcar posición en el mapa')}: el informe se dibuja en el mapa del destinatario (rombo amarillo con la fuente) "
              "durante los turnos de vigencia.", f"Pulse {B('Inyectar evento / informe')}."),
        P("<b>Ajuste manual</b>: corrige la fuerza, el combustible, la munición, las existencias o los daños de una unidad. Queda registrado "
          "en el informe como ajuste del instructor."),
    ])
    h += al_lado("consola_escenario", "Consola: escenario.", [
        H2("7.10 Escenario: copias y acceso"),
        Bul([f"{B('Duplicar')}: copia el despliegue inicial, los objetivos y los modelos de aeronave en un escenario nuevo.",
             f"{B('Archivar')}: lo saca de la lista sin borrarlo (casilla «archivados» de la cabecera para verlo).",
             f"{B('Exportar JSON')}: descarga la definición y el informe del escenario.",
             "<b>Usuarios con acceso a este escenario</b>: marque los alumnos y observadores que participan. Solo ellos lo ven."]),
    ])
    h += al_lado("consola_usuarios", "Consola: usuarios y solicitudes.", [
        H2("7.11 Usuarios y solicitudes de cuenta"),
        P("<b>Solicitudes de cuenta pendientes</b> (recuadro ámbar; el título Usuarios muestra cuántas hay y el simulador avisa de las nuevas):"),
        pasos("Revise el usuario y lo que pidió.", "Si hace falta, cambie el rol o la repartición en sus listas.",
              f"Pulse {B('Aprobar')} (el alumno ya puede entrar con la contraseña que eligió) o {B('Rechazar')} (se borra y el nombre queda libre)."),
        P("En la lista de usuarios se cambia el rol o la repartición de cada uno (el alumno vuelve a entrar con su nueva interfaz), se pone una "
          f"contraseña nueva con {B('Clave')} (provisional: el alumno la cambia al entrar) y se activa o desactiva la cuenta. Abajo se crea "
          "un usuario directamente, también con contraseña provisional."),
    ])
    h += [H2("7.12 Conducir el turno"),
          pasos("Durante la fase de <b>decisión</b> los bandos dan órdenes; el instructor sigue la situación, el chat y las alertas, y puede "
                "inyectar eventos.",
                "El estado de cada bando aparece en la barra inferior (PENDIENTE o LISTO).",
                f"Pulse {B('Resolver y avanzar turno')}: el simulador mueve las unidades, calcula detecciones y combates y avanza una hora. "
                "También se resuelve solo si así se configuró (ambos listos o límite de tiempo)."),
          P("Cada unidad ve en su ficha y en la cola de órdenes el resultado; los sucesos llegan como alertas a cada bando. Use <b>Ver como</b> "
            "(7.3) para mostrar en clase lo que veía cada bando.")]
    h += figura("videowall", "Modo videowall: el mapa a pantalla completa con turno, hora, reloj, estado de los bandos, marcador y alertas.")
    h += [H2("7.13 Videowall"),
          P(f"{B('Videowall')} (o la tecla <b>V</b>) muestra el mapa a pantalla completa para la pantalla grande o el proyector del centro de "
            "operaciones, con un rótulo del turno, la hora, el reloj, el estado de los bandos, el marcador y las últimas alertas. Esc sale. "
            "Se puede abrir directamente con la dirección <font face='Mono'>?modo=videowall&amp;vista=azul</font> (o rojo, o completa).")]
    h += [H2("7.14 Infraestructura y objetivos que pesan en la guerra"),
          P("Además de las unidades militares, el ejercicio puede incluir <b>infraestructura no militar</b>: centrales termoeléctricas e "
            "hidroeléctricas, refinerías, centros de comunicaciones y puentes estratégicos. No se mueven ni combaten, pero se las puede "
            "atacar, proteger o fijar como objetivo, y <b>su estado cambia lo que el bando puede hacer</b>:"),
          Tbl(["Infraestructura", "Si se la daña…", "Al máximo daño"], [
              ["Centrales eléctricas (energía)", "Los radares fijos del bando trabajan con generadores de respaldo y pierden alcance.",
               "Radares fijos al 50 %"],
              ["Refinerías (combustible)", "Los depósitos del bando reponen menos combustible cada turno (la munición no cambia).",
               "Reposición al 25 % (reservas)"],
              ["Centros de comunicaciones", "Más órdenes del bando no llegan a tiempo y se cumplen un turno después, aunque el instructor "
               "no haya activado la demora (7.7).", "+30 % de órdenes demoradas"],
              ["Puentes", "Con menos del 50 % de fuerza el puente queda <b>cortado</b>: ninguna unidad terrestre cruza por él. La "
               "infantería puede vadear un río; los vehículos, no. Los ingenieros pueden tender un vado o un puente al lado (6.8).",
               "Cortado"],
          ], [4.0 * cm, ANCHO_TEXTO - 7.4 * cm, 3.4 * cm], tam=8),
          P("La capacidad de cada categoría es la fuerza media de sus instalaciones. Si un bando no tiene instalaciones de una categoría, "
            "esa categoría no le afecta: el instructor decide qué infraestructura importa en el ejercicio colocándola en el mapa. Cuando "
            "una cae o se recupera, el bando recibe el aviso («Energía eléctrica: la capacidad cae al 40 %: radares fijos al 70 % de su "
            "alcance»), y la IA también la tiene en cuenta como blanco.")]
    h += al_lado("ficha_infraestructura", "Ficha de una instalación de la capa Infraestructura.", [
        H3("Colocarla en el ejercicio"),
        pasos("Encienda la capa <b>Infraestructura</b> en la tarjeta Capas (4.11) y acérquese a la zona del ejercicio.",
              "Haga clic en el icono de la instalación: la ficha muestra su tipo, su capacidad (megavatios o barriles por día), su "
              "operador, su efecto en el juego y las coordenadas.",
              f"Pulse {B('Bando Azul')} o {B('Bando Rojo')}, según a quién sirve: aparece en el ejercicio como una unidad fija con su "
              "miniatura, en el orden de batalla bajo <b>Infraestructura</b>.",
              "Fije los objetivos (7.5): por ejemplo, para el rojo <b>destruir</b> la central y para el azul <b>protegerla</b>."),
        P("Las plantillas contra la IA de la región central y de la costa oriental ya traen Planta Centro, la refinería El Palito y la "
          "de Puerto La Cruz con sus objetivos (8.2)."),
    ], ancho_img=7.0 * cm)
    h += al_lado("ficha_puente", "Ficha de un puente cortado.", [
        P("La ficha de una instalación muestra su <b>capacidad operativa</b> (su fuerza) y su estado: <b>Operativa</b>, <b>Dañada</b> "
          "con su porcentaje o, en un puente por debajo del 50 %, <b>Cortado</b>. El instructor puede repararla o dañarla con el "
          "<b>Ajuste manual</b> (7.9), por ejemplo para empezar el ejercicio con un puente ya volado."),
    ], ancho_img=6.0 * cm)

    # ---------------------------------------------------------------- 8 combate contra la IA
    h += [H2("7.15 La situación: el Problema Militar Operativo")]
    h += al_lado("pmo_instructor", "Pestaña TIEM del instructor: el Problema Militar.", [
        P("El Problema Militar Operativo de cada bando (6.15) lo prepara el instructor de dos maneras, que se pueden combinar:"),
        leyenda([("1", "Bando", "El PMO que se muestra y se edita: Azul o Rojo."),
                 ("2", "Crear la situación automáticamente", "El simulador lo redacta a partir del escenario."),
                 ("3", "Redactar / corregir", "Escribirlo o corregirlo a mano.")]),
        P("<b>Automáticamente</b>, el simulador usa los países de cada bando, sus unidades, los objetivos, el terreno y el calendario: "
          "redacta la situación general (con una causa del conflicto), las fuerzas enemigas en forma aproximada, las propias, la misión "
          "del escalón superior y la del componente aéreo según la postura del bando (ofensiva si sus objetivos son atacar u ocupar; "
          "defensiva si son proteger), los medios, el área de operaciones con sus paralelos y meridianos, las limitaciones y las "
          "instrucciones. Además, si faltan, fija el <b>calendario</b> (7.16) y arma la <b>cadena de objetivos</b> (7.5)."),
    ], ancho_img=6.4 * cm)
    h += al_lado("pmo_editar", "Redactar el PMO: la misión por partes y su revisión.", [
        P("<b>A mano</b>, " + B("Redactar / corregir") + " abre un formulario con cada párrafo. Las líneas que empiezan con «- » se ven "
          "como viñetas. La misión se escribe por partes (tarea, qué, dónde, cuándo y propósito) y el simulador la arma y la "
          "revisa mientras se escribe con las reglas del TIEM: que la tarea empiece con un verbo en infinitivo, que estén el qué, "
          "el dónde, el cuándo y el propósito, y que no tenga condiciones («si…», «en caso de…»)."),
        P(f"{B('Guardar y enviar al bando')} lo emite: el bando recibe una alerta. Lo que el instructor redacta a mano no se reemplaza al "
          "crear la situación automáticamente, salvo que marque «reemplazar también lo redactado a mano»."),
    ], ancho_img=6.4 * cm)
    h += al_lado("consola_calendario", "Consola: calendario de la operación.", [
        H2("7.16 El calendario de la operación"),
        P("En <i>Consola → Calendario de la operación</i> se fija:"),
        Bul(["La <b>fecha del turno 1</b>; cada turno dura una hora simulada desde la hora inicial (7.3), así que un ejercicio de "
             "varios días es simplemente uno de muchos turnos.",
             "El <b>turno en que cae la hora H</b>: el día D es el de ese turno.",
             "El <b>último turno previsto</b>, que da la duración del ejercicio.",
             "Las <b>fases de la operación</b>, con su nombre y sus turnos. Si no se definen, el simulador usa alistamiento, "
             "concentración y despliegue (antes de H), ejecución (desde H) y repliegue (los dos últimos turnos)."]),
        P(f"Pulse {B('Aplicar calendario')}. {B('Usar las fases por defecto')} descarta las fases propias. Dejar la fecha y la hora H "
          "vacías quita el calendario."),
    ], ancho_img=6.4 * cm)
    h += [H2("7.17 Quién conduce cada bando"),
          P("En <i>Consola → Dirección del ejercicio</i>, para cada bando, el instructor elige quién lo conduce:"),
          Tbl(["Opción", "Qué pasa"], [
              ["Grupo de alumnos", "Los alumnos asignados a ese bando, cada uno en su repartición (6.2). Es lo habitual."],
              ["El instructor", "El propio instructor da las órdenes de ese bando, como su comandante. Sirve para jugar de enemigo "
               "con un plan propio cuando no hay otro grupo de alumnos."],
              ["Adversario automático (IA)", "El simulador conduce el bando (capítulo 8)."],
          ], [4.4 * cm, ANCHO_TEXTO - 4.4 * cm])]
    h += figura("instructor_conduce", "El instructor conduciendo el bando Rojo: la franja ámbar lo recuerda y el botón vuelve a la consola.",
                ancho=ANCHO_TEXTO)
    h += [pasos("Elija <b>El instructor</b> para el bando y pulse " + B("Aplicar interruptores") + ".",
                "En la cabecera aparece el botón " + B("Conducir Rojo") + " (o Azul). Al pulsarlo, la pantalla pasa a ser la del "
                "comandante de ese bando: su niebla de guerra, sus órdenes, sus misiones y su «Estoy listo».",
                "Dé las órdenes del bando como cualquier alumno.",
                f"Pulse {B('Volver a instructor')} para regresar a la consola (y, por ejemplo, resolver el turno)."),
          P("Las órdenes que da el instructor cuentan para su bando en el informe, pero no aparecen en la evaluación por alumno.")]

    h += [H2("7.18 Revisar la apreciación de cada bando")]
    h += figura("tiem_instructor", "El instructor revisa la Guía de Planeamiento de Azul: lo que falta, el Word adjunto y los botones de revisión.",
                ancho=ANCHO_TEXTO)
    h += [P("En la pestaña <b>TIEM</b>, el instructor elige el bando y abre cualquiera de sus documentos. Cuando un bando presenta "
            "uno, llega una alerta. Al revisarlo:"),
          Bul([f"{B('Aprobar')}: queda aprobado (y bloqueado para el bando). El simulador pide una <b>nota de 1 a 20</b> "
               "(opcional), que entra en la evaluación del trabajo de Estado Mayor (6.20).",
               f"{B('Devolver con observaciones')}: escriba qué corregir; el bando las ve arriba del documento, puede editarlo de "
               "nuevo y volver a presentarlo.",
               f"{B('Reabrir como borrador')}: lo desbloquea sin observaciones.",
               f"{B('Editar')}: el instructor puede corregir o completar cualquier documento, por ejemplo para dar una solución "
               "de escuela."]),
          P("La Decisión, el Análisis previo y el Plan de Operaciones también se revisan así. El instructor puede emitir las tareas "
            "de un bando desde su Orden de Operaciones (como su Comandante), por ejemplo si conduce ese bando (7.17)."),
          P("Las apreciaciones del Paso 2 y los ensayos del juego de guerra se revisan igual: el instructor ve los ensayos de cada "
            "bando en su lista y puede abrirlos desde el selector de escenario para ver cómo se jugaron."),
          P("Cada revisión queda registrada en el informe, y los documentos (contenido, estado, observaciones y turno en que se "
            "presentaron) viajan en la exportación del escenario. El instructor que conduce un bando (7.17) redacta sus documentos "
            "como su Comandante.")]

    h += H1("8. Combate contra la IA")
    h += [P("En el <b>combate contra la IA</b> el simulador conduce uno de los bandos (normalmente el rojo) con su <b>adversario "
            "automático</b>. Así un solo grupo de alumnos puede entrenar sin que otro grupo haga de enemigo, el instructor queda libre para "
            "dirigir y observar, y el ejercicio se puede repetir con la misma situación para comparar el desempeño."),
          H2("8.1 Cómo juega la IA"),
          Bul(["<b>Con las mismas reglas que un alumno.</b> Sus órdenes pasan por las mismas comprobaciones de alcance, combustible, "
               "munición, terreno y repartición; si una no se puede cumplir, se rechaza igual que la de un alumno.",
               "<b>Solo con lo que su bando sabe.</b> Ve sus unidades, las enemigas que detecta (posición y clase, nunca su fuerza ni su "
               "logística), los últimos contactos, sus objetivos y la ubicación de las bases enemigas, que son instalaciones fijas. No ve las "
               "órdenes, los gráficos ni el chat de los alumnos. Si sus sensores no lo detectan, no sabe que usted está ahí.",
               "<b>Decide al empezar cada turno</b> (y en el turno en curso, en cuanto se la activa) y queda lista de inmediato: en la "
               "barra inferior su bando muestra <b>IA · LISTO</b>.",
               "Es una conducta <b>didáctica y legible</b>, no perfecta: sirve de oponente para ejercitar la apreciación y la toma de "
               "decisiones; no reemplaza al análisis del instructor."])]
    h += figura("ia_pantalla", "Un alumno del bando azul contra la IA, de noche: el bando rojo ya está listo.")
    h += [leyenda([
        ("1", "Hora y periodo", "Hora simulada del turno y, con el ciclo activo, Día, Crepúsculo o Noche (8.6)."),
        ("2", "Mapa de noche", "El fondo se oscurece; las unidades y los gráficos se siguen viendo igual."),
        ("3", "IA · LISTO", "El bando rojo lo conduce el simulador y ya dio sus órdenes del turno."),
        ("4", "Estoy listo", "Cuando su bando confirma, el turno puede resolverse (8.8)."),
    ])]
    h += [H2("8.2 Ejercicios listos para jugar contra la IA")]
    h += figura("plantillas_ia", "Plantillas con la etiqueta «Contra la IA»: el simulador ya conduce al bando rojo y el ciclo de día y noche está activo.",
                ancho=ANCHO_TEXTO * 0.9)
    h += [P(f"Pulse {B('Desde plantilla…')} en la cabecera y elija una de las plantillas con la etiqueta <b>Contra la IA</b>. El escenario "
            "se crea con las unidades, los objetivos de ambos bandos y el adversario automático ya activo en el bando rojo. Las fuerzas "
            "rojas son genéricas: no representan a un país real."),
          Tbl(["Ejercicio", "Situación", "Qué ejercita", "Comienza"], [
              ["Defensa aérea de la región central", "Un ataque aeronaval desde el Caribe (portaaviones, cazas embarcados, guerra electrónica y "
               "drones) contra la Base Aérea El Libertador y Maracay-Valencia.", "Alerta temprana con el radar de montaña, empleo de los Su-30 "
               "y F-16, defensa antiaérea por capas, protección de la base, de Planta Centro y de la refinería El Palito.", "05:00 (de noche)"],
              ["Interdicción en los llanos", "Una columna mecanizada roja con sus convoyes avanza de Guasdualito hacia Barinas.",
               "Interdicción de la logística (los convoyes son vulnerables), apoyo aéreo cercano con K-8W, Mi-35 y drones, coordinación entre "
               "reparticiones.", "06:00 (crepúsculo)"],
              ["Defensa de la costa oriental", "Una fuerza anfibia roja (buques de desembarco con fragatas y helicópteros) se acerca a "
               "Barcelona y Puerto La Cruz.", "Defensa de costa, ataque a la fuerza naval antes del desembarco, defensa de la playa y de "
               "la refinería de Puerto La Cruz.",
               "04:00 (de noche)"],
          ], [3.4 * cm, 5.0 * cm, ANCHO_TEXTO - 11.2 * cm, 2.8 * cm], tam=8),
          P("La reconstrucción del <b>3 de enero de 2026</b> se crea sin IA, para jugarla con dos grupos de alumnos. Para jugarla contra el "
            "simulador, marque «el simulador conduce el bando Rojo» (8.3): la IA conducirá a la fuerza de EE. UU.; también puede hacer que "
            "conduzca el bando Azul para que los alumnos planifiquen el ataque.")]
    h += al_lado("consola_ia", "Consola → Dirección del ejercicio.", [
        H2("8.3 Activar la IA en cualquier ejercicio"),
        P("Cualquier escenario, también uno creado a mano o desde otra plantilla, se puede jugar contra la IA:"),
        pasos("Abra la pestaña <b>Consola</b> y despliegue <b>Dirección del ejercicio</b>.",
              "En «Conduce el bando Rojo» (2), o el Azul, o los dos, elija <b>Adversario automático (IA)</b>.",
              "Elija el <b>nivel</b> del adversario (3; ver 8.4).",
              "Si quiere, marque el <b>ciclo de día y noche</b> (1; ver 8.6).",
              f"Pulse {B('Aplicar interruptores')}. La IA da sus órdenes del turno en curso en ese momento."),
        P("Para devolver el bando a los alumnos, elija <b>Grupo de alumnos</b> y aplique: el bando queda «pendiente» y los alumnos lo "
          "conducen desde ese turno. Cada cambio queda registrado como evento y en el informe."),
        leyenda([("1", "Ciclo de día y noche", "Activa la hora del día en la detección (8.6)."),
                 ("2", "Quién conduce", "Grupo de alumnos, el instructor o el adversario automático (7.17)."),
                 ("3", "Nivel", "Prudente, normal o agresiva (8.4)."),
                 ("4", "Modo demostración", "La IA juega los dos bandos sola (8.7).")]),
    ], ancho_img=7.2 * cm)
    h += [H2("8.4 Los tres niveles del adversario"),
          P("El nivel cambia <b>cuánto riesgo toma</b> la IA, no lo que sabe ni sus unidades: las reglas son las mismas para los tres."),
          Tbl(["", "Prudente", "Normal", "Agresiva"], [
              ["Cuándo ataca", "Solo con una ventaja clara.", "Con una relación de fuerzas razonable.", "Aun con poca ventaja."],
              ["Hasta dónde persigue a un blanco en tierra", "Unos 30 km.", "Unos 60 km.", "Hasta 150 km."],
              ["Cómo se acerca", "Se queda más lejos, al límite de su alcance.", "A distancia de tiro.", "Más cerca."],
              ["Combustible de sus aviones", "Vuelve antes a la base, con margen.", "Vuelve a tiempo.", "Apura el combustible."],
              ["Antiaérea enemiga que conoce", "No se mete en ella salvo para batirla.", "La evita solo con los aviones sin armas.", "Igual que la normal."],
              ["Cazas desde sus bases", "Uno propio por cada avión enemigo a la vista.", "Igual que la prudente.", "Hasta dos por cada avión enemigo."],
          ], [4.4 * cm, (ANCHO_TEXTO - 4.4 * cm) / 3, (ANCHO_TEXTO - 4.4 * cm) / 3, (ANCHO_TEXTO - 4.4 * cm) / 3], tam=8),
          Bul(["<b>Prudente</b>: un oponente cauteloso que no se expone. Obliga a los alumnos a buscarlo, a ganar el conocimiento del enemigo "
               "y a crear la ventaja antes de atacar. Conviene para practicar el reconocimiento y la iniciativa.",
               "<b>Normal</b>: el punto de partida recomendado para un primer ejercicio.",
               "<b>Agresiva</b>: castiga los errores de despliegue, la antiaérea débil y la logística descuidada, pero se expone y paga sus "
               "pérdidas. Conviene para practicar la defensa y la reacción ante las amenazas."])]
    h += [H2("8.5 Qué hace la IA con cada tipo de unidad"),
          Tbl(["Unidades", "Conducta"], [
              ["Aeronaves armadas", "Atacan el mejor blanco a su alcance o vuelan hacia uno que puedan batir y del que puedan volver. Con poco "
               "combustible o munición regresan a una base propia con lugar libre."],
              ["Aviones sin armas (alerta temprana, cisterna, guerra electrónica)", "Se mantienen fuera del alcance de la antiaérea enemiga que "
               "conocen; los de guerra electrónica interfieren al enemigo."],
              ["Bases aéreas y portaaviones", "Lanzan cazas si el enemigo tiene aviación a la vista y no hay suficientes cazas propios en el aire."],
              ["Unidades terrestres", "Se reabastecen cuando les falta combustible o munición, atacan si la relación de fuerzas es favorable "
               "(según el nivel) y van a cumplir sus objetivos: ocupar una zona, destruir o proteger una unidad."],
              ["Buques y baterías de misiles", "Lanzan salvas de misiles contra los blancos que detectan."],
              ["Radares, antiaérea y apoyos", "Se quedan en posición. La antiaérea dispara sola si tiene el fuego automático."],
              ["Convoyes", "Van a reabastecer a las unidades propias que lo necesitan y vuelven a un depósito a recargar."],
          ], [4.4 * cm, ANCHO_TEXTO - 4.4 * cm])]
    h += [H2("8.6 El ciclo de día y noche"),
          P("Con el <b>ciclo de día y noche</b> activo, cada turno (una hora) cae en un periodo del día según la hora simulada, y la "
            "oscuridad reduce la detección. Vale igual para los alumnos y para la IA."),
          Tbl(["Periodo", "Horas", "A simple vista (tropas, vehículos, bases, la mayoría de los buques)", "Cámaras de aviones, drones y reconocimiento",
               "Radares (vigilancia, antiaérea guiada, destructor, alerta temprana)"], [
              ["Día", "07:00 a 17:59", "100 %", "100 %", "100 %"],
              ["Crepúsculo", "06:00 y 18:00", "75 %", "90 %", "100 %"],
              ["Noche", "19:00 a 05:59", "50 %", "80 %", "100 %"],
          ], [2.4 * cm, 2.6 * cm, 4.0 * cm, 4.0 * cm, ANCHO_TEXTO - 13.0 * cm], tam=8),
          P("Los porcentajes son la distancia a la que cada unidad detecta, comparada con la de día; se suman a los efectos del clima, el "
            "terreno y la interferencia. La escucha electrónica tampoco depende de la luz. Por la noche cobran valor los <b>radares</b> y los aviones y drones con "
            "cámaras térmicas; una columna puede acercarse mucho más sin ser vista.")]
    h += dos_figuras(("mapa_dia", "El mismo despliegue a las 10:00 (día)."), ("mapa_noche", "A las 23:00 (noche): el fondo se oscurece."))
    h += al_lado("estado_noche", "Estado del escenario de noche.", [
        P("La hora y el periodo se leen en la tarjeta <b>Estado del escenario</b> (y en la barra de título, en pantallas anchas). Durante "
          "el crepúsculo el mapa toma un tono más cálido y de noche se oscurece."),
        P("El ciclo se activa en <i>Consola → Dirección del ejercicio</i> (8.3). La hora de inicio del ejercicio se fija en <i>Turno y "
          "configuración</i> (7.3): por ejemplo, un ataque a las 02:00 empieza de noche y amanece en el turno 5."),
    ], ancho_img=7.0 * cm)
    h += [H2("8.7 Modo demostración"),
          P(f"{B('Modo demostración')} pone a la IA a conducir <b>los dos bandos</b> y fija un límite de decisión de 15 segundos: el "
            "ejercicio avanza solo, un turno cada 15 segundos. Sirve para mostrar en clase, en el videowall (7.13), cómo se desarrolla un "
            "escenario antes de que lo jueguen los alumnos, o para ver cómo resuelve el simulador una situación."),
          Bul([f"Para detenerlo, pulse {B('Pausar')} (7.3), o devuelva los dos bandos a «Grupo de alumnos» y pulse {B('Aplicar interruptores')}.",
               "Después, devuelva el límite de decisión al que quiera usar en <i>Turno y configuración</i> (0 = sin límite).",
               "Como la demostración cambia el escenario, conviene hacerla sobre una copia: Consola → Escenario → <b>Duplicar</b> (7.10)."])]
    h += [H2("8.8 Una clase contra la IA, paso a paso"),
          pasos("Cree el escenario desde una plantilla <b>Contra la IA</b> (8.2), o active la IA en uno propio (8.3).",
                "Elija el nivel del adversario y revise la hora de inicio y el ciclo de día y noche.",
                "Asigne a los alumnos al escenario (7.10) y distribuya las reparticiones del bando azul (6.2).",
                "Explique la situación y los objetivos. La IA ya dio sus órdenes del primer turno: su bando figura como <b>IA · LISTO</b>.",
                f"Los alumnos dan sus órdenes y pulsan {B('Estoy listo')}. Si está marcado «Resolver solo cuando ambos bandos estén listos», "
                f"el turno se resuelve en ese momento; si no, pulse {B('Resolver y avanzar turno')}.",
                "Al abrirse cada turno la IA vuelve a decidir con lo que ve. Use <b>Ver como</b> (7.3) para mostrar qué sabía cada bando.",
                "Al terminar, finalice el escenario y analice el informe: rúbrica, indicadores doctrinales y nota (capítulo 9).",
                "Repita el ejercicio otro día, o con otro nivel, y use <b>Comparar con otros ejercicios</b> (9.5) para ver la evolución."),
          Nota("La IA no lee el chat ni los eventos inyectados por el instructor, y no planifica misiones aéreas de varios turnos: da "
               "órdenes turno a turno. Si sus unidades no hacen nada, es porque no detectan nada que puedan atacar ni tienen objetivos "
               "que cumplir: dele objetivos (7.5) o acérquele el enemigo.")]

    # ---------------------------------------------------------------- 9 informe
    h += H1("9. El informe posterior (AAR)")
    h += [P(f"El botón {B('Informe')} abre el análisis del ejercicio. El instructor y el observador lo ven siempre; los alumnos, cuando el "
            "escenario está finalizado. Mientras está abierto, el mapa muestra el pasado y no la situación en curso.")]
    h += figura("informe_barra", "Barra de la repetición.")
    h += [Tbl(["Botón", "Qué hace"], [
        ["&lt; y &gt;, la barra y Reproducir", "Recorren el ejercicio turno a turno: posiciones, trayectorias y combates de cada turno sobre el mapa."],
        ["Resumen", "Resumen por bando: pérdidas, unidades destruidas, objetivos y puntaje."],
        ["Línea de tiempo", "Combustible y munición de cada unidad turno a turno, cruzados con combates y reabastecimientos."],
        ["Rúbrica", "Evaluación por bando, por repartición y por alumno, con observaciones automáticas."],
        ["Imprimible", "Informe completo en una página lista para imprimir o guardar en PDF."],
        ["Diapositivas", "Presentación automática para la sesión de análisis: una diapositiva por turno, resumen y evaluación."],
        ["Replay", "Animación continua del ejercicio (9.6)."],
        ["CSV", "Combates en una hoja de cálculo."], ["Cerrar", "Vuelve a la situación en curso."],
    ], [4.2 * cm, ANCHO_TEXTO - 4.2 * cm])]
    h += [H2("9.1 La repetición turno a turno")]
    h += figura("informe_repeticion", "Repetición del turno 2: trayectorias de las unidades y combates del turno.")
    h += [H2("9.2 Resumen y línea de tiempo")]
    h += figura("informe_resumen", "Resumen del ejercicio.", ancho=ANCHO_TEXTO * 0.7)
    h += figura("informe_timeline", "Línea de tiempo de logística y combates; un clic en una unidad muestra su detalle.")
    h += [P("En la <b>línea de tiempo</b> cada fila es una unidad: la línea verde es el combustible y la ámbar la munición. Los símbolos marcan "
            "caídas abruptas (▼), niveles críticos (●), reabastecimientos (▲) y combates (◆). Los filtros de arriba eligen qué mostrar y de qué bando.")]
    h += [H2("9.3 Rúbrica")]
    h += figura("informe_rubrica", "Rúbrica: indicadores por bando y por repartición, y evaluación por alumno.")
    h += [P("La <b>rúbrica</b> resume la conducción de cada bando y de cada repartición (órdenes emitidas, resueltas y rechazadas con su motivo, "
            "turnos con órdenes y turnos pasivos, logística, pérdidas, objetivos, misiones) con <b>observaciones automáticas</b>. La "
            f"<b>evaluación por alumno</b> hace lo mismo para cada usuario, y {B('CSV por alumno')} la descarga para la planilla de calificaciones."),
          H2("9.4 Indicadores doctrinales y calificación")]
    h += figura("informe_doctrina", "Indicadores doctrinales de cada bando, con su valor, su puntaje de 0 a 100 y la calificación de 1 a 20.")
    h += [P("Los <b>indicadores doctrinales</b> miden la conducción de cada bando con criterios de la doctrina, a partir de lo que pasó en el "
            "ejercicio. Cada uno da un puntaje de 0 a 100; su promedio da la <b>calificación de 1 a 20</b>. «Cómo se calcula cada indicador», "
            "al pie de la tabla, explica el criterio de cada uno."),
          Tbl(["Indicador", "Qué mide"], [
              ["Reacción ante las amenazas", "Cuántos turnos tarda el bando en dar una orden contra una unidad enemiga que lo atacó."],
              ["Conocimiento del enemigo", "Qué parte de las unidades enemigas llegó a detectar (radares, reconocimiento, guerra electrónica)."],
              ["Sostenimiento logístico", "Si las unidades que se quedaron sin combustible o munición fueron reabastecidas."],
              ["Coordinación entre reparticiones", "Si las reparticiones A-2 a C-E con unidades a cargo dieron órdenes (solo cuando el bando trabaja con varias reparticiones)."],
              ["Economía de fuerzas", "Pérdidas infligidas frente a pérdidas sufridas en los combates del bando."],
              ["Cumplimiento de objetivos", "Objetivos cumplidos sobre los asignados."],
              ["Iniciativa", "Turnos en los que el bando dio al menos una orden o planificó una misión."],
          ], [4.6 * cm, ANCHO_TEXTO - 4.6 * cm]),
          P("Si los bandos trabajaron con los documentos del TIEM, la rúbrica agrega la tabla <b>Trabajo de Estado Mayor (TIEM)</b> "
            "con los indicadores de 6.20, la nota automática, la del instructor y la calificación."),
          P("Un indicador que no aplica (por ejemplo, la coordinación cuando un solo alumno condujo todo) figura como «no aplica» y no "
            "cuenta para la nota. En un ejercicio contra la IA, la nota del bando de la IA sirve de referencia, no de calificación."),
          H2("9.5 Comparar ejercicios")]
    h += figura("comparar", "Comparación de tres ejercicios: nota e indicadores de cada bando, y evolución de dos alumnos.", ancho=ANCHO_TEXTO * 0.95)
    h += [P(f"{B('Comparar con otros ejercicios…')} (en la rúbrica) pone lado a lado varios ejercicios: marque los que quiera (hasta 12) y "
            f"pulse {B('Comparar')}. La primera tabla muestra la nota y los indicadores de cada bando en cada ejercicio; la segunda, la "
            "<b>evolución de cada alumno</b>: sus órdenes, rechazos, turnos activos y pasivos, misiones y la nota de su bando en cada ejercicio. "
            "Es la forma de ver si un curso mejora de un ejercicio a otro, por ejemplo al repetir el mismo escenario contra la IA.")]
    h += figura("informe_replay", "Replay animado a mitad del ejercicio: estelas, combate en curso y rótulo con hora, clima, marcador y novedades.")
    h += [H2("9.6 Replay animado"),
          P("Reproduce el ejercicio de forma continua: las unidades se mueven entre turnos, los combates destellan, las unidades destruidas se "
            "desvanecen y un rótulo muestra el turno, la hora, el clima, el marcador y las novedades."),
          Bul(["Reproducir / pausa, ir al inicio o al final.", "Velocidad 0,5×, 1×, 2× o 4×.",
               "La barra se puede arrastrar para ir a cualquier momento.", "<b>Estela</b> deja el recorrido de cada unidad en el color de su bando."])]

    # ---------------------------------------------------------------- 9 observador
    h += H1("10. El observador")
    h += figura("observador", "Pantalla del observador: todo el ejercicio, sin controles para dar órdenes.")
    h += [P("El observador ve el mapa completo de ambos bandos, sin niebla de guerra, el orden de batalla, las misiones, los objetivos y el "
            "informe en cualquier momento. No puede dar órdenes, escribir en el chat ni cambiar nada. Es el rol para evaluadores y visitas.")]

    # ---------------------------------------------------------------- 10 problemas
    h += H1("11. Preguntas frecuentes")
    h += [Tbl(["Pregunta o problema", "Respuesta"], [
        ["Mi orden aparece RECHAZADA.", "Lea el motivo en la cola: objetivo fuera de alcance o no detectado, sin combustible o munición, "
         "terreno intransitable, río sin puente, base sin existencias…"],
        ["El simulador dice que la orden corresponde a otra repartición.", "Esa unidad la conduce otra repartición de su bando (6.2). Coordine por la red del bando."],
        ["No veo el botón Estoy listo.", "Solo lo tienen el Comandante y el JEM."],
        ["La pestaña TIEM dice que no hay Problema Militar.", "El instructor todavía no lo emitió. Cuando lo haga llega una alerta y la pestaña se actualiza sola."],
        ["No puedo presentar un documento del TIEM.", "Debajo del documento figura lo que falta (por ejemplo, la segunda Forma de Acción "
         "o un centro de gravedad enemigo). Complételo y vuelva a presentarlo."],
        ["No puedo editar un documento del TIEM.", "Lo redacta otra repartición (6.16), o ya fue presentado o aprobado: espere la "
         "revisión del instructor o pídale que lo reabra."],
        ["No veo a las unidades enemigas.", "Solo se ven las que su bando detecta. Acérquese con reconocimiento, drones o radares."],
        ["Las unidades se ven muy pequeñas o sin nombre.", "Es el mapa de lejos (4.2). Acerque el zoom: aparecen nombres y anillos de alcance."],
        ["El mapa sale gris o vacío.", "Faltan los datos de mapa en el servidor (avise al instructor) o se eligió una región sin datos."],
        ["El chat no llega o llega tarde.", "El instructor activó las comunicaciones simuladas (7.7): es parte del ejercicio."],
        ["El punto de conexión está rojo.", "Se perdió la conexión con el servidor; el simulador se reconecta solo. Si no, recargue la página (F5)."],
        ["La unidad no cruza el río por el puente.", "El puente está cortado (menos del 50 % de fuerza; 7.14). Busque otro paso con "
         "«Seguir carreteras», vadee con infantería o pida a los ingenieros un vado o un puente."],
        ["Mis radares ven menos que antes.", "Revise la pestaña Situación: si la energía del bando cayó, los radares fijos trabajan con "
         "generadores de respaldo (7.14). También los reduce la interferencia enemiga y, de noche, nada (el radar no depende de la luz)."],
        ["No puedo abrir el informe.", "Los alumnos lo ven cuando el instructor finaliza el escenario."],
        ["No hay alumnos para el otro bando.", "Que lo conduzca el simulador: active el adversario automático (8.3) o use una plantilla Contra la IA (8.2)."],
        ["La IA no hace nada.", "Solo actúa con lo que detecta y con sus objetivos: si no ve al enemigo ni tiene objetivos, espera. Revise "
         "también que su casilla esté marcada y aplicada."],
        ["De noche dejé de ver al enemigo.", "Con el ciclo de día y noche, de noche se detecta a la mitad de distancia a simple vista (8.6): use radares, drones y reconocimiento."],
        ["El ejercicio avanza solo cada 15 segundos.", "Está activo el modo demostración (8.7): pause el escenario o desmarque los adversarios automáticos."],
    ], [6.0 * cm, ANCHO_TEXTO - 6.0 * cm]),
          H2("Anexo A. Atajos"),
          Tbl(["Tecla o gesto", "Acción"], [
              ["V", "Entrar o salir del videowall (instructor y observador)."], ["Esc", "Salir del videowall, terminar la regla o cancelar un gráfico."],
              ["Ctrl + clic (o Mayúsculas + clic)", "Sumar o quitar unidades de la selección múltiple."],
              ["Intro", "Enviar el mensaje del chat; ingresar en la pantalla de acceso."],
              ["Doble clic", "Terminar la regla o un gráfico táctico."], ["Rueda del ratón", "Acercar o alejar el mapa."],
          ], [5.5 * cm, ANCHO_TEXTO - 5.5 * cm]),
          H2("Anexo B. Glosario"),
          Tbl(["Término", "Significado"], [
              ["AAR", "After Action Review: análisis posterior al ejercicio."],
              ["Adversario automático (IA)", "El simulador conduciendo un bando con las mismas reglas que los alumnos (capítulo 8)."],
              ["APP-6", "Norma de simbología militar; alternativa a las miniaturas."],
              ["CAP, CAS, SEAD", "Roles de misión aérea: patrulla de combate, apoyo aéreo cercano, supresión de defensas antiaéreas."],
              ["Crepúsculo", "Las horas de las 06:00 y las 18:00, con luz escasa: la detección a simple vista baja al 75 %."],
              ["Cuadro radar", "Lo que detecta ahora cada sensor del bando, con distancia y rumbo (6.14)."],
              ["ETA", "Hora estimada de llegada al final de una ruta."],
              ["Escalón", "Nivel de la unidad (equipo, sección, compañía, batallón, brigada)."],
              ["Fase de decisión / resolución", "Parte del turno en que se dan órdenes / en que el simulador las ejecuta."],
              ["Indicadores doctrinales", "Puntajes de 0 a 100 de la conducción de un bando que dan la calificación de 1 a 20 (9.4)."],
              ["Infraestructura crítica", "Centrales eléctricas, refinerías, centros de comunicaciones y puentes cuyo estado pesa en la operación (7.14)."],
              ["Niebla de guerra", "Cada bando solo ve lo que detecta."],
              ["Último contacto", "Última posición conocida de un enemigo que se dejó de ver."],
              ["Waypoint", "Punto de paso de una ruta."],
          ], [4.5 * cm, ANCHO_TEXTO - 4.5 * cm])]

    h += seccion_creditos("Créditos")
    doc.multiBuild(h)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=str(RAIZ / "docs" / "Manual_Usuario_SIETE.pdf"))
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    construir(salida)
    print(f"{salida} ({salida.stat().st_size // 1024} KB, {FIG[0]} figuras)")


if __name__ == "__main__":
    main()
