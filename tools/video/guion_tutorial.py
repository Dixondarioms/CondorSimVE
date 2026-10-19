"""Guion del video TUTORIAL de S.I.E.T.E.: como se usa el simulador paso a paso, para el instructor y los alumnos.

Mismo formato que guion.py (lo lee generar_video.py con --guion guion_tutorial y locucion.py con --guion guion_tutorial):
cada escena tiene su locucion (voz y subtitulo), el capitulo y las imagenes que se ven mientras habla. Ademas de las
capturas 4K (capturas_video.py) usa clips del simulador en marcha (clips_video.py): ("clip_x", "clip").

Cada imagen es (captura, movimiento de camara):
  "empuje"          acercamiento lento al centro;
  "foco"            de la pantalla entera al recuadro que el manual recortaba (salida/capturas/focos.json);
  "desde_foco"      al reves: del recuadro a la pantalla entera;
  (x, y, ancho)     de la pantalla entera a ese recuadro (pixeles de la captura 4K; el alto sale de 16:9);
  "clip"            un clip grabado: se reproduce entero, a su ritmo.
"""

NOMBRE_ARCHIVO = "SIETE_tutorial"

# Como se pronuncian (solo en la voz; el subtitulo conserva la escritura). El orden importa: lo largo primero.
PRONUNCIACION = {
    "S.I.E.T.E.": "Siete",
    "A-3 D/A": "a tres de defensa aérea",
    "F-16": "efe dieciséis",
    "Su-30": "Sujói treinta",
    "Buk-M2E": "Buk eme dos e",
    "Pechora-2M": "Pechora dos eme",
    "ZU-23-2": "zeta u veintitrés",
    "RBS 70": "erre be ese setenta",
    "S-300VM": "ese trescientos ve eme",
    "A-1": "a uno",
    "A-2": "a dos",
    "A-3": "a tres",
    "A-4": "a cuatro",
    "C-E": "ce e",
    "JEM": "jefe de Estado Mayor",
    "PMO": "pe eme o",
    "TIEM": "tiem",
    "DIDA": "Dida",
    "AMB": "a eme be",
    "IA": "i a",
    "AAR": "a a erre",
    "OTA": "ota",
    "D/H": "de y hache",
}

# recuadros habituales (pixeles de la captura 4K): paneles y barras de la pantalla
PANEL_IZQ = (0, 110, 1400)
PANEL_IZQ_ABAJO = (0, 760, 1400)
PANEL_DER = (2840, 110, 1000)
PANEL_DER_ABAJO = (2840, 1000, 1000)
BARRA_INFERIOR = (1100, 1820, 1700)
CABECERA = (0, 0, 2400)
MAPA = (900, 220, 2600)
CENTRO = (820, 300, 2200)

ESCENAS = [
    # ------------------------------------------------------------------ apertura
    {"id": "intro", "placa": "intro", "antes": 2.2, "despues": 1.2,
     "texto": "La División de Ingeniería y Desarrollo Aeroespacial de la Aviación Militar Bolivariana presenta el tutorial de "
              "S.I.E.T.E., el Sistema Integral de Entrenamiento Táctico y Estratégico. Veamos, paso a paso, cómo se usa."},

    # ------------------------------------------------------------------ 1. que es
    {"id": "que_es", "capitulo": "¿Qué es S.I.E.T.E.?",
     "imagenes": [("v_instructor", "empuje"), ("pantalla_general", "empuje")],
     "texto": "S.I.E.T.E. es un simulador de conducción de operaciones aéreas, terrestres y navales para el aula. Cada bando es "
              "el Estado Mayor del componente aéreo de un teatro de operaciones y trabaja con la metodología de apreciación y "
              "análisis de problemas militares operativos, e incorpora todas las etapas del Trabajo Integral de Estado Mayor, "
              "TIEM. Funciona en la red local, sin internet."},

    {"id": "como_se_juega", "capitulo": "¿Qué es S.I.E.T.E.?",
     "imagenes": [("alumno_pantalla", "empuje"), ("barra_inferior", BARRA_INFERIOR)],
     "texto": "El ejercicio avanza por turnos de una hora simulada. En cada turno los alumnos aprecian la situación, deciden y "
              "dan sus órdenes. Cuando los dos bandos están listos, el instructor resuelve el turno y el simulador calcula el "
              "resultado."},

    # ------------------------------------------------------------------ 2. puesta en marcha
    {"id": "instalar", "capitulo": "Puesta en marcha",
     "imagenes": [("v_venezuela", "desde_centro")],
     "texto": "Se instala con un doble clic a través de un paquete ejecutable: prepara Python, los datos de mapa y el acceso "
              "directo S.I.E.T.E. del escritorio, que arranca el servidor y abre el navegador. Los alumnos entran desde sus "
              "estaciones."},

    {"id": "acceso", "capitulo": "Puesta en marcha",
     "imagenes": [("acceso_login", "foco"), ("acceso_registro", "foco")],
     "texto": "Cada participante entra con su usuario y su contraseña. Quien no tiene cuenta pulsa Solicitar una cuenta, elige "
              "su usuario, su bando y su repartición, y el instructor la aprueba desde la consola."},

    {"id": "perfil", "capitulo": "Puesta en marcha",
     "imagenes": [("acceso_clave", "foco"), ("menu_perfil", "foco")],
     "texto": "La primera vez, el simulador pide cambiar la contraseña inicial. En el menú del perfil, arriba a la derecha, "
              "cada usuario ve su rol y su repartición, cambia su contraseña y cierra la sesión."},

    # ------------------------------------------------------------------ 3. roles
    {"id": "roles", "capitulo": "Roles y reparticiones",
     "imagenes": [("pantalla_general", "empuje"), ("ver_como", "foco")],
     "texto": "Hay tres roles. El instructor dirige el ejercicio y lo ve todo; puede ver el mapa como lo ve cada bando. Los "
              "alumnos se dividen en el bando azul y el rojo, y solo ven lo que sus sensores detectan. El observador sigue el "
              "ejercicio sin intervenir."},

    {"id": "reparticiones", "capitulo": "Roles y reparticiones",
     "imagenes": [("alumno_secciones", "foco"), ("observador", "empuje")],
     "texto": "Dentro de cada bando, cada alumno ocupa una repartición del Estado Mayor: comandante, jefe de Estado Mayor, A-1 "
              "personal, A-2 inteligencia, A-3 operaciones, A-3 D/A defensa aérea, A-4 logística y C-E comunicaciones. Cada una "
              "emite solo las órdenes que le corresponden."},

    # ------------------------------------------------------------------ 4. la pantalla
    {"id": "cabecera", "capitulo": "La pantalla",
     "imagenes": [("cabecera", CABECERA)],
     "texto": "Conozcamos la pantalla. Arriba, la cabecera: el turno en curso, el escenario activo, el punto verde de conexión, "
              "la cuenta regresiva de la fase de decisión, el videowall y el informe."},

    {"id": "paneles", "capitulo": "La pantalla",
     "imagenes": [("pantalla_general", PANEL_IZQ), ("panel_der_arriba", PANEL_DER), ("capas", PANEL_DER_ABAJO)],
     "texto": "A la izquierda, las pestañas Fuerzas, Situación, TIEM y, para el instructor, Consola. A la derecha, el estado "
              "del escenario, los objetivos con el puntaje, las capas del mapa, las comunicaciones y las alertas. En el centro, "
              "el mapa táctico."},

    {"id": "barra", "capitulo": "La pantalla",
     "imagenes": [("barra_inferior", BARRA_INFERIOR), ("cola_ordenes", "foco")],
     "texto": "Abajo está el botón más importante de cada turno: Estoy listo para los alumnos, o Resolver y avanzar turno para "
              "el instructor. Y en el panel izquierdo, la cola de órdenes muestra lo que el bando ya decidió."},

    # ------------------------------------------------------------------ 5. el terreno
    {"id": "terreno", "capitulo": "El terreno",
     "imagenes": [("clip_terreno", "clip")],
     "texto": "El teatro de operaciones abarca toda América, con foto satelital real y relieve. Sobre Venezuela y los países "
              "vecinos el detalle es mayor: al acercar el mapa se ven calles, pistas y plataformas."},

    {"id": "relieve", "capitulo": "El terreno",
     "imagenes": [("mapa_relieve", "empuje"), ("mapa_carreteras", "empuje"), ("mapa_regla", "foco")],
     "texto": "En las capas se cambia el fondo satelital por el relieve coloreado por tipo de terreno. Al acercar aparecen las "
              "carreteras y los puentes, por donde las unidades terrestres avanzan más rápido. La regla mide distancias y "
              "rumbos."},

    {"id": "aerodromos", "capitulo": "El terreno",
     "imagenes": [("mapa_aerodromo", "empuje"), ("v_carlota", "empuje"), ("mapa_ficticio", "empuje")],
     "texto": "Cada aeródromo aparece con su plano real: pistas, calles de rodaje y plataformas, y sus partes pueden dañarse y "
              "repararse. Para ejercicios sin países reales existe el teatro ficticio, con País Azul y País Rojo."},

    # ------------------------------------------------------------------ 6. preparar el ejercicio
    {"id": "plantillas", "capitulo": "Preparar el ejercicio",
     "imagenes": [("plantillas", "foco"), ("consola_escenario", "foco")],
     "texto": "El instructor prepara el ejercicio. Con Nuevo crea un escenario vacío; con Desde plantilla, uno que ya trae "
              "unidades, objetivos y clima. Y con Guardar como plantilla conserva cualquier situación para reutilizarla."},

    {"id": "agregar", "capitulo": "Preparar el ejercicio",
     "imagenes": [("consola_agregar", "foco"), ("consola_catalogo", "foco")],
     "texto": "En la consola, Agregar unidades coloca cada unidad sobre el mapa: bando, clase, tipo, nombre y escalón. El "
              "catálogo propio permite crear los tipos de unidades aéreas, terrestres y navales que falten, con sus valores y "
              "su foto."},

    {"id": "objetivos", "capitulo": "Preparar el ejercicio",
     "imagenes": [("consola_objetivos", "foco"), ("objetivos_avance", "foco")],
     "texto": "Objetivos y puntaje define qué debe lograr cada bando: ocupar una zona, neutralizar una unidad, proteger una "
              "base o un efecto deseado, con sus puntos. El panel derecho muestra el avance de cada uno."},

    {"id": "clima_calendario", "capitulo": "Preparar el ejercicio",
     "imagenes": [("consola_meteo", "foco"), ("mapa_meteo", "empuje"), ("consola_calendario", "foco")],
     "texto": "En Meteorología se colocan zonas de lluvia o tormenta que se desplazan con los turnos y afectan la detección, la "
              "velocidad y los ataques. El calendario fija el día D, la hora H y las fases del ejercicio."},

    {"id": "usuarios", "capitulo": "Preparar el ejercicio",
     "imagenes": [("consola_usuarios", "foco"), ("consola_turno", "foco")],
     "texto": "En Usuarios el instructor aprueba las solicitudes y asigna a cada alumno su bando y su repartición. En Turno "
              "fija el tiempo límite de la fase de decisión y pausa o reanuda el ejercicio."},

    # ------------------------------------------------------------------ 7. fuerzas
    {"id": "oob", "capitulo": "Fuerzas y fichas",
     "imagenes": [("oob", "foco"), ("ficha_unidad", "foco")],
     "texto": "En la pestaña Fuerzas, el orden de batalla agrupa las unidades por rama con su estado. Un clic en una unidad la "
              "selecciona y centra el mapa. Su ficha muestra la foto de referencia, la fuerza, el combustible, la munición y "
              "sus alcances."},

    {"id": "situacion", "capitulo": "Fuerzas y fichas",
     "imagenes": [("situacion_personal", "foco"), ("situacion_radar", "foco")],
     "texto": "La pestaña Situación resume el personal del bando: tripulaciones, técnicos, reservas y bajas; y el cuadro radar, "
              "con los contactos que ven los sensores propios."},

    # ------------------------------------------------------------------ 8. ordenes
    {"id": "orden_mover", "capitulo": "Dar órdenes",
     "imagenes": [("clip_orden_mover", "clip")],
     "texto": "Dar una orden siempre sigue los mismos pasos. Primero, seleccione la unidad. Segundo, elija el tipo de orden; en "
              "este caso, Mover. Tercero, haga clic en el mapa para cada punto de paso: la vista previa dice hasta dónde llega "
              "en el turno. Y cuarto, pulse Emitir orden: queda pendiente en la cola hasta que se resuelva el turno."},

    {"id": "orden_atacar", "capitulo": "Dar órdenes",
     "imagenes": [("orden_atacar", PANEL_IZQ), ("seleccion_multiple", "empuje"), ("orden_construir", PANEL_IZQ)],
     "texto": "Para atacar, elija el objetivo enemigo detectado en la lista o con un clic sobre él. Con la tecla control se "
              "seleccionan varias unidades a la vez. Los ingenieros construyen vados y puentes. Cada unidad tiene una sola "
              "orden por turno."},

    # ------------------------------------------------------------------ 9. aviacion
    {"id": "enviar_aeronaves", "capitulo": "Operaciones aéreas",
     "imagenes": [("aviacion_enviar", "foco"), ("perfil_vuelo", "foco")],
     "texto": "Desde una base aérea o un portaaviones, Enviar aeronaves lanza un grupo: elija el modelo en las fichas, con su "
              "foto, sus prestaciones y su armamento. El perfil de vuelo, alto, medio o rasante, decide si se esconde tras el "
              "relieve o si gasta más."},

    {"id": "mision", "capitulo": "Operaciones aéreas",
     "imagenes": [("clip_mision", "clip"), ("cronograma", "foco")],
     "texto": "El A-3 planifica misiones completas: el rol, patrulla, interdicción, apoyo aéreo cercano o supresión de "
              "defensas; el grupo o la base de origen; y la ruta con sus puntos. La vista previa calcula el combustible y las "
              "horas, y el cronograma muestra cada fase del vuelo."},

    {"id": "ota", "capitulo": "Operaciones aéreas",
     "imagenes": [("misiones_lista", "foco"), ("cobertura_radar", "empuje")],
     "texto": "Las misiones forman la orden de tareas aéreas: paquetes con comandante de misión, hora sobre el objetivo, "
              "cisternas, alerta temprana y rescate de tripulaciones. La cobertura de los radares muestra hasta dónde ven según "
              "el relieve."},

    # ------------------------------------------------------------------ 10. defensa aerea, mar y guerra electronica
    {"id": "defensa_aerea", "capitulo": "Defensa aérea, mar y guerra electrónica",
     "imagenes": [("ficha_acciones", "foco"), ("mapa_ficha", "empuje")],
     "texto": "Las baterías de defensa aérea, ZU-23-2, Mistral, RBS 70, Pechora-2M, Buk-M2E y S-300VM, disparan solas contra lo "
              "que entra en su alcance, con disciplina de fuego: una salva por aeronave y una reserva para su autodefensa. El "
              "operador puede apagar el radar para emboscar."},

    {"id": "naval", "capitulo": "Defensa aérea, mar y guerra electrónica",
     "imagenes": [("naval_misiles", PANEL_IZQ), ("naval_desembarcar", "empuje"), ("orden_interferir", PANEL_IZQ)],
     "texto": "En el mar, los buques lanzan salvas de misiles contra blancos a su alcance, y las unidades anfibias embarcan, "
              "navegan y desembarcan sobre la costa. La guerra electrónica interfiere las emisiones del enemigo, y los radares "
              "pueden callar para no delatarse."},

    # ------------------------------------------------------------------ 11. resolver el turno
    {"id": "resolver", "capitulo": "Resolver el turno",
     "imagenes": [("clip_resolver_turno", "clip")],
     "texto": "Cuando los dos bandos pulsan Estoy listo, o se agota el tiempo, el instructor pulsa Resolver y avanzar turno. El "
              "simulador resuelve movimientos, detecciones, combates y logística, y las unidades se desplazan por su ruta real. "
              "Cada orden queda en la cola con su resultado."},

    {"id": "dia_noche", "capitulo": "Resolver el turno",
     "imagenes": [("mapa_dia", "empuje"), ("mapa_noche", "empuje"), ("estado_noche", "foco")],
     "texto": "Con el ciclo de día y noche activo, el mapa se oscurece al anochecer: de noche se detecta menos y los cañones "
              "antiaéreos apuntan peor. El panel de estado indica la hora simulada y el periodo del día."},

    {"id": "direccion", "capitulo": "Resolver el turno",
     "imagenes": [("consola_direccion", "foco"), ("consola_eventos", "foco"), ("mapa_infraestructura", "empuje")],
     "texto": "Durante el ejercicio el instructor conduce desde Dirección: avanza varios turnos seguidos, inyecta informes y "
              "eventos, y vigila la infraestructura del país: centrales, refinerías y puentes."},

    # ------------------------------------------------------------------ 12. el TIEM
    {"id": "pmo", "capitulo": "El TIEM",
     "imagenes": [("pmo_mision", "foco"), ("pmo_calendario", "foco"), ("pmo_instructor", "foco")],
     "texto": "Ahora, el método. Todo comienza con el Problema Militar Operativo, el PMO: la situación, la misión y las "
              "instrucciones del comandante del teatro. El instructor lo redacta o lo genera automáticamente, y decide quién "
              "conduce a cada bando: alumnos, él mismo o el adversario automático."},

    {"id": "tiem_docs", "capitulo": "El TIEM",
     "imagenes": [("clip_tiem", "clip"), ("tiem_instructor", "foco")],
     "texto": "En la pestaña TIEM, cada repartición redacta los documentos de la apreciación: el análisis de la misión, el "
              "concepto del comandante, la guía de planeamiento y las formas de acción. Cada documento se presenta al "
              "instructor, que lo aprueba o lo devuelve con observaciones."},

    {"id": "tiem_paso2", "capitulo": "El TIEM",
     "imagenes": [("tiem_paso2", "foco"), ("tiem_matriz", "foco"), ("tiem_ensayos", "foco")],
     "texto": "En el paso dos, cada repartición hace su apreciación. La matriz de confrontación compara las formas de acción "
              "propias con las capacidades del enemigo, y el juego de guerra ensaya cada forma de acción en una copia del "
              "escenario contra la inteligencia artificial."},

    {"id": "tiem_plan", "capitulo": "El TIEM",
     "imagenes": [("tiem_decision", "foco"), ("tiem_plan", "foco"), ("tiem_orden", "foco")],
     "texto": "Con la decisión del comandante se redacta el Plan de Operaciones, con sus tareas por turno. Desde la Orden de "
              "Operaciones, esas tareas se emiten como órdenes reales a las unidades: lo que el Estado Mayor planifica es lo "
              "que se ejecuta."},

    {"id": "tiem_supervision", "capitulo": "El TIEM",
     "imagenes": [("tiem_supervision", "foco"), ("tiem_supervision_doc", "foco"), ("tiem_evaluacion", "foco")],
     "texto": "Durante la ejecución, Supervisión muestra el cuadro de control y el parte de cada turno, con las apreciaciones "
              "rápidas y las órdenes fragmentarias. Al terminar, el simulador evalúa el trabajo de Estado Mayor con una nota "
              "del uno al veinte, y el legajo se descarga en Word o PDF."},

    # ------------------------------------------------------------------ 13. contra la IA
    {"id": "ia", "capitulo": "Contra la IA",
     "imagenes": [("plantillas_ia", "foco"), ("consola_ia", "foco"), ("barra_inferior_ia", BARRA_INFERIOR)],
     "texto": "Para practicar sin un segundo grupo, el simulador conduce un bando. Las plantillas Contra la IA ya lo traen "
              "configurado; en la consola se elige el nivel: prudente, normal o agresiva. El adversario automático juega con "
              "las mismas reglas y la misma niebla de guerra que los alumnos."},

    # ------------------------------------------------------------------ 14. trabajo en equipo
    {"id": "equipo", "capitulo": "Trabajo en equipo",
     "imagenes": [("mapa_graficos", "empuje"), ("videowall", "empuje")],
     "texto": "Los alumnos trazan gráficos tácticos sobre el mapa: líneas de fase, ejes de avance, zonas de reunión y puntos de "
              "control, que todo su bando ve. Las comunicaciones sufren la interferencia enemiga. El videowall proyecta la "
              "situación en la pantalla grande."},

    # ------------------------------------------------------------------ 15. informe posterior
    {"id": "replay", "capitulo": "Informe posterior al ejercicio",
     "imagenes": [("clip_replay", "clip")],
     "texto": "Al finalizar, el informe posterior al ejercicio reproduce todo lo ocurrido sobre el mapa: movimientos, combates, "
              "estelas y el marcador turno a turno. Sirve para la sesión de análisis con los alumnos."},

    {"id": "informe", "capitulo": "Informe posterior al ejercicio",
     "imagenes": [("informe_resumen", "foco"), ("informe_timeline", "foco"), ("informe_repeticion", "foco")],
     "texto": "El informe resume cada bando: fuerza, bajas, objetivos y puntaje. La línea de tiempo muestra los hechos de cada "
              "turno, y la repetición permite volver a cualquier momento del ejercicio."},

    {"id": "evaluacion", "capitulo": "Informe posterior al ejercicio",
     "imagenes": [("informe_rubrica", "foco"), ("informe_doctrina", "foco"), ("comparar", "foco")],
     "texto": "La rúbrica evalúa a cada alumno por su repartición, con indicadores doctrinales y observaciones automáticas, y "
              "permite comparar dos ejercicios. Con esto termina el recorrido por S.I.E.T.E."},

    # ------------------------------------------------------------------ cierre
    {"id": "cierre", "placa": "cierre", "antes": 0.6, "despues": 4.0,
     "texto": "S.I.E.T.E.: desarrollado en la División de Ingeniería y Desarrollo Aeroespacial de la Aviación Militar "
              "Bolivariana. El infinito es el límite."},
]

CREDITOS = [
    "Desarrollado en la División de Ingeniería y Desarrollo Aeroespacial (DIDA)",
    "Aviación Militar Bolivariana",
    "Manual de usuario y tutorial en video: docs/ y tools/video/",
]
