/* Logica pura del cliente (sin DOM ni Leaflet): se prueba con `node --test frontend/tests`. */
(function (raiz) {
  "use strict";

  const BANDOS = ["azul", "rojo"];
  const esBando = (rol) => BANDOS.includes(rol);

  const pct = (v) => (v === null || v === undefined ? "?" : `${Math.round(v)}%`);

  /** "2026-09-24T21:00:00" (UTC sin zona, como lo envia el servidor) -> ms desde epoch. */
  function fechaUtc(iso) {
    if (!iso) return null;
    const t = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
    return Number.isNaN(t) ? null : t;
  }

  /** Segundos que faltan para `terminaEn`, corrigiendo la diferencia entre el reloj del
   *  servidor (ahoraServidor, recibido con el estado) y el del cliente (ahoraCliente). */
  function segundosRestantes(terminaEn, ahoraServidor, ahoraCliente, ahoraCliente2 = Date.now()) {
    const fin = fechaUtc(terminaEn);
    const srv = fechaUtc(ahoraServidor);
    if (fin === null) return null;
    const desfase = srv === null ? 0 : srv - ahoraCliente; // reloj servidor - reloj cliente al recibir
    return Math.max(0, Math.ceil((fin - (ahoraCliente2 + desfase)) / 1000));
  }

  function formatoTiempo(seg) {
    if (seg === null || seg === undefined) return "";
    const h = Math.floor(seg / 3600);
    const m = Math.floor((seg % 3600) / 60);
    const s = seg % 60;
    const dos = (n) => String(n).padStart(2, "0");
    return h > 0 ? `${h}:${dos(m)}:${dos(s)}` : `${dos(m)}:${dos(s)}`;
  }

  /** Objetivos que puede elegir un alumno: enemigos para atacar, otras unidades propias para apoyar. */
  function objetivosDisponibles(unidades, rol, tipoOrden, unidadId) {
    const activas = unidades.filter((u) => u.estado === "activa");
    if (tipoOrden === "apoyar") {
      return activas.filter((u) => u.bando === rol && u.tipo !== "base" && String(u.id) !== String(unidadId));
    }
    if (tipoOrden === "lanzar") { // un misil de crucero no persigue aeronaves en vuelo
      return activas.filter((u) => u.bando !== rol && (u.tipo !== "aerea" || u.en_tierra));
    }
    return activas.filter((u) => u.bando !== rol);
  }

  /** Unidades propias que pueden recibir ordenes (las bases no se mueven ni combaten; los misiles vuelan solos). */
  function unidadesConOrdenes(unidades, rol) {
    return unidades.filter((u) => u.estado === "activa" && u.bando === rol && u.tipo !== "base" && !esMisil(u) && !embarcada(u));
  }

  // ---------------------------------------------------------------- buques, portaaviones y misiles de crucero
  const PLAZAS_AERONAVES = { base_aerea: 12, portaaviones: 10 }; // igual que el catalogo del servidor
  const PISTA_INOPERATIVA = 60; // % de daño de la pista (engine/bases.py)
  const PARTES_BASE = [["", "Ataque general"], ["pista", "La pista (sin despegues ni aterrizajes al 60 % de daño)"], ["plataforma", "La plataforma (expone a los aviones estacionados)"], ["combustible", "El depósito de combustible (reduce las existencias)"]];
  /** "Pista 40 % · Plataforma 10 % · Depósito 0 %" */
  const textoPartesBase = (u) => `Pista ${Math.round(u.dano_pista || 0)} % · Plataforma ${Math.round(u.dano_plataforma || 0)} % · Depósito ${Math.round(u.dano_combustible || 0)} %`;
  const CLASES_EMBARCABLES = ["helicoptero", "helicoptero_artillado", "dron_reconocimiento", "dron_ataque", "municion_merodeadora"];
  const MODELOS_EMBARCABLES = ["caza_embarcado", "fa18ef", "ea18g", "e2d", "f35b"]; // como `embarcable` en catalogo.py
  const LANZAN_MISILES = ["fragata", "destructor", "submarino", "lanzador_misiles"];
  const MAX_MISILES_SALVA = 4;
  const MUNICION_POR_MISIL = 25;

  const esMisil = (u) => !!u && u.clase === "misil_crucero";

  // transporte de tropas (engine/transporte.py): buque de desembarco (3 unidades) y helicoptero de transporte (1 ligera)
  const CAPACIDAD_TRANSPORTE = { buque_desembarco: 3, helicoptero_artillado: 1 };
  const RADIO_EMBARQUE_KM = 3;
  const esTransporte = (u) => !!u && (CAPACIDAD_TRANSPORTE[u.clase] || 0) > 0;
  const embarcada = (u) => !!u && u.transporte_id !== null && u.transporte_id !== undefined;
  const aBordo = (t, unidades) => (unidades || []).filter((x) => x.transporte_id === t.id && x.estado === "activa");
  /** Transportes propios a los que `u` puede subir ahora (a <= 3 km, con plaza y del tipo adecuado). */
  function transportesCercanos(u, unidades, claseDe) {
    if (!u || u.tipo !== "terrestre" || embarcada(u)) return [];
    const cl = claseDe ? claseDe(u) : null;
    const ligera = cl ? cl.movilidad === "ligera" : ["infanteria", "antiaerea_portatil", "ingenieros", "reconocimiento"].includes(u.clase);
    return (unidades || []).filter((t) => t.bando === u.bando && t.estado === "activa" && esTransporte(t)
      && (t.clase !== "helicoptero_artillado" || ligera)
      && aBordo(t, unidades).length < CAPACIDAD_TRANSPORTE[t.clase]
      && distanciaKm(u.lat, u.lon, t.lat, t.lon) <= RADIO_EMBARQUE_KM)
      .map((t) => ({ t, km: distanciaKm(u.lat, u.lon, t.lat, t.lon) }));
  }
  /** Base aerea o portaaviones: lanza, recibe y estaciona aeronaves. */
  const operaAeronaves = (u) => !!u && Object.prototype.hasOwnProperty.call(PLAZAS_AERONAVES, u.clase || "");
  const esPortaaviones = (u) => operaAeronaves(u) && u.tipo !== "base";
  const plazasDe = (u) => PLAZAS_AERONAVES[u.clase] || 0;
  /** La aeronave puede operar desde un portaaviones (por su modelo o, si no lo tiene, por su clase). */
  const esEmbarcable = (u) => !!u && (MODELOS_EMBARCABLES.includes(u.modelo || "") || CLASES_EMBARCABLES.includes(u.clase || ""));
  /** `u` puede aterrizar en (o despegar de) `base`. */
  const puedeOperarEn = (u, base) => operaAeronaves(base) && !esMisil(u) && (!esPortaaviones(base) || esEmbarcable(u));
  /** Modelo del catalogo que puede salir de esa base (un portaaviones solo lanza embarcables; nadie lanza misiles). */
  const modeloDespegaDe = (m, base) => !!m && !m.misil && (!esPortaaviones(base) || !!m.embarcable);
  const puedeLanzarMisiles = (u, clase) => !!u && u.estado === "activa" && (clase ? !!clase.lanza_misiles : LANZAN_MISILES.includes(u.clase || ""));
  /** Misiles que la municion del lanzador permite en una salva (0 a 4). */
  const misilesDisponibles = (u) => Math.max(0, Math.min(MAX_MISILES_SALVA, Math.floor(((u && u.municion) || 0) / MUNICION_POR_MISIL)));

  /** Texto de la situacion de un misil en vuelo: "Salva x2 · hacia Deposito Norte". */
  function textoMisil(u, unidades) {
    const blanco = (unidades || []).find((x) => x.id === u.blanco_id);
    return `${u.aeronaves || 1} misil${(u.aeronaves || 1) === 1 ? "" : "es"} en vuelo hacia ${blanco ? blanco.nombre : "su blanco"}`;
  }

  const ETIQUETA_CLIMA = { despejado: "Despejado", nublado: "Nublado", lluvia: "Lluvia", tormenta: "Tormenta" };
  const etiquetaClima = (c) => ETIQUETA_CLIMA[c] || c || "";

  function textoListos(esc) {
    const f = (b, v) => `${b} ${v ? "listo" : "pendiente"}`;
    return `${f("Azul", esc.listo_azul)} · ${f("Rojo", esc.listo_rojo)}`;
  }

  /** Movimientos entre dos instantaneas: unidades cuya posicion cambio mas que `umbral` grados. */
  function trayectorias(previas, actuales, umbral = 0.0005) {
    const antes = new Map(previas.map((u) => [u.id, u]));
    const salida = [];
    for (const u of actuales) {
      const p = antes.get(u.id);
      if (!p) continue;
      if (Math.abs(p.lat - u.lat) > umbral || Math.abs(p.lon - u.lon) > umbral) {
        salida.push({ id: u.id, bando: u.bando, desde: [p.lat, p.lon], hasta: [u.lat, u.lon] });
      }
    }
    return salida;
  }

  /** Lineas atacante -> defensor de los combates de un turno, con las posiciones de la instantanea. */
  function lineasCombate(combates, unidades) {
    const por = new Map(unidades.map((u) => [u.id, u]));
    const salida = [];
    for (const c of combates) {
      const a = por.get(c.atacante_id);
      const d = por.get(c.defensor_id);
      if (!a || !d) continue;
      salida.push({ combate: c, desde: [a.lat, a.lon], hasta: [d.lat, d.lon] });
    }
    return salida;
  }

  function describirCombate(c) {
    return `${c.atacante} → ${c.defensor}: ratio ${c.ratio.toFixed(2)}, bajas ${c.perdida_atacante.toFixed(0)}/${c.perdida_defensor.toFixed(0)}`
      + (c.efectos ? ` (${c.efectos})` : "");
  }

  /** Turnos que se pueden reproducir (los que tienen instantanea; el turno en curso no). */
  const turnosReproducibles = (informe) => informe.turnos.filter((t) => t.unidades.length > 0);

  // ---------------------------------------------------------------- orden de batalla
  const RAMA_DE_CLASE = {
    infanteria: "infanteria", reconocimiento: "infanteria", blindado: "blindados", artilleria: "artilleria",
    antiaerea: "artilleria", caza: "aviacion", ataque: "aviacion", helicoptero: "aviacion",
    fragata: "naval", patrullero: "naval", destructor: "naval", portaaviones: "naval", submarino: "naval",
    buque_desembarco: "naval", lanzador_misiles: "artilleria", misil_crucero: "artilleria",
    base_aerea: "bases", deposito: "bases", puerto: "bases",
    termoelectrica: "infraestructura", hidroelectrica: "infraestructura", refineria: "infraestructura",
    centro_comunicaciones: "infraestructura", puente: "infraestructura",
  };
  const RAMA_DE_TIPO = { terrestre: "infanteria", aerea: "aviacion", naval: "naval", base: "bases" };
  const RAMAS = [
    ["infanteria", "Infantería"], ["blindados", "Blindados"], ["artilleria", "Artillería"],
    ["aviacion", "Aviación"], ["naval", "Naval"], ["bases", "Bases y logística"], ["infraestructura", "Infraestructura"],
  ];
  const ramaDe = (u) => RAMA_DE_CLASE[u.clase] || RAMA_DE_TIPO[u.tipo] || "infanteria";

  /** [{rama, nombre, unidades}] en orden fijo, solo las ramas con unidades. */
  function agruparPorRama(unidades) {
    return RAMAS
      .map(([rama, nombre]) => ({ rama, nombre, unidades: unidades.filter((u) => ramaDe(u) === rama) }))
      .filter((g) => g.unidades.length > 0);
  }

  // ---------------------------------------------------------------- hora, clima y bando
  /** Hora simulada del turno (cada turno = 1 h) desde `inicioMin` minutos despues de medianoche. */
  function horaSimulada(inicioMin, turno) {
    const total = (inicioMin ?? 360) + Math.max(0, (turno || 1) - 1) * 60;
    const dia = Math.floor(total / 1440);
    const hh = String(Math.floor((total % 1440) / 60)).padStart(2, "0");
    const mm = String(total % 60).padStart(2, "0");
    return { texto: `${hh}:${mm}h`, dia };
  }
  const textoHora = (h) => h.texto + (h.dia > 0 ? ` (D+${h.dia})` : "");

  // Mismos valores que backend/app/engine/clima.py (la interfaz solo los muestra).
  const CLIMA = {
    despejado: { deteccion: 1.0, terrestre: 1.0, ataqueAereo: 1.0 },
    nublado: { deteccion: 0.9, terrestre: 1.0, ataqueAereo: 0.95 },
    lluvia: { deteccion: 0.7, terrestre: 0.8, ataqueAereo: 0.8 },
    tormenta: { deteccion: 0.5, terrestre: 0.6, ataqueAereo: 0.5 },
  };
  const efectosClima = (c) => CLIMA[c] || CLIMA.despejado;
  const visibilidadPct = (c) => Math.round(efectosClima(c).deteccion * 100);

  // meteorologia por zonas: el clima efectivo en un punto es el peor entre el general y las zonas que lo cubren
  const SEVERIDAD_CLIMA = { despejado: 0, nublado: 1, lluvia: 2, tormenta: 3 };
  function climaEn(lat, lon, general, zonas) {
    let peor = SEVERIDAD_CLIMA[general] !== undefined ? general : "despejado";
    for (const z of zonas || []) {
      if ((SEVERIDAD_CLIMA[z.tipo] || 0) > SEVERIDAD_CLIMA[peor] && distanciaKm(lat, lon, z.lat, z.lon) <= z.radio_km) peor = z.tipo;
    }
    return peor;
  }
  const NOMBRE_RUMBO = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
  /** "Lluvia · radio 60 km · deriva 20 km/h al NE · hasta el turno 12" */
  function textoZonaClima(z) {
    const partes = [`${etiquetaClima(z.tipo)}${z.nombre ? " " + z.nombre : ""}`, `radio ${Math.round(z.radio_km)} km`];
    if (z.deriva_kmh > 0) partes.push(`deriva ${Math.round(z.deriva_kmh)} km/h al ${NOMBRE_RUMBO[Math.round((((z.deriva_rumbo % 360) + 360) % 360) / 45) % 8]}`);
    else partes.push("estacionaria");
    partes.push(z.hasta_turno ? `hasta el turno ${z.hasta_turno}` : "sin caducidad");
    return partes.join(" · ");
  }

  function etiquetaBando(rol, vista, puesto) {
    const alumno = { azul: "AZUL (ALUMNO)", rojo: "ROJO (ALUMNO)" };
    if (alumno[rol]) return puesto ? `${rol.toUpperCase()} · ${etiquetaPuesto(puesto).toUpperCase()}` : alumno[rol];
    if (rol === "instructor") return esBando(vista) ? `INSTRUCTOR · VISTA ${vista.toUpperCase()}` : "INSTRUCTOR";
    return "OBSERVADOR";
  }

  const claseBarra = (v) => (v === null || v === undefined ? "oculto" : v < 30 ? "critico" : v < 60 ? "bajo" : "");

  /** Estado legible de una unidad segun sus datos y las ordenes pendientes de este turno. */
  // infraestructura no militar (backend/app/engine/infraestructura.py): un puente bajo el 50 % queda cortado
  const INFRAESTRUCTURA = ["termoelectrica", "hidroelectrica", "refineria", "centro_comunicaciones", "puente"];

  function estadoUnidad(u, ordenesPendientes = []) {
    if (esMisil(u) && u.estado === "activa") return { texto: "Misil en vuelo", clase: "ok" };
    if (embarcada(u) && u.estado === "activa") return { texto: "A bordo", clase: "ok" };
    if (operaAeronaves(u) && u.estado === "activa" && (u.dano_pista || 0) >= PISTA_INOPERATIVA) return { texto: "Pista inoperativa", clase: "fuego" };
    if (u.estado === "destruida") return { texto: "Destruida", clase: "fuego" };
    if (u.fuerza === null || u.fuerza === undefined) return { texto: "Detectada", clase: "fuego" };
    const orden = ordenesPendientes.find((o) => o.unidad_id === u.id);
    if (orden) {
      const t = {
        mover: ["Orden: mover", "mov"], atacar: ["Orden: atacar", "fuego"], apoyar: ["Orden: apoyar", "ok"],
        patrullar: ["Orden: patrullar", "mov"], aterrizar: ["Orden: aterrizar", "ok"], despegar: ["Orden: despegar", "mov"],
      }[orden.tipo];
      if (t) return { texto: t[0], clase: t[1] };
    }
    if (INFRAESTRUCTURA.includes(u.clase)) {
      if (u.clase === "puente" && u.fuerza < 50) return { texto: "Cortado", clase: "fuego" };
      if (u.fuerza < 100) return { texto: `Dañada (${Math.round(u.fuerza)} %)`, clase: "mov" };
      return { texto: "Operativa", clase: "ok" };
    }
    if (u.tipo === "base") {
      if (u.stock_combustible === 0 || u.stock_municion === 0) return { texto: "Base sin existencias", clase: "fuego" };
      return { texto: "Base operativa", clase: "ok" };
    }
    if (u.en_tierra) {
      return u.espera_restante > 0
        ? { texto: `En base · ${u.espera_restante} t`, clase: "mov" }
        : { texto: "En base · lista", clase: "ok" };
    }
    if (u.mision === "patrulla") return { texto: "Patrullando", clase: "mov" };
    if (u.combustible !== null && u.combustible <= 0) return { texto: "Sin combustible", clase: "fuego" };
    if (u.municion !== null && u.municion <= 0) return { texto: "Sin munición", clase: "fuego" };
    if (u.emitiendo === false) return { texto: "Radar apagado", clase: "mov" };
    if (u.fuego_libre === false) return { texto: "Fuego retenido", clase: "mov" };
    return { texto: "Operativa", clase: "ok" };
  }

  // ---------------------------------------------------------------- alertas derivadas de los cambios de estado
  const UMBRAL_BAJO = 25;

  function memoriaVacia() {
    return { inicializada: false, enemigos: {}, destruidas: [], bajos: [], eventos: [], ordenes: {} };
  }

  /**
   * Compara el estado recibido con lo ya visto y devuelve las novedades como alertas.
   * `data` es el mensaje de estado del servidor; `rol` el rol del usuario. En la primera
   * llamada (memoria sin inicializar) solo se registra lo existente, sin alertar.
   * Devuelve { alertas, memoria } sin modificar la memoria recibida.
   */
  function alertasNuevas(memoria, data, rol) {
    const mem = {
      inicializada: true,
      enemigos: { ...memoria.enemigos },
      destruidas: [...memoria.destruidas],
      bajos: [...memoria.bajos],
      eventos: [...memoria.eventos],
      ordenes: { ...memoria.ordenes },
    };
    const alertas = [];
    const turno = data.escenario.turno_actual;
    const avisar = (nivel, texto, clave) => { if (memoria.inicializada) alertas.push({ nivel, texto, clave, turno }); };
    const vista = esBando(data.vista) ? data.vista : esBando(rol) ? rol : null;

    // enemigos: nuevos, perdidos de vista o destruidos (solo tiene sentido con niebla de guerra)
    if (vista) {
      const ahora = {};
      for (const u of data.unidades.filter((x) => x.bando !== vista)) {
        ahora[u.id] = u;
        if (u.estado === "destruida") continue;
        if (!(u.id in mem.enemigos)) avisar("critica", `Unidad enemiga detectada: ${u.nombre} (${u.clase || u.tipo})`, `det-${u.id}-${turno}`);
        mem.enemigos[u.id] = { nombre: u.nombre };
      }
      for (const [id, e] of Object.entries(memoria.enemigos)) {
        const u = ahora[id];
        if (!u) {
          avisar("aviso", `Se perdió contacto con ${e.nombre}`, `perd-${id}-${turno}`);
          delete mem.enemigos[id];
        } else if (u.estado === "destruida") {
          avisar("info", `${u.nombre} fue destruida`, `dest-${id}-${turno}`);
          delete mem.enemigos[id];
        }
      }
    }

    // unidades propias (o de ambos bandos en vista completa): destruccion y logistica baja
    for (const u of data.unidades) {
      if (vista && u.bando !== vista) continue;
      if (u.estado === "destruida" && !mem.destruidas.includes(u.id)) {
        mem.destruidas.push(u.id);
        avisar("critica", `${u.nombre} fue destruida`, `baja-${u.id}`);
      }
      if (u.estado !== "activa" || u.tipo === "base") continue;
      const bajo = (u.combustible !== null && u.combustible < UMBRAL_BAJO) || (u.municion !== null && u.municion < UMBRAL_BAJO);
      if (bajo && !mem.bajos.includes(u.id)) {
        mem.bajos.push(u.id);
        const que = u.combustible < UMBRAL_BAJO ? `combustible ${Math.round(u.combustible)}%` : `munición ${Math.round(u.municion)}%`;
        avisar("aviso", `${u.nombre}: ${que}, necesita reabastecerse`, `log-${u.id}-${turno}`);
      } else if (!bajo && mem.bajos.includes(u.id)) {
        mem.bajos.splice(mem.bajos.indexOf(u.id), 1);
      }
    }

    // eventos del servidor (clima, logistica, avisos del instructor)
    const porTipo = { clima: "info", logistica: "aviso" };
    for (const e of [...data.eventos].reverse()) {
      if (mem.eventos.includes(e.id)) continue;
      mem.eventos.push(e.id);
      avisar(porTipo[e.tipo] || "info", e.descripcion, `ev-${e.id}`);
    }

    // resultado de las ordenes propias
    for (const o of data.ordenes) {
      const antes = memoria.ordenes[o.id];
      mem.ordenes[o.id] = o.estado;
      if (antes === "pendiente" && o.estado !== "pendiente") {
        const u = data.unidades.find((x) => x.id === o.unidad_id);
        const nombre = u ? u.nombre : `#${o.unidad_id}`;
        const rechazada = o.estado === "rechazada";
        avisar(rechazada ? "aviso" : "info", `Orden ${rechazada ? "rechazada" : "resuelta"} (${nombre}, ${o.tipo}): ${o.resultado}`, `ord-${o.id}`);
      }
    }
    return { alertas, memoria: mem };
  }

  // ---------------------------------------------------------------- geometria, chat y graficos
  /** Distancia en km entre dos puntos (Haversine). */
  function distanciaKm(lat1, lon1, lat2, lon2) {
    const r = Math.PI / 180;
    const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2
      + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(a));
  }

  const ETIQUETA_CANAL = { azul: "Red azul", rojo: "Red roja", todos: "Difusión", mando: "Al mando" };
  const etiquetaCanal = (c) => ETIQUETA_CANAL[c] || c;

  /** Canales que puede elegir cada rol al escribir (mismos que valida el servidor). */
  function canalesDe(rol) {
    if (rol === "instructor") return [["todos", "Todos los bandos"], ["azul", "Solo Azul"], ["rojo", "Solo Rojo"]];
    if (esBando(rol)) return [["bando", "Red del bando"], ["mando", "Al mando (instructor)"]];
    return [];
  }

  /** Lo que le paso a un mensaje en cada bando afectado, para la celula de control. */
  function resumenEntrega(entrega) {
    return Object.entries(entrega || {}).map(([lado, e]) => ({
      lado, perdido: e.perdido, demora_ms: e.demora_ms,
      texto: e.perdido ? `${lado}: perdido` : e.demora_ms > 0 ? `${lado}: +${(e.demora_ms / 1000).toFixed(1)} s` : `${lado}: entregado`,
    }));
  }

  const TIPOS_GRAFICO = {
    linea_fase: { nombre: "Línea de fase", geometria: "LineString" },
    eje_avance: { nombre: "Eje de avance", geometria: "LineString" },
    zona_reunion: { nombre: "Zona de reunión", geometria: "Polygon" },
    punto_control: { nombre: "Punto de control", geometria: "Point" },
  };

  /** [lat, lon] de una geometria GeoJSON ([lon, lat]) segun su tipo. */
  function latLngsDe(geometria) {
    const inv = (c) => [c[1], c[0]];
    if (geometria.type === "Point") return inv(geometria.coordinates);
    if (geometria.type === "LineString") return geometria.coordinates.map(inv);
    if (geometria.type === "Polygon") return geometria.coordinates[0].map(inv);
    return [];
  }

  /** Un grafico se puede borrar si es de tu bando o eres instructor (igual que en el servidor). */
  const puedeBorrarGrafico = (g, rol) => rol === "instructor" || (esBando(rol) && g.bando === rol);

  // ---------------------------------------------------------------- aeronaves y bases aereas
  const FUERZA_MINIMA_BASE = 25; // igual que en el servidor: una base muy danada no lanza grupos

  /** Modelo del catalogo de una unidad, o null (sin modelo, o enemiga sin identificar). */
  const modeloDe = (u, modelos) => (u && u.modelo && modelos ? modelos.find((m) => m.id === u.modelo) || null : null);

  /** Segunda linea del rotulo en el mapa: "F-16 ×4". */
  function rotuloModelo(u, modelos) {
    const m = modeloDe(u, modelos);
    if (!m) return "";
    return u.aeronaves > 1 ? `${m.corto} ×${u.aeronaves}` : m.corto;
  }

  /** Aeronaves del grupo que siguen operativas segun su fuerza (null si no se conoce). */
  function aeronavesOperativas(u) {
    if (!u.aeronaves || u.fuerza === null || u.fuerza === undefined) return null;
    return u.fuerza > 0 ? Math.max(1, Math.round((u.aeronaves * u.fuerza) / 100)) : 0;
  }

  /** Bases aereas y portaaviones propios en condiciones de lanzar un grupo. */
  const basesAereasPropias = (unidades, rol) => unidades.filter(
    (u) => u.bando === rol && operaAeronaves(u) && u.estado === "activa" && u.fuerza >= FUERZA_MINIMA_BASE,
  );

  /** {modelo, aeronaves, indicativo} de una orden de despegue (vacio si no se puede leer). */
  function detalleDespegue(orden) {
    try {
      const d = JSON.parse((orden && orden.detalle) || "{}");
      return d && typeof d === "object" ? d : {};
    } catch (_) {
      return {};
    }
  }

  function textoDespegue(orden, modelos) {
    const d = detalleDespegue(orden);
    const m = modelos && modelos.find((x) => x.id === d.modelo);
    return `Despegar ${m ? m.corto : "grupo"} ×${d.aeronaves || "?"}${d.indicativo ? ` «${d.indicativo}»` : ""}`;
  }

  /** Aeronaves de combate activas del bando mas las de sus despegues pendientes (para mostrar el tope). */
  /** Clase del catalogo (/api/catalogo) marcada como dron. */
  const claseEsDron = (claseId, catalogo) => !!(catalogo && (catalogo.clases || []).some((c) => c.id === claseId && c.dron));
  /** El modelo de aeronave pertenece a una clase de dron (los drones tienen su propio tope). */
  function modeloEsDron(modeloId, catalogo) {
    const m = catalogo && (catalogo.modelos || []).find((x) => x.id === modeloId);
    return !!(m && claseEsDron(m.clase, catalogo));
  }

  /** Aeronaves tripuladas (o drones, con drones=true) activas del bando mas las de despegues pendientes.
   *  Sin catalogo no se distingue y cuenta todo (compatibilidad). */
  function aeronavesComprometidas(unidades, ordenes, bando, drones = false, catalogo = null) {
    const activas = unidades
      .filter((u) => u.bando === bando && u.tipo === "aerea" && u.estado === "activa" && claseEsDron(u.clase, catalogo) === drones)
      .reduce((s, u) => s + (u.aeronaves || 1), 0);
    const pendientes = (ordenes || [])
      .filter((o) => o.tipo === "despegar" && o.estado === "pendiente" && modeloEsDron(detalleDespegue(o).modelo, catalogo) === drones)
      .reduce((s, o) => s + (detalleDespegue(o).aeronaves || 0), 0);
    return activas + pendientes;
  }

  // ---------------------------------------------------------------- radares, defensa aerea y existencias de las bases
  const RADIO_SIN_EMISION_KM = 5;
  /** Radio de deteccion real: un radar apagado (silencio de emisiones) solo ve a ojo. */
  const deteccionEfectiva = (u, clase) => (clase && clase.emisor && u.emitiendo === false
    ? Math.min(u.deteccion_km || 0, RADIO_SIN_EMISION_KM) : u.deteccion_km);
  /** Porcentaje de las existencias de una base respecto de su maximo (null si no se conoce). */
  const pctStock = (valor, clase) => (valor === null || valor === undefined || !clase || !clase.stock_max
    ? null : Math.max(0, Math.min(100, (valor / clase.stock_max) * 100)));

  // ---------------------------------------------------------------- misiones aereas
  const ESTADOS_MISION = { programada: "Programada", en_curso: "En curso", cumplida: "Cumplida", abortada: "Abortada", fallida: "Fallida", cancelada: "Cancelada" };
  const TIPOS_PUNTO_MISION = { paso: "Paso", orbita: "Órbita", blanco: "Blanco", aterrizaje: "Aterrizaje" };
  const misionActiva = (m) => m.estado === "programada" || m.estado === "en_curso";

  /** "HH:MM" (y "+Nd" si pasa de dia) del instante que esta `horas` despues del inicio del turno `turno`. */
  function horaEstimada(inicioMin, turno, horas) {
    const total = (inicioMin ?? 360) + Math.max(0, (turno || 1) - 1) * 60 + Math.round((horas || 0) * 60);
    const dia = Math.floor(total / 1440);
    const hh = String(Math.floor((total % 1440) / 60)).padStart(2, "0");
    const mm = String(total % 60).padStart(2, "0");
    return `${hh}:${mm}${dia > 0 ? ` (+${dia}d)` : ""}`;
  }

  /** Situacion de una mision en una frase (para la lista y los tooltips). */
  function textoMision(m) {
    if (m.estado === "programada") return m.unidad_id ? "Se inicia al resolver el turno" : `Despega en el turno ${m.turno_despegue}`;
    if (m.estado === "en_curso") {
      const p = (m.puntos || [])[m.indice];
      if (!p) return "En ruta";
      return `Punto ${m.indice + 1}/${m.puntos.length}: ${TIPOS_PUNTO_MISION[p.tipo] || p.tipo}`
        + (m.espera > 0 ? ` (en órbita, ${m.espera} turno${m.espera === 1 ? "" : "s"} más)` : "");
    }
    return m.resultado || ESTADOS_MISION[m.estado] || m.estado;
  }

  /** Tramos del cronograma (flow sheet) de una mision segun su plan: horas desde el inicio del turno 1.
   *  segmentos: vuelo u orbita; marcas: ataque (blanco) o aterrizaje. */
  function tramosCronograma(m) {
    const filas = (m.plan && m.plan.puntos) || [];
    const t0 = Math.max(0, (m.turno_despegue || 1) - 1);
    const segmentos = [];
    const marcas = [];
    let desde = 0;
    filas.forEach((f, i) => {
      const tipo = f.tipo || ((m.puntos || [])[i] || {}).tipo;
      if (f.llegada_h > desde) segmentos.push({ desde: t0 + desde, hasta: t0 + f.llegada_h, tipo: "vuelo" });
      if (tipo === "orbita") {
        const salida = f.salida_h ?? f.llegada_h;
        segmentos.push({ desde: t0 + f.llegada_h, hasta: t0 + salida, tipo: "orbita" });
        desde = salida;
      } else if (tipo === "blanco") {
        marcas.push({ h: t0 + f.llegada_h, tipo: "blanco" });
        desde = f.salida_h ?? f.llegada_h;
      } else {
        if (tipo === "aterrizaje") marcas.push({ h: t0 + f.llegada_h, tipo: "aterrizaje" });
        desde = f.llegada_h;
      }
    });
    return { inicio: t0, fin: t0 + desde, segmentos, marcas };
  }

  // ---------------------------------------------------------------- guerra electronica
  /** Zonas de interferencia del bando contrario que cubren a la unidad. */
  function interferenciasSobre(u, zonas) {
    return (zonas || []).filter((z) => z.bando !== u.bando && distanciaKm(u.lat, u.lon, z.lat, z.lon) <= z.radio_km);
  }
  /** La unidad puede recibir la orden de interferir (GE activa; si es aerea, en vuelo). */
  const puedeInterferir = (u, clase) => !!(u && clase && clase.interferencia_km > 0 && u.estado === "activa" && !(u.tipo === "aerea" && u.en_tierra));
  /** Aviso para el detalle de una unidad afectada por la interferencia enemiga ("" si no la afecta). */
  function textoInterferido(u, clase, zonas) {
    if (!u || !interferenciasSobre(u, zonas).length) return "";
    if (clase && clase.dron) return "Sin enlace de datos: el dron está dentro de una interferencia enemiga y no acepta órdenes.";
    if (clase && clase.solo_aereo) return "Radar interferido por guerra electrónica enemiga: ve al 20 % de su alcance.";
    if (clase && clase.emisor) return "Interferida por guerra electrónica enemiga: detecta al 30 % y su tiro contra aeronaves pierde el 60 % de efecto.";
    return "Sensores interferidos por guerra electrónica enemiga: detecta al 30 % de su alcance (a ojo, 3 km).";
  }

  /** Unidad base_aerea del escenario que ya ocupa ese punto de la capa de referencia (a <= km), o null. */
  const baseEnEscenario = (unidades, lat, lon, km = 2) => unidades.find(
    (u) => u.clase === "base_aerea" && u.estado !== "destruida" && distanciaKm(u.lat, u.lon, lat, lon) <= km,
  ) || null;

  /** Nombre corto de una base de la capa de referencia: sin "Base Aerea"/"... Airport" ni el parentesis final. */
  const nombreCortoBase = (nombre) => String(nombre || "").replace(/^Base A[ée]rea\s+(de\s+)?/i, "").replace(/^Aeropuerto\s+(Internacional\s+)?(de\s+)?/i, "")
    .replace(/\s*\([^)]*\)\s*$/, "").replace(/\s+(International\s+|Regional\s+|Municipal\s+)?Airport$/i, "").replace(/\s+(Naval\s+)?Air\s+(Force\s+)?Base$/i, "").trim();

  // capa de referencia de aerodromos de toda America (geo/bases_aereas.geojson): de lejos solo las bases
  // militares y las curadas como puntos; los aeropuertos civiles desde ZOOM_AEROPUERTOS; con icono y rotulo
  // (los que caen en pantalla) desde ZOOM_ICONOS_AERODROMO, para que 1000+ puntos no frenen el mapa
  const ZOOM_AEROPUERTOS = 6;
  const ZOOM_ICONOS_AERODROMO = 8;
  /** Como se dibuja un aerodromo a este zoom: "icono" (marcador con rotulo), "punto" (circulo en canvas) o null. */
  function modoAerodromo(p, zoom) {
    if (zoom >= ZOOM_ICONOS_AERODROMO) return "icono";
    if (p.tipo === "base aérea" || p.origen === "curado" || zoom >= ZOOM_AEROPUERTOS) return "punto";
    return null;
  }

  /** Color del icono de un aerodromo por pais: el fijo si lo hay, si no el color oscuro de la bandera de la nacion, si no neutro. */
  function colorAerodromo(pais, naciones, fijos = {}, neutro = "#3d4a57") {
    if (fijos[pais]) return fijos[pais];
    const n = (naciones || []).find((x) => x.nombre === pais);
    const oscuro = (hex) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.55; // sobre el fondo blanco del avion, que se vea
    };
    return (n && (n.colores || []).find(oscuro)) || neutro;
  }

  // ---------------------------------------------------------------- ciclo de vuelo
  const CAPACIDAD_BASE = 12; // aeronaves que caben estacionadas en una base (igual que en el servidor)
  const RADIO_ATERRIZAJE_KM = 3;

  /** Aeronaves estacionadas en la base. */
  const estacionadasEn = (base, unidades) => unidades.filter((u) => u.en_tierra && u.base_id === base.id && u.estado === "activa");

  /** Plazas libres de una base para el grupo `u` (un numero negativo o cero significa que no cabe). */
  function plazasLibres(base, unidades) {
    return (plazasDe(base) || CAPACIDAD_BASE) - estacionadasEn(base, unidades).reduce((s, x) => s + Math.max(1, x.aeronaves || 1), 0);
  }

  /** Bases aereas propias donde `u` cabe, con la distancia y si llega este turno con su combustible. */
  function opcionesDeAterrizaje(u, unidades) {
    const km = (b) => distanciaKm(u.lat, u.lon, b.lat, b.lon);
    return basesAereasPropias(unidades, u.bando)
      .filter((b) => puedeOperarEn(u, b) && plazasLibres(b, unidades) >= Math.max(1, u.aeronaves || 1))
      .map((b) => {
        const d = km(b);
        const alcanceTurno = (u.velocidad_kmh || 0) * 1; // un turno = 1 h
        const combustibleNecesario = u.autonomia_km ? (d / u.autonomia_km) * 100 : null;
        return {
          base: b, km: d, llegaEsteTurno: d <= alcanceTurno + RADIO_ATERRIZAJE_KM,
          turnos: alcanceTurno > 0 ? Math.max(1, Math.ceil((d - RADIO_ATERRIZAJE_KM) / alcanceTurno)) : null,
          combustibleNecesario,
          alcanzaCombustible: combustibleNecesario === null || u.combustible === null || combustibleNecesario <= u.combustible,
        };
      })
      .sort((a, b) => a.km - b.km);
  }

  /** Texto de la situacion de vuelo de una aeronave (en el detalle de la unidad). */
  function situacionDeVuelo(u, unidades) {
    if (u.tipo !== "aerea" || u.estado !== "activa") return null;
    if (u.en_tierra) {
      const base = unidades.find((b) => b.id === u.base_id);
      const donde = base ? ` en ${base.nombre}` : "";
      if (u.espera_restante === null || u.espera_restante === undefined) return `En tierra${donde}`;
      return u.espera_restante > 0
        ? `En tierra${donde}: reabasteciendo y rearmando, lista en ${u.espera_restante} turno${u.espera_restante === 1 ? "" : "s"}`
        : `En tierra${donde}: lista para despegar`;
    }
    if (u.mision === "patrulla" && u.mision_lat !== null && u.mision_lat !== undefined) {
      return `Patrullando sobre ${u.mision_lat.toFixed(2)}, ${u.mision_lon.toFixed(2)}`;
    }
    return "En vuelo";
  }

  // ---------------------------------------------------------------- objetivos, marcador y busqueda
  const sinAcentos = (t) => String(t ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  /** Unidades cuyo nombre, clase o modelo contienen el texto (sin distinguir mayusculas ni acentos). */
  function filtrarUnidades(unidades, texto) {
    const q = sinAcentos(texto).trim();
    if (!q) return unidades;
    return unidades.filter((u) => [u.nombre, u.clase, u.modelo, u.tipo].some((c) => sinAcentos(c).includes(q)));
  }

  const ETIQUETA_OBJETIVO = { ocupar: "Ocupar", destruir: "Destruir", neutralizar: "Neutralizar", proteger: "Proteger", efecto: "Efecto" };
  const NIVELES_OBJETIVO = { ulterior: "Objetivo ulterior", asignado: "Objetivo asignado", material: "Objetivo material" };

  /** Linea de resumen de un objetivo: que hay que hacer, cuanto vale y como va. */
  function textoObjetivo(o) {
    const umbral = o.umbral ?? (o.tipo === "neutralizar" ? 50 : 100);
    const que = {
      ocupar: `Ocupar la zona (radio ${o.radio_km} km)${o.turnos_requeridos > 1 ? ` durante ${o.turnos_requeridos} turnos seguidos` : ""}`,
      destruir: `Destruir ${o.unidad_nombre || "la unidad"}`,
      neutralizar: `Neutralizar ${o.unidad_nombre || "la unidad"} (fuerza ${umbral} % o menos)`,
      proteger: `Proteger ${o.unidad_nombre || "la unidad"}${o.hasta_turno ? ` hasta el turno ${o.hasta_turno}` : ""}`,
      efecto: `Cumplir el ${umbral} % de los objetivos que dependen de él`,
    }[o.tipo] || o.tipo;
    const plazo = o.hasta_turno && o.tipo !== "proteger" ? ` · plazo: turno ${o.hasta_turno}` : "";
    return `${que}${plazo}${o.puntos ? ` · ${o.puntos} pts` : ""}`;
  }

  /** {texto, clase} del avance de un objetivo. */
  function avanceObjetivo(o) {
    if (o.estado === "cumplido") return { texto: `Cumplido (turno ${o.turno_resuelto})`, clase: "ok" };
    if (o.estado === "fallido") return { texto: `Fallido (turno ${o.turno_resuelto})`, clase: "fuego" };
    if (o.tipo === "ocupar") return { texto: `${o.progreso}/${o.turnos_requeridos} turnos`, clase: o.progreso > 0 ? "mov" : "" };
    if (o.tipo === "efecto" && o.avance) {
      const a = o.avance;
      return { texto: a.total ? `${a.cumplidos}/${a.total} cumplidos` : "Sin objetivos dependientes", clase: a.cumplidos > 0 ? "mov" : "" };
    }
    return { texto: "En curso", clase: "" };
  }

  /** Cadena de objetivos como arbol: [{o, nivel}] con cada objetivo despues de su superior (nivel = sangria). Los
   * que no tienen superior visible van primero: ulteriores, asignados y materiales, en ese orden. */
  function arbolObjetivos(objetivos) {
    const lista = objetivos || [];
    const ids = new Set(lista.map((o) => o.id));
    const hijos = new Map();
    for (const o of lista) {
      if (o.padre_id != null && ids.has(o.padre_id)) {
        if (!hijos.has(o.padre_id)) hijos.set(o.padre_id, []);
        hijos.get(o.padre_id).push(o);
      }
    }
    const orden = { ulterior: 0, asignado: 1, material: 2 };
    const raices = lista.filter((o) => o.padre_id == null || !ids.has(o.padre_id))
      .sort((a, b) => (orden[a.nivel] ?? 2) - (orden[b.nivel] ?? 2) || a.id - b.id);
    const salida = [];
    const vistos = new Set();
    const visitar = (o, nivel) => {
      if (vistos.has(o.id)) return;
      vistos.add(o.id);
      salida.push({ o, nivel });
      for (const h of hijos.get(o.id) || []) visitar(h, nivel + 1);
    };
    raices.forEach((o) => visitar(o, 0));
    return salida;
  }

  /** Objetivos de efecto que pueden ser superiores de uno nuevo de ese bando y nivel. */
  function superioresPosibles(objetivos, bando, nivel) {
    const orden = { ulterior: 0, asignado: 1, material: 2 };
    return (objetivos || []).filter((o) => o.tipo === "efecto" && o.bando === bando && (orden[o.nivel] ?? 2) < (orden[nivel] ?? 2));
  }

  // ---------------------------------------------------------------- calendario de la operacion (TIEM)
  /** "D+1 · H+5 · Ejecución" del turno en curso, o "" si el escenario no tiene calendario. */
  function textoCalendario(cal) {
    if (!cal || !cal.actual) return "";
    const a = cal.actual;
    return [a.dia, a.hora_h, nombreFase(a.fase)].filter(Boolean).join(" · ");
  }

  const FASES_TILDES = { "Concentracion y despliegue": "Concentración y despliegue", Ejecucion: "Ejecución" };
  const nombreFase = (f) => FASES_TILDES[f] || f || "";

  /** Quien conduce un bando, en palabras. */
  const CONDUCCION = { alumnos: "Grupo de alumnos", instructor: "Instructor", ia: "Adversario automático (IA)" };

  // ---------------------------------------------------------------- identidad nacional del bando
  /** Nacion (del catalogo /api/naciones) asignada a un bando en este escenario, o null si no tiene. */
  function nacionDe(bando, esc, naciones) {
    if (!esc || !naciones) return null;
    const id = bando === "azul" ? esc.nacion_azul : bando === "rojo" ? esc.nacion_rojo : "";
    return (id && naciones.find((n) => n.id === id)) || null;
  }

  /** "Azul" o "Azul (Colombia)" segun tenga o no identidad nacional asignada. */
  function etiquetaBandoNacion(bando, esc, naciones) {
    const base = bando === "azul" ? "Azul" : "Rojo";
    const n = nacionDe(bando, esc, naciones);
    return n ? `${base} (${n.nombre})` : base;
  }

  // ---------------------------------------------------------------- reparticiones del TIEM dentro del bando
  // Misma matriz que backend/app/engine/puestos.py: el servidor es quien decide; esto solo adapta la interfaz.
  const FUNCIONES_PUESTO = ["superficie", "aereo", "caza", "despegar", "defensa_aerea", "reconocimiento", "logistica", "guerra_electronica", "listo"];
  const PUESTOS = [
    { id: "comandante", sigla: "CMDTE", nombre: "Comandante", descripcion: "Decide y conduce el bando: reúne las funciones de todas las reparticiones y confirma las órdenes (LISTO).", funciones: FUNCIONES_PUESTO },
    { id: "jem", sigla: "JEM", nombre: "Jefe de Estado Mayor", descripcion: "Coordina el trabajo de las reparticiones; reúne sus funciones y confirma las órdenes (LISTO) por el comandante.", funciones: FUNCIONES_PUESTO },
    { id: "a1", sigla: "A-1", nombre: "Personal", descripcion: "Sigue los efectivos propios (dotación, bajas, reemplazos y moral) y prepara la apreciación de personal. No ordena unidades.", funciones: [] },
    { id: "a2", sigla: "A-2", nombre: "Inteligencia", descripcion: "Sigue al enemigo (contactos, cuadro de radares, capacidades del ENO) y conduce el reconocimiento: unidades y drones de reconocimiento.", funciones: ["reconocimiento"] },
    { id: "a3", sigla: "A-3", nombre: "Operaciones", descripcion: "Conduce la maniobra: despegues, caza, ataque, helicópteros, drones armados, cisternas, fuerzas de superficie y lanzadores de misiles.", funciones: ["superficie", "aereo", "caza", "despegar"] },
    { id: "a3da", sigla: "A-3 D/A", nombre: "Defensa Aérea", descripcion: "Conduce la defensa aérea: radares, artillería y misiles antiaéreos, alerta temprana y la caza de intercepción con sus despegues.", funciones: ["defensa_aerea", "caza", "despegar"] },
    { id: "a4", sigla: "A-4", nombre: "Logística", descripcion: "Conduce el abastecimiento: convoyes y depósitos, e ingenieros (puentes y vados).", funciones: ["logistica"] },
    { id: "ce", sigla: "C-E", nombre: "Comunicaciones y Electrónica", descripcion: "Conduce la guerra electrónica: escucha e interferencia desde tierra y aviones de guerra electrónica.", funciones: ["guerra_electronica"] },
  ];
  /** Ids anteriores al TIEM y la reparticion que los reemplaza. */
  const EQUIVALENCIAS_PUESTO = { mando: "comandante", inteligencia: "a2", operaciones: "a3", logistica: "a4", planificacion: "a3" };
  const GENERALES = ["comandante", "jem"];
  /** Reparticion por id; vacio o desconocido = Comandante (los ids viejos se traducen). */
  const puestoDe = (id) => { const k = EQUIVALENCIAS_PUESTO[id] || id; return PUESTOS.find((p) => p.id === k) || PUESTOS[0]; };
  const puestoPuede = (id, funcion) => puestoDe(id).funciones.includes(funcion);
  /** Puede conducir aeronaves en vuelo (alguna funcion aerea). */
  const puestoPuedeAereo = (id) => ["aereo", "caza", "defensa_aerea", "reconocimiento", "guerra_electronica"].some((f) => puestoPuede(id, f));
  const puestosResponsables = (funcion) => PUESTOS.filter((p) => !GENERALES.includes(p.id) && p.funciones.includes(funcion));
  const etiquetaPuesto = (id) => { const p = puestoDe(id); return `${p.nombre} (${p.sigla})`; };

  const CLASES_DEFENSA_AEREA = ["antiaerea", "antiaerea_portatil", "artilleria_antiaerea", "radar", "alerta_temprana"];
  const CLASES_GUERRA_ELECTRONICA = ["guerra_electronica", "avion_ge"];
  const CLASES_RECONOCIMIENTO = ["reconocimiento", "dron_reconocimiento"];

  /** Funcion (reparticion responsable) de una orden sobre una unidad; sin tipo, la de la unidad en general. */
  function funcionDeOrden(u, tipoOrden, clase) {
    if (tipoOrden === "despegar" || u.tipo === "base") return "despegar";
    const id = (clase && clase.id) || u.clase || "";
    if (CLASES_DEFENSA_AEREA.includes(id) || (clase && (clase.defensa_aerea || (clase.emisor && clase.solo_aereo)))) return "defensa_aerea";
    if (CLASES_GUERRA_ELECTRONICA.includes(id) || (clase && clase.interferencia_km > 0)) return "guerra_electronica";
    if (CLASES_RECONOCIMIENTO.includes(id)) return "reconocimiento";
    if (tipoOrden === "construir" || (clase && (clase.construye || (clase.carga_max > 0 && u.tipo !== "aerea")))) return "logistica";
    if (id === "caza") return "caza";
    if (u.tipo === "aerea") return "aereo";
    return "superficie";
  }

  /** Unidades propias que este puesto puede ordenar (clasePor: unidad -> clase del catalogo o null). */
  function unidadesDelPuesto(unidades, rol, puesto, clasePor) {
    return unidadesConOrdenes(unidades, rol).filter((u) => puestoPuede(puesto, funcionDeOrden(u, null, clasePor ? clasePor(u) : null)));
  }

  /** Aviso para una unidad propia que conduce otro puesto ("" si no corresponde a ninguno). */
  function textoPuestoAjeno(u, clase) {
    const r = puestosResponsables(funcionDeOrden(u, null, clase));
    return r.length ? `Esta unidad la conduce la repartición ${r.map((p) => `${p.nombre} (${p.sigla})`).join(" o ")}.` : "";
  }

  // ---------- mapas (regiones del terreno, ver tools/preparar_terreno.py) ----------
  /** Region de detalle que siempre existe: se usa si el servidor no informa ninguna. */
  const MAPA_VENEZUELA = { id: "venezuela", nombre: "Venezuela y vecinos", bbox: [-73.5, 0.5, -59.5, 12.5], z: 9, z_min: 5, metros_por_pixel: 304, satelite: { z_min: 5, z_max: 12 } };

  /** Regiones validas ordenadas de menos a mas detallada (asi se apilan las capas: la mas fina encima). */
  function ordenarMapas(mapas) {
    const validos = (mapas || []).filter((m) => m && m.id && Array.isArray(m.bbox) && m.bbox.length === 4 && Number.isFinite(m.z));
    return (validos.length ? validos : [MAPA_VENEZUELA]).slice().sort((a, b) => a.z - b.z);
  }

  /** Limites Leaflet [[latMin, lonMin], [latMax, lonMax]] de una region. */
  function limitesDe(mapa) {
    const [lon0, lat0, lon1, lat1] = mapa.bbox;
    return [[lat0, lon0], [lat1, lon1]];
  }

  /** Limites que abarcan todas las regiones, zoom minimo del mapa y region principal (la mas detallada). */
  function limitesDeMapas(mapas) {
    const lista = ordenarMapas(mapas);
    const lons = lista.flatMap((m) => [m.bbox[0], m.bbox[2]]);
    const lats = lista.flatMap((m) => [m.bbox[1], m.bbox[3]]);
    return {
      limites: [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]],
      zoomMin: Math.min(...lista.map((m) => (Number.isFinite(m.z_min) ? m.z_min : Math.max(2, m.z - 4)))),
      principal: lista[lista.length - 1],
    };
  }

  // ---- perfil de vuelo (engine/relieve.py): cota de las aeronaves frente al relieve y los sensores ----
  const PERFILES_VUELO = {
    alto: { nombre: "Alto", altura: "6 000 m", ayuda: "Lo ve el radar desde muy lejos, por encima de las montañas; fuera del alcance de la antiaérea portátil; gasta 15 % menos." },
    medio: { nombre: "Medio", altura: "1 500 m", ayuda: "Equilibrado: lo ocultan las montañas altas que tenga delante." },
    rasante: { nombre: "Rasante", altura: "60 m", ayuda: "Se esconde tras el relieve y bajo el horizonte del radar; gasta 30 % más y queda expuesto a la antiaérea portátil." },
  };
  /** "Rasante (60 m)" o "" si no es una aeronave. */
  function textoPerfil(perfil) {
    const p = PERFILES_VUELO[perfil];
    return p ? `${p.nombre} (${p.altura})` : "";
  }
  /** Si conviene pedir y dibujar la cobertura por relieve de esta unidad: sensores en tierra o en el mar. */
  /** Sistema de defensa aerea (engine/defensa_aerea.py): filas de sus armas con lo listo y en reserva, y datos de la
   * bateria para la ficha. `sistema` viene del catalogo (sistemas_da) y `estado` de la unidad (sistema_da). */
  function resumenSistemaDA(sistema, estado) {
    if (!sistema) return null;
    const porId = new Map(((estado && estado.armas) || []).map((a) => [a.id, a]));
    const km = (v) => (Number.isInteger(v) ? String(v) : String(v).replace(".", ","));
    const armas = sistema.armas.map((a) => {
      const e = porId.get(a.id);
      return {
        id: a.id, nombre: a.nombre, tipo: a.tipo_nombre, categoria: a.categoria === "largo" ? "Largo alcance" : "Corto alcance",
        alcance: `${km(a.alcance_min_km)}–${km(a.alcance_max_km)} km`,
        altura: `${Math.round(a.altura_min_m)}–${Math.round(a.altura_max_m).toLocaleString("es")} m`,
        pk: `${Math.round(a.pk * 100)} %`, salva: `${a.por_blanco} por blanco`,
        listos: e ? `${e.listos} de ${a.cargados}` : `${a.cargados}`, reserva: e ? `${e.reserva} de ${a.reserva}` : `${a.reserva}`,
        carga: e ? `${e.listos}/${a.cargados} (+${e.reserva})` : `${a.cargados} (+${a.reserva})`,
        recarga: `${km(a.recarga_min)} min`,
      };
    });
    const radar = sistema.radar_tiro_km
      ? `Vigilancia ${sistema.radar_vigilancia_km || "—"} km · tiro ${sistema.radar_tiro_km} km`
      : sistema.radar_vigilancia_km ? `Vigilancia ${sistema.radar_vigilancia_km} km · puntería óptica` : "Sin radar: puntería óptica (depende del cuadro aéreo)";
    return {
      armas, radar, reaccion: `${sistema.reaccion_s} s · ${sistema.canales} canal${sistema.canales === 1 ? "" : "es"} de tiro`,
      despliegue: `${km(sistema.despliegue_min)} min / ${km(sistema.repliegue_min)} min`, movilidad: sistema.movilidad,
      vehiculos: `${sistema.total_vehiculos}: ${sistema.vehiculos.map((v) => `${v.cantidad} ${v.descripcion}`).join(", ")}`,
      personal: sistema.personal, nota: sistema.nota, elegida: (estado && estado.arma_elegida) || "",
    };
  }

  function muestraCobertura(u, clase) {
    return !!u && u.tipo !== "aerea" && u.estado === "activa" && (u.deteccion_km || 0) >= 15 && !!clase && (clase.emisor || u.tipo === "naval" || (u.deteccion_km || 0) >= 20);
  }

  // ---- unidades segun el zoom: de lejos no deben tapar el mapa ni encimarse; de cerca se ven con detalle ----
  const ZOOM_ROTULOS = 8; // por debajo, las unidades van sin nombre (se lee al pasar el cursor)
  const ZOOM_ALCANCES = 9; // desde aca, cada unidad desplegada muestra el anillo de su alcance
  const ZOOM_CARRETERAS = 7; // desde aca se dibujan las carreteras reales

  /** Factor de tamaño de miniaturas y simbolos: 0,35 de lejos (pais entero), 1 hacia el zoom 10, hasta 1,5 de cerca. */
  function escalaUnidad(zoom) {
    return Math.max(0.35, Math.min(1.5, 0.75 + 0.15 * (zoom - 8)));
  }

  /** Unidades que muestran su anillo de alcance con el mapa cerca: desplegadas y con armas o radio propio
   * (no bases, misiles en vuelo, tropas embarcadas ni aeronaves en tierra). */
  function unidadesConAlcance(unidades) {
    return unidades.filter((u) => u.estado === "activa" && u.alcance_km > 0 && u.tipo !== "base" && !esMisil(u)
      && !embarcada(u) && !u.en_tierra && Number.isFinite(u.lat) && Number.isFinite(u.lon));
  }

  /** Rotulo de una region: nombre y resolucion aproximada. */
  function textoMapa(m) {
    const mpp = m.metros_por_pixel;
    if (!mpp) return m.nombre || m.id;
    return `${m.nombre || m.id} · ${mpp >= 1000 ? `${(mpp / 1000).toFixed(1).replace(".", ",")} km` : `${mpp} m`}/píxel`;
  }

  const api = {
    MAPA_VENEZUELA, ordenarMapas, limitesDe, limitesDeMapas, textoMapa, ZOOM_ROTULOS, ZOOM_ALCANCES, ZOOM_CARRETERAS, escalaUnidad, unidadesConAlcance,
    PERFILES_VUELO, textoPerfil, muestraCobertura, resumenSistemaDA,
    NIVELES_OBJETIVO, arbolObjetivos, superioresPosibles, textoCalendario, nombreFase, CONDUCCION,
    PUESTOS, puestoDe, puestoPuede, puestoPuedeAereo, puestosResponsables, etiquetaPuesto, funcionDeOrden, unidadesDelPuesto, textoPuestoAjeno,
    claseEsDron, modeloEsDron, interferenciasSobre, puedeInterferir, textoInterferido,
    ESTADOS_MISION, TIPOS_PUNTO_MISION, misionActiva, horaEstimada, textoMision, tramosCronograma,
    RADIO_SIN_EMISION_KM, deteccionEfectiva, pctStock,
    nacionDe, etiquetaBandoNacion, filtrarUnidades, textoObjetivo, avanceObjetivo, ETIQUETA_OBJETIVO, CAPACIDAD_BASE, RADIO_ATERRIZAJE_KM, estacionadasEn, plazasLibres, opcionesDeAterrizaje, situacionDeVuelo,
    modeloDe, rotuloModelo, aeronavesOperativas, basesAereasPropias, detalleDespegue, textoDespegue,
    aeronavesComprometidas, baseEnEscenario, nombreCortoBase, FUERZA_MINIMA_BASE, modoAerodromo, colorAerodromo, ZOOM_AEROPUERTOS, ZOOM_ICONOS_AERODROMO,
    esMisil, operaAeronaves, esPortaaviones, plazasDe, esEmbarcable, puedeOperarEn, modeloDespegaDe, puedeLanzarMisiles,
    misilesDisponibles, textoMisil, MAX_MISILES_SALVA, MUNICION_POR_MISIL, PISTA_INOPERATIVA, PARTES_BASE, textoPartesBase,
    esTransporte, embarcada, aBordo, transportesCercanos, CAPACIDAD_TRANSPORTE,
    distanciaKm, etiquetaCanal, canalesDe, resumenEntrega, TIPOS_GRAFICO, latLngsDe, puedeBorrarGrafico,
    BANDOS, esBando, pct, fechaUtc, segundosRestantes, formatoTiempo, objetivosDisponibles,
    unidadesConOrdenes, etiquetaClima, textoListos, trayectorias, lineasCombate, describirCombate,
    turnosReproducibles, RAMAS, ramaDe, agruparPorRama, horaSimulada, textoHora, efectosClima, visibilidadPct,
    etiquetaBando, claseBarra, estadoUnidad, memoriaVacia, alertasNuevas, climaEn, textoZonaClima,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Logica = api;
})(typeof window !== "undefined" ? window : globalThis);
