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
    if (tipoOrden === "torpedo") return activas.filter((u) => u.bando !== rol && u.tipo === "naval" && !esMisil(u));
    if (tipoOrden === "interceptar") { // aeronaves en vuelo y buques; un buque solo alcanza a otros buques
      const propia = unidades.find((u) => String(u.id) === String(unidadId));
      return activas.filter((u) => u.bando !== rol && interceptable(u) && !(propia && propia.tipo === "naval" && u.tipo === "aerea"));
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
  const PLAZAS_AERONAVES = { base_aerea: 12, portaaviones: 10, punto_recobre: 4 }; // igual que el catalogo del servidor
  const PISTA_INOPERATIVA = 60; // % de daño de la pista (engine/bases.py)
  const PARTES_BASE = [["", "Ataque general"], ["pista", "La pista (sin despegues ni aterrizajes al 60 % de daño)"], ["plataforma", "La plataforma (expone a los aviones estacionados)"], ["combustible", "El depósito de combustible (reduce las existencias)"]];
  /** "Pista 40 % · Plataforma 10 % · Depósito 0 %" */
  const textoPartesBase = (u) => `Pista ${Math.round(u.dano_pista || 0)} % · Plataforma ${Math.round(u.dano_plataforma || 0)} % · Depósito ${Math.round(u.dano_combustible || 0)} %`;
  const CLASES_EMBARCABLES = ["helicoptero", "helicoptero_artillado", "dron_reconocimiento", "dron_ataque", "municion_merodeadora"];
  const MODELOS_EMBARCABLES = ["caza_embarcado", "fa18ef", "ea18g", "e2d", "f35b"]; // como `embarcable` en catalogo.py
  const LANZAN_MISILES = ["fragata", "destructor", "submarino", "lanzador_misiles", "lanzador_balistico"];
  const MAX_MISILES_SALVA = 4;
  const MUNICION_POR_MISIL = 25;

  const esMisil = (u) => !!u && (u.clase === "misil_crucero" || u.clase === "torpedo"); // armas autoguiadas en recorrido

  // transporte de tropas (engine/transporte.py): buque de desembarco (3 unidades) y helicoptero de transporte (1 ligera)
  const CAPACIDAD_TRANSPORTE = { buque_desembarco: 3, helicoptero_artillado: 1, avion_transporte: 2 };
  const CAPACIDAD_MODELO = { c27j: 1, an26: 1, an32: 1, c295: 1, cn235: 1, c212: 1, bt67: 1, dhc6: 1, c208: 1, emb110: 1,
    il76md: 3, a400m: 3 };  // por avion (engine/transporte.py)
  const RADIO_EMBARQUE_KM = 3;
  const esTransporte = (u) => !!u && (CAPACIDAD_TRANSPORTE[u.clase] || 0) > 0;
  const esAvionTransporte = (u) => !!u && u.clase === "avion_transporte";
  /** Unidades que lleva el transporte (el avion, segun su modelo y por cada avion del grupo). */
  function capacidadTransporte(t) {
    if (!t) return 0;
    if (esAvionTransporte(t)) return (CAPACIDAD_MODELO[t.modelo] || CAPACIDAD_TRANSPORTE.avion_transporte) * Math.max(1, t.aeronaves || 1);
    return CAPACIDAD_TRANSPORTE[t.clase] || 0;
  }
  const embarcada = (u) => !!u && u.transporte_id !== null && u.transporte_id !== undefined;
  const aBordo = (t, unidades) => (unidades || []).filter((x) => x.transporte_id === t.id && x.estado === "activa");
  /** Transportes propios a los que `u` puede subir ahora (a <= 3 km, con plaza y del tipo adecuado). */
  function transportesCercanos(u, unidades, claseDe) {
    if (!u || u.tipo !== "terrestre" || embarcada(u)) return [];
    const cl = claseDe ? claseDe(u) : null;
    const ligera = cl ? cl.movilidad === "ligera" : ["infanteria", "antiaerea_portatil", "ingenieros", "reconocimiento"].includes(u.clase);
    return (unidades || []).filter((t) => t.bando === u.bando && t.estado === "activa" && esTransporte(t)
      && ((t.clase !== "helicoptero_artillado" && !esAvionTransporte(t)) || ligera)
      && (!esAvionTransporte(t) || t.en_tierra)  // el avion embarca en la base
      && aBordo(t, unidades).length < capacidadTransporte(t)
      && distanciaEmbarque(u, t, unidades) <= RADIO_EMBARQUE_KM)
      .map((t) => ({ t, km: distanciaEmbarque(u, t, unidades) }));
  }
  /** Distancia al transporte; al avion estacionado se sube en su base (engine/transporte.py). */
  function distanciaEmbarque(u, t, unidades) {
    const d = distanciaKm(u.lat, u.lon, t.lat, t.lon);
    const base = esAvionTransporte(t) && t.en_tierra && t.base_id ? (unidades || []).find((x) => x.id === t.base_id) : null;
    return base ? Math.min(d, distanciaKm(u.lat, u.lon, base.lat, base.lon)) : d;
  }
  /** Paracaidistas a bordo de `t` (los unicos que saltan). */
  const paracaidistasABordo = (t, unidades) => (t ? aBordo(t, unidades).filter((x) => x.clase === "paracaidistas") : []);
  /** El avion de transporte puede lanzar paracaidistas: lleva alguno a bordo. */
  const puedeLanzarParacaidistas = (t, unidades) => esAvionTransporte(t) && paracaidistasABordo(t, unidades).length > 0;
  /** Puede desembarcar: lleva tropas; el avion, solo en tierra (en vuelo lanza paracaidistas). */
  const puedeDesembarcar = (t, unidades) => esTransporte(t) && aBordo(t, unidades).length > 0 && (!esAvionTransporte(t) || !!t.en_tierra);
  /** Base aerea o portaaviones: lanza, recibe y estaciona aeronaves. */
  const operaAeronaves = (u) => !!u && Object.prototype.hasOwnProperty.call(PLAZAS_AERONAVES, u.clase || "");
  const esPortaaviones = (u) => operaAeronaves(u) && u.tipo !== "base";
  const plazasDe = (u) => PLAZAS_AERONAVES[u.clase] || 0;
  /** La aeronave puede operar desde un portaaviones (por su modelo o, si no lo tiene, por su clase). */
  const esEmbarcable = (u) => !!u && (MODELOS_EMBARCABLES.includes(u.modelo || "") || CLASES_EMBARCABLES.includes(u.clase || ""));
  /** `u` puede aterrizar en (o despegar de) `base`. */
  const puedeOperarEn = (u, base) => operaAeronaves(base) && !esMisil(u) && (!esPortaaviones(base) || esEmbarcable(u));
  /** Modelo del catalogo que puede salir de esa base (un portaaviones solo lanza embarcables; nadie lanza misiles). */
  const esAeronave = (m) => !!m && !m.misil && (!m.tipo || m.tipo === "aerea");
  const modeloDespegaDe = (m, base) => esAeronave(m) && (!esPortaaviones(base) || !!m.embarcable);

  /** Filtro del selector de aeronaves: texto (nombre, pais, fabricante o funcion, sin acentos) y clase. */
  function filtrarModelos(modelos, texto, clase) {
    const q = String(texto || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
    return (modelos || []).filter((m) => (!clase || m.clase === clase) && (!q || `${m.nombre} ${m.corto} ${m.pais} ${m.fabricante} ${m.funcion}`
      .toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").includes(q)));
  }
  const puedeLanzarMisiles = (u, clase) => !!u && u.estado === "activa"
    && (u.clase === "lanzador_balistico" || (clase ? !!clase.lanza_misiles : LANZAN_MISILES.includes(u.clase || "")));
  /** Misiles que la municion del lanzador permite en una salva (0 a 4). */
  const misilesDisponibles = (u) => Math.max(0, Math.min(MAX_MISILES_SALVA, Math.floor(((u && u.municion) || 0) / MUNICION_POR_MISIL)));

  /** Texto de la situacion de un misil en vuelo: "Salva x2 · hacia Deposito Norte". */
  function textoMisil(u, unidades) {
    const blanco = (unidades || []).find((x) => x.id === u.blanco_id);
    const hacia = blanco ? blanco.nombre : "su blanco";
    if (u.clase === "torpedo") return `Torpedo en recorrido hacia ${hacia}`;
    if (u.clase === "misil_balistico") {
      const b = u.balistico;
      return b ? `Misil balístico en fase ${b.fase}: impacto en ${b.minutos} min (apogeo ${b.apogeo_km} km)` : `Misil balístico hacia ${hacia}`;
    }
    if ((u.aeronaves || 1) === 1) return `Misil en vuelo hacia ${hacia}${u.fuerza != null && u.fuerza < 100 ? ` (dañado: ${Math.round(u.fuerza)} %)` : ""}`;
    return `${u.aeronaves} misiles en vuelo hacia ${hacia}`;
  }

  /** Defensa de punto de un buque (engine/misiles.py): «2 canales a 8 km (Pk 0,45)». */
  function textoDefensaPunto(u, cat) {
    const d = cat && cat.defensa_punto && cat.defensa_punto[u.clase];
    return d && u.tipo === "naval" ? `${d.canales} canal${d.canales === 1 ? "" : "es"} a ${d.km} km (Pk ${String(d.pk).replace(".", ",")} por disparo)` : "";
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

  /** Movimientos a animar al recibir un estado: solo si es el mismo escenario y avanzo el turno (no al cambiar de
   *  escenario, ni al arrastrar una unidad, ni en una actualizacion dentro del mismo turno). `previas`: Map id ->
   *  [lat, lon] de lo que se dibujo antes. */
  function movimientosDelTurno(previas, unidades, antes, ahora, umbral = 0.0005) {
    if (!antes || !ahora || antes.escenario !== ahora.escenario || !(ahora.turno > antes.turno) || !previas) return [];
    const salida = [];
    for (const u of unidades) {
      const p = previas.get(u.id);
      if (!p || u.estado === "destruida") continue;
      if (Math.abs(p[0] - u.lat) > umbral || Math.abs(p[1] - u.lon) > umbral) {
        // el camino real del turno (por la carretera, si la seguia) cuando el servidor lo manda: el de las propias
        const r = Array.isArray(u.recorrido) && u.recorrido.length >= 2 ? u.recorrido : null;
        const ruta = r ? [p, ...r.slice(1, -1), [u.lat, u.lon]] : [p, [u.lat, u.lon]];
        salida.push({ id: u.id, bando: u.bando, tipo: u.tipo, desde: p, hasta: [u.lat, u.lon], ruta });
      }
    }
    return salida;
  }

  /** Punto de la ruta [[lat, lon], ...] a la fraccion `f` (0 a 1) de su largo: la unidad avanza a velocidad pareja
   *  por cada tramo de la carretera, no en linea recta. */
  function puntoEnRuta(ruta, f) {
    if (!ruta || !ruta.length) return null;
    if (ruta.length === 1 || f <= 0) return ruta[0];
    if (f >= 1) return ruta[ruta.length - 1];
    const largos = [];
    let total = 0;
    for (let i = 1; i < ruta.length; i++) {
      const [a, b] = [ruta[i - 1], ruta[i]];
      const c = Math.cos(((a[0] + b[0]) / 2) * Math.PI / 180);
      const d = Math.hypot(b[0] - a[0], (b[1] - a[1]) * c);
      largos.push(d);
      total += d;
    }
    if (total <= 0) return ruta[ruta.length - 1];
    let falta = f * total;
    for (let i = 0; i < largos.length; i++) {
      if (falta <= largos[i] || i === largos.length - 1) {
        const t = largos[i] ? Math.min(1, falta / largos[i]) : 1;
        const [a, b] = [ruta[i], ruta[i + 1]];
        return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
      }
      falta -= largos[i];
    }
    return ruta[ruta.length - 1];
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
    base_aerea: "bases", deposito: "bases", puerto: "bases", punto_recobre: "bases",
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
    // defensa aerea: la municion es la reserva; con misiles aun en los lanzadores no esta "sin municion"
    const armasDA = u.sistema_da && Array.isArray(u.sistema_da.armas) ? u.sistema_da.armas : null;
    const listosDA = armasDA ? armasDA.reduce((t, a) => t + (a.listos || 0), 0) : 0;
    if (u.municion !== null && u.municion <= 0 && listosDA > 0) return { texto: `Sin reserva · ${listosDA} misiles listos`, clase: "mov" };
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

  /** Punto a `km` de (lat, lon) siguiendo el rumbo verdadero `rumbo` (0 = norte, 90 = este). */
  function destinoPorRumbo(lat, lon, rumbo, km) {
    const r = Math.PI / 180;
    const d = km / 6371;
    const la1 = lat * r;
    const lo1 = lon * r;
    const la2 = Math.asin(Math.sin(la1) * Math.cos(d) + Math.cos(la1) * Math.sin(d) * Math.cos(rumbo * r));
    const lo2 = lo1 + Math.atan2(Math.sin(rumbo * r) * Math.sin(d) * Math.cos(la1), Math.cos(d) - Math.sin(la1) * Math.sin(la2));
    return [la2 / r, ((lo2 / r + 540) % 360) - 180];
  }

  /**
   * Orden de rumbo, como el control de transito aereo (igual que tiempo_real.rumbo_objetivo): "virar" N grados a la
   * derecha o a la izquierda, o tomar el "rumbo" N por el lado pedido o por el mas corto. Devuelve el rumbo final, el
   * lado del viraje y cuantos grados gira.
   */
  function rumboObjetivo(actual, modo, grados, sentido) {
    const a = (((Number(actual) || 0) % 360) + 360) % 360;
    const g = Number(grados) || 0;
    let objetivo;
    let lado = sentido;
    if (modo === "virar") objetivo = (((sentido === "derecha" ? a + g : a - g) % 360) + 360) % 360;
    else {
      objetivo = ((g % 360) + 360) % 360;
      if (sentido !== "derecha" && sentido !== "izquierda") lado = ((objetivo - a + 360) % 360) <= 180 ? "derecha" : "izquierda";
    }
    const giro = lado === "derecha" ? (objetivo - a + 360) % 360 : (a - objetivo + 360) % 360;
    return { objetivo, lado, giro };
  }

  const rumbo3 = (g) => String(Math.round(g) % 360).padStart(3, "0");

  /** Texto de una orden de rumbo para la cola de ordenes: «Virar a la derecha 30° (rumbo 110°)», «Rumbo 270°». */
  function textoRumbo(detalle) {
    let d = {};
    try { d = JSON.parse(detalle || "{}"); } catch (_) { /* detalle viejo o vacio */ }
    const destino = d.objetivo != null ? ` (rumbo ${rumbo3(d.objetivo)}°)` : "";
    if (d.modo === "virar") return `Virar a la ${d.sentido} ${Math.round(d.grados)}°${destino}`;
    const lado = d.lado || (d.sentido === "corto" ? "" : d.sentido);
    return `Rumbo ${rumbo3(d.grados || 0)}°${lado ? `, virando a la ${lado}` : ""}`;
  }

  /**
   * Cargas de armamento del modelo (catalogo.cargas, engine/armas.py) para un select: [[id, «Aire-aire: AIM-120 ×4,
   * AIM-9X ×2»], ...]; la primera es la que el servidor elige si no se pide otra.
   */
  function opcionesDeCarga(cat, modeloId) {
    const cargas = (cat && cat.cargas && cat.cargas[modeloId]) || {};
    return Object.entries(cargas).map(([id, armas]) => [id, textoCarga(cat, id, armas)]);
  }

  /** Carga que conviene a un rol de mision, entre las que tiene el modelo. */
  function cargaParaRol(rol, disponibles) {
    const quiere = { CAP: "aire_aire", ESCOLTA: "aire_aire", INTERCEPCION: "aire_aire", INTERDICCION: "ataque", CAS: "ataque",
      SEAD: "sead", RECO: "reconocimiento" }[rol];
    return disponibles.includes(quiere) ? quiere : disponibles[0] || "";
  }

  /** «Aire-aire: AIM-120 AMRAAM ×4, AIM-9X ×2» (por aeronave). */
  function textoCarga(cat, id, armas) {
    const nombre = (cat && cat.nombres_carga && cat.nombres_carga[id]) || id;
    const partes = Object.entries(armas || {}).map(([a, n]) => `${(cat && cat.armas && cat.armas[a] && cat.armas[a].nombre) || a} ×${n}`);
    return `${nombre}: ${partes.length ? partes.join(", ") : "sin armas"}`;
  }

  /** Detalle de cada arma de una carga: alcance y probabilidad de impacto («AIM-120 AMRAAM: 75 km, Pk 0,6»). */
  function detalleArmas(cat, armas) {
    return Object.keys(armas || {}).map((a) => {
      const d = cat && cat.armas && cat.armas[a];
      return d ? `${d.nombre}: ${d.tipo_nombre}, ${Math.round(d.alcance_km)} km, Pk ${String(d.pk).replace(".", ",")}` : a;
    });
  }

  /** Eventos automaticos del director (engine/eventos_auto.py) en palabras: «cuando … → …». */
  const BANDO_TXT = { azul: "Azul", rojo: "Rojo", neutral: "Neutral", todos: "todos", cualquiera: "cualquier bando" };
  function textoAccionAuto(a) {
    if (!a) return "";
    if (a.tipo === "mensaje") return `mensaje a ${BANDO_TXT[a.para] || a.para}: «${a.texto}»`;
    if (a.tipo === "aparecer") return `aparecen ${a.cantidad} ${a.nombre || a.clase} (${BANDO_TXT[a.bando] || a.bando})`;
    if (a.tipo === "clima") return `el clima pasa a ${a.clima}`;
    if (a.tipo === "puntos") return `${a.puntos >= 0 ? "+" : ""}${a.puntos} puntos para ${BANDO_TXT[a.bando] || a.bando}`;
    if (a.tipo === "pausar") return "se pausa el reloj";
    if (a.tipo === "lanzar") return `${a.unidad} lanza ${a.misiles} misil(es) contra ${a.blanco}`;
    return a.tipo;
  }
  function textoReglaAuto(r) {
    const d = (r && r.disparador) || {};
    let cuando = d.tipo;
    if (d.tipo === "entra_area") cuando = `${d.unidad || (d.bando && d.bando !== "cualquiera" ? `una unidad ${BANDO_TXT[d.bando]}` : "una unidad")} entra a ${d.area_nombre ? `«${d.area_nombre}»` : "el área"}`;
    else if (d.tipo === "hora") cuando = `a las ${d.hora}`;
    else if (d.tipo === "destruida") cuando = `${d.unidad} es destruida`;
    else if (d.tipo === "objetivo") cuando = `el objetivo «${d.objetivo}» ${d.estado === "fallido" ? "falla" : "se cumple"}`;
    const disparos = r.disparos ? ` (disparada ${r.disparos} vez${r.disparos === 1 ? "" : "es"})` : "";
    return `cuando ${cuando}${r.repetir ? ", cada vez" : ""} → ${(r.acciones || []).map(textoAccionAuto).join("; ")}${disparos}`;
  }

  /** Guerra antisubmarina (engine/asw.py, datos en catalogo.asw). */
  const aswDe = (cat) => (cat && cat.asw) || { aviones: [], helos: [], torpedo_km: {} };
  const esAvionAsw = (u, cat) => !!u && u.tipo === "aerea" && aswDe(cat).aviones.includes(u.modelo);
  const esHeloAsw = (u, cat) => !!u && u.tipo === "aerea" && aswDe(cat).helos.includes(u.modelo);
  function alcanceTorpedo(u, cat) {
    if (!u || u.estado !== "activa") return 0;
    const km = aswDe(cat).torpedo_km || {};
    if (u.tipo === "aerea") return (esAvionAsw(u, cat) || esHeloAsw(u, cat)) && !u.en_tierra ? km.aerea || 0 : 0;
    return km[u.clase] || 0;
  }
  /** Minas navales (engine/minas.py, datos en catalogo.minas). */
  function siembraMinas(u, cat) {
    const m = (cat && cat.minas) || { navales: [], aereos: [] };
    if (!u || u.estado !== "activa") return false;
    if (u.tipo === "naval") return m.navales.includes(u.clase);
    return u.tipo === "aerea" && m.aereos.includes(u.clase);
  }
  const barreMinas = (u) => !!u && u.estado === "activa" && u.clase === "cazaminas";
  const PROFUNDIDADES = [["periscopica", "Cota periscópica"], ["profunda", "Profundidad"]];
  /** Señales sobre el icono de una unidad propia: lo urgente, de un vistazo (del enemigo no se sabe: ninguna). */
  const COMBUSTIBLE_BAJO = 25;
  function senalesUnidad(u) {
    if (!u || u.estado !== "activa" || u.combustible === null || u.combustible === undefined || u.tipo === "base") return [];
    const s = [];
    if (u.apresto && u.apresto.despega_en_min !== null && u.apresto.despega_en_min !== undefined) {
      s.push({ clase: "despega", texto: `↗ ${u.apresto.despega_en_min}'`, ayuda: `Carreteando: despega en ${u.apresto.despega_en_min} min` });
    }
    if (u.apresto && u.apresto.minutos === 0 && u.en_tierra) s.push({ clase: "averia", texto: "MANT", ayuda: "En mantenimiento" });
    if (u.combustible < COMBUSTIBLE_BAJO) s.push({ clase: "combustible", texto: "COMB", ayuda: `Poco combustible (${Math.round(u.combustible)} %)` });
    if (u.municion !== null && u.municion !== undefined && u.municion <= 5) s.push({ clase: "municion", texto: "MUN", ayuda: "Sin munición" });
    if (u.enlace === false) s.push({ clase: "enlace", texto: "S/E", ayuda: "Sin enlace de datos: su bando no ve lo que detecta" });
    const sistemas = u.sistemas ? Object.values(u.sistemas) : [];
    if (sistemas.some((x) => x.fuera)) s.push({ clase: "averia", texto: "AVER", ayuda: `Fuera de servicio: ${sistemas.filter((x) => x.fuera).map((x) => x.nombre).join(", ")}` });
    return s;
  }

  /** Anillos de alcance de cada arma de una unidad (de mayor a menor): su antiaerea, las armas de la carga que le
   * quedan, torpedos, defensa de punto, antimisil y misil balistico. */
  function anillosArmas(u, cat) {
    if (!u || u.estado !== "activa") return [];
    const out = [];
    const sumar = (km, nombre) => {
      if (km > 0 && !out.some((o) => o.nombre === nombre && Math.abs(o.km - km) < 0.5)) out.push({ km: Number(km), nombre });
    };
    const da = cat && cat.sistemas_da && u.modelo ? cat.sistemas_da[u.modelo] : null;
    if (da) for (const a of da.armas || []) sumar(a.alcance_max_km, a.nombre);
    const quedan = (u.armamento && u.armamento.quedan) || {};
    for (const [codigo, n] of Object.entries(quedan)) {
      const d = cat && cat.armas && cat.armas[codigo];
      if (d && n > 0) sumar(d.alcance_km, d.nombre);
    }
    sumar(alcanceTorpedo(u, cat), "Torpedo");
    const dp = cat && cat.defensa_punto && u.tipo === "naval" ? cat.defensa_punto[u.clase] : null;
    if (dp) sumar(dp.km, "Defensa de punto");
    if (u.antimisil) sumar(u.antimisil.km, "Antimisil");
    if (u.clase === "lanzador_balistico") sumar(500, "Misil balístico");
    return out.sort((a, b) => b.km - a.km);
  }

  /** Nombres que se pisan en la pantalla: de cada grupo de puntos a menos de `px` pixeles entre si, solo el primero
   * (el elegido, si esta) muestra su nombre; devuelve los ids que lo esconden. puntos: [{id, x, y, prioridad}]. */
  function rotulosTapados(puntos, px = 26) {
    const orden = [...puntos].sort((a, b) => (b.prioridad || 0) - (a.prioridad || 0));
    const visibles = [];
    const tapados = new Set();
    for (const p of orden) {
      if (visibles.some((q) => Math.abs(q.x - p.x) < px * 2.5 && Math.abs(q.y - p.y) < px)) tapados.add(p.id);
      else visibles.push(p);
    }
    return tapados;
  }

  /** Cuanto tarda y con cuanto combustible llega a cada punto de una ruta (en linea recta, aproximado: el servidor
   * calcula el terreno y las carreteras en la previsualizacion). Los tramos cambian la velocidad y la altura como
   * la orden (engine/movimiento.py): el tramo i es el que lleva al punto i. */
  const FACTOR_VELOCIDAD = { economica: [0.75, 0.85], crucero: [1, 1], maxima: [1.3, 2.2] };
  const CONSUMO_PERFIL = { alto: 0.85, medio: 1, rasante: 1.3 };
  function estimarRuta(u, waypoints, tramos) {
    if (!u || !(u.velocidad_kmh > 0)) return [];
    let lat = u.lat;
    let lon = u.lon;
    let horas = 0;
    let comb = u.combustible === null || u.combustible === undefined ? 100 : u.combustible;
    let modo = u.velocidad_actual || "crucero";
    let perfil = u.perfil_actual || "medio";
    return (waypoints || []).map((w, i) => {
      const t = (tramos || [])[i] || {};
      if (t.velocidad) modo = t.velocidad;
      if (t.perfil) perfil = t.perfil;
      const [fv, fc] = FACTOR_VELOCIDAD[modo] || [1, 1];
      const km = distanciaKm(lat, lon, w[0], w[1]);
      horas += km / (u.velocidad_kmh * fv);
      if (u.autonomia_km > 0) comb -= (km / u.autonomia_km) * 100 * fc * (u.tipo === "aerea" ? CONSUMO_PERFIL[perfil] || 1 : 1);
      [lat, lon] = w;
      return { minutos: Math.round(horas * 60), combustible: Math.round(comb), km: Math.round(km) };
    });
  }
  /** Texto de un punto de la ruta: "W2 · en 14 min · combustible 63 %". */
  function textoPuntoRuta(i, e) {
    if (!e) return `W${i + 1}`;
    const t = e.minutos >= 120 ? `${Math.floor(e.minutos / 60)} h ${e.minutos % 60} min` : `${e.minutos} min`;
    return `W${i + 1} · en ${t} · ${e.combustible < 0 ? "no llega: sin combustible" : `combustible ${e.combustible} %`} (aprox.)`;
  }

  /** Velocidad elegida de aeronaves y buques (engine/movimiento.py). */
  const VELOCIDADES = [["economica", "Económica"], ["crucero", "Crucero"], ["maxima", "Máxima"]];
  const AYUDA_VELOCIDAD = {
    economica: "Económica: 75 % de la velocidad; rinde más kilómetros y más tiempo en el aire o en el mar.",
    crucero: "Crucero: la velocidad normal.",
    maxima: "Máxima (postcombustión en los aviones): 30 % más rápido, pero gasta más del doble de combustible por kilómetro.",
  };
  /** Texto de un tramo de la ruta: "W2 · máxima · rasante". */
  function textoTramo(i, tramo) {
    const partes = [`W${i + 1}`];
    const v = VELOCIDADES.find(([k]) => k === (tramo || {}).velocidad);
    if (v) partes.push(v[1].toLowerCase());
    if (tramo && tramo.perfil) partes.push(tramo.perfil);
    return partes.join(" · ");
  }
  /** Apresto de una aeronave en tierra (engine/aeronaves.py): minutos de alerta; 0 = en mantenimiento. */
  const APRESTOS = [[5, "Alerta 5"], [15, "Alerta 15"], [30, "Alerta 30"], [60, "Alerta 60"], [0, "Mantenimiento"]];
  /** Texto del apresto para el panel de la unidad. */
  function textoApresto(a, enTierra) {
    if (!a) return "";
    if (a.despega_en_min != null) return `Carreteando: despega en ${a.despega_en_min} min.`;
    if (a.minutos === 0) return "En mantenimiento: no despega hasta que le cambie el apresto.";
    return `${enTierra ? "En tierra" : "Al volver a la base"}, una orden de vuelo la hace despegar en ${a.minutos} min.`;
  }

  /** Se intercepta una aeronave en vuelo o un buque (no un misil). */
  const interceptable = (u) => !!u && u.estado === "activa" && !esMisil(u) && ((u.tipo === "aerea" && !u.en_tierra) || u.tipo === "naval");
  const ACCIONES_INTERCEPCION = [["neutralizar", "Identificar y neutralizar"], ["seguir", "Identificar y seguir"], ["directo", "Neutralizar sin esperar la identificación"]];
  const FASES_INTERCEPCION = { alerta: "alerta en tierra", vectoreo: "vectoreo", contacto: "contacto", identificacion: "identificación",
    seguimiento: "seguimiento", ataque: "ataque", estima: "estima (contacto perdido)", busqueda: "búsqueda" };

  /** Cola de ordenes: «Interceptar a Bandido (identificar y seguir) · fase: contacto». */
  function textoIntercepcion(detalle, nombreObj) {
    let d = {};
    try { d = JSON.parse(detalle || "{}"); } catch (_) { /* detalle vacio */ }
    const accion = (ACCIONES_INTERCEPCION.find(([k]) => k === d.accion) || [null, "Identificar y neutralizar"])[1].toLowerCase();
    return `Interceptar a ${nombreObj} (${accion})` + (d.fase ? ` · fase: ${FASES_INTERCEPCION[d.fase] || d.fase}` : "");
  }

  /** Estimacion de una interceptacion antes de emitirla (POST /ordenes/interceptacion) en palabras. */
  function textoEstimacionIntercepcion(e) {
    if (!e) return "";
    if (e.motivo_no) return e.motivo_no;
    const partes = [];
    if (e.despegue_min) partes.push(`Despega en ${e.despegue_min} min (alerta en tierra).`);
    if (!e.alcanzable) partes.push(e.motivo || "No lo alcanza: lo perseguirá por si cambia de rumbo.");
    else {
      partes.push(`Lo alcanza en ${e.minutos} min${e.hora ? ` (a las ${e.hora})` : ""}, a ${e.km} km; llega con ${Math.max(0, Math.round(e.combustible_llegada))} % de combustible.`);
      if (e.combustible_regreso != null) partes.push(`Para volver a ${e.base} le quedaría ${Math.round(e.combustible_regreso)} %.`);
      if (e.motivo) partes.push(e.motivo);
    }
    partes.push(`Blanco a ${e.velocidad_blanco_kmh} km/h; propio a ${e.velocidad_propia_kmh} km/h.`);
    if (e.identifica) partes.push(e.armas === "restringido" ? "Armas restringidas: lo identificará a la vista antes de tirar." : "Lo identificará a la vista (a menos de 8 km) antes de actuar.");
    return partes.join(" ");
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

  /** Armamento de la OTA que lleva el modelo, como [[codigo, "codigo · nombre"]]. Para el armamento primario, solo el
   *  que sirve al rol: aire-aire para CAP y escolta, aire-superficie para interdiccion, CAS y SEAD. */
  function armasParaRol(catOta, modeloId, rolId, primario = true) {
    if (!catOta || !catOta.armamento) return [];
    const lista = (catOta.por_modelo || {})[modeloId] || ["M120", "M9X", "MPB", "BMK", "BBU"];
    const aa = ["CAP", "ESCOLTA"].includes(rolId);
    const sup = ["INTERDICCION", "CAS", "SEAD"].includes(rolId);
    return lista.filter((c) => catOta.armamento[c]).filter((c) => {
      if (!primario) return true;
      const t = catOta.armamento[c].tipo;
      return aa ? t === "aa" : sup ? t !== "aa" : true;
    }).map((c) => [c, `${c} · ${catOta.armamento[c].nombre}`]);
  }

  /** Rumbo, distancia y altitud de un tramo de la ruta: "045° · 54 NM · 5000 ft". */
  function textoTramo(t) {
    if (!t) return "";
    return `${String(t.rumbo).padStart(3, "0")}° · ${t.nm} NM` + (t.altitud_ft ? ` · ${t.altitud_ft} ft` : "");
  }

  // ---------------------------------------------------------------- recuperacion de personal (engine/rescate.py)
  const ESTADOS_DERRIBADO = { aislado: "Aislados: esperan rescate", rescatado: "Rescatados", capturado: "Capturados", perdido: "Perdidos" };

  /** "2 tripulantes de Halcón · aislados desde T5 (en el agua)". */
  function textoDerribado(d) {
    if (!d) return "";
    const quien = `${d.tripulantes} tripulante${d.tripulantes === 1 ? "" : "s"}${d.grupo ? ` de ${d.grupo}` : ""}`;
    const donde = d.medio === "agua" ? " (en el agua)" : "";
    if (d.estado === "aislado") return `${quien} · aislados desde T${d.turno}${donde}`;
    const por = d.por ? ` por ${d.por}` : "";
    return `${quien} · ${(ESTADOS_DERRIBADO[d.estado] || d.estado).toLowerCase()}${d.estado === "perdido" ? "" : por} en T${d.turno_fin}`;
  }

  /** Tripulacion propia aislada mas cercana a un punto (para el rescate), o null. */
  function derribadoCercano(derribados, bando, lat, lon, km = 15) {
    let mejor = null;
    for (const d of derribados || []) {
      if (d.estado !== "aislado" || d.bando !== bando) continue;
      const dist = distanciaKm(lat, lon, d.lat, d.lon);
      if (dist <= km && (!mejor || dist < mejor.dist)) mejor = { d, dist };
    }
    return mejor ? mejor.d : null;
  }

  /** Calculo de armamento en una frase: "Para «neutraliza…» hacen falta 24 BMK (12 en el blanco, 4 DMPI): 4 aeronaves; lleva 12." */
  function textoWeaponeering(w) {
    if (!w) return "";
    return `Cálculo de armamento (${w.blanco_nombre.toLowerCase()}, «${w.criterio_nombre.toLowerCase()}», ${w.angulo}°): `
      + `${w.impactos} ${w.arma} en el blanco (${w.dmpi} DMPI) y ${w.lanzar} a lanzar${w.guiada ? " (guiadas)" : " (×3 por la dispersión)"}`
      + `: ${w.aeronaves_necesarias} aeronave${w.aeronaves_necesarias === 1 ? "" : "s"} de ${w.por_aeronave}`
      + (w.lleva !== undefined ? `; el grupo lleva ${w.lleva}${w.suficiente ? "" : " (no alcanza)"}` : "")
      + `. Radio de escombros ${w.radio_escombros_m} m.`;
  }

  /** Fila del cuadro de anillos de Warden: [nombre, objetivos, "2 neutralizados · 1 destruido", ejemplos]. */
  function filaWarden(f) {
    const estado = [[f.degradados, "degradado"], [f.neutralizados, "neutralizado"], [f.destruidos, "destruido"], [f.sin_noticias, "sin noticias"]]
      .filter(([n]) => n).map(([n, t]) => `${n} ${t}${n === 1 || t === "sin noticias" ? "" : "s"}`).join(" · ");
    return [f.nombre, String(f.objetivos), estado || (f.objetivos ? "operativos" : "—"), (f.ejemplos || []).join(", ")];
  }

  // ---------------------------------------------------------------- apresto operacional (engine/apresto.py)
  const ASPECTOS_APRESTO = ["personal", "armamento", "equipamiento", "adiestramiento", "c3"];

  /** Linea del grado del bando: "Elevado Apresto Operacional (fase naranja) · aeronaves listas 80 % · ..." */
  function textoGradoApresto(r) {
    if (!r) return "";
    const c = r.config || {};
    return `${r.grado_nombre}${c.grado === "elevado" && r.fase_nombre ? ` (fase ${r.fase_nombre})` : ""}`
      + ` · aeronaves listas ${r.aeronaves_listas_pct} %`
      + ` · reservas y milicia ${r.reservas_incorporadas ? "incorporadas" : "sin incorporar (evento 2 de la PCAO)"}`
      + ` · ${r.tienen} de ${r.total} unidad${r.total === 1 ? "" : "es"} con apresto.`;
  }

  /** Celdas de una unidad en el cuadro de apresto (en %): [nombre, {texto, bajo} x 5, "Sí" | "No"]. */
  function filaApresto(f, minimos) {
    return [f.nombre, ...ASPECTOS_APRESTO.map((k) => ({ texto: String(Math.round(f.aspectos[k])), bajo: f.aspectos[k] < minimos[k] })),
      f.tiene ? "Sí" : "No"];
  }

  /** Estado de cada evento de la PCAO: "1. Activación ... · 2 turnos · cumplido". */
  function lineasPcao(p) {
    if (!p) return [];
    return p.eventos.map((e) => `${e.nombre} · ${e.plazo} turno${e.plazo === 1 ? "" : "s"}${e.estado ? ` · ${e.estado}` : ""}`);
  }

  // ---------------------------------------------------------------- tarjeta tactica dinamica de una unidad
  const NOMBRE_PERFIL_CORTO = { alto: "alto", medio: "medio", rasante: "rasante" };

  /** Estado de la unidad para su simbolo: "critico" (fuerza < 30), "degradado" (< 70), "sin-combustible" (aeronave propia
   *  con 25 % o menos) o "" (sin novedad; la fuerza enemiga no se conoce). */
  function estadoSimbolo(u) {
    if (!u || u.fuerza === null || u.fuerza === undefined) return "";
    if (u.fuerza < 30) return "critico";
    if (u.fuerza < 70) return "degradado";
    if (u.tipo === "aerea" && u.combustible !== null && u.combustible !== undefined && u.combustible <= 25 && !u.en_tierra) return "sin-combustible";
    return "";
  }

  /** Etapa de un contacto enemigo y su incertidumbre (backend/app/engine/contactos_vivo.py); "" si no corresponde. */
  function textoEtapa(u) {
    if (!u || !u.etapa) return "";
    const nombre = { desconocido: "Contacto desconocido", clasificado: "Contacto clasificado", identificado: "Contacto identificado" }[u.etapa] || u.etapa;
    const inc = Number(u.incertidumbre_km) || 0;
    if (inc < 0.05) return nombre;
    return `${nombre} · posición ± ${inc < 10 ? inc.toFixed(1).replace(".", ",") : Math.round(inc)} km`;
  }

  /** Lineas de la tarjeta tactica: lo que se sabe de la unidad ahora (las propias, todo; las enemigas, lo visible). */
  function lineasTarjeta(u, orden) {
    if (!u) return [];
    const out = [];
    if (u.etapa) out.push(textoEtapa(u));
    const conocido = u.fuerza !== null && u.fuerza !== undefined;
    out.push(conocido ? `Fuerza ${Math.round(u.fuerza)} %` : "Fuerza desconocida (enemigo)");
    if (conocido && u.tipo !== "base" && u.combustible !== null && u.combustible !== undefined) {
      out.push(`Combustible ${Math.round(u.combustible)} % · Munición ${Math.round(u.municion ?? 0)} %`);
    }
    if (u.tipo === "aerea" && !esMisil(u)) {
      const n = u.aeronaves ? `${u.aeronaves} aeronave${u.aeronaves === 1 ? "" : "s"} · ` : "";
      const vuelo = u.en_tierra
        ? `en tierra${u.espera_restante ? `, lista en ${u.espera_restante} turno${u.espera_restante === 1 ? "" : "s"}` : ", lista"}`
        : `en vuelo${u.perfil_actual ? `, perfil ${NOMBRE_PERFIL_CORTO[u.perfil_actual] || u.perfil_actual}` : ""}`;
      out.push(n + vuelo);
    }
    if (u.mision === "patrulla") out.push("Patrulla: intercepta lo que entre a su alcance");
    if (orden) out.push(`Orden pendiente: ${orden.tipo}${orden.detalle ? ` (${orden.detalle})` : ""}`);
    const e = estadoSimbolo(u);
    if (e === "critico") out.push("Situación crítica: casi sin capacidad de combate");
    else if (e === "sin-combustible") out.push("Combustible bajo: debe regresar");
    return out;
  }

  /** Paquete y funcion de una mision en la OTA: "paq. TELA (CM)" ("" si no va en un paquete). */
  function textoPaquete(m) {
    const o = (m && m.ota) || {};
    if (!o.paquete) return "";
    return `paq. ${o.paquete}${o.funcion && o.funcion !== "-" ? ` (${o.funcion})` : ""}`;
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
    if (bando === "neutral") return "Neutrales (tráfico civil y países ajenos)";
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
  // ---- unidades de medida: la aviacion, la defensa aerea y la armada en nudos, millas nauticas y pies; las fuerzas
  // terrestres en km. El motor trabaja siempre en km, km/h y metros. ----
  const UNIDADES = {
    distancia: { nombre: "Distancia", base: "km", unidades: { km: ["km", 1], nm: ["NM (milla náutica)", 1.852], mi: ["mi (milla terrestre)", 1.609344], m: ["m", 0.001], ft: ["ft (pie)", 0.0003048] } },
    velocidad: { nombre: "Velocidad", base: "kmh", unidades: { kmh: ["km/h", 1], kt: ["kt (nudo)", 1.852], mph: ["mph", 1.609344], ms: ["m/s", 3.6], mach: ["Mach (nivel del mar)", 1225.04] } },
    altura: { nombre: "Altura", base: "m", unidades: { m: ["m", 1], ft: ["ft (pie)", 0.3048], km: ["km", 1000], fl: ["FL (nivel de vuelo)", 30.48] } },
    masa: { nombre: "Masa", base: "kg", unidades: { kg: ["kg", 1], lb: ["lb (libra)", 0.45359237], t: ["t", 1000] } },
    volumen: { nombre: "Volumen", base: "l", unidades: { l: ["l", 1], gal: ["gal (galón EE. UU.)", 3.785411784], m3: ["m³", 1000] } },
  };

  /** Convierte `valor` de la unidad `de` a la unidad `a` dentro de una magnitud de UNIDADES. */
  function convertir(magnitud, valor, de, a) {
    const m = UNIDADES[magnitud];
    if (!m || !m.unidades[de] || !m.unidades[a]) return null;
    return (Number(valor) * m.unidades[de][1]) / m.unidades[a][1];
  }

  /** "aeronautico" (aviacion y defensa aerea), "naval" (armada) o "metrico" (fuerzas terrestres). */
  function sistemaMedidas(u, clase) {
    if (!u) return "metrico";
    if (u.tipo === "aerea") return "aeronautico";
    if (u.tipo === "naval") return "naval";
    if (clase && (clase.defensa_aerea || (clase.emisor && clase.solo_aereo))) return "aeronautico";
    return "metrico";
  }

  const numeroEs = (v, dec = 0) => Number(v).toLocaleString("es", { maximumFractionDigits: dec, minimumFractionDigits: 0 });

  /** Texto de una medida (el motor da km, km/h o m) en el sistema de la unidad: "486 kt (900 km/h)", "24 NM (45 km)",
   * "20.000 ft (6.000 m)"; en el metrico, solo "45 km". */
  function medida(sistema, magnitud, valor) {
    if (valor === null || valor === undefined) return "?";
    const v = Number(valor);
    if (sistema === "metrico") {
      return magnitud === "velocidad" ? `${numeroEs(v)} km/h` : magnitud === "altura" ? `${numeroEs(v)} m` : `${numeroEs(v, 1)} km`;
    }
    if (magnitud === "velocidad") return `${numeroEs(v / 1.852)} kt (${numeroEs(v)} km/h)`;
    if (magnitud === "altura") return `${numeroEs(v / 0.3048, 0)} ft (${numeroEs(v)} m)`;
    const nm = v / 1.852;
    return `${numeroEs(nm, nm < 100 ? 1 : 0)} NM (${numeroEs(v, v < 100 ? 1 : 0)} km)`;
  }

  /** Filas de la ficha tecnica de una aeronave (engine/plataformas.py) para la interfaz. */
  function filasFicha(f) {
    if (!f) return [];
    const ft = (m) => `${numeroEs(m)} m (${numeroEs(m / 0.3048)} ft)`;
    return [
      ["Roles", f.roles_nombres.join(", ")],
      ["Velocidad en ruta / máx.", `${numeroEs(f.crucero_kt)} kt / ${numeroEs(f.max_kt)} kt`],
      ["Radio de acción", `${numeroEs(f.radio_nm)} NM (${numeroEs(f.radio_nm * 1.852)} km)`],
      ["Techo", `${numeroEs(f.techo_ft)} ft`],
      ["Combustible interno", `${numeroEs(f.combustible_kg)} kg · ${numeroEs(f.consumo_kg_h)} kg/h${f.autonomia_h ? ` (${numeroEs(f.autonomia_h, 1)} h)` : ""}`],
      ["Oxígeno líquido", f.lox_l ? `${numeroEs(f.lox_l, 1)} l · ${numeroEs(f.lox_l_h, 1)} l/h${f.lox_horas ? ` (${numeroEs(f.lox_horas, 1)} h)` : ""}` : (f.tripulacion ? "Genera su oxígeno a bordo (OBOGS)" : "No tripulada")],
      ["Despegue / aterrizaje", f.despegue_m || f.aterrizaje_m ? `${f.despegue_m ? ft(f.despegue_m) : "vertical"} / ${f.aterrizaje_m ? ft(f.aterrizaje_m) : "vertical"}` : "Vertical (no necesita pista)"],
      ["Tripulación", f.tripulacion ? `${f.tripulacion} por aeronave` : "No tripulada (se opera desde tierra)"],
    ];
  }

  /** La aeronave puede despegar de la pista util de la base (sin ficha o sin pista: si). */
  function entraEnPista(modelo, base) {
    const f = modelo && modelo.ficha;
    if (!f || !base || base.pista_util_m === null || base.pista_util_m === undefined) return true;
    return !f.despegue_m || f.despegue_m <= base.pista_util_m;
  }

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

  // ---- ciudades segun el zoom: de lejos solo las grandes, y los nombres aparecen al acercarse ----
  /** Nivel de una ciudad por su poblacion: 1 metropolis (5 millones o mas), 2 de un millon, 3 de 300 000, 4 el resto. */
  function nivelLugar(pop) {
    const p = Number(pop) || 0;
    return p >= 5e6 ? 1 : p >= 1e6 ? 2 : p >= 3e5 ? 3 : 4;
  }
  const ZOOM_PUNTO_LUGAR = { 1: 3, 2: 5, 3: 6, 4: 7 }; // desde que zoom se ve el punto de cada nivel
  const ZOOM_NOMBRE_LUGAR = { 1: 5, 2: 6, 3: 7, 4: 8 }; // y desde cual su nombre
  /** Niveles de ciudad cuyo punto o cuyo nombre se esconden a este zoom. */
  function lugaresOcultos(zoom) {
    const niveles = [1, 2, 3, 4];
    return { puntos: niveles.filter((n) => zoom < ZOOM_PUNTO_LUGAR[n]), nombres: niveles.filter((n) => zoom < ZOOM_NOMBRE_LUGAR[n]) };
  }
  /**
   * Filtro de ciudades repetidas: cada region del mapa trae sus propias ciudades, y donde se superponen (Venezuela
   * dentro de America, America dentro del mundo) la misma ciudad llega dos o tres veces con coordenadas casi iguales.
   */
  function filtroLugaresRepetidos() {
    const vistos = new Map();
    return (nombre, lon, lat) => {
      const previos = vistos.get(nombre) || [];
      if (previos.some(([x, y]) => Math.abs(x - lon) < 0.5 && Math.abs(y - lat) < 0.5)) return false;
      previos.push([lon, lat]);
      vistos.set(nombre, previos);
      return true;
    };
  }

  /** Rotulo de un tramo de carretera apto como pista de un PRO (tools/preparar_tramos_pro.py). */
  function textoTramoPro(p) {
    const via = [p.ref, p.nombre].filter(Boolean).join(" ") || "Carretera";
    const miles = (n) => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return `${p.id} · ${via}: tramo recto de ${miles(p.largo_m)} m, ancho ${p.ancho_m} m, pendiente ${p.pendiente_pct} %`;
  }

  /** Factor de tamaño de miniaturas y simbolos: 0,35 de lejos (pais entero), 1 hacia el zoom 10, hasta 1,5 de cerca. */
  function escalaUnidad(zoom) {
    return Math.max(0.35, Math.min(1.5, 0.75 + 0.15 * (zoom - 8)));
  }

  /** Factor de tamaño de las aeronaves en vuelo: de cerca (zoom 10 o mas) como las demas unidades; de lejos se achican
   * mas rapido (0,65 en el zoom 8, 0,45 en el 7, hasta 0,28), porque en un ataque hay decenas de grupos juntos. */
  function escalaAeronave(zoom) {
    if (zoom >= 10) return escalaUnidad(zoom);
    return Math.max(0.28, escalaUnidad(10) - 0.2 * (10 - zoom));
  }

  /** Siluetas que dibuja un grupo aereo: la formacion completa de cerca, hasta 2 en el zoom 8 y una sola mas lejos
   * (el numero de aviones sigue en el rotulo y en la tarjeta de la unidad). */
  function siluetasGrupo(n, zoom) {
    const total = Math.max(1, n || 1);
    if (zoom >= 9) return total;
    return Math.min(total, zoom >= 8 ? 2 : 1);
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
    MAPA_VENEZUELA, ordenarMapas, limitesDe, limitesDeMapas, textoMapa, ZOOM_ROTULOS, ZOOM_ALCANCES, ZOOM_CARRETERAS, textoTramoPro,
    nivelLugar, lugaresOcultos, filtroLugaresRepetidos, escalaUnidad, escalaAeronave, siluetasGrupo, unidadesConAlcance,
    PERFILES_VUELO, textoPerfil, muestraCobertura, resumenSistemaDA, UNIDADES, convertir, sistemaMedidas, medida,
    filasFicha, entraEnPista,
    NIVELES_OBJETIVO, arbolObjetivos, superioresPosibles, textoCalendario, nombreFase, CONDUCCION,
    PUESTOS, puestoDe, puestoPuede, puestoPuedeAereo, puestosResponsables, etiquetaPuesto, funcionDeOrden, unidadesDelPuesto, textoPuestoAjeno,
    claseEsDron, modeloEsDron, interferenciasSobre, puedeInterferir, textoInterferido,
    ESTADOS_MISION, TIPOS_PUNTO_MISION, misionActiva, horaEstimada, textoMision, tramosCronograma, armasParaRol, textoTramo, textoPaquete,
    ESTADOS_DERRIBADO, textoDerribado, derribadoCercano, textoWeaponeering, filaWarden, estadoSimbolo, lineasTarjeta, textoEtapa,
    ASPECTOS_APRESTO, textoGradoApresto, filaApresto, lineasPcao,
    RADIO_SIN_EMISION_KM, deteccionEfectiva, pctStock,
    nacionDe, etiquetaBandoNacion, filtrarUnidades, textoObjetivo, avanceObjetivo, ETIQUETA_OBJETIVO, CAPACIDAD_BASE, RADIO_ATERRIZAJE_KM, estacionadasEn, plazasLibres, opcionesDeAterrizaje, situacionDeVuelo,
    modeloDe, rotuloModelo, aeronavesOperativas, basesAereasPropias, detalleDespegue, textoDespegue,
    aeronavesComprometidas, baseEnEscenario, nombreCortoBase, FUERZA_MINIMA_BASE, modoAerodromo, colorAerodromo, ZOOM_AEROPUERTOS, ZOOM_ICONOS_AERODROMO,
    esMisil, operaAeronaves, esPortaaviones, plazasDe, esEmbarcable, puedeOperarEn, modeloDespegaDe, puedeLanzarMisiles,
    esAeronave, filtrarModelos,
    misilesDisponibles, textoMisil, MAX_MISILES_SALVA, MUNICION_POR_MISIL, PISTA_INOPERATIVA, PARTES_BASE, textoPartesBase,
    esTransporte, embarcada, aBordo, transportesCercanos, CAPACIDAD_TRANSPORTE, esAvionTransporte, capacidadTransporte,
    paracaidistasABordo, puedeLanzarParacaidistas, puedeDesembarcar,
    distanciaKm, destinoPorRumbo, rumboObjetivo, textoRumbo, siembraMinas, barreMinas, textoDefensaPunto, esAvionAsw, esHeloAsw, alcanceTorpedo, PROFUNDIDADES, APRESTOS, textoApresto, senalesUnidad, estimarRuta, textoPuntoRuta, rotulosTapados, anillosArmas, VELOCIDADES, AYUDA_VELOCIDAD, textoTramo, textoReglaAuto, textoAccionAuto, opcionesDeCarga, cargaParaRol, textoCarga, detalleArmas, interceptable, ACCIONES_INTERCEPCION, FASES_INTERCEPCION, textoIntercepcion, textoEstimacionIntercepcion, etiquetaCanal, canalesDe, resumenEntrega, TIPOS_GRAFICO, latLngsDe, puedeBorrarGrafico,
    BANDOS, esBando, pct, fechaUtc, segundosRestantes, formatoTiempo, objetivosDisponibles,
    unidadesConOrdenes, etiquetaClima, textoListos, trayectorias, movimientosDelTurno, puntoEnRuta, lineasCombate, describirCombate,
    turnosReproducibles, RAMAS, ramaDe, agruparPorRama, horaSimulada, textoHora, efectosClima, visibilidadPct,
    etiquetaBando, claseBarra, estadoUnidad, memoriaVacia, alertasNuevas, climaEn, textoZonaClima,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Logica = api;
})(typeof window !== "undefined" ? window : globalThis);
