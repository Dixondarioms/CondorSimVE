/* ARNES DE PRUEBAS VISUALES: servidor simulado en el navegador (fetch y WebSocket falsos).
 * Se carga ANTES de app.js, que corre sin cambios. Los datos no son reales. */
(() => {
  "use strict";
  const REAL_FETCH = window.fetch.bind(window);
  // el mapa queda accesible (window.__mapa) para revisar zoom y capas desde las pruebas
  if (window.L) L.Map.addInitHook(function () { window.__mapa = this; });
  const params = new URLSearchParams(location.search);
  const ROL = ["instructor", "azul", "rojo", "observador"].includes(params.get("rol")) ? params.get("rol") : "instructor";
  const USUARIOS = { instructor: [1, "prof"], azul: [2, "alfa"], rojo: [3, "bravo"], observador: [4, "obs"] };
  const PUESTO = ["mando", "inteligencia", "operaciones", "logistica", "planificacion"].includes(params.get("puesto")) ? params.get("puesto") : "mando";
  const YO = { id: USUARIOS[ROL][0], username: USUARIOS[ROL][1], rol: ROL, puesto: PUESTO, activo: true };
  const iso = (ms = 0) => new Date(Date.now() + ms).toISOString().slice(0, 19);
  const BANDOS = ["azul", "rojo"];

  let CAT = null;
  const cargaCatalogo = REAL_FETCH("/static/pruebas/catalogo.json").then((r) => r.json()).then((c) => { CAT = c; });

  // ------------------------------------------------------------------ datos de ejemplo
  const ESC = {
    id: 1, nombre: "Ejercicio de ejemplo: piedemonte andino", turno_actual: 3, fase: "decision", estado: "activo", clima: "lluvia",
    azar: true, auto_resolver: false, limite_decision_seg: 1200, decision_termina_en: iso(18 * 60000 + 32000),
    listo_azul: false, listo_rojo: true, archivado: false, hora_inicio_min: 360,
    com_latencia_ms: 1500, com_jitter_ms: 500, com_perdida_pct: 30,
    nacion_azul: "venezuela", nacion_rojo: "colombia",
    niebla: true, logistica: true, efectos_clima: true, fuego_automatico: true,
    ia_azul: params.get("ia") === "azul", ia_rojo: params.get("ia") === "rojo",
    ia_nivel: ["prudente", "normal", "agresiva"].includes(params.get("nivel")) ? params.get("nivel") : "normal",
    dia_noche: params.get("noche") === "1",
  };
  if (params.get("hora")) ESC.hora_inicio_min = parseInt(params.get("hora"), 10) || 360;
  // periodo del dia del turno en curso (mismo criterio que backend/app/engine/clima.py, periodo_del_dia)
  Object.defineProperty(ESC, "periodo", {
    enumerable: true,
    get() {
      if (!ESC.dia_noche) return "dia";
      const hora = Math.floor((((ESC.hora_inicio_min || 0) + Math.max(0, ESC.turno_actual - 1) * 60) % 1440) / 60);
      return hora >= 7 && hora < 18 ? "dia" : hora === 6 || hora === 18 ? "crepusculo" : "noche";
    },
  });
  // informes inyectados con posicion (direccion del ejercicio)
  const INFORMES = [{ id: 501, turno: 2, tipo: "inteligencia", descripcion: "Fuentes locales reportan una columna blindada moviéndose al sur del río.", lat: 8.70, lon: -70.58, hasta_turno: 5, fuente: "Inteligencia" }];
  // mismo catalogo que backend/app/engine/naciones.py (Venezuela primero, el resto alfabetico)
  const NACIONES = [
    { id: "venezuela", nombre: "Venezuela", gentilicio: "venezolano", capital: "Caracas", colores: ["#FFCC00", "#00247D", "#CF142B"], iso: "VE" },
    { id: "argentina", nombre: "Argentina", gentilicio: "argentino", capital: "Buenos Aires", colores: ["#74ACDF", "#FFFFFF", "#F6B40E"], iso: "AR" },
    { id: "bahamas", nombre: "Bahamas", gentilicio: "bahameño", capital: "Nasáu", colores: ["#00778B", "#FFC72C", "#000000"], iso: "BS" },
    { id: "barbados", nombre: "Barbados", gentilicio: "barbadense", capital: "Bridgetown", colores: ["#00267F", "#FFC726", "#000000"], iso: "BB" },
    { id: "belice", nombre: "Belice", gentilicio: "beliceño", capital: "Belmopán", colores: ["#003F87", "#FFFFFF", "#CE1126"], iso: "BZ" },
    { id: "bolivia", nombre: "Bolivia", gentilicio: "boliviano", capital: "Sucre (sede de gobierno: La Paz)", colores: ["#D52B1E", "#F9E300", "#007934"], iso: "BO" },
    { id: "brasil", nombre: "Brasil", gentilicio: "brasileño", capital: "Brasilia", colores: ["#009C3B", "#FFDF00", "#002776"], iso: "BR" },
    { id: "canada", nombre: "Canadá", gentilicio: "canadiense", capital: "Ottawa", colores: ["#FF0000", "#FFFFFF"], iso: "CA" },
    { id: "chile", nombre: "Chile", gentilicio: "chileno", capital: "Santiago", colores: ["#FFFFFF", "#0039A6", "#D52B1E"], iso: "CL" },
    { id: "colombia", nombre: "Colombia", gentilicio: "colombiano", capital: "Bogotá", colores: ["#FCD116", "#003893", "#CE1126"], iso: "CO" },
    { id: "costa_rica", nombre: "Costa Rica", gentilicio: "costarricense", capital: "San José", colores: ["#002B7F", "#FFFFFF", "#CE1126"], iso: "CR" },
    { id: "cuba", nombre: "Cuba", gentilicio: "cubano", capital: "La Habana", colores: ["#002A8F", "#FFFFFF", "#CB1515"], iso: "CU" },
    { id: "ecuador", nombre: "Ecuador", gentilicio: "ecuatoriano", capital: "Quito", colores: ["#FFDD00", "#034EA2", "#ED1C24"], iso: "EC" },
    { id: "el_salvador", nombre: "El Salvador", gentilicio: "salvadoreño", capital: "San Salvador", colores: ["#0F47AF", "#FFFFFF"], iso: "SV" },
    { id: "estados_unidos", nombre: "Estados Unidos", gentilicio: "estadounidense", capital: "Washington D. C.", colores: ["#B22234", "#FFFFFF", "#3C3B6E"], iso: "US" },
    { id: "guatemala", nombre: "Guatemala", gentilicio: "guatemalteco", capital: "Ciudad de Guatemala", colores: ["#4997D0", "#FFFFFF"], iso: "GT" },
    { id: "guyana", nombre: "Guyana", gentilicio: "guyanés", capital: "Georgetown", colores: ["#009E49", "#FCD116", "#CE1126"], iso: "GY" },
    { id: "haiti", nombre: "Haití", gentilicio: "haitiano", capital: "Puerto Príncipe", colores: ["#00209F", "#D21034"], iso: "HT" },
    { id: "honduras", nombre: "Honduras", gentilicio: "hondureño", capital: "Tegucigalpa", colores: ["#00BCE4", "#FFFFFF"], iso: "HN" },
    { id: "jamaica", nombre: "Jamaica", gentilicio: "jamaiquino", capital: "Kingston", colores: ["#009B3A", "#FED100", "#000000"], iso: "JM" },
    { id: "mexico", nombre: "México", gentilicio: "mexicano", capital: "Ciudad de México", colores: ["#006847", "#FFFFFF", "#CE1126"], iso: "MX" },
    { id: "nicaragua", nombre: "Nicaragua", gentilicio: "nicaragüense", capital: "Managua", colores: ["#0067C6", "#FFFFFF"], iso: "NI" },
    { id: "panama", nombre: "Panamá", gentilicio: "panameño", capital: "Ciudad de Panamá", colores: ["#FFFFFF", "#005293", "#D21034"], iso: "PA" },
    { id: "paraguay", nombre: "Paraguay", gentilicio: "paraguayo", capital: "Asunción", colores: ["#D52B1E", "#FFFFFF", "#0038A8"], iso: "PY" },
    { id: "peru", nombre: "Perú", gentilicio: "peruano", capital: "Lima", colores: ["#D91023", "#FFFFFF"], iso: "PE" },
    { id: "republica_dominicana", nombre: "República Dominicana", gentilicio: "dominicano", capital: "Santo Domingo", colores: ["#002D62", "#FFFFFF", "#CE1126"], iso: "DO" },
    { id: "surinam", nombre: "Surinam", gentilicio: "surinamés", capital: "Paramaribo", colores: ["#377E3F", "#FFFFFF", "#B40A2D"], iso: "SR" },
    { id: "trinidad_tobago", nombre: "Trinidad y Tobago", gentilicio: "trinitense", capital: "Puerto España", colores: ["#CE1126", "#000000", "#FFFFFF"], iso: "TT" },
    { id: "uruguay", nombre: "Uruguay", gentilicio: "uruguayo", capital: "Montevideo", colores: ["#FFFFFF", "#0038A8", "#FCD116"], iso: "UY" },
  ];
  const base_ = (...a) => base(...a);
  const base = (id, nombre, bando, clase, lat, lon, x = {}) => ({
    id, escenario_id: 1, nombre, bando, clase, lat, lon, fuerza: 100, combustible: 100, municion: 100,
    carga: 0, recarga_restante: 0, despliegue_restante: 0, estado: "activa", echelon: "", terreno: "llano",
    modelo: "", aeronaves: 1, en_tierra: false, base_id: null, espera_restante: 0, mision: "", mision_lat: null, mision_lon: null,
    emitiendo: true, fuego_libre: true, stock_combustible: 1000, stock_municion: 1000, dano_pista: 0, dano_plataforma: 0, dano_combustible: 0, refugios: 0, transporte_id: null, ...x,
  });
  const PLANTILLAS = [
    { id: "ataque-al-puente-turno-4", nombre: "Ataque al puente (situación al turno 4)", descripcion: "Guardada desde un ejercicio anterior por el instructor.", nacion_azul: "venezuela", nacion_rojo: "colombia", unidades: 7, objetivos: 2, origen: "usuario", con_estado: true, guardada_en: iso() },
  ];
  const UNIDADES = [
    base(1, "1ra Bda Infantería", "azul", "infanteria", 8.590, -70.620, { fuerza: 92, municion: 15 }),
    base(2, "Blindados A", "azul", "blindado", 8.585, -70.600, { combustible: 45 }),
    base(3, "Artillería A", "azul", "artilleria", 8.575, -70.630, { municion: 60 }),
    base(4, "Ingenieros 1", "azul", "ingenieros", 8.598, -70.580, { municion: 100 }),
    base(5, "Convoy Log 1", "azul", "transporte", 8.570, -70.600, { carga: 65 }),
    base(6, "AA Portátil 1", "azul", "antiaerea_portatil", 8.588, -70.550, { recarga_restante: 1 }),
    base(7, "Helo Artillado", "azul", "helicoptero_artillado", 8.600, -70.660, { municion: 38, combustible: 22 }),
    base(8, "Halcón 1", "azul", "caza", 8.650, -70.500, { modelo: "f16", aeronaves: 4, echelon: "escuadra" }),
    base(10, "Flecha 1", "azul", "caza", 8.560, -70.520, { modelo: "su30", aeronaves: 2, echelon: "equipo", fuerza: 60, mision: "patrulla", mision_lat: 8.75, mision_lon: -70.3 }),
    base(15, "Cobra 1", "azul", "caza", 8.624, -70.209, { modelo: "f16", aeronaves: 2, echelon: "equipo", en_tierra: true, base_id: 9, espera_restante: 1 }),
    // sobre el aerodromo real de Barinas (SVBI), dañada: muestra el plano con crateres en la pista
    base(9, "Aeropuerto de Barinas", "azul", "base_aerea", 8.618, -70.215, { stock_combustible: 180, stock_municion: 900, fuerza: 55, dano_pista: 45, dano_plataforma: 20, dano_combustible: 10, refugios: 4 }),
    base(19, "AA Pesada 1", "azul", "antiaerea", 8.575, -70.565),
    base(11, "Infantería Roja", "rojo", "infanteria", 8.660, -70.600, { fuerza: 70 }),
    base(12, "Depósito R", "rojo", "deposito", 8.700, -70.620),
    base(13, "Caza R", "rojo", "caza", 8.750, -70.500, { modelo: "su30", aeronaves: 2 }),
    base(14, "Recon Roja", "rojo", "reconocimiento", 9.600, -69.800),
    base(16, "GE Escucha 1", "azul", "guerra_electronica", 8.580, -70.640),
    base(17, "Vigía 1", "azul", "dron_reconocimiento", 8.640, -70.470, { modelo: "uav_reco", aeronaves: 1, echelon: "equipo" }),
    base(18, "Radar Rojo", "rojo", "radar", 8.720, -70.560),
    // mar Caribe frente a Puerto Cabello: buques, portaaviones con un helicoptero a bordo y una salva en vuelo
    base(20, "Destructor Mariscal", "azul", "destructor", 10.62, -68.05, { velocidad_kmh: 55, alcance_km: 60, deteccion_km: 60, municion: 75 }),
    base(21, "Portaaviones Bolívar", "azul", "portaaviones", 10.66, -68.12, { velocidad_kmh: 45, alcance_km: 15, deteccion_km: 50, stock_combustible: 900, stock_municion: 1200 }),
    base(22, "Tiburón 1", "azul", "helicoptero", 10.666, -68.114, { modelo: "helo_ataque", aeronaves: 2, echelon: "equipo", en_tierra: true, base_id: 21, espera_restante: 0 }),
    base(23, "Fragata Roja", "rojo", "fragata", 10.80, -67.70, { velocidad_kmh: 40, alcance_km: 40, deteccion_km: 30 }),
    base(24, "Crucero x2 de Destructor Mariscal", "azul", "misil_crucero", 10.70, -67.90, { modelo: "crucero", aeronaves: 2, velocidad_kmh: 850, alcance_km: 5, autonomia_km: 1000, mision: "impacto", blanco_id: 23, mision_lat: 10.80, mision_lon: -67.70 }),
    base(25, "Submarino Carite", "azul", "submarino", 10.58, -67.98, { velocidad_kmh: 35, alcance_km: 30, deteccion_km: 25 }),
    base(26, "Buque de desembarco Capana", "azul", "buque_desembarco", 10.60, -68.10, { velocidad_kmh: 35, alcance_km: 10, deteccion_km: 25 }),
    base(27, "Infantería de Marina 1", "azul", "infanteria", 10.60, -68.10, { transporte_id: 26 }),
  ];
  // perfil de vuelo de las aeronaves (engine/relieve.py): helicopteros rasantes, misiles siempre rasantes, el resto
  // medio; para variar el ejemplo, Flecha 1 patrulla en perfil alto y el caza rojo entra rasante
  const SIN_ALTO = ["helicoptero", "helicoptero_artillado", "municion_merodeadora"];
  const AEREAS = ["caza", "ataque", "helicoptero", "helicoptero_artillado", "avion_ge", "alerta_temprana", "cisterna", "dron_reconocimiento", "dron_ataque", "municion_merodeadora", "misil_crucero"];
  for (const u of UNIDADES) {
    if (!AEREAS.includes(u.clase)) { u.perfil_actual = null; u.perfiles_permitidos = []; continue; }
    u.perfiles_permitidos = u.clase === "misil_crucero" ? [] : SIN_ALTO.includes(u.clase) ? ["medio", "rasante"] : ["alto", "medio", "rasante"];
    u.perfil_actual = u.clase === "misil_crucero" || u.clase.startsWith("helicoptero") ? "rasante" : ({ 10: "alto", 13: "rasante" })[u.id] || "medio";
  }
  // cobertura por relieve de algunos sensores, calculada con el motor y el terreno real (GET .../cobertura)
  const COBERTURAS = {"18":{"disponible":true,"altura_sensor_m":690,"perfiles":{"alto":{"alcance_km":150.0,"altura_m":6000.0,"poligono":[[9.14088,-70.56],[9.18766,-70.51855],[9.24607,-70.46602],[9.32978,-70.39441],[9.33346,-70.3337],[9.25297,-70.30816],[9.21056,-70.27302],[9.25906,-70.17743],[9.20753,-70.14539],[9.1166,-70.15811],[9.04583,-70.16656],[9.04468,-70.09005],[8.99219,-70.08215],[8.97273,-70.01045],[8.95015,-69.91837],[8.89539,-69.89529],[8.83653,-69.88778],[8.76479,-70.03786],[8.71964,-70.03593],[8.6745,-70.03799],[8.6297,-70.04402],[8.57858,-70.02763],[8.53511,-70.04727],[8.48935,-70.0606],[8.44991,-70.08757],[8.50942,-70.25609],[8.48404,-70.27581],[8.46046,-70.29769],[8.36026,-70.25501],[8.45917,-70.37539],[8.31338,-70.32279],[8.14284,-70.28817],[7.4521,-70.09473],[7.41683,-70.20794],[7.39144,-70.32381],[7.37613,-70.44146],[7.37102,-70.56],[7.37613,-70.67854],[7.39144,-70.79619],[7.41683,-70.91206],[7.4521,-71.02527],[7.49699,-71.13498],[7.74761,-71.12632],[7.79124,-71.21597],[8.0541,-71.12397],[8.21984,-71.06501],[8.38335,-70.96528],[8.37614,-71.05592],[8.50668,-70.93327],[8.53965,-70.95067],[8.59065,-70.91896],[8.62066,-70.93429],[8.66364,-70.88252],[8.69212,-70.88083],[8.71988,-70.86571],[8.74947,-70.90264],[8.78913,-70.9579],[8.83149,-70.98197],[8.86742,-70.97055],[8.89085,-70.93124],[8.91949,-70.91004],[8.9427,-70.88216],[8.92109,-70.80268],[8.92217,-70.7647],[8.91837,-70.72852],[8.95423,-70.72606],[8.96764,-70.70476],[9.00362,-70.69391],[9.04449,-70.6796],[9.07441,-70.65617],[9.11323,-70.63022],[9.1339,-70.59668]]},"medio":{"alcance_km":150.0,"altura_m":1500.0,"poligono":[[8.83331,-70.56],[8.84363,-70.54905],[9.00164,-70.50972],[8.95975,-70.49496],[8.9076,-70.49088],[8.86181,-70.49307],[8.85551,-70.48082],[8.84817,-70.46916],[8.84812,-70.45118],[8.83445,-70.44416],[8.81016,-70.45125],[8.79426,-70.45266],[8.78473,-70.44652],[8.78155,-70.42639],[8.77165,-70.41635],[8.76326,-70.39652],[8.74901,-70.39333],[8.73126,-70.42948],[8.71998,-70.4399],[8.71011,-70.4458],[8.70125,-70.45248],[8.69066,-70.44928],[8.68123,-70.45229],[8.6721,-70.45611],[8.66333,-70.46073],[8.67667,-70.4974],[8.67144,-70.50146],[8.66276,-70.50211],[8.64146,-70.49334],[8.66254,-70.5193],[8.63588,-70.51088],[8.60263,-70.50465],[7.86803,-70.24702],[7.8443,-70.32317],[7.82722,-70.40111],[7.81155,-70.47978],[8.1858,-70.56],[8.18783,-70.60704],[8.31082,-70.63291],[8.31344,-70.67009],[7.95425,-70.84137],[8.1086,-70.84793],[8.44893,-70.7182],[8.46359,-70.74148],[8.5505,-70.7038],[8.59788,-70.68348],[8.61593,-70.68542],[8.63022,-70.68965],[8.65253,-70.67817],[8.67894,-70.64905],[8.68862,-70.6472],[8.69625,-70.64964],[8.70406,-70.65139],[8.71105,-70.66332],[8.71998,-70.66918],[8.73126,-70.69052],[8.75462,-70.75893],[8.7772,-70.77623],[8.79377,-70.76523],[8.80433,-70.7431],[8.81439,-70.72551],[8.8252,-70.71208],[8.8171,-70.67712],[8.81919,-70.66039],[8.7944,-70.62317],[8.79514,-70.61324],[8.79477,-70.60368],[8.84225,-70.6177],[8.85183,-70.60856],[8.86072,-70.59816],[8.85816,-70.58466],[8.84901,-70.57142]]},"rasante":{"alcance_km":150.0,"altura_m":60.0,"poligono":[[8.74158,-70.56],[8.74688,-70.55762],[8.74657,-70.55526],[8.74085,-70.55435],[8.74028,-70.55253],[8.73956,-70.55077],[8.74336,-70.54635],[8.7421,-70.54434],[8.74067,-70.54245],[8.73908,-70.5407],[8.73734,-70.53909],[8.73857,-70.53317],[8.73349,-70.53636],[8.7314,-70.53526],[8.72554,-70.54461],[8.72419,-70.54418],[8.72281,-70.54387],[8.72141,-70.54369],[8.72,-70.54362],[8.71859,-70.54369],[8.71719,-70.54387],[8.71581,-70.54418],[8.71446,-70.54461],[8.71316,-70.54516],[8.71191,-70.54582],[8.71071,-70.54659],[8.70959,-70.54745],[8.70855,-70.54842],[8.7076,-70.54947],[8.71116,-70.55374],[8.70598,-70.55181],[8.70533,-70.55308],[8.70986,-70.55627],[8.70958,-70.55717],[8.70937,-70.5581],[8.70925,-70.55905],[8.67683,-70.56],[8.677,-70.56381],[8.6828,-70.56663],[8.68352,-70.56989],[8.68451,-70.57307],[8.66621,-70.58537],[8.69196,-70.57638],[8.69348,-70.57879],[8.68693,-70.58807],[8.70855,-70.57158],[8.70613,-70.57673],[8.68595,-70.60919],[8.70381,-70.58836],[8.70632,-70.58968],[8.70708,-70.59591],[8.71022,-70.59691],[8.7125,-70.60301],[8.71765,-70.58719],[8.72,-70.59821],[8.72235,-70.58719],[8.72562,-70.59226],[8.72279,-70.57055],[8.72369,-70.57026],[8.72456,-70.5699],[8.7254,-70.56946],[8.72619,-70.56894],[8.72694,-70.56836],[8.72763,-70.56772],[8.7324,-70.57053],[8.73326,-70.56939],[8.76673,-70.5873],[8.73467,-70.56692],[8.73521,-70.5656],[8.73564,-70.56424],[8.74126,-70.56379],[8.7415,-70.5619]]}}},"19":{"disponible":true,"altura_sensor_m":296,"perfiles":{"alto":{"alcance_km":20.0,"altura_m":6000.0,"poligono":[[8.75486,-70.565],[8.75418,-70.54914],[8.75213,-70.5334],[8.74873,-70.5179],[8.74401,-70.50276],[8.738,-70.48809],[8.73076,-70.47401],[8.72232,-70.46063],[8.71277,-70.44804],[8.70216,-70.43634],[8.69059,-70.42562],[8.67814,-70.41596],[8.6649,-70.40743],[8.65098,-70.40011],[8.63648,-70.39404],[8.62151,-70.38928],[8.60619,-70.38585],[8.59063,-70.38379],[8.57496,-70.3831],[8.55928,-70.3838],[8.54373,-70.38588],[8.52841,-70.38932],[8.51345,-70.3941],[8.49895,-70.40018],[8.48504,-70.40751],[8.47181,-70.41604],[8.45936,-70.4257],[8.4478,-70.43642],[8.4372,-70.44812],[8.42765,-70.46071],[8.41922,-70.47409],[8.41198,-70.48816],[8.40598,-70.50281],[8.40126,-70.51794],[8.39787,-70.53343],[8.39582,-70.54915],[8.39514,-70.565],[8.39582,-70.58085],[8.39787,-70.59657],[8.40126,-70.61206],[8.40598,-70.62719],[8.41198,-70.64184],[8.41922,-70.65591],[8.42765,-70.66929],[8.4372,-70.68188],[8.4478,-70.69358],[8.45936,-70.7043],[8.47181,-70.71396],[8.48504,-70.72249],[8.49895,-70.72982],[8.51345,-70.7359],[8.52841,-70.74068],[8.54373,-70.74412],[8.55928,-70.7462],[8.57496,-70.7469],[8.59063,-70.74621],[8.60619,-70.74415],[8.62151,-70.74072],[8.63648,-70.73596],[8.65098,-70.72989],[8.6649,-70.72257],[8.67814,-70.71404],[8.69059,-70.70438],[8.70216,-70.69366],[8.71277,-70.68196],[8.72232,-70.66937],[8.73076,-70.65599],[8.738,-70.64191],[8.74401,-70.62724],[8.74873,-70.6121],[8.75213,-70.5966],[8.75418,-70.58086]]},"medio":{"alcance_km":20.0,"altura_m":1500.0,"poligono":[[8.75486,-70.565],[8.75418,-70.54914],[8.75213,-70.5334],[8.74873,-70.5179],[8.74401,-70.50276],[8.738,-70.48809],[8.73076,-70.47401],[8.72232,-70.46063],[8.71277,-70.44804],[8.70216,-70.43634],[8.69059,-70.42562],[8.67814,-70.41596],[8.6649,-70.40743],[8.65098,-70.40011],[8.63648,-70.39404],[8.62151,-70.38928],[8.60619,-70.38585],[8.59063,-70.38379],[8.57496,-70.3831],[8.55928,-70.3838],[8.54373,-70.38588],[8.52841,-70.38932],[8.51345,-70.3941],[8.49895,-70.40018],[8.48504,-70.40751],[8.47181,-70.41604],[8.45936,-70.4257],[8.4478,-70.43642],[8.4372,-70.44812],[8.42765,-70.46071],[8.41922,-70.47409],[8.41198,-70.48816],[8.40598,-70.50281],[8.40126,-70.51794],[8.39787,-70.53343],[8.39582,-70.54915],[8.39514,-70.565],[8.39582,-70.58085],[8.39787,-70.59657],[8.40126,-70.61206],[8.40598,-70.62719],[8.41198,-70.64184],[8.41922,-70.65591],[8.42765,-70.66929],[8.4372,-70.68188],[8.4478,-70.69358],[8.45936,-70.7043],[8.47181,-70.71396],[8.48504,-70.72249],[8.49895,-70.72982],[8.51345,-70.7359],[8.52841,-70.74068],[8.54373,-70.74412],[8.55928,-70.7462],[8.57496,-70.7469],[8.59063,-70.74621],[8.60619,-70.74415],[8.62151,-70.74072],[8.63648,-70.73596],[8.65098,-70.72989],[8.6649,-70.72257],[8.67814,-70.71404],[8.69059,-70.70438],[8.70216,-70.69366],[8.71277,-70.68196],[8.72232,-70.66937],[8.73076,-70.65599],[8.738,-70.64191],[8.74401,-70.62724],[8.74873,-70.6121],[8.75213,-70.5966],[8.75418,-70.58086]]},"rasante":{"alcance_km":20.0,"altura_m":60.0,"poligono":[[8.5859,-70.565],[8.58586,-70.56404],[8.58574,-70.56309],[8.58553,-70.56215],[8.58524,-70.56123],[8.58488,-70.56034],[8.60332,-70.54846],[8.59732,-70.54919],[8.5917,-70.55083],[8.61354,-70.52602],[8.61003,-70.52277],[8.60626,-70.51984],[8.60497,-70.51249],[8.60264,-70.50505],[8.59736,-70.50284],[8.59333,-70.49578],[8.58824,-70.489],[8.58117,-70.49361],[8.57499,-70.49886],[8.56929,-70.49911],[8.557,-70.46187],[8.54395,-70.44788],[8.52464,-70.42517],[8.54735,-70.50506],[8.54229,-70.50772],[8.53435,-70.50631],[8.52945,-70.51011],[8.52875,-70.51823],[8.52907,-70.52603],[8.53035,-70.53339],[8.52308,-70.53469],[8.52066,-70.53938],[8.51866,-70.54427],[8.51182,-70.54788],[8.50522,-70.55256],[8.53156,-70.56116],[8.5314,-70.565],[8.50984,-70.57076],[8.50522,-70.57744],[8.48023,-70.59067],[8.47256,-70.60269],[8.4762,-70.61158],[8.48059,-70.62011],[8.50356,-70.61558],[8.55412,-70.58271],[8.55573,-70.58449],[8.55748,-70.58611],[8.56249,-70.58306],[8.5641,-70.58409],[8.56809,-70.57999],[8.56941,-70.58054],[8.57218,-70.57565],[8.57311,-70.57586],[8.57405,-70.57598],[8.575,-70.57602],[8.57595,-70.57598],[8.57689,-70.57586],[8.57782,-70.57565],[8.57873,-70.57536],[8.57961,-70.57499],[8.58045,-70.57455],[8.58125,-70.57403],[8.58201,-70.57345],[8.58271,-70.5728],[8.58753,-70.57563],[8.58839,-70.57449],[8.60332,-70.58154],[8.60464,-70.57898],[8.61085,-70.5782],[8.61185,-70.57499],[8.61257,-70.5717],[8.61301,-70.56836]]}}},"20":{"disponible":true,"altura_sensor_m":30,"perfiles":{"alto":{"alcance_km":60.0,"altura_m":6000.0,"poligono":[[11.15959,-68.05],[11.15754,-68.00207],[11.15138,-67.9545],[11.14117,-67.90766],[11.12699,-67.86192],[11.10895,-67.81761],[11.08718,-67.77508],[11.06185,-67.73465],[11.03315,-67.69663],[11.00131,-67.66131],[10.96656,-67.62896],[10.92917,-67.59983],[10.88944,-67.57413],[10.84765,-67.55207],[10.80413,-67.5338],[10.75921,-67.51947],[10.71324,-67.50918],[10.66656,-67.50301],[10.61952,-67.501],[10.5725,-67.50318],[10.52584,-67.50951],[10.4799,-67.51995],[10.43503,-67.53442],[10.39157,-67.55281],[10.34985,-67.57497],[10.31019,-67.60074],[10.27288,-67.62992],[10.23822,-67.66228],[10.20645,-67.69758],[10.17784,-67.73556],[10.15258,-67.77591],[10.13088,-67.81835],[10.11289,-67.86254],[10.09876,-67.90815],[10.08859,-67.95483],[10.08246,-68.00223],[10.08041,-68.05],[10.08246,-68.09777],[10.08859,-68.14517],[10.09876,-68.19185],[10.11289,-68.23746],[10.13088,-68.28165],[10.15258,-68.32409],[10.17784,-68.36444],[10.20645,-68.40242],[10.23822,-68.43772],[10.27288,-68.47008],[10.31019,-68.49926],[10.34985,-68.52503],[10.39157,-68.54719],[10.43503,-68.56558],[10.4799,-68.58005],[10.52584,-68.59049],[10.5725,-68.59682],[10.61952,-68.599],[10.66656,-68.59699],[10.71324,-68.59082],[10.75921,-68.58053],[10.80413,-68.5662],[10.84765,-68.54793],[10.88944,-68.52587],[10.92917,-68.50017],[10.96656,-68.47104],[11.00131,-68.43869],[11.03315,-68.40337],[11.06185,-68.36535],[11.08718,-68.32492],[11.10895,-68.28239],[11.12699,-68.23808],[11.14117,-68.19234],[11.15138,-68.1455],[11.15754,-68.09793]]},"medio":{"alcance_km":60.0,"altura_m":1500.0,"poligono":[[11.15959,-68.05],[11.15754,-68.00207],[11.15138,-67.9545],[11.14117,-67.90766],[11.12699,-67.86192],[11.10895,-67.81761],[11.08718,-67.77508],[11.06185,-67.73465],[11.03315,-67.69663],[11.00131,-67.66131],[10.96656,-67.62896],[10.92917,-67.59983],[10.88944,-67.57413],[10.84765,-67.55207],[10.80413,-67.5338],[10.75921,-67.51947],[10.71324,-67.50918],[10.66656,-67.50301],[10.61952,-67.501],[10.5725,-67.50318],[10.52584,-67.50951],[10.4799,-67.51995],[10.43503,-67.53442],[10.39157,-67.55281],[10.34985,-67.57497],[10.31019,-67.60074],[10.27288,-67.62992],[10.26877,-67.69326],[10.26437,-67.74686],[10.28841,-67.81408],[10.24608,-67.83067],[10.30698,-67.90166],[10.30561,-67.9337],[10.2812,-67.95774],[10.22145,-67.97859],[10.25985,-68.01798],[10.19372,-68.05],[10.10933,-68.09538],[10.12579,-68.13852],[10.1144,-68.1876],[10.23968,-68.19065],[10.21893,-68.24001],[10.15258,-68.32409],[10.17784,-68.36444],[10.20645,-68.40242],[10.23822,-68.43772],[10.27288,-68.47008],[10.31019,-68.49926],[10.34985,-68.52503],[10.39157,-68.54719],[10.43503,-68.56558],[10.4799,-68.58005],[10.52584,-68.59049],[10.5725,-68.59682],[10.61952,-68.599],[10.66656,-68.59699],[10.71324,-68.59082],[10.75921,-68.58053],[10.80413,-68.5662],[10.84765,-68.54793],[10.88944,-68.52587],[10.92917,-68.50017],[10.96656,-68.47104],[11.00131,-68.43869],[11.03315,-68.40337],[11.06185,-68.36535],[11.08718,-68.32492],[11.10895,-68.28239],[11.12699,-68.23808],[11.14117,-68.19234],[11.15138,-68.1455],[11.15754,-68.09793]]},"rasante":{"alcance_km":60.0,"altura_m":60.0,"poligono":[[11.12182,-68.05],[11.11991,-68.00543],[11.11419,-67.9612],[11.10469,-67.91764],[11.09151,-67.8751],[11.07473,-67.8339],[11.05449,-67.79435],[11.03093,-67.75675],[11.00425,-67.7214],[10.97463,-67.68855],[10.94232,-67.65847],[10.90755,-67.63137],[10.8706,-67.60747],[10.83174,-67.58695],[10.79127,-67.56995],[10.74949,-67.55662],[10.70674,-67.54705],[10.66333,-67.5413],[10.61959,-67.53943],[10.57586,-67.54145],[10.53246,-67.54733],[10.50097,-67.59943],[10.49616,-67.70449],[10.48303,-67.7516],[10.4715,-67.78863],[10.46517,-67.82526],[10.46733,-67.86505],[10.44825,-67.87541],[10.43395,-67.8913],[10.46086,-67.9367],[10.42839,-67.93753],[10.45861,-67.97347],[10.45774,-67.98995],[10.42194,-67.99604],[10.45527,-68.02046],[10.40498,-68.03087],[10.46352,-68.05],[10.45874,-68.06435],[10.42338,-68.08525],[10.44279,-68.09828],[10.46281,-68.10818],[10.43904,-68.1358],[10.46578,-68.14054],[10.46086,-68.1633],[10.45463,-68.19108],[10.45589,-68.21684],[10.45345,-68.25176],[10.43729,-68.31517],[10.44989,-68.34936],[10.5036,-68.30366],[10.4795,-68.4419],[10.48693,-68.55356],[10.54569,-68.47701],[10.5725,-68.59682],[10.61952,-68.599],[10.66656,-68.59699],[10.70674,-68.55295],[10.75782,-68.57523],[10.80045,-68.55587],[10.81355,-68.4732],[10.82753,-68.41634],[10.85503,-68.39205],[10.86958,-68.35305],[10.87934,-68.3142],[10.89686,-68.28665],[10.89398,-68.24541],[11.05449,-68.30565],[11.07473,-68.2661],[11.09151,-68.2249],[11.10469,-68.18236],[11.11419,-68.1388],[11.11991,-68.09457]]}}}};

  // zona de interferencia roja vigente (la emitio el turno anterior) sobre parte del despliegue azul
  const INTERFERENCIAS = [{ id: 1, bando: "rojo", unidad_id: 13, lat: 8.63, lon: -70.49, radio_km: 12, turno: 2 }];
  // meteorologia por zonas: una tormenta estacionaria sobre los Andes y un frente de lluvia que deriva al este
  const ZONAS_CLIMA = [
    { id: 1, tipo: "tormenta", lat: 8.72, lon: -70.85, radio_km: 35, deriva_rumbo: 0, deriva_kmh: 0, hasta_turno: null, nombre: "" },
    { id: 2, tipo: "lluvia", lat: 8.45, lon: -70.35, radio_km: 60, deriva_rumbo: 90, deriva_kmh: 25, hasta_turno: 8, nombre: "Frente 1" },
  ];
  // misiones aereas: una CAP en orbita, una interdiccion programada (azul) y una SEAD roja que azul no debe ver
  let misiones = [
    { id: 1, bando: "azul", rol: "CAP", rol_nombre: "Patrulla aerea de combate (CAP)", nombre: "Flecha", estado: "en_curso", unidad_id: 10, base_id: null, modelo: "su30", aeronaves: 2, turno_despegue: 2, creada_turno: 2,
      puntos: [{ tipo: "orbita", lat: 8.75, lon: -70.3, turnos: 3 }, { tipo: "aterrizaje", lat: 8.618, lon: -70.215, base_id: 9 }],
      plan: { puntos: [{ tipo: "orbita", km: 32, llegada_h: 0.03, combustible_llegada: 99, salida_h: 4, combustible_salida: 75 }, { tipo: "aterrizaje", km: 31, llegada_h: 4.03, combustible_llegada: 74 }], duracion_h: 4.03, combustible_final: 74, advertencias: [] },
      indice: 0, espera: 2, resultado: "En orbita: 2 turno(s) mas.", autor: "alfa", autor_puesto: "operaciones" },
    { id: 2, bando: "azul", rol: "INTERDICCION", rol_nombre: "Interdiccion (ataque a un blanco)", nombre: "Rayo", estado: "programada", unidad_id: null, base_id: 9, modelo: "f16", aeronaves: 2, turno_despegue: 5, creada_turno: 3,
      puntos: [{ tipo: "paso", lat: 8.60, lon: -70.66 }, { tipo: "blanco", lat: 8.66, lon: -70.60, objetivo_unidad_id: 11 }, { tipo: "aterrizaje", lat: 8.618, lon: -70.215, base_id: 9 }],
      plan: { puntos: [{ tipo: "paso", km: 18, llegada_h: 0.02, combustible_llegada: 99 }, { tipo: "blanco", km: 9, llegada_h: 0.03, combustible_llegada: 98.6, salida_h: 1 }, { tipo: "aterrizaje", km: 16, llegada_h: 1.02, combustible_llegada: 97.7 }], duracion_h: 1.02, combustible_final: 97.7, advertencias: [] },
      indice: 0, espera: -1, resultado: "Programada.", autor: "alfa", autor_puesto: "operaciones" },
    { id: 3, bando: "rojo", rol: "SEAD", rol_nombre: "Supresion de defensas aereas (SEAD)", nombre: "Víbora", estado: "programada", unidad_id: null, base_id: 12, modelo: "su30", aeronaves: 2, turno_despegue: 4, creada_turno: 3,
      puntos: [{ tipo: "blanco", lat: 8.588, lon: -70.55 }, { tipo: "aterrizaje", lat: 8.7, lon: -70.62, base_id: 12 }],
      plan: { puntos: [{ tipo: "blanco", km: 13, llegada_h: 0.01, combustible_llegada: 99.6, salida_h: 1 }, { tipo: "aterrizaje", km: 13, llegada_h: 1.01, combustible_llegada: 99.1 }], duracion_h: 1.01, combustible_final: 99.1, advertencias: [] },
      indice: 0, espera: -1, resultado: "Programada.", autor: "bravo", autor_puesto: "mando" },
  ];
  let proximaMision = 4;

  /** Estimacion simplificada (misma idea que engine/misiones.py) para el planificador del arnes. */
  function previsualizarMision(c) {
    const origen = UNIDADES.find((x) => x.id === (c.unidad_id ?? c.base_id));
    const modelo = CAT.modelos.find((x) => x.id === (c.modelo || (origen && origen.modelo)));
    const clase = CAT.clases.find((x) => x.id === (modelo ? modelo.clase : origen && origen.clase)) || {};
    const vel = (modelo || clase).velocidad_kmh || 800;
    const aut = (modelo || clase).autonomia_km || 1500;
    let horas = 0;
    let comb = c.unidad_id ? (origen.combustible ?? 100) : 100;
    let prev = [origen.lat, origen.lon];
    const filas = [];
    for (const p of c.puntos) {
      const d = Logica.distanciaKm(prev[0], prev[1], p.lat, p.lon);
      horas += d / vel;
      comb -= (d / aut) * 100;
      const f = { tipo: p.tipo, km: +d.toFixed(1), llegada_h: +horas.toFixed(2), combustible_llegada: +comb.toFixed(1) };
      if (p.tipo === "orbita") { horas = Math.floor(horas) + 1 + (p.turnos || 1); comb -= 8 * (p.turnos || 1); f.salida_h = horas; f.combustible_salida = +comb.toFixed(1); }
      else if (p.tipo === "blanco") { horas = Math.floor(horas) + 1; f.salida_h = horas; }
      filas.push(f);
      prev = [p.lat, p.lon];
    }
    const rol = CAT.misiones.roles.find((r) => r.id === c.rol);
    const tipos = c.puntos.map((p) => p.tipo);
    const errores = [];
    if (!rol) errores.push("Rol de mision desconocido.");
    else for (const t of rol.requiere) if (!tipos.includes(t)) errores.push(`El rol ${rol.nombre} necesita al menos un punto de tipo ${t}.`);
    if (!clase.se_consume && tipos[tipos.length - 1] !== "aterrizaje") errores.push("La ruta debe terminar con el aterrizaje en una base propia.");
    const advertencias = comb < 0 ? ["No alcanza el combustible: se quedaria sin combustible antes del final."] : [];
    return { plan: { puntos: filas, duracion_h: +horas.toFixed(2), combustible_final: +comb.toFixed(1), advertencias }, errores, turno_despegue: c.turno_despegue ?? ESC.turno_actual, puntos: c.puntos };
  }
  const CONTACTO_FANTASMA = { unidad_id: 14, nombre: "Recon Roja", tipo: "terrestre", clase: "reconocimiento", lat: 9.6, lon: -69.8, turno_visto: 2 };
  let ordenes = [
    // autor / autor_puesto: quien la emitio y su puesto en ese momento (vacios en las ordenes automaticas del motor)
    { id: 1, escenario_id: 1, unidad_id: 2, tipo: "mover", objetivo_unidad_id: null, waypoints: [[8.600, -70.570], [8.620, -70.550]], detalle: "", turno_emitida: 3, estado: "pendiente", resultado: "", autor: "alfa", autor_puesto: "planificacion" },
    { id: 2, escenario_id: 1, unidad_id: 3, tipo: "atacar", objetivo_unidad_id: 11, waypoints: [], detalle: "", turno_emitida: 3, estado: "pendiente", resultado: "", autor: "alfa", autor_puesto: "planificacion" },
    { id: 3, escenario_id: 1, unidad_id: 4, tipo: "construir", objetivo_unidad_id: null, waypoints: [[8.605, -70.580]], detalle: "puente", turno_emitida: 3, estado: "pendiente", resultado: "", autor: "carlos", autor_puesto: "logistica" },
    { id: 4, escenario_id: 1, unidad_id: 1, tipo: "atacar", objetivo_unidad_id: 11, waypoints: [], detalle: "", turno_emitida: 2, estado: "resuelta", resultado: "Ataque a Infantería Roja. Ratio 1.32: defensor pierde 19.0%, atacante pierde 12.0%. Efectos: clima x0.80 al ataque; sorpresa (atacante no detectado) x1.20.", autor: "alfa", autor_puesto: "mando" },
  ];
  let proximaOrden = 5;
  let objetivos = [
    { id: 1, bando: "azul", tipo: "ocupar", nombre: "Tomar el puente", puntos: 40, lat: 8.63, lon: -70.52, radio_km: 4, turnos_requeridos: 3, progreso: 1, unidad_id: null, unidad_nombre: "", hasta_turno: null, estado: "pendiente", turno_resuelto: null },
    { id: 2, bando: "azul", tipo: "destruir", nombre: "Neutralizar la infantería enemiga", puntos: 50, lat: null, lon: null, radio_km: 5, turnos_requeridos: 1, progreso: 0, unidad_id: 11, unidad_nombre: "Infantería Roja", hasta_turno: null, estado: "pendiente", turno_resuelto: null },
    { id: 3, bando: "azul", tipo: "proteger", nombre: "Mantener la base", puntos: 30, lat: null, lon: null, radio_km: 5, turnos_requeridos: 1, progreso: 0, unidad_id: 9, unidad_nombre: "Aeropuerto de Barinas", hasta_turno: 8, estado: "cumplido", turno_resuelto: 2 },
    { id: 4, bando: "rojo", tipo: "ocupar", nombre: "Cruzar el río", puntos: 25, lat: 8.7, lon: -70.7, radio_km: 5, turnos_requeridos: 1, progreso: 0, unidad_id: null, unidad_nombre: "", hasta_turno: null, estado: "pendiente", turno_resuelto: null },
  ];
  let proximoObjetivo = 5;
  const OBRAS = [
    { id: 1, bando: "azul", tipo: "puente", lat: 8.605, lon: -70.560, radio_km: 0.8, creada_turno: 2, expira_turno: 14 },
    { id: 2, bando: "rojo", tipo: "vado", lat: 8.605, lon: -70.700, radio_km: 0.8, creada_turno: 3, expira_turno: 7 },
  ];
  let graficos = [
    { id: 1, bando: "azul", tipo: "linea_fase", etiqueta: "LF ALFA", geometria: { type: "LineString", coordinates: [[-70.66, 8.63], [-70.60, 8.635], [-70.54, 8.63]] }, autor: "alfa", turno: 2 },
    { id: 2, bando: "azul", tipo: "zona_reunion", etiqueta: "ZR 1", geometria: { type: "Polygon", coordinates: [[[-70.64, 8.56], [-70.60, 8.56], [-70.60, 8.58], [-70.64, 8.58], [-70.64, 8.56]]] }, autor: "alfa", turno: 1 },
    { id: 3, bando: "rojo", tipo: "punto_control", etiqueta: "PC ROJO", geometria: { type: "Point", coordinates: [-70.58, 8.69] }, autor: "bravo", turno: 2 },
    { id: 4, bando: "todos", tipo: "eje_avance", etiqueta: "EA NORTE", geometria: { type: "LineString", coordinates: [[-70.70, 8.60], [-70.68, 8.64], [-70.66, 8.68]] }, autor: "prof", turno: 1 },
  ];
  let proximoGrafico = 5;
  let eventos = [
    { id: 2, escenario_id: 1, turno: 3, tipo: "clima", descripcion: "El clima cambia a lluvia.", bando_destino: "todos" },
    { id: 1, escenario_id: 1, turno: 2, tipo: "logistica", descripcion: "Caza R se quedo sin combustible lejos de una base aerea y se perdio.", bando_destino: "rojo" },
  ];
  let mensajes = [
    { id: 1, canal: "azul", remitente: "alfa", rol: "azul", texto: "Blindados en posición, esperando órdenes.", turno: 2, creado_en: iso(-600000) + "Z" },
  ];
  let proximoMensaje = 2;

  // ------------------------------------------------------------------ vista por rol (como el servidor)
  const FACTOR_DET = { despejado: 1, nublado: 0.9, lluvia: 0.7, tormenta: 0.5 };
  const OCULTOS = ["fuerza", "velocidad_kmh", "alcance_km", "deteccion_km", "combustible", "municion", "autonomia_km", "carga", "recarga_restante", "despliegue_restante", "modelo", "aeronaves", "base_id", "espera_restante", "mision", "mision_lat", "mision_lon", "blanco_id", "emitiendo", "fuego_libre", "stock_combustible", "stock_municion", "dano_pista", "dano_plataforma", "dano_combustible", "refugios", "transporte_id"];
  const km = (a, b) => Logica.distanciaKm(a.lat, a.lon, b.lat, b.lon);

  function completar(u) {
    const c = CAT.clases.find((x) => x.id === u.clase);
    const rama = { terrestre: 0, aerea: 0, naval: 0, base: 0 };
    void rama;
    return { ...u, tipo: c.tipo, sidc: u.bando === "azul" ? c.sidc_azul : c.sidc_rojo, velocidad_kmh: c.velocidad_kmh, alcance_km: c.alcance_km, deteccion_km: c.deteccion_km, autonomia_km: c.autonomia_km };
  }

  function claseTerreno(lat) { return lat >= 8.60 && lat <= 8.61 ? "rio" : lat < 8.4 ? "agua" : "llano"; }

  let vista = null; // instructor: "azul" | "rojo" | null
  function rolEfectivo() { return vista || ROL; }

  function estadoPara() {
    const rol = rolEfectivo();
    const todas = UNIDADES.map(completar);
    const esBando = BANDOS.includes(rol);
    let unidades = todas;
    let contactos = [];
    if (esBando) {
      const propias = todas.filter((u) => u.bando === rol);
      const f = FACTOR_DET[ESC.clima];
      const visibles = todas.filter((u) => u.bando !== rol && u.id !== 14 && propias.some((p) => p.estado === "activa" && km(p, u) <= p.deteccion_km * f));
      unidades = [...propias, ...visibles.map((u) => { const c = { ...u }; OCULTOS.forEach((k) => { c[k] = null; }); return c; })];
      // zonas meteorologicas (las ven todos)
      if (rol === "azul") contactos = [{ ...CONTACTO_FANTASMA, sidc: completar(UNIDADES.find((u) => u.id === 14)).sidc }];
    }
    unidades = unidades.map((u) => ({ ...u, terreno: claseTerreno(u.lat) }));
    const ids = new Set(unidades.map((u) => u.id));
    const propiasIds = new Set(unidades.filter((u) => !esBando || u.bando === rol).map((u) => u.id));
    const esc = { ...ESC };
    if (rol !== "instructor") { delete esc.com_latencia_ms; delete esc.com_jitter_ms; delete esc.com_perdida_pct; }
    return {
      tipo: "estado", ahora: iso(), vista: esBando ? rol : "completa", escenario: esc, unidades, contactos,
      obras: OBRAS.filter((o) => !esBando || o.bando === rol || unidades.some((u) => u.bando === rol && km(u, o) <= 15)),
      interferencias: INTERFERENCIAS,
      clima_zonas: ZONAS_CLIMA,
      informes: ROL === "rojo" ? [] : INFORMES,
      misiones: misiones.filter((mi) => !esBando || mi.bando === rol),
      graficos: graficos.filter((g) => g.bando === "todos" || !esBando || g.bando === rol),
      objetivos: objetivos.filter((o) => !esBando || o.bando === rol),
      marcador: { azul: { objetivos: 30, bajas: 4, total: 34 }, rojo: { objetivos: 0, bajas: 3, total: 3 } },
      ordenes: ordenes.filter((o) => propiasIds.has(o.unidad_id) && ids.has(o.unidad_id)),
      eventos: eventos.filter((e) => !esBando || e.bando_destino === "todos" || e.bando_destino === rol),
    };
  }

  // ------------------------------------------------------------------ historial para el informe y la linea de tiempo
  function historia() {
    const mun = { 1: [100, 75, 15, 15], 2: [100, 100, 100, 100], 7: [100, 100, 46, 38], 5: [100, 100, 100, 100] };
    const com = { 1: [100, 100, 100, 95], 2: [100, 60, 55, 20], 7: [100, 90, 55, 22], 5: [100, 90, 60, 50] };
    const fue = { 1: [100, 95, 92, 92], 11: [100, 81, 63, 63] };
    const turnos = [0, 1, 2, 3].map((t) => ({
      turno: t, clima: t < 2 ? "despejado" : "lluvia", combates: [], ordenes: [], eventos: [], en_curso: false,
      unidades: UNIDADES.map(completar).map((u) => ({
        id: u.id, nombre: u.nombre, bando: u.bando, tipo: u.tipo, clase: u.clase, sidc: u.sidc,
        lat: u.lat + (u.id === 2 ? t * 0.008 : 0), lon: u.lon + (u.id === 2 ? t * 0.006 : 0),
        fuerza: (fue[u.id] || [100, 100, 100, 100])[t], estado: "activa",
        combustible: (com[u.id] || [100, 100, 100, 100])[t], municion: (mun[u.id] || [100, 100, 100, 100])[t],
      })),
    }));
    const combate = (id, turno, a, d, ratio, pa, pd, efectos) => {
      const ua = UNIDADES.find((u) => u.id === a);
      const ud = UNIDADES.find((u) => u.id === d);
      const c = { id, turno, atacante_id: a, defensor_id: d, atacante: ua.nombre, defensor: ud.nombre, atacante_bando: ua.bando, defensor_bando: ud.bando, ratio, perdida_atacante: pa, perdida_defensor: pd, terreno: "llano", efectos, lat: ud.lat, lon: ud.lon };
      turnos[turno].combates.push(c);
      return c;
    };
    const cs = [
      combate(1, 1, 1, 11, 1.1, 8, 19, "sorpresa (atacante no detectado) x1.20"),
      combate(2, 2, 1, 11, 1.32, 12, 18, "clima x0.80 al ataque; apoyo al atacante x1.30"),
      combate(3, 3, 2, 11, 1.6, 6, 22, "cadencia de fuego x1.26"),
    ];
    turnos[3].eventos.push({ id: 5, turno: 3, tipo: "clima", bando_destino: "todos", descripcion: "El clima cambia a lluvia." });
    turnos[2].eventos.push({ id: 6, turno: 2, tipo: "logistica", bando_destino: "rojo", descripcion: "Caza R se quedo sin combustible y se perdio." });
    return { turnos, cs };
  }

  function informe() {
    const { turnos } = historia();
    return {
      escenario: { id: 1, nombre: ESC.nombre, estado: ESC.estado, turno_actual: 4, clima: ESC.clima, azar: true, creado_en: iso() },
      turnos, resumen: {
        azul: { unidades: 9, destruidas: 0, fuerza_perdida: 26, combates_iniciados: 3, combates_recibidos: 0, ordenes_emitidas: 6, ordenes_rechazadas: 1, dano_infligido: 59 },
        rojo: { unidades: 4, destruidas: 1, fuerza_perdida: 59, combates_iniciados: 0, combates_recibidos: 3, ordenes_emitidas: 0, ordenes_rechazadas: 0, dano_infligido: 26 },
      },
    };
  }

  // replay animado: 5 instantaneas (despliegue + 4 turnos) coherentes con UNIDADES; Blindados A y la 1ra Bda
  // avanzan sobre la Infanteria Roja, el helo hace un rodeo, el radar rojo se repliega, Caza R cae en el turno 3
  // y la Infanteria Roja en el 4 (las demas unidades no se mueven)
  function replay() {
    const ruta = {
      2: [[8.585, -70.600], [8.600, -70.594], [8.618, -70.590], [8.640, -70.596], [8.655, -70.600]],
      1: [[8.590, -70.620], [8.605, -70.618], [8.622, -70.612], [8.640, -70.606], [8.650, -70.604]],
      7: [[8.600, -70.660], [8.640, -70.690], [8.690, -70.660], [8.700, -70.610], [8.670, -70.640]],
      13: [[8.750, -70.500], [8.720, -70.540], [8.690, -70.560], [8.690, -70.560], [8.690, -70.560]],
      18: [[8.720, -70.560], [8.720, -70.560], [8.735, -70.585], [8.750, -70.610], [8.750, -70.610]],
    };
    const fuerza = { 11: [70, 51, 33, 33, 0], 13: [100, 100, 100, 0, 0], 1: [92, 87, 80, 80, 78], 2: [100, 100, 100, 94, 90] };
    const estado = (id, t) => ((id === 11 && t >= 4) || (id === 13 && t >= 3) ? "destruida" : "activa");
    const marcador = [[0, 0], [1, 0], [33, 2], [37, 2], [40, 3]].map(([a, r]) => ({ azul: { objetivos: a >= 30 ? 30 : 0, bajas: a >= 30 ? a - 30 : a, total: a }, rojo: { objetivos: 0, bajas: r, total: r } }));
    const turnos = [0, 1, 2, 3, 4].map((t) => ({
      turno: t, clima: t < 3 ? "despejado" : "lluvia", combates: [], eventos: [], marcador: marcador[t],
      unidades: UNIDADES.map(completar).map((u) => ({
        id: u.id, nombre: u.nombre, bando: u.bando, tipo: u.tipo, clase: u.clase, sidc: u.sidc,
        lat: ruta[u.id] ? ruta[u.id][t][0] : u.lat, lon: ruta[u.id] ? ruta[u.id][t][1] : u.lon,
        fuerza: (fuerza[u.id] || [100, 100, 100, 100, 100])[t], estado: estado(u.id, t),
      })),
    }));
    const combate = (id, turno, a, d, pa, pd, efectos) => {
      const ua = UNIDADES.find((u) => u.id === a);
      const ud = UNIDADES.find((u) => u.id === d);
      const pos = ruta[d] ? ruta[d][turno] : [ud.lat, ud.lon];
      turnos[turno].combates.push({ id, turno, atacante_id: a, defensor_id: d, atacante: ua.nombre, defensor: ud.nombre, atacante_bando: ua.bando, defensor_bando: ud.bando, ratio: 1.2, perdida_atacante: pa, perdida_defensor: pd, terreno: "llano", efectos, lat: pos[0], lon: pos[1] });
    };
    combate(1, 1, 1, 11, 5, 19, "sorpresa (atacante no detectado) x1.20");
    combate(2, 2, 1, 11, 7, 18, "apoyo al atacante x1.30");
    combate(3, 3, 8, 13, 0, 100, "cadencia de fuego x1.26");
    combate(4, 4, 2, 11, 4, 33, "clima x0.80 al ataque");
    turnos[2].eventos.push({ id: 7, tipo: "objetivo", descripcion: "Azul cumple 'Mantener la base' (+30 pts)." });
    turnos[3].eventos.push({ id: 5, tipo: "clima", descripcion: "El clima cambia a lluvia." });
    turnos[3].eventos.push({ id: 8, tipo: "logistica", descripcion: "Caza R se quedo sin combustible y se perdio." });
    turnos[4].eventos.push({ id: 9, tipo: "combate", descripcion: "Infanteria Roja destruida." });
    return { escenario: { id: 1, nombre: ESC.nombre, estado: ESC.estado, turno_actual: 5, hora_inicio_min: 360 }, turnos };
  }

  // indicadores doctrinales (mismos nombres y criterios que backend/app/engine/aar.py, _doctrina)
  const INDICADORES = [
    ["reaccion", "Reacción ante las amenazas", "Turnos entre el primer ataque de una unidad enemiga y la primera orden propia contra ella (1 turno = 100; 2 = 75; 3 = 50; más = 25), ponderado por las amenazas respondidas."],
    ["inteligencia", "Conocimiento del enemigo", "Porcentaje de las unidades enemigas que el bando llegó a detectar (radares, reconocimiento, guerra electrónica y contacto)."],
    ["logistica", "Sostenimiento logístico", "100 si ninguna unidad bajó del nivel crítico; si no, reabastecimientos / (reabastecimientos + unidades críticas)."],
    ["coordinacion", "Coordinación entre puestos", "Puestos especializados (A2, A3, A4, A5) que dieron órdenes, sobre los que tenían unidades a cargo (según quién emitió cada orden)."],
    ["economia", "Economía de fuerzas", "Pérdidas infligidas sobre el total de pérdidas de ambos lados en los combates del bando."],
    ["objetivos", "Cumplimiento de objetivos", "Objetivos cumplidos sobre los asignados al bando."],
    ["iniciativa", "Iniciativa", "Turnos en los que el bando dio al menos una orden o planificó una misión."],
  ];
  function doctrina(valores) {
    const indicadores = INDICADORES.map(([id, nombre, criterio]) => ({ id, nombre, criterio, valor: valores[id][0], puntaje: valores[id][1] }));
    const p = indicadores.map((i) => i.puntaje).filter((x) => x !== null);
    const promedio = Math.round((10 * p.reduce((a, b) => a + b, 0)) / p.length) / 10;
    return { indicadores, promedio, nota: Math.round(1 + (19 * promedio) / 100), escala: "1 a 20 (promedio de los indicadores que aplican)" };
  }
  function comparacion(ids) {
    const nombres = { 1: ESC.nombre, 2: "Interdicción en los llanos (contra la IA)", 3: "Defensa aérea de la región central (contra la IA)" };
    const datos = {
      1: { azul: [12, { reaccion: 75, inteligencia: 67, logistica: 0, coordinacion: 67, economia: 69, objetivos: 50, iniciativa: 100 }], rojo: [6, { reaccion: 0, inteligencia: 40, logistica: 100, coordinacion: null, economia: 31, objetivos: 0, iniciativa: 0 }] },
      2: { azul: [10, { reaccion: 50, inteligencia: 57, logistica: 50, coordinacion: 50, economia: 45, objetivos: 25, iniciativa: 83 }], rojo: [11, { reaccion: 75, inteligencia: 60, logistica: 100, coordinacion: null, economia: 55, objetivos: 0, iniciativa: 100 }] },
      3: { azul: [15, { reaccion: 100, inteligencia: 80, logistica: 100, coordinacion: 75, economia: 72, objetivos: 67, iniciativa: 100 }], rojo: [8, { reaccion: 50, inteligencia: 45, logistica: 100, coordinacion: null, economia: 28, objetivos: 0, iniciativa: 100 }] },
    };
    const lista = ids.split(",").map((x) => parseInt(x, 10)).filter((x) => datos[x]);
    const ejercicios = lista.map((id) => ({ id, nombre: nombres[id], estado: "finalizado", turnos: 6,
      bandos: Object.fromEntries(BANDOS.map((b) => [b, { nota: datos[id][b][0], promedio: null, indicadores: datos[id][b][1], ordenes: 20, tasa_rechazo: 5 }])) }));
    const alumnos = [["alfa", "azul", "EM"], ["delta", "azul", "A3"]].map(([u, b, p]) => ({ username: u,
      ejercicios: lista.map((id, i) => ({ escenario_id: id, escenario: nombres[id], bando: b, puesto: p, ordenes: 6 + 3 * i, rechazadas: Math.max(0, 2 - i), turnos_activos: 4 + i, turnos_pasivos: Math.max(0, 2 - i), misiones: p === "A3" ? 2 + i : 0, nota_bando: datos[id][b][0] })) }));
    return { ejercicios, indicadores: Object.fromEntries(INDICADORES.map(([id, nombre]) => [id, nombre])), alumnos };
  }

  function rubrica() {
    const ordenes = (e, r, x, motivos) => ({ emitidas: e, resueltas: r, rechazadas: x, pendientes: 0, motivos_rechazo: motivos, tasa_rechazo: e ? Math.round((1000 * x) / e) / 10 : 0 });
    const puesto = (sigla, nombre, o, misiones = 0, observaciones = []) => ({ sigla, nombre, ordenes: o, misiones, observaciones });
    const vacio = () => ordenes(0, 0, 0, []);
    return {
      escenario: { id: 1, nombre: ESC.nombre, estado: ESC.estado, turno_actual: 4, turnos_resueltos: 3 },
      umbral_critico: 25,
      nota_puestos: "El desglose por puesto se deriva de la funcion de cada orden (puesto responsable: A2, A3, A4 o A5), no del alumno que la firmo; la evaluacion por alumno usa el autor registrado en cada orden y mision.",
      bandos: {
        azul: {
          ordenes: ordenes(6, 5, 1, [{ motivo: "Objetivo fuera de alcance", veces: 1 }]),
          turnos_pasivos: { cantidad: 0, turnos: [] },
          logistica: { unidades_criticas: [{ unidad_id: 1, unidad: "1ra Brigada de Infanteria", bando: "azul", variables: ["combustible"], turno: 3, minimo: 18 }], unidades_en_nivel_critico: 1, reabastecimientos: 0 },
          perdidas: { infligidas: 59, sufridas: 26, unidades_destruidas: 0, enemigas_destruidas: 1 },
          objetivos: { cumplidos: 1, fallidos: 0, pendientes: 1, puntos: 20 },
          misiones: { planificadas: 2, cumplidas: 1, abortadas: 1, fallidas: 0, canceladas: 0, en_curso: 0 },
          doctrina: doctrina({ reaccion: ["1.5 turno(s) en promedio", 75], inteligencia: ["67 % de las unidades enemigas detectadas (2 sensor(es) propio(s))", 67],
            logistica: ["1 unidad(es) en nivel crítico; 0 reabastecimiento(s)", 0], coordinacion: ["2 de 3 puesto(s) con unidades a cargo dieron órdenes", 67],
            economia: ["59 pts infligidos / 26 sufridos", 69], objetivos: ["1 de 2 cumplido(s)", 50], iniciativa: ["3 de 3 turno(s) con órdenes", 100] }),
          puestos: {
            inteligencia: puesto("A2", "Inteligencia", vacio()),
            operaciones: puesto("A3", "Operaciones en curso", ordenes(2, 2, 0, []), 2),
            logistica: puesto("A4", "Logistica", vacio()),
            planificacion: puesto("A5", "Planificacion", ordenes(4, 3, 1, [{ motivo: "Objetivo fuera de alcance", veces: 1 }])),
          },
          observaciones: [
            "1 unidad(es) llegaron a menos del 25 % de combustible o municion (1ra Brigada de Infanteria) y no hubo ningun reabastecimiento: coordinar los convoyes y las bases (A4) antes de que la unidad quede inmovil.",
            "Relacion de intercambio favorable: 59 pts infligidos frente a 26 sufridos.",
            "Misiones aereas abortadas o fallidas (1) igualan o superan a las cumplidas (1): revisar el combustible, las rutas y la ventana de aterrizaje (A3).",
          ],
        },
        rojo: {
          ordenes: vacio(), turnos_pasivos: { cantidad: 3, turnos: [1, 2, 3] },
          logistica: { unidades_criticas: [], unidades_en_nivel_critico: 0, reabastecimientos: 0 },
          perdidas: { infligidas: 26, sufridas: 59, unidades_destruidas: 1, enemigas_destruidas: 0 },
          objetivos: { cumplidos: 0, fallidos: 1, pendientes: 0, puntos: 0 },
          misiones: { planificadas: 0, cumplidas: 0, abortadas: 0, fallidas: 0, canceladas: 0, en_curso: 0 },
          doctrina: doctrina({ reaccion: ["sin respuesta; 2 amenaza(s) sin respuesta", 0], inteligencia: ["40 % de las unidades enemigas detectadas (1 sensor(es) propio(s))", 40],
            logistica: ["0 unidad(es) en nivel crítico; 0 reabastecimiento(s)", 100], coordinacion: ["un solo puesto (Estado Mayor) condujo todo", null],
            economia: ["26 pts infligidos / 59 sufridos", 31], objetivos: ["0 de 1 cumplido(s)", 0], iniciativa: ["0 de 3 turno(s) con órdenes", 0] }),
          puestos: { inteligencia: puesto("A2", "Inteligencia", vacio()), operaciones: puesto("A3", "Operaciones en curso", vacio()), logistica: puesto("A4", "Logistica", vacio()), planificacion: puesto("A5", "Planificacion", vacio()) },
          observaciones: [
            "El bando no emitio ninguna orden durante el ejercicio.",
            "Las perdidas sufridas (59 pts) superan ampliamente a las infligidas (26 pts): revisar la relacion de fuerzas y el terreno antes de empenar.",
            "1 objetivo(s) fallido(s): contrastar el plan con los objetivos asignados.",
          ],
        },
      },
      // evaluacion por alumno (autor registrado en cada orden y mision) y lo que quedo sin autor, por bando
      alumnos: [
        { usuario_id: 2, username: "alfa", bando: "azul", asignado: true, puesto: "mando", sigla: "EM", puesto_nombre: "Estado Mayor",
          ordenes: ordenes(5, 4, 1, [{ motivo: "Objetivo fuera de alcance", veces: 1 }]),
          turnos_activos: { cantidad: 3, turnos: [1, 2, 3] }, turnos_pasivos: { cantidad: 0, turnos: [] },
          misiones: { planificadas: 2, cumplidas: 1, abortadas: 1, fallidas: 0, canceladas: 0, en_curso: 0 },
          observaciones: ["Misiones aereas abortadas o fallidas (1) igualan o superan a las cumplidas (1): revisar el combustible, las rutas y la ventana de aterrizaje (A3)."] },
        { usuario_id: 5, username: "carlos", bando: "azul", asignado: true, puesto: "logistica", sigla: "A4", puesto_nombre: "Logistica",
          ordenes: ordenes(1, 1, 0, []), turnos_activos: { cantidad: 1, turnos: [3] }, turnos_pasivos: { cantidad: 2, turnos: [1, 2] },
          misiones: { planificadas: 0, cumplidas: 0, abortadas: 0, fallidas: 0, canceladas: 0, en_curso: 0 },
          observaciones: ["2 turno(s) sin emitir ninguna orden (turno(s) 1, 2): mantener la iniciativa o dejar constancia de la decision de esperar."] },
        { usuario_id: 3, username: "bravo", bando: "rojo", asignado: true, puesto: "mando", sigla: "EM", puesto_nombre: "Estado Mayor",
          ordenes: vacio(), turnos_activos: { cantidad: 0, turnos: [] }, turnos_pasivos: { cantidad: 3, turnos: [1, 2, 3] },
          misiones: { planificadas: 1, cumplidas: 0, abortadas: 0, fallidas: 0, canceladas: 0, en_curso: 0 },
          observaciones: ["3 turno(s) sin emitir ninguna orden (turno(s) 1, 2, 3): mantener la iniciativa o dejar constancia de la decision de esperar."] },
      ],
      sin_autor: { azul: { ordenes: 1, misiones: 0 }, rojo: { ordenes: 0, misiones: 0 } },
      nota_alumnos: "Las ordenes y misiones anteriores a la version que registra su autor figuran como 'sin autor registrado'; las ordenes automaticas del motor (intercepciones, defensa antiaerea, ataques de mision) no se atribuyen a nadie.",
    };
  }

  function timeline() {
    const { turnos, cs } = historia();
    const series = new Map();
    for (const t of turnos) {
      for (const u of t.unidades) {
        const s = series.get(u.id) || { unidad_id: u.id, nombre: u.nombre, bando: u.bando, clase: u.clase, turnos: [], combustible: [], municion: [], fuerza: [], estado: [] };
        s.turnos.push(t.turno); s.combustible.push(u.combustible); s.municion.push(u.municion); s.fuerza.push(u.fuerza); s.estado.push(u.estado);
        series.set(u.id, s);
      }
    }
    const logi = (turno, unidad_id, variable, antes, despues, causas, subtipo, orden_ids = []) => ({
      id: `l${turno}-${unidad_id}-${variable}`, tipo: "logistico", subtipo, turno, unidad_id, unidad: UNIDADES.find((u) => u.id === unidad_id).nombre,
      bando: "azul", variable, antes, despues, delta: despues - antes, causas, orden_ids,
    });
    const ls = [
      logi(1, 1, "municion", 100, 75, ["combate"], "nivel_menor").id && logi(2, 1, "municion", 75, 15, ["combate"], "nivel_critico", [6]),
      logi(1, 2, "combustible", 100, 60, ["movimiento"], "caida_abrupta", [4]),
      logi(3, 2, "combustible", 55, 20, ["movimiento"], "caida_abrupta", [8]),
      logi(3, 7, "municion", 46, 38, ["combate"], "nivel_menor"),
      logi(3, 5, "carga", 60, 50, ["convoy"], "nivel_menor"),
    ].filter((e) => e.subtipo !== "nivel_menor");
    const ev = [
      ...cs.map((c) => ({ id: `c${c.id}`, tipo: "combate", subtipo: "ataque", ...c, efectos: c.efectos.split("; "), orden_id: c.id })),
      ...ls,
      { id: "e5", tipo: "evento", subtipo: "clima", turno: 3, texto: "El clima cambia a lluvia.", bando_destino: "todos" },
      { id: "e6", tipo: "evento", subtipo: "perdida", turno: 2, texto: "Caza R se quedo sin combustible y se perdio.", bando_destino: "rojo" },
    ].sort((a, b) => a.turno - b.turno);
    const corr = [
      { tipo: "consumo_en_combate", turno: 2, unidad_id: 1, logistico: "l2-1-municion", combate: "c2", detalle: "municion 75% -> 15%" },
      { tipo: "coincide_con_combate", turno: 3, unidad_id: 2, logistico: "l3-2-combustible", combate: "c3", detalle: "combustible 55% -> 20% (movimiento)" },
      { tipo: "combate_con_logistica_baja", turno: 3, unidad_id: 1, logistico: null, combate: "c3", detalle: "atacante con municion 15% al iniciar el turno" },
    ];
    return {
      escenario: { id: 1, nombre: ESC.nombre, estado: ESC.estado, turno_actual: 4, hora_inicio_min: 360 },
      ejes: { turnos: [0, 1, 2, 3], hora_inicio_min: 360, umbrales: { caida_abrupta: 30, nivel_critico: 25 } },
      series: [...series.values()], eventos: ev, correlaciones: corr,
      resumen: { combates: 3, caidas_abruptas: 2, niveles_criticos: 1, reabastecimientos: 0, ajustes_manuales: 0, correlaciones: 3, por_bando: {} },
    };
  }

  // ------------------------------------------------------------------ servidor simulado
  const sockets = new Set();
  const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json" } });
  const error = (detalle, status = 400) => json({ detail: detalle }, status);
  const enviarEstado = () => sockets.forEach((s) => s._emit(estadoPara()));
  const puedeVer = (g) => g.bando === "todos" || !BANDOS.includes(rolEfectivo()) || g.bando === rolEfectivo();
  const difundirGrafico = (m, g) => sockets.forEach((s) => { if (!g || puedeVer(g)) s._emit(m); });

  async function ruta(metodo, url, cuerpo) {
    const [path, qs] = url.split("?");
    const q = new URLSearchParams(qs || "");
    let m;
    if (path === "/api/auth/yo") return json(YO);
    if (path === "/api/auth/logout") return json({ ok: true });
    if (path === "/api/catalogo") { await cargaCatalogo; return json(CAT); }
    if (path === "/api/naciones") return json({ naciones: NACIONES });
    // regiones del mapa: las que realmente hay en el servidor de pruebas (misma carpeta que en produccion)
    if (path === "/api/terreno/mapas") {
      const ids = ["venezuela", "america", "mundo"];
      const metas = await Promise.all(ids.map((id) => REAL_FETCH(`/static/geo/${id}/fronteras.geojson`, { method: "HEAD" }).then((r) => (r.ok ? id : null)).catch(() => null)));
      const DEF = { venezuela: { nombre: "Venezuela y vecinos", bbox: [-73.5, 0.5, -59.5, 12.5], z: 9, z_min: 5, metros_por_pixel: 304, satelite: { z_min: 5, z_max: 12 } },
        america: { nombre: "América", bbox: [-170, -56, -30, 72], z: 7, z_min: 3, metros_por_pixel: 1178, satelite: { z_min: 3, z_max: 8 } },
        mundo: { nombre: "Mundo", bbox: [-180, -60, 180, 75], z: 6, z_min: 2, metros_por_pixel: 2366, satelite: null } };
      return json({ mapas: metas.filter(Boolean).map((id) => ({ id, ...DEF[id] })) });
    }
    if (path === "/api/plantillas" && metodo === "GET") {
      await cargaCatalogo;
      if (!PLANTILLAS.some((p) => p.origen === "codigo")) PLANTILLAS.unshift(...(CAT.plantillas || []));
      return json({ plantillas: PLANTILLAS });
    }
    // catalogo propio del instructor
    if (path === "/api/catalogo/modelos" && metodo === "POST") {
      await cargaCatalogo;
      if (ROL !== "instructor") return error("No autorizado para esta accion", 403);
      const clase = CAT.clases.find((c) => c.id === cuerpo.clase);
      if (!clase) return error("Elija una clase de unidad (no una base ni un misil)");
      const id = cuerpo.id || "u_" + cuerpo.nombre.toLowerCase().normalize("NFD").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
      const m = { ...clase, ...cuerpo, id, propio: true, foto: "", credito: { autor: "Catálogo propio del instructor", licencia: "—" }, fabricante: "-", funcion: clase.nombre, firma: clase.firma };
      CAT.modelos = CAT.modelos.filter((x) => x.id !== id).concat([m]);
      return json(m);
    }
    if ((m = path.match(/^\/api\/catalogo\/modelos\/([^/]+)$/)) && metodo === "DELETE") {
      await cargaCatalogo;
      CAT.modelos = CAT.modelos.filter((x) => x.id !== decodeURIComponent(m[1]));
      return json({ ok: true });
    }
    // comparacion de ejercicios (indicadores doctrinales y evolucion de cada alumno)
    if (path === "/api/evaluacion/comparar") return json(comparacion(q.get("ids") || "1"));
    if ((m = path.match(/^\/api\/plantillas\/([^/]+)$/)) && metodo === "DELETE") {
      if (ROL !== "instructor") return error("No autorizado para esta accion", 403);
      const i = PLANTILLAS.findIndex((p) => p.id === decodeURIComponent(m[1]));
      if (i < 0) return error("Plantilla desconocida", 404);
      if (PLANTILLAS[i].origen !== "usuario") return error("Las plantillas del sistema no se pueden eliminar");
      PLANTILLAS.splice(i, 1);
      return json({ ok: true, id: m[1] });
    }
    if (path === "/api/escenarios/1/guardar_plantilla" && metodo === "POST") {
      if (ROL !== "instructor") return error("No autorizado para esta accion", 403);
      const nombre = (cuerpo.nombre || "").trim();
      const id = nombre.toLowerCase().normalize("NFKD").replace(/\p{M}/gu, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);
      if (!id) return error("El nombre debe contener al menos una letra o un numero");
      const existente = PLANTILLAS.findIndex((p) => p.id === id);
      if (existente >= 0 && !cuerpo.reemplazar) return error(`Ya existe una plantilla con el identificador '${id}': cambie el nombre o marque 'reemplazar'`, 409);
      const p = { id, nombre, descripcion: cuerpo.descripcion || "", nacion_azul: ESC.nacion_azul, nacion_rojo: ESC.nacion_rojo, unidades: UNIDADES.filter((u) => u.estado !== "destruida").length, objetivos: objetivos.length, origen: "usuario", con_estado: !!cuerpo.con_estado, guardada_en: iso() };
      if (existente >= 0) PLANTILLAS[existente] = p; else PLANTILLAS.push(p);
      return json(p);
    }
    if (path.match(/^\/api\/plantillas\/[^/]+$/) && metodo === "POST") {
      if (ROL !== "instructor") return error("No autorizado para esta accion", 403);
      const id = 100 + Math.floor(Math.random() * 900);
      return json({ id, nombre: "Escenario de prueba (plantilla)", turno_actual: 1, fase: "decision", estado: "activo", clima: "despejado", azar: false, auto_resolver: false, hora_inicio_min: 120, nacion_azul: "venezuela", nacion_rojo: "estados_unidos", com_latencia_ms: 0, com_jitter_ms: 0, com_perdida_pct: 0 });
    }
    if (path === "/api/escenarios" && metodo === "GET") return json([ESC]);
    if (path === "/api/usuarios") return json([[1, "prof", "instructor"], [2, "alfa", "azul"], [3, "bravo", "rojo"], [4, "obs", "observador"]]
      .map(([id, username, rol]) => ({ id, username, rol, puesto: "mando", activo: true, aprobado: true, debe_cambiar_clave: false }))
      // una solicitud de cuenta pendiente (pantalla de acceso) y un alumno con contrasena provisional
      .concat([{ id: 5, username: "charlie", rol: "azul", puesto: "logistica", activo: true, aprobado: false, debe_cambiar_clave: false },
               { id: 6, username: "delta", rol: "rojo", puesto: "mando", activo: true, aprobado: true, debe_cambiar_clave: true }]));
    if (path === "/api/terreno/clase") return json({ clase: claseTerreno(parseFloat(q.get("lat"))) });
    if ((m = path.match(/^\/api\/escenarios\/1\/usuarios$/))) return json({ usuario_ids: [2, 3, 4] });
    if (path === "/api/escenarios/1/aar") return json(informe());
    if (path === "/api/escenarios/1/aar/replay") return json(replay());
    if (path === "/api/escenarios/1/aar/timeline") return json(timeline());
    if (path === "/api/escenarios/1/aar/rubrica") return json(rubrica());

    if (path === "/api/escenarios/1/ordenes/previsualizar") {
      const u = UNIDADES.find((x) => x.id === cuerpo.unidad_id);
      const ult = cuerpo.waypoints[cuerpo.waypoints.length - 1];
      return json({ ruta: [[u.lat, u.lon], ...cuerpo.waypoints], destino: ult, km: 14.2, combustible_restante: 41.3, llega: true, nota: "" });
    }
    if (path === "/api/escenarios/1/ordenes/lote" && metodo === "POST") {
      const resultados = [];
      for (const id of cuerpo.unidad_ids) {
        const r = await ruta("POST", "/api/escenarios/1/ordenes", { ...cuerpo.orden, unidad_id: id });
        const d = await r.json();
        resultados.push(r.ok ? { unidad_id: id, ok: true, orden_id: d.id } : { unidad_id: id, ok: false, detalle: d.detail });
      }
      return json({ resultados, emitidas: resultados.filter((x) => x.ok).length });
    }
    if (path === "/api/escenarios/1/ordenes" && metodo === "POST") {
      await cargaCatalogo;
      const u = UNIDADES.find((x) => x.id === cuerpo.unidad_id);
      if (!u || u.bando !== ROL) return error("Unidad no encontrada", 404);
      const cl = CAT.clases.find((c) => c.id === u.clase);
      if (cuerpo.tipo === "despegar") {
        if (!(cl.plazas_aeronaves > 0)) return error("Solo una base aerea o un portaaviones puede lanzar grupos de caza.");
        const m = CAT.modelos.find((x) => x.id === cuerpo.modelo);
        if (!m) return error("Elija un modelo de aeronave del catalogo.");
        if (u.tipo !== "base" && !m.embarcable) return error(`${m.nombre} no puede despegar de un portaaviones: solo helicopteros, drones y cazas embarcados operan desde un portaaviones.`);
        const en = UNIDADES.filter((x) => x.bando === ROL && x.tipo === "aerea" && x.estado === "activa").reduce((s, x) => s + (x.aeronaves || 1), 0);
        if (en + cuerpo.aeronaves > CAT.aeronaves.max_bando) return error(`Tope de ${CAT.aeronaves.max_bando} aeronaves por bando (${en} ya en servicio o comprometidas).`);
      }
      if (cuerpo.tipo === "lanzar") {
        if (!cl.lanza_misiles) return error("Esta unidad no puede lanzar misiles de crucero.");
        if (!cuerpo.misiles || cuerpo.misiles > 4) return error("Una salva tiene entre 1 y 4 misiles.");
        if (u.municion < 25 * cuerpo.misiles) return error(`Municion insuficiente para ${cuerpo.misiles} misil(es).`);
      }
      if (cl.misil) return error("Un misil en vuelo no admite ordenes.");
      if (u.transporte_id) return error("La unidad viaja a bordo de un transporte: primero debe desembarcar");
      if (cuerpo.tipo === "embarcar" && !UNIDADES.some((t) => t.id === cuerpo.objetivo_unidad_id && t.bando === ROL)) return error("Elija un transporte propio", 404);
      if (cuerpo.tipo === "construir" && !cl.construye) return error("Solo los ingenieros pueden construir puentes y vados");
      if (cuerpo.tipo === "interferir" && !(cl.interferencia_km > 0)) return error("Solo las unidades de guerra electronica pueden interferir.");
      ordenes = ordenes.filter((o) => !(o.unidad_id === u.id && o.estado === "pendiente"));
      const detalle = cuerpo.tipo === "despegar" ? JSON.stringify({ modelo: cuerpo.modelo, aeronaves: cuerpo.aeronaves, indicativo: cuerpo.indicativo || "" })
        : cuerpo.tipo === "lanzar" ? JSON.stringify({ misiles: cuerpo.misiles || 1 }) : cuerpo.detalle || "";
      const o = { id: proximaOrden++, escenario_id: 1, unidad_id: u.id, tipo: cuerpo.tipo, objetivo_unidad_id: cuerpo.objetivo_unidad_id, waypoints: cuerpo.waypoints || [], detalle, turno_emitida: ESC.turno_actual, estado: "pendiente", resultado: "", autor: YO.username, autor_puesto: PUESTO };
      ordenes.push(o);
      ESC[`listo_${ROL}`] = false;
      enviarEstado();
      return json(o);
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/ordenes\/(\d+)$/)) && metodo === "DELETE") {
      ordenes = ordenes.filter((o) => o.id !== parseInt(m[1], 10));
      enviarEstado();
      return json({ ok: true });
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/unidades\/(\d+)\/defensa$/)) && metodo === "POST") {
      await cargaCatalogo;
      const u = UNIDADES.find((x) => x.id === parseInt(m[1], 10));
      if (!u || (ROL !== "instructor" && u.bando !== ROL)) return error("Unidad no encontrada", 404);
      const cl = CAT.clases.find((c) => c.id === u.clase) || {};
      if (cuerpo.emitiendo !== undefined && !cl.emisor) return error("Esta unidad no tiene radar");
      if (cuerpo.fuego_libre !== undefined && !cl.defensa_aerea) return error("Solo la defensa antiaerea tiene fuego automatico");
      if (cuerpo.emitiendo !== undefined) u.emitiendo = cuerpo.emitiendo;
      if (cuerpo.fuego_libre !== undefined) u.fuego_libre = cuerpo.fuego_libre;
      enviarEstado();
      return json(completar(u));
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/unidades\/(\d+)\/perfil$/)) && metodo === "POST") {
      const u = UNIDADES.find((x) => x.id === parseInt(m[1], 10));
      if (!u || (ROL !== "instructor" && u.bando !== ROL)) return error("Unidad no encontrada", 404);
      if (!(u.perfiles_permitidos || []).includes(cuerpo.perfil_vuelo)) return error("Esta aeronave no puede volar en ese perfil");
      u.perfil_actual = cuerpo.perfil_vuelo;
      enviarEstado();
      return json(completar(u));
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/unidades\/(\d+)\/cobertura$/))) {
      const u = UNIDADES.find((x) => x.id === parseInt(m[1], 10));
      if (!u || (BANDOS.includes(ROL) && u.bando !== ROL)) return error("Unidad no encontrada", 404);
      return json(COBERTURAS[u.id] || { disponible: false, perfiles: {} });
    }
    if (path === "/api/escenarios/1/misiones/previsualizar" && metodo === "POST") { await cargaCatalogo; return json(previsualizarMision(cuerpo)); }
    if (path === "/api/escenarios/1/misiones" && metodo === "POST") {
      await cargaCatalogo;
      const r = previsualizarMision(cuerpo);
      if (r.errores.length) return error(r.errores.join(" "));
      const rol = CAT.misiones.roles.find((x) => x.id === cuerpo.rol);
      const mi = { id: proximaMision++, bando: ROL, rol: cuerpo.rol, rol_nombre: rol ? rol.nombre : cuerpo.rol, nombre: cuerpo.nombre || "", estado: "programada",
        unidad_id: cuerpo.unidad_id ?? null, base_id: cuerpo.base_id ?? null, modelo: cuerpo.modelo || "", aeronaves: cuerpo.aeronaves || 0,
        turno_despegue: r.turno_despegue, creada_turno: ESC.turno_actual, puntos: r.puntos, plan: r.plan, indice: 0, espera: -1, resultado: "Programada.", autor: YO.username, autor_puesto: PUESTO };
      misiones.push(mi);
      ESC[`listo_${ROL}`] = false;
      enviarEstado();
      return json(mi);
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/misiones\/(\d+)$/)) && metodo === "DELETE") {
      const mi = misiones.find((x) => x.id === parseInt(m[1], 10));
      if (!mi) return error("Mision no encontrada", 404);
      if (mi.estado === "en_curso") { mi.resultado = "Abortada: regresa al Aeropuerto de Barinas."; } else { mi.estado = "cancelada"; mi.resultado = "Cancelada antes de iniciarse."; }
      enviarEstado();
      return json(mi);
    }
    if (path === "/api/escenarios/1/listo") { ESC[`listo_${ROL}`] = cuerpo.listo; enviarEstado(); return json(estadoPara()); }
    if (path === "/api/escenarios/1/avanzar_turno") {
      for (const o of ordenes.filter((x) => x.tipo === "despegar" && x.estado === "pendiente")) {
        const base = UNIDADES.find((x) => x.id === o.unidad_id);
        const d = JSON.parse(o.detalle);
        const m = CAT.modelos.find((x) => x.id === d.modelo);
        UNIDADES.push(base_(900 + o.id, d.indicativo || `${m.corto} de ${base.nombre}`, base.bando, "caza", base.lat + 0.018, base.lon + 0.018, { modelo: d.modelo, aeronaves: d.aeronaves, echelon: d.aeronaves <= 2 ? "equipo" : d.aeronaves <= 4 ? "escuadra" : "seccion" }));
        o.estado = "resuelta";
        o.resultado = `Despego de ${base.nombre}; podra recibir ordenes el proximo turno.`;
      }
      ESC.turno_actual += 1; ESC.listo_azul = ESC.listo_rojo = false; enviarEstado(); return json(estadoPara()); }
    if (path === "/api/escenarios/1/pausar") { ESC.estado = "pausado"; enviarEstado(); return json(estadoPara()); }
    if (path === "/api/escenarios/1/reanudar") { ESC.estado = "activo"; enviarEstado(); return json(estadoPara()); }
    if (path === "/api/escenarios/1/finalizar") { ESC.estado = "finalizado"; enviarEstado(); return json(estadoPara()); }
    if (path === "/api/escenarios/1/config" && metodo === "PATCH") {
      Object.assign(ESC, Object.fromEntries(Object.entries(cuerpo).filter(([k]) => k !== "hora_inicio")));
      if ("nacion_azul" in cuerpo || "nacion_rojo" in cuerpo) {
        eventos.unshift({ id: eventos.length + 10, escenario_id: 1, turno: ESC.turno_actual, tipo: "ajuste",
          descripcion: `Configuracion: bando Azul representa a ${cuerpo.nacion_azul || "(nadie)"}, bando Rojo a ${cuerpo.nacion_rojo || "(nadie)"}` });
      }
      if (cuerpo.hora_inicio) { const [h, mm] = cuerpo.hora_inicio.split(":"); ESC.hora_inicio_min = +h * 60 + +mm; }
      enviarEstado();
      return json(estadoPara());
    }
    if (path === "/api/escenarios/1/clima/zonas" && metodo === "POST") {
      const z = { id: ZONAS_CLIMA.length + 1, tipo: cuerpo.tipo, lat: cuerpo.lat, lon: cuerpo.lon, radio_km: cuerpo.radio_km || 60, deriva_rumbo: cuerpo.deriva_rumbo || 0, deriva_kmh: cuerpo.deriva_kmh || 0, hasta_turno: cuerpo.turnos ? ESC.turno_actual + cuerpo.turnos : null, nombre: cuerpo.nombre || "" };
      ZONAS_CLIMA.push(z); enviarEstado(); return json(z);
    }
    if (path.startsWith("/api/escenarios/1/clima/zonas/") && metodo === "DELETE") {
      const id = parseInt(path.split("/").pop(), 10); const i = ZONAS_CLIMA.findIndex((z) => z.id === id); if (i >= 0) ZONAS_CLIMA.splice(i, 1); enviarEstado(); return json({ ok: true });
    }
    if (path === "/api/escenarios/1/eventos") {
      eventos.unshift({ id: eventos.length + 10, escenario_id: 1, turno: ESC.turno_actual, tipo: cuerpo.tipo || "general", descripcion: cuerpo.descripcion, bando_destino: cuerpo.bando_destino });
      if (cuerpo.lat !== undefined && cuerpo.lat !== null) INFORMES.push({ id: 600 + INFORMES.length, turno: ESC.turno_actual, tipo: cuerpo.tipo || "inteligencia", descripcion: cuerpo.descripcion, lat: cuerpo.lat, lon: cuerpo.lon, hasta_turno: ESC.turno_actual + (cuerpo.turnos || 3), fuente: cuerpo.fuente || "" });
      enviarEstado(); return json({});
    }

    if (path === "/api/escenarios/1/graficos" && metodo === "POST") {
      if (!["azul", "rojo", "instructor"].includes(ROL)) return error("No autorizado para esta accion", 403);
      const bando = ROL === "instructor" ? cuerpo.bando || "todos" : ROL;
      const g = { id: proximoGrafico++, bando, tipo: cuerpo.tipo, etiqueta: cuerpo.etiqueta, geometria: cuerpo.geometria, autor: YO.username, turno: ESC.turno_actual };
      graficos.push(g);
      difundirGrafico({ tipo: "grafico", accion: "crear", grafico: g }, g);
      return json(g);
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/graficos\/(\d+)$/)) && metodo === "DELETE") {
      const id = parseInt(m[1], 10);
      const g = graficos.find((x) => x.id === id);
      if (!g || (ROL !== "instructor" && g.bando !== ROL)) return error("Grafico no encontrado", 404);
      graficos = graficos.filter((x) => x.id !== id);
      difundirGrafico({ tipo: "grafico", accion: "borrar", id }, g);
      return json({ ok: true });
    }
    if (path === "/api/escenarios/1/objetivos" && metodo === "POST") {
      if (ROL !== "instructor") return error("No autorizado para esta accion", 403);
      const o = { id: proximoObjetivo++, unidad_nombre: (UNIDADES.find((u) => u.id === cuerpo.unidad_id) || {}).nombre || "", progreso: 0, estado: "pendiente", turno_resuelto: null, lat: null, lon: null, unidad_id: null, hasta_turno: null, radio_km: 5, turnos_requeridos: 1, ...cuerpo };
      objetivos.push(o);
      enviarEstado();
      return json(o);
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/objetivos\/(\d+)$/)) && metodo === "DELETE") {
      objetivos = objetivos.filter((o) => o.id !== parseInt(m[1], 10));
      enviarEstado();
      return json({ ok: true });
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/unidades\/(\d+)$/)) && metodo === "DELETE") {
      const id = parseInt(m[1], 10);
      if (id === 11) return error("Esta unidad ya participo en combates y consta en el informe: marquela como destruida en lugar de borrarla", 409);
      UNIDADES.splice(UNIDADES.findIndex((u) => u.id === id), 1);
      enviarEstado();
      return json({ ok: true });
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/unidades\/(\d+)$/)) && metodo === "PATCH") {
      const u = UNIDADES.find((x) => x.id === parseInt(m[1], 10));
      if (cuerpo.lat > 12) return error("Esta unidad no puede ubicarse en el agua");
      Object.assign(u, cuerpo);
      enviarEstado();
      return json(u);
    }
    if (path.startsWith("/api/escenarios/1/unidades")) return json({});
    return error(`El arnes no simula ${metodo} ${path}`, 404);
  }

  window.fetch = async (url, opts = {}) => {
    const u = String(url);
    if (!u.startsWith("/api/")) return REAL_FETCH(url, opts);
    await new Promise((r) => setTimeout(r, 20));
    return ruta((opts.method || "GET").toUpperCase(), u, opts.body ? JSON.parse(opts.body) : undefined);
  };

  // ------------------------------------------------------------------ chat simulado (misma logica que el servidor)
  function manejarChat(sock, d) {
    const canales = ROL === "instructor" ? ["azul", "rojo", "todos"] : BANDOS.includes(ROL) ? ["bando", "mando"] : [];
    const texto = String(d.texto || "").trim();
    if (!canales.includes(d.canal)) return sock._emit({ tipo: "chat_error", detalle: "No tiene acceso a ese canal de comunicaciones." });
    if (!texto) return sock._emit({ tipo: "chat_error", detalle: "El mensaje esta vacio." });
    const canal = d.canal === "bando" ? ROL : d.canal;
    const lados = canal === "azul" || canal === "rojo" ? [canal] : canal === "todos" ? BANDOS : [ROL];
    const decidir = () => ({ perdido: Math.random() * 100 < ESC.com_perdida_pct, demora_ms: ESC.com_latencia_ms + Math.floor(Math.random() * (ESC.com_jitter_ms + 1)) });
    const dec = Object.fromEntries(lados.map((l) => [l, decidir()]));
    const msg = { id: proximoMensaje++, canal, remitente: YO.username, rol: ROL, texto, turno: ESC.turno_actual, creado_en: iso() + "Z" };
    mensajes.push(msg);
    sock._emit({ tipo: "chat", mensaje: ROL === "instructor" ? { ...msg, entrega: dec } : msg });
    // un companero simulado responde por la red del bando, con la misma interferencia
    if (BANDOS.includes(ROL) && canal === ROL) {
      const r = decidir();
      if (!r.perdido) setTimeout(() => sock._emit({ tipo: "chat", mensaje: { id: proximoMensaje++, canal: ROL, remitente: "companero", rol: ROL, texto: `Recibido: ${texto}`, turno: ESC.turno_actual, creado_en: iso() + "Z" } }), 600 + r.demora_ms);
    }
  }

  window.WebSocket = class WebSocketFalso {
    constructor() {
      this.readyState = 0;
      sockets.add(this);
      setTimeout(async () => {
        await cargaCatalogo;
        this.readyState = 1;
        if (this.onopen) this.onopen();
        this._emit(estadoPara());
        this._emit({ tipo: "chat_historial", mensajes: mensajes.filter((m) => ROL === "instructor" || m.canal === ROL || m.canal === "todos").map((m) => ({ tipo: "chat", mensaje: m })) });
      }, 30);
    }
    _emit(obj) { if (this.readyState === 1 && this.onmessage) this.onmessage({ data: JSON.stringify(obj) }); }
    send(texto) {
      if (texto === "ping" || !texto.startsWith("{")) return;
      const d = JSON.parse(texto);
      if (d.tipo === "chat") manejarChat(this, d);
      else if (d.vista) { vista = d.vista === "completa" ? null : d.vista; this._emit(estadoPara()); }
    }
    close() { this.readyState = 3; sockets.delete(this); }
  };

  document.addEventListener("DOMContentLoaded", () => {
    const aviso = document.createElement("div");
    aviso.textContent = `ARNÉS DE PRUEBAS · rol: ${ROL}${BANDOS.includes(ROL) ? ` · puesto: ${PUESTO}` : ""} · datos simulados`;
    aviso.style.cssText = "position:fixed;left:8px;bottom:2px;z-index:9999;font:10px system-ui;color:#ffb703;background:rgba(0,0,0,.7);padding:1px 8px;border-radius:3px;pointer-events:none";
    document.body.appendChild(aviso);
    // &abrir=informe|replay|rubrica abre el informe (y el replay animado, o el dialogo Rubrica) al cargar;
    // &instante=1.5 deja el replay detenido en ese punto (en turnos) para capturas reproducibles
    const abrir = params.get("abrir");
    if (abrir === "informe" || abrir === "replay" || abrir === "rubrica") {
      const esperar = (cond, luego, intentos = 40) => {
        if (cond()) return luego();
        if (intentos > 0) setTimeout(() => esperar(cond, luego, intentos - 1), 150);
      };
      // el boton Informe no hace nada hasta que app.js termina de arrancar: se insiste hasta que el panel aparece
      const intentarInforme = () => { if (!document.getElementById("app").hidden) document.getElementById("btn-informe").click(); return !document.getElementById("replay").hidden; };
      esperar(intentarInforme, () => {
        if (abrir === "rubrica") return document.getElementById("rp-rubrica").click();
        if (abrir !== "replay") return;
        esperar(() => !document.getElementById("replay").hidden, () => {
          document.getElementById("rp-replay").click();
          const instante = parseFloat(params.get("instante"));
          if (!Number.isFinite(instante)) return;
          esperar(() => !document.getElementById("replay-anim").hidden, () => {
            const barra = document.getElementById("ra-progreso");
            barra.value = String(Math.round(instante * 1000));
            barra.dispatchEvent(new Event("input", { bubbles: true }));
          });
        });
      });
    }
  });
})();
