/* Linea de tiempo del informe posterior: cruza la logistica (caidas abruptas de combustible y municion)
 * con los combates. `layout` es pura (se prueba con Node); `crear` dibuja el SVG interactivo. */
(function (raiz) {
  "use strict";

  const COLORES = { azul: "#3A86FF", rojo: "#EF233C", combustible: "#2EC4B6", municion: "#FFB703", combate: "#FF4D4D" };

  /**
   * Calcula la disposicion del diagrama. `datos` es la respuesta de /aar/timeline; `op` admite
   * { ancho, margenIzq, margenDer, margenSup, altoCarril, bando: "todos"|"azul"|"rojo",
   *   mostrar: { combates, logistica, eventos } }.
   */
  function layout(datos, op = {}) {
    const o = {
      ancho: 940, margenIzq: 170, margenDer: 24, margenSup: 46, altoCarril: 28, bando: "todos",
      ...op, mostrar: { combates: true, logistica: true, eventos: true, ...(op.mostrar || {}) },
    };
    const turnos = datos.ejes.turnos;
    if (!turnos.length) return { vacio: true, ancho: o.ancho, alto: 0, ticks: [], carriles: [], marcas: [], enlaces: [] };

    const t0 = turnos[0];
    const t1 = turnos[turnos.length - 1];
    const util = o.ancho - o.margenIzq - o.margenDer;
    const x = (t) => o.margenIzq + ((t - t0) / Math.max(1, t1 - t0)) * util;

    const orden = { azul: 0, rojo: 1 };
    const series = datos.series
      .filter((s) => o.bando === "todos" || s.bando === o.bando)
      .sort((a, b) => (orden[a.bando] ?? 2) - (orden[b.bando] ?? 2) || a.nombre.localeCompare(b.nombre));

    const carril = new Map();
    const carriles = series.map((s, i) => {
      const y = o.margenSup + i * o.altoCarril;
      const alto = o.altoCarril - 8;
      const linea = (variable) => s.turnos.map((t, k) => [x(t), y + o.altoCarril - 4 - (s[variable][k] / 100) * alto]);
      const c = {
        unidad_id: s.unidad_id, nombre: s.nombre, bando: s.bando, clase: s.clase, y, yCentro: y + o.altoCarril / 2,
        combustible: linea("combustible"), municion: linea("municion"),
        destruida: s.estado.includes("destruida") ? x(s.turnos[s.estado.indexOf("destruida")]) : null,
      };
      carril.set(s.unidad_id, c);
      return c;
    });

    const marcas = [];
    const claves = new Map();
    const anadir = (m) => { marcas.push(m); claves.set(m.clave, m); };

    if (o.mostrar.combates) {
      for (const e of datos.eventos.filter((v) => v.tipo === "combate")) {
        for (const [uid, papel] of [[e.atacante_id, "atacante"], [e.defensor_id, "defensor"]]) {
          const c = carril.get(uid);
          if (c) anadir({ clave: `${e.id}@${uid}`, id: e.id, tipo: "combate", subtipo: papel, x: x(e.turno), y: c.yCentro, turno: e.turno, unidad_id: uid, datos: e });
        }
      }
    }
    if (o.mostrar.logistica) {
      const desplazamiento = { municion: -5, combustible: 5 };
      for (const e of datos.eventos.filter((v) => v.tipo === "logistico")) {
        const c = carril.get(e.unidad_id);
        if (c) anadir({ clave: `${e.id}@${e.unidad_id}`, id: e.id, tipo: "logistico", subtipo: e.subtipo, variable: e.variable, x: x(e.turno) + (desplazamiento[e.variable] || 0), y: c.yCentro, turno: e.turno, unidad_id: e.unidad_id, datos: e });
      }
    }
    if (o.mostrar.eventos) {
      const apilados = new Map();
      for (const e of datos.eventos.filter((v) => v.tipo === "evento")) {
        if (o.bando !== "todos" && e.bando_destino !== "todos" && e.bando_destino !== o.bando) continue;
        const n = apilados.get(e.turno) || 0;
        apilados.set(e.turno, n + 1);
        anadir({ clave: `${e.id}@eje`, id: e.id, tipo: "evento", subtipo: e.subtipo, x: x(e.turno) + n * 9, y: o.margenSup - 16, turno: e.turno, unidad_id: null, datos: e });
      }
    }

    // enlaces: gasto logistico -> combate, o "llego al combate con la logistica baja"
    const enlaces = [];
    for (const c of datos.correlaciones) {
      const combate = claves.get(`${c.combate}@${c.unidad_id}`);
      if (!combate) continue;
      const origen = c.logistico ? claves.get(`${c.logistico}@${c.unidad_id}`) : null;
      if (c.logistico && !origen) continue;
      const desde = origen ? { x: origen.x, y: origen.y } : { x: x(Math.max(t0, c.turno - 1)), y: combate.y };
      const arriba = Math.min(20, Math.abs(combate.x - desde.x) / 2 + 8);
      enlaces.push({
        tipo: c.tipo, detalle: c.detalle, turno: c.turno, unidad_id: c.unidad_id, de: origen ? origen.clave : null, a: combate.clave,
        ruta: `M${desde.x.toFixed(1)} ${desde.y.toFixed(1)} Q${((desde.x + combate.x) / 2).toFixed(1)} ${(desde.y - arriba).toFixed(1)} ${combate.x.toFixed(1)} ${combate.y.toFixed(1)}`,
      });
    }

    return {
      vacio: false, ancho: o.ancho, alto: o.margenSup + carriles.length * o.altoCarril + 18, margenIzq: o.margenIzq,
      ticks: turnos.map((t) => ({ turno: t, x: x(t) })), carriles, marcas, enlaces, t0, t1,
    };
  }

  const api = { layout, COLORES };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }

  // ------------------------------------------------------------------ dibujo (solo navegador)
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs = {}, texto) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (texto !== undefined) e.textContent = texto;
    return e;
  };
  const limpiar = (n) => { while (n.firstChild) n.removeChild(n.firstChild); };

  const ETIQUETA_SUBTIPO = {
    caida_abrupta: "Caída abrupta", nivel_critico: "Nivel crítico", reabastecimiento: "Reabastecimiento",
    ajuste_manual: "Ajuste manual", ataque: "Combate", clima: "Clima", perdida: "Pérdida logística", ajuste: "Ajuste", general: "Aviso",
  };

  function descripcion(m) {
    const d = m.datos;
    if (m.tipo === "combate") {
      return `Turno ${d.turno} · ${d.atacante} → ${d.defensor}\nRatio ${d.ratio}, bajas ${d.perdida_atacante}/${d.perdida_defensor} · ${d.terreno}` + (d.efectos.length ? `\n${d.efectos.join("; ")}` : "");
    }
    if (m.tipo === "logistico") {
      return `Turno ${d.turno} · ${ETIQUETA_SUBTIPO[d.subtipo] || d.subtipo}: ${d.unidad}\n${d.variable} ${d.antes}% → ${d.despues}% (${d.delta > 0 ? "+" : ""}${d.delta})\nCausa: ${d.causas.join(", ")}`;
    }
    return `Turno ${d.turno} · ${ETIQUETA_SUBTIPO[d.subtipo] || d.subtipo}\n${d.texto}`;
  }

  /** ctx: { api, escenarioId, toast, alElegir(marca) } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    let datos = null;
    let estado = { bando: "todos", mostrar: { combates: true, logistica: true, eventos: true } };

    function tarjetaDeResumen() {
      const r = datos.resumen;
      $("tl-resumen").textContent = `${r.combates} combates · ${r.caidas_abruptas} caídas abruptas · ${r.niveles_criticos} niveles críticos · ${r.reabastecimientos} reabastecimientos · ${r.correlaciones} correlaciones logística-combate`;
    }

    function dibujar() {
      const L = layout(datos, { ...estado, ancho: Math.max(720, Math.min(1200, $("tl-svg-wrap").clientWidth - 8 || 940)) });
      const svg = $("tl-svg");
      limpiar(svg);
      if (L.vacio) { svg.setAttribute("height", 60); svg.appendChild(el("text", { x: 12, y: 32, fill: "#8D99AE" }, "Aún no se cumplió ninguna hora del ejercicio.")); return; }
      svg.setAttribute("viewBox", `0 0 ${L.ancho} ${L.alto}`);
      svg.setAttribute("width", L.ancho);
      svg.setAttribute("height", L.alto);

      L.carriles.forEach((c, i) => {
        if (i % 2 === 0) svg.appendChild(el("rect", { x: 0, y: c.y, width: L.ancho, height: 28, fill: "rgba(255,255,255,.035)" }));
        const t = el("text", { x: 8, y: c.yCentro + 4, fill: COLORES[c.bando], "font-size": 11, "font-weight": 700 }, c.nombre.length > 20 ? c.nombre.slice(0, 19) + "…" : c.nombre);
        t.appendChild(el("title", {}, `${c.nombre} (${c.clase})`));
        svg.appendChild(t);
      });
      for (const t of L.ticks) {
        svg.appendChild(el("line", { x1: t.x, x2: t.x, y1: 30, y2: L.alto - 14, stroke: "rgba(141,153,174,.25)", "stroke-dasharray": "3 4" }));
        svg.appendChild(el("text", { x: t.x, y: L.alto - 3, fill: "#8D99AE", "font-size": 10, "text-anchor": "middle" }, t.turno === 0 ? "Inicio" : `T${t.turno}`));
      }
      const polilinea = (pts, color) => pts.length > 1 && el("polyline", { points: pts.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" "), fill: "none", stroke: color, "stroke-width": 1.6, opacity: 0.85 });
      for (const c of L.carriles) {
        for (const [pts, color] of [[c.combustible, COLORES.combustible], [c.municion, COLORES.municion]]) {
          const p = polilinea(pts, color);
          if (p) svg.appendChild(p);
        }
        if (c.destruida !== null) svg.appendChild(el("text", { x: c.destruida + 6, y: c.yCentro + 4, fill: "#ff6b7d", "font-size": 11, "font-weight": 800 }, "✕"));
      }

      const grupoEnlaces = el("g", { "pointer-events": "none" });
      const rutas = new Map();
      for (const e of L.enlaces) {
        const p = el("path", { d: e.ruta, fill: "none", stroke: "#ff8fab", "stroke-width": 1.6, "stroke-dasharray": e.tipo === "combate_con_logistica_baja" ? "2 4" : "5 3", opacity: 0.55 });
        grupoEnlaces.appendChild(p);
        rutas.set(e, p);
      }
      svg.appendChild(grupoEnlaces);

      const tip = $("tl-tip");
      for (const m of L.marcas) {
        const g = el("g", { transform: `translate(${m.x.toFixed(1)},${m.y.toFixed(1)})`, tabindex: 0, role: "button", style: "cursor:pointer" });
        let forma;
        if (m.tipo === "combate") forma = el("path", { d: "M0 -7 7 0 0 7 -7 0Z", fill: COLORES.combate, stroke: "#fff", "stroke-width": m.subtipo === "atacante" ? 1.5 : 0.6 });
        else if (m.tipo === "evento") forma = el("circle", { r: 4, fill: m.subtipo === "clima" ? "#6db8ff" : m.subtipo === "perdida" ? "#ff6b7d" : "#8D99AE", stroke: "#fff", "stroke-width": 0.8 });
        else if (m.subtipo === "reabastecimiento") forma = el("path", { d: "M0 -6 6 5 -6 5Z", fill: "#2EC4B6", stroke: "#fff", "stroke-width": 0.8 });
        else if (m.subtipo === "nivel_critico") forma = el("circle", { r: 5, fill: "#EF233C", stroke: "#fff", "stroke-width": 1.2 });
        else if (m.subtipo === "ajuste_manual") forma = el("rect", { x: -4, y: -4, width: 8, height: 8, fill: "#8D99AE", stroke: "#fff", "stroke-width": 0.8 });
        else forma = el("path", { d: "M-6 -5 6 -5 0 6Z", fill: m.variable === "municion" ? COLORES.municion : COLORES.combustible, stroke: "#fff", "stroke-width": 1.2 });
        g.appendChild(forma);
        g.appendChild(el("title", {}, descripcion(m)));
        const relacionados = L.enlaces.filter((e) => e.de === m.clave || e.a === m.clave);
        const resaltar = (on) => relacionados.forEach((e) => rutas.get(e).setAttribute("opacity", on ? 1 : 0.55));
        g.addEventListener("mouseenter", (ev) => {
          resaltar(true);
          tip.textContent = descripcion(m) + (relacionados.length ? "\n\n" + relacionados.map((e) => `↔ ${e.detalle}`).join("\n") : "");
          tip.hidden = false;
          const caja = $("tl-svg-wrap").getBoundingClientRect();
          tip.style.left = `${Math.min(ev.clientX - caja.left + 12, caja.width - 260)}px`;
          tip.style.top = `${ev.clientY - caja.top + 14}px`;
        });
        g.addEventListener("mouseleave", () => { resaltar(false); tip.hidden = true; });
        g.addEventListener("click", () => ctx.alElegir(m));
        g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); ctx.alElegir(m); } });
        svg.appendChild(g);
      }
      lista(L);
    }

    function lista(L) {
      const ul = $("tl-lista");
      limpiar(ul);
      const ordenadas = [...new Map(L.marcas.map((m) => [m.id, m])).values()].sort((a, b) => a.turno - b.turno);
      for (const m of ordenadas) {
        const li = document.createElement("li");
        li.tabIndex = 0;
        li.textContent = descripcion(m).replace(/\n/g, " · ");
        li.className = m.tipo + (m.subtipo ? " " + m.subtipo : "");
        li.addEventListener("click", () => ctx.alElegir(m));
        ul.appendChild(li);
      }
      if (!ordenadas.length) { const li = document.createElement("li"); li.textContent = "Sin eventos para estos filtros."; ul.appendChild(li); }
    }

    async function abrir() {
      try {
        datos = await ctx.api("GET", `/api/escenarios/${ctx.escenarioId()}/aar/timeline`);
      } catch (_) { return; }
      $("dlg-timeline").showModal();
      tarjetaDeResumen();
      dibujar();
    }

    document.querySelectorAll("[data-tl-filtro]").forEach((chk) => chk.addEventListener("change", () => {
      estado.mostrar[chk.dataset.tlFiltro] = chk.checked;
      if (datos) dibujar();
    }));
    $("tl-bando").addEventListener("change", () => { estado.bando = $("tl-bando").value; if (datos) dibujar(); });
    window.addEventListener("resize", () => { if ($("dlg-timeline").open && datos) dibujar(); });

    return { abrir };
  }

  raiz.Timeline = { layout, crear, COLORES };
})(typeof window !== "undefined" ? window : globalThis);
