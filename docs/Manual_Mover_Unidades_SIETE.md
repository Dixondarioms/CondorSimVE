# S.I.E.T.E. — Manual paso a paso: cómo mover las unidades

**Sistema Integral de Entrenamiento Táctico y Estratégico (Simulador Fénix)**
Guía para los alumnos de cada bando y para el instructor. Versión del 24 de octubre de 2026.

> **Cómo usar los espacios para capturas.** Cada recuadro marcado con 📷 indica una captura de pantalla
> que falta pegar. Debajo del número va la descripción de lo que debe verse. Pegue la imagen justo debajo
> del recuadro y borre la línea *(pegar aquí la imagen)*.

---

## Índice

1. [Antes de empezar](#1-antes-de-empezar)
2. [Unidades terrestres y navales: la orden «Mover»](#2-unidades-terrestres-y-navales-la-orden-mover)
3. [Mover varias unidades a la vez (Ctrl+clic y formación)](#3-mover-varias-unidades-a-la-vez-ctrlclic-y-formación)
4. [Aeronaves: despegar, mover, patrullar y aterrizar](#4-aeronaves-despegar-mover-patrullar-y-aterrizar)
5. [Embarque y desembarco de tropas](#5-embarque-y-desembarco-de-tropas)
6. [Confirmar las órdenes del turno](#6-confirmar-las-órdenes-del-turno)
7. [Instructor: reubicar unidades arrastrándolas en el editor del escenario](#7-instructor-reubicar-unidades-arrastrándolas-en-el-editor-del-escenario)
8. [Problemas frecuentes](#8-problemas-frecuentes)
9. [Resumen en una página](#9-resumen-en-una-página)
10. [Lista de capturas](#10-lista-de-capturas)

---

## 1. Antes de empezar

Para dar órdenes de movimiento se necesitan cuatro cosas:

1. **Entrar como alumno de un bando** (azul o rojo). El instructor y el observador no emiten órdenes;
   el instructor mueve unidades solo con el editor del escenario (sección 7).
2. **Que el escenario esté activo y en fase de decisión.** El reloj de la cabecera muestra
   «PLANIFICACIÓN» y el tiempo que queda. Si dice «PAUSADO» o «ESCENARIO FINALIZADO», los botones de
   órdenes quedan apagados.
3. **Estar en la pestaña FUERZAS** del panel izquierdo. Allí están el *Orden de batalla*, la ficha de la
   *Unidad seleccionada*, el bloque *Nueva orden* y la *Cola de órdenes*.
4. **Que la unidad sea de su repartición.** Cada alumno conduce las unidades que corresponden a su puesto
   de estado mayor. Si selecciona una unidad de otra repartición, el bloque *Nueva orden* lo avisa
   («Esta unidad la conduce la repartición…») y no la acepta.

> 📷 **Captura 1.** Pantalla completa del alumno: cabecera con el reloj en «PLANIFICACIÓN», pestaña FUERZAS
> abierta a la izquierda, el mapa al centro y la barra inferior con el botón «ESTOY LISTO - CONFIRMAR ÓRDENES».
> *(pegar aquí la imagen)*

**Qué significa un turno.** Cada turno equivale a una hora simulada. Una orden de movimiento se cumple
durante ese turno: la unidad avanza lo que su velocidad, el terreno, el clima y el combustible le
permiten en una hora, y se detiene. Si no llegó al destino, el turno siguiente se le da otra orden.

---

## 2. Unidades terrestres y navales: la orden «Mover»

### 2.1 Seleccionar la unidad

1. En el *Orden de batalla*, haga clic sobre la unidad. También puede hacer clic sobre su símbolo en el
   mapa. El mapa se centra en ella y la ficha *Unidad seleccionada* muestra sus datos (velocidad,
   combustible, fuerza).
2. Compruebe que el título del bloque *Nueva orden* cambió a **«Nueva orden · nombre de la unidad»**. Si
   sigue diciendo «elija una unidad», la unidad no acepta órdenes (está destruida, embarcada, es una base
   o pertenece a otra repartición).
3. Si la lista es larga, escriba parte del nombre, la clase o el modelo en el cuadro *Buscar unidad* y
   pulse Enter para seleccionar la primera coincidencia.

> 📷 **Captura 2.** Panel FUERZAS con una unidad terrestre seleccionada en el Orden de batalla, su ficha
> desplegada y el bloque «Nueva orden» mostrando el nombre de la unidad.
> *(pegar aquí la imagen)*

### 2.2 Marcar la ruta con puntos de paso (waypoints)

1. En *Nueva orden*, deje activo el modo **«Mover»** (es el que viene marcado por defecto).
2. Haga clic en el mapa en el primer punto por donde quiere que pase la unidad. Aparece un círculo azul
   con la etiqueta **W1**.
3. Siga haciendo clic para agregar **W2, W3…** en el orden en que se recorrerán. Una línea blanca
   punteada une los puntos. El último punto es el destino. Una orden admite hasta 30 puntos.
4. En el bloque de la orden se listan las coordenadas de cada punto («W1: lat, lon | W2: …»).
5. Si se equivocó, pulse **«Limpiar waypoints»** y marque la ruta de nuevo. No se puede borrar un solo
   punto: se limpian todos.

> 📷 **Captura 3.** Mapa con una ruta de tres puntos (W1, W2, W3) unidos por la línea punteada, y el
> bloque «Nueva orden» con la lista de coordenadas.
> *(pegar aquí la imagen)*

### 2.3 Leer la previsualización

Al marcar el primer punto, el simulador calcula dónde terminaría la unidad **al final de este turno** y
lo dibuja en el mapa:

- Una **línea celeste gruesa** sobre el camino real que seguirá durante la hora.
- Un **círculo celeste** en el punto donde quedará al cerrar el turno («Posición al final del turno»).
- Si llega al destino, una etiqueta **ETA** con la hora de llegada y la duración.
- En el bloque de la orden, un texto como: *«Llega al último waypoint: recorre 38 km, combustible
  restante 71 %»* o *«No llega al destino este turno: …»*. Si algo la detiene (río sin puente, terreno
  intransitable, sin combustible), la nota lo dice.

Lea siempre esta nota antes de emitir: es la forma de saber cuántos turnos necesitará la unidad.

> 📷 **Captura 4.** Previsualización: línea celeste, círculo de «Posición al final del turno», etiqueta
> ETA y el texto de la nota con los kilómetros y el combustible restante.
> *(pegar aquí la imagen)*

### 2.4 «Seguir carreteras» (solo unidades terrestres)

Una unidad terrestre que cruza campo traviesa avanza lento y puede quedar detenida en un río. El botón
**«Seguir carreteras»** le ahorra marcar la ruta a mano:

1. Marque un solo punto en el mapa: el destino (si marcó varios, se toma el último).
2. Pulse **«Seguir carreteras»**. El simulador reemplaza sus puntos por la ruta más rápida por carreteras
   y puentes (hasta 30 tramos) y vuelve a calcular la previsualización.
3. Aparece un aviso con el resultado, por ejemplo: *«Ruta por el camino más rápido (62 km, 14 tramos)»*.
4. Si la nota dice *«No hay camino transitable (ríos sin puente, agua o montaña): ruta directa»* o
   *«El destino es intransitable para esta unidad: ruta directa»*, la ruta queda en línea recta y
   conviene elegir otro destino o pedir ingenieros para tender un puente o vado.
5. Para un buque, el botón responde *«Solo las unidades terrestres siguen carreteras: ruta directa»*.

> 📷 **Captura 5.** Antes y después de «Seguir carreteras»: a la izquierda el destino marcado con un solo
> punto, a la derecha la ruta trazada por la carretera con sus tramos y el aviso del resultado.
> *(pegar aquí la imagen)*

### 2.5 Reglas del terreno que conviene recordar

| Tipo de unidad | Por dónde avanza | Qué la frena o detiene |
| --- | --- | --- |
| Terrestre ligera (infantería, antiaérea portátil, ingenieros, reconocimiento) | Campo, carreteras; vadea los ríos a pie | Bosque y montaña la frenan; el agua (mar, lagos) la detiene |
| Terrestre pesada (blindados, artillería, camiones) | Campo, carreteras; cruza ríos **solo por un puente** o por una obra de ingenieros | Un río sin puente la detiene con la nota «río sin puente ni vado» |
| Naval | Solo sobre el agua | Se detiene en la costa si un tramo de la ruta pasa por tierra |

Las carreteras aceleran el avance; un puente de carretera cortado se cruza como si no existiera. El
clima (lluvia, tormenta) reduce la velocidad de todas.

### 2.6 Emitir la orden

1. Pulse **«Emitir orden»**. Aparece el aviso «Orden emitida» y la orden pasa a la *Cola de órdenes* como
   «Mover (3 waypoints) · PENDIENTE».
2. En el mapa, la ruta pendiente se dibuja con una línea azul discontinua animada desde la unidad hasta
   su destino, y en el *Orden de batalla* la unidad muestra la etiqueta «Orden: mover».
3. Cada unidad tiene **una sola orden por turno**: si emite otra, la nueva reemplaza a la anterior.
4. Para anular una orden pendiente, pulse la **×** que aparece a su derecha en la *Cola de órdenes*.

> 📷 **Captura 6.** Cola de órdenes con la orden «Mover (3 waypoints)» en estado PENDIENTE, el botón ×
> para cancelarla y, en el mapa, la línea azul animada de la ruta.
> *(pegar aquí la imagen)*

### 2.7 Buques: lo mismo, sobre el agua

El procedimiento para un buque es idéntico: seleccionar, marcar los puntos sobre el mar y emitir. Marque
los puntos **siempre sobre el agua**: si un tramo de la ruta pasa por tierra, el buque se detiene en la
costa y la previsualización muestra «Avance detenido: terreno intransitable». Para rodear una
península o entrar a un golfo, agregue puntos intermedios que sigan la costa.

> 📷 **Captura 7.** Buque con una ruta de varios puntos que bordea la costa y la previsualización
> indicando que llega al destino.
> *(pegar aquí la imagen)*

---

## 3. Mover varias unidades a la vez (Ctrl+clic y formación)

### 3.1 Armar la selección múltiple

1. Seleccione la primera unidad con un clic normal. Esa unidad es la **líder** del grupo.
2. Mantenga pulsada la tecla **Ctrl** (o Mayús) y haga clic sobre las demás unidades, en el *Orden de
   batalla* o en el mapa. Cada clic con Ctrl **suma** la unidad al grupo; un segundo clic con Ctrl sobre
   la misma la **quita**.
3. Solo entran unidades propias, activas y que su repartición pueda conducir. Las bases y las unidades a
   bordo de un transporte no se pueden sumar.
4. En *Nueva orden* aparece el aviso **«N unidades seleccionadas: la orden se emite a todas»**, con la
   casilla **«Mantener la formación»** y el botón **«Dejar solo una»** (vuelve a quedar solo la líder).

> 📷 **Captura 8.** Tres unidades seleccionadas con Ctrl+clic: resaltadas en el Orden de batalla y en el
> mapa, y el aviso «3 unidades seleccionadas» con la casilla «Mantener la formación».
> *(pegar aquí la imagen)*

### 3.2 Marcar la ruta y emitir

1. Marque los puntos de paso igual que para una sola unidad. La ruta y la previsualización se calculan
   para la **líder**.
2. Si quiere usar carreteras, pulse «Seguir carreteras»: la ruta de la líder se traza por la vía y las
   demás la copian desplazada.
3. Decida qué hacer con la formación:
   - **Casilla marcada (recomendado para avanzar en bloque):** cada unidad recibe la misma ruta
     desplazada según su posición respecto de la líder. Si estaban en línea a 2 km una de otra, llegan al
     destino en línea a 2 km una de otra.
   - **Casilla desmarcada (para concentrar):** todas reciben exactamente los mismos puntos y convergen en
     el mismo destino.
4. Pulse **«Emitir orden»**. El aviso informa cuántas se emitieron, por ejemplo
   *«Orden emitida a 3 de 3 unidades»*. Si alguna falla, el aviso indica el motivo por unidad
   (*«Batallón 42: La unidad no tiene combustible»*) y las demás sí quedan ordenadas.

> 📷 **Captura 9.** Resultado de una orden en lote con la formación activa: tres rutas paralelas en el
> mapa y el aviso «Orden emitida a 3 de 3 unidades».
> *(pegar aquí la imagen)*

**Consejo.** Con la formación activa, cada unidad cruza el terreno que tiene delante, no el de la líder.
Si la líder va por la carretera y una compañera queda 3 km al costado, esa compañera irá campo traviesa
y puede retrasarse. Revise en la cola la nota de cada una después de resolver el turno.

---

## 4. Aeronaves: despegar, mover, patrullar y aterrizar

Las aeronaves vuelan en línea recta y no las frena el terreno, pero gastan combustible según su perfil
de vuelo y necesitan una base propia para aterrizar.

### 4.1 Enviar a despegar un grupo nuevo

Las aeronaves no existen en el mapa hasta que despegan desde una base aérea o un portaaviones propio.

1. En la pestaña FUERZAS, bloque **Aviación**, pulse **«✈ Enviar aeronaves o drones…»**. Si antes
   seleccionó una base en el mapa, esa base viene elegida.
2. En la ventana *Enviar aeronaves o drones*:
   - Elija el **modelo** en las tarjetas (caza, dron, avión de guerra electrónica, helicóptero). Cada
     tarjeta muestra alcance, detección y autonomía. Los modelos que no caben en la pista útil de la base
     aparecen explicados en una nota.
   - Elija la **base de origen** (desde un portaaviones solo salen helicópteros, drones y cazas
     embarcados).
   - Elija **cuántas aeronaves** forman el grupo (de 1 a 12) y, si quiere, un **indicativo** («Halcón 1»).
   - El resumen indica que el grupo saldrá de la base al resolverse el turno y aparecerá junto a ella.
3. Pulse **«Enviar a despegar»**. El aviso dice «Grupo listo para despegar al resolverse el turno» y en
   la cola aparece una orden «Despegar».
4. El contador del bloque Aviación (por ejemplo «8/12») muestra cuántas aeronaves tiene comprometidas su
   bando sobre el tope del escenario; los drones tienen su propio tope.

> 📷 **Captura 10.** Ventana «Enviar aeronaves o drones» con el modelo elegido, la base de origen, la
> cantidad, el indicativo y el botón «Enviar a despegar».
> *(pegar aquí la imagen)*

> 📷 **Captura 11.** El grupo recién aparecido junto a su base después de resolver el turno, con su
> símbolo y su nombre en el Orden de batalla.
> *(pegar aquí la imagen)*

### 4.2 Mover un grupo en vuelo

Una vez en el aire, el grupo se mueve como cualquier unidad: selecciónelo, modo **«Mover»**, marque los
puntos y emita. La previsualización indica cuánto combustible le quedará. Como vuela recto, con un solo
punto basta en la mayoría de los casos.

Si el grupo está **en tierra** (aterrizó antes), cualquier orden de vuelo (mover, patrullar, atacar)
vale como despegue, pero solo cuando terminó de reabastecer y rearmar: el bloque *Nueva orden* muestra
*«En tierra: podrá despegar en N turnos»* y, hasta entonces, rechaza las órdenes de vuelo.

### 4.3 Patrullar una zona

1. Seleccione el grupo. Como es una aeronave, en los modos de la orden aparece el botón **«Patrullar»**.
2. Pulse «Patrullar» y haga **un solo clic** en el mapa, en el centro de la zona a cubrir.
3. Pulse **«Emitir orden»**. Al resolverse el turno, el grupo vuela hasta allí, se queda en la zona
   gastando un 8 % de combustible por turno e intercepta a los aviones enemigos que detecte a su alcance.
4. La patrulla **se mantiene sola** en los turnos siguientes sin que haga falta repetir la orden. En el
   Orden de batalla la unidad figura como «Patrullando». Con combustible crítico regresa por su cuenta a
   la base más cercana.
5. Para terminar la patrulla, dele otra orden (mover, aterrizar o atacar).

> 📷 **Captura 12.** Modo «Patrullar» con el punto de patrulla marcado en el mapa y la ayuda del bloque
> de la orden.
> *(pegar aquí la imagen)*

### 4.4 Aterrizar

1. Seleccione el grupo en vuelo. Aparece el modo **«Aterrizar»** (solo para aeronaves en vuelo).
2. Pulse «Aterrizar» y elija la **base de destino** en la lista; cada opción muestra la distancia.
3. Lea la nota: *«Llega y aterriza este turno (45 km)»* o *«A 380 km: tardará 2 turnos en llegar»*. Si
   el combustible no alcanza, la nota indica cuánto necesita y cuánto tiene.
4. Pulse **«Emitir orden»**. Si no llega este turno, el grupo avanza hacia la base; el turno siguiente
   repita la orden de aterrizar.
5. En tierra, el grupo tarda **2 turnos** en reabastecer y rearmar. Una base guarda hasta 12 aeronaves;
   si no tiene plazas libres, no aparece en la lista.

> 📷 **Captura 13.** Modo «Aterrizar» con la lista de bases y la nota de distancia y turnos.
> *(pegar aquí la imagen)*

**Misiones aéreas planificadas.** Para una salida con ruta, blanco, escolta y hora sobre el blanco se usa
el bloque *Misiones aéreas* (botón «Planificar misión…»), no la orden simple de mover. Ese procedimiento
tiene su propio capítulo en el Manual de usuario.

---

## 5. Embarque y desembarco de tropas

Solo dos tipos de transporte llevan tropas: el **buque de desembarco** (hasta 3 unidades terrestres de
cualquier movilidad) y el **helicóptero de transporte artillado** (1 unidad ligera: infantería,
antiaérea portátil, ingenieros o reconocimiento).

### 5.1 Embarcar

1. Acerque la unidad terrestre al transporte: tiene que quedar **a menos de 3 km**. Si está más lejos,
   primero dele una orden «Mover» hasta su lado y resuelva ese turno.
2. Seleccione la unidad terrestre. Si hay un transporte propio con plazas a menos de 3 km, aparece el
   modo **«Embarcar»**.
3. Pulse «Embarcar» y elija el transporte en la lista. Cada opción muestra el nombre, la distancia y la
   carga actual («2/3 a bordo»).
4. Pulse **«Emitir orden»**. La unidad sube al resolverse el turno.
5. A bordo, la unidad figura como **«A bordo»** en el Orden de batalla: no se la ve ni se la ataca por
   separado, no recibe órdenes, viaja con el transporte y sufre la mitad del daño que este reciba. Si
   hunden o derriban el transporte, se pierde con él.

> 📷 **Captura 14.** Unidad de infantería junto a un buque de desembarco, con el modo «Embarcar» visible y
> la lista de transportes con la distancia y la carga.
> *(pegar aquí la imagen)*

### 5.2 Desembarcar

1. Seleccione el **transporte** (no la tropa). Si lleva unidades a bordo, aparece el modo
   **«Desembarcar»**.
2. Pulse «Desembarcar» y marque en el mapa la ruta del transporte. El **último punto** es el lugar de
   desembarco y debe estar **en tierra firme**; la nota del bloque muestra quién va a bordo y las
   coordenadas del punto.
3. Pulse **«Emitir orden»**. Al resolverse el turno, el buque navega hasta **a menos de 5 km** del punto
   (no entra en tierra) y las unidades aparecen en el lugar marcado. Un helicóptero vuela hasta el
   punto y las deja allí.
4. Si el transporte no llega en este turno, **sigue solo** en los turnos siguientes hasta desembarcar; no
   hace falta repetir la orden.
5. Las tropas recién desembarcadas necesitan sus turnos de despliegue antes de combatir a pleno; aparecen
   en la ficha de cada una.

> 📷 **Captura 15.** Buque de desembarco con la ruta de desembarco marcada, el último punto en la playa y
> la nota «A bordo: … Punto de desembarco: …».
> *(pegar aquí la imagen)*

---

## 6. Confirmar las órdenes del turno

Emitir una orden no cierra el turno. El bando debe **confirmar** que terminó de planificar.

1. Revise la *Cola de órdenes*: todas las órdenes del turno deben decir **PENDIENTE**. El contador del
   título indica cuántas hay. Si falta alguna, emítala; si sobra, cancélela con la **×**.
2. En la barra inferior pulse **«ESTOY LISTO - CONFIRMAR ÓRDENES»**. El botón cambia a
   **«ÓRDENES CONFIRMADAS - CLIC PARA RETIRAR»** y el estado de su bando en la barra pasa de
   «PLANIFICANDO» a «LISTO».
3. Si después de confirmar emite o cancela una orden, la confirmación **se retira sola** y hay que volver
   a pulsar el botón. Esto evita que un bando quede «listo» con órdenes distintas de las que revisó.
4. El turno se resuelve de una de tres maneras: el instructor pulsa **«RESOLVER Y AVANZAR TURNO»**; se
   agota el tiempo de planificación (el simulador resuelve solo, con las órdenes que haya); o los dos
   bandos confirman y el escenario tiene activada la resolución automática. Al resolverse, las unidades
   se deslizan por el mapa hasta su nueva posición y dejan un rastro del camino recorrido.
5. Después de resolver, cada orden de la cola pasa a **RESUELTA** con su resultado (kilómetros recorridos,
   combustible, si llegó) o a **RECHAZADA** con el motivo. Las unidades que no llegaron necesitan una
   orden nueva.

> 📷 **Captura 16.** Barra inferior con el botón «ÓRDENES CONFIRMADAS - CLIC PARA RETIRAR» y el estado del
> bando en «LISTO».
> *(pegar aquí la imagen)*

> 📷 **Captura 17.** Cola de órdenes después de resolver el turno: órdenes RESUELTAS con su resultado y el
> rastro del movimiento en el mapa.
> *(pegar aquí la imagen)*

**Comunicaciones.** Si el escenario tiene demoras de comunicaciones, una orden puede «no llegar a tiempo»:
queda pendiente y se cumple en el turno siguiente, una sola vez. La interferencia enemiga y los daños en
la infraestructura de transmisiones aumentan esa probabilidad. Las órdenes de despegue a una base
siempre llegan.

---

## 7. Instructor: reubicar unidades arrastrándolas en el editor del escenario

El instructor no da órdenes: coloca y corrige. Para mover una unidad sin gastar un turno (por ejemplo,
al preparar el escenario o al adjudicar un resultado), se usa el editor.

1. Entre como instructor y abra la pestaña **CONSOLA** del panel izquierdo.
2. Despliegue el apartado **«Editar el escenario»** y marque la casilla
   **«Arrastrar unidades en el mapa para reubicarlas»**.
3. En el mapa, tome cualquier unidad con el botón izquierdo, arrástrela y suéltela en su nueva posición.
   El cambio se guarda al soltar y todos los conectados lo ven al instante.
4. El servidor valida el terreno al soltar: una unidad terrestre o una base **no puede quedar en el
   agua**, y un buque **solo puede quedar en el agua**. Si suelta en un lugar no válido, la unidad vuelve
   sola a donde estaba. Un punto de recobre con pista solo acepta tramos de carretera aptos o aeródromos.
5. Cada arrastre queda registrado en el informe del ejercicio como **ajuste manual** de esa unidad, con
   las coordenadas anteriores y las nuevas.
6. Al terminar, **desmarque la casilla** para que un clic accidental no desplace unidades mientras dirige
   el ejercicio.

> 📷 **Captura 18.** Pestaña CONSOLA con el apartado «Editar el escenario» desplegado y la casilla
> «Arrastrar unidades en el mapa para reubicarlas» marcada.
> *(pegar aquí la imagen)*

> 📷 **Captura 19.** Una unidad a mitad de arrastre en el mapa y, después de soltarla, el registro del
> ajuste manual en las novedades del turno o en el informe.
> *(pegar aquí la imagen)*

Para quitar una unidad, selecciónela y use «Eliminar unidad» en su ficha. Si ya participó en combates y
consta en el informe, el simulador no permite borrarla: hay que marcarla como destruida.

---

## 8. Problemas frecuentes

| Qué pasa | Por qué | Qué hacer |
| --- | --- | --- |
| Hago clic en el mapa y no aparece ningún punto W1 | No hay una unidad elegida para la orden, o no es la pestaña FUERZAS, o entró como instructor u observador | Seleccione primero una unidad propia; compruebe que *Nueva orden* muestre su nombre |
| El bloque *Nueva orden* dice «elija una unidad» aunque hice clic en una | La unidad está destruida, a bordo de un transporte, es una base, o la conduce otra repartición | Lea el aviso amarillo del bloque; pida la orden al alumno de la repartición responsable |
| «Emitir orden» está apagado | El escenario no está activo o no está en fase de decisión (pausado, resolviendo o finalizado) | Espere a que el instructor reanude o abra el turno siguiente |
| Aviso «Marque al menos un waypoint en el mapa» | Pulsó «Emitir orden» sin puntos de paso | Marque la ruta y vuelva a emitir |
| La previsualización dice «Avance detenido: río sin puente ni vado» | Unidad pesada frente a un río sin puente | Use «Seguir carreteras» para cruzar por un puente, o pida a los ingenieros que construyan un vado o puente |
| «Avance detenido: terreno intransitable» | Una unidad terrestre apunta al agua, o un buque a tierra | Corrija los puntos de paso para que queden sobre el terreno que la unidad puede recorrer |
| «No llega al destino este turno» | La distancia supera lo que recorre en una hora | Es normal: emita otra orden el turno siguiente, o acorte el destino |
| «Seguir carreteras» responde «ruta directa» | No hay camino transitable, el destino es intransitable o la unidad es naval o aérea | Elija otro destino en tierra con acceso por carretera, o marque la ruta a mano |
| «La unidad no tiene combustible» / «Avance detenido: sin combustible» | Combustible en cero | Reabastezca en un depósito, puerto o base propia; mientras tanto la unidad no se mueve |
| Con Ctrl+clic la unidad no se suma al grupo | No es propia, está destruida, es una base, va a bordo, o es de otra repartición | Solo se agrupan unidades que usted mismo podría ordenar una por una |
| «Orden emitida a 2 de 3 unidades» | Una del grupo falló su validación; el aviso dice cuál y por qué | Resuelva el motivo (combustible, espera en tierra) y emítale su orden por separado |
| En el grupo, una unidad se quedó atrás | Con formación, cada una cruza su propio terreno | Desmarque «Mantener la formación» para concentrarlas por la misma ruta, o acérquelas antes |
| No aparece el modo «Patrullar» ni «Aterrizar» | La unidad no es una aeronave, o ya está en tierra (Aterrizar) | Seleccione un grupo aéreo en vuelo |
| «En tierra: faltan N turno(s) para reabastecer y rearmar» | El grupo aterrizó hace menos de 2 turnos | Espere; mientras tanto puede planificar otras unidades |
| «No hay una base propia con plazas libres para este grupo» | Todas las bases están llenas (12 aeronaves) o fuera de servicio | Despeje una base despegando otro grupo, o use otra base o portaaviones |
| «Su bando no tiene una base aérea activa» | No hay base aérea propia en el escenario | Pida al instructor que coloque una desde la capa «Bases aéreas y aeródromos» |
| No aparece el modo «Embarcar» | No hay transporte propio con plazas a menos de 3 km, o la unidad no es terrestre | Acerque la unidad al transporte con una orden «Mover» y resuelva el turno |
| «El transporte está a X km: acérquese a menos de 3 km» | Demasiado lejos para embarcar | Igual que arriba |
| «X solo transporta unidades ligeras» | Quiso subir blindados o artillería a un helicóptero | Use un buque de desembarco para unidades pesadas |
| «El punto de desembarco debe estar en tierra firme» | El último punto de la ruta cayó en el agua | Mueva el último punto a la playa o a tierra |
| El buque no desembarcó este turno | No llegó a menos de 5 km del punto | Déjelo: sigue solo los turnos siguientes y desembarca al llegar |
| Confirmé y el botón volvió a «ESTOY LISTO» | Alguien de su bando emitió o canceló una orden después de confirmar | Revise la cola y confirme de nuevo |
| Una orden quedó PENDIENTE después de resolver el turno | Demora de comunicaciones: se cumple en el turno siguiente | No la repita; si la vuelve a emitir, reemplaza la que ya está en camino |
| Instructor: arrastré una unidad y volvió a su sitio | El servidor rechazó la posición (terrestre en el agua, buque en tierra, pista de PRO fuera de tramo apto) | Suéltela en terreno válido |
| Instructor: las unidades no se dejan arrastrar | La casilla «Arrastrar unidades en el mapa para reubicarlas» está desmarcada | Márquela en CONSOLA › Editar el escenario |

---

## 9. Resumen en una página

**Mover una unidad:** FUERZAS › clic en la unidad › modo «Mover» › clic en el mapa (W1, W2…) › leer la
previsualización › «Emitir orden».

**Por carretera:** marcar solo el destino › «Seguir carreteras» › «Emitir orden».

**Varias a la vez:** clic en la líder › Ctrl+clic en las demás › marcar la ruta › decidir «Mantener la
formación» › «Emitir orden».

**Aeronaves:** Aviación › «Enviar aeronaves o drones…» › modelo, base, cantidad › «Enviar a despegar».
En vuelo: «Mover», «Patrullar» (un clic) o «Aterrizar» (elegir base). En tierra: 2 turnos de espera.

**Tropas embarcadas:** tropa a menos de 3 km del transporte › «Embarcar» › elegir transporte. Después,
seleccionar el transporte › «Desembarcar» › ruta con el último punto en tierra.

**Cerrar el turno:** revisar la Cola de órdenes › «ESTOY LISTO - CONFIRMAR ÓRDENES». Cualquier orden
nueva retira la confirmación.

**Instructor:** CONSOLA › Editar el escenario › «Arrastrar unidades en el mapa para reubicarlas» ›
arrastrar y soltar. Queda registrado como ajuste manual.

---

## 10. Lista de capturas

Use esta lista para controlar cuáles faltan. Nombre sugerido para los archivos: `mover_01.png`,
`mover_02.png`, etc., en una carpeta `docs/capturas_mover/`.

| N.º | Sección | Qué debe verse |
| --- | --- | --- |
| 1 | 1 | Pantalla completa del alumno en PLANIFICACIÓN, pestaña FUERZAS y barra inferior |
| 2 | 2.1 | Unidad terrestre seleccionada, su ficha y «Nueva orden · nombre» |
| 3 | 2.2 | Ruta de tres puntos W1-W3 y la lista de coordenadas |
| 4 | 2.3 | Previsualización: línea celeste, posición final, ETA y nota |
| 5 | 2.4 | Antes y después de «Seguir carreteras» |
| 6 | 2.6 | Cola con la orden PENDIENTE, la × y la ruta azul animada |
| 7 | 2.7 | Buque con ruta que bordea la costa |
| 8 | 3.1 | Tres unidades seleccionadas con Ctrl+clic y la casilla de formación |
| 9 | 3.2 | Rutas paralelas del lote y aviso «Orden emitida a 3 de 3 unidades» |
| 10 | 4.1 | Ventana «Enviar aeronaves o drones» completa |
| 11 | 4.1 | Grupo recién despegado junto a su base |
| 12 | 4.3 | Modo «Patrullar» con el punto marcado |
| 13 | 4.4 | Modo «Aterrizar» con la lista de bases y la nota |
| 14 | 5.1 | Modo «Embarcar» con la lista de transportes |
| 15 | 5.2 | Ruta de desembarco con el último punto en tierra |
| 16 | 6 | Botón «ÓRDENES CONFIRMADAS» y bando en LISTO |
| 17 | 6 | Cola con órdenes RESUELTAS y rastro del movimiento |
| 18 | 7 | CONSOLA › Editar el escenario con la casilla marcada |
| 19 | 7 | Unidad arrastrada y el registro del ajuste manual |

---

*Manual elaborado para S.I.E.T.E. (Simulador Fénix). Cap. Dixon Malpica, División de Ingeniería y
Desarrollo Aeroespacial (DIDA), Aviación Militar Bolivariana.*
