/* Zonas meteorológicas en el mapa del Cóndor (backend/app/engine/clima.py), en dos vistas a elección de cada puesto:
 * - "radio": el círculo de la zona con su rótulo y la flecha de deriva (como hasta ahora);
 * - "satelite": la nubosidad como se ve en una imagen de satélite meteorológico (nubes blancas de bordes irregulares,
 *   más densas y brillantes en el núcleo de una tormenta).
 * Entre un estado y el siguiente la zona sigue moviéndose en pantalla con su deriva, sin saltos. */
(function (raiz) {
  "use strict";

  const COLOR = { nublado: "#9aa5b1", lluvia: "#3b7dd8", tormenta: "#7b2cbf" };
  // capas de nube de la vista satelite: [fraccion del radio, color, opacidad, con textura (huecos entre nubes)]
  const CAPAS_NUBE = {
    nublado: [[1.0, "#c5cbd2", 0.42, true], [0.62, "#e1e5e9", 0.42, true]],
    lluvia: [[1.0, "#cbd0d7", 0.55, true], [0.72, "#e6e9ec", 0.62, true], [0.4, "#f4f5f7", 0.6, false]],
    tormenta: [[1.06, "#d0d5dc", 0.6, true], [0.78, "#edf0f3", 0.78, true], [0.48, "#ffffff", 0.92, false], [0.2, "#ffffff", 0.97, false]],
  };
  const NS = "http://www.w3.org/2000/svg";

  /** Punto a `km` de (lat, lon) con rumbo `rumbo` (igual que clima.desplazar en el servidor). */
  function desplazar(lat, lon, rumbo, km) {
    const r = (rumbo * Math.PI) / 180;
    return [lat + (km * Math.cos(r)) / 110.574, lon + (km * Math.sin(r)) / (111.32 * Math.max(0.2, Math.cos((lat * Math.PI) / 180)))];
  }

  /** Donde esta la zona ahora: la del estado mas lo que derivo desde entonces (segundos simulados). */
  function posicion(z, segAhora, segEstado) {
    const horas = Math.max(0, (segAhora || 0) - (segEstado || 0)) / 3600;
    return z.deriva_kmh > 0 && horas > 0 ? desplazar(z.lat, z.lon, z.deriva_rumbo, z.deriva_kmh * horas) : [z.lat, z.lon];
  }

  /** Parametros del filtro de nubes segun el tamaño de la zona en pantalla (pixeles del radio). */
  function filtroPara(radioPx) {
    const lim = (v, a, b) => Math.max(a, Math.min(b, v));
    return { desplazamiento: lim(radioPx * 0.3, 2, 70), desenfoque: lim(radioPx * 0.035, 0.6, 9), frecuencia: lim(2.6 / Math.max(1, radioPx), 0.003, 0.09) };
  }

  /** ctx: { L, mapa, capa (layerGroup), etiqueta(tipo), texto(z), escapar } */
  function crear(ctx) {
    const L = ctx.L;
    let vista = "radio";
    let zonas = [];
    let segEstado = 0;
    let dibujadas = [];  // [{ z, circulos: [{capa, frac}], rotulo, flecha, punta, filtros }]
    const renderer = L.svg({ padding: 0.6 });
    let defs = null;

    function asegurarDefs() {
      if (defs) return defs;
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("width", "0");
      svg.setAttribute("height", "0");
      svg.setAttribute("aria-hidden", "true");
      svg.style.position = "absolute";
      defs = document.createElementNS(NS, "defs");
      svg.appendChild(defs);
      document.body.appendChild(svg);
      return defs;
    }

    function crearFiltro(id, semilla, textura) {
      const f = document.createElementNS(NS, "filter");
      f.setAttribute("id", id);
      for (const [k, v] of [["x", "-35%"], ["y", "-35%"], ["width", "170%"], ["height", "170%"], ["color-interpolation-filters", "sRGB"]]) f.setAttribute(k, v);
      const el = (tag, attrs) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); f.appendChild(n); return n; };
      const ruido = el("feTurbulence", { type: "fractalNoise", numOctaves: "4", seed: String(semilla), result: "ruido" });
      const disp = el("feDisplacementMap", { in: "SourceGraphic", in2: "ruido", xChannelSelector: "R", yChannelSelector: "G", result: "borde" });
      const blur = el("feGaussianBlur", { in: "borde", result: "suave" });
      if (textura) {  // huecos entre las nubes: el ruido decide donde hay nube
        el("feColorMatrix", { in: "ruido", type: "matrix", values: "0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 2.2 -0.55", result: "textura" });
        el("feComposite", { in: "suave", in2: "textura", operator: "in" });
      }
      asegurarDefs().appendChild(f);
      return { f, ruido, disp, blur };
    }

    function ajustarFiltros() {
      const zoom = ctx.mapa.getZoom();
      for (const d of dibujadas) {
        if (!d.filtros.length) continue;
        const lat = d.z.lat;
        const mPorPx = (40075016.686 * Math.cos((lat * Math.PI) / 180)) / 2 ** (zoom + 8);
        const p = filtroPara((d.z.radio_km * 1000) / mPorPx);
        for (const fl of d.filtros) {
          fl.ruido.setAttribute("baseFrequency", String(p.frecuencia));
          fl.disp.setAttribute("scale", String(p.desplazamiento));
          fl.blur.setAttribute("stdDeviation", String(p.desenfoque));
        }
      }
    }

    function limpiar() {
      ctx.capa.clearLayers();
      for (const d of dibujadas) for (const fl of d.filtros) fl.f.remove();
      dibujadas = [];
    }

    function dibujarRadio(z, centro) {
      const color = COLOR[z.tipo] || "#9aa5b1";
      const circ = L.circle(centro, { radius: z.radio_km * 1000, color, weight: 2, dashArray: "6 6", fillColor: color, fillOpacity: z.tipo === "tormenta" ? 0.28 : 0.18, interactive: true })
        .bindTooltip(ctx.texto(z), { sticky: true }).addTo(ctx.capa);
      const d = { z, circulos: [{ capa: circ, frac: 1 }], filtros: [], flecha: null, punta: null, rotulo: null };
      if (z.deriva_kmh > 0) {  // flecha de deriva: hacia donde se mueve en las proximas 3 horas
        const fin = desplazar(centro[0], centro[1], z.deriva_rumbo, z.deriva_kmh * 3);
        d.flecha = L.polyline([centro, fin], { color: "#fff", weight: 2, opacity: 0.9, interactive: false }).addTo(ctx.capa);
        d.punta = L.circleMarker(fin, { radius: 3, color: "#fff", fillColor: color, fillOpacity: 1, interactive: false }).addTo(ctx.capa);
      }
      d.rotulo = L.marker(centro, {
        icon: L.divIcon({ className: "zona-clima-rotulo", iconSize: [90, 18], iconAnchor: [45, 9], html: `<span style="border-color:${color}">${ctx.escapar(ctx.etiqueta(z.tipo))}${z.nombre ? " " + ctx.escapar(z.nombre) : ""}</span>` }),
        keyboard: false, interactive: false,
      }).addTo(ctx.capa);
      return d;
    }

    function dibujarSatelite(z, centro) {
      const d = { z, circulos: [], filtros: [], flecha: null, punta: null, rotulo: null };
      (CAPAS_NUBE[z.tipo] || CAPAS_NUBE.nublado).forEach(([frac, color, opacidad, textura], i) => {
        const id = `nube-${z.id}-${i}`;
        d.filtros.push(crearFiltro(id, (z.id * 7 + i * 13) % 97 + 1, textura));
        const c = L.circle(centro, { renderer, radius: z.radio_km * 1000 * frac, stroke: false, fillColor: color, fillOpacity: opacidad, interactive: false, className: "nube-satelite" }).addTo(ctx.capa);
        const el = c.getElement && c.getElement();
        if (el) el.setAttribute("filter", `url(#${id})`);
        d.circulos.push({ capa: c, frac });
      });
      // el radio real de la zona, invisible, para el cartel al pasar el cursor
      const toque = L.circle(centro, { radius: z.radio_km * 1000, stroke: false, fillColor: "#fff", fillOpacity: 0, interactive: true })
        .bindTooltip(ctx.texto(z), { sticky: true }).addTo(ctx.capa);
      d.circulos.push({ capa: toque, frac: 1 });
      return d;
    }

    function dibujar(lista, seg, segAhora) {
      zonas = lista || [];
      segEstado = seg || 0;
      limpiar();
      for (const z of zonas) {
        const centro = posicion(z, segAhora, segEstado);
        dibujadas.push(vista === "satelite" ? dibujarSatelite(z, centro) : dibujarRadio(z, centro));
      }
      if (vista === "satelite") ajustarFiltros();
    }

    /** Lleva cada zona a donde esta ahora (se llama varias veces por segundo con el reloj en marcha). */
    function mover(segAhora) {
      for (const d of dibujadas) {
        if (!(d.z.deriva_kmh > 0)) continue;
        const c = posicion(d.z, segAhora, segEstado);
        for (const { capa } of d.circulos) capa.setLatLng(c);
        if (d.rotulo) d.rotulo.setLatLng(c);
        if (d.flecha) {
          const fin = desplazar(c[0], c[1], d.z.deriva_rumbo, d.z.deriva_kmh * 3);
          d.flecha.setLatLngs([c, fin]);
          d.punta.setLatLng(fin);
        }
      }
    }

    ctx.mapa.on("zoomend", () => { if (vista === "satelite") ajustarFiltros(); });

    return {
      dibujar, mover,
      fijarVista(v, segAhora) { vista = v === "satelite" ? "satelite" : "radio"; dibujar(zonas, segEstado, segAhora); },
      vista: () => vista,
      // posicion actual de las zonas (para el clima local de una unidad)
      zonasAhora: (segAhora) => zonas.map((z) => { const [lat, lon] = posicion(z, segAhora, segEstado); return { ...z, lat, lon }; }),
    };
  }

  const api = { crear, posicion, desplazar, filtroPara, COLOR, CAPAS_NUBE };
  if (typeof module !== "undefined") module.exports = api;
  raiz.ClimaMapa = api;
})(typeof window !== "undefined" ? window : globalThis);
