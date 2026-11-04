/* Areas de referencia y zonas (engine/zonas.py): areas de patrulla, zonas de exclusion y zonas de no vuelo.
 * El director las dibuja para todos (o para un bando) y cada bando, las suyas; se dibujan en el mapa y se listan en
 * la tarjeta «Áreas y zonas». */
(function (raiz) {
  "use strict";

  const TIPOS = { patrulla: "Área de patrulla", exclusion: "Zona de exclusión", no_vuelo: "Zona de no vuelo" };
  const ESTILO = {
    patrulla: { color: "#06d6a0", weight: 2, dashArray: "10 6", fillOpacity: 0.05 },
    exclusion: { color: "#f77f00", weight: 2.5, dashArray: "4 4", fillOpacity: 0.1 },
    no_vuelo: { color: "#ef233c", weight: 2.5, fillOpacity: 0.12 },
  };

  /** ctx: { api, toast, rutaEsc, datos(), map(), rol(), alDibujar(bool), seleccion() } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const grupo = L.layerGroup();
    let firma = "";
    let herramienta = null;

    const director = () => ctx.rol() === "instructor";
    const propia = (z) => director() || z.bando === ctx.rol();
    const dueno = (z) => (z.bando === "todos" ? "Dirección" : z.bando === "azul" ? "Azul" : "Rojo");

    function texto(t) {
      const s = document.createElement("span");
      s.textContent = t;
      return s;
    }

    function dibujarMapa(zonas) {
      grupo.clearLayers();
      for (const z of zonas) {
        if (z.puntos.length < 3) continue;
        const capa = L.polygon(z.puntos, { ...ESTILO[z.tipo], fillColor: ESTILO[z.tipo].color, interactive: false });
        capa.bindTooltip(texto(`${z.nombre || TIPOS[z.tipo]}${z.armas ? " · armas libres" : ""}`),
          { permanent: true, direction: "center", className: "grafico-etiqueta zona-etiqueta" });
        capa.addTo(grupo);
      }
    }

    function dibujarLista(zonas) {
      const ul = $("zonas-lista");
      ul.replaceChildren();
      if (!zonas.length) {
        const li = document.createElement("li");
        li.className = "vacio";
        li.textContent = "Sin áreas ni zonas.";
        ul.appendChild(li);
        return;
      }
      for (const z of zonas) {
        const li = document.createElement("li");
        li.className = `zona-item zona-${z.tipo}`;
        const t = document.createElement("div");
        const b = document.createElement("b");
        b.textContent = z.nombre || TIPOS[z.tipo];
        const ancla = z.unidad_id && ((ctx.datos() || {}).unidades || []).find((u) => u.id === z.unidad_id);
        t.append(b, texto(` · ${TIPOS[z.tipo]} · ${dueno(z)}${ancla ? ` · acompaña a ${ancla.nombre}` : ""}`));
        li.appendChild(t);
        if (propia(z)) {
          const fila = document.createElement("div");
          fila.className = "fila";
          if (z.tipo !== "patrulla" && z.bando !== "todos") {
            const l = document.createElement("label");
            l.className = "chk";
            const c = document.createElement("input");
            c.type = "checkbox";
            c.checked = !!z.armas;
            c.addEventListener("change", () => cambiar(z.id, { armas: c.checked }));
            l.append(c, texto("Las armas propias tiran contra quien entre"));
            fila.appendChild(l);
          }
          const borrar = document.createElement("button");
          borrar.type = "button";
          borrar.className = "mini peligro";
          borrar.textContent = "Borrar";
          borrar.addEventListener("click", () => quitar(z.id));
          fila.appendChild(borrar);
          li.appendChild(fila);
        } else if (z.armas) li.appendChild(texto(" · armas libres"));
        ul.appendChild(li);
      }
    }

    /** Sincroniza con las zonas del estado (solo redibuja si cambiaron). */
    function render(data) {
      const zonas = (data && data.zonas) || [];
      const nueva = JSON.stringify(zonas);
      $("zona-form").hidden = !(director() || ["azul", "rojo"].includes(ctx.rol()));
      $("zona-bando-fila").hidden = !director();
      $("zona-armas-fila").hidden = director() || $("zona-tipo").value === "patrulla";
      if (nueva === firma) return;
      firma = nueva;
      dibujarMapa(zonas);
      dibujarLista(zonas);
    }

    async function cambiar(id, cuerpo) {
      try { await ctx.api("PATCH", ctx.rutaEsc(`/zonas/${id}`), cuerpo); } catch (_) { /* toast ya mostrado */ }
    }

    async function quitar(id) {
      if (!confirm("¿Borrar esta zona? Las unidades que patrullan en ella dejan de hacerlo.")) return;
      try { await ctx.api("DELETE", ctx.rutaEsc(`/zonas/${id}`)); } catch (_) { /* toast ya mostrado */ }
    }

    function cancelar() {
      if (herramienta) { try { herramienta.disable(); } catch (_) { /* ya terminada */ } }
      herramienta = null;
      $("zona-dibujar").classList.remove("activa");
      $("zona-cancelar").hidden = true;
      setTimeout(() => ctx.alDibujar(false), 60); // el ultimo clic del trazado no cuenta como clic de mapa
    }

    function iniciar() {
      if (herramienta) return cancelar();
      const tipo = $("zona-tipo").value;
      herramienta = new L.Draw.Polygon(ctx.map(), { allowIntersection: false, showArea: false, shapeOptions: { color: ESTILO[tipo].color, weight: 2 } });
      herramienta.enable();
      $("zona-dibujar").classList.add("activa");
      $("zona-cancelar").hidden = false;
      ctx.alDibujar(true);
      ctx.toast("Haga clic en el mapa en cada vértice; para terminar, clic en el primero.", true);
    }

    /** La unidad seleccionada que puede llevar la zona (propia; el director, cualquiera), o null. */
    function unidadAncla() {
      const u = ctx.seleccion();
      return u && u.estado === "activa" && (director() || u.bando === ctx.rol()) ? u : null;
    }

    async function enviar(cuerpo) {
      if (director()) cuerpo.bando = $("zona-bando").value;
      else if (cuerpo.tipo !== "patrulla") cuerpo.armas = $("zona-armas").checked;
      try {
        await ctx.api("POST", ctx.rutaEsc("/zonas"), cuerpo);
        $("zona-nombre").value = "";
        ctx.toast(`${TIPOS[cuerpo.tipo]} creada.`, true);
      } catch (_) { /* toast ya mostrado */ }
    }

    function circulo() {
      const u = unidadAncla();
      if (!u) return ctx.toast("Seleccione antes una unidad propia: el círculo va alrededor de ella.");
      const radio = Math.max(1, Math.min(300, parseFloat($("zona-radio").value) || 20));
      enviar({ tipo: $("zona-tipo").value, nombre: $("zona-nombre").value.trim(), unidad_id: u.id, radio_km: radio,
        acompana: $("zona-acompana").checked });
    }

    async function alCrearse(e) {
      if (!herramienta) return;
      const anillo = e.layer.getLatLngs()[0] || [];
      cancelar();
      const cuerpo = { tipo: $("zona-tipo").value, nombre: $("zona-nombre").value.trim(), puntos: anillo.map((p) => [p.lat, p.lng]) };
      if ($("zona-acompana").checked) {
        const u = unidadAncla();
        if (!u) return ctx.toast("Para que la zona acompañe a una unidad, seleccione antes una unidad propia.");
        cuerpo.unidad_id = u.id;
      }
      return enviar(cuerpo);
    }

    function conectar() {
      const map = ctx.map();
      grupo.addTo(map);
      map.on(L.Draw.Event.CREATED, alCrearse);
      $("zona-dibujar").addEventListener("click", iniciar);
      $("zona-cancelar").addEventListener("click", cancelar);
      $("zona-circulo").addEventListener("click", circulo);
      $("zona-tipo").addEventListener("change", () => { $("zona-armas-fila").hidden = director() || $("zona-tipo").value === "patrulla"; });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape" && herramienta) cancelar(); });
    }

    /** Areas de patrulla que la unidad puede recorrer (las de su bando y las de la direccion). */
    function areasDePatrulla(data) {
      return ((data && data.zonas) || []).filter((z) => z.tipo === "patrulla" && z.puntos.length >= 3);
    }

    return { conectar, render, cancelar, areasDePatrulla, capa: grupo };
  }

  raiz.Zonas = { crear, TIPOS };
})(window);
