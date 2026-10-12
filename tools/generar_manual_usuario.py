"""Genera el manual de usuario en PDF (docs/Manual_Usuario_SIETE.pdf): guia paso a paso, con capturas, de cada parte
de la interfaz para el instructor, los alumnos de cada puesto y el observador.

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
          Spacer(1, 8), Paragraph("Guía paso a paso para el instructor, los alumnos de cada puesto y el observador", S["subtitulo"]),
          Spacer(1, 24)]
    h += credito_portada()
    h += [Spacer(1, 10), Paragraph(f"{fecha} · versión 1.0", S["subtitulo"]), PageBreak()]

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
               "resuelve los turnos, inyecta eventos y conduce el análisis posterior.", "2 a 5, 7, 8"],
              ["Alumno del bando azul o rojo", "Aprecia la situación, da órdenes a las unidades de su puesto, coordina con su bando por la red "
               "de comunicaciones y confirma el turno.", "2 a 6, 8"],
              ["Observador", "Ve todo el ejercicio sin poder cambiar nada (evaluadores, visitas).", "2 a 5, 9"],
          ], [4.0 * cm, ANCHO_TEXTO - 6.0 * cm, 2.0 * cm]),
          H2("1.2 Convenciones"),
          Bul(["Los nombres de botones, pestañas y casillas van en <b>negrita</b>, tal como aparecen en pantalla.",
               "Los <b>círculos rojos numerados</b> de las capturas señalan las zonas que se explican en la tabla que las acompaña.",
               "Las capturas usan un <b>ejercicio de ejemplo</b> (unidades en el piedemonte andino y un grupo naval frente a Puerto Cabello): "
               "sus nombres y cifras no son datos reales.",
               "Un <b>turno</b> equivale a una hora simulada. Cada turno tiene una fase de <b>decisión</b> (los bandos dan órdenes) y una de "
               "<b>resolución</b> (el simulador calcula movimientos, detecciones y combates de todos a la vez)."])]

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
        P("<b>Primer uso del simulador.</b> El administrador entra con el usuario <b>admin</b> y la contraseña inicial <b>siete1234</b>; "
          "el simulador le pedirá cambiarla de inmediato (2.4)."),
    ])
    h += al_lado("acceso_registro", "Solicitar una cuenta.", [
        H2("2.3 Solicitar una cuenta"),
        P("Los alumnos no necesitan que el instructor les cree la cuenta: la piden ellos mismos."),
        pasos(f"En la pantalla de acceso pulse {B('Solicitar una cuenta')}.",
              "Elija un <b>usuario</b> (letras, números, punto o guion, sin espacios) y escriba la <b>contraseña</b> dos veces (mínimo 8 caracteres).",
              "Elija el <b>rol</b> que le corresponde (alumno del bando azul o rojo, observador o instructor) y, si es alumno, su <b>puesto</b>.",
              f"Pulse {B('Enviar solicitud')}."),
        P("La cuenta queda <b>pendiente</b>: hasta que el instructor la apruebe (7.11) el simulador responde «Su solicitud de cuenta aún no "
          "fue aprobada». El instructor puede aprobarla con otro rol o puesto."),
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
        P("El botón redondo de la esquina superior derecha abre el menú del perfil: muestra su usuario, su rol y su puesto."),
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
            "pestaña <b>Consola</b>; el alumno, los bloques para dar órdenes de su puesto.")]
    h += figura("pantalla_general", "Pantalla del instructor con el ejercicio de ejemplo.")
    h += [leyenda([
        ("1", "Cabecera", "Escenario activo, botones de escenario, conexión, reloj, videowall, informe y perfil (3.1)."),
        ("2", "Panel izquierdo", "Pestaña Fuerzas (orden de batalla, ficha de la unidad, órdenes, misiones, cola) y, para el instructor, Consola."),
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
        ("8", "Informe", "Informe posterior al ejercicio (capítulo 8)."),
        ("9", "Perfil", "Usuario, rol y puesto; cambiar contraseña y cerrar sesión (2.5)."),
    ]),
          P("La barra de título también muestra el <b>turno</b>, la <b>hora simulada</b> y el <b>bando</b> con que trabaja.")]
    h += [H2("3.2 La barra inferior")]
    h += figura("barra_inferior", "Barra inferior de un alumno: botón para confirmar el turno y estado de ambos bandos.")
    h += [Bul([f"<b>Alumnos:</b> {B('Estoy listo - confirmar órdenes')} avisa que su bando terminó de dar órdenes (lo pueden pulsar el "
               "Estado Mayor y el A5). Si después emite o cancela una orden, el «listo» se anula y hay que volver a confirmarlo.",
               f"<b>Instructor:</b> {B('Resolver y avanzar turno')} resuelve el turno aunque algún bando no esté listo (7.12).",
               "A la derecha, el estado de cada bando: <b>PENDIENTE</b> (dando órdenes) o <b>LISTO</b>."])]

    # ---------------------------------------------------------------- 4 mapa
    h += H1("4. El mapa")
    h += [H2("4.1 Moverse por el mapa"),
          Bul(["<b>Desplazar:</b> arrastre el mapa con el ratón.", "<b>Acercar o alejar:</b> rueda del ratón o los botones <b>+</b> y <b>−</b> de la esquina inferior derecha.",
               "<b>Coordenadas y terreno:</b> el recuadro de la esquina superior izquierda muestra la latitud, la longitud y el tipo de terreno bajo el cursor.",
               "<b>Ir a una unidad:</b> haga clic en su nombre en el orden de batalla; el mapa se centra en ella.",
               "<b>Ir a una región:</b> en la tarjeta Capas, los botones «Venezuela y vecinos» y «América» encuadran cada región del mapa."]),
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

    # ---------------------------------------------------------------- 5 panel derecho
    h += H1("5. El panel derecho")
    h += al_lado("panel_der_arriba", "Estado del escenario, objetivos y capas.", [
        H2("5.1 Estado del escenario"),
        P("Clima general y su visibilidad, cómo afecta al movimiento terrestre y a los ataques aéreos, la <b>fase</b> del turno (Decisión o "
          "Resolución, y si el escenario está activo, en pausa o finalizado) y el <b>modo</b>: con o sin azar en los combates, y resolución "
          "manual (la decide el instructor) o automática (cuando ambos bandos están listos)."),
        H2("5.2 Objetivos y puntaje"),
        P("El marcador de cada bando (puntos por objetivos más un punto por cada 10 de fuerza infligida al enemigo) y la lista de "
          "objetivos de su bando con su avance: ocupar una zona varios turnos, destruir una unidad o proteger una propia. Cada bando ve solo "
          "los suyos."),
    ])
    h += al_lado("panel_der_abajo", "Comunicaciones y alertas.", [
        H2("5.3 Comunicaciones"),
        P("Chat de texto del ejercicio. El alumno elige el canal: <b>Red del bando</b> (todos los puestos de su bando) o <b>Al mando "
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
    h += figura("alumno_pantalla", "Pantalla de un alumno del bando azul (puesto Estado Mayor).")
    h += [leyenda([
        ("1", "Escenario y bando", "El escenario en el que participa y su bando. Solo ve los escenarios que el instructor le asignó."),
        ("2", "Orden de batalla", "Sus unidades por rama y las enemigas que su bando detecta."),
        ("3", "Mapa", "Sus unidades, el enemigo detectado (niebla de guerra) y los últimos contactos."),
        ("4", "Panel derecho", "Estado, objetivos de su bando, capas, comunicaciones y alertas."),
        ("5", "Estoy listo", "Confirma las órdenes de su bando para el turno (6.12)."),
    ])]
    h += [H2("6.2 Su puesto"),
          P("Cada alumno ocupa un <b>puesto</b> del estado mayor de su bando. Todos ven lo mismo; cambia <b>qué unidades conducen</b>. El bloque "
            "<b>Mi puesto</b> lo recuerda y el simulador rechaza (explicando a quién corresponde) cualquier orden fuera de su puesto."),
          Tbl(["Puesto", "Conduce", "Confirma «listo»"], [
              ["EM · Estado Mayor", "Todo el bando (un solo alumno por bando)", "Sí"],
              ["A2 · Inteligencia", "Radares (encender o apagar) y guerra electrónica terrestre; sigue contactos y dibuja gráficos de blancos", "No"],
              ["A3 · Operaciones en curso", "Las aeronaves ya en el aire: rutas, patrullas, ataques, aterrizajes y misiones de grupos existentes", "No"],
              ["A4 · Logística", "Ingenieros (puentes y vados) y convoyes de abastecimiento", "No"],
              ["A5 · Planificación", "Unidades terrestres y navales, antiaérea, misiles, envío de aeronaves desde las bases y misiones programadas", "Sí"],
          ], [3.6 * cm, ANCHO_TEXTO - 6.4 * cm, 2.8 * cm])]
    h += al_lado("alumno_secciones", "Bloques del panel izquierdo de un alumno.", [
        P("En la pestaña de su panel izquierdo, debajo del orden de batalla y de la ficha de la unidad, encuentra:"),
        leyenda([("1", "Mi puesto", "Su puesto y lo que puede conducir."),
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
             "escucha enemiga no lo puede localizar (A2 o EM).",
             f"{B('Retener el fuego')} / {B('Fuego libre')} (antiaérea, destructores): con fuego libre dispara sola contra la aeronave enemiga "
             "más cercana a su alcance."]),
    ])
    h += [H2("6.4 Dar una orden: los pasos de siempre"),
          pasos("Seleccione la unidad (en el orden de batalla o con un clic en el mapa).",
                "En <b>Nueva orden</b>, elija el tipo de orden: los botones que aparecen dependen de la unidad y de su puesto.",
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
    h += [P("<b>Enviar aeronaves o drones</b> (A5 o EM):"),
          pasos(f"Pulse {B('Enviar aeronaves o drones…')} en el bloque Aviación.", "Elija el modelo en las fichas (foto, velocidad, alcances, autonomía, armamento).",
                "Elija la <b>base de origen</b> (o un portaaviones), la <b>cantidad</b> (1 a 8) y, si quiere, un <b>indicativo</b>.",
                f"Pulse {B('Enviar a despegar')}: el grupo aparece junto a la base al resolverse el turno y recibe órdenes desde el siguiente."),
          P("Una base muy dañada o sin existencias no puede lanzar aviones. Desde un portaaviones solo despegan helicópteros, drones y cazas embarcados.")]
    h += figura("orden_patrullar", "Patrulla: el grupo vuela al punto, se mantiene en la zona e intercepta a los aviones enemigos que detecte.")
    h += [Bul(["<b>Patrullar</b> (A3 o EM): clic en el punto de patrulla. Gasta combustible cada turno y, con combustible crítico, regresa sola.",
               "<b>Aterrizar</b>: elija la base o portaaviones de destino. En tierra tarda 2 turnos en reabastecer y rearmar; después cualquier orden de vuelo es el despegue."]),
          ]
    h += al_lado("perfil_vuelo", "Perfil de vuelo en la ficha de una aeronave.", [
        H3("Perfil de vuelo"),
        P("Cada aeronave vuela en un <b>perfil</b>, que se elige en su ficha con los botones <b>Alto</b>, <b>Medio</b> o <b>Rasante</b> "
          "(A3 o EM). El cambio rige de inmediato, y el mapa anota «alto» o «rasante» bajo el avión."),
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
    h += [pasos(f"Pulse {B('Planificar misión…')}.", "Elija quién la vuela: <b>un grupo existente</b> (A3) o un <b>despegue desde una base</b> en un turno futuro (A5), con modelo y cantidad.",
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
    h += [pasos("Seleccione la unidad de guerra electrónica (A2 o EM) y pulse <b>Interferir</b>.",
                "Haga clic en el centro de la zona, dentro del alcance del interferidor.", f"Pulse {B('Emitir orden')}."),
          P("Durante ese turno y la planificación del siguiente, en la zona el enemigo detecta mucho menos, su antiaérea guiada por radar pierde "
            "efecto y sus drones pierden el enlace. Pero al emitir, el enemigo localiza al interferidor.")]
    h += al_lado("cola_ordenes", "Cola de órdenes del turno.", [
        H2("6.12 La cola de órdenes y el «listo»"),
        P("La <b>cola de órdenes</b> lista las órdenes del turno de su bando, con quién las dio y su puesto:"),
        Bul(["<b>PENDIENTE</b>: se cumplirá al resolverse el turno. La «×» la cancela.",
             "<b>RESUELTA</b>: ya se cumplió; muestra el resultado (por ejemplo las pérdidas de un ataque).",
             "<b>RECHAZADA</b>: no se pudo cumplir, con el motivo (fuera de alcance, sin combustible…)."]),
        P(f"Cuando su bando terminó, el EM o el A5 pulsan {B('Estoy listo - confirmar órdenes')}. El turno se resuelve cuando el instructor lo "
          "decide, cuando ambos bandos están listos (si así lo configuró) o al agotarse el tiempo."),
    ], ancho_img=7.0 * cm)
    h += [H2("6.13 Lo que ve su bando"),
          Bul(["De las unidades enemigas solo se conoce posición, clase y bando mientras alguna unidad propia las detecte. La detección "
               "disminuye con el mal clima, el terreno (bosque, montaña, ciudad) y la interferencia.",
               "Al perder de vista a un enemigo queda su <b>último contacto</b>, en gris translúcido, con el turno en que se lo vio.",
               "Un caza enemigo se ve como caza genérico: su modelo exacto no se conoce.",
               "Las órdenes, gráficos, mensajes y alertas del otro bando nunca se ven."])]

    # ---------------------------------------------------------------- 7 instructor
    h += H1("7. Guía del instructor")
    h += [H2("7.1 Preparar un ejercicio: lista de pasos"),
          pasos("Cree el escenario: vacío con <b>Nuevo</b> o <b>Desde plantilla…</b> (7.2).",
                "Ubique las unidades de ambos bandos (7.4) y, si corresponde, las bases aéreas reales desde su capa.",
                "Fije el clima, la hora inicial y el modo de resolución (7.3); si quiere, zonas de meteorología (7.6).",
                "Cree los objetivos de cada bando (7.5).",
                "Apruebe o cree las cuentas de los alumnos y asígnelos al escenario (7.10 y 7.11).",
                "Explique la situación y deje que los bandos den órdenes; resuelva los turnos (7.12).",
                "Al terminar, finalice el escenario y conduzca el análisis con el informe (capítulo 8)."),
          H2("7.2 Crear un escenario")]
    h += figura("plantillas", "Nuevo escenario desde una plantilla.", ancho=ANCHO_TEXTO * 0.8)
    h += [Bul([f"{B('Nuevo')} crea un escenario vacío y le pide el nombre.",
               f"{B('Desde plantilla…')} crea un escenario nuevo con unidades, objetivos y clima ya cargados. Hay plantillas del sistema y las que "
               "guardaron los instructores. Entre las del sistema está «3 de enero de 2026: Operación Resolución Absoluta», que reconstruye "
               "el ataque con las aeronaves y los buques de EE. UU. que se informaron y las defensas venezolanas del litoral central."])]
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
              f"Para aeronaves, {B('Elegir aeronave…')} abre las fichas de los modelos.",
              f"Pulse {B('Ubicar en mapa')} y haga clic en el lugar: la unidad aparece allí."),
        P("Las unidades navales solo pueden ir sobre el agua. Para colocar una <b>base aérea real</b>, haga clic en el aeródromo en el mapa "
          "(capa Bases aéreas y aeródromos) y elija «Base azul» o «Base roja»."),
    ])
    h += figura("elegir_aeronave", "Elegir el modelo de aeronave: foto, prestaciones y armamento de cada uno.", ancho=ANCHO_TEXTO * 0.85)
    h += al_lado("consola_objetivos", "Consola: objetivos y puntaje.", [
        H2("7.5 Objetivos y puntaje"),
        pasos("Elija el tipo: <b>Ocupar una zona</b>, <b>Destruir una unidad</b> enemiga o <b>Proteger una unidad</b> propia.",
              "Elija para qué bando es, el nombre y los puntos.",
              "Ocupar: radio y turnos seguidos; con " + B("Ubicar la zona en el mapa") + " marque el centro. Destruir o proteger: la unidad "
              "(y, para proteger, hasta qué turno).", f"Pulse {B('Crear objetivo')}."),
        P("Cada bando ve solo sus objetivos y su avance. Además de los objetivos, cada 10 de fuerza infligida al enemigo vale 1 punto."),
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
          "el trabajo con una red degradada. El instructor ve todo al instante y sabe qué mensaje llegó a quién."),
    ])
    h += al_lado("consola_direccion", "Consola: edición e interruptores.", [
        H2("7.8 Editar el escenario y dirección del ejercicio"),
        P("<b>Editar el escenario</b>: con la casilla marcada, las unidades se reubican <b>arrastrándolas</b> en el mapa (queda registrado). Para "
          "quitar una unidad, selecciónela y use «Eliminar unidad» en su ficha."),
        P("<b>Dirección del ejercicio</b>: interruptores para simplificar con fines didácticos: niebla de guerra, consumo de combustible y "
          f"munición, efectos del clima y fuego automático. Pulse {B('Aplicar interruptores')}; cada cambio queda en el informe."),
        P("<b>Adversario automático</b>: con «el simulador conduce el bando Azul (o Rojo)» marcado, el simulador da las órdenes de ese "
          "bando al empezar cada turno y lo marca listo, para que un solo bando de alumnos entrene sin contraparte. Juega con las "
          "mismas reglas y solo con lo que su bando ve; en el pie de pantalla aparece «IA · LISTO»."),
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
        pasos("Revise el usuario y lo que pidió.", "Si hace falta, cambie el rol o el puesto en sus listas.",
              f"Pulse {B('Aprobar')} (el alumno ya puede entrar con la contraseña que eligió) o {B('Rechazar')} (se borra y el nombre queda libre)."),
        P("En la lista de usuarios se cambia el rol o el puesto de cada uno (el alumno vuelve a entrar con su nueva interfaz), se pone una "
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

    # ---------------------------------------------------------------- 8 informe
    h += H1("8. El informe posterior (AAR)")
    h += [P(f"El botón {B('Informe')} abre el análisis del ejercicio. El instructor y el observador lo ven siempre; los alumnos, cuando el "
            "escenario está finalizado. Mientras está abierto, el mapa muestra el pasado y no la situación en curso.")]
    h += figura("informe_barra", "Barra de la repetición.")
    h += [Tbl(["Botón", "Qué hace"], [
        ["&lt; y &gt;, la barra y Reproducir", "Recorren el ejercicio turno a turno: posiciones, trayectorias y combates de cada turno sobre el mapa."],
        ["Resumen", "Resumen por bando: pérdidas, unidades destruidas, objetivos y puntaje."],
        ["Línea de tiempo", "Combustible y munición de cada unidad turno a turno, cruzados con combates y reabastecimientos."],
        ["Rúbrica", "Evaluación por bando, por puesto y por alumno, con observaciones automáticas."],
        ["Imprimible", "Informe completo en una página lista para imprimir o guardar en PDF."],
        ["Diapositivas", "Presentación automática para la sesión de análisis: una diapositiva por turno, resumen y evaluación."],
        ["Replay", "Animación continua del ejercicio (8.5)."],
        ["CSV", "Combates en una hoja de cálculo."], ["Cerrar", "Vuelve a la situación en curso."],
    ], [4.2 * cm, ANCHO_TEXTO - 4.2 * cm])]
    h += figura("informe_repeticion", "Repetición del turno 2: trayectorias de las unidades y combates del turno.")
    h += figura("informe_resumen", "Resumen del ejercicio.", ancho=ANCHO_TEXTO * 0.7)
    h += figura("informe_timeline", "Línea de tiempo de logística y combates; un clic en una unidad muestra su detalle.")
    h += [P("En la <b>línea de tiempo</b> cada fila es una unidad: la línea verde es el combustible y la ámbar la munición. Los símbolos marcan "
            "caídas abruptas (▼), niveles críticos (●), reabastecimientos (▲) y combates (◆). Los filtros de arriba eligen qué mostrar y de qué bando.")]
    h += figura("informe_rubrica", "Rúbrica: indicadores por bando y por puesto, y evaluación por alumno.")
    h += [P("La <b>rúbrica</b> resume la conducción de cada bando y de cada puesto (órdenes emitidas, resueltas y rechazadas con su motivo, "
            "turnos con órdenes y turnos pasivos, logística, pérdidas, objetivos, misiones) con <b>observaciones automáticas</b>. La "
            f"<b>evaluación por alumno</b> hace lo mismo para cada usuario, y {B('CSV por alumno')} la descarga para la planilla de calificaciones.")]
    h += figura("informe_replay", "Replay animado a mitad del ejercicio: estelas, combate en curso y rótulo con hora, clima, marcador y novedades.")
    h += [H2("8.5 Replay animado"),
          P("Reproduce el ejercicio de forma continua: las unidades se mueven entre turnos, los combates destellan, las unidades destruidas se "
            "desvanecen y un rótulo muestra el turno, la hora, el clima, el marcador y las novedades."),
          Bul(["Reproducir / pausa, ir al inicio o al final.", "Velocidad 0,5×, 1×, 2× o 4×.",
               "La barra se puede arrastrar para ir a cualquier momento.", "<b>Estela</b> deja el recorrido de cada unidad en el color de su bando."])]

    # ---------------------------------------------------------------- 9 observador
    h += H1("9. El observador")
    h += figura("observador", "Pantalla del observador: todo el ejercicio, sin controles para dar órdenes.")
    h += [P("El observador ve el mapa completo de ambos bandos, sin niebla de guerra, el orden de batalla, las misiones, los objetivos y el "
            "informe en cualquier momento. No puede dar órdenes, escribir en el chat ni cambiar nada. Es el rol para evaluadores y visitas.")]

    # ---------------------------------------------------------------- 10 problemas
    h += H1("10. Preguntas frecuentes")
    h += [Tbl(["Pregunta o problema", "Respuesta"], [
        ["Mi orden aparece RECHAZADA.", "Lea el motivo en la cola: objetivo fuera de alcance o no detectado, sin combustible o munición, "
         "terreno intransitable, río sin puente, base sin existencias…"],
        ["El simulador dice que la orden corresponde a otro puesto.", "Esa unidad la conduce otra célula de su bando (6.2). Coordine por la red del bando."],
        ["No veo el botón Estoy listo.", "Solo lo tienen el Estado Mayor y el A5."],
        ["No veo a las unidades enemigas.", "Solo se ven las que su bando detecta. Acérquese con reconocimiento, drones o radares."],
        ["Las unidades se ven muy pequeñas o sin nombre.", "Es el mapa de lejos (4.2). Acerque el zoom: aparecen nombres y anillos de alcance."],
        ["El mapa sale gris o vacío.", "Faltan los datos de mapa en el servidor (avise al instructor) o se eligió una región sin datos."],
        ["El chat no llega o llega tarde.", "El instructor activó las comunicaciones simuladas (7.7): es parte del ejercicio."],
        ["El punto de conexión está rojo.", "Se perdió la conexión con el servidor; el simulador se reconecta solo. Si no, recargue la página (F5)."],
        ["No puedo abrir el informe.", "Los alumnos lo ven cuando el instructor finaliza el escenario."],
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
              ["APP-6", "Norma de simbología militar; alternativa a las miniaturas."],
              ["CAP, CAS, SEAD", "Roles de misión aérea: patrulla de combate, apoyo aéreo cercano, supresión de defensas antiaéreas."],
              ["Escalón", "Nivel de la unidad (equipo, sección, compañía, batallón, brigada)."],
              ["Fase de decisión / resolución", "Parte del turno en que se dan órdenes / en que el simulador las ejecuta."],
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
