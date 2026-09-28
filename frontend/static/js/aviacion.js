/* Aviacion: selector de aeronaves con fotos (F-16, Su-30), envio de grupos de caza desde una base aerea propia
 * y capa de referencia con las bases aereas de Venezuela. */
(function (raiz) {
  "use strict";
  const { basesAereasPropias, aeronavesComprometidas, baseEnEscenario, nombreCortoBase } = Logica;

  const AVION = "M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z";
  const ESCALA_ATAQUE = 1.5; // multiplicador de ataque que llena la barra

  /** ctx: { map(), api, toast, rutaEsc(sufijo), usuario(), catalogo(), datos(), escenarioId(), capa } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const el = (tag, clase, texto) => {
      const e = document.createElement(tag);
      if (clase) e.className = clase;
      if (texto !== undefined) e.textContent = texto;
      return e;
    };
    const limpiar = (n) => { while (n.firstChild) n.removeChild(n.firstChild); };

    let modoActual = null; // { tipo: "despegue" | "modelo", alConfirmar }
    let elegido = null; // id del modelo marcado en el selector

    const modelos = () => (ctx.catalogo() && ctx.catalogo().modelos) || [];
    const topes = () => (ctx.catalogo() && ctx.catalogo().aeronaves) || { max_grupo: 8, max_bando: 24 };

    // ------------------------------------------------------------------ selector de modelo con fotos
    function barraAtaque(nombre, valor) {
      const fila = el("div", "barra-ataque");
      fila.append(el("span", "", nombre));
      const pista = el("div", "pista");
      const relleno = el("div", "relleno");
      relleno.style.width = `${Math.min(100, Math.round((valor / ESCALA_ATAQUE) * 100))}%`;
      pista.appendChild(relleno);
      fila.append(pista, el("b", "", `×${valor.toFixed(2)}`));
      return fila;
    }

    function tarjeta(m) {
      const b = el("button", "tarjeta-modelo");
      b.type = "button";
      b.dataset.modelo = m.id;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", "false");
      const foto = el("img");
      foto.src = m.foto;
      foto.alt = `${m.nombre} de la Aviación Militar Bolivariana`;
      foto.loading = "lazy";
      const cuerpo = el("div", "cuerpo");
      cuerpo.append(el("h4", "", m.nombre), el("small", "", `${m.fabricante} · ${m.pais}`), el("p", "funcion", m.funcion));
      const specs = el("dl", "specs");
      for (const [k, v] of [
        ["Velocidad", `${m.velocidad_kmh} km/h`], ["Alcance de armas", `${m.alcance_km} km`],
        ["Detección", `${m.deteccion_km} km`], ["Autonomía", `${m.autonomia_km} km`],
      ]) {
        const d = el("div");
        d.append(el("dt", "", k), el("dd", "", v));
        specs.appendChild(d);
      }
      cuerpo.appendChild(specs);
      const ataque = el("div", "ataques");
      ataque.append(barraAtaque("Vs aire", m.ataque_vs.aerea), barraAtaque("Vs tierra", m.ataque_vs.terrestre), barraAtaque("Vs mar", m.ataque_vs.naval));
      cuerpo.append(ataque, el("p", "arma", m.armamento), el("p", "desc", m.descripcion));
      const c = m.credito;
      const credito = el("small", "credito");
      credito.append("Foto: ");
      const enlace = el("a", "", `${c.autor}, ${c.licencia}`);
      enlace.href = c.pagina;
      enlace.target = "_blank";
      enlace.rel = "noopener noreferrer";
      enlace.addEventListener("click", (e) => e.stopPropagation());
      credito.appendChild(enlace);
      cuerpo.appendChild(credito);
      b.append(foto, cuerpo);
      b.addEventListener("click", () => marcar(m.id));
      return b;
    }

    function marcar(id) {
      elegido = id;
      document.querySelectorAll("#aer-tarjetas .tarjeta-modelo").forEach((t) => {
        const sel = t.dataset.modelo === id;
        t.classList.toggle("sel", sel);
        t.setAttribute("aria-checked", sel ? "true" : "false");
      });
      actualizarResumen();
    }

    function actualizarResumen() {
      const m = modelos().find((x) => x.id === elegido);
      const n = parseInt($("aer-cantidad").value, 10) || 1;
      const conf = $("aer-confirmar");
      if (!m) { $("aer-resumen").textContent = "Elija un modelo de aeronave."; conf.disabled = true; return; }
      conf.disabled = false;
      if (modoActual.tipo === "modelo") {
        $("aer-resumen").textContent = `${m.corto} ×${n}: los valores de alcance, detección y autonomía del formulario se ajustan al modelo.`;
        return;
      }
      const rol = ctx.usuario().rol;
      const datos = ctx.datos();
      const en = aeronavesComprometidas(datos.unidades, datos.ordenes, rol);
      const base = datos.unidades.find((u) => String(u.id) === $("aer-base").value);
      const previa = datos.ordenes.find((o) => o.estado === "pendiente" && base && o.unidad_id === base.id && o.tipo === "despegar");
      const descontar = previa ? (Logica.detalleDespegue(previa).aeronaves || 0) : 0;
      const total = en - descontar + n;
      const excede = total > topes().max_bando;
      $("aer-resumen").textContent = `${m.corto} ×${n} saldrá de ${base ? base.nombre : "la base"} al resolverse el turno y aparecerá junto a ella; `
        + `podrá recibir órdenes el turno siguiente. Aeronaves del bando: ${total} de ${topes().max_bando}${excede ? " (excede el tope)" : ""}.`;
      conf.disabled = excede;
    }

    function llenarCantidad(actual) {
      const sel = $("aer-cantidad");
      limpiar(sel);
      for (let n = 1; n <= topes().max_grupo; n++) {
        const o = el("option", "", n === 1 ? "1 aeronave" : `${n} aeronaves`);
        o.value = String(n);
        sel.appendChild(o);
      }
      sel.value = String(Math.min(actual || 4, topes().max_grupo));
    }

    function abrirDialogo({ tipo, titulo, ayuda, textoConfirmar, bases, modeloInicial, cantidadInicial, alConfirmar }) {
      modoActual = { tipo, alConfirmar };
      $("aer-titulo").textContent = titulo;
      $("aer-ayuda").textContent = ayuda;
      $("aer-confirmar").textContent = textoConfirmar;
      const tarjetas = $("aer-tarjetas");
      limpiar(tarjetas);
      modelos().forEach((m) => tarjetas.appendChild(tarjeta(m)));
      llenarCantidad(cantidadInicial);
      const despegue = tipo === "despegue";
      $("aer-base-fila").hidden = !despegue;
      $("aer-indicativo-fila").hidden = !despegue;
      if (despegue) {
        const sel = $("aer-base");
        limpiar(sel);
        bases.forEach((b) => { const o = el("option", "", b.nombre); o.value = String(b.id); sel.appendChild(o); });
        if (modeloInicial && bases.some((b) => b.id === modeloInicial.base)) sel.value = String(modeloInicial.base);
        $("aer-indicativo").value = "";
      }
      marcar((modeloInicial && modeloInicial.modelo) || null);
      if (!$("dlg-aeronaves").open) $("dlg-aeronaves").showModal();
    }

    /** Alumno: elegir modelo, tamano, indicativo y base de origen, y emitir la orden de despegue. */
    function abrirDespegue(baseId) {
      const datos = ctx.datos();
      if (!datos || !ctx.usuario()) return;
      const bases = basesAereasPropias(datos.unidades, ctx.usuario().rol);
      if (!bases.length) return ctx.toast("Su bando no tiene una base aérea activa desde la cual despegar.");
      abrirDialogo({
        tipo: "despegue", titulo: "Enviar grupo de caza",
        ayuda: "Elija la aeronave, cuántas salen y desde qué base. El grupo aparece al resolverse el turno.",
        textoConfirmar: "Enviar a despegar", bases,
        modeloInicial: { modelo: null, base: baseId }, cantidadInicial: 4,
        alConfirmar: async () => {
          const cuerpo = {
            unidad_id: parseInt($("aer-base").value, 10), tipo: "despegar", modelo: elegido,
            aeronaves: parseInt($("aer-cantidad").value, 10), indicativo: $("aer-indicativo").value.trim(),
          };
          await ctx.api("POST", ctx.rutaEsc("/ordenes"), cuerpo);
          ctx.toast("Grupo listo para despegar al resolverse el turno", true);
        },
      });
    }

    /** Instructor: elegir un modelo (y tamano) para la unidad que va a ubicar; devuelve {modelo, aeronaves} o null. */
    function elegirModelo(actual) {
      return new Promise((resolver) => {
        let resuelto = false;
        const fin = (v) => { if (!resuelto) { resuelto = true; resolver(v); } };
        $("dlg-aeronaves").addEventListener("close", () => fin(null), { once: true });
        abrirDialogo({
          tipo: "modelo", titulo: "Elegir aeronave",
          ayuda: "El modelo define la foto, la velocidad, el alcance, la detección, la autonomía y la efectividad de la unidad.",
          textoConfirmar: "Usar este modelo", modeloInicial: { modelo: actual && actual.modelo }, cantidadInicial: (actual && actual.aeronaves) || 4,
          alConfirmar: async () => fin({ modelo: elegido, aeronaves: parseInt($("aer-cantidad").value, 10) }),
        });
      });
    }

    function conectarDialogo() {
      $("aer-cantidad").addEventListener("change", actualizarResumen);
      $("aer-base").addEventListener("change", actualizarResumen);
      $("aer-cancelar").addEventListener("click", () => $("dlg-aeronaves").close());
      $("aer-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!modoActual || !elegido) return;
        const { alConfirmar } = modoActual;
        try {
          await alConfirmar();
          $("dlg-aeronaves").close();
        } catch (_) { /* el toast del error ya se mostro; el dialogo sigue abierto para corregir */ }
      });
    }

    // ------------------------------------------------------------------ capa: bases aereas de Venezuela
    function iconoBase() {
      return L.divIcon({
        className: "base-ven", iconSize: [26, 26], iconAnchor: [13, 13],
        html: `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="${AVION}"/></svg>`,
      });
    }

    function popupBase(p, lat, lon) {
      const div = el("div", "popup-base");
      div.append(el("b", "", p.nombre));
      const filas = [
        ["OACI", p.icao], ["Ubicación", `${p.ciudad}, ${p.estado}`], ["Elevación", `${p.elevacion_m} m`],
        ["Coordenadas", `${lat.toFixed(4)}, ${lon.toFixed(4)}`],
      ];
      const dl = el("dl", "specs");
      for (const [k, v] of filas) { const d = el("div"); d.append(el("dt", "", k), el("dd", "", v)); dl.appendChild(d); }
      div.appendChild(dl);
      const datos = ctx.datos();
      const usuario = ctx.usuario();
      const existente = datos ? baseEnEscenario(datos.unidades, lat, lon) : null;
      if (existente) {
        div.appendChild(el("p", "nota", `En el ejercicio: ${existente.nombre} (bando ${existente.bando}).`));
      } else if (usuario && usuario.rol === "instructor" && ctx.escenarioId()) {
        div.appendChild(el("p", "ayuda", "Capa de referencia. Colóquela como base del ejercicio:"));
        const fila = el("div", "fila");
        for (const bando of ["azul", "rojo"]) {
          const b = el("button", `mini ${bando}`, `Base ${bando === "azul" ? "Azul" : "Roja"}`);
          b.type = "button";
          b.addEventListener("click", async () => {
            try {
              await ctx.api("POST", ctx.rutaEsc("/unidades"), { nombre: `BA ${nombreCortoBase(p.nombre)}`, bando, clase: "base_aerea", lat, lon });
              ctx.map().closePopup();
              ctx.toast(`${p.icao} colocada como base ${bando === "azul" ? "azul" : "roja"}.`, true);
            } catch (_) { /* toast ya mostrado */ }
          });
          fila.appendChild(b);
        }
        div.appendChild(fila);
      } else {
        div.appendChild(el("p", "ayuda", "Capa de referencia: solo forma parte del ejercicio si el instructor la coloca."));
      }
      return div;
    }

    function cargarBases() {
      fetch("/static/geo/bases_aereas.geojson").then((r) => r.json()).then((g) => {
        for (const f of g.features) {
          const [lon, lat] = f.geometry.coordinates;
          const p = f.properties;
          const m = L.marker([lat, lon], { icon: iconoBase(), keyboard: false, riseOnHover: true });
          const rotulo = el("span", "", `${p.icao} · ${p.ciudad.replace(/\s*\(.*\)$/, "")}`);
          m.bindTooltip(rotulo, { permanent: true, direction: "right", offset: [12, 0], className: "nombre-base" });
          m.bindPopup(() => popupBase(p, lat, lon), { minWidth: 230, autoPanPaddingTopLeft: [20, 60], autoPanPaddingBottomRight: [290, 20] });
          m.addTo(ctx.capa);
        }
      }).catch(() => { /* sin la capa el ejercicio sigue funcionando */ });
    }

    function conectar() {
      conectarDialogo();
      cargarBases();
    }

    return { conectar, abrirDespegue, elegirModelo };
  }

  raiz.Aviacion = { crear };
})(window);
