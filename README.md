# S.I.E.T.E. — Sistema Integral de Entrenamiento Táctico y Estratégico

(Nombre de desarrollo del proyecto: "Simulador Fénix"; el código, la base de datos y el repositorio conservan ese nombre.)

Wargame web multiusuario para adiestramiento en conducción (operaciones terrestres, aéreas y navales)
sobre el terreno de Venezuela. Instructor/director de ejercicio + alumnos por bando (azul/rojo),
sincronizados por WebSocket. **Funciona sin internet**: mapa, relieve, cobertura terrestre, librerías
y datos se sirven desde el propio servidor (una política CSP bloquea cualquier recurso externo).

## Manual de usuario

`docs/Manual_SIETE.pdf` (qué es, cómo se hizo, instalación y funcionamiento, con capturas y esquemas). Se regenera con
`python tools/generar_manual.py --imagenes <carpeta de capturas>` (las capturas se toman con Chrome headless del arnés de pruebas).
El logotipo e iconos están en `frontend/static/img/` (imagen institucional S.I.E.T.E. de la FANB).

## Puesta en marcha

```
cd backend
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt

# 1) crear el primer instructor (pide la contraseña por consola, mín. 8 caracteres)
venv\Scripts\python -m app.crear_usuario <usuario> --rol instructor

# 2) (opcional) escenario de demostración en los Andes/Llanos
venv\Scripts\python -m app.crear_demo

# 3) arrancar
venv\Scripts\python -m app.servidor --host 0.0.0.0 --port 8000          # HTTP en la LAN
venv\Scripts\python -m app.servidor --host 0.0.0.0 --port 8443 --https  # HTTPS (autofirmado)
```

Abrir `http://<ip-del-servidor>:8000/` (o `https://…:8443/`). La base de datos se migra sola al
arrancar (Alembic) y se hace una copia de seguridad en cada arranque y cada 6 h.

**HTTPS.** `--https` genera `backend/certs/cert.pem` y `key.pem` (autofirmado, con `localhost`, el nombre
del equipo y sus IP locales; `python -m app.gen_cert --host aula.local` añade nombres). Los navegadores
avisarán hasta que se instale `cert.pem` como certificado de confianza en cada equipo. Con un proxy
inverso TLS (Caddy, nginx) use `--proxy` en lugar de `--https`; en ambos casos la cookie de sesión pasa a
`Secure` y se envía HSTS.

### Instalación con un clic (Windows)

En un PC con Windows basta con **doble clic en `instalar.cmd`** (ejecuta `instalar.ps1`). El instalador:

1. Comprueba que hay Python 3.11 o superior (`py -3` o `python`). Si falta, indica de dónde descargarlo
   (python.org, marcando "Add python.exe to PATH") y se detiene: **nunca descarga programas por su cuenta**.
2. Crea `backend\venv` e instala `requirements.txt` (se salta si ya está instalado y no cambió).
3. Si la base no tiene usuarios, pide el nombre y la contraseña del primer instructor (la contraseña se
   escribe oculta y no pasa por la línea de comandos) y lo crea.
4. Crea el acceso directo **S.I.E.T.E.** en el Escritorio (icono del sistema). Al abrirlo se arranca el
   servidor en `http://localhost:8000/`, abierto a la red local, y a los pocos segundos se abre el navegador.
5. Abre el puerto TCP 8000 en el cortafuegos de Windows si se ejecuta como administrador; si no, muestra el
   comando `netsh` para hacerlo.

Opciones (se escriben tras el nombre: `instalar.cmd -Demo`):

| Opción | Efecto |
|---|---|
| `-Demo` | crea además el escenario de demostración (Andes/Llanos). |
| `-Servicio` | registra la tarea programada **"SIETE Servidor"** para que el servidor arranque solo al iniciar Windows (requiere ejecutar `instalar.cmd` con el botón derecho → *Ejecutar como administrador*). |
| `-Desinstalar` | quita la tarea programada, el acceso directo y la regla del cortafuegos. No borra la base de datos ni el entorno de Python. |
| `-Destino <carpeta>` | dónde crear el acceso directo (por defecto, el Escritorio). |
| `-Usuario <nombre>` | nombre del primer instructor (si no se indica, se pregunta). Con la variable de entorno `SIETE_CONTRASENA` la instalación es desatendida. |
| `-SinUsuario`, `-SinAccesoDirecto` | omiten esos pasos. |

Archivos de la carpeta raíz: `iniciar.cmd` arranca el servidor y abre el navegador (`iniciar.cmd /sin-navegador`
solo el servidor; si ya hay uno en marcha, solo abre el navegador); `detener.cmd` lo para. Las variables de
entorno `SIETE_PUERTO` (8000) y `SIETE_HOST` (0.0.0.0) cambian el puerto y la interfaz; `SIMULADOR_DB`, la base.
Cerrar la ventana del servidor también lo detiene. El instalador se puede ejecutar cuantas veces haga falta:
no repite lo que ya está hecho.

## PostgreSQL (opcional)

Por defecto se usa SQLite (un archivo, ideal para un aula). Para varias aulas o más concurrencia, el mismo
código corre sobre PostgreSQL: basta definir `SIMULADOR_DATABASE_URL` (ver `.env.example`).

```
cp .env.example .env                       # cambie POSTGRES_PASSWORD
docker compose up -d db                    # PostgreSQL 16 solo en 127.0.0.1:5432, con volumen persistente

# copiar los datos actuales (opcional; --forzar vacía el destino si ya tiene datos)
cd backend
venv\Scripts\python -m app.migrar_a_postgres --destino postgresql://simulador:<clave>@localhost:5432/simulador

# arrancar contra PostgreSQL (las migraciones se aplican solas, con un bloqueo asesor entre procesos)
set SIMULADOR_DATABASE_URL=postgresql://simulador:<clave>@localhost:5432/simulador
venv\Scripts\python -m app.servidor --host 0.0.0.0 --port 8000
```

`docker compose --profile app up -d --build` levanta también la aplicación en un contenedor. Con PostgreSQL,
los respaldos se hacen con `pg_dump` (`python -m app.respaldo`). Al resolver un turno se bloquea la fila del
escenario (`SELECT … FOR UPDATE`), de modo que dos procesos nunca lo resuelven a la vez.

## Pruebas

```
cd backend && venv\Scripts\python -m pytest          # motor, API, migraciones, respaldo, TLS, símbolos
cd backend && set TEST_DB=postgres && venv\Scripts\python -m pytest   # la misma suite sobre PostgreSQL real
node --test "frontend/tests/*.test.js"               # lógica pura del cliente
```

Las pruebas usan bases en memoria (con `TEST_DB=postgres`, un PostgreSQL embebido de `pixeltable-pgserver` o el
indicado en `TEST_DATABASE_URL`). Para probar a mano sin tocar los datos reales, apunte a otra base:
`SIMULADOR_DB=C:\ruta\prueba.db python -m app.servidor`.

**Arnés de pruebas visuales.** `python tools/generar_arnes.py` genera `frontend/static/pruebas/arnes.html`, que
ejecuta el `app.js` real contra un servidor simulado en el navegador (datos de ejemplo, sin sesión ni base de
datos): `http://localhost:8000/static/pruebas/arnes.html?rol=instructor` (o `azul`, `rojo`, `observador`).
Sirve para revisar la interfaz tras un cambio. Regenérelo si cambia `index.html` (una prueba lo avisa).

## Roles y acceso

| Rol | Ve | Puede |
|---|---|---|
| `instructor` | Todo (sin niebla); puede "ver como" un bando | Todo: escenarios, unidades, turnos, clima, eventos, ajustes, usuarios, asignaciones, informe |
| `azul` / `rojo` | Sus unidades + enemigas detectadas + últimos contactos | Emitir/cancelar órdenes, marcar "listo"; informe solo al finalizar |
| `observador` | Todo | Solo lectura (incluye el informe) |

### Puestos por función dentro del bando (estado mayor de aula)

Cada alumno de un bando ocupa un **puesto**, como las células de un centro de operaciones; así varios
alumnos trabajan a la vez sobre el mismo bando sin pisarse. Todos los puestos comparten la misma vista
(niebla de guerra, contactos, gráficos, red de mensajes del bando); lo que cambia es **qué órdenes puede
emitir** cada uno. El instructor lo asigna al crear el usuario o después (panel "Usuarios"); cambiarlo
cierra la sesión del alumno para que entre con su nueva interfaz.

| Puesto | Conduce | Confirma LISTO |
|---|---|---|
| **EM · Estado Mayor** (por defecto) | Todo: es el comportamiento de siempre para un solo alumno por bando | Sí |
| **A2 · Inteligencia** | Radares y unidades terrestres de guerra electrónica (escucha e interferencia); sigue contactos, dibuja gráficos de blancos | No |
| **A3 · Operaciones en curso** | Las aeronaves ya creadas: despegue desde pista, rutas, patrullas, ataques, aterrizajes | No |
| **A4 · Logística** | Ingenieros (puentes y vados) y convoyes de abastecimiento | No |
| **A5 · Planificación** | Unidades terrestres y navales, y el envío de grupos de caza desde las bases | Sí |

El servidor rechaza (403, explicando qué puesto corresponde) cualquier orden, cancelación o "listo" fuera
del puesto; la interfaz solo muestra las herramientas del puesto ("Mi puesto" en el panel izquierdo) y
avisa si la unidad seleccionada la conduce otra célula. Desde la consola: `python -m app.crear_usuario
a5azul --rol azul --puesto planificacion`; en el arnés, `arnes.html?rol=azul&puesto=operaciones`.

Alumnos y observadores solo acceden a los **escenarios que el instructor les asigna** (panel "Escenario").
Autorización en el servidor: cookie de sesión HttpOnly + SameSite=Strict, contraseñas PBKDF2-SHA256,
bloqueo tras 5 intentos fallidos (persistente en la base), sesiones de 12 h revocables, WebSocket
autenticado con verificación de origen, y cabeceras CSP / nosniff / frame-deny.

## Flujo de un turno (1 turno = 1 hora simulada)

1. El instructor crea el escenario, ubica unidades (clase, escalón, bando) y asigna alumnos.
2. Cada bando emite órdenes (mover con waypoints / atacar / apoyar). Una orden por unidad y turno; al
   marcar waypoints se **previsualiza** dónde terminaría la unidad (terreno, clima, combustible).
3. Cada bando pulsa "Estoy listo" (emitir o cancelar una orden lo anula). El turno se resuelve cuando el
   instructor lo pide, o **solo** al estar ambos listos (opción), o al **agotarse el límite de tiempo**.
4. Resolución en fases: movimiento → apoyos → combates simultáneos → logística.
5. Todos los clientes reciben el nuevo estado, filtrado según su bando.

## Unidades, logística y efectos

Catálogo (`backend/app/engine/catalogo.py`, 17 clases): infantería, blindados, artillería, reconocimiento,
defensa antiaérea, **antiaérea portátil** (tipo IGLA-S), **ingenieros**, **transporte logístico** (terrestres);
caza (con los modelos F-16 y Su-30), ataque a tierra, helicóptero, **helicóptero de transporte artillado** (aéreas); fragata, patrullero
(navales); base aérea, depósito y puerto (bases). Cada clase define velocidad, alcance, detección, autonomía,
efectividad contra cada tipo de objetivo y símbolo APP-6/MIL-STD-2525 (con escalón), además de movilidad
(ligera/pesada), penalización por peso, cadencia de fuego y tiempos de despliegue y recarga.

| Terreno | Velocidad terrestre | Defensa | Radio de detección enemigo |
|---|---|---|---|
| llano | ×1.0 | ×1.0 | ×1.0 |
| bosque / selva | ×0.6 | ×1.3 | ×0.6 |
| pantano / humedal | ×0.5 | ×1.0 | ×0.9 |
| urbano | ×0.7 | ×1.5 | ×0.7 |
| montaña | ×0.4 | ×1.6 | ×0.75 |
| agua | intransitable | – | – |

- **Naval:** solo navega sobre agua; los terrestres y las bases no pueden estar en el agua.
- **Clima** (lo fija el instructor): lluvia y tormenta reducen la detección (×0.7 / ×0.5), la velocidad y
  la efectividad de los ataques aéreos.
- **Combustible y munición:** moverse gasta combustible según la distancia real (autonomía de la clase);
  atacar gasta munición (25 % terrestre, 34 % aérea, 20 % naval); con munición escasa el ataque pierde
  fuerza. Las bases reabastecen +50 % por turno a las unidades propias de su tipo dentro de su radio
  (siempre que conserven ≥ 25 % de fuerza). Una aeronave sin combustible lejos de una base aérea se pierde.
- **Cobertura aérea** (aeronave propia activa a ≤ 40 km): un blanco terrestre atacado desde el aire sin
  cobertura defiende ×0.7; un atacante terrestre con cobertura frente a uno sin ella ataca ×1.15.
- **Apoyo:** cada unidad que apoya (en su alcance) suma hasta +30 % (tope +60 %) al ataque y a la defensa
  de la apoyada ese turno; consume 10 % de munición.
- **Ingenieros** (orden `construir`): levantan un **vado** (cuesta 30 % de su material, dura 4 turnos, cruce a
  ×0.5) o un **puente** (60 %, 12 turnos, cruce a ×0.9) sobre un río, dentro de su alcance de trabajo (5 km).
  Sin obra, los vehículos pesados no cruzan ríos (los ligeros, a ×0.5). Las obras caducan solas, se ven en el
  mapa y el enemigo solo las conoce si están dentro de su radio de detección.
- **Transporte logístico:** convoyes terrestres que actúan como **nodo de reabastecimiento móvil**: dan +40 % de
  combustible y munición a las unidades propias en un radio de 3 km, gastando 15 puntos de su carga por unidad;
  recargan +50 por turno junto a una base o depósito. Son vulnerables a la emboscada (×1.5 si el atacante no
  fue detectado).
- **Fidelidad de plataformas:** el helicóptero artillado (montaje de 12,7 mm) rinde más fuego pero pesa más
  (penaliza la movilidad); la antiaérea portátil exige **desplegarse** (1 turno quieta), tiene alcance corto
  (5 km) y debe **recargar** 1 turno entre disparos; solo actúa contra blancos aéreos.
- **Resolución:** relación de fuerzas → pérdidas con una curva **continua** (interpolada en log₂ del ratio).
  Determinista por defecto; el **azar** opcional es reproducible (semilla del escenario + turno + unidades)
  y se informa en cada combate.

## Meteorología por zonas

Además del clima general del escenario, el instructor coloca **zonas meteorológicas** (*Consola → Meteorología por
zonas*): frentes de **nublado, lluvia o tormenta** con centro (clic en el mapa), radio (5–600 km), **deriva** (rumbo y
km/h: la zona se desplaza cada turno) y **duración** en turnos (o sin caducidad). El clima efectivo en cada punto es
el **peor** entre el general y las zonas que lo cubren, y con él se calculan la detección (en la posición del
blanco), la velocidad (en la posición de la unidad) y la efectividad de los ataques aéreos (sobre el blanco). Las
zonas las ven ambos bandos (capa *Meteorología*), con su flecha de deriva; la ficha de una unidad muestra su
«clima local» cuando difiere del general, y al disiparse una zona llega un aviso. API:
`GET/POST /api/escenarios/{id}/clima/zonas`, `DELETE …/zonas/{zid}`, `GET …/clima/en?lat=&lon=`. Motor:
`engine/clima.py` (`ClimaLocal`), migración 0014.

## Bases aéreas y aeródromos de los países vecinos

La capa de referencia (*Capas → Bases aéreas y aeródromos*) incluye, además de las 8 bases de la AMB, los aeródromos
de los vecinos que caen dentro del área del mapa, con el icono en el color de cada país: Colombia (Marandúa, Yopal,
Cúcuta, Arauca, Puerto Carreño, Riohacha, Valledupar), Brasil (Boa Vista), Guyana (Lethem) y Trinidad y Tobago
(Piarco). Se distingue **base aérea** de **aeropuerto** (uso civil, utilizable como base en el ejercicio); el
instructor los coloca como base azul o roja igual que los venezolanos, y todos tienen su **plano real** de
OpenStreetMap al acercarse (pistas, rodajes, plataformas, edificios). Lista en `tools/generar_bases_aereas.py`
(`VECINOS`) y `tools/preparar_aerodromos.py`; Georgetown queda fuera del área del mapa.

## Niebla de guerra

Cada unidad tiene un radio de detección (editable). Un bando ve las unidades enemigas dentro de ese radio,
reducido por el clima y, en objetivos terrestres/bases, por el terreno. De las enemigas solo se conoce
posición, clase y bando (fuerza, combustible y capacidades aparecen como "?"). Solo se puede atacar lo
detectado. Al perder de vista a una unidad enemiga se conserva su **último contacto** (dónde y en qué turno).
Órdenes y eventos también se filtran por bando; el instructor puede dirigir un evento a uno solo, y usar
"Ver como" para mostrar en clase lo que ve cada bando.

## Informe posterior al ejercicio (AAR)

Se guarda una instantánea completa al terminar cada turno, más cada combate con su ratio, terreno y efectos.
Botón **Informe**: repetición turno a turno sobre el mapa (trayectorias, combates, novedades), resumen por
bando, informe **imprimible** (HTML, sin JavaScript) y CSV de combates. Los ajustes manuales del instructor
quedan registrados. Los alumnos lo ven solo cuando el escenario está finalizado (muestra ambos bandos).

**Línea de tiempo (logística vs. combates).** Desde la repetición, el botón *Línea de tiempo* dibuja, por unidad,
el combustible y la munición turno a turno con marcas de **caída abrupta** (≥ 30 puntos en un turno), **nivel
crítico** (< 25 %) y reabastecimiento, cruzados con los combates y eventos; al elegir un suceso, la repetición
salta a ese turno y lugar. Los datos salen de `GET /api/escenarios/{id}/aar/timeline` (también incluidos en
la exportación JSON): series, eventos con su causa (movimiento, combate, apoyo, convoy, construcción…) y
correlaciones (`consumo_en_combate`, `coincide_con_combate`, `combate_con_logistica_baja`).

**Rúbrica de evaluación por bando y por puesto.** El botón *Rúbrica* de la repetición (y la sección
"Rubrica de evaluacion" del informe imprimible) resume, para cada bando: órdenes emitidas / resueltas /
rechazadas con los tres motivos de rechazo más frecuentes (agrupados sin cifras: "Objetivo fuera de alcance"),
**turnos pasivos** (turnos resueltos en los que el bando no emitió ninguna orden ni planificó misiones),
logística (unidades que llegaron a menos del 25 % de combustible o munición y reabastecimientos realizados),
pérdidas infligidas vs. sufridas y unidades destruidas, objetivos cumplidos / fallidos / pendientes, misiones
aéreas cumplidas / abortadas / fallidas, y una lista de **observaciones automáticas** en español (p. ej. "2
orden(es) rechazada(s) por 'Objetivo fuera de alcance': revisar la apreciacion de distancias antes de emitir
la orden."). El desglose por puesto (A2, A3, A4, A5) se deriva de la **función de cada orden** —el puesto
responsable según la unidad y el tipo de orden—, porque las órdenes no registran qué alumno las emitió.
Datos en `GET /api/escenarios/{id}/aar/rubrica` (mismos permisos que el informe) e incluidos en la
exportación JSON (`rubrica`).

## Aviación: F-16, Su-30 y bases aéreas de Venezuela

- **Modelos con foto** (`MODELOS` en `backend/app/engine/catalogo.py`): **F-16A/B Fighting Falcon** y
  **Su-30MK2 Flanker-G**, ambos de la Aviación Militar Bolivariana. Cada modelo trae su foto (con crédito y
  licencia visibles), velocidad, alcance de armas, detección, autonomía y efectividad contra aire/tierra/mar.
  El Su-30 tiene más autonomía, radar y capacidad antibuque; el F-16 es mejor en combate aéreo. Las cifras son
  parámetros de juego relativos entre modelos, no datos técnicos oficiales. Para agregar otro modelo: una
  entrada en `MODELOS` y su foto en `frontend/static/fotos/` (con su línea en `CREDITOS.md`).
- **Enviar un grupo de caza (alumnos):** en *Aviación* → *Enviar grupo de caza…* se abre un selector con las
  fotos y datos de cada modelo; se elige el número de aeronaves (1 a 8), un indicativo y la **base aérea propia**
  de origen. Es una orden `despegar` (una por base y turno): al resolverse el turno el grupo nace junto a la
  base, con combustible y munición llenos, y recibe órdenes desde el turno siguiente. Tope de 24 aeronaves por
  bando (activas más despegues pendientes). Una base muy dañada (< 25 %) no lanza grupos.
- **Grupos:** el tamaño del grupo multiplica su efectividad con la raíz de su tamaño (4 aeronaves = ×1,0;
  8 = ×1,41; 2 = ×0,71); al perder fuerza pierde aeronaves operativas. En el mapa se ve el símbolo APP-6 con
  «F-16 ×4»; al pasar el cursor, la foto; al seleccionarlo, la foto, el modelo y las aeronaves operativas.
  El enemigo detectado solo se conoce como «caza» (modelo y tamaño ocultos por la niebla de guerra).
- **Instructor:** en *Consola → Agregar unidad*, con clase *Caza*, *Elegir aeronave…* abre el mismo selector y
  ubica el grupo (con modelo y tamaño) directamente, sin pasar por el límite de despegues.
- **Bases aéreas de Venezuela:** capa de referencia (activable en *Capas*) con las 8 bases de la Aviación Militar
  Bolivariana y su código OACI: El Libertador (SVBL), Mariscal Sucre (SVBS), La Carlota (SVFM), Rafael Urdaneta
  (SVMC), Luis del Valle García (SVBC), Landaeta Gil (SVBM), Teófilo Luis Méndez (SVPR) y José Antonio Páez
  (SVPA). Al tocar una, se ve su nombre, ubicación y elevación; el instructor puede **colocarla como base azul o
  roja** del ejercicio con un botón. Datos en `frontend/static/geo/bases_aereas.geojson`
  (`python tools/generar_bases_aereas.py` lo regenera; fuentes: Wikipedia y OurAirports).
- **Ciclo de vuelo** (motor: `engine/aeronaves.py` y `engine/orders.py`):
  - **Aterrizar:** orden `aterrizar` hacia una base aérea propia en servicio y con plazas (caben 12 aeronaves por
    base). Si no llega en el turno, sigue volando hacia ella. Ya no basta pasar cerca de una base: **un avión solo se
    reabastece en tierra**.
  - **En tierra:** el grupo se estaciona junto a la base y tarda **2 turnos** en reabastecer y rearmar (+50 % de
    combustible y munición por turno). Hasta entonces rechaza órdenes de vuelo; después, cualquier orden de
    mover, atacar o patrullar es el despegue. Los aviones estacionados cuentan como blancos terrestres, no dan
    cobertura aérea y **sufren el 60 % del daño que recibe su base**.
  - **Patrullar:** misión persistente sobre un punto: la aeronave vuela hasta allí, se mantiene en la zona (8 % de
    combustible por turno) y **intercepta** al avión enemigo detectado más cercano dentro de su alcance (se
    registra como una orden de ataque «interceptar» y aparece en el informe).
  - **Combustible crítico:** una patrulla con ≤ 25 % deja la misión y se le ordena regresar a la base más cercana
    (orden de aterrizaje pendiente para el turno siguiente, con aviso). Sin combustible: aterrizaje de emergencia si
    hay una base al alcance, y si no, se pierde.
- **Miniaturas 3D en el mapa (todas las unidades):** cada unidad se dibuja con su miniatura en lugar del símbolo
  militar, orientada hacia donde va (su último desplazamiento o su orden pendiente) y más grande al acercar el mapa.
  F-16 y Su-30 son imágenes renderizadas de modelos 3D reales (24 rumbos; licencia Sketchfab Standard en
  `frontend/static/aeronaves/CREDITOS.md`, `tools/sprites3d/` las regenera; el «Su-30» usa un modelo de Su-33).
  El resto son miniaturas propias (`js/miniaturas.js`, sin archivos de terceros): helicópteros con su rotor, drones,
  avión de guerra electrónica, tanques, artillería autopropulsada, blindados 8x8, antiaérea, equipos de misiles
  portátiles, infantería, ingenieros, convoyes, radares, guerra electrónica, patrulleros, fragatas y las bases,
  depósitos y puertos. Las aeronaves llevan las derivas del color de su bando y una sombra; lo que está en tierra o
  en el agua, una **peana** del color de su bando. Un grupo aéreo se ve en formación (hasta 4). Un enemigo
  detectado se ve con la miniatura genérica de su clase (el modelo sigue oculto). En *Capas* → «Símbolos militares
  (APP-6) en lugar de miniaturas» se vuelve a la simbología (preferencia de cada puesto).
  `frontend/static/pruebas/miniaturas.html` muestra todas las miniaturas en cualquier rumbo.
- **Fotos:** de Wikimedia Commons, bajo CC BY-SA (créditos en `frontend/static/fotos/CREDITOS.md` y en la
  interfaz). Quien redistribuya el proyecto debe mantener esos créditos.

## Bases aéreas en detalle: plano real, estacionamiento y daños

Al acercar el mapa (zoom 11 en adelante; ahora llega hasta el 17) cada base aérea de Venezuela se dibuja con su
**plano real**, tomado de OpenStreetMap, en lugar de la imagen satelital, que a 10 m/píxel no muestra una pista:

- **Qué se ve:** el perímetro del aeródromo; las **pistas** con su largo, ancho y orientación reales, sus bordes,
  umbrales, eje, zona de toma de contacto y la **numeración de cada cabecera** (rumbo magnético); las **calles de
  rodaje** con su eje amarillo; las **plataformas**; los **helipuertos**; y los **hangares y edificios** con su
  sombra (según su altura). Lejos (zoom 11–13) un rótulo resume la base: «SVBL 10/28 · 3,8 km».
- **Bases incluidas:** El Libertador (SVBL), Mariscal Sucre (SVBS), La Carlota (SVFM), Rafael Urdaneta (SVMC),
  Luis del Valle García (SVBC), Landaeta Gil (SVBM), Teófilo Luis Méndez (SVPR), José Antonio Páez (SVPA) y Barinas
  (SVBI). El detalle depende de lo que esté cargado en OpenStreetMap: en algunas bases militares hay pocas
  construcciones mapeadas (p. ej. El Libertador solo tiene pista, rodajes y plataforma), y no se inventan.
- **La base del ejercicio sobre su plano:** una unidad `base_aerea` a menos de 4 km de un aeródromo lo «ocupa». Al
  acercarse, su miniatura se reduce a una ficha «BA» del color del bando para no tapar la pista, y sus **aeronaves
  estacionadas se dibujan repartidas sobre la plataforma real** (solo cambia el dibujo: el motor no cambia).
- **Daños a la vista:** con la base dañada aparecen **cráteres en la pista** (uno cada ~7 % de fuerza perdida,
  hasta 14, siempre en los mismos lugares); por debajo del 25 %, cuando la base ya no puede lanzar ni recibir
  aviones, se pintan las **cruces amarillas de pista cerrada** y el rótulo «PISTA INOPERATIVA». El bando enemigo no
  ve el daño de una base ajena (la niebla de guerra oculta su fuerza).
- **Capa:** *Capas* → «Plano de los aeródromos (pistas y hangares)». Con el plano a la vista, la capa de referencia
  de bases se atenúa para no duplicar rótulos (su popup para colocar la base sigue disponible).
- **Datos y licencia:** `frontend/static/geo/aerodromos.geojson` (~1,8 MB), generado una vez con internet por
  `python tools/preparar_aerodromos.py`. Consulta OpenStreetMap vía Overpass o, si no responde, con
  `--api` directamente la API de OSM por celdas pequeñas. La respuesta cruda queda en
  `tools/cache/osm_aerodromos.json` y se reprocesa sin internet. Datos © colaboradores de OpenStreetMap,
  **ODbL 1.0**: uso libre, también offline, citando la fuente; el crédito ya aparece en el mapa. Para agregar otra
  base, añádala a `BASES` en el script y vuelva a correrlo con `--descargar`.

## Daño por partes de la base y refugios reforzados

Una base aérea (o un portaaviones) tiene, además de su fuerza, tres partes con daño propio (0–100 %): **pista**,
**plataforma** y **depósito de combustible**. Al atacar una base se puede elegir la parte («Qué se ataca de la base»
en el panel de órdenes; las misiones y los misiles hacen ataque general):

- Un ataque dirigido aplica a esa parte 1,5 veces la pérdida de fuerza de la base; uno general, la mitad a cada parte.
- **Pista ≥ 60 %:** pista inoperativa: sin despegues ni aterrizajes (los grupos en vuelo se desvían a otra base),
  aunque la fuerza general sea alta. En el plano del aeródromo se pintan las cruces de pista cerrada.
- **Plataforma:** los aviones estacionados sufren más daño (hasta el doble) en cada ataque a la base.
- **Depósito:** las existencias máximas se reducen en proporción y el excedente se pierde.
- **Refugios reforzados** (`refugios`, 4 en cada base aérea nueva; el instructor los ajusta en *Ajuste manual*):
  protegen a los primeros N grupos estacionados, que reciben solo un cuarto del daño.
- **Reparación:** la pista recupera 8 % por turno con los medios de la base; con **ingenieros propios a ≤ 5 km**
  todas las partes recuperan 25 % más por turno. Llega un aviso cuando la pista queda inoperativa y cuando vuelve
  a operar. Motor: `engine/bases.py`; migración 0015.

## Guerra electrónica, radares y drones

Abstracción didáctica (no un modelo de propagación), en la línea de los conceptos de GE de los juegos de guerra
aérea: interferir cuesta quedar expuesto, y los drones dependen de su enlace.

**Unidades** (el instructor las ubica; drones y avión de GE también se envían desde las bases aéreas con
"✈ Enviar aeronaves o drones…", con **tope propio de 16 drones** que no descuenta del de 24 aeronaves tripuladas):

| Unidad | Qué aporta |
|---|---|
| Radar de vigilancia aérea | Ve aeronaves en vuelo hasta 150 km, pero lo que está en tierra solo a ~8 km. Emite: la escucha enemiga lo localiza |
| Guerra electrónica (terrestre) | **Escucha**: localiza radares, antiaérea guiada por radar e interferidores activos hasta 120 km. **Interfiere** 25 km a hasta 40 km de distancia |
| Avión de guerra electrónica | Interfiere 40 km a hasta 60 km, en vuelo (gasta combustible como en órbita); escucha hasta 200 km. Sin armas |
| Dron de reconocimiento | Detección 45 km, gran autonomía, sin armas; firma radar pequeña (se lo detecta a la mitad de distancia) |
| Dron armado | Misiles ligeros contra vehículos y buques; firma radar pequeña |
| Munición merodeadora (kamikaze) | Un solo ataque muy potente: se destruye al impactar |

**Orden "Interferir"** (unidades de GE; clic en el mapa en el centro de la zona): la zona rige durante la
resolución de ese turno y la planificación del siguiente; para sostenerla hay que volver a ordenarla. Dentro de
ella, contra el bando contrario: sus sensores detectan al **30 %** (radares al **20 %**; a ojo siempre 3 km), su
**antiaérea guiada por radar** pierde el **60 %** de efecto contra aeronaves (la portátil infrarroja no), y sus
**drones pierden el enlace** y no aceptan órdenes (siguen su patrulla o mantienen posición). **Interferir delata**:
el interferidor es visible para el enemigo mientras emite, y recibe un aviso con la zona. Las zonas se ven en el
mapa (capa "Guerra electrónica") y el detalle de una unidad afectada lo explica.

**Puestos**: los radares y la GE terrestre los conduce **A2 Inteligencia**; el avión de GE y los drones, como toda
aeronave, **A3 Operaciones**; el envío desde la base, **A5 Planificación**.

## Buques, portaaviones y misiles de crucero

- **Clases navales nuevas** (además de fragata y patrullero): **destructor** (radar de búsqueda aérea con control de
  emisiones y misiles antiaéreos: dispara solo contra aeronaves y misiles enemigos a su alcance, como la antiaérea),
  **portaaviones**, **submarino** (se lo detecta a un cuarto de la distancia; solo ataca buques) y **buque de
  desembarco**. En tierra, el **lanzador de misiles de crucero** (batería costera, debe desplegarse un turno).
- **Portaaviones = base aérea móvil:** lanza y recibe aeronaves como una base (*Aviación → Enviar aeronaves*,
  orden `aterrizar`, misiones aéreas), con **10 plazas** y sus propias existencias (1500), que **repone junto a un
  puerto propio** (100 puntos por turno). Solo operan desde él las aeronaves **embarcables**: helicópteros, drones,
  munición merodeadora y el modelo **Caza embarcado**; el F-16, el Su-30, el avión de ataque ligero y el de guerra
  electrónica solo desde bases terrestres. Las aeronaves a bordo navegan con él, sufren parte del daño que recibe
  y se hunden si lo hunden. Armas propias débiles: necesita escolta.
- **Modelos genéricos nuevos** (ilustraciones propias generadas de sus miniaturas 3D, CC0): Caza embarcado,
  Helicóptero de ataque, Helicóptero de transporte artillado, Avión de ataque ligero y Misil de crucero. Con ellos
  los helicópteros y los aviones de ataque también pueden despegar de una base.
- **Misiles de crucero (orden `lanzar`):** fragatas, destructores, submarinos y baterías costeras lanzan salvas de
  **1 a 4 misiles** (25 % de munición cada uno) contra una unidad enemiga detectada en tierra o en el mar a menos
  de 1 000 km. Al resolverse el turno la salva nace sobre el lanzador y **vuela sola** (850 km/h) hacia la posición
  actual del blanco: si lo alcanza, impacta (un solo ataque, se consume; rinde como un grupo aéreo); si el blanco
  desapareció, va al último punto conocido y se pierde; sin alcance, cae. No admite órdenes, no aterriza ni cuenta
  para los topes de aeronaves. **Intercepción antes del impacto:** la antiaérea automática, los destructores y
  las patrullas enemigas disparan contra la salva en ese mismo turno y sus pérdidas se descuentan **antes** de que
  impacte; si la derriban, no impacta («Derribado antes del impacto», con aviso al lanzador). Lo mismo vale ahora
  para la munición merodeadora. La orden la conduce el puesto de superficie (A5) o el Estado Mayor.
- En el mapa, cada buque y el misil tienen su miniatura; el detalle de un lanzador muestra los misiles listos y el
  de un portaaviones, las aeronaves a bordo. Motor: `engine/misiles.py`, `engine/aeronaves.py`, `engine/orders.py`;
  migración 0013 (`blanco_id`).

## Unidades anfibias y helitransportadas

- **Embarcar** (orden `embarcar`, unidad terrestre → transporte propio a ≤ 3 km): el **buque de desembarco** lleva
  hasta 3 unidades terrestres de cualquier movilidad; el **helicóptero de transporte artillado**, 1 unidad ligera
  (infantería, antiaérea portátil, ingenieros, reconocimiento). A bordo la unidad viaja con el transporte, **no se
  la detecta ni se la ataca por separado**, no recibe órdenes y sufre la mitad del daño que reciba el transporte
  (se pierde si lo hunden o derriban). En el orden de batalla figura «A bordo».
- **Desembarcar** (orden `desembarcar` del transporte: ruta + último punto = lugar de desembarco, en tierra firme):
  el buque se acerca por el agua y, a ≤ 5 km del punto, deja allí a las unidades (con su tiempo de despliegue); el
  helicóptero vuela hasta el punto. Si no llega en el turno, sigue en los siguientes con la misma orden. Motor:
  `engine/transporte.py`; migración 0016 (`transporte_id`).

## Radares, defensa antiaérea y logística de base

- **Control de emisiones:** radares y antiaérea guiada por radar se encienden o apagan desde el detalle de la unidad
  (rige de inmediato). Apagado, el radar solo ve a ojo (5 km), pero la escucha enemiga ya no lo localiza y la SEAD
  no lo elige como blanco: encender es ver y ser visto. Los radares los conduce A2; la antiaérea, A5.
- **Antiaérea automática:** cada pieza con el **fuego libre** dispara sola, cada turno, contra la aeronave enemiga
  en vuelo más cercana a su alcance que su bando detecte (aparece como "defensa aérea" en la cola de órdenes). La
  guiada por radar necesita el radar encendido; con el radar apagado solo tira **por orden y a ojo** (×0,3). La
  portátil infrarroja no necesita radar, pero sí estar desplegada. Se puede **retener el fuego** para no delatarse.
- **Existencias de las bases:** cada base guarda combustible y munición (100 puntos = llenar una unidad; bases
  aéreas y puertos hasta 2000, depósitos hasta 3000). El reabastecimiento (+50 % por turno) sale de ahí; cada
  aeronave que despega consume 25 de cada uno y, sin existencias, la base no lanza el grupo (**sin logística**).
  Los **depósitos reponen 150** por turno; los **convoyes** se recargan en los depósitos y **descargan en las bases
  aéreas y puertos** a su lado (25 de carga por turno = 50 de cada existencia). Cuando una base se queda sin
  combustible o munición, el bando recibe un aviso. El enemigo no ve las existencias ni el estado de los radares;
  el instructor las ajusta desde "Ajuste manual".

## Misiones aéreas: roles, navegación y cronograma

Además de las órdenes turno a turno, un grupo aéreo puede recibir una **misión**: un **rol** y una **ruta** que
el motor ejecuta solo, turno tras turno ("✈ Planificar misión…" en el panel *Misiones aéreas*).

- **Quién vuela:** un grupo que ya existe (lo decide **A3 Operaciones**) o un grupo que **despegará de una base
  en un turno programado**, hasta 24 turnos después (lo decide **A5 Planificación**): así se arma con anticipación
  el plan aéreo del día. Los despegues programados cuentan para el tope de aeronaves/drones del bando.
- **Ruta:** clic en el mapa para cada punto y elegir su tipo: **paso** (se sobrevuela), **órbita** (se mantiene
  N turnos, sin contar el de llegada) o **blanco** (clic sobre el símbolo enemigo, o "el enemigo detectado más
  cercano"); termina con el **aterrizaje** en una base propia (la munición merodeadora termina en el blanco).
- **Roles:** CAP (en la órbita intercepta aviones enemigos), interdicción (ataca el blanco; si se movió y se lo
  sigue viendo, lo persigue), CAS (en la órbita ataca cada turno al enemigo de superficie más cercano), SEAD
  (prioriza radares y antiaérea), reconocimiento (no ataca), guerra electrónica (interfiere desde la órbita) y
  traslado a otra base. Cada rol exige la capacidad adecuada (no se puede hacer CAP con un dron de reconocimiento).
- **Estimación:** mientras se traza la ruta, el servidor calcula la **hora de llegada y el combustible en cada
  punto** con las mismas reglas con que después resuelve los turnos, y avisa si no alcanza el combustible.
- **Durante la ejecución:** una orden directa al grupo reemplaza la misión (redireccionamiento); con combustible
  crítico abandona la ruta y regresa a la base más cercana; si la base de aterrizaje está fuera de servicio se
  desvía a otra; los drones sin enlace (interferencia) mantienen posición. Cancelar una misión programada la
  anula; abortar una en curso hace regresar al grupo.
- **Escolta y paquetes de ataque:** el rol **ESCOLTA** acompaña a otra misión propia («Misión que escolta»): vuela
  junto a su grupo (a ≤ 8 km), lo espera en el aire si aún no despegó, **intercepta** a los aviones enemigos que lo
  amenacen (actúa como una patrulla que se mueve con el grupo) y, cuando esa misión termina, regresa a la base
  indicada. Al planificar una interdicción, CAS, SEAD, reconocimiento o GE se puede agregar la **escolta del
  paquete** en la misma pantalla: un grupo de caza ya en vuelo o un par de cazas que despegan de la misma base en
  el mismo turno; el servidor crea las dos misiones juntas (`escolta` en `POST /misiones`; la escolta guarda
  `escolta_de`). Una escolta no escolta a otra escolta.
- **Cronograma (flow sheet):** botón *Cronograma*: una fila por misión con vuelo, órbitas, ataques y aterrizajes
  sobre la línea de tiempo, y el turno actual marcado. Cada bando ve solo sus misiones; el instructor, todas.

## Ejercicios con o contra los países vecinos

- **Identidad nacional** (*Consola → Identidad nacional*; catálogo en `engine/naciones.py`, endpoint
  `GET /api/naciones`): a cada bando (azul/rojo) se le puede asignar un país — Venezuela, Colombia, Brasil,
  Guyana o Trinidad y Tobago — o dejarlo sin especificar. Es solo un nombre para la interfaz (cabecera, orden
  de batalla, pie, HUD del videowall, informe y exportación): el bando "azul"/"rojo" sigue siendo el mecanismo
  real del motor (símbolos, niebla de guerra, combate), y el catálogo de unidades no cambia según el país — el
  simulador no modela el orden de batalla real de cada vecino. No hace falta que Venezuela participe: los dos
  bandos pueden representar al mismo país o a dos vecinos distintos, según lo que se quiera ensayar. La
  identidad nacional no es secreta: la ven ambos bandos (a diferencia de la configuración de comunicaciones).
- **Terreno de referencia de los vecinos:** las fronteras, los departamentos/estados y las ciudades principales
  de Colombia, Brasil, Guyana y Trinidad y Tobago que entran en el área del mapa ya están en las capas
  `fronteras.geojson`, `estados.geojson` y `lugares.geojson` (recortadas a esa área, no el contorno completo de
  cada país) — se ven igual que las de Venezuela, sin activar nada aparte. El relieve y la cobertura terrestre
  (montaña, bosque, río, urbano…) ya cubrían esa misma zona porque se generaron por coordenadas, no por país.
  `python tools/preparar_terreno.py --solo-vectores` regenera solo estas capas (rápido, sin tocar el relieve).
- **Límite:** no hay bases ni unidades reales de esos países cargadas de fábrica (a diferencia de las bases
  aéreas venezolanas, verificadas una por una); el instructor las ubica como cualquier otra unidad o base.

## Fondo del mapa: satélite real o relieve

- **Vista satelital** (por defecto): foto real, no un relieve coloreado por clase de terreno. Es la capa
  **"Sentinel-2 cloudless"** de EOX (https://cloudless.eox.at), un mosaico global sin nubes hecho con
  imágenes Copernicus Sentinel-2 (ESA) — la misma fuente en la que ya se basa la cobertura terrestre
  (ESA WorldCover). Licencia **CC BY 4.0** (libre, con atribución, que ya está en el control del mapa).
  Resolución real ~10 m/píxel: se generó hasta el zoom 12, que es donde deja de haber información nueva (más
  allá el propio servicio solo interpola). En *Capas* hay un botón **Satélite / Relieve** para alternar; el
  relieve (el de siempre, con el terreno coloreado por clase) sigue disponible porque distingue mejor a
  simple vista el bosque, el pantano o la montaña.
- **Más zoom:** antes el mapa llegaba como máximo a la tesela nativa de zoom 9 (con estiramiento hasta 11).
  Ahora el zoom máximo es 15, con detalle real de satélite hasta el 12 (calles y manzanas se distinguen en
  zonas urbanas); no llega al detalle de edificio/vehículo individual de Google Maps, porque esa resolución
  no existe como dato abierto y gratuito para toda el área del ejercicio.
- **Cómo se generó:** `python tools/preparar_satelite.py` (independiente de `preparar_terreno.py`: no toca el
  relieve, la cobertura ni la grilla que usa el motor, solo agrega la imagen de fondo alternativa). Es
  reanudable y admite `--hasta-zoom` para llegar más lejos más adelante (13 agrega ~88 000 teselas más).
  Créditos y licencia completos en `frontend/static/tiles_sat/CREDITOS.md`.
- **Tamaño:** esta capa pesa varios cientos de MB (bastante más que el resto del proyecto), porque es imagen
  real a buena resolución para toda el área del mapa, no datos vectoriales livianos.

## Escenarios precargados (plantillas)

- **Qué son:** en lugar de armar un escenario unidad por unidad, *Nuevo escenario* → **Desde plantilla…**
  (cabecera, junto a "Nuevo"; solo el instructor) crea uno nuevo (no reemplaza ninguno) con las unidades, los
  objetivos, el clima y la identidad nacional ya definidos. También por línea de comandos:
  `python -m app.crear_demo <id>` (sin argumento usa `demo_llanos`) y por la API (`GET /api/plantillas`,
  `POST /api/plantillas/{id}`). Las plantillas están declaradas en `backend/app/engine/plantillas.py`.
- **`demo_llanos`:** el escenario de práctica genérico de siempre (sin cambios).
- **`defensa_3_enero_2026`** — *"3 de enero de 2026 (estudio): defensa del litoral central"*: para practicar la
  defensa aérea y naval del litoral central en las horas previas a un ataque como el ocurrido la madrugada del
  3 de enero de 2026, cuando fuerzas de EE. UU. bombardearon instalaciones militares en Caracas y Vargas
  ("Operación Resolución Absoluta"). Bando azul = Venezuela, con unidades en las ubicaciones reales de La
  Carlota, Fuerte Tiuna, el puerto de La Guaira y Charallave; bando rojo = una fuerza expedicionaria genérica
  (sin modelo de aeronave específico, porque no se pretende representar los F-22/F-35/B-1B reales). Objetivos
  de "proteger" para azul y de "destruir" para rojo, emparejados en esas cuatro instalaciones.
  **Es una simplificación para el ejercicio, no una reconstrucción histórica**: la composición y el número de
  fuerzas de ambos bandos son ficticios, las cifras de bajas varían según la fuente, y el desenlace político
  real (la captura del jefe de Estado) queda fuera del alcance de este ejercicio táctico. Antes de usarla en
  clase, ajuste las unidades y objetivos con lo que la institución considere pedagógicamente apropiado.
- Para agregar una plantilla propia: una entrada más en `PLANTILLAS` (`engine/plantillas.py`), con sus
  `UnidadPlantilla` y, si aplica, `ObjetivoPlantilla`; no hace falta tocar la base de datos ni el resto del código.

### Guardar el escenario actual como plantilla

Desde la cabecera, **Guardar como plantilla…** (solo el instructor) toma el escenario elegido **tal como está
ahora** —posiciones actuales de las unidades (sin las destruidas), objetivos, clima e identidad nacional— y lo
guarda como una plantilla más, con nombre y descripción. La casilla *Conservar la fuerza, el combustible, la
munición y las existencias actuales* decide si las unidades arrancan al 100 % (por defecto) o con su estado
del momento; las aeronaves estacionadas conservan su base. La plantilla aparece de inmediato en «Desde
plantilla…» (marcada como *Guardada por un instructor*), se instancia igual que las del código y se puede
**Eliminar** desde esa misma lista (las del sistema no).

- Se guarda como un archivo JSON por plantilla en `backend/data/plantillas_usuario/<id>.json` (sin tocar la
  base de datos; la variable `SIMULADOR_PLANTILLAS_USUARIO` cambia la carpeta). El `id` sale del nombre
  (minúsculas sin acentos, `a-z0-9-`, máximo 60 caracteres); un archivo corrupto se omite con un aviso en el
  registro del servidor.
- API: `POST /api/escenarios/{id}/guardar_plantilla` con `{nombre, descripcion, con_estado, reemplazar}`
  (400 si el nombre no sirve o coincide con una plantilla del sistema; 409 si ya existe y no se pide
  reemplazar), `GET /api/plantillas` (cada entrada trae `origen: "codigo" | "usuario"`),
  `POST /api/plantillas/{id}` y `DELETE /api/plantillas/{id}` (solo las de usuario). También sirven en la
  consola: `python -m app.crear_demo <id>`.

## Objetivos, puntaje y editor del escenario

- **Objetivos** (*Consola → Objetivos y puntaje*; motor en `engine/objetivos.py`), cada uno para un bando y con
  sus puntos; cada bando solo ve los suyos:
  - **Ocupar** una zona circular: al menos una unidad terrestre propia dentro y ninguna enemiga, durante N turnos
    seguidos (si la pierde, el conteo vuelve a cero).
  - **Destruir** una unidad del bando contrario.
  - **Proteger** una unidad propia: falla si cae; se cumple al llegar al turno indicado con la unidad viva.
- **Marcador:** puntos de los objetivos cumplidos más 1 punto por cada 10 de fuerza que el bando inflige al enemigo
  (atacando o defendiendo). Se muestra en la tarjeta «Objetivos y puntaje», en el HUD del videowall, en el informe
  (`marcador` y `objetivos` en `/aar` y en la exportación) y llega como aviso a cada bando al cumplirse o fallar.
  Las zonas y las unidades objetivo se dibujan en el mapa (capa «Objetivos»).
- **Editor:** *Consola → Editar el escenario* permite arrastrar las unidades para reubicarlas (queda como ajuste
  manual) y, desde la ficha de una unidad, **eliminarla**. Una unidad que ya combatió no se puede borrar sin falsear
  el informe (`409`): hay que marcarla como destruida. «Duplicar escenario» copia también los objetivos, y los modelos
  y grupos de aeronave.
- **Selección múltiple y formaciones:** Ctrl+clic (o Shift+clic) en el orden de batalla o en el mapa suma o quita
  unidades propias a la selección; el panel de órdenes indica «N unidades seleccionadas» y la orden se emite a todas
  (`POST /api/escenarios/{id}/ordenes/lote`: resultado por unidad; las que fallan no impiden a las demás). Con
  **Mantener la formación**, al mover (o desembarcar) cada unidad recibe los waypoints desplazados según su posición
  relativa a la primera, así el conjunto conserva su formación; sin ella, todas van al mismo punto.
- **Herramientas de mapa:** **Regla** (clic para cada punto, doble clic o `Esc` para terminar: distancia y rumbo de
  cada tramo y total), anillos de alcance, detección y avance de la unidad seleccionada, y **búsqueda** de unidades
  por nombre, clase o modelo (sin acentos) sobre la orden de batalla.
- **Pantallas estrechas** (< 760 px): el panel derecho (estado, objetivos, chat, alertas) y la barra de dibujo pasan
  a paneles que se abren con los botones «Panel» y «Dibujar» sobre el mapa.

## Trabajo en equipo: gráficos, comunicaciones y videowall

- **Gráficos de control:** barra *Gráficos tácticos* (Leaflet.draw) para trazar líneas de fase, ejes de avance,
  zonas de reunión y puntos de control. Se guardan como GeoJSON y se difunden por WebSocket a todo el bando
  (o a todos, si los traza el instructor); cada bando solo ve los suyos. Capa desactivable en *Capas*.
- **Comunicaciones simuladas:** chat sobre el mismo WebSocket (red del bando o "al mando"; el instructor
  escribe a un bando o a todos). Un **interceptor** en el servidor aplica, por bando destinatario, **latencia**,
  **jitter** y **probabilidad de pérdida** que fija el instructor en *Consola*; el instructor ve en cada mensaje
  qué le pasó en cada bando (`[azul: +1.8 s] [rojo: perdido]`). Límite de 6 mensajes/10 s y 500 caracteres.
- **Centro de operaciones (videowall):** botón *Videowall* del instructor, tecla `V` o URL
  `?modo=videowall&escenario=ID&vista=azul|rojo|completa`. Los paneles colapsan por completo, el mapa ocupa el
  100 % de la pantalla (pantalla completa; se adapta a varias pantallas o cambios de tamaño) y un HUD muestra
  turno, hora, reloj, estado de los bandos y las últimas alertas. `Esc` sale.

## Administración

- **Escenario:** archivar/desarchivar, duplicar (copia el despliegue inicial con toda la fuerza y logística),
  exportar JSON (definición + informe) y asignar usuarios.
- **Respaldos:** `python -m app.respaldo` (o automáticos, `SIMULADOR_RESPALDO_HORAS`, 0 los desactiva) en
  `backend/respaldos/`, conservando las 14 últimas. Restaurar = detener el servidor y copiar una sobre
  `backend/simulador_fenix.db`.
- **Migraciones:** `backend/migrations/` (Alembic); una base anterior a las migraciones se adopta sola.
  Una prueba comprueba que los modelos y las migraciones no divergen.

### Ajustar los valores de juego

Los valores del catálogo (velocidades, alcances, detección, autonomía, defensa, efectividad por tipo de
objetivo, existencias de las bases, firma, radios de escucha e interferencia, cadencia, munición por ataque,
turnos de despliegue y recarga, plazas de aeronaves) y los topes de aeronaves se pueden cambiar **sin tocar el
código** con el archivo opcional `backend/data/ajustes_catalogo.json`. Copie
`backend/data/ajustes_catalogo.ejemplo.json` con ese nombre, deje solo lo que quiera cambiar y reinicie el
servidor. Formato:

```json
{
  "clases":  {"caza": {"velocidad_kmh": 950, "ataque_vs": {"aerea": 1.4}}, "base_aerea": {"plazas_aeronaves": 16}},
  "modelos": {"f16": {"alcance_km": 90}},
  "topes":   {"MAX_AERONAVES_BANDO": 32}
}
```

- `clases`: por id de clase (`infanteria`, `blindado`, `caza`, `fragata`, `base_aerea`…; ver `catalogo.py`).
  Campos: `velocidad_kmh`, `alcance_km`, `deteccion_km`, `autonomia_km`, `defensa`, `ataque_vs`, `stock_max`,
  `reposicion_turno`, `firma`, `escucha_km`, `interferencia_km`, `cadencia_fuego`, `municion_por_ataque`,
  `despliegue_turnos`, `recarga_turnos`, `plazas_aeronaves`.
- `modelos`: por id de modelo (`f16`, `su30`, `uav_reco`…). Campos: `velocidad_kmh`, `alcance_km`,
  `deteccion_km`, `autonomia_km`, `defensa`, `ataque_vs`.
- `ataque_vs` se fusiona clave a clave (`terrestre`, `aerea`, `naval`): lo que no se indica se conserva.
- `topes`: `MAX_AERONAVES_GRUPO`, `MAX_AERONAVES_BANDO`, `MAX_DRONES_BANDO` (enteros ≥ 1).
- Las claves que empiezan por `_` (p. ej. `"_comentario"`) se ignoran. Ids o campos desconocidos y valores de
  tipo incorrecto (texto, negativos, decimales en un entero) se registran como aviso en el log del servidor y
  se ignoran; el resto se aplica. Si el archivo no existe, no cambia nada.
- La variable de entorno `SIMULADOR_AJUSTES_CATALOGO` apunta a otro archivo. Los cambios se ven en
  `GET /api/catalogo` tras reiniciar el servidor. Ojo: cada unidad copia `velocidad_kmh`, `alcance_km`,
  `deteccion_km` y `autonomia_km` de su clase **al crearse**, así que esos cuatro solo afectan a las unidades
  nuevas (las existentes se editan desde la ficha de la unidad); el resto (`ataque_vs`, `defensa`, existencias,
  firma, cadencia, despliegue, recarga, plazas, topes) se consulta en cada resolución y afecta también a los
  escenarios ya creados.

## Datos de terreno (offline)

`tools/preparar_terreno.py` se ejecutó una vez con internet (el resultado ya está en el repositorio):

- `frontend/static/tiles/` – mapa z5–z9 (relieve + clases de terreno).
- `frontend/static/geo/` – fronteras, estados, ríos, lagos y poblaciones.
- `backend/data/terreno/` – grilla de clases que usa el motor.

Fuentes: elevación de *AWS Terrain Tiles* (SRTM/GMTED/ETOPO1 vía Mapzen), cobertura terrestre de
*ESA WorldCover 2021* (10 m, CC BY 4.0) y *Natural Earth* (dominio público). Montaña sale del relieve y la
pendiente; bosque, pantano y urbano, de WorldCover (más un radio alrededor de las ciudades); agua, del nivel
del mar, los lagos de Natural Earth y los cuerpos grandes de WorldCover (se descartan los ríos angostos para
que las unidades puedan cruzarlos; los tramos muy anchos del Orinoco sí son obstáculo). Resolución ≈ 300 m.
Para regenerar: `pip install -r tools/requirements.txt` y `python tools/preparar_terreno.py`
(`tools/cache/` guarda las descargas, unos cientos de MB, y puede borrarse).

## Maqueta de interfaz (C4ISR)

`frontend/static/maqueta/index.html` es una maqueta estática del diseño "Simulador Fénix" (cabecera con turno,
hora y cuenta regresiva; orden de batalla, unidad seleccionada y cola de órdenes a la izquierda; mapa táctico
con simbología, rutas, waypoints y vectores de ataque; entorno, capas y alertas a la derecha; botón
"Estoy listo" abajo). Es HTML/CSS/JS puro con datos de ejemplo, sin servidor ni internet: se puede abrir
con doble clic (`file://`) o en `http://<servidor>:8000/static/maqueta/index.html`. Usa el relieve offline
del proyecto centrado en La Guaira/Caracas.

## Limitaciones conocidas

- El modelo de combate es una abstracción didáctica, no una simulación física; los valores del catálogo
  y de la tabla de pérdidas son ajustables en `engine/`.
- El terreno no distingue cultivos, cárcavas ni carreteras; los ríos se detectan en la grilla (~300 m) y
  los puentes que existen en la realidad no están cargados (solo los que construyen los ingenieros).
- No hay unidades anfibias/aerotransportadas; el transporte logístico es terrestre.
- Los modelos de aeronave son solo F-16 y Su-30; los aviones no gastan inventario de las bases (solo hay un tope
  por bando) y el estado real de cada aparato en la flota venezolana no se modela.
- Las comunicaciones simuladas solo afectan al chat, no a las órdenes ni a la niebla de guerra.
- No hay selección múltiple de unidades ni órdenes de grupo: cada orden se da a una unidad.
- La identidad nacional es solo un nombre para la interfaz: no se modela el orden de batalla real de Colombia, Brasil, Guyana ni Trinidad y Tobago, y el terreno detallado de esos países se limita a lo que entra en el área del mapa (recortado alrededor de Venezuela).
- El bloqueo de inicio de sesión es por usuario (un atacante puede bloquear una cuenta 5 min).
- Un solo servidor: WebSocket y temporizador viven en el proceso.
