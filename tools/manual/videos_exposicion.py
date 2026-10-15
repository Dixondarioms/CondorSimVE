"""Videos narrados de S.I.E.T.E. para exposiciones (MP4 1920x1080, voz de Microsoft y subtitulos).

  1. SIETE_1_que_es.mp4       Que es el SIETE, como esta hecho y que puede hacer (voz: Raul).
  2. SIETE_2_como_se_usa.mp4  Como se usa: roles, reparticiones del TIEM y que hace cada uno (voz: Sabina).

Cada escena es una captura real del simulador (tools/manual/salida, generadas por capturas_guia.py, capturas.py y
diagramas.py) con su titulo y la frase que se narra como subtitulo. La voz sale de las voces de Microsoft instaladas
en Windows (voz.ps1) y ffmpeg arma cada frase como un clip y los une, con fundidos entre escenas.

    backend\\venv\\Scripts\\python tools/manual/videos_exposicion.py          # los dos
    backend\\venv\\Scripts\\python tools/manual/videos_exposicion.py 2        # solo el segundo
"""

import json
import re
import shutil
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
SALIDA_CAPT = RAIZ / "tools" / "manual" / "salida"
TRABAJO = RAIZ / "dist" / "video" / "trabajo"
DESTINO = RAIZ / "dist" / "video"
IMG = RAIZ / "frontend" / "static" / "img"
FUENTES = Path(r"C:\Windows\Fonts")
ANCHO, ALTO, FPS = 1920, 1080, 25
AMBAR = (255, 196, 0)
FFMPEG = shutil.which("ffmpeg") or str(next(Path.home().glob(
    "AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg*/*/bin/ffmpeg.exe")))


def fuente(tam, negrita=False):
    return ImageFont.truetype(str(FUENTES / ("arialbd.ttf" if negrita else "arial.ttf")), tam)


# ------------------------------------------------------------------ guiones
# Cada escena: (captura | "portada" | "cierre" | "titulo:Texto|Subtitulo", titulo en pantalla, [frases narradas])
VIDEO_1 = {
    "archivo": "SIETE_1_que_es.mp4", "voz": "Raul", "subtitulo_portada": "Qué es, cómo está hecho y qué puede hacer",
    "escenas": [
        ("portada", "", [
            "Bienvenidos. Les presentamos el SIETE: el Sistema Integral de Entrenamiento Táctico y Estratégico.",
            "Fue concebido, diseñado y desarrollado por el Capitán Dixon Malpica, en la División de Ingeniería y "
            "Desarrollo Aeroespacial de la Aviación Militar Bolivariana.",
        ]),
        ("pantalla_general", "Qué es el SIETE", [
            "El SIETE es un simulador de ejercicios militares por turnos, pensado para el aula.",
            "Un instructor dirige el ejercicio, y los alumnos, organizados en dos bandos, el azul y el rojo, planifican y "
            "conducen operaciones aéreas, terrestres y navales sobre mapas reales.",
            "Cada turno equivale a una hora simulada: los bandos dan sus órdenes, y el simulador resuelve a la vez "
            "movimientos, detecciones, combates y logística.",
        ]),
        ("diag_arquitectura", "Cómo está hecho", [
            "El simulador es una aplicación web que se instala en un solo equipo del aula y se usa desde cualquier "
            "navegador de la red local.",
            "No necesita internet: los mapas satelitales, el relieve, los planos de las bases aéreas y el catálogo de "
            "unidades viajan con el propio simulador.",
            "El servidor está escrito en Python, con una base de datos que guarda cada ejercicio, y la pantalla se "
            "actualiza en tiempo real para todos los participantes.",
            "Funciona en una sola computadora, se lleva en un paquete portátil, y cuenta con más de setecientas pruebas "
            "automáticas que verifican cada función.",
        ]),
        ("diag_ciclo", "El ciclo de cada turno", [
            "Cada turno tiene dos fases: la decisión, en la que los bandos dan órdenes, y la resolución, en la que el "
            "motor calcula lo que ocurre.",
            "Cada bando ve solo lo que sus sensores detectan: es la niebla de guerra. Del enemigo se conocen únicamente "
            "los contactos.",
        ]),
        ("mapa_relieve", "Mapas reales, con relieve", [
            "El terreno es real: Venezuela en detalle y toda América, con relieve, ríos, carreteras, ciudades y fronteras.",
            "El relieve importa: tapa la línea de vista de los radares, y los aviones pueden volar alto, a media altura o "
            "rasantes para esconderse.",
        ]),
        ("mapa_ficticio", "Un mapa ficticio para ejercitar sin países reales", [
            "Para ejercicios que no deben involucrar a ningún país real, el simulador trae un mapa ficticio completo: el "
            "País Azul y el País Rojo.",
            "Tiene cordilleras, llanos, ríos, embalses, ciudades, carreteras e infraestructura, igual que un país verdadero.",
        ]),
        ("aviacion_enviar", "Unidades con datos y fotos reales", [
            "El catálogo incluye unidades terrestres, aéreas y navales: cazas, aviones de ataque, helicópteros, drones, "
            "defensa antiaérea, radares, buques y misiles.",
            "Cada modelo tiene su foto, sus prestaciones y su armamento, y el instructor puede agregar los tipos propios "
            "de la Aviación Militar Bolivariana.",
        ]),
        ("mision_planificar", "Aviación y misiones", [
            "La aviación despega de sus bases, patrulla, ataca y aterriza a reabastecerse.",
            "Las misiones aéreas se planifican con su rol y su ruta: patrulla de combate, interdicción, apoyo cercano, "
            "supresión de defensas, reconocimiento o escolta.",
        ]),
        ("cobertura_radar", "Sensores y guerra electrónica", [
            "Los radares tienen cobertura real según el terreno. La guerra electrónica escucha las emisiones del enemigo "
            "y las interfiere, a costa de quedar expuesta.",
        ]),
        ("mapa_dia_noche" if (SALIDA_CAPT / "guia" / "mapa_dia_noche.png").exists() else "mapa_noche", "Clima, día y noche", [
            "El clima por zonas y el ciclo de día y noche cambian la detección y el movimiento.",
        ]),
        ("mapa_infraestructura", "Infraestructura que pesa en la guerra", [
            "Las centrales eléctricas, refinerías, centros de comunicaciones y puentes son objetivos: si caen, los "
            "radares pierden alcance, falta combustible y las órdenes se demoran.",
        ]),
        ("situacion_radar", "La pestaña Situación", [
            "El cuadro radar muestra lo que detecta cada sensor, y los contactos nuevos se informan solos al bando.",
            "También se siguen el personal, las bajas y el estado de la infraestructura.",
        ]),
        ("ia_pantalla", "Combate contra la inteligencia artificial", [
            "Si no hay alumnos para un bando, lo puede conducir el adversario automático, con tres niveles: prudente, "
            "normal y agresivo.",
        ]),
        ("titulo:El Trabajo Integral de Estado Mayor|La metodología del TIEM dentro del simulador", "", [
            "Lo más importante: el SIETE sigue el Trabajo Integral de Estado Mayor, la metodología oficial para "
            "planificar y conducir operaciones.",
        ]),
        ("pmo_calendario", "Problema Militar y calendario", [
            "Cada bando recibe su Problema Militar Operativo, que el instructor redacta o el simulador crea "
            "automáticamente a partir del escenario.",
            "El calendario fija el día D, la hora H y las fases de la operación.",
        ]),
        ("tiem_paso2", "Apreciación de la situación", [
            "El Estado Mayor redacta, dentro del simulador, los documentos del TIEM: el análisis de la misión, el "
            "concepto del comandante, la guía de planeamiento y las formas de acción con el criterio de adaptabilidad, "
            "practicabilidad y aceptabilidad.",
            "Luego, cada repartición elabora su apreciación: inteligencia, operaciones, defensa aérea, personal, "
            "logística, y comunicaciones y electrónica.",
        ]),
        ("tiem_matriz", "Confrontación y juego de guerra", [
            "Las formas de acción se confrontan con las capacidades del enemigo, y se pueden ensayar en una copia del "
            "ejercicio contra la inteligencia artificial.",
        ]),
        ("tiem_orden", "Del plan a la orden", [
            "El comandante decide, y el Plan de Operaciones asigna tareas a cada unidad. Esas tareas se emiten como "
            "órdenes reales del simulador, turno a turno.",
        ]),
        ("tiem_supervision", "Supervisión de la ejecución", [
            "Durante la ejecución, el simulador compara lo planeado con lo ocurrido, y el Estado Mayor registra la causa "
            "de cada desvío y la acción correctiva.",
        ]),
        ("informe_doctrina", "Evaluación", [
            "Al final, el informe posterior reproduce el ejercicio turno a turno y evalúa la conducción con indicadores "
            "doctrinales, el trabajo de Estado Mayor y una nota de uno a veinte por bando y por alumno.",
        ]),
        ("legajo_word", "Documentos en Word y PDF", [
            "Todos los documentos se exportan a Word o a PDF, con el formato del TIEM.",
        ]),
        ("cierre", "", [
            "El SIETE: una herramienta nacional para formar oficiales de Estado Mayor, con soberanía tecnológica.",
            "Muchas gracias.",
        ]),
    ],
}

VIDEO_2 = {
    "archivo": "SIETE_2_como_se_usa.mp4", "voz": "Sabina", "subtitulo_portada": "Cómo se usa: roles y tareas de cada uno",
    "escenas": [
        ("portada", "", [
            "En este video veremos cómo se usa el SIETE: los roles del ejercicio y lo que hace cada participante.",
        ]),
        ("diag_puestos", "Los roles del ejercicio", [
            "Hay tres roles. El instructor dirige el ejercicio. Los alumnos integran el Estado Mayor de cada bando. Y el "
            "observador ve todo, sin poder cambiar nada.",
            "Dentro de cada bando, cada alumno ocupa una repartición del Estado Mayor: el Comandante, el Jefe de Estado "
            "Mayor, la A uno de personal, la A dos de inteligencia, la A tres de operaciones, la A tres de defensa "
            "aérea, la A cuatro de logística, y comunicaciones y electrónica.",
        ]),
        ("acceso_login", "Entrar al simulador", [
            "Para entrar, se abre el navegador con la dirección del servidor del aula, y cada uno ingresa con su usuario "
            "y su contraseña.",
        ]),
        ("acceso_registro", "Pedir una cuenta", [
            "Quien no tiene cuenta la solicita desde la misma pantalla, eligiendo su rol y su repartición. El instructor "
            "la aprueba.",
        ]),
        ("titulo:El instructor|Prepara, dirige y evalúa el ejercicio", "", [
            "Empecemos por el instructor.",
        ]),
        ("plantillas", "Crear el escenario", [
            "El instructor crea el escenario desde cero o desde una plantilla, con las unidades y los objetivos ya "
            "cargados. Hay plantillas sobre Venezuela, contra la inteligencia artificial, y sobre el mapa ficticio.",
        ]),
        ("consola_agregar", "Ubicar unidades", [
            "En la consola agrega unidades con un clic en el mapa, eligiendo su clase y su modelo.",
        ]),
        ("consola_objetivos", "Objetivos de cada bando", [
            "Fija los objetivos de cada bando, organizados en la cadena del TIEM: el objetivo ulterior, los asignados y "
            "los materiales, cada uno con su efecto deseado y su indicador.",
        ]),
        ("pmo_instructor", "La situación inicial", [
            "Con un solo botón, el simulador crea la situación automáticamente: redacta el Problema Militar Operativo de "
            "cada bando, fija el calendario y arma la cadena de objetivos. El instructor la puede corregir a mano.",
        ]),
        ("consola_calendario", "Calendario de la operación", [
            "En el calendario fija la fecha, el turno de la hora H, la duración y las fases de la operación.",
        ]),
        ("consola_ia", "Quién conduce cada bando", [
            "Para cada bando elige quién lo conduce: un grupo de alumnos, el propio instructor, o el adversario automático.",
        ]),
        ("consola_usuarios", "Usuarios y reparticiones", [
            "En la sección de usuarios aprueba las cuentas, asigna a cada alumno su bando y su repartición, y los "
            "habilita en el escenario.",
        ]),
        ("titulo:El Estado Mayor de cada bando|Apreciación, decisión, plan y conducción", "", [
            "Ahora, el trabajo de los alumnos, que siguen las tres fases del TIEM.",
        ]),
        ("alumno_pantalla", "La pantalla del alumno", [
            "El alumno ve su orden de batalla, el mapa con la niebla de guerra, los objetivos de su bando, las "
            "comunicaciones y las alertas.",
        ]),
        ("pmo_mision", "Leer el Problema Militar", [
            "Todo empieza en la pestaña TIEM, con el Problema Militar Operativo: la situación, la misión del escalón "
            "superior y la misión del componente aéreo, redactada como tarea, a fin de, propósito.",
        ]),
        ("tiem_lista", "Fase uno: la apreciación inicial", [
            "El Comandante y el Jefe de Estado Mayor redactan el análisis de la misión y el concepto del comandante. El "
            "Jefe de Estado Mayor emite la guía de planeamiento.",
            "Cada documento se presenta al instructor, que lo aprueba o lo devuelve con observaciones.",
        ]),
        ("tiem_analisis", "Ayudas del simulador", [
            "El simulador ayuda con lo que es transcripción: trae los datos del Problema Militar y calcula el poder "
            "relativo de combate. El análisis lo hacen los alumnos.",
        ]),
        ("tiem_formas", "Las formas de acción", [
            "La A tres, la A tres de defensa aérea y la A dos elaboran al menos dos formas de acción, y analizan cada "
            "una con el criterio de adaptabilidad, practicabilidad y aceptabilidad.",
        ]),
        ("tiem_paso2", "Las apreciaciones de cada repartición", [
            "Luego, cada repartición presenta su apreciación. La A dos analiza las capacidades del enemigo. La A uno, el "
            "personal. La A cuatro, la logística. Y comunicaciones y electrónica, los enlaces y la guerra electrónica.",
        ]),
        ("tiem_matriz", "Confrontar las formas de acción", [
            "Operaciones y defensa aérea confrontan cada forma de acción con cada capacidad del enemigo, las comparan y "
            "recomiendan la mejor.",
        ]),
        ("tiem_ensayos", "El juego de guerra", [
            "Antes de decidir, el bando puede ensayar una forma de acción en una copia del ejercicio, contra la "
            "inteligencia artificial, y usar el resultado en su análisis.",
        ]),
        ("tiem_decision", "La decisión del Comandante", [
            "Oídas las apreciaciones, el Comandante decide la forma de acción, con su fundamentación y su idea de la "
            "maniobra.",
        ]),
        ("tiem_plan_editar", "Fase dos: el Plan de Operaciones", [
            "En la fase dos, el Plan de Operaciones asigna tareas a cada unidad: qué acción, contra qué objetivo o hacia "
            "dónde, y en qué turno.",
        ]),
        ("tiem_orden", "La Orden de Operaciones", [
            "En cada turno, la Orden de Operaciones muestra las tareas que vencen, y con un botón se emiten como órdenes "
            "reales. Si alguna no se puede cumplir, el simulador explica el motivo.",
        ]),
        ("orden_mover", "Dar órdenes directas", [
            "También se dan órdenes directas: se selecciona la unidad, se elige mover, atacar, apoyar o patrullar, y se "
            "marca en el mapa. El simulador muestra la ruta y el tiempo de recorrido.",
            "Cada repartición conduce solo sus unidades. Por ejemplo, los radares y la antiaérea son de la A tres de "
            "defensa aérea, y la guerra electrónica es de comunicaciones y electrónica.",
        ]),
        ("cola_ordenes", "Confirmar el turno", [
            "Cuando el bando terminó, el Comandante o el Jefe de Estado Mayor pulsan Estoy listo, y el turno se "
            "resuelve.",
        ]),
        ("tiem_supervision", "Fase tres: la supervisión", [
            "En la fase tres, el cuadro de supervisión compara lo planeado con lo ocurrido. El Estado Mayor registra la "
            "causa de cada desvío, la acción correctiva, y si hace falta, da órdenes fragmentarias.",
        ]),
        ("tiem_instructor", "El instructor revisa", [
            "Durante todo el ejercicio, el instructor revisa los documentos, los aprueba o los devuelve, y les pone nota.",
        ]),
        ("instructor_conduce", "El instructor puede jugar de enemigo", [
            "Si el instructor conduce un bando, entra como su comandante, con su niebla de guerra, y da sus órdenes.",
        ]),
        ("consola_eventos", "Dirigir el ejercicio", [
            "El instructor también inyecta eventos e informes de inteligencia, cambia el clima, y resuelve los turnos.",
        ]),
        ("observador", "El observador", [
            "El observador ve el ejercicio completo, sin niebla de guerra, y el informe. Es el rol para evaluadores y "
            "visitas.",
        ]),
        ("tiem_evaluacion", "Evaluación y legajo", [
            "Al terminar, cada bando ve la evaluación de su trabajo de Estado Mayor, con su nota, y descarga el legajo "
            "completo en Word o en PDF.",
        ]),
        ("informe_repeticion", "El informe posterior", [
            "Y el instructor conduce el análisis posterior: la repetición turno a turno, la rúbrica por bando y por "
            "alumno, y la calificación.",
        ]),
        ("cierre", "", [
            "Así se usa el SIETE: un Estado Mayor completo, trabajando con el TIEM, en un ejercicio que se juega y se "
            "evalúa en el aula. Muchas gracias.",
        ]),
    ],
}


NUMEROS = {"uno": "1", "dos": "2", "tres": "3", "cuatro": "4"}


def _hablado(frase: str) -> str:
    """Lo que dice la voz: las siglas que se leen como palabra."""
    return frase.replace("TIEM", "Tiem").replace("SIETE", "Siete")


def _escrito(frase: str) -> str:
    """El subtitulo: las reparticiones con su sigla (la A tres -> la A-3)."""
    return re.sub(r"\bA (uno|dos|tres|cuatro)\b", lambda m: "A-" + NUMEROS[m.group(1)], frase)


# ------------------------------------------------------------------ cuadros
def fondo() -> Image.Image:
    im = Image.new("RGB", (ANCHO, ALTO))
    d = ImageDraw.Draw(im)
    for y in range(ALTO):
        k = y / ALTO
        d.line([(0, y), (ANCHO, y)], fill=(int(12 + 18 * k), int(18 + 22 * k), int(36 + 40 * k)))
    return im


def logo(nombre: str, alto: int) -> Image.Image:
    im = Image.open(IMG / nombre).convert("RGB")
    return im.resize((int(im.width * alto / im.height), alto), Image.LANCZOS)


def centrado(d, y, texto, f, color=(255, 255, 255)):
    d.text((ANCHO / 2, y), texto, font=f, fill=color, anchor="mm")


def portada(subtitulo: str) -> Image.Image:
    im = fondo()
    siete = logo("siete_logo_recortado.jpg", 330)
    im.paste(siete, ((ANCHO - siete.width) // 2, 36))
    d = ImageDraw.Draw(im)
    centrado(d, 435, "S.I.E.T.E.", fuente(80, True))
    centrado(d, 510, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(38), (200, 214, 235))
    centrado(d, 572, subtitulo, fuente(40, True), AMBAR)
    dida = logo("dida_logo.jpg", 180)
    x = ANCHO // 2 - 470
    im.paste(dida, (x, 640))
    d.text((x + dida.width + 36, 668), "División de Ingeniería y Desarrollo Aeroespacial (DIDA)", font=fuente(30, True), fill=(255, 255, 255))
    d.text((x + dida.width + 36, 714), "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana", font=fuente(28), fill=(200, 214, 235))
    d.text((x + dida.width + 36, 760), "Creador del simulador: Cap. Dixon Malpica", font=fuente(30, True), fill=AMBAR)
    return im


def cierre() -> Image.Image:
    im = fondo()
    siete = logo("siete_logo_recortado.jpg", 300)
    dida = logo("dida_logo.jpg", 300)
    hueco = 60
    x = (ANCHO - siete.width - dida.width - hueco) // 2
    im.paste(siete, (x, 50))
    im.paste(dida, (x + siete.width + hueco, 50))
    d = ImageDraw.Draw(im)
    centrado(d, 450, "S.I.E.T.E.", fuente(72, True))
    centrado(d, 518, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(36), (200, 214, 235))
    centrado(d, 600, "Concebido, diseñado y desarrollado por el Cap. Dixon Malpica", fuente(38, True), AMBAR)
    centrado(d, 655, "División de Ingeniería y Desarrollo Aeroespacial (DIDA) · Aviación Militar Bolivariana", fuente(30))
    centrado(d, 730, "«El infinito es el límite»", fuente(34, True), (200, 214, 235))
    return im


def separador(titulo: str, subtitulo: str) -> Image.Image:
    im = fondo()
    d = ImageDraw.Draw(im)
    centrado(d, 380, titulo, fuente(66, True))
    centrado(d, 465, subtitulo, fuente(36), (200, 214, 235))
    d.line([(ANCHO / 2 - 240, 520), (ANCHO / 2 + 240, 520)], fill=AMBAR, width=4)
    return im


def _captura(nombre: str) -> Image.Image:
    for ruta in (SALIDA_CAPT / "guia" / f"{nombre}.png", SALIDA_CAPT / f"{nombre}.png"):
        if ruta.exists():
            return Image.open(ruta).convert("RGB")
    raise FileNotFoundError(nombre)


SUB_FUENTE, SUB_LINEA, SUB_ANCHO = 34, 44, 92


def _lineas(frase: str) -> list[str]:
    return textwrap.wrap(frase, width=SUB_ANCHO)


def _alto_sub(n_lineas: int) -> int:
    return 24 + SUB_LINEA * n_lineas


def escena_base(clave: str, titulo: str, subtitulo_portada: str, max_lineas: int = 3) -> Image.Image:
    """Cuadro sin subtitulo: portada, cierre, separador o captura con su titulo."""
    if clave == "portada":
        return portada(subtitulo_portada)
    if clave == "cierre":
        return cierre()
    if clave.startswith("titulo:"):
        t, _, sub = clave[7:].partition("|")
        return separador(t, sub)
    im = fondo()
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, ANCHO, 96], fill=(14, 22, 44))
    d.line([(0, 96), (ANCHO, 96)], fill=AMBAR, width=3)
    icono = logo("siete_icono_128.png", 64)
    im.paste(icono, (36, 16))
    d.text((120, 48), titulo, font=fuente(44, True), fill=(255, 255, 255), anchor="lm")
    d.text((ANCHO - 40, 48), "S.I.E.T.E. · DIDA", font=fuente(26), fill=(200, 214, 235), anchor="rm")
    cap = _captura(clave)
    arriba = 116
    caja_w, caja_h = ANCHO - 160, ALTO - 26 - _alto_sub(max_lineas) - 22 - arriba
    escala = min(caja_w / cap.width, caja_h / cap.height, 2.2)
    cap = cap.resize((int(cap.width * escala), int(cap.height * escala)), Image.LANCZOS)
    x, y = (ANCHO - cap.width) // 2, arriba + (caja_h - cap.height) // 2
    sombra = Image.new("RGBA", (cap.width + 40, cap.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rectangle([20, 20, cap.width + 20, cap.height + 20], fill=(0, 0, 0, 150))
    sombra = sombra.filter(ImageFilter.GaussianBlur(12))
    im.paste(sombra, (x - 14, y - 6), sombra)
    im.paste(cap, (x, y))
    d.rectangle([x - 1, y - 1, x + cap.width, y + cap.height], outline=(90, 110, 150), width=2)
    return im


def con_subtitulo(base: Image.Image, frase: str) -> Image.Image:
    im = base.copy()
    d = ImageDraw.Draw(im, "RGBA")
    lineas = _lineas(_escrito(frase))
    f = fuente(SUB_FUENTE)
    y0 = ALTO - 26 - _alto_sub(len(lineas))
    d.rounded_rectangle([70, y0, ANCHO - 70, ALTO - 26], radius=14, fill=(0, 0, 0, 200))
    for i, linea in enumerate(lineas):
        d.text((ANCHO / 2, y0 + 12 + SUB_LINEA // 2 + SUB_LINEA * i), linea, font=f, fill=(255, 255, 255), anchor="mm")
    return im


# ------------------------------------------------------------------ armado
def _duracion(wav: Path) -> float:
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def generar(video: dict, n: int) -> Path:
    carpeta = TRABAJO / f"video{n}"
    if carpeta.exists():
        shutil.rmtree(carpeta)
    carpeta.mkdir(parents=True)
    frases = []
    for i, (clave, titulo, textos) in enumerate(video["escenas"]):
        base = escena_base(clave, titulo, video["subtitulo_portada"], max(len(_lineas(_escrito(t))) for t in textos))
        for j, t in enumerate(textos):
            png = carpeta / f"{i:03d}_{j:02d}.png"
            con_subtitulo(base, t).save(png)
            frases.append({"png": png, "wav": carpeta / f"{i:03d}_{j:02d}.wav", "texto": t,
                           "primera": j == 0, "ultima": j == len(textos) - 1})
    lista = carpeta / "voces.json"
    lista.write_text(json.dumps([{"texto": _hablado(f["texto"]), "archivo": str(f["wav"]).replace("\\", "/"), "voz": video["voz"]}
                                 for f in frases], ensure_ascii=False), encoding="utf-8")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(Path(__file__).with_name("voz.ps1")),
                    "-Lista", str(lista)], check=True)
    clips = []
    for k, f in enumerate(frases):
        dur = _duracion(f["wav"]) + (0.9 if f["ultima"] else 0.35) + (0.3 if f["primera"] else 0.0)
        filtros = []
        if f["primera"]:
            filtros.append("fade=t=in:st=0:d=0.35")
        if f["ultima"]:
            filtros.append(f"fade=t=out:st={dur - 0.4:.2f}:d=0.4")
        clip = carpeta / f"clip_{k:03d}.mp4"
        retraso = "adelay=300|300," if f["primera"] else ""
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(f["png"]),
                        "-i", str(f["wav"]), "-t", f"{dur:.2f}",
                        "-vf", ",".join(filtros + ["format=yuv420p"]),
                        "-af", f"{retraso}aresample=44100,apad", "-ac", "2",
                        "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "20", "-r", str(FPS),
                        "-c:a", "aac", "-b:a", "160k", str(clip)], check=True)
        clips.append(clip)
    concat = carpeta / "lista.txt"
    concat.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    salida = DESTINO / video["archivo"]
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(salida)], check=True)
    total = sum(_duracion(f["wav"]) for f in frases)
    print(f"{salida} ({len(frases)} frases, unos {total / 60:.1f} min de voz)")
    return salida


def main() -> None:
    pedidos = sys.argv[1:] or ["1", "2"]
    DESTINO.mkdir(parents=True, exist_ok=True)
    for n, video in ((1, VIDEO_1), (2, VIDEO_2)):
        if str(n) in pedidos:
            generar(video, n)


if __name__ == "__main__":
    main()
