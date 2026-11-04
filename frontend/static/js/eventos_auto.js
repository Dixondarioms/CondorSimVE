/* Eventos automaticos del director (engine/eventos_auto.py): reglas «cuando pasa esto, hacer aquello».
 * Editor en CONSOLA → «Eventos automáticos»: la lista de reglas (activar, borrar) y el formulario de una regla nueva
 * con su disparador y sus acciones. Las unidades y los objetivos se nombran por su nombre. */
(function (raiz) {
  "use strict";

  /** ctx: { api, toast, rutaEsc, datos(), catalogo(), esDirector(), escenarioId() } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    let reglas = [];
    let acciones = [];
    let cargado = null; // escenario cuyas reglas estan cargadas
    let punto = null; // [lat, lon] de la accion «aparecer»
    let esperandoPunto = false;

    function opciones(sel, lista, valor) {
      const previo = valor ?? sel.value;
      sel.replaceChildren(...lista.map(([v, t]) => Object.assign(document.createElement("option"), { value: v, textContent: t })));
      if (lista.some(([v]) => String(v) === String(previo))) sel.value = previo;
    }

    function mostrarCampos() {
      const d = $("ea-disparador").value;
      for (const t of ["entra_area", "hora", "destruida", "objetivo"]) $(`ea-d-${t}`).hidden = d !== t;
      const a = $("ea-accion").value;
      for (const t of ["mensaje", "aparecer", "clima", "puntos", "lanzar"]) $(`ea-a-${t}`).hidden = a !== t;
    }

    function llenarListas() {
      const data = ctx.datos();
      if (!data) return;
      const zonas = (data.zonas || []).filter((z) => z.puntos.length >= 3);
      opciones($("ea-area"), zonas.length ? zonas.map((z) => [z.id, `${z.nombre || "Zona sin nombre"} (${z.tipo})`]) : [["", "Dibuje antes una zona en «Áreas y zonas»"]]);
      const clasePorId = new Map(((ctx.catalogo() || {}).clases || []).map((c) => [c.id, c]));
      const nombres = [...new Set(data.unidades.filter((u) => u.estado === "activa").map((u) => u.nombre))].sort((a, b) => a.localeCompare(b, "es"));
      opciones($("ea-unidad"), nombres.map((n) => [n, n]));
      opciones($("ea-unidad-area"), [["", "Cualquier unidad"], ...nombres.map((n) => [n, n])]);
      const lanzadores = [...new Set(data.unidades.filter((u) => Logica.puedeLanzarMisiles(u, clasePorId.get(u.clase)))
        .map((u) => u.nombre))].sort((a, b) => a.localeCompare(b, "es"));
      opciones($("ea-la-unidad"), lanzadores.length ? lanzadores.map((n) => [n, n]) : [["", "No hay lanzadores de misiles"]]);
      opciones($("ea-la-blanco"), nombres.map((n) => [n, n]));
      opciones($("ea-objetivo"), (data.objetivos || []).map((o) => [o.nombre, `${o.nombre} (${o.bando})`]));
      const clases = ((ctx.catalogo() || {}).clases || []).filter((c) => c.tipo !== "base" && !c.misil);
      opciones($("ea-ap-clase"), clases.map((c) => [c.id, c.nombre]));
    }

    function dibujarLista() {
      const ul = $("ea-lista");
      ul.replaceChildren();
      if (!reglas.length) {
        ul.appendChild(Object.assign(document.createElement("li"), { className: "vacio", textContent: "Sin eventos automáticos." }));
        return;
      }
      reglas.forEach((r, i) => {
        const li = document.createElement("li");
        li.className = "ea-regla";
        const t = document.createElement("div");
        const b = document.createElement("b");
        b.textContent = r.nombre;
        t.append(b, document.createTextNode(` · ${Logica.textoReglaAuto(r)}`));
        const fila = document.createElement("div");
        fila.className = "fila";
        const l = document.createElement("label");
        l.className = "chk";
        const c = Object.assign(document.createElement("input"), { type: "checkbox", checked: r.activo !== false });
        c.addEventListener("change", () => { reglas[i].activo = c.checked; guardar(); });
        l.append(c, Object.assign(document.createElement("span"), { textContent: "Activa" }));
        const borrar = Object.assign(document.createElement("button"), { type: "button", className: "mini peligro", textContent: "Borrar" });
        borrar.addEventListener("click", () => { reglas.splice(i, 1); guardar(); });
        fila.append(l, borrar);
        li.append(t, fila);
        ul.appendChild(li);
      });
    }

    function dibujarAcciones() {
      const ul = $("ea-acciones");
      ul.replaceChildren(...acciones.map((a, i) => {
        const li = document.createElement("li");
        li.textContent = Logica.textoAccionAuto(a);
        const x = Object.assign(document.createElement("button"), { type: "button", className: "mini", textContent: "✕", title: "Quitar" });
        x.addEventListener("click", () => { acciones.splice(i, 1); dibujarAcciones(); });
        li.appendChild(x);
        return li;
      }));
    }

    async function cargar() {
      if (!ctx.esDirector() || !ctx.escenarioId()) return;
      try {
        const r = await ctx.api("GET", ctx.rutaEsc("/eventos_auto"), undefined, true);
        reglas = r.reglas || [];
        cargado = ctx.escenarioId();
        dibujarLista();
      } catch (_) { /* sin permiso o sin escenario */ }
    }

    async function guardar() {
      try {
        const r = await ctx.api("PUT", ctx.rutaEsc("/eventos_auto"), { reglas });
        reglas = r.reglas;
        dibujarLista();
        return true;
      } catch (_) { await cargar(); return false; }
    }

    function accionDelFormulario() {
      const tipo = $("ea-accion").value;
      if (tipo === "mensaje") {
        const texto = $("ea-texto").value.trim();
        if (!texto) return ctx.toast("Escriba el texto del mensaje.");
        return { tipo, para: $("ea-para").value, texto };
      }
      if (tipo === "aparecer") {
        if (!punto) return ctx.toast("Elija en el mapa dónde aparecen las unidades.");
        return { tipo, bando: $("ea-ap-bando").value, clase: $("ea-ap-clase").value, cantidad: Math.max(1, Math.min(12, parseInt($("ea-ap-cantidad").value, 10) || 1)),
          nombre: $("ea-ap-nombre").value.trim(), lat: punto[0], lon: punto[1] };
      }
      if (tipo === "clima") return { tipo, clima: $("ea-clima").value };
      if (tipo === "puntos") return { tipo, bando: $("ea-pt-bando").value, puntos: parseInt($("ea-pt-n").value, 10) || 0 };
      if (tipo === "lanzar") {
        if (!$("ea-la-unidad").value || !$("ea-la-blanco").value) return ctx.toast("Elija el lanzador y el blanco.");
        return { tipo, unidad: $("ea-la-unidad").value, blanco: $("ea-la-blanco").value,
          misiles: Math.max(1, Math.min(4, parseInt($("ea-la-misiles").value, 10) || 1)) };
      }
      return { tipo };
    }

    function disparadorDelFormulario() {
      const tipo = $("ea-disparador").value;
      if (tipo === "entra_area") {
        const z = (ctx.datos().zonas || []).find((x) => String(x.id) === $("ea-area").value);
        if (!z) return ctx.toast("Elija el área (dibújela antes en «Áreas y zonas»).");
        return { tipo, area: z.puntos, area_nombre: z.nombre || "", bando: $("ea-bando").value, unidad: $("ea-unidad-area").value };
      }
      if (tipo === "hora") return $("ea-hora").value ? { tipo, hora: $("ea-hora").value } : ctx.toast("Elija la hora.");
      if (tipo === "destruida") return { tipo, unidad: $("ea-unidad").value };
      return $("ea-objetivo").value ? { tipo, objetivo: $("ea-objetivo").value, estado: $("ea-obj-estado").value } : ctx.toast("No hay objetivos.");
    }

    /** Clic en el mapa mientras se elige el punto de «aparecer». Devuelve true si lo uso. */
    function alClicMapa(lat, lon) {
      if (!esperandoPunto) return false;
      esperandoPunto = false;
      punto = [lat, lon];
      $("ea-ap-donde").textContent = `En ${lat.toFixed(3)}, ${lon.toFixed(3)}.`;
      $("ea-ap-punto").classList.remove("activa");
      return true;
    }

    function conectar() {
      $("ea-disparador").addEventListener("change", mostrarCampos);
      $("ea-accion").addEventListener("change", mostrarCampos);
      $("sec-eventos-auto").addEventListener("toggle", () => { if ($("sec-eventos-auto").open) { llenarListas(); cargar(); } });
      $("ea-ap-punto").addEventListener("click", () => {
        esperandoPunto = true;
        $("ea-ap-punto").classList.add("activa");
        ctx.toast("Haga clic en el mapa donde aparecen las unidades.", true);
      });
      $("ea-agregar-accion").addEventListener("click", () => {
        const a = accionDelFormulario();
        if (!a) return;
        acciones.push(a);
        dibujarAcciones();
      });
      $("ea-guardar").addEventListener("click", async () => {
        const d = disparadorDelFormulario();
        if (!d) return;
        if (!acciones.length) {
          const a = accionDelFormulario();
          if (!a) return;
          acciones.push(a);
        }
        const nueva = { nombre: $("ea-nombre").value.trim() || `Regla ${reglas.length + 1}`, activo: true,
          repetir: $("ea-repetir").checked, disparador: d, acciones: acciones.slice() };
        reglas.push(nueva);
        if (await guardar()) {
          acciones = [];
          punto = null;
          $("ea-nombre").value = "";
          $("ea-ap-donde").textContent = "";
          dibujarAcciones();
          ctx.toast("Evento automático guardado.", true);
        }
      });
      mostrarCampos();
    }

    function render(data) {
      if (!ctx.esDirector() || !data) return;
      if (cargado !== ctx.escenarioId()) { cargado = ctx.escenarioId(); cargar(); }
      if ($("sec-eventos-auto").open && !document.activeElement.closest("#sec-eventos-auto")) llenarListas();
    }

    return { conectar, render, alClicMapa };
  }

  raiz.EventosAuto = { crear };
})(window);
