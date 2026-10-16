"""Videos narrados de S.I.E.T.E. para exposiciones (MP4 1920x1080, voz natural y subtitulos).

  1. SIETE_1_que_es.mp4       Que es el SIETE, como esta hecho y que puede hacer (voz: Sebastian, Venezuela).
  2. SIETE_2_como_se_usa.mp4  Como se usa: roles, reparticiones del TIEM y que hace cada uno (voz: Jorge, Mexico).

Cada escena es una captura real del simulador (tools/manual/salida, generadas por capturas_guia.py, capturas.py y
diagramas.py) con su titulo y la frase que se narra como subtitulo. La voz es neuronal de Microsoft (las voces
naturales de Edge, paquete edge-tts; necesita internet). Sin internet, o con --offline, usa las voces instaladas en
Windows (voz.ps1), que suenan mas roboticas. ffmpeg arma cada frase como un clip y los une, con fundidos entre escenas.

    backend\\venv\\Scripts\\python -m pip install edge-tts                    # una vez
    backend\\venv\\Scripts\\python tools/manual/videos_exposicion.py          # los dos
    backend\\venv\\Scripts\\python tools/manual/videos_exposicion.py 2        # solo el segundo
    backend\\venv\\Scripts\\python tools/manual/videos_exposicion.py --voz2=es-CO-GonzaloNeural --velocidad=+10%
"""

import asyncio
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
    "archivo": "SIETE_1_que_es.mp4", "voz": "es-VE-SebastianNeural", "voz_local": "Raul",
    "subtitulo_portada": "Operaciones aéreas con el Trabajo Integral de Estado Mayor",
    "escenas": [
        ("portada", "", [
            "Bienvenidos. Les presentamos el SIETE: el Sistema Integral de Entrenamiento Táctico y Estratégico.",
            "Fue desarrollado en la División de Ingeniería y Desarrollo Aeroespacial, "
            "para formar oficiales de Estado Mayor de la Aviación Militar Bolivariana en el planeamiento y la conducción "
            "de operaciones aéreas.",
        ]),
        ("pantalla_general", "Qué es el SIETE", [
            "El SIETE es un simulador de operaciones aéreas por turnos, pensado para el aula.",
            "Los alumnos integran el Estado Mayor de un componente aéreo, en dos bandos, el azul y el rojo, y "
            "planifican y conducen la campaña aérea, con el apoyo de fuerzas terrestres y navales, sobre mapas reales.",
            "Cada turno equivale a una hora simulada: los bandos dan sus órdenes, y el simulador resuelve a la vez "
            "despegues, vuelos, detecciones, combates aéreos y logística.",
        ]),
        ("titulo:Orientado al TIEM|Planeamiento y conducción de operaciones aéreas según el Trabajo Integral de Estado Mayor", "", [
            "Su eje es el Trabajo Integral de Estado Mayor, la metodología oficial para planificar y conducir operaciones.",
            "El simulador no solo resuelve combates: con él, el Estado Mayor aprecia la situación, decide, planifica, "
            "ordena y supervisa la ejecución, paso a paso, como lo establece el TIEM.",
        ]),
        ("diag_puestos", "Un Estado Mayor completo", [
            "Cada alumno ocupa una repartición: el Comandante, el Jefe de Estado Mayor, personal, inteligencia, "
            "operaciones, defensa aérea, logística, y comunicaciones y electrónica. Cada una conduce solo lo que le "
            "corresponde.",
        ]),
        ("pmo_calendario", "Problema Militar y calendario", [
            "Cada bando recibe su Problema Militar Operativo, con la misión del componente aéreo, que el instructor "
            "redacta o el simulador crea automáticamente a partir del escenario.",
            "El calendario fija el día D, la hora H y las fases de la operación.",
        ]),
        ("tiem_paso2", "Fase uno: la apreciación", [
            "El Estado Mayor redacta, dentro del simulador, los documentos del TIEM: el análisis de la misión, el "
            "concepto del comandante, la guía de planeamiento y las formas de acción con el criterio de adaptabilidad, "
            "practicabilidad y aceptabilidad.",
            "Luego cada repartición elabora su apreciación: inteligencia, operaciones, defensa aérea, personal, "
            "logística, y comunicaciones y electrónica.",
        ]),
        ("tiem_matriz", "Confrontación y juego de guerra", [
            "Las formas de acción se confrontan con las capacidades del enemigo, y se pueden ensayar en una copia del "
            "ejercicio contra la inteligencia artificial antes de decidir.",
        ]),
        ("tiem_orden", "Fase dos: del plan a la orden", [
            "El Comandante decide, y el Plan de Operaciones asigna tareas a cada unidad aérea. Esas tareas se emiten "
            "como órdenes reales del simulador, turno a turno.",
        ]),
        ("tiem_supervision", "Fase tres: la supervisión", [
            "Durante la ejecución, el simulador compara lo planeado con lo ocurrido, y el Estado Mayor registra la causa "
            "de cada desvío y la acción correctiva.",
        ]),
        ("titulo:La campaña aérea|Aviación, defensa aérea y guerra electrónica", "", [
            "Veamos ahora cómo el simulador representa la campaña aérea.",
        ]),
        ("aviacion_enviar", "Aeronaves con datos reales", [
            "El catálogo incluye cazas, aviones de ataque, cisternas, helicópteros y drones, cada uno con su "
            "foto, su alcance, su autonomía y su armamento. También se pueden agregar los tipos propios de la Aviación "
            "Militar Bolivariana.",
        ]),
        ("mision_planificar", "Misiones aéreas", [
            "La aviación despega de sus bases, cumple su misión y aterriza a reabastecerse.",
            "Cada misión se planifica con su rol y su ruta: patrulla aérea de combate, interdicción, apoyo aéreo "
            "cercano, supresión de defensas, reconocimiento o escolta.",
        ]),
        ("cronograma", "Cronograma de misiones", [
            "El cronograma muestra cada misión en el tiempo: el vuelo, la órbita, el ataque y el aterrizaje.",
        ]),
        ("perfil_vuelo", "Perfil de vuelo", [
            "Cada grupo vuela alto, a media altura o rasante: lo que gana en alcance de detección lo pierde frente al "
            "radar enemigo, y el vuelo rasante gasta más combustible.",
        ]),
        ("cobertura_radar", "Defensa aérea y sensores", [
            "Los radares tienen cobertura real según el relieve, y la defensa aérea combina alerta temprana, antiaéreas "
            "y caza de intercepción.",
        ]),
        ("orden_interferir", "Guerra electrónica", [
            "La guerra electrónica escucha las emisiones del enemigo y las interfiere, a costa de quedar expuesta.",
        ]),
        ("mapa_relieve", "Teatro de operaciones real", [
            "El terreno es real: Venezuela en detalle y toda América, con relieve, ríos, carreteras, ciudades y fronteras. "
            "El relieve tapa la línea de vista de los radares.",
        ]),
        ("mapa_ficticio", "Un teatro ficticio", [
            "Para ejercicios que no deben involucrar a ningún país real, hay un mapa ficticio completo: el País Azul y el "
            "País Rojo, con bases aéreas, ciudades e infraestructura.",
        ]),
        ("mapa_noche", "Clima, día y noche", [
            "El clima por zonas y el ciclo de día y noche cambian la detección y las operaciones aéreas.",
        ]),
        ("mapa_infraestructura", "Objetivos estratégicos", [
            "Las centrales eléctricas, refinerías, centros de comunicaciones y puentes son objetivos: si caen, los "
            "radares pierden alcance, falta combustible y las órdenes se demoran.",
        ]),
        ("ia_pantalla", "Adversario automático", [
            "Si no hay alumnos para un bando, lo conduce el adversario automático, con tres niveles: prudente, normal y "
            "agresivo. El instructor también puede jugar de enemigo.",
        ]),
        ("diag_arquitectura", "Cómo está hecho", [
            "El SIETE es una aplicación web que se instala en un solo equipo del aula y se usa desde cualquier navegador "
            "de la red local.",
            "No necesita internet: los mapas satelitales, el relieve, los planos de las bases aéreas y el catálogo viajan "
            "con el propio simulador, en un paquete portátil.",
            "Es un desarrollo nacional, verificado con más de setecientas pruebas automáticas.",
        ]),
        ("informe_doctrina", "Evaluación", [
            "Al final, el informe posterior reproduce el ejercicio turno a turno y evalúa la conducción con indicadores "
            "doctrinales, el trabajo de Estado Mayor según el TIEM, y una nota de uno a veinte por bando y por alumno.",
        ]),
        ("legajo_word", "Documentos en Word y PDF", [
            "Todos los documentos del TIEM se exportan a Word o a PDF, con el formato del TIEM.",
        ]),
        ("cierre", "", [
            "El SIETE: desarrollado en la DIDA para formar oficiales de Estado Mayor de la Aviación Militar Bolivariana, "
            "en el planeamiento y la conducción de operaciones aéreas, con soberanía tecnológica.",
            "Muchas gracias.",
        ]),
    ],
}

VIDEO_2 = {
    "archivo": "SIETE_2_como_se_usa.mp4", "voz": "es-MX-JorgeNeural", "voz_local": "Raul", "subtitulo_portada": "Cómo se usa: roles y tareas de cada uno",
    "escenas": [
        ("portada", "", [
            "En este video veremos cómo se usa el SIETE para formar oficiales de Estado Mayor de la Aviación Militar "
            "Bolivariana con el Trabajo Integral de Estado Mayor: los roles del ejercicio y lo que hace cada participante.",
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


VELOCIDAD = "+8%"  # ritmo de la voz natural (0% = normal)
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
    im = Image.open(IMG / nombre)
    im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
    return im.resize((int(im.width * alto / im.height), alto), Image.LANCZOS)


def pegar(fondo_im: Image.Image, im: Image.Image, xy) -> None:
    """Pega respetando la transparencia (el logo redondo de la DIDA)."""
    fondo_im.paste(im, xy, im if im.mode == "RGBA" else None)


def centrado(d, y, texto, f, color=(255, 255, 255)):
    d.text((ANCHO / 2, y), texto, font=f, fill=color, anchor="mm")


def portada(subtitulo: str) -> Image.Image:
    im = fondo()
    aguila = logo("siete_aguila.png", 330)
    pegar(im, aguila, ((ANCHO - aguila.width) // 2, 36))
    d = ImageDraw.Draw(im)
    centrado(d, 435, "S.I.E.T.E.", fuente(80, True))
    centrado(d, 510, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(38), (200, 214, 235))
    centrado(d, 572, subtitulo, fuente(40, True), AMBAR)
    dida = logo("dida_logo_redondo.png", 180)
    x = ANCHO // 2 - 470
    pegar(im, dida, (x, 640))
    d.text((x + dida.width + 36, 668), "División de Ingeniería y Desarrollo Aeroespacial (DIDA)", font=fuente(30, True), fill=(255, 255, 255))
    d.text((x + dida.width + 36, 714), "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana", font=fuente(28), fill=(200, 214, 235))
    d.text((x + dida.width + 36, 760), "Simulador de operaciones aéreas orientado al TIEM", font=fuente(30, True), fill=AMBAR)
    return im


def cierre() -> Image.Image:
    im = fondo()
    aguila = logo("siete_aguila.png", 300)
    dida = logo("dida_logo_redondo.png", 300)
    hueco = 70
    x = (ANCHO - aguila.width - dida.width - hueco) // 2
    pegar(im, aguila, (x, 50))
    pegar(im, dida, (x + aguila.width + hueco, 50))
    d = ImageDraw.Draw(im)
    centrado(d, 450, "S.I.E.T.E.", fuente(72, True))
    centrado(d, 518, "Sistema Integral de Entrenamiento Táctico y Estratégico", fuente(36), (200, 214, 235))
    centrado(d, 600, "Desarrollado en la División de Ingeniería y Desarrollo Aeroespacial (DIDA)", fuente(38, True), AMBAR)
    centrado(d, 655, "Aviación Militar Bolivariana · Fuerza Armada Nacional Bolivariana", fuente(30))
    centrado(d, 730, "«El infinito es el límite»", fuente(34, True), (200, 214, 235))
    return im


def separador(titulo: str, subtitulo: str) -> Image.Image:
    im = fondo()
    aguila = logo("siete_aguila.png", 200)
    pegar(im, aguila, ((ANCHO - aguila.width) // 2, 100))
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
    pegar(im, icono, (36, 16))
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
async def _voces_naturales(frases: list[dict], voz: str) -> None:
    import edge_tts

    limite = asyncio.Semaphore(4)

    async def una(f):
        mp3 = f["wav"].with_suffix(".mp3")
        async with limite:
            for intento in range(4):
                try:
                    await edge_tts.Communicate(_hablado(f["texto"]), voz, rate=VELOCIDAD).save(str(mp3))
                    break
                except Exception:
                    if intento == 3:
                        raise
                    await asyncio.sleep(2 + 3 * intento)
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(f["wav"])],
                       check=True)

    await asyncio.gather(*(una(f) for f in frases))


def _voces_locales(frases: list[dict], voz: str, carpeta: Path) -> None:
    lista = carpeta / "voces.json"
    lista.write_text(json.dumps([{"texto": _hablado(f["texto"]), "archivo": str(f["wav"]).replace("\\", "/"), "voz": voz}
                                 for f in frases], ensure_ascii=False), encoding="utf-8")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(Path(__file__).with_name("voz.ps1")),
                    "-Lista", str(lista)], check=True)


def _duracion(wav: Path) -> float:
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def generar(video: dict, n: int, offline: bool = False) -> Path:
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
    if offline:
        _voces_locales(frases, video["voz_local"], carpeta)
    else:
        try:
            asyncio.run(_voces_naturales(frases, video["voz"]))
        except Exception as e:  # sin internet o sin edge-tts: voces de Windows
            print(f"Voces naturales no disponibles ({e}); se usan las de Windows.")
            _voces_locales(frases, video["voz_local"], carpeta)
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
    """Opciones: 1 o 2 (solo ese video), --offline, --voz1=es-VE-SebastianNeural, --voz2=..., --velocidad=+8%."""
    global VELOCIDAD
    opciones = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    VIDEO_1["voz"] = opciones.get("voz1", VIDEO_1["voz"])
    VIDEO_2["voz"] = opciones.get("voz2", VIDEO_2["voz"])
    VELOCIDAD = opciones.get("velocidad", VELOCIDAD)
    offline = "--offline" in sys.argv
    pedidos = [a for a in sys.argv[1:] if not a.startswith("--")] or ["1", "2"]
    DESTINO.mkdir(parents=True, exist_ok=True)
    for n, video in ((1, VIDEO_1), (2, VIDEO_2)):
        if str(n) in pedidos:
            generar(video, n, offline)


if __name__ == "__main__":
    main()
