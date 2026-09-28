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
    return activas.filter((u) => u.bando !== rol);
  }

  /** Unidades propias que pueden recibir ordenes (las bases no se mueven ni combaten). */
  function unidadesConOrdenes(unidades, rol) {
    return unidades.filter((u) => u.estado === "activa" && u.bando === rol && u.tipo !== "base");
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
    fragata: "naval", patrullero: "naval", base_aerea: "bases", deposito: "bases", puerto: "bases",
  };
  const RAMA_DE_TIPO = { terrestre: "infanteria", aerea: "aviacion", naval: "naval", base: "bases" };
  const RAMAS = [
    ["infanteria", "Infantería"], ["blindados", "Blindados"], ["artilleria", "Artillería"],
    ["aviacion", "Aviación"], ["naval", "Naval"], ["bases", "Bases y logística"],
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

  function etiquetaBando(rol, vista) {
    const alumno = { azul: "AZUL (ALUMNO)", rojo: "ROJO (ALUMNO)" };
    if (alumno[rol]) return alumno[rol];
    if (rol === "instructor") return esBando(vista) ? `INSTRUCTOR · VISTA ${vista.toUpperCase()}` : "INSTRUCTOR";
    return "OBSERVADOR";
  }

  const claseBarra = (v) => (v === null || v === undefined ? "oculto" : v < 30 ? "critico" : v < 60 ? "bajo" : "");

  /** Estado legible de una unidad segun sus datos y las ordenes pendientes de este turno. */
  function estadoUnidad(u, ordenesPendientes = []) {
    if (u.estado === "destruida") return { texto: "Destruida", clase: "fuego" };
    if (u.fuerza === null || u.fuerza === undefined) return { texto: "Detectada", clase: "fuego" };
    const orden = ordenesPendientes.find((o) => o.unidad_id === u.id);
    if (orden) {
      const t = { mover: ["Orden: mover", "mov"], atacar: ["Orden: atacar", "fuego"], apoyar: ["Orden: apoyar", "ok"] }[orden.tipo];
      if (t) return { texto: t[0], clase: t[1] };
    }
    if (u.tipo === "base") return { texto: "Base operativa", clase: "ok" };
    if (u.combustible !== null && u.combustible <= 0) return { texto: "Sin combustible", clase: "fuego" };
    if (u.municion !== null && u.municion <= 0) return { texto: "Sin munición", clase: "fuego" };
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

  /** Bases aereas propias en condiciones de lanzar un grupo. */
  const basesAereasPropias = (unidades, rol) => unidades.filter(
    (u) => u.bando === rol && u.clase === "base_aerea" && u.estado === "activa" && u.fuerza >= FUERZA_MINIMA_BASE,
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
  function aeronavesComprometidas(unidades, ordenes, bando) {
    const activas = unidades
      .filter((u) => u.bando === bando && u.tipo === "aerea" && u.estado === "activa")
      .reduce((s, u) => s + (u.aeronaves || 1), 0);
    const pendientes = (ordenes || [])
      .filter((o) => o.tipo === "despegar" && o.estado === "pendiente")
      .reduce((s, o) => s + (detalleDespegue(o).aeronaves || 0), 0);
    return activas + pendientes;
  }

  /** Unidad base_aerea del escenario que ya ocupa ese punto de la capa de referencia (a <= km), o null. */
  const baseEnEscenario = (unidades, lat, lon, km = 2) => unidades.find(
    (u) => u.clase === "base_aerea" && u.estado !== "destruida" && distanciaKm(u.lat, u.lon, lat, lon) <= km,
  ) || null;

  /** Nombre corto de una base de la capa de referencia: sin "Base Aerea" ni el parentesis final. */
  const nombreCortoBase = (nombre) => String(nombre || "").replace(/^Base A[ée]rea\s+/i, "").replace(/\s*\([^)]*\)\s*$/, "").trim();

  const api = {
    modeloDe, rotuloModelo, aeronavesOperativas, basesAereasPropias, detalleDespegue, textoDespegue,
    aeronavesComprometidas, baseEnEscenario, nombreCortoBase, FUERZA_MINIMA_BASE,
    distanciaKm, etiquetaCanal, canalesDe, resumenEntrega, TIPOS_GRAFICO, latLngsDe, puedeBorrarGrafico,
    BANDOS, esBando, pct, fechaUtc, segundosRestantes, formatoTiempo, objetivosDisponibles,
    unidadesConOrdenes, etiquetaClima, textoListos, trayectorias, lineasCombate, describirCombate,
    turnosReproducibles, RAMAS, ramaDe, agruparPorRama, horaSimulada, textoHora, efectosClima, visibilidadPct,
    etiquetaBando, claseBarra, estadoUnidad, memoriaVacia, alertasNuevas,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Logica = api;
})(typeof window !== "undefined" ? window : globalThis);
