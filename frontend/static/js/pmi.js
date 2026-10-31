/* Puntos medios de impacto (PMI) sobre las pistas enemigas (backend/app/engine/pmi.py y routers/pmi.py).
 *
 * Operaciones (A-3) pide a Inteligencia los PMI de la pista de una base aerea enemiga. Inteligencia (A-2) pide al
 * sistema la propuesta (cortes sobre el eje de la pista para que ningun tramo sano alcance para despegar), puede
 * correr cada punto arrastrandolo en el mapa y los entrega. Con los PMI entregados, el ataque a esa pista hace todo
 * su daño; sin ellos, la mitad. Los PMI entregados se dibujan en el mapa al acercarse a la base. */
(function (raiz) {
  "use strict";

  const ZOOM_MARCAS = 11; // desde este zoom se ven los PMI entregados (de lejos se encimarian sobre la base)

  /** 8.2872 -> «08°17'13.9"» con el hemisferio; la latitud con 2 cifras de grados y la longitud con 3. */
  function gms(v, pos, neg, cifras) {
    const a = Math.abs(v);
    const g = Math.floor(a);
    const m = Math.floor((a - g) * 60);
    const s = ((a - g) * 60 - m) * 60;
    return `${String(g).padStart(cifras, "0")}°${String(m).padStart(2, "0")}'${s.toFixed(1).padStart(4, "0")}" ${v >= 0 ? pos : neg}`;
  }
  const textoCoord = (lat, lon) => `${gms(lat, "N", "S", 2)} ${gms(lon, "E", "O", 3)}`;

  /** Bases aereas enemigas conocidas (data.pmi_bases) a las que se les pueden pedir PMI: sin un pedido vigente del bando. */
  function basesPedibles(bases, bando, pedidos) {
    const tomadas = new Set((pedidos || []).filter((p) => p.bando === bando).map((p) => p.base_id));
    return (bases || []).filter((b) => !tomadas.has(b.id));
  }

  /** ctx: { api, toast, rutaEsc(sufijo), datos(), bando() (el que actua o null), puede(funcion), map() } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const el = (tag, clase, texto) => {
      const e = document.createElement(tag);
      if (clase) e.className = clase;
      if (texto !== undefined) e.textContent = texto;
      return e;
    };
    let capaEntregados = null;
    let capaBorrador = null;
    let borrador = null; // { pedidoId, puntos: [{ id, lat, lon, nota }], pista }
    let firma = "";

    function capas() {
      const map = ctx.map();
      if (!map || capaEntregados) return;
      capaEntregados = L.layerGroup();
      capaBorrador = L.layerGroup().addTo(map);
      const ajustar = () => {
        if (map.getZoom() >= ZOOM_MARCAS) capaEntregados.addTo(map);
        else map.removeLayer(capaEntregados);
      };
      map.on("zoomend", ajustar);
      ajustar();
    }

    const icono = (id, clase) => L.divIcon({
      className: `pmi-marca ${clase}`, iconSize: [22, 22], iconAnchor: [11, 11],
      html: `<svg viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/>`
        + `<path d="M11 1v6M11 15v6M1 11h6M15 11h6" stroke="currentColor" stroke-width="2"/></svg><span>${id}</span>`,
    });

    function dibujarEntregados(pedidos) {
      capaEntregados.clearLayers();
      for (const p of pedidos) {
        if (p.estado !== "entregado") continue;
        for (const pt of p.puntos) {
          L.marker([pt.lat, pt.lon], { icon: icono(pt.id, p.bando), interactive: true, keyboard: false })
            .bindTooltip(`${pt.id} · pista de ${p.base_nombre}<br>${textoCoord(pt.lat, pt.lon)}${pt.nota ? `<br>${pt.nota}` : ""}`)
            .addTo(capaEntregados);
        }
      }
    }

    function dibujarBorrador() {
      capaBorrador.clearLayers();
      if (!borrador) return;
      borrador.puntos.forEach((pt, i) => {
        const m = L.marker([pt.lat, pt.lon], { icon: icono(pt.id, "borrador"), draggable: true, keyboard: false })
          .bindTooltip("Arrástrelo para correr el punto");
        m.on("dragend", () => {
          const { lat, lng } = m.getLatLng();
          borrador.puntos[i] = { ...borrador.puntos[i], lat: Math.round(lat * 1e6) / 1e6, lon: Math.round(lng * 1e6) / 1e6, nota: "Ajustado por Inteligencia" };
          firma = "";
          render(ctx.datos());
        });
        m.addTo(capaBorrador);
      });
    }

    async function preparar(p) {
      try {
        const r = await ctx.api("POST", ctx.rutaEsc(`/pmi/${p.id}/propuesta`), {});
        borrador = { pedidoId: p.id, puntos: r.puntos, pista: r.pista, mos: r.mos_m };
        dibujarBorrador();
        const map = ctx.map();
        if (map) map.fitBounds(r.puntos.map((x) => [x.lat, x.lon]).concat(r.pista.extremos), { padding: [90, 90], maxZoom: 15 });
        firma = "";
        render(ctx.datos());
      } catch (_) { /* toast ya mostrado */ }
    }

    async function entregar() {
      if (!borrador) return;
      try {
        await ctx.api("POST", ctx.rutaEsc(`/pmi/${borrador.pedidoId}/entregar`), { puntos: borrador.puntos });
        ctx.toast("PMI entregados a Operaciones: el ataque a esa pista hace ahora todo su daño", true);
        borrador = null;
        dibujarBorrador();
      } catch (_) { /* toast ya mostrado */ }
    }

    async function pedir() {
      const id = parseInt($("pmi-base").value, 10);
      if (!id) return ctx.toast("Elija la base aérea enemiga.");
      try {
        await ctx.api("POST", ctx.rutaEsc("/pmi"), { base_id: id });
        ctx.toast("Pedido enviado a Inteligencia (A-2)", true);
      } catch (_) { /* toast ya mostrado */ }
    }

    async function cancelar(p) {
      if (!confirm(`¿Dar de baja el pedido de PMI de ${p.base_nombre}?${p.estado === "entregado" ? " Los PMI entregados dejan de valer." : ""}`)) return;
      try {
        await ctx.api("POST", ctx.rutaEsc(`/pmi/${p.id}/cancelar`), {});
        if (borrador && borrador.pedidoId === p.id) { borrador = null; dibujarBorrador(); }
      } catch (_) { /* toast ya mostrado */ }
    }

    function listaPuntos(puntos) {
      const ol = el("ol", "pmi-puntos");
      for (const pt of puntos) {
        const li = el("li");
        li.append(el("b", "", pt.id), ` ${textoCoord(pt.lat, pt.lon)}`);
        if (pt.nota) li.append(el("small", "", ` · ${pt.nota}`));
        ol.appendChild(li);
      }
      return ol;
    }

    function boton(texto, clase, accion, titulo) {
      const b = el("button", `mini ${clase}`, texto);
      b.type = "button";
      if (titulo) b.title = titulo;
      b.addEventListener("click", accion);
      return b;
    }

    function render(data) {
      if (!data) return;
      capas();
      const pedidos = data.pmi || [];
      const bando = ctx.bando();
      const pide = !!bando && ctx.puede("aereo");
      const entrega = !!bando && ctx.puede("reconocimiento");
      const nueva = JSON.stringify([pedidos, bando, pide, entrega, borrador, data.pmi_bases]);
      if (nueva === firma) return;
      firma = nueva;
      if (capaEntregados) dibujarEntregados(pedidos);
      if (borrador && !pedidos.some((p) => p.id === borrador.pedidoId && p.estado === "pedido")) { borrador = null; dibujarBorrador(); }

      const pendientes = pedidos.filter((p) => p.estado === "pedido").length;
      $("pmi-contador").textContent = pendientes ? String(pendientes) : "";
      $("pmi-pedir").hidden = !pide;
      if (pide) {
        const sel = $("pmi-base");
        const previo = sel.value;
        while (sel.firstChild) sel.removeChild(sel.firstChild);
        const bases = basesPedibles(data.pmi_bases, bando, pedidos);
        for (const b of bases) sel.appendChild(Object.assign(el("option", "", b.nombre), { value: String(b.id) }));
        if (bases.some((b) => String(b.id) === previo)) sel.value = previo;
        $("btn-pmi-pedir").disabled = !bases.length;
      }
      const lista = $("lista-pmi");
      while (lista.firstChild) lista.removeChild(lista.firstChild);
      if (!pedidos.length) lista.appendChild(el("li", "vacio", "Sin pedidos de puntos medios de impacto."));
      for (const p of pedidos) {
        const li = el("li", `pmi-pedido ${p.estado}`);
        const cab = el("div", "pmi-cab");
        cab.append(el("b", "", `Pista de ${p.base_nombre}`), el("span", `chip ${p.estado === "entregado" ? "res" : "pend"}`, p.estado === "entregado" ? "ENTREGADO" : "PEDIDO"));
        li.appendChild(cab);
        li.appendChild(el("small", "", `Pidió ${p.pedido_por}${p.entregado_por ? ` · entregó ${p.entregado_por}` : ""}${data.vista === "completa" ? ` · bando ${p.bando}` : ""}`));
        const acciones = el("div", "fila-botones");
        if (p.estado === "entregado") {
          if (p.pista && p.pista.largo_m) {
            li.appendChild(el("small", "", `${p.pista.ref ? `Pista ${p.pista.ref}, ` : ""}${Math.round(p.pista.largo_m)} m${p.pista.estimada ? " (estimada, sin plano)" : ""}: con estos PMI el ataque a la pista hace todo su daño.`));
          }
          li.appendChild(listaPuntos(p.puntos));
          acciones.appendChild(boton("Ver en el mapa", "secundario", () => {
            const map = ctx.map();
            if (map && p.puntos.length) map.fitBounds(p.puntos.map((x) => [x.lat, x.lon]), { padding: [90, 90], maxZoom: 15 });
          }));
        } else if (entrega && borrador && borrador.pedidoId === p.id) {
          const pista = borrador.pista;
          li.appendChild(el("p", "ayuda", `Pista ${pista.ref || "(estimada, sin plano del aerodromo)"} de ${Math.round(pista.largo_m)} m: `
            + `${borrador.puntos.length} cortes dejan tramos de ~${pista.tramo_m} m, menos que los ${Math.round(borrador.mos)} m que necesita un caza para despegar. `
            + "Puede arrastrar cada punto en el mapa antes de entregar."));
          li.appendChild(listaPuntos(borrador.puntos));
          acciones.append(boton("Entregar a Operaciones", "primario", entregar), boton("Descartar", "secundario", () => { borrador = null; dibujarBorrador(); firma = ""; render(ctx.datos()); }));
        } else if (entrega) {
          acciones.appendChild(boton("Preparar los PMI…", "primario", () => preparar(p), "El sistema propone los puntos sobre la pista; usted los revisa y los entrega"));
        } else {
          li.appendChild(el("small", "", "Esperando que Inteligencia (A-2) los prepare."));
        }
        if (bando && (pide || entrega)) acciones.appendChild(boton(p.estado === "entregado" ? "Dar de baja" : "Cancelar", "secundario", () => cancelar(p)));
        if (acciones.childNodes.length) li.appendChild(acciones);
        lista.appendChild(li);
      }
    }

    function conectar() {
      $("btn-pmi-pedir").addEventListener("click", pedir);
    }

    /** Si el bando que actua tiene los PMI de esa base entregados. */
    const conPmi = (baseId) => {
      const d = ctx.datos();
      const bando = ctx.bando();
      return !!d && (d.pmi || []).some((p) => p.base_id === baseId && p.estado === "entregado" && (!bando || p.bando === bando));
    };

    return { render, conectar, conPmi };
  }

  const api = { crear, textoCoord, basesPedibles, ZOOM_MARCAS };
  raiz.Pmi = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
