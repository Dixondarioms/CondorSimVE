/* Temas de la ayuda del Cóndor (ayuda.js): cómo funciona el simulador, en lenguaje llano. Cada tema: id, sección,
 * título, palabras clave (lo que alguien escribiría al preguntar) y el texto (HTML propio, sin datos de usuarios).
 * "director: true" = solo lo ve el director del ejercicio. Al cambiar el simulador, actualizar el tema que corresponda. */
(function (raiz) {
  "use strict";

  const SECCIONES = [
    "Primeros pasos", "El reloj y las alertas", "Órdenes", "Aviación", "Defensa aérea y doctrina",
    "Inteligencia y contactos", "Logística, ingenieros y transporte", "Guerra electrónica", "El mapa",
    "Estado Mayor (TIEM)", "Informe y repetición", "Dirección del ejercicio", "Problemas frecuentes",
  ];

  const TEMAS = [
    // ------------------------------------------------------------------ primeros pasos
    {
      id: "que-es", seccion: "Primeros pasos", titulo: "Qué es el Cóndor",
      claves: "simulador tiempo real que es para que sirve bandos azul rojo director ejercicio juego de guerra",
      texto: `<p>El Cóndor es un simulador de entrenamiento táctico y estratégico <b>en tiempo real</b>: las unidades se mueven,
        detectan y combaten mientras corre el reloj, y las órdenes se cumplen en el acto (no hay que esperar al fin de un turno).</p>
        <p>Se enfrentan dos bandos (Azul y Rojo). Cada bando es un Estado Mayor: cada persona entra con la cuenta de su
        <b>repartición</b> (Comandante, JEM, A-1, A-2, A-3, A-3 D/A, A-4, C-E) y ordena solo las unidades que le corresponden.
        El <b>director del ejercicio</b> prepara el escenario, maneja el reloj y ve los dos bandos.</p>`,
    },
    {
      id: "entrar", seccion: "Primeros pasos", titulo: "Entrar y elegir el ejercicio",
      claves: "entrar iniciar sesion login usuario contraseña clave escenario elegir lista cambiar contraseña cerrar sesion salir cuenta",
      texto: `<ol><li>Abra en Chrome o Edge la dirección que le dio el director (termina en <b>:8001</b>).</li>
        <li>Escriba su usuario y contraseña tal como figuran en su tarjeta (respetando mayúsculas y guiones).</li>
        <li>Arriba, en la lista <b>Escenario</b>, elija el ejercicio (una cuenta puede tener más de uno).</li></ol>
        <p>Para cambiar la contraseña o salir: botón del usuario (arriba a la derecha) → <b>Cambiar contraseña</b> o
        <b>Cerrar sesión</b>. Use una cuenta por vez en cada navegador.</p>`,
    },
    {
      id: "pantalla", seccion: "Primeros pasos", titulo: "Las partes de la pantalla",
      claves: "pantalla zoom acercar alejar centrar mira paneles pestañas esconder ocultar plegar fuerzas situacion tiem consola mapa derecha izquierda estado del escenario objetivos capas comunicaciones alertas abajo reloj",
      texto: `<ul><li><b>Izquierda</b>, en pestañas: <b>FUERZAS</b> (orden de batalla, doctrina, aviación, misiones aéreas,
        nueva orden y cola de órdenes), <b>SITUACIÓN</b> (cuadro radar, personal, apresto, infraestructura…), <b>TIEM</b>
        (trabajo de Estado Mayor) y, para el director, <b>CONSOLA</b>.</li>
        <li><b>Centro</b>: el mapa con las unidades, rutas, zonas y contactos.</li>
        <li><b>Derecha</b>: estado del escenario (hora, clima, reloj), objetivos y puntaje, capas del mapa, comunicaciones y alertas.</li>
        <li><b>Abajo</b>: al elegir una unidad, sus datos (foto, misión, estado, capacidades y armamento); y el reloj del
        ejercicio y quién conduce cada bando.</li></ul>
        <p>Las pestañitas <b>◀</b> y <b>▶</b> en los bordes del mapa esconden el panel de la izquierda o las tarjetas de
        la derecha, para ver el mapa más grande; con un clic vuelven a aparecer.</p>
        <p>Junto al borde derecho del mapa están <b>+</b> y <b>−</b> para acercar y alejar, y el botón <b>Centrar</b> (la mira):
        lleva el mapa a la unidad seleccionada o, sin selección, encuadra todas las unidades de su bando. También se acerca
        con la rueda del ratón o las teclas + y −.</p>`,
    },
    {
      id: "reparticiones", seccion: "Primeros pasos", titulo: "Qué ordena cada repartición",
      claves: "reparticion puesto comandante jem a1 a2 a3 a3da a4 ce personal inteligencia operaciones defensa aerea logistica comunicaciones electronica quien ordena permisos funciones corresponde",
      texto: `<table><tr><th>Repartición</th><th>Qué conduce</th></tr>
        <tr><td>Comandante y JEM</td><td>Todo: reúnen las funciones de todas las reparticiones y fijan la doctrina del bando.</td></tr>
        <tr><td>A-1 Personal</td><td>Sigue efectivos, bajas y moral. No ordena unidades.</td></tr>
        <tr><td>A-2 Inteligencia</td><td>Sigue al enemigo y conduce el reconocimiento (unidades y drones de reconocimiento).</td></tr>
        <tr><td>A-3 Operaciones</td><td>La maniobra: despegues, caza, ataque, helicópteros, drones armados, cisternas, fuerzas de superficie y lanzadores de misiles.</td></tr>
        <tr><td>A-3 D/A Defensa Aérea</td><td>Radares, antiaérea, alerta temprana y la caza de intercepción con sus despegues.</td></tr>
        <tr><td>A-4 Logística</td><td>Convoyes, depósitos e ingenieros (puentes y vados).</td></tr>
        <tr><td>C-E Comunicaciones y Electrónica</td><td>Guerra electrónica: escucha e interferencia desde tierra y aviones de guerra electrónica.</td></tr></table>
        <p>Si una orden «corresponde a otra repartición», pídasela a quien la conduce (o al Comandante o al JEM).</p>`,
    },
    {
      id: "catalogo", seccion: "Primeros pasos", titulo: "El catálogo: aeronaves, vehículos y buques",
      claves: "catalogo ficha modelo aeronave avion helicoptero dron tanque blindado artilleria buque fragata submarino portaaviones foto pais fabricante tucano",
      texto: `<p>Cada unidad puede ser un <b>modelo real</b> con su ficha: foto de referencia, fabricante, país, función,
        armamento, velocidad, alcance, detección y efectividad contra aire, tierra y mar. El catálogo trae cerca de 200 modelos
        de muchos ejércitos: cazas (F-16, Su-30, Rafale, Gripen, Kfir…), ataque (A-29 Super Tucano, AT-27 Tucano, K-8W, Su-25…),
        helicópteros, drones, misiles, tanques, artillería, defensa antiaérea, radares y buques.</p>
        <p>La ficha se ve al pasar el cursor sobre una unidad en el mapa y en <b>Unidad seleccionada</b>. Al despegar aeronaves o
        al agregar una unidad, el buscador encuentra el modelo por nombre, país o fabricante. Las cifras son didácticas:
        sirven para comparar plataformas entre sí, no son datos oficiales.</p>`,
    },
    // ------------------------------------------------------------------ reloj y alertas
    {
      id: "reloj", seccion: "El reloj y las alertas", titulo: "El reloj: tiempo real y velocidades",
      claves: "reloj tiempo real velocidad 1x 10x 60x poner en marcha detener pausa hora simulada hora del ejercicio adelantar +1 h acelerar",
      texto: `<p>El ejercicio corre en tiempo simulado. La velocidad puede ser <b>1×</b> (igual que la realidad), <b>10×</b> o
        <b>60×</b> (un minuto simulado por segundo). El reloj lo pone en marcha y lo detiene el director (en el ensayo de una
        forma de acción, el Comandante y el JEM); el botón <b>+1 h</b> adelanta una hora de golpe.</p>
        <p>Arriba se ve la <b>hora simulada</b> y la <b>hora del ejercicio</b> (la primera hora es la 1). Con el reloj detenido
        se pueden dar órdenes: se cumplen al ponerlo en marcha.</p>`,
    },
    {
      id: "pausa-auto", seccion: "El reloj y las alertas", titulo: "Pausa automática y alertas",
      claves: "pausa automatica alerta aviso se detuvo solo contacto nuevo ataque unidad perdida combustible critico mision terminada reanudar ver en el mapa banner",
      texto: `<p>Las <b>alertas</b> avisan al instante lo importante para su bando: contacto nuevo, ataque a una unidad propia,
        unidad perdida, combustible crítico, misión terminada, fase de una interceptación, intrusión en una zona y daño
        colateral. Aparecen como aviso sobre el mapa y quedan en el panel
        <b>Alertas</b> (derecha); con un clic en el lugar, el mapa va hasta allí.</p>
        <p>El director elige en CONSOLA → <b>Reloj y configuración</b> qué causas <b>detienen el reloj solas</b>. Cuando eso pasa,
        arriba aparece la franja roja <b>PAUSA AUTOMÁTICA</b> con el motivo, <b>Ver en el mapa</b> y (para el director)
        <b>Reanudar</b>.</p>`,
    },
    {
      id: "eventos-auto", seccion: "Dirección del ejercicio", titulo: "Eventos automáticos (disparadores y acciones)",
      claves: "eventos automaticos disparador disparadores accion acciones regla reglas cuando entonces guion inyeccion automatica aparecer refuerzos mensaje programado hora",
      director: true,
      texto: `<p>En CONSOLA → <b>Eventos automáticos</b> el director arma reglas que el simulador cumple solo:</p>
        <ul><li><b>Cuando</b>: una unidad entra a un área (una zona dibujada en «Áreas y zonas»; de un bando o una unidad
        concreta), llega una hora del ejercicio, se destruye una unidad, o se cumple o falla un objetivo.</li>
        <li><b>Entonces</b> (una o varias): enviar un mensaje a un bando o a todos, hacer aparecer unidades (elija bando,
        clase, cantidad y el punto en el mapa), cambiar el clima, dar o quitar puntos, o pausar el reloj.</li></ul>
        <p>Cada regla se dispara una vez, salvo que marque <b>Repetir</b>. En la lista se activan, se desactivan y se borran, y
        se ve cuántas veces se dispararon. Se guardan con el escenario y con las plantillas (las unidades y los objetivos se
        nombran por su nombre).</p>`,
    },
    {
      id: "trafico", seccion: "Dirección del ejercicio", titulo: "Tráfico civil, neutrales y daño colateral",
      claves: "trafico civil neutral neutrales avion comercial aerolinea aerovia mercante buque pesquero colateral daño colateral penalizacion pais ajeno",
      texto: `<p>El director genera tráfico civil en CONSOLA → <b>Tráfico civil y neutral</b>: cuántos aviones comerciales,
        buques mercantes y pesqueros, en la zona que se ve en el mapa. Los aviones vuelan por <b>aerovías</b> (líneas verdes
        punteadas), los mercantes cruzan por el mar y los pesqueros van de un caladero a otro. El que sale de la zona se
        retira y entra otro.</p>
        <p>Para cada bando son <b>contactos desconocidos</b> hasta que los clasifica (o los identifica a la vista). Con las
        armas <i>libres</i> se les puede tirar por error mientras sean desconocidos; con las armas <i>restringidas</i>, nunca.
        Tirarle a una unidad neutral es <b>daño colateral</b>: alerta al bando, penaliza su puntaje (10 puntos por unidad y uno
        más cada 5 de fuerza) y figura en el informe.</p>
        <p>Para las fuerzas de un país que no participa, el director agrega unidades con el bando <b>Neutral</b>.</p>`,
    },
    // ------------------------------------------------------------------ órdenes
    {
      id: "dar-orden", seccion: "Órdenes", titulo: "Cómo dar una orden",
      claves: "dar orden ordenar seleccionar unidad nueva orden enviar waypoints puntos clic mapa cola detener cancelar reemplazar varias unidades ctrl formacion",
      texto: `<ol><li>Elija la unidad en el <b>orden de batalla</b> (izquierda) o con un clic en el mapa.</li>
        <li>En <b>Nueva orden</b>, elija el tipo (Mover, Atacar, Apoyar…). Solo aparecen los que esa unidad puede cumplir.</li>
        <li>Complete lo que pide: puntos de la ruta (clic en el mapa), el blanco o el lugar.</li>
        <li>Envíela. La unidad empieza en el acto.</li></ol>
        <p>Una orden nueva <b>reemplaza</b> a la que estaba cumpliendo (una aeronave en vuelo se desvía al momento). En la
        <b>Cola de órdenes</b>, el botón ■ detiene una orden. Con <b>Ctrl+clic</b> se suman varias unidades propias: la orden va a
        todas y, con formación, cada una conserva su lugar.</p>`,
    },
    {
      id: "tipos-orden", seccion: "Órdenes", titulo: "Los tipos de orden",
      claves: "tipos de orden mover atacar apoyar construir patrullar aterrizar rumbo interceptar interferir lanzar misiles embarcar desembarcar que hace cada orden",
      texto: `<table><tr><th>Orden</th><th>Qué hace</th></tr>
        <tr><td>Mover</td><td>Va por los puntos marcados (por carretera cuando conviene).</td></tr>
        <tr><td>Atacar</td><td>Ataca a un enemigo detectado; si hace falta, se acerca hasta tenerlo a su alcance.</td></tr>
        <tr><td>Apoyar</td><td>Acompaña y apoya con fuego a otra unidad propia.</td></tr>
        <tr><td>Construir</td><td>Ingenieros: puente o vado sobre un río.</td></tr>
        <tr><td>Patrullar</td><td>Aeronaves: orbitan sobre una zona e interceptan lo que entre.</td></tr>
        <tr><td>Aterrizar</td><td>Aeronaves en vuelo: vuelven a una base.</td></tr>
        <tr><td>Rumbo</td><td>Aeronaves en vuelo: viran unos grados a un lado o toman un rumbo y lo mantienen.</td></tr>
        <tr><td>Torpedo, Sonoboyas, Sonar de inmersión</td><td>Guerra antisubmarina (ver «Guerra antisubmarina»).</td></tr>
        <tr><td>Interceptar</td><td>Aeronaves (también en tierra, en alerta) y buques: salen al encuentro de una aeronave o un buque enemigo para seguirlo o neutralizarlo.</td></tr>
        <tr><td>Interferir</td><td>Guerra electrónica: degrada al enemigo en una zona.</td></tr>
        <tr><td>Lanzar misiles</td><td>Buques y baterías con misiles de crucero.</td></tr>
        <tr><td>Embarcar / Desembarcar</td><td>Tropas a bordo de un buque de desembarco o un helicóptero de transporte.</td></tr></table>`,
    },
    {
      id: "mover", seccion: "Órdenes", titulo: "Mover: terreno, ríos y combustible",
      claves: "mover marcha desplazar ruta camino carretera terreno rio cruzar puente velocidad lento no avanza varada combustible se detuvo llegar",
      texto: `<p>La velocidad depende del tipo de unidad, del <b>terreno</b> y del <b>clima</b>. Las unidades de tierra aprovechan las
        carreteras. Los <b>vehículos pesados solo cruzan los ríos por un puente o un vado</b> (obra de ingenieros); si no hay paso,
        la unidad busca otro camino y, si no lo encuentra, se detiene y avisa.</p>
        <p>Moverse gasta combustible: sin combustible la unidad no avanza hasta que la reabastezcan (ver «Logística»).</p>`,
    },
    {
      id: "atacar", seccion: "Órdenes", titulo: "Atacar y el combate",
      claves: "atacar ataque combate disparar fuego blanco objetivo enemigo daño fuerza municion alcance no aparece el blanco fuego continuo bajas",
      texto: `<p>Solo se puede atacar a un enemigo <b>detectado</b> por su bando. La unidad se acerca hasta tenerlo a su alcance y
        combate mientras dure la orden: el daño se reparte poco a poco y depende de las armas, la defensa, el terreno, el clima
        y el azar. Cada ataque gasta munición; una unidad con poca fuerza queda casi sin capacidad de combate.</p>
        <p>Además, según la <b>doctrina</b>, las unidades pueden tirar solas contra lo que tengan a su alcance (ver «Doctrina y
        reglas de enfrentamiento»).</p>`,
    },
    // ------------------------------------------------------------------ aviación
    {
      id: "despegar", seccion: "Aviación", titulo: "Despegar aviones y drones",
      claves: "despegar despegue avion aeronave caza dron drones enviar aeronaves base aerea tope cuantos aviones grupo",
      texto: `<p>En la pestaña FUERZAS, panel <b>Aviación</b> → <b>Enviar aeronaves o drones…</b>: elija el tipo (caza, ataque,
        dron, avión de guerra electrónica…), cuántas y la base de la que despegan. Los despegues los ordenan A-3 y A-3 D/A
        (y el Comandante o el JEM).</p>
        <p>Cada bando tiene un <b>tope</b> de aeronaves y de drones (lo muestra el panel). Una aeronave en tierra que acaba de
        aterrizar necesita tiempo para reabastecer y rearmar antes de volver a salir.</p>`,
    },
    {
      id: "cargas", seccion: "Aviación", titulo: "Cargas de armamento y existencias de armas",
      claves: "carga cargas armamento misiles bombas aire-aire ataque antibuque sead reconocimiento existencias pañol rearmar municion armas pk probabilidad alcance arma",
      texto: `<p>Al despegar se elige la <b>carga de armamento</b> según el modelo: <i>aire-aire</i>, <i>ataque</i>,
        <i>antibuque</i>, <i>SEAD</i> (misiles antirradiación) o <i>reconocimiento</i>. Cada carga lleva una cantidad real de
        misiles y bombas por aeronave. También se elige en el planificador de misiones y, para una aeronave en tierra, en la
        Nueva orden («Carga de armamento al despegar»).</p>
        <ul><li>Cada pasada gasta armas reales: un misil por aeronave, o la mitad de las bombas o los cohetes. La munición en %
        se calcula con lo que queda.</li>
        <li>Se tira con el arma que sirve contra ese blanco y desde su alcance: los misiles aire-aire contra aviones, los
        antibuque contra buques, los antirradiación contra radares que emiten. Las bombas se sueltan casi encima del blanco.</li>
        <li>El daño de cada pasada sale de la misma tabla de combate de siempre; el arma guiada o antirradiación suma.</li></ul>
        <p>En el panel de abajo se ven la carga (con alcance y probabilidad de impacto de cada arma) y, en las bases y los
        portaaviones, las <b>existencias de armas</b>: despegar y rearmar las toma de ahí. Son abundantes; el director las
        puede cambiar y guardar.</p>`,
    },
    {
      id: "patrulla", seccion: "Aviación", titulo: "Patrullar, aterrizar y el combustible",
      claves: "patrulla patrullar cap orbitar interceptar aterrizar regreso base combustible bingo winchester reabastecer rearmar 2 horas plazas",
      texto: `<p><b>Patrullar</b>: la aeronave vuela a la zona, orbita (gasta cerca de 8 % de combustible por hora) e intercepta a
        los aviones enemigos que detecte a su alcance.</p>
        <p><b>Aterrizar</b>: vuelve a la base elegida. En tierra tarda unas <b>2 horas</b> en reabastecer y rearmar; después,
        cualquier orden de vuelo es el despegue. Cada base tiene un número de plazas.</p>
        <p>Con poco combustible (por defecto 25 %) o sin armamento, la aeronave <b>regresa sola</b> a la base más cercana; esos
        valores se cambian en la doctrina.</p>`,
    },
    {
      id: "desviar", seccion: "Aviación", titulo: "Desviar una aeronave: waypoints o rumbo",
      claves: "desviar desvio redirigir cambiar rumbo virar viraje derecha izquierda grados rumbo control de transito aereo vectorear vector",
      texto: `<p>Una orden nueva reemplaza en el acto a la que cumplía la aeronave, así que hay dos formas de desviarla:</p>
        <ul><li><b>Mover</b> con waypoints: clic en el mapa en cada punto de la nueva ruta; la aeronave gira enseguida hacia el primero.</li>
        <li><b>Rumbo</b>, como el control de tránsito aéreo: <i>Virar … grados</i> a la derecha o a la izquierda («vire a la
        derecha 25 grados»), o <i>Tomar el rumbo …</i> (de 0 a 360) por el lado que diga o por el más corto («tome rumbo 270»).
        El mapa muestra en amarillo la recta que seguirá. La aeronave vira 3° por segundo y mantiene el rumbo hasta otra
        orden; con combustible crítico regresa sola.</li></ul>`,
    },
    {
      id: "interceptar", seccion: "Aviación", titulo: "Interceptar una aeronave o un buque",
      claves: "interceptar interceptacion interceptor alerta en tierra scramble punteria adelantada punto de encuentro identificar seguir neutralizar sombra vectoreo contacto identificacion seguimiento estima busqueda buque",
      texto: `<p>Elija la aeronave (en vuelo o lista en tierra) o el buque, pulse <b>Interceptar</b>, elija el <b>blanco</b> (una
        aeronave en vuelo o un buque enemigo detectado; también con un clic en el mapa) y <b>qué hacer</b>:</p>
        <ul><li><b>Identificar y seguir</b>: lo identifica a la vista y lo sigue a unos kilómetros, sin tirar; el bando lo ve mientras tanto.</li>
        <li><b>Identificar y neutralizar</b>: lo identifica y lo ataca.</li>
        <li><b>Neutralizar sin esperar la identificación</b>: lo ataca apenas lo tiene a su alcance. Si la doctrina tiene las armas
        <i>restringidas</i>, igual lo identifica antes de tirar.</li></ul>
        <p>Antes de emitir, el panel dice si lo alcanza, en cuánto tiempo y a qué hora, con cuánto combustible llega y cuánto le
        quedaría para volver a la base; el mapa dibuja en amarillo el curso al <b>punto de encuentro</b>: el interceptor no va
        hacia donde está el blanco sino hacia donde estará (puntería adelantada).</p>
        <p>Cada fase llega como alerta: vectoreo, contacto (sus sensores lo detectan), identificación, seguimiento o ataque. Si
        se pierde el contacto, sigue la estima del rumbo y la velocidad del blanco, después busca sobre el último punto y, si no
        lo encuentra, aborta. Una aeronave en tierra <b>despega en 5 minutos</b> (alerta en tierra). Un buque solo intercepta
        buques. En el planificador de misiones está también el rol <b>Interceptación</b>.</p>`,
    },
    {
      id: "misiones", seccion: "Aviación", titulo: "Misiones aéreas planificadas",
      claves: "mision misiones aereas planificar paquete ota cronograma flow sheet escolta ataque hora sobre el blanco tot",
      texto: `<p>El panel <b>Misiones aéreas</b> arma misiones completas: qué aeronaves, la ruta, el blanco, la escolta y la hora.
        Al llegar la hora, las aeronaves despegan y cumplen la misión solas; al terminar llega la alerta «misión terminada».
        El <b>cronograma</b> (flow sheet) muestra todas las misiones en el tiempo.</p>`,
    },
    // ------------------------------------------------------------------ defensa aérea y doctrina
    {
      id: "doctrina", seccion: "Defensa aérea y doctrina", titulo: "Doctrina y reglas de enfrentamiento",
      claves: "doctrina reglas de enfrentamiento roe libre restringido retenido solo identificados solo con orden misiles por blanco distancia abre fuego disparar solas combustible de regreso sin armamento",
      texto: `<p>En FUERZAS → <b>Doctrina y reglas de enfrentamiento</b> se decide cómo actúan las unidades por su cuenta:</p>
        <ul><li><b>Contra aeronaves</b> y <b>contra superficie</b>: <i>Libre</i> (tiran contra cualquier enemigo detectado),
        <i>Solo identificados</i> o <i>Solo con orden</i>.</li>
        <li><b>Misiles por blanco</b> de la defensa aérea y <b>a qué distancia abren fuego</b> (100, 75 o 50 % del alcance:
        más cerca, más probable el impacto).</li>
        <li>Aeronaves: con qué <b>combustible regresan</b> y si vuelven al quedarse <b>sin armamento</b>.</li></ul>
        <p>La del bando la fijan el Comandante y el JEM (y el director). Cada unidad puede tener la suya: lo que deje en «Del
        bando» lo toma de la doctrina del bando. Por defecto: contra aeronaves libre, contra superficie solo con orden.</p>`,
    },
    {
      id: "asw", seccion: "Defensa aérea y doctrina", titulo: "Guerra antisubmarina: sonar, sonoboyas y torpedos",
      claves: "antisubmarina submarino sonar sonoboya sonoboyas torpedo profundidad periscopica periscopio inmersion helicoptero p-3 p-8 orion poseidon nh90",
      texto: `<p>Un submarino sumergido no se ve con radar ni a ojo: se lo detecta con <b>sonar</b>.</p>
        <ul><li><b>Profundidad</b> (panel de abajo del submarino): a <i>cota periscópica</i> un radar o un vigía lo ven a menos
        de 8 km y puede lanzar misiles; a <i>profundidad</i> solo lo oye el sonar, al 60 % de su alcance.</li>
        <li><b>Sonar de casco</b>: fragatas (25 km), destructores (30 km) y submarinos (35 km).</li>
        <li><b>Sonoboyas</b>: un P-3 o P-8 con la orden <b>Sonoboyas</b> vuela al punto y deja 4 boyas que escuchan a 10 km
        durante 4 horas (se ven en el mapa en celeste).</li>
        <li><b>Sonar de inmersión</b>: un helicóptero antisubmarino (NH90) con la orden <b>Sonar de inmersión</b> va al punto,
        queda en vuelo estacionario y escucha a 12 km mientras mantenga la orden.</li>
        <li><b>Torpedos</b>: orden <b>Torpedo</b> de submarinos (30 km), fragatas y destructores (10 km) y aeronaves
        antisubmarinas (8 km; carga «antisubmarina») contra un buque o submarino detectado. El torpedo navega a unos 40 nudos
        y golpea al llegar.</li></ul>
        <p>Al atacar (fuego, misiles o torpedos) el submarino se <b>delata</b> unos 10 minutos: se lo ve como a un buque.</p>`,
    },
    {
      id: "sistemas", seccion: "Defensa aérea y doctrina", titulo: "Daño por sistemas y control de averías",
      claves: "sistemas daño averia averias control de averias sensores radar sonar armas propulsion movilidad comunicaciones fuera de servicio reparar puerto",
      texto: `<p>Los buques y las unidades de tierra tienen cuatro sistemas que se dañan por separado; se ven en el panel de
        abajo, en <b>Sistemas</b>:</p>
        <ul><li><b>Sensores</b> (radar y sonar): con daño detecta menos; sin ellos, solo a ojo.</li>
        <li><b>Armas</b>: su fuego (y la defensa aérea) pierde efecto en proporción.</li>
        <li><b>Propulsión</b> (o movilidad): va más lento; fuera de servicio, queda inmóvil.</li>
        <li><b>Comunicaciones</b>: sus órdenes tardan más en llegar.</li></ul>
        <p>Cada punto de fuerza que pierde puede causar un impacto crítico en un sistema (perder unos 25 puntos daña uno en
        promedio). Un sistema al 75 % de daño queda <b>fuera de servicio</b> y llega una alerta. El <b>control de averías</b>
        repara unos 10 puntos por hora; las averías graves (más del 40 %) solo se terminan de reparar junto a un puerto,
        depósito o base propia.</p>`,
    },
    {
      id: "zonas", seccion: "Defensa aérea y doctrina", titulo: "Áreas de patrulla y zonas de exclusión o de no vuelo",
      claves: "zona zonas area areas de patrulla exclusion no vuelo poligono dibujar intrusion intruso armas libres sector referencia",
      texto: `<p>En la tarjeta <b>Áreas y zonas</b> (panel derecho) elija el tipo, escriba un nombre y pulse <b>Dibujar en el
        mapa</b>: clic en cada vértice y, para terminar, clic en el primero. El director las dibuja para todos o para un
        bando; cada bando, las suyas (el otro bando no las ve).</p>
        <ul><li><b>Área de patrulla</b>: elija una unidad (aeronave, buque o tropa), orden <b>Patrullar</b> y, en «Dónde», el
        área. La unidad la recorre de vértice en vértice y ataca a los enemigos que entran en ella si su doctrina lo permite.</li>
        <li><b>Zona de exclusión</b>: nadie ajeno debe entrar (aeronaves, buques ni tropas). <b>Zona de no vuelo</b>: ninguna
        aeronave ajena debe volar sobre ella.</li></ul>
        <p>Quien cruza una zona de exclusión o de no vuelo dispara una alerta (al dueño de la zona si lo ve; en las de la
        dirección, al bando del intruso), y la pausa automática si el director la eligió. Con <b>«Las armas propias tiran
        contra quien entre»</b>, la antiaérea, las patrullas y las unidades al alcance le tiran aunque la doctrina tenga las
        armas restringidas o retenidas.</p>`,
    },
    {
      id: "defensa-aerea", seccion: "Defensa aérea y doctrina", titulo: "Radares y defensa antiaérea",
      claves: "defensa aerea antiaerea misiles radar alerta temprana derribar interceptar salva alcance techo relieve fuego libre sistema",
      texto: `<p>Los <b>radares</b> y la antiaérea guiada detectan aeronaves según su alcance, el relieve (las montañas tapan) y la
        altura a la que vuelan. La antiaérea dispara sola contra las aeronaves enemigas que tenga a su alcance, según la doctrina
        (misiles por salva y distancia de apertura de fuego). Los conduce A-3 D/A.</p>
        <p>En SITUACIÓN → <b>Cuadro radar</b> se ve qué detecta ahora cada sensor del bando.</p>`,
    },
    // ------------------------------------------------------------------ inteligencia
    {
      id: "contactos", seccion: "Inteligencia y contactos", titulo: "Contactos: desconocido, clasificado e identificado",
      claves: "contacto contactos enemigo desconocido clasificado identificado circulo amarillo incertidumbre posicion dudosa donde esta niebla de guerra",
      texto: `<p>Un enemigo recién detectado aparece como <b>desconocido</b> (solo se sabe si está en el aire o en superficie). Mientras
        se lo sigue, pasa a <b>clasificado</b> (se sabe qué clase de unidad es) y luego a <b>identificado</b> (se sabe cuál es). Es
        más rápido de cerca y con radar; solo por escucha electrónica es lento y no pasa de clasificado. A menos de 8 km se
        identifica a ojo; las bases se conocen de antemano.</p>
        <p>El <b>círculo amarillo</b> muestra dónde puede estar en realidad. Si se pierde el contacto, queda su último lugar
        conocido y el círculo crece con lo que pudo moverse. Las armas en <i>Solo identificados</i> no tiran contra desconocidos.</p>`,
    },
    {
      id: "pmi", seccion: "Inteligencia y contactos", titulo: "Puntos medios de impacto (PMI) sobre las pistas",
      claves: "pmi punto medio de impacto dmpi pdi pista atacar base aerea inteligencia operaciones a2 a3 cortes pedir entregar blanco",
      texto: `<p>Para dejar fuera de servicio una pista hay que cortarla en tramos más cortos de lo que necesita un caza para
        despegar. Esos cortes son los <b>puntos medios de impacto (PMI)</b>, y los prepara Inteligencia.</p>
        <ol><li><b>A-3</b> (o el Comandante o el JEM), en FUERZAS → <b>Puntos medios de impacto</b>: elige la base aérea enemiga
        y pulsa <b>Pedir a Inteligencia</b>.</li>
        <li><b>A-2</b> ve el pedido y pulsa <b>Preparar los PMI…</b>: el sistema propone los cortes sobre el eje de la pista real
        (con sus coordenadas). Puede arrastrar cada punto en el mapa para correrlo.</li>
        <li><b>Entregar a Operaciones</b>: desde ese momento el ataque a la pista de esa base hace <b>todo su daño</b>.</li></ol>
        <p>Sin los PMI, las bombas caen dispersas y el ataque a la pista hace <b>la mitad</b> del daño. La orden Atacar avisa si
        los tiene o no. Los PMI entregados se ven en el mapa al acercarse a la base.</p>`,
    },
    {
      id: "no-veo", seccion: "Inteligencia y contactos", titulo: "Por qué no veo al enemigo",
      claves: "no veo enemigo no aparece invisible deteccion detectar reconocimiento niebla de guerra radar alcance ocultamiento clima noche",
      texto: `<p>Cada bando ve solo lo que detectan sus unidades (<b>niebla de guerra</b>). La detección depende del alcance de cada
        sensor, del terreno (bosques y ciudades ocultan), del relieve, del clima y de la noche. Para ver más: acerque unidades de
        reconocimiento o drones (A-2), use radares y patrullas, o la escucha electrónica (C-E).</p>`,
    },
    // ------------------------------------------------------------------ logística
    {
      id: "logistica", seccion: "Logística, ingenieros y transporte", titulo: "Combustible, munición y abastecimiento",
      claves: "logistica combustible municion abastecer reabastecer deposito convoy cisterna base sin combustible stock suministro",
      texto: `<p>Las unidades gastan combustible al moverse y munición al combatir. Se reabastecen solas, poco a poco, cerca de
        las <b>bases</b>, los <b>depósitos</b> y los <b>convoyes</b> propios (que llevan su carga a donde se los mande). Las
        aeronaves pueden reabastecer en vuelo junto a un <b>avión cisterna</b>. Conduce A-4.</p>`,
    },
    {
      id: "ingenieros", seccion: "Logística, ingenieros y transporte", titulo: "Ingenieros: puentes y vados",
      claves: "ingenieros construir puente vado obra rio cruzar",
      texto: `<p>Elija la unidad de ingenieros → orden <b>Construir</b> → clic sobre un río a menos de 5 km. La obra tarda un
        tiempo; cuando está lista, los vehículos pesados pueden cruzar por allí.</p>`,
    },
    {
      id: "embarcar", seccion: "Logística, ingenieros y transporte", titulo: "Embarcar y desembarcar tropas",
      claves: "embarcar desembarcar transporte buque helicoptero tropas asalto aereo anfibio a bordo",
      texto: `<p><b>Embarcar</b>: la unidad sube a un buque de desembarco o a un helicóptero de transporte propio que esté a menos
        de 3 km. A bordo viaja con el transporte, no se la ve ni ataca por separado y sufre la mitad del daño que reciba el
        transporte (se pierde si lo hunden o derriban).</p>
        <p><b>Desembarcar</b>: elija el transporte y marque la ruta; el último punto es el lugar de desembarco, en tierra firme.</p>`,
    },
    {
      id: "misiles-crucero", seccion: "Logística, ingenieros y transporte", titulo: "Misiles de crucero",
      claves: "misil misiles crucero lanzar salva lanzador bateria buque",
      texto: `<p>Buques y baterías con misiles de crucero: orden <b>Lanzar misiles</b> sobre un blanco. La salva vuela sola
        (unos 850 km/h) hacia donde estaba el blanco; la antiaérea y las patrullas enemigas pueden derribarla antes. Cada misil
        gasta el 25 % de la munición del lanzador.</p>`,
    },
    // ------------------------------------------------------------------ guerra electrónica
    {
      id: "ge", seccion: "Guerra electrónica", titulo: "Interferencia y escucha",
      claves: "guerra electronica interferir interferencia escucha esm jammer radar apagado enlace drones emisor localizado",
      texto: `<p><b>Interferir</b>: con la unidad o el avión de guerra electrónica, clic en el centro de la zona (dentro de su
        alcance). Mientras dure la orden, allí el enemigo detecta mucho menos, su antiaérea guiada por radar pierde efecto y sus
        drones pierden el enlace. Pero al emitir, <b>el enemigo localiza al interferidor</b>.</p>
        <p>La <b>escucha</b> electrónica localiza de lejos a los radares enemigos encendidos. Un radar apagado no se oye, pero
        tampoco ve. Conduce C-E.</p>`,
    },
    // ------------------------------------------------------------------ mapa
    {
      id: "capas", seccion: "El mapa", titulo: "Capas, estelas y símbolos",
      claves: "capas mapa estela estelas rastro donde estuvo simbolos app-6 miniaturas cobertura niebla alcances relieve satelite zoom",
      texto: `<p>En la tarjeta <b>Capas</b> (derecha) se enciende o apaga lo que muestra el mapa: terreno, cobertura de detección,
        niebla de guerra, unidades, alcances (al acercarse), últimos contactos, gráficos tácticos, objetivos, infraestructura,
        guerra electrónica, meteorología y misiones.</p>
        <ul><li><b>Estelas de movimiento</b>: la línea por donde pasó cada unidad, más tenue cuanto más vieja. Puede elegir su
        largo (de 10 minutos a 3 horas simuladas).</li>
        <li><b>Símbolos militares (APP-6)</b> en lugar de las miniaturas.</li></ul>`,
    },
    {
      id: "clima", seccion: "El mapa", titulo: "Clima, lluvia, tormentas y noche",
      claves: "clima meteorologia lluvia tormenta nublado zona deriva se mueve satelite meteorologico radio noche dia crepusculo visibilidad",
      texto: `<p>Además del clima general, el director puede poner <b>zonas</b> de nubosidad, lluvia o tormenta, que se desplazan
        de forma continua. Dentro de ellas se detecta menos, se avanza más lento y el ataque aéreo pierde efecto. De noche
        también se detecta menos.</p>
        <p>En Capas → <b>Vista del clima</b>: <i>Solo el radio</i> (el círculo con su rótulo y la flecha de hacia dónde va) o
        <i>Satélite meteorológico</i> (las nubes como en una imagen de satélite).</p>`,
    },
    {
      id: "graficos", seccion: "El mapa", titulo: "Gráficos tácticos y herramientas",
      claves: "graficos tacticos linea de fase eje de avance zona de reunion punto de control dibujar regla medir distancia convertir coordenadas",
      texto: `<p>En el panel <b>Gráficos tácticos</b> (sobre el mapa) se dibujan líneas de fase, ejes de avance, zonas de reunión y
        puntos de control, visibles para todos o solo para su bando. Con <b>▲ Esconder</b> el cuadro queda reducido a su
        título (<b>▼ Mostrar</b> lo vuelve a abrir). La <b>Regla</b> mide distancias y <b>Convertir</b> pasa
        coordenadas de un formato a otro.</p>`,
    },
    {
      id: "videowall", seccion: "El mapa", titulo: "Videowall (pantalla completa)",
      claves: "videowall pantalla completa proyector centro de operaciones tecla v",
      texto: `<p>El botón <b>Videowall</b> (o la tecla <b>V</b>) muestra el mapa a pantalla completa, sin paneles, para un proyector o
        un centro de operaciones. Con <b>Esc</b> se vuelve.</p>`,
    },
    // ------------------------------------------------------------------ TIEM
    {
      id: "tiem", seccion: "Estado Mayor (TIEM)", titulo: "Trabajo de Estado Mayor (pestaña TIEM)",
      claves: "tiem estado mayor problema militar operativo pmo apreciacion orden de operaciones supervision evaluacion legajo forma de accion ensayo juego de guerra calendario fases",
      texto: `<p>La pestaña <b>TIEM</b> guía el trabajo del Estado Mayor: el <b>Problema Militar Operativo</b> de su bando, las
        apreciaciones de cada repartición, las formas de acción y su <b>ensayo</b> (juego de guerra), la <b>Orden de
        Operaciones</b>, la <b>supervisión</b> de la ejecución y la <b>evaluación</b>. El calendario muestra el día D, la hora H
        y las fases de la operación.</p>`,
    },
    {
      id: "comunicaciones", seccion: "Estado Mayor (TIEM)", titulo: "Comunicaciones del bando",
      claves: "comunicaciones chat mensajes hablar escribir bando compañeros",
      texto: `<p>En la tarjeta <b>Comunicaciones</b> (derecha) se escriben mensajes al resto del bando. Las comunicaciones pueden
        tener demoras o pérdidas si el director las simula.</p>`,
    },
    // ------------------------------------------------------------------ informe
    {
      id: "informe", seccion: "Informe y repetición", titulo: "Informe, repetición y rúbrica",
      claves: "informe resumen aar repeticion replay linea de tiempo rubrica evaluacion comparar ejercicios resultado final",
      texto: `<p>El botón <b>Informe</b> abre el resumen del ejercicio de cada bando, la <b>línea de tiempo</b> (logística y
        combates), la <b>repetición</b> del ejercicio sobre el mapa, la <b>rúbrica</b> de evaluación por repartición y la
        comparación entre ejercicios.</p>`,
    },
    // ------------------------------------------------------------------ dirección (solo director)
    {
      id: "preparar", seccion: "Dirección del ejercicio", titulo: "Preparar un ejercicio", director: true,
      claves: "preparar crear escenario nuevo plantilla desde plantilla guardar como plantilla agregar unidad objetivos puntaje editar escenario",
      texto: `<ul><li><b>Nuevo</b> o <b>Desde plantilla…</b> (arriba) crea el escenario; <b>Guardar como plantilla…</b> guarda el
        actual para reutilizarlo.</li>
        <li>En CONSOLA: <b>Agregar unidad</b>, <b>Objetivos y puntaje</b>, <b>Editar el escenario</b>, meteorología por zonas,
        calendario de la operación, identidad nacional, apresto y personal de cada bando.</li>
        <li>CONSOLA → <b>Escenario</b> → <b>Usuarios con acceso</b>: marque las cuentas que entran a este ejercicio.</li></ul>`,
    },
    {
      id: "conducir", seccion: "Dirección del ejercicio", titulo: "Conducir el ejercicio", director: true,
      claves: "conducir director reloj inyectar eventos informes ajuste manual ver como conducir bando adversario automatico ia demostracion interruptores fuego automatico niebla",
      texto: `<ul><li>Abajo: <b>PONER EN MARCHA / DETENER EL RELOJ</b>, la velocidad y <b>+1 h</b>.</li>
        <li>CONSOLA → <b>Eventos e informes inyectados</b>: mensajes para un bando (con lugar en el mapa si quiere) y el ajuste
        manual de una unidad (queda en el informe).</li>
        <li>CONSOLA → <b>Dirección del ejercicio</b>: interruptores del motor (niebla de guerra, fuego automático, clima, azar…) y
        el <b>adversario automático</b> para el bando que no tenga alumnos.</li>
        <li><b>Conducir Azul / Rojo</b> (arriba) para dar órdenes como el comandante de un bando sin alumnos.</li>
        <li>CONSOLA → <b>Reloj y configuración</b>: qué causas detienen el reloj solas (pausa automática).</li></ul>`,
    },
    {
      id: "usuarios", seccion: "Dirección del ejercicio", titulo: "Cuentas y usuarios", director: true,
      claves: "usuarios cuentas crear cuenta contraseña olvidada restablecer solicitudes pendientes asignar escenario alumno",
      texto: `<p>CONSOLA → <b>Usuarios</b>: crear cuentas, cambiar su repartición, restablecer contraseñas y aprobar las
        solicitudes de cuenta pendientes. Para que una cuenta vea un ejercicio, márquela en CONSOLA → Escenario → <b>Usuarios
        con acceso a este escenario</b>.</p>`,
    },
    // ------------------------------------------------------------------ problemas
    {
      id: "no-puedo-ordenar", seccion: "Problemas frecuentes", titulo: "No puedo dar la orden",
      claves: "no puedo ordenar orden rechazada corresponde a otra reparticion no aparece el tipo de orden boton gris error unidad destruida embarcada",
      texto: `<ul><li>«Esa acción corresponde a otra repartición»: cada repartición ordena solo sus unidades (ver «Qué ordena cada
        repartición»).</li>
        <li>No aparece el tipo de orden: esa unidad no puede cumplirla (por ejemplo, solo las aeronaves patrullan).</li>
        <li>No aparece el blanco: el enemigo no está detectado por su bando.</li>
        <li>Una unidad embarcada, destruida o sin enlace (drones interferidos) no recibe órdenes.</li></ul>`,
    },
    {
      id: "reloj-quieto", seccion: "Problemas frecuentes", titulo: "El reloj no avanza o las unidades no se mueven",
      claves: "reloj no avanza detenido quieto no se mueven congelado pausa nada pasa",
      texto: `<ul><li>Mire abajo: si dice <b>RELOJ DETENIDO</b>, el director debe ponerlo en marcha.</li>
        <li>Si arriba hay una franja <b>PAUSA AUTOMÁTICA</b>, el reloj se detuvo por una alerta: el director lo reanuda.</li>
        <li>El reloj solo corre mientras alguien está conectado al ejercicio.</li>
        <li>Una unidad sin combustible, varada o esperando en tierra no se mueve: revise su detalle.</li></ul>`,
    },
    {
      id: "no-abre", seccion: "Problemas frecuentes", titulo: "La página no abre o se desconectó",
      claves: "no abre pagina no carga desconectado sin conexion servidor direccion puerto 8001 recargar f5 caida",
      texto: `<ul><li>Revise la dirección: es la de la PC del Cóndor y termina en <b>:8001</b>.</li>
        <li>El punto de conexión (arriba, junto al reloj) en rojo indica que se perdió la conexión: recargue con <b>F5</b>.</li>
        <li>Si se cerró la ventana del servidor, el director lo vuelve a abrir con el acceso directo <b>Condor</b>; no se pierde
        lo hecho.</li></ul>`,
    },
  ];

  // ------------------------------------------------------------------ buscador
  const VACIAS = new Set(("a al como con cual cuales cuando de del donde el en es esta este hay la las le lo los me mi mis " +
    "o para por porque puedo puede que se si sin su sus un una uno unos y yo hacer hace hago tengo tiene quiero saber " +
    "funciona funcionan sirve hago").split(" "));
  const SINONIMOS = {
    avion: "aeronave", aviones: "aeronave", aeronaves: "aeronave", jet: "aeronave", caza: "aeronave",
    disparar: "atacar", tirar: "atacar", bombardear: "atacar", fuego: "atacar",
    clave: "contraseña", password: "contraseña", login: "entrar", ingresar: "entrar",
    tiempo: "reloj", acelerar: "velocidad", pausar: "pausa", parar: "detener",
    lluvia: "clima", tormenta: "clima", meteorologia: "clima",
    gasolina: "combustible", nafta: "combustible", balas: "municion",
    jamming: "interferencia", interferir: "interferencia", radares: "radar",
  };

  function normalizar(texto) {
    return String(texto || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/\b([a-z])-(\d)/g, "$1$2")  // "A-4" = "a4", "C-E" queda igual
      .replace(/[^a-z0-9+\- ]+/g, " ");
  }

  function raizDe(p) {  // plural sencillo: "ordenes" -> "orden", "unidades" -> "unidad", "radares" -> "radar"
    if (p.length > 5 && p.endsWith("es")) return p.slice(0, -2);
    if (p.length > 3 && p.endsWith("s")) return p.slice(0, -1);
    return p;
  }

  function palabras(texto) {
    const salida = [];
    for (const p of normalizar(texto).split(/\s+/)) {
      if (!p || VACIAS.has(p)) continue;
      salida.push(raizDe(p));
      if (SINONIMOS[p]) salida.push(raizDe(normalizar(SINONIMOS[p])));
    }
    return [...new Set(salida)];
  }

  const sinEtiquetas = (html) => String(html).replace(/<[^>]+>/g, " ");
  const INDICE = new Map();
  function indice(t) {
    let i = INDICE.get(t.id);
    if (!i) {
      i = { titulo: palabras(t.titulo), claves: palabras(t.claves), texto: palabras(sinEtiquetas(t.texto)) };
      INDICE.set(t.id, i);
    }
    return i;
  }

  function coincide(p, lista) {
    for (const w of lista) {
      if (w === p) return 1;
      if (p.length >= 4 && w.length >= 4 && (w.startsWith(p) || p.startsWith(w))) return 0.7;
    }
    return 0;
  }

  /** Temas que responden a la pregunta, del más al menos pertinente (sin los del director si no corresponde). */
  function buscar(pregunta, opciones = {}) {
    const q = palabras(pregunta);
    if (!q.length) return [];
    const temas = opciones.temas || TEMAS;
    const res = [];
    for (const t of temas) {
      if (t.director && !opciones.director) continue;
      const i = indice(t);
      let puntos = 0;
      let halladas = 0;
      for (const p of q) {
        const s = 3 * coincide(p, i.titulo) + 2 * coincide(p, i.claves) + coincide(p, i.texto);
        if (s > 0) halladas += 1;
        puntos += s;
      }
      if (puntos > 0) res.push({ tema: t, puntos: puntos * (0.5 + halladas / q.length) });
    }
    res.sort((a, b) => b.puntos - a.puntos);
    return res.slice(0, opciones.max || 6).map((r) => r.tema);
  }

  const api = { SECCIONES, TEMAS, buscar, palabras, normalizar };
  if (typeof module !== "undefined") module.exports = api;
  raiz.AyudaTemas = api;
})(typeof window !== "undefined" ? window : globalThis);
