"""Guion del video de presentacion de S.I.E.T.E.: cada escena tiene su locucion (lo que dice la voz y, tal cual, el
subtitulo), el capitulo al que pertenece y las capturas que se ven mientras habla (tools/video/capturas_video.py).

Cada imagen es (captura, movimiento de camara):
  "empuje"          acercamiento lento al centro;
  "foco"            de la pantalla entera al recuadro que el manual recortaba (salida/capturas/focos.json);
  "desde_foco"      al reves: del recuadro a la pantalla entera;
  (x, y, ancho)     de la pantalla entera a ese recuadro (pixeles de la captura 4K; el alto sale de 16:9).
Las escenas "intro" y "cierre" son placas animadas con los logotipos (sin capturas).
"""

# Como se pronuncian (solo en la voz; el subtitulo conserva la escritura).
PRONUNCIACION = {
    "S.I.E.T.E.": "Siete",
    "F-16": "efe dieciséis",
    "Su-30": "Sujói treinta",
    "AMB": "a eme be",
    "DIDA": "Dida",
}

ESCENAS = [
    {"id": "intro", "placa": "intro", "antes": 2.2, "despues": 1.2,
     "texto": "La División de Ingeniería y Desarrollo Aeroespacial de la Aviación Militar Bolivariana presenta "
              "S.I.E.T.E., el Sistema Integral de Entrenamiento Táctico y Estratégico."},

    {"id": "que_es", "capitulo": "¿Qué es S.I.E.T.E.?",
     "imagenes": [("v_instructor", "empuje")],
     "texto": "S.I.E.T.E. es un simulador para conducir operaciones terrestres, aéreas y navales en el aula. "
              "Funciona en la red local y sin conexión a internet: el mapa, el relieve, las imágenes satelitales "
              "y todos los datos se sirven desde el propio servidor."},

    {"id": "acceso", "capitulo": "Acceso y roles",
     "imagenes": [("v_acceso", (1100, 300, 1640)), ("acceso_registro", "foco")],
     "texto": "Cada participante entra con su propia cuenta. Quien no tiene una la solicita desde la pantalla de "
              "acceso, indicando su rol y su puesto, y el instructor la aprueba."},

    {"id": "roles", "capitulo": "Acceso y roles",
     "imagenes": [("pantalla_general", "empuje"), ("alumno_pantalla", (0, 0, 2400))],
     "texto": "El instructor dirige el ejercicio y lo ve todo. Los alumnos se dividen en dos bandos, azul y rojo, "
              "y el observador sigue el ejercicio sin intervenir. Dentro de cada bando, los alumnos ocupan los "
              "puestos de un estado mayor: inteligencia, operaciones, logística y planificación. Cada célula "
              "emite solo las órdenes que le corresponden."},

    {"id": "terreno", "capitulo": "El terreno",
     "imagenes": [("v_america", "empuje"), ("v_venezuela", "empuje"), ("mapa_relieve", "empuje")],
     "texto": "El teatro de operaciones abarca toda América, con imagen satelital real y un modelo de relieve. "
              "Sobre Venezuela el detalle es mayor: montañas, selvas, ríos, humedales y zonas urbanas modifican "
              "la velocidad, la defensa y la detección de cada unidad."},

    {"id": "unidades", "capitulo": "Fuerzas y unidades",
     "imagenes": [("oob", "foco"), ("ficha_unidad", "foco")],
     "texto": "El orden de batalla reúne infantería, blindados, artillería, defensa antiaérea, ingenieros, "
              "convoyes logísticos, aviación, buques y bases. Cada unidad tiene su ficha, con fuerza, combustible, "
              "munición, alcance y radio de detección, y su símbolo militar normalizado."},

    {"id": "ordenes", "capitulo": "Órdenes y turnos",
     "imagenes": [("orden_mover", (700, 250, 2700)), ("orden_atacar", (700, 250, 2700)),
                  ("seleccion_multiple", (700, 250, 2700))],
     "texto": "El ejercicio avanza por turnos de una hora simulada. Cada bando planifica sus órdenes: mover por "
              "puntos de paso, con una vista previa de dónde terminará la unidad; atacar, apoyar, o construir "
              "puentes y vados. También se pueden ordenar varias unidades a la vez, en formación."},

    {"id": "resolucion", "capitulo": "Órdenes y turnos",
     "imagenes": [("v_instructor", (900, 1300, 2200))],
     "texto": "Cuando ambos bandos confirman que están listos, el motor resuelve el turno en fases: movimiento, "
              "apoyos, combates simultáneos y logística. Cada puesto recibe el nuevo estado, filtrado según lo que "
              "su bando puede ver."},

    {"id": "niebla", "capitulo": "Niebla de guerra y sensores",
     "imagenes": [("cobertura_radar", "empuje"), ("perfil_vuelo", "foco")],
     "texto": "La niebla de guerra es real: solo se ve lo que los sensores detectan, y nada se detecta sin línea "
              "de vista. El simulador calcula las sombras del relieve, el horizonte y la cota de vuelo de cada "
              "aeronave: alta, media o rasante, para esconderse tras las montañas."},

    {"id": "aviacion", "capitulo": "Operaciones aéreas",
     "imagenes": [("aviacion_enviar", "foco"), ("mision_planificar", (600, 200, 2900)), ("cronograma", "foco")],
     "texto": "La aviación opera aeronaves como el F-16 y el Su-30 desde las bases aéreas reales. El puesto de "
              "operaciones planifica misiones de interdicción, escolta o patrulla, con navegación por puntos y un "
              "cronograma que muestra cada fase del vuelo."},

    {"id": "bases", "capitulo": "Operaciones aéreas",
     "imagenes": [("mapa_aerodromo", "empuje"), ("v_carlota", "empuje")],
     "texto": "Cada base aérea aparece con su plano real: pistas, calles de rodaje y plataformas. Sus partes pueden "
              "ser dañadas y reparadas, y los refugios reforzados protegen a las aeronaves en tierra."},

    {"id": "naval", "capitulo": "Mar y guerra electrónica",
     "imagenes": [("v_naval", "empuje"), ("naval_misiles", (700, 250, 2700)), ("naval_desembarcar", (700, 250, 2700))],
     "texto": "En el mar operan fragatas, patrulleros y portaaviones, con misiles de crucero, y las unidades "
              "anfibias embarcan, navegan y desembarcan sobre la costa."},

    {"id": "guerra_e", "capitulo": "Mar y guerra electrónica",
     "imagenes": [("orden_interferir", (700, 250, 2700))],
     "texto": "La guerra electrónica permite escuchar e interferir las emisiones del enemigo, y los radares pueden "
              "controlar sus emisiones para no delatar su posición."},

    {"id": "meteo", "capitulo": "Meteorología",
     "imagenes": [("mapa_meteo", "empuje")],
     "texto": "El instructor coloca frentes meteorológicos que se desplazan con el paso de los turnos. La lluvia y "
              "la tormenta reducen la detección, la velocidad y la eficacia de los ataques aéreos."},

    {"id": "instructor", "capitulo": "Dirección del ejercicio",
     "imagenes": [("consola_agregar", "foco"), ("consola_objetivos", "foco"), ("consola_eventos", "foco"),
                  ("plantillas", "foco")],
     "texto": "Desde la consola, el instructor crea y edita el escenario, agrega unidades, define los objetivos y "
              "el puntaje, e inyecta informes y eventos durante el ejercicio. Cada escenario se puede guardar como "
              "plantilla para volver a usarlo."},

    {"id": "equipo", "capitulo": "Trabajo en equipo",
     "imagenes": [("mapa_graficos", "empuje"), ("videowall", "empuje")],
     "texto": "Los alumnos trazan gráficos tácticos sobre el mapa y se comunican por la red de mensajes de su "
              "bando. El modo videowall proyecta la situación en la pantalla grande de la sala."},

    {"id": "aar", "capitulo": "Informe posterior al ejercicio",
     "imagenes": [("v_replay_0", "fijo"), ("v_replay_1", "fijo"), ("v_replay_2", "fijo"), ("v_replay_3", "fijo"),
                  ("informe_resumen", "foco"), ("informe_rubrica", "foco")],
     "texto": "Al finalizar, el informe posterior al ejercicio repite cada turno sobre el mapa, con trayectorias y "
              "combates animados. Muestra el resumen de cada bando y permite evaluar a cada alumno con una rúbrica."},

    {"id": "instalacion", "capitulo": "Puesta en marcha",
     "imagenes": [("v_venezuela", "desde_centro")],
     "texto": "S.I.E.T.E. se instala con un solo clic en cualquier computadora con Windows, o se lleva en una "
              "carpeta portátil, y atiende a toda el aula a través de la red local."},

    {"id": "cierre", "placa": "cierre", "antes": 0.6, "despues": 4.0,
     "texto": "S.I.E.T.E.: desarrollado por la División de Ingeniería y Desarrollo Aeroespacial. "
              "El infinito es el límite."},
]

CREDITOS = [
    "Desarrollado por la División de Ingeniería y Desarrollo Aeroespacial (DIDA)",
    "Aviación Militar Bolivariana",
    "Creador: Cap. Dixon Malpica",
]
