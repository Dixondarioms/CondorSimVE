/* Plano detallado de los aerodromos: pistas, calles de rodaje, plataformas, hangares y edificios reales
 * (OpenStreetMap, ver tools/preparar_aerodromos.py), con las marcas de pista y la numeracion de cada cabecera.
 * Aparece al acercarse (zoom 11 en adelante) en su propio panel, debajo de las unidades, y muestra el estado de la
 * base del escenario que la ocupa: crateres en la pista segun el daño y las cruces de pista cerrada cuando ya no
 * puede operar.
 *
 * Hay un archivo por aerodromo (geo/aerodromos/<OACI>.json, ~1 300 en toda America) y un indice: solo se descargan
 * los planos de los aerodromos que quedan a la vista al acercarse. Los archivos traen lo minimo (eje y ancho de las
 * calles de rodaje, extremos y ancho de las pistas): las marcas de pista y el ancho a escala se calculan aca.
 *
 * La logica (crateres, marcas, escalas, busqueda de la base) es pura y se prueba con Node; el dibujo usa Leaflet. */
(function (raiz) {
  "use strict";

  const ZOOM_PLANO = 11; // desde aca se ve el contorno del aerodromo, las pistas y las plataformas
  const ZOOM_DETALLE = 14; // marcas de pista, eje de rodaje y numeracion
  const ZOOM_CARGA = 10; // los planos de lo que esta a la vista se piden un poco antes de mostrarse
  const MARGEN_CARGA_KM = 15; // y tambien los de los aerodromos apenas fuera de la pantalla
  const RADIO_BASE_KM = 4; // una unidad base_aerea a esta distancia de la pista "ocupa" el aerodromo
  const FUERZA_MINIMA_BASE = 25; // igual que el motor: por debajo la base no opera
  const PISTA_INOPERATIVA = 60; // % de daño de la pista a partir del cual no hay despegues ni aterrizajes

  const COLORES = {
    aerodromo: { color: "#d8c690", weight: 1, dashArray: "5 4", fillColor: "#6c7a50", fillOpacity: 0.55 },
    plataforma: { color: "#7a7e80", weight: 1, fillColor: "#a3a6a7", fillOpacity: 1 },
    rodaje: { color: "#6a6e72", opacity: 1, lineCap: "round", lineJoin: "round" },  // linea con el ancho real a escala
    helipuerto: { color: "#f2f2ec", weight: 1.5, fillColor: "#56595d", fillOpacity: 1 },
    pista: { color: "#202225", weight: 1, fillColor: "#2e3134", fillOpacity: 1 },
    marca: { stroke: false, fillColor: "#f4f4ee", fillOpacity: 0.95 },
    edificio: { color: "#6b655c", weight: 1, fillColor: "#bdb4a5", fillOpacity: 1 },
    hangar: { color: "#56616a", weight: 1, fillColor: "#9eabb3", fillOpacity: 1 },
    torre: { color: "#6b655c", weight: 1, fillColor: "#e1d9c8", fillOpacity: 1 },
  };
  const ALTO_POR_DEFECTO = { edificio: 6, hangar: 12, torre: 20 };

  // ---------------------------------------------------------------- logica pura
  const R = Math.PI / 180;
  function distanciaKm(lat1, lon1, lat2, lon2) {
    const dLat = (lat2 - lat1) * R, dLon = (lon2 - lon1) * R;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * R) * Math.cos(lat2 * R) * Math.sin(dLon / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(a));
  }

  /** Punto a `s` metros del extremo A de la pista hacia B, desplazado `t` metros a estribor. */
  function puntoEnPista(pista, s, t = 0) {
    const [[la1, lo1], [la2, lo2]] = pista.extremos;
    const ky = 110574, kx = 111320 * Math.cos(la1 * R);
    const dx = (lo2 - lo1) * kx, dy = (la2 - la1) * ky;
    const largo = Math.hypot(dx, dy) || 1;
    const ux = dx / largo, uy = dy / largo;
    const x = ux * s + uy * t, y = uy * s - ux * t;
    return [la1 + y / ky, lo1 + x / kx];
  }

  /**
   * Marcas pintadas de una pista (anillos [[lat, lon], ...]) a partir de sus extremos y su ancho, en metros reales:
   * bordes, umbrales tipo "piano" en ambas cabeceras (con hueco central para la numeracion), eje discontinuo y, en
   * las pistas de mas de 1200 m, punto de visada y zona de toma de contacto.
   */
  function marcasPista(pista) {
    const largo = pista.largo_m, ancho = pista.ancho_m, medio = ancho / 2;
    const out = [];
    const barra = (s0, s1, t, w) => out.push([
      puntoEnPista(pista, s0, t - w / 2), puntoEnPista(pista, s1, t - w / 2),
      puntoEnPista(pista, s1, t + w / 2), puntoEnPista(pista, s0, t + w / 2),
    ]);
    barra(0, largo, medio - 1.5, 1.2);
    barra(0, largo, -medio + 1.5, 1.2);
    const franjas = Math.max(4, Math.min(16, Math.floor(ancho / 5.5)));
    const paso = (ancho - 6) / franjas;
    for (const s0 of [6, largo - 36]) {
      for (let k = 0; k < franjas; k++) {
        const t = -medio + 3 + paso * (k + 0.5);
        if (Math.abs(t) < paso * 0.6) continue;
        barra(s0, s0 + 30, t, paso * 0.55);
      }
    }
    for (let s = 130; s + 30 < largo - 130; s += 50) barra(s, s + 30, 0, 2.5);
    if (largo > 1200) {
      for (const s0 of [300, largo - 345]) for (const lado of [1, -1]) barra(s0, s0 + 45, lado * (medio - 11), 6);
      for (const s0 of [150, 450, largo - 180, largo - 480]) for (const lado of [1, -1]) barra(s0, s0 + 22, lado * (medio - 11), 2.5);
    }
    return out;
  }

  /** Pixeles que ocupan `metros` en el mapa (Web Mercator) a esa latitud y ese zoom. */
  function metrosAPixeles(metros, lat, zoom) {
    return metros / ((156543.03392 * Math.cos(lat * R)) / 2 ** zoom);
  }

  /** Aerodromos del indice dentro del recuadro {sur, oeste, norte, este} ampliado `margenKm`, el mas central primero. */
  function aerodromosEnVista(indice, caja, margenKm = 0) {
    const dLat = margenKm / 110.574;
    const latMedia = (caja.sur + caja.norte) / 2;
    const dLon = margenKm / (111.32 * Math.max(0.2, Math.cos(latMedia * R)));
    const centro = [latMedia, (caja.oeste + caja.este) / 2];
    return indice
      .filter((b) => b.lat >= caja.sur - dLat && b.lat <= caja.norte + dLat && b.lon >= caja.oeste - dLon && b.lon <= caja.este + dLon)
      .sort((a, b) => distanciaKm(a.lat, a.lon, ...centro) - distanciaKm(b.lat, b.lon, ...centro));
  }

  /** Generador pseudoaleatorio reproducible (mulberry32): los crateres no "saltan" al redibujar. */
  function azar(semilla) {
    let a = semilla >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /** Cantidad de crateres segun la fuerza de la base (0 intacta, hasta 14 destruida). */
  const cantidadCrateres = (fuerza) => (fuerza >= 97 ? 0 : Math.min(14, Math.ceil((100 - Math.max(0, fuerza)) / 7)));

  /**
   * Crateres sobre las pistas de un aerodromo: [{ lat, lon, radio_m }]. Deterministas para una misma base (semilla)
   * y crecientes con el daño: con menos fuerza aparecen los mismos mas otros nuevos.
   */
  function crateres(pistas, fuerza, semilla) {
    const n = cantidadCrateres(fuerza);
    if (!n || !pistas.length) return [];
    const rnd = azar(semilla || 1);
    const out = [];
    for (let i = 0; i < n; i++) {
      const p = pistas[i % pistas.length];
      const s = p.largo_m * (0.12 + 0.76 * rnd());
      const t = (rnd() - 0.5) * p.ancho_m * 0.8;
      const [lat, lon] = puntoEnPista(p, s, t);
      out.push({ lat, lon, radio_m: 9 + rnd() * 9 });
    }
    return out;
  }

  /** Tamaño (px) de la numeracion de pista: acompaña al zoom, como si estuviera pintada. */
  const tamNumero = (zoom) => Math.round(Math.max(9, Math.min(34, 9 * 2 ** ((zoom - 14) * 0.75))));

  /** La unidad base_aerea que ocupa el aerodromo (la mas cercana a su pista principal, a <= 4 km), o null. */
  function baseQueOcupa(aerodromo, unidades) {
    const [lat, lon] = aerodromo.centro;
    let mejor = null, dmin = RADIO_BASE_KM;
    for (const u of unidades || []) {
      if (u.clase !== "base_aerea") continue;
      const d = distanciaKm(lat, lon, u.lat, u.lon);
      if (d <= dmin) { mejor = u; dmin = d; }
    }
    return mejor;
  }

  function enAnillo(x, y, anillo) {
    let dentro = false;
    for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
      const [xi, yi] = anillo[i], [xj, yj] = anillo[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-12) + xi) dentro = !dentro;
    }
    return dentro;
  }

  function areaAnillo(anillo) {
    let a = 0;
    for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) a += (anillo[j][0] + anillo[i][0]) * (anillo[j][1] - anillo[i][1]);
    return Math.abs(a / 2);
  }

  /**
   * `n` puestos de estacionamiento repartidos sobre las plataformas (anillos [lon, lat]): [[lat, lon], ...].
   * Se buscan puntos de una grilla de ~20 m dentro de las plataformas y se eligen lo mas separados posible,
   * empezando por el centro de la plataforma mayor. Deterministico.
   */
  function puestos(plataformas, n) {
    if (!n || !plataformas || !plataformas.length) return [];
    const mayor = plataformas.reduce((a, x) => (areaAnillo(x) > areaAnillo(a) ? x : a));
    const lat0 = mayor[0][1];
    const paso = 20 / 110574, pasoLon = 20 / (111320 * Math.cos(lat0 * R));
    const cand = [];
    for (const anillo of plataformas) {
      const xs = anillo.map((q) => q[0]), ys = anillo.map((q) => q[1]);
      for (let y = Math.min(...ys) + paso / 2; y < Math.max(...ys); y += paso) {
        for (let x = Math.min(...xs) + pasoLon / 2; x < Math.max(...xs); x += pasoLon) {
          if (enAnillo(x, y, anillo)) cand.push([y, x]);
        }
      }
      if (cand.length > 4000) break;
    }
    if (!cand.length) return [];
    const cx = mayor.reduce((a, q) => a + q[0], 0) / mayor.length, cy = mayor.reduce((a, q) => a + q[1], 0) / mayor.length;
    const d = (a, b) => distanciaKm(a[0], a[1], b[0], b[1]);
    const elegidos = [cand.reduce((a, c) => (d(c, [cy, cx]) < d(a, [cy, cx]) ? c : a))];
    const minimo = cand.map((c) => d(c, elegidos[0]));
    while (elegidos.length < Math.min(n, cand.length)) {
      let k = 0;
      for (let i = 1; i < cand.length; i++) if (minimo[i] > minimo[k]) k = i;
      elegidos.push(cand[k]);
      for (let i = 0; i < cand.length; i++) minimo[i] = Math.min(minimo[i], d(cand[i], cand[k]));
    }
    return elegidos;
  }

  /** Agrupa el GeoJSON por base: { icao: { nombre, centro, pistas: [...props], plataformas: [anillos] } }. */
  function indexar(geo) {
    const bases = {};
    for (const b of geo.bases || []) bases[b.icao] = { icao: b.icao, nombre: b.nombre, centro: [b.lat, b.lon], pistas: [], plataformas: [] };
    for (const f of geo.features || []) {
      const p = f.properties;
      if (p.tipo === "pista" && bases[p.base]) bases[p.base].pistas.push(p);
      if (p.tipo === "plataforma" && bases[p.base]) bases[p.base].plataformas.push(f.geometry.coordinates[0]);
    }
    for (const b of Object.values(bases)) {
      if (b.pistas.length) {
        // centro del aerodromo = punto medio de la pista mas larga (la posicion de la lista puede estar corrida)
        const larga = b.pistas.reduce((a, x) => (x.largo_m > a.largo_m ? x : a));
        b.centro = puntoEnPista(larga, larga.largo_m / 2);
      }
    }
    return bases;
  }

  /** Semilla estable de una base (por su id o su nombre). */
  const semillaDe = (u) => (u.id || 0) * 2654435761 + [...(u.nombre || "")].reduce((a, c) => a + c.charCodeAt(0), 0);

  // ---------------------------------------------------------------- dibujo (Leaflet)
  function crear({ map, capa, alCargar, ruta = "/static/geo/aerodromos/" } = {}) {
    let indice = [];
    const bases = {}; // icao -> { icao, nombre, centro, pistas, plataformas } (pistas vacias hasta cargar su plano)
    const cargados = new Set(), pedidos = new Set();
    const cachePuestos = new Map();
    let unidades = [];
    const render = L.canvas({ pane: "aerodromos", padding: 0.3 });
    const grupos = {
      plano: L.layerGroup(), detalle: L.layerGroup(), sombras: L.layerGroup(), edificios: L.layerGroup(),
      numeros: L.layerGroup(), estado: L.layerGroup(), rotulos: L.layerGroup(),
    };
    Object.values(grupos).forEach((g) => g.addTo(capa));
    const terrenos = [];
    const rodajes = []; // { linea, ancho_m, lat }: su grosor en pixeles se recalcula con el zoom

    function estilo(tipo) {
      return { ...(COLORES[tipo] || {}), renderer: render, interactive: false };
    }

    /** Sombra del edificio: su planta corrida hacia el sureste segun su altura (sol de la mañana). */
    function sombra(anillo, alto_m) {
      const d = alto_m * 0.7;
      const dLat = -d / 110574, dLon = d / (111320 * Math.cos(anillo[0][1] * R));
      return anillo.map(([lon, lat]) => [lat + dLat, lon + dLon]);
    }

    /** Dibuja el plano de un aerodromo recien descargado (se agrega a lo ya dibujado). */
    function construirAerodromo(geo) {
      Object.assign(bases, indexar(geo));
      for (const f of geo.features) {
        const p = f.properties;
        const g = f.geometry;
        if (p.tipo === "rodaje") {
          const ll = g.coordinates.map(([lon, lat]) => [lat, lon]);
          rodajes.push({ linea: L.polyline(ll, { ...estilo("rodaje"), weight: 1 }).addTo(grupos.plano), ancho_m: p.ancho_m || 18, lat: ll[0][0] });
          L.polyline(ll, { color: "#e3bf2a", weight: 1.3, opacity: 0.95, renderer: render, interactive: false }).addTo(grupos.detalle);
          continue;
        }
        if (g.type !== "Polygon") continue;
        const anillo = g.coordinates[0];
        const ll = anillo.map(([lon, lat]) => [lat, lon]);
        if (p.tipo === "edificio" || p.tipo === "hangar" || p.tipo === "torre") {
          L.polygon(sombra(anillo, p.alto_m || ALTO_POR_DEFECTO[p.tipo]), { stroke: false, fillColor: "#000", fillOpacity: 0.32, renderer: render, interactive: false }).addTo(grupos.sombras);
          L.polygon(ll, estilo(p.tipo)).addTo(grupos.edificios);
        } else {
          const poligono = L.polygon(ll, estilo(p.tipo)).addTo(grupos.plano);
          if (p.tipo === "aerodromo") terrenos.push(poligono);
          if (p.tipo === "pista") for (const m of marcasPista(p)) L.polygon(m, estilo("marca")).addTo(grupos.detalle);
        }
      }
      for (const b of geo.bases || []) {
        const base = bases[b.icao];
        if (!base) continue;
        for (const p of base.pistas) {
          for (const [txt, lat, lon, rumbo] of p.numeros || []) {
            L.marker([lat, lon], {
              pane: "aerodromos-rotulos", interactive: false, keyboard: false,
              icon: L.divIcon({ className: "numero-pista", html: `<span style="transform:rotate(${rumbo}deg)">${txt}</span>`, iconSize: [0, 0] }),
            }).addTo(grupos.numeros);
          }
        }
        if (!base.pistas.length) continue;
        const largo = Math.max(...base.pistas.map((x) => x.largo_m));
        L.marker(base.centro, {
          pane: "aerodromos-rotulos", interactive: false, keyboard: false,
          icon: L.divIcon({ className: "rotulo-aerodromo", html: `<b>${base.icao}</b> ${base.pistas.map((x) => x.ref).join(" · ")} · ${(largo / 1000).toFixed(1).replace(".", ",")} km`, iconSize: [0, 0] }),
        }).addTo(grupos.rotulos);
      }
    }

    /** Pide los planos de los aerodromos a la vista (y apenas fuera de ella) que aun no se descargaron. */
    function cargarVisibles() {
      if (!indice.length || !map.hasLayer(capa) || map.getZoom() < ZOOM_CARGA) return;
      const b = map.getBounds();
      const caja = { sur: b.getSouth(), oeste: b.getWest(), norte: b.getNorth(), este: b.getEast() };
      for (const a of aerodromosEnVista(indice, caja, MARGEN_CARGA_KM)) {
        if (pedidos.has(a.icao)) continue;
        pedidos.add(a.icao);
        fetch(ruta + encodeURIComponent(a.archivo || `${a.icao}.json`)).then((r) => (r.ok ? r.json() : null)).then((geo) => {
          if (!geo) return;
          cargados.add(a.icao);
          construirAerodromo(geo);
          actualizarEstado();
          ajustarZoom();
          if (alCargar) alCargar();
        }).catch(() => pedidos.delete(a.icao)); // sin conexion con el servidor: se reintenta al mover el mapa
      }
    }

    /** Crateres y cruces de pista cerrada segun la base del escenario que ocupa cada aerodromo. */
    function actualizarEstado() {
      grupos.estado.clearLayers();
      for (const b of Object.values(bases)) {
        if (!b.pistas.length) continue;
        const u = baseQueOcupa(b, unidades);
        if (!u) continue;
        const fuerza = u.estado === "destruida" ? 0 : u.fuerza;
        if (fuerza === null || fuerza === undefined) continue; // base enemiga sin informacion de daño
        // el estado de la pista manda: su daño propio (partes de la base) o, si no se conoce, la fuerza general
        const pista = u.dano_pista !== null && u.dano_pista !== undefined ? Math.max(0, 100 - u.dano_pista) : fuerza;
        const inoperativa = u.estado === "destruida" || fuerza < FUERZA_MINIMA_BASE || (u.dano_pista || 0) >= PISTA_INOPERATIVA;
        for (const c of crateres(b.pistas, Math.min(pista, u.estado === "destruida" ? 0 : 100), semillaDe(u))) {
          L.circle([c.lat, c.lon], { radius: c.radio_m * 1.9, stroke: false, fillColor: "#1d1712", fillOpacity: 0.35, renderer: render, interactive: false }).addTo(grupos.estado);
          L.circle([c.lat, c.lon], { radius: c.radio_m, color: "#9c7b52", weight: 1.5, fillColor: "#3a2a1c", fillOpacity: 1, renderer: render, interactive: false }).addTo(grupos.estado);
        }
        if (inoperativa) {
          for (const p of b.pistas) {
            for (const s of [p.largo_m * 0.08, p.largo_m * 0.5, p.largo_m * 0.92]) {
              const brazo = Math.min(60, p.ancho_m * 1.1);
              for (const [a, c] of [[[-brazo, -brazo], [brazo, brazo]], [[-brazo, brazo], [brazo, -brazo]]]) {
                L.polyline([puntoEnPista(p, s + a[0], a[1]), puntoEnPista(p, s + c[0], c[1])], { color: "#ffd21f", weight: 5, opacity: 0.95, lineCap: "butt", renderer: render, interactive: false }).addTo(grupos.estado);
              }
            }
          }
          L.marker(b.centro, {
            pane: "aerodromos-rotulos", interactive: false, keyboard: false,
            icon: L.divIcon({ className: "rotulo-aerodromo cerrada", html: "PISTA INOPERATIVA", iconSize: [0, 0] }),
          }).addTo(grupos.estado);
        }
      }
    }

    function ajustarZoom() {
      const z = map.getZoom();
      const poner = (g, on) => (on ? capa.hasLayer(g) || g.addTo(capa) : capa.removeLayer(g));
      poner(grupos.plano, z >= ZOOM_PLANO);
      poner(grupos.sombras, z >= 13);
      poner(grupos.edificios, z >= 12);
      poner(grupos.detalle, z >= ZOOM_DETALLE);
      poner(grupos.numeros, z >= ZOOM_DETALLE);
      poner(grupos.estado, z >= ZOOM_PLANO);
      poner(grupos.rotulos, z >= ZOOM_PLANO && z < 14);
      // las calles de rodaje tienen su ancho real: el grosor de la linea sigue a la escala del mapa
      if (z >= ZOOM_PLANO) for (const r of rodajes) r.linea.setStyle({ weight: Math.max(0.8, metrosAPixeles(r.ancho_m, r.lat, z)) });
      // de cerca el satelite (10 m/pixel) se ve borroso: el terreno del aerodromo lo tapa casi del todo
      const opacidad = z >= 15 ? 0.88 : z >= 13 ? 0.72 : 0.55;
      for (const t of terrenos) t.setStyle({ fillOpacity: opacidad });
      const cont = map.getContainer();
      cont.style.setProperty("--tam-numero-pista", `${tamNumero(z)}px`);
      // con el plano a la vista, la capa de referencia de bases se atenua (no tapa la pista ni duplica el rotulo)
      cont.classList.toggle("plano-aerodromos", z >= ZOOM_PLANO && map.hasLayer(capa));
    }

    map.on("zoomend", ajustarZoom);
    map.on("moveend", cargarVisibles);
    capa.on("add remove", () => setTimeout(() => { ajustarZoom(); cargarVisibles(); }, 0));
    fetch(ruta + "indice.json").then((r) => (r.ok ? r.json() : null)).then((ind) => {
      if (!ind) return;
      indice = ind.bases || [];
      for (const b of indice) bases[b.icao] = bases[b.icao] || { icao: b.icao, nombre: b.nombre, centro: [b.lat, b.lon], pistas: [], plataformas: [] };
      cargarVisibles();
    }).catch(() => {});

    return {
      /** Actualiza el estado (daños) con las unidades del escenario. */
      actualizar(lista) { unidades = lista || []; actualizarEstado(); },
      /** Si hay plano detallado (ya descargado) bajo esa unidad base_aerea, para dibujarla en pequeño al acercarse. */
      cubre(u) { return !!u && u.clase === "base_aerea" && Object.values(bases).some((b) => b.pistas.length && baseQueOcupa(b, [u])); },
      /**
       * Posicion para dibujar una aeronave estacionada sobre la plataforma real de su base ([lat, lon]) o null.
       * Solo cambia donde se dibuja (el motor no usa posiciones dentro de la base).
       */
      posicionEstacionada(u, lista) {
        if (!u || !u.en_tierra || !u.base_id) return null;
        const base = (lista || []).find((x) => x.id === u.base_id);
        const b = base && Object.values(bases).find((x) => x.pistas.length && x.plataformas.length && baseQueOcupa(x, [base]));
        if (!b) return null;
        const hermanos = lista.filter((x) => x.en_tierra && x.base_id === u.base_id && x.estado !== "destruida").sort((x, y) => x.id - y.id);
        const k = hermanos.findIndex((x) => x.id === u.id);
        const clave = b.icao + "|" + hermanos.length;
        if (!cachePuestos.has(clave)) cachePuestos.set(clave, puestos(b.plataformas, hermanos.length));
        return cachePuestos.get(clave)[k] || null;
      },
      /** Zoom desde el que el plano se ve con detalle. */
      zoomDetalle: ZOOM_PLANO,
      bases: () => bases,
      /** Aerodromos cuyo plano ya se descargo. */
      cargados: () => [...cargados],
    };
  }

  const api = {
    crear, crateres, cantidadCrateres, puntoEnPista, tamNumero, baseQueOcupa, indexar, puestos, distanciaKm, marcasPista,
    metrosAPixeles, aerodromosEnVista, ZOOM_PLANO, ZOOM_DETALLE, ZOOM_CARGA,
  };
  raiz.Aerodromos = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
