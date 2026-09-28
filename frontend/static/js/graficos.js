/* Graficos tacticos (lineas de fase, ejes de avance, zonas de reunion, puntos de control) con Leaflet.draw.
 * Se guardan como GeoJSON en el servidor y se sincronizan por WebSocket con todo el bando. */
(function (raiz) {
  "use strict";
  const { TIPOS_GRAFICO, latLngsDe, puedeBorrarGrafico } = Logica;

  const COLOR_BANDO = { azul: "#3A86FF", rojo: "#EF233C", todos: "#cbd5e1" };
  const ESTILO = {
    linea_fase: { color: "#ffd166", weight: 3, dashArray: "12 7", opacity: 0.95 },
    eje_avance: { weight: 5, opacity: 0.95, lineCap: "round" },
    zona_reunion: { weight: 2, dashArray: "6 5", fillOpacity: 0.16, opacity: 0.95 },
  };

  /** ctx: { map(), api, toast, escenarioId(), usuario(), alDibujar(bool) } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const grupo = L.layerGroup();
    const graficos = new Map(); // id -> grafico
    let firma = "";
    let herramienta = null;
    let tipoActual = null;
    let puntas = []; // flechas de los ejes de avance (se reorientan al cambiar el zoom)

    const colorDe = (g) => COLOR_BANDO[g.bando] || COLOR_BANDO.todos;

    function elementoTooltip(texto) {
      const s = document.createElement("span");
      s.textContent = texto;
      return s;
    }

    function popup(g) {
      const div = document.createElement("div");
      div.className = "popup-grafico";
      const t = document.createElement("b");
      t.textContent = g.etiqueta || TIPOS_GRAFICO[g.tipo].nombre;
      const p = document.createElement("div");
      p.textContent = `${TIPOS_GRAFICO[g.tipo].nombre} · ${g.bando === "todos" ? "todos" : "bando " + g.bando} · turno ${g.turno} · ${g.autor}`;
      div.append(t, p);
      if (puedeBorrarGrafico(g, ctx.usuario().rol)) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "peligro";
        b.textContent = "Borrar";
        b.addEventListener("click", () => borrar(g.id));
        div.appendChild(b);
      }
      return div;
    }

    function puntaEje(g, puntos, color) {
      const marcador = L.marker(puntos[puntos.length - 1], { interactive: false, keyboard: false, icon: L.divIcon({ className: "flecha", html: "", iconSize: [1, 1] }) });
      const f = {
        actualizar() {
          const m = ctx.map();
          const a = m.latLngToLayerPoint(puntos[puntos.length - 2]);
          const b = m.latLngToLayerPoint(puntos[puntos.length - 1]);
          const grados = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
          marcador.setIcon(L.divIcon({
            className: "flecha", iconSize: [1, 1],
            html: `<svg width="1" height="1"><g transform="rotate(${grados})"><path d="M12 0 -8 -10 -3 0 -8 10Z" fill="${color}" stroke="#fff" stroke-width="1"/></g></svg>`,
          }));
        },
      };
      f.actualizar();
      puntas.push(f);
      return marcador;
    }

    function dibujarUno(g) {
      const color = g.tipo === "linea_fase" ? ESTILO.linea_fase.color : colorDe(g);
      const etiqueta = g.etiqueta || TIPOS_GRAFICO[g.tipo].nombre;
      let capa;
      if (g.tipo === "punto_control") {
        capa = L.marker(latLngsDe(g.geometria), {
          icon: L.divIcon({ className: "grafico-punto", html: `<span style="color:${color}"><b>PC</b></span>`, iconSize: [22, 22], iconAnchor: [11, 11] }),
        });
        capa.bindTooltip(elementoTooltip(etiqueta), { permanent: true, direction: "right", offset: [12, 0], className: "grafico-etiqueta" });
      } else if (g.tipo === "zona_reunion") {
        capa = L.polygon(latLngsDe(g.geometria), { ...ESTILO.zona_reunion, color, fillColor: color });
        capa.bindTooltip(elementoTooltip(etiqueta), { permanent: true, direction: "center", className: "grafico-etiqueta" });
      } else {
        const puntos = latLngsDe(g.geometria);
        capa = L.polyline(puntos, { ...ESTILO[g.tipo], color });
        capa.bindTooltip(elementoTooltip(etiqueta), { permanent: true, direction: "top", className: "grafico-etiqueta" });
        if (g.tipo === "eje_avance" && puntos.length > 1) puntaEje(g, puntos, color).addTo(grupo);
      }
      capa.bindPopup(() => popup(g));
      capa.addTo(grupo);
    }

    function dibujar() {
      grupo.clearLayers();
      puntas = [];
      for (const g of graficos.values()) dibujarUno(g);
    }

    /** Sincroniza con la lista completa que viene en el estado (solo redibuja si cambio). */
    function sincronizar(lista) {
      const nueva = lista.map((g) => `${g.id}:${g.etiqueta}`).join("|");
      if (nueva === firma) return;
      firma = nueva;
      graficos.clear();
      lista.forEach((g) => graficos.set(g.id, g));
      dibujar();
    }

    /** Cambio en vivo enviado por el servidor ({ accion: "crear"|"borrar", ... }). */
    function aplicar(m) {
      if (m.accion === "crear") graficos.set(m.grafico.id, m.grafico);
      else if (m.accion === "borrar") graficos.delete(m.id);
      firma = [...graficos.values()].map((g) => `${g.id}:${g.etiqueta}`).join("|");
      dibujar();
    }

    function limpiar() {
      graficos.clear();
      firma = "";
      dibujar();
    }

    async function borrar(id) {
      ctx.map().closePopup();
      try { await ctx.api("DELETE", `/api/escenarios/${ctx.escenarioId()}/graficos/${id}`); } catch (_) { /* toast ya mostrado */ }
    }

    // ---------------- herramientas de trazado (Leaflet.draw)
    function crearHerramienta(tipo) {
      const map = ctx.map();
      if (tipo === "punto_control") return new L.Draw.Marker(map, {});
      if (tipo === "zona_reunion") return new L.Draw.Polygon(map, { allowIntersection: false, showArea: false, shapeOptions: { color: "#2EC4B6", weight: 2 } });
      return new L.Draw.Polyline(map, { shapeOptions: { color: tipo === "linea_fase" ? "#ffd166" : "#3A86FF", weight: 4 } });
    }

    function marcarBoton(tipo) {
      document.querySelectorAll("[data-grafico]").forEach((b) => b.classList.toggle("activa", b.dataset.grafico === tipo));
      $("graf-cancelar").hidden = !tipo;
    }

    function cancelar() {
      if (herramienta) { try { herramienta.disable(); } catch (_) { /* ya terminada */ } }
      herramienta = null;
      tipoActual = null;
      marcarBoton(null);
      setTimeout(() => ctx.alDibujar(false), 60); // el ultimo clic del trazado no debe contar como clic de mapa
    }

    function iniciar(tipo) {
      if (tipoActual === tipo) return cancelar();
      cancelar();
      tipoActual = tipo;
      herramienta = crearHerramienta(tipo);
      herramienta.enable();
      marcarBoton(tipo);
      ctx.alDibujar(true);
    }

    async function alCrearse(evento) {
      if (!tipoActual) return;
      const tipo = tipoActual;
      const geometria = evento.layer.toGeoJSON().geometry;
      cancelar();
      const etiqueta = $("graf-etiqueta").value.trim();
      const cuerpo = { tipo, etiqueta, geometria };
      if (ctx.usuario().rol === "instructor") cuerpo.bando = $("graf-bando").value;
      try {
        const g = await ctx.api("POST", `/api/escenarios/${ctx.escenarioId()}/graficos`, cuerpo);
        if (!graficos.has(g.id)) aplicar({ accion: "crear", grafico: g }); // la difusion por WebSocket puede llegar antes o despues
        $("graf-etiqueta").value = "";
      } catch (_) { /* toast ya mostrado */ }
    }

    function conectar(map) {
      grupo.addTo(map);
      map.on("zoomend", () => puntas.forEach((f) => f.actualizar()));
      map.on(L.Draw.Event.CREATED, alCrearse);
      document.querySelectorAll("[data-grafico]").forEach((b) => b.addEventListener("click", () => iniciar(b.dataset.grafico)));
      $("graf-cancelar").addEventListener("click", cancelar);
      document.addEventListener("keydown", (e) => { if (e.key === "Escape" && tipoActual) cancelar(); });
    }

    return { conectar, sincronizar, aplicar, limpiar, cancelar, capa: grupo };
  }

  raiz.Graficos = { crear };
})(window);
