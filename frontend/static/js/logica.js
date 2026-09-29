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

  function etiquetaBando(rol, vista, puesto) {
    const alumno = { azul: "AZUL (ALUMNO)", rojo: "ROJO (ALUMNO)" };
    if (alumno[rol]) return puesto ? `${rol.toUpperCase()} · ${etiquetaPuesto(puesto).toUpperCase()}` : alumno[rol];
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
      const t = {
        mover: ["Orden: mover", "mov"], atacar: ["Orden: atacar", "fuego"], apoyar: ["Orden: apoyar", "ok"],
        patrullar: ["Orden: patrullar", "mov"], aterrizar: ["Orden: aterrizar", "ok"], despegar: ["Orden: despegar", "mov"],
      }[orden.tipo];
      if (t) return { texto: t[0], clase: t[1] };
    }
    if (u.tipo === "base") return { texto: "Base operativa", clase: "ok" };
    if (u.en_tierra) {
      return u.espera_restante > 0
        ? { texto: `En base · ${u.espera_restante} t`, clase: "mov" }
        : { texto: "En base · lista", clase: "ok" };
    }
    if (u.mision === "patrulla") return { texto: "Patrullando", clase: "mov" };
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

  /** Nombre corto de una base de la capa de referencia: sin "Base Aerea" ni el parentesis final. */
  const nombreCortoBase = (nombre) => String(nombre || "").replace(/^Base A[ée]rea\s+/i, "").replace(/\s*\([^)]*\)\s*$/, "").trim();

  // ---------------------------------------------------------------- ciclo de vuelo
  const CAPACIDAD_BASE = 12; // aeronaves que caben estacionadas en una base (igual que en el servidor)
  const RADIO_ATERRIZAJE_KM = 3;

  /** Aeronaves estacionadas en la base. */
  const estacionadasEn = (base, unidades) => unidades.filter((u) => u.en_tierra && u.base_id === base.id && u.estado === "activa");

  /** Plazas libres de una base para el grupo `u` (un numero negativo o cero significa que no cabe). */
  function plazasLibres(base, unidades) {
    return CAPACIDAD_BASE - estacionadasEn(base, unidades).reduce((s, x) => s + Math.max(1, x.aeronaves || 1), 0);
  }

  /** Bases aereas propias donde `u` cabe, con la distancia y si llega este turno con su combustible. */
  function opcionesDeAterrizaje(u, unidades) {
    const km = (b) => distanciaKm(u.lat, u.lon, b.lat, b.lon);
    return basesAereasPropias(unidades, u.bando)
      .filter((b) => plazasLibres(b, unidades) >= Math.max(1, u.aeronaves || 1))
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

  const ETIQUETA_OBJETIVO = { ocupar: "Ocupar", destruir: "Destruir", proteger: "Proteger" };

  /** Linea de resumen de un objetivo: que hay que hacer, cuanto vale y como va. */
  function textoObjetivo(o) {
    const que = {
      ocupar: `Ocupar la zona (radio ${o.radio_km} km)${o.turnos_requeridos > 1 ? ` durante ${o.turnos_requeridos} turnos seguidos` : ""}`,
      destruir: `Destruir ${o.unidad_nombre || "la unidad"}`,
      proteger: `Proteger ${o.unidad_nombre || "la unidad"}${o.hasta_turno ? ` hasta el turno ${o.hasta_turno}` : ""}`,
    }[o.tipo] || o.tipo;
    return `${que} · ${o.puntos} pts`;
  }

  /** {texto, clase} del avance de un objetivo. */
  function avanceObjetivo(o) {
    if (o.estado === "cumplido") return { texto: `Cumplido (turno ${o.turno_resuelto})`, clase: "ok" };
    if (o.estado === "fallido") return { texto: `Fallido (turno ${o.turno_resuelto})`, clase: "fuego" };
    if (o.tipo === "ocupar") return { texto: `${o.progreso}/${o.turnos_requeridos} turnos`, clase: o.progreso > 0 ? "mov" : "" };
    return { texto: "En curso", clase: "" };
  }

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

  // ---------------------------------------------------------------- puestos por funcion dentro del bando
  // Misma matriz que backend/app/engine/puestos.py: el servidor es quien decide; esto solo adapta la interfaz.
  const PUESTOS = [
    { id: "mando", sigla: "EM", nombre: "Estado Mayor", descripcion: "Conduce todo el bando: reúne las funciones de los demás puestos.", funciones: ["superficie", "aereo", "despegar", "logistica", "guerra_electronica", "listo"] },
    { id: "inteligencia", sigla: "A2", nombre: "Inteligencia", descripcion: "Sigue la situación enemiga (contactos, gráficos de blancos, mensajes) y conduce los radares y las unidades terrestres de guerra electrónica: escucha e interferencia.", funciones: ["guerra_electronica"] },
    { id: "operaciones", sigla: "A3", nombre: "Operaciones en curso", descripcion: "Conduce las aeronaves: despegue desde la pista, rutas, patrullas, ataques y aterrizajes.", funciones: ["aereo"] },
    { id: "logistica", sigla: "A4", nombre: "Logística", descripcion: "Conduce los convoyes de abastecimiento y a los ingenieros (puentes y vados).", funciones: ["logistica"] },
    { id: "planificacion", sigla: "A5", nombre: "Planificación", descripcion: "Ordena a las unidades terrestres y navales, envía los grupos de caza desde las bases y confirma las órdenes del bando (LISTO).", funciones: ["superficie", "despegar", "listo"] },
  ];
  /** Puesto por id; vacio o desconocido = Estado Mayor (usuarios anteriores a los puestos). */
  const puestoDe = (id) => PUESTOS.find((p) => p.id === id) || PUESTOS[0];
  const puestoPuede = (id, funcion) => puestoDe(id).funciones.includes(funcion);
  const puestosResponsables = (funcion) => PUESTOS.filter((p) => p.id !== "mando" && p.funciones.includes(funcion));
  const etiquetaPuesto = (id) => { const p = puestoDe(id); return `${p.nombre} (${p.sigla})`; };

  /** Funcion (puesto responsable) de una orden sobre una unidad; sin tipo, la de la unidad en general. */
  function funcionDeOrden(u, tipoOrden, clase) {
    if (tipoOrden === "despegar" || u.tipo === "base") return "despegar";
    if (clase && clase.celula === "ge" && u.tipo !== "aerea") return "guerra_electronica";
    if (tipoOrden === "construir" || (clase && (clase.construye || clase.carga_max > 0))) return "logistica";
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
    return r.length ? `Esta unidad la conduce el puesto ${r.map((p) => `${p.nombre} (${p.sigla})`).join(" o ")}.` : "";
  }

  const api = {
    PUESTOS, puestoDe, puestoPuede, puestosResponsables, etiquetaPuesto, funcionDeOrden, unidadesDelPuesto, textoPuestoAjeno,
    claseEsDron, modeloEsDron, interferenciasSobre, puedeInterferir, textoInterferido,
    nacionDe, etiquetaBandoNacion, filtrarUnidades, textoObjetivo, avanceObjetivo, ETIQUETA_OBJETIVO, CAPACIDAD_BASE, RADIO_ATERRIZAJE_KM, estacionadasEn, plazasLibres, opcionesDeAterrizaje, situacionDeVuelo,
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
