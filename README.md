# Simulador de Conducción Militar (estilo "Fénix")

Wargame web multiusuario para adiestramiento en conducción (operaciones terrestres, aéreas y navales)
sobre el terreno de Venezuela. Instructor/director de ejercicio + alumnos por bando (azul/rojo),
sincronizados por WebSocket. **Funciona sin internet**: mapa, relieve, cobertura terrestre, librerías
y datos se sirven desde el propio servidor (una política CSP bloquea cualquier recurso externo).

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
- **Fotos:** de Wikimedia Commons, bajo CC BY-SA (créditos en `frontend/static/fotos/CREDITOS.md` y en la
  interfaz). Quien redistribuya el proyecto debe mantener esos créditos.

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
- El bloqueo de inicio de sesión es por usuario (un atacante puede bloquear una cuenta 5 min).
- Un solo servidor: WebSocket y temporizador viven en el proceso.
