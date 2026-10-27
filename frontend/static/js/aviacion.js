/* Aviacion: selector de aeronaves con fotos (F-16, Su-30), envio de grupos de caza desde una base aerea propia
 * y capa de referencia con las bases aereas y aeropuertos de toda America (Venezuela en detalle). */
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
    const topes = () => (ctx.catalogo() && ctx.catalogo().aeronaves) || { max_grupo: 8, max_bando: 24, max_drones: 16 };

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
      foto.alt = m.nombre;
      foto.loading = "lazy";
      const cuerpo = el("div", "cuerpo");
      cuerpo.append(el("h4", "", m.nombre), el("small", "", `${m.fabricante} · ${m.pais}`), el("p", "funcion", m.funcion));
      const specs = el("dl", "specs");
      const f = m.ficha;
      for (const [k, v] of [
        ["Velocidad", f ? `${f.crucero_kt} kt en ruta` : `${m.velocidad_kmh} km/h`],
        ["Alcance de armas", `${Math.round(m.alcance_km / 1.852)} NM`],
        ["Detección", `${Math.round(m.deteccion_km / 1.852)} NM`],
        [f ? "Radio de acción" : "Autonomía", f ? `${f.radio_nm} NM` : `${m.autonomia_km} km`],
        ...(f ? [["Despegue", f.despegue_m ? `${f.despegue_m} m de pista` : "vertical"], ["Roles", f.roles.join(" · ")]] : []),
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
      credito.append(m.foto.endsWith(".svg") ? "Imagen: " : c.obra ? `Foto de referencia (${c.obra}): ` : "Foto: ");
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

    /** Base elegida en el dialogo de despegue (null al elegir modelo para el instructor). */
    function baseElegida() {
      const datos = ctx.datos();
      return modoActual && modoActual.tipo === "despegue" && datos
        ? datos.unidades.find((u) => String(u.id) === $("aer-base").value) || null : null;
    }

    /** Tarjetas de los modelos que pueden salir de la base elegida (un portaaviones solo lanza embarcables). */
    function llenarTarjetas() {
      const tarjetas = $("aer-tarjetas");
      limpiar(tarjetas);
      const base = baseElegida();
      const despegue = modoActual && modoActual.tipo === "despegue";
      const todos = modelos().filter((m) => (despegue ? Logica.modeloDespegaDe(m, base) : Logica.esAeronave(m)));
      llenarFiltroClase(todos);
      const posibles = Logica.filtrarModelos(todos, $("aer-buscar").value, $("aer-filtro-clase").value);
      const lista = despegue ? posibles.filter((m) => Logica.entraEnPista(m, base)) : posibles;
      const cortos = despegue ? posibles.filter((m) => !Logica.entraEnPista(m, base)) : [];
      lista.forEach((m) => tarjetas.appendChild(tarjeta(m)));
      if (elegido && !lista.some((m) => m.id === elegido)) elegido = null;
      $("aer-nota-base").hidden = !Logica.esPortaaviones(base);
      const nota = $("aer-nota-pista");
      if (nota) {
        nota.hidden = !cortos.length;
        nota.textContent = cortos.length
          ? `La pista útil de ${base.nombre} (${Math.round(base.pista_util_m)} m) no alcanza para despegar: ${cortos.map((m) => `${m.corto} (${m.ficha.despegue_m} m)`).join(", ")}.`
          : "";
      }
    }

    /** Las clases de aeronave presentes en la lista (para filtrar: cazas, ataque, helicopteros, drones...). */
    function llenarFiltroClase(todos) {
      const sel = $("aer-filtro-clase");
      const previo = sel.value;
      const clases = (ctx.catalogo() && ctx.catalogo().clases) || [];
      const presentes = clases.filter((c) => todos.some((m) => m.clase === c.id));
      limpiar(sel);
      sel.appendChild(Object.assign(el("option", "", `Todas (${todos.length})`), { value: "" }));
      presentes.forEach((c) => sel.appendChild(Object.assign(el("option", "", `${c.nombre} (${todos.filter((m) => m.clase === c.id).length})`), { value: c.id })));
      sel.value = presentes.some((c) => c.id === previo) ? previo : "";
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
      const cat = ctx.catalogo();
      const dron = Logica.modeloEsDron(m.id, cat);
      const tope = dron ? (topes().max_drones || 16) : topes().max_bando;
      const en = aeronavesComprometidas(datos.unidades, datos.ordenes, rol, dron, cat);
      const base = datos.unidades.find((u) => String(u.id) === $("aer-base").value);
      const previa = datos.ordenes.find((o) => o.estado === "pendiente" && base && o.unidad_id === base.id && o.tipo === "despegar");
      const detPrevia = previa ? Logica.detalleDespegue(previa) : null;
      const descontar = detPrevia && Logica.modeloEsDron(detPrevia.modelo, cat) === dron ? (detPrevia.aeronaves || 0) : 0;
      const total = en - descontar + n;
      const excede = total > tope;
      $("aer-resumen").textContent = `${m.corto} ×${n} despega de ${base ? base.nombre : "la base"} en el acto y espera órdenes sobre ella; `
        + `puede recibir órdenes de inmediato. ${dron ? "Drones" : "Aeronaves tripuladas"} del bando: ${total} de ${tope}${excede ? " (excede el tope)" : ""}.`;
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
      $("aer-buscar").value = "";
      $("aer-filtro-clase").value = "";
      llenarTarjetas();
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
        tipo: "despegue", titulo: "Enviar aeronaves o drones",
        ayuda: "Elija el caza, el dron o el avión de guerra electrónica, cuántos salen y desde qué base. El grupo despega en el acto.",
        textoConfirmar: "Enviar a despegar", bases,
        modeloInicial: { modelo: null, base: baseId }, cantidadInicial: 4,
        alConfirmar: async () => {
          const cuerpo = {
            unidad_id: parseInt($("aer-base").value, 10), tipo: "despegar", modelo: elegido,
            aeronaves: parseInt($("aer-cantidad").value, 10), indicativo: $("aer-indicativo").value.trim(),
          };
          await ctx.api("POST", ctx.rutaEsc("/ordenes"), cuerpo);
          ctx.toast("El grupo despegó y espera órdenes sobre la base", true);
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
      $("aer-base").addEventListener("change", () => { llenarTarjetas(); marcar(elegido); });
      $("aer-buscar").addEventListener("input", () => { llenarTarjetas(); marcar(elegido); });
      $("aer-filtro-clase").addEventListener("change", () => { llenarTarjetas(); marcar(elegido); });
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

    // ------------------------------------------------------------------ capa: bases aereas y aerodromos de America
    // color fijo del icono para Venezuela y los vecinos del area de detalle (como siempre); el resto toma el color
    // oscuro de la bandera de su nacion (catalogo /api/naciones) o un gris neutro (territorios sin nacion)
    const COLOR_PAIS = { Venezuela: "#14213D", Colombia: "#8a6d00", Brasil: "#1f6b3a", Guyana: "#5b3a8a", "Trinidad y Tobago": "#8a1f2b" };
    const colorPais = (p) => Logica.colorAerodromo(p.pais, ctx.naciones ? ctx.naciones() : [], COLOR_PAIS);
    function iconoBase(p) {
      const aeropuerto = p.tipo === "aeropuerto";
      return L.divIcon({
        className: `base-ven${aeropuerto ? " aeropuerto" : ""}`, iconSize: [26, 26], iconAnchor: [13, 13],
        html: `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" style="background:${colorPais(p)}"><path d="${AVION}"/></svg>`,
      });
    }
    const ORIGEN = { curado: "Datos verificados (Wikipedia / OurAirports)", ourairports: "OurAirports (dominio público)" };

    function popupBase(p, lat, lon) {
      const div = el("div", "popup-base");
      div.append(el("b", "", p.nombre));
      const filas = [
        ["OACI", p.icao], ["País", p.pais || "Venezuela"], ["Tipo", p.tipo === "aeropuerto" ? "Aeropuerto (uso civil; utilizable como base en el ejercicio)" : "Base aérea"],
        ["Ubicación", [p.ciudad, p.estado].filter(Boolean).join(", ")],
        ...(p.elevacion_m !== null && p.elevacion_m !== undefined ? [["Elevación", `${p.elevacion_m} m`]] : []),
        ["Coordenadas", `${lat.toFixed(4)}, ${lon.toFixed(4)}`],
        ["Origen", ORIGEN[p.origen] || ORIGEN.curado],
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

    const OPCIONES_POPUP = { minWidth: 230, autoPanPaddingTopLeft: [20, 60], autoPanPaddingBottomRight: [290, 20] };
    const rotuloDe = (p) => `${p.icao} · ${(p.ciudad || p.nombre).replace(/\s*\(.*\)$/, "")}`;

    /** Marcador con icono y rotulo permanente (de cerca), igual para todos los paises. */
    function marcadorIcono(p, lat, lon) {
      const m = L.marker([lat, lon], { icon: iconoBase(p), keyboard: false, riseOnHover: true });
      m.bindTooltip(el("span", "", rotuloDe(p)), { permanent: true, direction: "right", offset: [12, 0], className: "nombre-base" });
      m.bindPopup(() => popupBase(p, lat, lon), OPCIONES_POPUP);
      return m;
    }

    /** Punto liviano en canvas (de lejos): las bases militares mas grandes que los aeropuertos; rotulo al pasar el raton. */
    function marcadorPunto(p, lat, lon, lienzo) {
      const militar = p.tipo !== "aeropuerto";
      const m = L.circleMarker([lat, lon], {
        renderer: lienzo, radius: militar ? 5 : 3.5, color: "#fff", weight: militar ? 1.5 : 1, fillColor: colorPais(p), fillOpacity: 0.95,
        pane: "markerPane", interactive: true,
      });
      m.bindTooltip(rotuloDe(p), { direction: "right", offset: [8, 0], className: "nombre-base" });
      m.bindPopup(() => popupBase(p, lat, lon), OPCIONES_POPUP);
      return m;
    }

    /**
     * Carga la capa y la redibuja segun el zoom y la vista (Logica.modoAerodromo): de lejos, puntos en canvas de las
     * bases militares (y desde el zoom 6 tambien de los aeropuertos); de cerca, solo los aerodromos que caen en
     * pantalla (mas un margen) con icono y rotulo, para que los ~1300 puntos del continente no frenen el mapa.
     */
    function cargarBases() {
      const mapa = ctx.map();
      const lienzo = L.canvas({ padding: 0.5 });
      let rasgos = [];
      let modoDibujado = null; // "punto:<zoom>" | "icono:<limites>"
      const puntos = L.layerGroup();
      const iconos = L.layerGroup();

      function redibujar() {
        if (!rasgos.length || !mapa.hasLayer(ctx.capa)) return;
        const zoom = mapa.getZoom();
        const deCerca = zoom >= Logica.ZOOM_ICONOS_AERODROMO;
        const limites = deCerca ? mapa.getBounds().pad(0.3) : null;
        const clave = deCerca ? `icono:${limites.toBBoxString()}` : `punto:${zoom}`;
        if (clave === modoDibujado) return;
        modoDibujado = clave;
        puntos.clearLayers();
        iconos.clearLayers();
        for (const { p, lat, lon } of rasgos) {
          const modo = Logica.modoAerodromo(p, zoom);
          if (modo === "icono" && limites.contains([lat, lon])) marcadorIcono(p, lat, lon).addTo(iconos);
          else if (modo === "punto") marcadorPunto(p, lat, lon, lienzo).addTo(puntos);
        }
      }

      puntos.addTo(ctx.capa);
      iconos.addTo(ctx.capa);
      mapa.on("zoomend moveend", redibujar);
      ctx.capa.on("add", () => setTimeout(redibujar, 0));
      fetch("/static/geo/bases_aereas.geojson").then((r) => r.json()).then((g) => {
        rasgos = g.features.map((f) => ({ p: f.properties, lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0] }));
        redibujar();
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
