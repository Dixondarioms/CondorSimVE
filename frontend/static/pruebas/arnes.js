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
    id: 1, nombre: "Arnés: ejercicio de prueba", turno_actual: 3, fase: "decision", estado: "activo", clima: "lluvia",
    azar: true, auto_resolver: false, limite_decision_seg: 1200, decision_termina_en: iso(18 * 60000 + 32000),
    listo_azul: false, listo_rojo: true, archivado: false, hora_inicio_min: 360,
    com_latencia_ms: 1500, com_jitter_ms: 500, com_perdida_pct: 30,
    nacion_azul: "venezuela", nacion_rojo: "colombia",
  };
  const NACIONES = [
    { id: "venezuela", nombre: "Venezuela", gentilicio: "venezolano", capital: "Caracas", colores: ["#FFCC00", "#00247D", "#CF142B"] },
    { id: "colombia", nombre: "Colombia", gentilicio: "colombiano", capital: "Bogotá", colores: ["#FCD116", "#003893", "#CE1126"] },
    { id: "brasil", nombre: "Brasil", gentilicio: "brasileño", capital: "Brasilia", colores: ["#009C3B", "#FFDF00", "#002776"] },
    { id: "guyana", nombre: "Guyana", gentilicio: "guyanés", capital: "Georgetown", colores: ["#009E49", "#FCD116", "#CE1126"] },
    { id: "trinidad_tobago", nombre: "Trinidad y Tobago", gentilicio: "trinitense", capital: "Puerto España", colores: ["#CE1126", "#000000", "#FFFFFF"] },
    { id: "estados_unidos", nombre: "Estados Unidos", gentilicio: "estadounidense", capital: "Washington D. C.", colores: ["#B22234", "#FFFFFF", "#3C3B6E"] },
  ];
  const base_ = (...a) => base(...a);
  const base = (id, nombre, bando, clase, lat, lon, x = {}) => ({
    id, escenario_id: 1, nombre, bando, clase, lat, lon, fuerza: 100, combustible: 100, municion: 100,
    carga: 0, recarga_restante: 0, despliegue_restante: 0, estado: "activa", echelon: "", terreno: "llano",
    modelo: "", aeronaves: 1, en_tierra: false, base_id: null, espera_restante: 0, mision: "", mision_lat: null, mision_lon: null, ...x,
  });
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
    base(15, "Cobra 1", "azul", "caza", 8.556, -70.494, { modelo: "f16", aeronaves: 2, echelon: "equipo", en_tierra: true, base_id: 9, espera_restante: 1 }),
    base(9, "Base Aérea Barinas", "azul", "base_aerea", 8.550, -70.500),
    base(11, "Infantería Roja", "rojo", "infanteria", 8.660, -70.600, { fuerza: 70 }),
    base(12, "Depósito R", "rojo", "deposito", 8.700, -70.620),
    base(13, "Caza R", "rojo", "caza", 8.750, -70.500, { modelo: "su30", aeronaves: 2 }),
    base(14, "Recon Roja", "rojo", "reconocimiento", 9.600, -69.800),
    base(16, "GE Escucha 1", "azul", "guerra_electronica", 8.580, -70.640),
    base(17, "Vigía 1", "azul", "dron_reconocimiento", 8.640, -70.470, { modelo: "uav_reco", aeronaves: 1, echelon: "equipo" }),
    base(18, "Radar Rojo", "rojo", "radar", 8.720, -70.560),
  ];
  // zona de interferencia roja vigente (la emitio el turno anterior) sobre parte del despliegue azul
  const INTERFERENCIAS = [{ id: 1, bando: "rojo", unidad_id: 13, lat: 8.63, lon: -70.49, radio_km: 12, turno: 2 }];
  // misiones aereas: una CAP en orbita, una interdiccion programada (azul) y una SEAD roja que azul no debe ver
  let misiones = [
    { id: 1, bando: "azul", rol: "CAP", rol_nombre: "Patrulla aerea de combate (CAP)", nombre: "Flecha", estado: "en_curso", unidad_id: 10, base_id: null, modelo: "su30", aeronaves: 2, turno_despegue: 2, creada_turno: 2,
      puntos: [{ tipo: "orbita", lat: 8.75, lon: -70.3, turnos: 3 }, { tipo: "aterrizaje", lat: 8.55, lon: -70.5, base_id: 9 }],
      plan: { puntos: [{ tipo: "orbita", km: 32, llegada_h: 0.03, combustible_llegada: 99, salida_h: 4, combustible_salida: 75 }, { tipo: "aterrizaje", km: 31, llegada_h: 4.03, combustible_llegada: 74 }], duracion_h: 4.03, combustible_final: 74, advertencias: [] },
      indice: 0, espera: 2, resultado: "En orbita: 2 turno(s) mas." },
    { id: 2, bando: "azul", rol: "INTERDICCION", rol_nombre: "Interdiccion (ataque a un blanco)", nombre: "Rayo", estado: "programada", unidad_id: null, base_id: 9, modelo: "f16", aeronaves: 2, turno_despegue: 5, creada_turno: 3,
      puntos: [{ tipo: "paso", lat: 8.60, lon: -70.66 }, { tipo: "blanco", lat: 8.66, lon: -70.60, objetivo_unidad_id: 11 }, { tipo: "aterrizaje", lat: 8.55, lon: -70.5, base_id: 9 }],
      plan: { puntos: [{ tipo: "paso", km: 18, llegada_h: 0.02, combustible_llegada: 99 }, { tipo: "blanco", km: 9, llegada_h: 0.03, combustible_llegada: 98.6, salida_h: 1 }, { tipo: "aterrizaje", km: 16, llegada_h: 1.02, combustible_llegada: 97.7 }], duracion_h: 1.02, combustible_final: 97.7, advertencias: [] },
      indice: 0, espera: -1, resultado: "Programada." },
    { id: 3, bando: "rojo", rol: "SEAD", rol_nombre: "Supresion de defensas aereas (SEAD)", nombre: "Víbora", estado: "programada", unidad_id: null, base_id: 12, modelo: "su30", aeronaves: 2, turno_despegue: 4, creada_turno: 3,
      puntos: [{ tipo: "blanco", lat: 8.588, lon: -70.55 }, { tipo: "aterrizaje", lat: 8.7, lon: -70.62, base_id: 12 }],
      plan: { puntos: [{ tipo: "blanco", km: 13, llegada_h: 0.01, combustible_llegada: 99.6, salida_h: 1 }, { tipo: "aterrizaje", km: 13, llegada_h: 1.01, combustible_llegada: 99.1 }], duracion_h: 1.01, combustible_final: 99.1, advertencias: [] },
      indice: 0, espera: -1, resultado: "Programada." },
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
    { id: 1, escenario_id: 1, unidad_id: 2, tipo: "mover", objetivo_unidad_id: null, waypoints: [[8.600, -70.570], [8.620, -70.550]], detalle: "", turno_emitida: 3, estado: "pendiente", resultado: "" },
    { id: 2, escenario_id: 1, unidad_id: 3, tipo: "atacar", objetivo_unidad_id: 11, waypoints: [], detalle: "", turno_emitida: 3, estado: "pendiente", resultado: "" },
    { id: 3, escenario_id: 1, unidad_id: 4, tipo: "construir", objetivo_unidad_id: null, waypoints: [[8.605, -70.580]], detalle: "puente", turno_emitida: 3, estado: "pendiente", resultado: "" },
    { id: 4, escenario_id: 1, unidad_id: 1, tipo: "atacar", objetivo_unidad_id: 11, waypoints: [], detalle: "", turno_emitida: 2, estado: "resuelta", resultado: "Ataque a Infantería Roja. Ratio 1.32: defensor pierde 19.0%, atacante pierde 12.0%. Efectos: clima x0.80 al ataque; sorpresa (atacante no detectado) x1.20." },
  ];
  let proximaOrden = 5;
  let objetivos = [
    { id: 1, bando: "azul", tipo: "ocupar", nombre: "Tomar el puente", puntos: 40, lat: 8.63, lon: -70.52, radio_km: 4, turnos_requeridos: 3, progreso: 1, unidad_id: null, unidad_nombre: "", hasta_turno: null, estado: "pendiente", turno_resuelto: null },
    { id: 2, bando: "azul", tipo: "destruir", nombre: "Neutralizar la infantería enemiga", puntos: 50, lat: null, lon: null, radio_km: 5, turnos_requeridos: 1, progreso: 0, unidad_id: 11, unidad_nombre: "Infantería Roja", hasta_turno: null, estado: "pendiente", turno_resuelto: null },
    { id: 3, bando: "azul", tipo: "proteger", nombre: "Mantener la base", puntos: 30, lat: null, lon: null, radio_km: 5, turnos_requeridos: 1, progreso: 0, unidad_id: 9, unidad_nombre: "Base Aérea Barinas", hasta_turno: 8, estado: "cumplido", turno_resuelto: 2 },
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
  const OCULTOS = ["fuerza", "velocidad_kmh", "alcance_km", "deteccion_km", "combustible", "municion", "autonomia_km", "carga", "recarga_restante", "despliegue_restante", "modelo", "aeronaves", "base_id", "espera_restante", "mision", "mision_lat", "mision_lon"];
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
    if (path === "/api/plantillas" && metodo === "GET") {
      return json({ plantillas: [
        { id: "demo_llanos", nombre: "Demo: Piedemonte andino - Llanos", descripcion: "Escenario de práctica genérico.", nacion_azul: "venezuela", nacion_rojo: "", unidades: 9, objetivos: 0 },
        { id: "defensa_3_enero_2026", nombre: "3 de enero de 2026 (estudio): defensa del litoral central", descripcion: "Ejercicio de estudio para practicar la defensa del litoral central. Simplificado; no es una reconstrucción histórica precisa.", nacion_azul: "venezuela", nacion_rojo: "estados_unidos", unidades: 9, objetivos: 8 },
      ] });
    }
    if (path.match(/^\/api\/plantillas\/[^/]+$/) && metodo === "POST") {
      if (ROL !== "instructor") return error("No autorizado para esta accion", 403);
      const id = 100 + Math.floor(Math.random() * 900);
      return json({ id, nombre: "Escenario de prueba (plantilla)", turno_actual: 1, fase: "decision", estado: "activo", clima: "despejado", azar: false, auto_resolver: false, hora_inicio_min: 120, nacion_azul: "venezuela", nacion_rojo: "estados_unidos", com_latencia_ms: 0, com_jitter_ms: 0, com_perdida_pct: 0 });
    }
    if (path === "/api/escenarios" && metodo === "GET") return json([ESC]);
    if (path === "/api/usuarios") return json([[1, "prof", "instructor"], [2, "alfa", "azul"], [3, "bravo", "rojo"], [4, "obs", "observador"]].map(([id, username, rol]) => ({ id, username, rol, puesto: "mando", activo: true })));
    if (path === "/api/terreno/clase") return json({ clase: claseTerreno(parseFloat(q.get("lat"))) });
    if ((m = path.match(/^\/api\/escenarios\/1\/usuarios$/))) return json({ usuario_ids: [2, 3, 4] });
    if (path === "/api/escenarios/1/aar") return json(informe());
    if (path === "/api/escenarios/1/aar/timeline") return json(timeline());

    if (path === "/api/escenarios/1/ordenes/previsualizar") {
      const u = UNIDADES.find((x) => x.id === cuerpo.unidad_id);
      const ult = cuerpo.waypoints[cuerpo.waypoints.length - 1];
      return json({ ruta: [[u.lat, u.lon], ...cuerpo.waypoints], destino: ult, km: 14.2, combustible_restante: 41.3, llega: true, nota: "" });
    }
    if (path === "/api/escenarios/1/ordenes" && metodo === "POST") {
      await cargaCatalogo;
      const u = UNIDADES.find((x) => x.id === cuerpo.unidad_id);
      if (!u || u.bando !== ROL) return error("Unidad no encontrada", 404);
      const cl = CAT.clases.find((c) => c.id === u.clase);
      if (cuerpo.tipo === "despegar") {
        if (u.clase !== "base_aerea") return error("Solo una base aerea puede lanzar grupos de caza.");
        if (!CAT.modelos.some((m) => m.id === cuerpo.modelo)) return error("Elija un modelo de aeronave del catalogo.");
        const en = UNIDADES.filter((x) => x.bando === ROL && x.tipo === "aerea" && x.estado === "activa").reduce((s, x) => s + (x.aeronaves || 1), 0);
        if (en + cuerpo.aeronaves > CAT.aeronaves.max_bando) return error(`Tope de ${CAT.aeronaves.max_bando} aeronaves por bando (${en} ya en servicio o comprometidas).`);
      }
      if (cuerpo.tipo === "construir" && !cl.construye) return error("Solo los ingenieros pueden construir puentes y vados");
      if (cuerpo.tipo === "interferir" && !(cl.interferencia_km > 0)) return error("Solo las unidades de guerra electronica pueden interferir.");
      ordenes = ordenes.filter((o) => !(o.unidad_id === u.id && o.estado === "pendiente"));
      const detalle = cuerpo.tipo === "despegar" ? JSON.stringify({ modelo: cuerpo.modelo, aeronaves: cuerpo.aeronaves, indicativo: cuerpo.indicativo || "" }) : cuerpo.detalle || "";
      const o = { id: proximaOrden++, escenario_id: 1, unidad_id: u.id, tipo: cuerpo.tipo, objetivo_unidad_id: cuerpo.objetivo_unidad_id, waypoints: cuerpo.waypoints || [], detalle, turno_emitida: ESC.turno_actual, estado: "pendiente", resultado: "" };
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
    if (path === "/api/escenarios/1/misiones/previsualizar" && metodo === "POST") { await cargaCatalogo; return json(previsualizarMision(cuerpo)); }
    if (path === "/api/escenarios/1/misiones" && metodo === "POST") {
      await cargaCatalogo;
      const r = previsualizarMision(cuerpo);
      if (r.errores.length) return error(r.errores.join(" "));
      const rol = CAT.misiones.roles.find((x) => x.id === cuerpo.rol);
      const mi = { id: proximaMision++, bando: ROL, rol: cuerpo.rol, rol_nombre: rol ? rol.nombre : cuerpo.rol, nombre: cuerpo.nombre || "", estado: "programada",
        unidad_id: cuerpo.unidad_id ?? null, base_id: cuerpo.base_id ?? null, modelo: cuerpo.modelo || "", aeronaves: cuerpo.aeronaves || 0,
        turno_despegue: r.turno_despegue, creada_turno: ESC.turno_actual, puntos: r.puntos, plan: r.plan, indice: 0, espera: -1, resultado: "Programada." };
      misiones.push(mi);
      ESC[`listo_${ROL}`] = false;
      enviarEstado();
      return json(mi);
    }
    if ((m = path.match(/^\/api\/escenarios\/1\/misiones\/(\d+)$/)) && metodo === "DELETE") {
      const mi = misiones.find((x) => x.id === parseInt(m[1], 10));
      if (!mi) return error("Mision no encontrada", 404);
      if (mi.estado === "en_curso") { mi.resultado = "Abortada: regresa a Base Aérea Barinas."; } else { mi.estado = "cancelada"; mi.resultado = "Cancelada antes de iniciarse."; }
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
    if (path === "/api/escenarios/1/eventos") { eventos.unshift({ id: eventos.length + 10, escenario_id: 1, turno: ESC.turno_actual, tipo: "general", descripcion: cuerpo.descripcion, bando_destino: cuerpo.bando_destino }); enviarEstado(); return json({}); }

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
  });
})();
