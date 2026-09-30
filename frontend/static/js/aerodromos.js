/* Plano detallado de las bases aereas: pistas, calles de rodaje, plataformas, hangares y edificios reales
 * (OpenStreetMap, ver tools/preparar_aerodromos.py y geo/aerodromos.geojson), con las marcas de pista y la
 * numeracion de cada cabecera. Aparece al acercarse (zoom 11 en adelante) en su propio panel, debajo de las
 * unidades, y muestra el estado de la base del escenario que la ocupa: crateres en la pista segun el daño y las
 * cruces de pista cerrada cuando ya no puede operar.
 *
 * La logica (crateres, escalas, busqueda de la base) es pura y se prueba con Node; el dibujo usa Leaflet. */
(function (raiz) {
  "use strict";

  const ZOOM_PLANO = 11; // desde aca se ve el contorno del aerodromo, las pistas y las plataformas
  const ZOOM_DETALLE = 14; // marcas de pista, eje de rodaje y numeracion
  const RADIO_BASE_KM = 4; // una unidad base_aerea a esta distancia de la pista "ocupa" el aerodromo
  const FUERZA_MINIMA_BASE = 25; // igual que el motor: por debajo la base no opera

  const COLORES = {
    aerodromo: { color: "#d8c690", weight: 1, dashArray: "5 4", fillColor: "#6c7a50", fillOpacity: 0.55 },
    plataforma: { color: "#7a7e80", weight: 1, fillColor: "#a3a6a7", fillOpacity: 1 },
    rodaje: { stroke: false, fillColor: "#6a6e72", fillOpacity: 1 },
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
  function crear({ map, capa, alCargar } = {}) {
    let geo = null, bases = {};
    const cachePuestos = new Map();
    let unidades = [];
    const render = L.canvas({ pane: "aerodromos", padding: 0.3 });
    const grupos = {
      plano: L.layerGroup(), detalle: L.layerGroup(), sombras: L.layerGroup(), edificios: L.layerGroup(),
      numeros: L.layerGroup(), estado: L.layerGroup(), rotulos: L.layerGroup(),
    };
    Object.values(grupos).forEach((g) => g.addTo(capa));

    function estilo(tipo) {
      return { ...(COLORES[tipo] || {}), renderer: render, interactive: false };
    }

    /** Sombra del edificio: su planta corrida hacia el sureste segun su altura (sol de la mañana). */
    function sombra(anillo, alto_m) {
      const d = alto_m * 0.7;
      const dLat = -d / 110574, dLon = d / (111320 * Math.cos(anillo[0][1] * R));
      return anillo.map(([lon, lat]) => [lat + dLat, lon + dLon]);
    }

    let terrenos = [];
    function construir() {
      Object.values(grupos).forEach((g) => g.clearLayers());
      terrenos = [];
      for (const f of geo.features) {
        const p = f.properties;
        const g = f.geometry;
        if (g.type === "LineString") {
          L.polyline(g.coordinates.map(([lon, lat]) => [lat, lon]), { color: "#e3bf2a", weight: 1.3, opacity: 0.95, renderer: render, interactive: false }).addTo(grupos.detalle);
          continue;
        }
        const anillo = g.coordinates[0];
        const ll = anillo.map(([lon, lat]) => [lat, lon]);
        if (p.tipo === "marca") L.polygon(ll, estilo("marca")).addTo(grupos.detalle);
        else if (p.tipo === "edificio" || p.tipo === "hangar" || p.tipo === "torre") {
          L.polygon(sombra(anillo, p.alto_m || ALTO_POR_DEFECTO[p.tipo]), { stroke: false, fillColor: "#000", fillOpacity: 0.32, renderer: render, interactive: false }).addTo(grupos.sombras);
          L.polygon(ll, estilo(p.tipo)).addTo(grupos.edificios);
        } else {
          const poligono = L.polygon(ll, estilo(p.tipo)).addTo(grupos.plano);
          if (p.tipo === "aerodromo") terrenos.push(poligono);
        }
      }
      for (const b of Object.values(bases)) {
        for (const p of b.pistas) {
          for (const [txt, lat, lon, rumbo] of p.numeros || []) {
            L.marker([lat, lon], {
              pane: "aerodromos-rotulos", interactive: false, keyboard: false,
              icon: L.divIcon({ className: "numero-pista", html: `<span style="transform:rotate(${rumbo}deg)">${txt}</span>`, iconSize: [0, 0] }),
            }).addTo(grupos.numeros);
          }
        }
        if (!b.pistas.length) continue;
        const largo = Math.max(...b.pistas.map((x) => x.largo_m));
        L.marker(b.centro, {
          pane: "aerodromos-rotulos", interactive: false, keyboard: false,
          icon: L.divIcon({ className: "rotulo-aerodromo", html: `<b>${b.icao}</b> ${b.pistas.map((x) => x.ref).join(" · ")} · ${(largo / 1000).toFixed(1).replace(".", ",")} km`, iconSize: [0, 0] }),
        }).addTo(grupos.rotulos);
      }
      actualizarEstado();
      ajustarZoom();
    }

    /** Crateres y cruces de pista cerrada segun la base del escenario que ocupa cada aerodromo. */
    function actualizarEstado() {
      grupos.estado.clearLayers();
      if (!geo) return;
      for (const b of Object.values(bases)) {
        const u = baseQueOcupa(b, unidades);
        if (!u || !b.pistas.length) continue;
        const fuerza = u.estado === "destruida" ? 0 : u.fuerza;
        if (fuerza === null || fuerza === undefined) continue; // base enemiga sin informacion de daño
        for (const c of crateres(b.pistas, fuerza, semillaDe(u))) {
          L.circle([c.lat, c.lon], { radius: c.radio_m * 1.9, stroke: false, fillColor: "#1d1712", fillOpacity: 0.35, renderer: render, interactive: false }).addTo(grupos.estado);
          L.circle([c.lat, c.lon], { radius: c.radio_m, color: "#9c7b52", weight: 1.5, fillColor: "#3a2a1c", fillOpacity: 1, renderer: render, interactive: false }).addTo(grupos.estado);
        }
        if (fuerza < FUERZA_MINIMA_BASE) {
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
      // de cerca el satelite (10 m/pixel) se ve borroso: el terreno del aerodromo lo tapa casi del todo
      const opacidad = z >= 15 ? 0.88 : z >= 13 ? 0.72 : 0.55;
      for (const t of terrenos) t.setStyle({ fillOpacity: opacidad });
      const cont = map.getContainer();
      cont.style.setProperty("--tam-numero-pista", `${tamNumero(z)}px`);
      // con el plano a la vista, la capa de referencia de bases se atenua (no tapa la pista ni duplica el rotulo)
      cont.classList.toggle("plano-aerodromos", z >= ZOOM_PLANO && map.hasLayer(capa));
    }

    map.on("zoomend", ajustarZoom);
    capa.on("add remove", () => setTimeout(ajustarZoom, 0));
    fetch("/static/geo/aerodromos.geojson").then((r) => (r.ok ? r.json() : null)).then((g) => {
      if (!g) return;
      geo = g;
      bases = indexar(g);
      construir();
      if (alCargar) alCargar();
    }).catch(() => {});

    return {
      /** Actualiza el estado (daños) con las unidades del escenario. */
      actualizar(lista) { unidades = lista || []; actualizarEstado(); },
      /** Si hay plano detallado bajo esa unidad base_aerea (para dibujarla en pequeño al acercarse). */
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
    };
  }

  const api = { crear, crateres, cantidadCrateres, puntoEnPista, tamNumero, baseQueOcupa, indexar, puestos, distanciaKm, ZOOM_PLANO, ZOOM_DETALLE };
  raiz.Aerodromos = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
