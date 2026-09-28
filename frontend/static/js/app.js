(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const { esBando, pct } = Logica;
  const COLOR = { azul: "#3A86FF", rojo: "#EF233C" };
  const LIMITES = [[0.6, -73.4], [12.4, -59.6]]; // area cubierta por los tiles de Venezuela
  const NOMBRE_TIPO = { terrestre: "Terrestres", aerea: "Aéreas", naval: "Navales", base: "Bases y logística" };
  const ETIQUETA_FASE = { decision: "Decisión", resolucion: "Resolución" };
  const MAX_ALERTAS = 40;

  const app = {
    usuario: null, escenarioId: null, ws: null, wsAlive: null, data: null, recibidoEn: 0,
    porId: new Map(), contactosPorId: new Map(),
    modoAgregar: false, waypoints: [], modoOrden: "mover", unidadOrden: null, seleccion: null,
    markers: new Map(), flechas: [], encuadrado: false, map: null, capas: {}, capaActiva: {},
    catalogo: null, vista: "completa", informe: null, usuariosLista: [],
    temporizadorPreview: null, relojTimer: null,
    memoria: Logica.memoriaVacia(), alertas: [], alertasSinLeer: 0,
    tamSimbolo: 26, obraSitio: null, dibujando: false, urlInicial: Videowall.parametrosDeUrl(),
    graficos: null, chat: null, videowall: null, aviacion: null,
    modeloUnidad: null, baseSeleccionada: null,
  };

  // ---------- utilidades ----------
  let toastTimer = null;
  function toast(msg, ok = false) {
    const t = $("toast");
    t.textContent = msg;
    t.className = ok ? "ok" : "";
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 4500);
  }

  async function api(metodo, ruta, cuerpo, silencioso = false) {
    const resp = await fetch(ruta, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
      credentials: "same-origin",
    });
    if (resp.status === 401 && !ruta.startsWith("/api/auth/")) {
      mostrarLogin();
      throw new Error("Sesión expirada");
    }
    if (!resp.ok) {
      let detalle = resp.statusText;
      try {
        const j = await resp.json();
        detalle = typeof j.detail === "string" ? j.detail : "Datos inválidos";
      } catch (_) { /* sin cuerpo */ }
      if (!silencioso) toast(detalle);
      throw new Error(detalle);
    }
    return resp.json();
  }
  const enSilencio = (p) => p.catch(() => {});

  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const escapar = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  function limpiar(el) { while (el.firstChild) el.removeChild(el.firstChild); }

  function boton(texto, onclick, clase = "mini secundario") {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = texto;
    b.className = clase;
    b.addEventListener("click", onclick);
    return b;
  }

  function llenarSelect(sel, opciones) {
    const previo = sel.value;
    limpiar(sel);
    for (const [valor, texto] of opciones) {
      const o = document.createElement("option");
      o.value = valor;
      o.textContent = texto;
      sel.appendChild(o);
    }
    if ([...sel.options].some((o) => o.value === previo)) sel.value = previo;
  }

  const rutaEsc = (sufijo = "") => `/api/escenarios/${app.escenarioId}${sufijo}`;
  const esInstructor = () => !!app.usuario && app.usuario.rol === "instructor";
  const esAlumno = () => !!app.usuario && esBando(app.usuario.rol);
  /** Bando cuya perspectiva se muestra (null = vista completa). */
  const bandoVista = () => {
    const v = app.data ? app.data.vista : null;
    return esBando(v) ? v : esAlumno() ? app.usuario.rol : null;
  };
  const horaDelTurno = (turno) => {
    const esc = app.data && app.data.escenario;
    return Logica.textoHora(Logica.horaSimulada(esc ? esc.hora_inicio_min : 360, turno));
  };

  // ---------- sesion ----------
  function mostrarLogin() {
    cerrarWs();
    clearInterval(app.relojTimer);
    if (app.informe) app.informe.cerrar();
    app.usuario = null;
    $("app").hidden = true;
    $("login").hidden = false;
    $("l-pass").value = "";
    $("l-user").focus();
  }

  async function arrancar() {
    try {
      app.usuario = await api("GET", "/api/auth/yo", undefined, true);
    } catch (_) {
      return mostrarLogin();
    }
    $("login").hidden = true;
    $("app").hidden = false;
    aplicarRol();
    initMapa();
    iniciarModulos();
    app.map.invalidateSize();
    app.informe = app.informe || Informe.crear({
      map: app.map, api, toast, escenarioId: () => app.escenarioId, crearIcono: (u) => iconoUnidad(u),
      alActivar: () => { limpiarCapasVivas(); },
      alDesactivar: () => { if (app.data) render(app.data); },
    });
    try { app.catalogo = await api("GET", "/api/catalogo"); prepararCatalogo(); } catch (_) { /* sin catalogo */ }
    clearInterval(app.relojTimer);
    app.relojTimer = setInterval(actualizarReloj, 1000);
    await cargarEscenarios();
    if (esInstructor()) enSilencio(cargarUsuarios());
    aplicarParametrosUrl();
  }

  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("l-error").textContent = "";
    try {
      await api("POST", "/api/auth/login", { username: $("l-user").value.trim(), password: $("l-pass").value }, true);
      arrancar();
    } catch (err) {
      $("l-error").textContent = err.message;
    }
  });

  $("btn-logout").addEventListener("click", async () => {
    try { await api("POST", "/api/auth/logout", undefined, true); } catch (_) { /* ya cerrada */ }
    $("menu-perfil").hidden = true;
    mostrarLogin();
  });

  $("btn-perfil").addEventListener("click", (e) => {
    e.stopPropagation();
    const m = $("menu-perfil");
    m.hidden = !m.hidden;
    $("btn-perfil").setAttribute("aria-expanded", String(!m.hidden));
  });
  document.addEventListener("click", (e) => {
    if (!$("menu-perfil").hidden && !e.target.closest(".perfil-wrap")) { $("menu-perfil").hidden = true; $("btn-perfil").setAttribute("aria-expanded", "false"); }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("menu-perfil").hidden = true; $("btn-perfil").setAttribute("aria-expanded", "false"); } });

  function aplicarRol() {
    const rol = app.usuario.rol;
    $("mp-nombre").textContent = app.usuario.username;
    $("mp-rol").textContent = rol;
    document.querySelectorAll(".solo-instructor").forEach((e) => (e.hidden = rol !== "instructor"));
    document.querySelectorAll(".solo-alumno").forEach((e) => (e.hidden = !esBando(rol)));
    document.querySelectorAll(".solo-control").forEach((e) => (e.hidden = !(rol === "instructor" || rol === "observador")));
    document.querySelectorAll(".solo-dibuja").forEach((e) => (e.hidden = !(rol === "instructor" || esBando(rol))));
    if (app.chat) app.chat.configurarRol();
    activarPestana("fuerzas");
    app.waypoints = [];
    dibujarWaypoints();
    // la niebla de guerra visual se activa por defecto para quien no ve todo
    const niebla = document.querySelector('[data-capa="niebla"]');
    niebla.checked = esBando(rol);
    if (app.map) alternarCapa("niebla", niebla.checked);
  }

  function activarPestana(nombre) {
    document.querySelectorAll(".pestanas button").forEach((b) => b.classList.toggle("activa", b.dataset.pestana === nombre));
    $("pest-fuerzas").hidden = nombre !== "fuerzas";
    $("pest-consola").hidden = nombre !== "consola" || !esInstructor();
  }
  document.querySelectorAll(".pestanas button").forEach((b) => b.addEventListener("click", () => activarPestana(b.dataset.pestana)));

  // ---------- catalogo de unidades ----------
  function prepararCatalogo() {
    const cat = app.catalogo;
    const sel = $("u-clase");
    limpiar(sel);
    for (const tipo of Object.keys(NOMBRE_TIPO)) {
      const grupo = document.createElement("optgroup");
      grupo.label = NOMBRE_TIPO[tipo];
      for (const c of cat.clases.filter((x) => x.tipo === tipo)) {
        const o = document.createElement("option");
        o.value = c.id;
        o.textContent = c.nombre;
        grupo.appendChild(o);
      }
      sel.appendChild(grupo);
    }
    llenarSelect($("u-escalon"), [["", "Escalón: el de la clase"], ...cat.escalones.map((e) => [e, e])]);
    aplicarDefectosClase();
  }

  const modeloPorId = (id) => (app.catalogo && app.catalogo.modelos ? app.catalogo.modelos.find((m) => m.id === id) : null) || null;

  function aplicarDefectosClase() {
    const c = app.catalogo && app.catalogo.clases.find((x) => x.id === $("u-clase").value);
    if (!c) return;
    const esCaza = c.id === "caza";
    if (!esCaza) app.modeloUnidad = null;
    $("u-aeronave-fila").hidden = !esCaza;
    const ref = (esCaza && app.modeloUnidad && modeloPorId(app.modeloUnidad.modelo)) || c;
    $("u-velocidad").value = ref.velocidad_kmh;
    $("u-alcance").value = ref.alcance_km;
    $("u-deteccion").value = ref.deteccion_km;
    $("u-autonomia").value = ref.autonomia_km || 1;
    $("u-velocidad").disabled = c.tipo === "base";
    $("u-autonomia").disabled = c.tipo === "base";
    actualizarFilaModelo();
  }
  $("u-clase").addEventListener("change", aplicarDefectosClase);

  function actualizarFilaModelo() {
    const m = app.modeloUnidad ? modeloPorId(app.modeloUnidad.modelo) : null;
    const foto = $("u-modelo-foto");
    foto.hidden = !m;
    if (m) { foto.src = m.foto; foto.alt = m.nombre; }
    $("u-modelo-nombre").textContent = m ? m.nombre : "Caza genérico";
    $("u-modelo-grupo").textContent = m ? `Grupo de ${app.modeloUnidad.aeronaves} aeronave${app.modeloUnidad.aeronaves === 1 ? "" : "s"}` : "Sin modelo: valores de la clase";
  }
  $("btn-elegir-modelo").addEventListener("click", async () => {
    const elegido = await app.aviacion.elegirModelo(app.modeloUnidad);
    if (elegido) { app.modeloUnidad = elegido; aplicarDefectosClase(); }
  });

  // ---------- mapa (100% offline) ----------
  function initMapa() {
    if (app.map) return;
    const bounds = L.latLngBounds(LIMITES);
    const map = L.map("map", { zoomControl: false, attributionControl: false, minZoom: 5, maxZoom: 11, maxBounds: bounds.pad(0.1), maxBoundsViscosity: 0.85 });
    map.fitBounds(bounds);
    app.map = map;
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control.attribution({ position: "bottomleft", prefix: false })
      .addAttribution("Relieve: SRTM/GMTED (AWS Terrain Tiles) · Cobertura: ESA WorldCover · Vectores: Natural Earth").addTo(map);

    L.tileLayer("/static/tiles/{z}/{x}/{y}.jpg", { minZoom: 5, maxNativeZoom: 9, maxZoom: 11, bounds }).addTo(map);

    const c = app.capas;
    c.referencias = L.layerGroup().addTo(map);
    c.bases_ven = L.layerGroup().addTo(map);
    const fronteras = L.geoJSON(null, { style: { color: "#1a1a1a", weight: 2.5, fill: false } }).addTo(c.referencias);
    const estados = L.geoJSON(null, { style: { color: "#333", weight: 1, dashArray: "4 4", fill: false, opacity: 0.7 } }).addTo(c.referencias);
    const rios = L.geoJSON(null, { style: { color: "#2f6fb0", weight: 1.5 } }).addTo(c.referencias);
    const lagos = L.geoJSON(null, { style: { color: "#2f6fb0", weight: 1, fillColor: "#78aacd", fillOpacity: 0.7 } }).addTo(c.referencias);
    const lugares = L.geoJSON(null, {
      pointToLayer: (f, ll) => {
        const m = L.circleMarker(ll, { radius: 3, color: "#222", weight: 1, fillColor: "#fff", fillOpacity: 1 });
        m.bindTooltip(f.properties.name || "", {
          permanent: (f.properties.pop || 0) >= 400000, direction: "right", className: "nombre-lugar", offset: [4, 0],
        });
        return m;
      },
    }).addTo(c.referencias);
    for (const [archivo, capa] of [["fronteras", fronteras], ["estados", estados], ["rios", rios], ["lagos", lagos], ["lugares", lugares]]) {
      fetch(`/static/geo/${archivo}.geojson`).then((r) => r.json()).then((g) => capa.addData(g)).catch(() => {});
    }

    c.niebla = L.layerGroup();
    c.cobertura = L.layerGroup();
    c.contactos = L.layerGroup().addTo(map);
    c.unidades = L.layerGroup().addTo(map);
    c.ordenes = L.layerGroup().addTo(map);
    c.seleccion = L.layerGroup().addTo(map);
    c.preview = L.layerGroup().addTo(map);
    c.waypoints = L.layerGroup().addTo(map);
    c.obras = L.layerGroup().addTo(map);
    app.capaActiva = { terreno: true, cobertura: false, niebla: esBando(app.usuario.rol), unidades: true, contactos: true, referencias: true, graficos: true, bases_ven: true };
    if (app.capaActiva.niebla) c.niebla.addTo(map);

    let pendiente = null;
    map.on("mousemove", (e) => {
      const txt = `${e.latlng.lat.toFixed(3)}, ${e.latlng.lng.toFixed(3)}`;
      $("coords").textContent = txt;
      clearTimeout(pendiente);
      pendiente = setTimeout(async () => {
        try {
          const r = await api("GET", `/api/terreno/clase?lat=${e.latlng.lat}&lon=${e.latlng.lng}`, undefined, true);
          $("coords").textContent = `${txt} · ${r.clase}`;
        } catch (_) { /* fuera de linea o sin sesion */ }
      }, 250);
    });
    map.on("click", alClickMapa);
    map.on("zoomend", () => app.flechas.forEach((f) => f.actualizar()));
  }

  // capas alternables desde la tarjeta "Capas"
  function alternarCapa(nombre, encendida) {
    app.capaActiva[nombre] = encendida;
    const g = app.capas;
    const poner = (capa, on) => (on ? capa.addTo(app.map) : app.map.removeLayer(capa));
    if (nombre === "terreno") $("zona-mapa").classList.toggle("sin-terreno", !encendida);
    else if (nombre === "unidades") { poner(g.unidades, encendida); poner(g.ordenes, encendida); poner(g.obras, encendida); if (encendida) app.flechas.forEach((f) => f.actualizar()); }
    else if (nombre === "graficos") poner(app.graficos.capa, encendida);
    else if (g[nombre]) poner(g[nombre], encendida);
  }
  document.querySelectorAll("[data-capa]").forEach((chk) => chk.addEventListener("change", () => alternarCapa(chk.dataset.capa, chk.checked)));

  async function alClickMapa(e) {
    if (app.dibujando || (app.informe && app.informe.activo())) return;
    const { lat, lng } = e.latlng;
    if (esInstructor() && app.modoAgregar) {
      const nombre = $("u-nombre").value.trim();
      if (!nombre) return toast("Ingrese un nombre para la unidad.");
      const num = (id) => { const v = parseFloat($(id).value); return Number.isNaN(v) ? undefined : v; };
      try {
        await api("POST", rutaEsc("/unidades"), {
          nombre, bando: $("u-bando").value, clase: $("u-clase").value, echelon: $("u-escalon").value,
          modelo: app.modeloUnidad ? app.modeloUnidad.modelo : undefined,
          aeronaves: app.modeloUnidad ? app.modeloUnidad.aeronaves : undefined,
          lat, lon: lng, fuerza: num("u-fuerza") ?? 100, velocidad_kmh: num("u-velocidad"),
          alcance_km: num("u-alcance"), deteccion_km: num("u-deteccion"), autonomia_km: num("u-autonomia"),
        });
        app.modoAgregar = false;
        $("btn-modo-agregar").textContent = "Ubicar en mapa";
      } catch (_) { /* toast ya mostrado */ }
      return;
    }
    if (esAlumno() && app.modoOrden === "construir" && app.unidadOrden) {
      app.obraSitio = [lat, lng];
      dibujarSitioObra();
      return;
    }
    if (esAlumno() && app.modoOrden === "mover" && app.unidadOrden) {
      app.waypoints.push([lat, lng]);
      dibujarWaypoints();
      pedirPreview();
    }
  }

  function dibujarWaypoints() {
    const g = app.capas.waypoints;
    if (g) {
      g.clearLayers();
      app.waypoints.forEach((wp, i) => L.circleMarker(wp, { radius: 5, color: "#fff", fillColor: "#3A86FF", fillOpacity: 1 }).bindTooltip(`W${i + 1}`).addTo(g));
      if (app.waypoints.length > 1) L.polyline(app.waypoints, { dashArray: "5 5", color: "#fff" }).addTo(g);
    }
    $("o-waypoints").textContent = app.waypoints.length
      ? app.waypoints.map((w, i) => `W${i + 1}: ${w[0].toFixed(3)}, ${w[1].toFixed(3)}`).join(" | ")
      : "(sin waypoints)";
    if (!app.waypoints.length) {
      if (app.capas.preview) app.capas.preview.clearLayers();
      $("o-preview").textContent = "";
    }
  }

  // Previsualizacion: donde terminaria la unidad este turno con los waypoints marcados.
  function pedirPreview() {
    clearTimeout(app.temporizadorPreview);
    app.temporizadorPreview = setTimeout(async () => {
      if (!app.unidadOrden || !app.waypoints.length || app.modoOrden !== "mover") return;
      try {
        const p = await api("POST", rutaEsc("/ordenes/previsualizar"), { unidad_id: app.unidadOrden, waypoints: app.waypoints }, true);
        const g = app.capas.preview;
        g.clearLayers();
        L.polyline(p.ruta, { color: "#81d4fa", weight: 4, opacity: 0.9, interactive: false }).addTo(g);
        L.circleMarker(p.destino, { radius: 7, color: "#81d4fa", fillColor: "#0288d1", fillOpacity: 0.9 }).bindTooltip("Posición al final del turno").addTo(g);
        $("o-preview").textContent = `${p.llega ? "Llega al último waypoint" : "No llega al destino este turno"}: recorre ${p.km} km, combustible restante ${p.combustible_restante}%. ${p.nota}`;
      } catch (_) { /* p. ej. fase de decision cerrada */ }
    }, 250);
  }

  // ---------- simbologia sobre el mapa ----------
  function simboloSvg(sidc, size) {
    return new ms.Symbol((sidc || "SUGP").padEnd(15, "-"), { size }).asSVG();
  }

  const rotuloModelo = (u) => Logica.rotuloModelo(u, app.catalogo && app.catalogo.modelos);

  function iconoUnidad(u, clases = "") {
    const sym = new ms.Symbol((u.sidc || "SUGP").padEnd(15, "-"), { size: app.tamSimbolo });
    const tam = sym.getSize();
    const anc = sym.getAnchor();
    const sub = rotuloModelo(u);
    return L.divIcon({
      className: `marca ${clases}`,
      html: `<div class="cuerpo">${sym.asSVG()}<div class="rotulo">${escapar(u.nombre || "")}</div>`
        + (sub ? `<div class="rotulo modelo">${escapar(sub)}</div>` : "") + "</div>",
      iconSize: [110, tam.height + (sub ? 30 : 16)],
      iconAnchor: [55 + (anc.x - tam.width / 2), anc.y],
    });
  }

  function tooltipUnidad(u) {
    const el = document.createElement("span");
    const modelo = Logica.modeloDe(u, app.catalogo && app.catalogo.modelos);
    const grupo = modelo ? ` · ${rotuloModelo(u)}` : "";
    el.textContent = `${u.nombre} (${u.clase || u.tipo}${grupo}, ${u.terreno}) fuerza ${pct(u.fuerza)}`;
    if (!modelo) return el;
    const caja = document.createElement("div");
    caja.className = "tip-modelo";
    const foto = document.createElement("img");
    foto.src = modelo.foto;
    foto.alt = modelo.nombre;
    foto.width = 132;
    caja.append(foto, el);
    return caja;
  }

  function limpiarCapasVivas() {
    for (const m of app.markers.values()) app.capas.unidades.removeLayer(m);
    app.markers.clear();
    for (const g of ["contactos", "cobertura", "niebla", "ordenes", "seleccion", "preview", "obras"]) app.capas[g].clearLayers();
    app.flechas = [];
  }

  function anillo(lat, lon, km, pasos = 56) {
    const dLat = km / 111.32;
    const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180));
    return Array.from({ length: pasos }, (_, i) => {
      const a = (i / pasos) * 2 * Math.PI;
      return [lat + dLat * Math.sin(a), lon + dLon * Math.cos(a)];
    });
  }

  function dibujarUnidades(unidades) {
    const vivas = new Set();
    for (const u of unidades) {
      if (u.estado === "destruida") continue;
      vivas.add(u.id);
      const vista = bandoVista();
      const enemiga = vista ? u.bando !== vista : u.bando === "rojo";
      const clases = enemiga ? "enemigo" : "amigo";
      let m = app.markers.get(u.id);
      const firma = `${u.sidc}|${u.nombre}|${clases}|${app.tamSimbolo}|${rotuloModelo(u)}`;
      if (m && m._firma !== firma) { app.capas.unidades.removeLayer(m); m = null; }
      if (!m) {
        m = L.marker([u.lat, u.lon], { icon: iconoUnidad(u, clases), keyboard: false }).addTo(app.capas.unidades);
        m._firma = firma;
        m.on("click", () => seleccionar(u.id, "mapa"));
        app.markers.set(u.id, m);
      } else {
        m.setLatLng([u.lat, u.lon]);
      }
      m.unbindTooltip();
      m.bindTooltip(tooltipUnidad(u), { direction: "top", offset: [0, -14] });
    }
    for (const [id, m] of app.markers) {
      if (!vivas.has(id)) { app.capas.unidades.removeLayer(m); app.markers.delete(id); }
    }
    marcarSeleccionEnMapa();
  }

  function marcarSeleccionEnMapa() {
    for (const [id, m] of app.markers) {
      const el = m.getElement();
      if (el) el.classList.toggle("sel", id === app.seleccion);
    }
  }

  function dibujarContactos(contactos) {
    const g = app.capas.contactos;
    g.clearLayers();
    for (const c of contactos) {
      const m = L.marker([c.lat, c.lon], { icon: iconoUnidad(c, "enemigo fantasma"), keyboard: false });
      m.on("click", () => seleccionar(c.unidad_id, "mapa"));
      const tip = document.createElement("span");
      tip.textContent = `Último contacto (turno ${c.turno_visto}): ${c.nombre}, ${c.clase || c.tipo}`;
      m.bindTooltip(tip, { direction: "top", offset: [0, -14] }).addTo(g);
    }
  }

  // cobertura de deteccion y niebla de guerra (agujeros donde el bando ve)
  function dibujarCoberturaYNiebla(unidades, clima) {
    app.capas.cobertura.clearLayers();
    app.capas.niebla.clearLayers();
    const vista = bandoVista();
    const factor = Logica.efectosClima(clima).deteccion;
    const detectores = unidades.filter((u) => u.estado === "activa" && u.deteccion_km && (!vista || u.bando === vista));
    for (const u of detectores) {
      L.polygon(anillo(u.lat, u.lon, u.deteccion_km * factor), {
        color: COLOR[u.bando], weight: 1, dashArray: "4 4", fillColor: COLOR[u.bando], fillOpacity: 0.07, interactive: false,
      }).addTo(app.capas.cobertura);
    }
    if (vista) {
      const exterior = [[0.6, -73.4], [12.4, -73.4], [12.4, -59.6], [0.6, -59.6]];
      L.polygon([exterior, ...detectores.map((u) => anillo(u.lat, u.lon, u.deteccion_km * factor))], {
        stroke: false, fillColor: "#0b1020", fillOpacity: 0.38, interactive: false,
      }).addTo(app.capas.niebla);
    }
  }

  // ordenes pendientes: rutas, vectores de ataque y apoyos
  function crearFlecha(desde, hasta) {
    const linea = L.polyline([desde, hasta], { color: COLOR.rojo, weight: 4, opacity: 0.95, lineCap: "round" }).addTo(app.capas.ordenes);
    const punta = L.marker(hasta, { icon: L.divIcon({ className: "flecha", html: "", iconSize: [1, 1] }), interactive: false, keyboard: false }).addTo(app.capas.ordenes);
    const f = {
      actualizar() {
        const a = app.map.latLngToLayerPoint(desde);
        const b = app.map.latLngToLayerPoint(hasta);
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const largo = Math.hypot(dx, dy) || 1;
        const fin = L.point(b.x - (dx / largo) * 24, b.y - (dy / largo) * 24); // se detiene antes del simbolo objetivo
        const grados = (Math.atan2(dy, dx) * 180) / Math.PI;
        linea.setLatLngs([desde, app.map.layerPointToLatLng(fin)]);
        punta.setLatLng(app.map.layerPointToLatLng(fin));
        punta.setIcon(L.divIcon({
          className: "flecha", iconSize: [1, 1],
          html: `<svg width="1" height="1"><g transform="rotate(${grados})"><path d="M8 0 -8 -8 -4 0 -8 8Z" fill="${COLOR.rojo}" stroke="#fff" stroke-width="1"/></g></svg>`,
        }));
      },
    };
    f.actualizar();
    return f;
  }

  function dibujarOrdenes(data) {
    app.capas.ordenes.clearLayers();
    app.flechas = [];
    const posicion = (id) => {
      const u = app.porId.get(id) || app.contactosPorId.get(id);
      return u ? [u.lat, u.lon] : null;
    };
    for (const o of data.ordenes) {
      if (o.estado !== "pendiente") continue;
      const u = app.porId.get(o.unidad_id);
      if (!u || u.estado === "destruida") continue;
      const origen = [u.lat, u.lon];
      if (o.tipo === "mover" && o.waypoints.length) {
        L.polyline([origen, ...o.waypoints], { color: COLOR.azul, weight: 3, dashArray: "9 7", opacity: 0.95, className: "ruta-anim" }).addTo(app.capas.ordenes);
        o.waypoints.forEach((w, i) => {
          L.marker(w, { icon: L.divIcon({ className: "wp", html: `<span>W${i + 1}</span>`, iconSize: [22, 22], iconAnchor: [11, 11] }), keyboard: false })
            .bindTooltip(`W${i + 1} · ${u.nombre}`, { direction: "top" }).addTo(app.capas.ordenes);
        });
      } else if (o.tipo === "atacar") {
        const destino = posicion(o.objetivo_unidad_id);
        if (destino) app.flechas.push(crearFlecha(origen, destino));
      } else if (o.tipo === "apoyar") {
        const destino = posicion(o.objetivo_unidad_id);
        if (destino) L.polyline([origen, destino], { color: "#2EC4B6", weight: 3, dashArray: "2 7", opacity: 0.95, lineCap: "round" }).bindTooltip(`Apoyo · ${u.nombre}`).addTo(app.capas.ordenes);
      }
    }
  }

  function dibujarSeleccion() {
    const g = app.capas.seleccion;
    g.clearLayers();
    const u = app.porId.get(app.seleccion);
    if (!u || u.estado === "destruida" || u.alcance_km === null) return;
    if (u.alcance_km > 0) {
      L.circle([u.lat, u.lon], { radius: u.alcance_km * 1000, color: "#ffd54f", weight: 1.5, dashArray: "6 4", fill: false, interactive: false })
        .bindTooltip(u.tipo === "base" ? "Radio de reabastecimiento" : "Alcance de fuego / apoyo").addTo(g);
    }
    if (u.velocidad_kmh > 0) {
      L.circle([u.lat, u.lon], { radius: u.velocidad_kmh * 1000, color: "#81d4fa", weight: 1, dashArray: "2 5", fill: false, interactive: false })
        .bindTooltip("Avance máximo en 1 turno (en llano, despejado)").addTo(g);
    }
  }

  // ---------- seleccion ----------
  function seleccionar(id, origen = "lista") {
    const u = app.porId.get(id);
    const c = app.contactosPorId.get(id);
    if (!u && !c) return;
    const rol = app.usuario.rol;
    if (esAlumno()) {
      const propia = u && u.bando === rol;
      const objetivo = $("o-objetivo");
      if (origen === "mapa" && app.modoOrden === "atacar" && !propia && u && u.estado === "activa") {
        objetivo.value = String(id);
      } else if (origen === "mapa" && app.modoOrden === "apoyar" && propia && app.unidadOrden && id !== app.unidadOrden && u.tipo !== "base") {
        objetivo.value = String(id);
      } else if (propia && u.clase === "base_aerea") {
        app.baseSeleccionada = id;
      } else if (propia && u.estado === "activa" && u.tipo !== "base") {
        if (app.unidadOrden !== id) { app.unidadOrden = id; app.waypoints = []; app.obraSitio = null; dibujarWaypoints(); if (app.modoOrden === "construir") dibujarSitioObra(); }
      }
    } else if (esInstructor() && u) {
      $("adj-unidad").value = String(id);
    }
    app.seleccion = id;
    if (app.data) { renderOOBSeleccion(); renderDetalle(); actualizarNuevaOrden(app.data); dibujarSeleccion(); marcarSeleccionEnMapa(); }
  }

  // ---------- panel izquierdo: orden de batalla ----------
  function itemUnidad(u, extra = {}) {
    const li = document.createElement("li");
    const b = document.createElement("button");
    b.type = "button";
    b.className = "oob-item" + (u.estado !== "activa" && !extra.contacto ? " inactiva" : "");
    b.dataset.id = String(u.id);
    const est = extra.contacto ? { texto: `contacto T${extra.turno}`, clase: "fuego" } : Logica.estadoUnidad(u, pendientes());
    b.innerHTML = `<span class="simbolo">${simboloSvg(u.sidc, 20)}</span>`
      + `<span class="nom">${escapar(u.nombre)}</span><span class="estado-mini">${escapar(est.texto)}</span><i class="punto ${est.clase}"></i>`;
    b.addEventListener("click", () => { seleccionar(u.id, "lista"); if (u.estado !== "destruida") app.map.panTo([u.lat, u.lon]); });
    li.appendChild(b);
    return li;
  }

  function ramas(unidades, abiertas = true) {
    const frag = document.createDocumentFragment();
    for (const g of Logica.agruparPorRama(unidades)) {
      const det = document.createElement("details");
      det.open = abiertas;
      const sum = document.createElement("summary");
      sum.append(g.nombre);
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = `${g.unidades.length} un.`;
      sum.appendChild(n);
      det.appendChild(sum);
      const ul = document.createElement("ul");
      g.unidades.forEach((u) => ul.appendChild(itemUnidad(u)));
      det.appendChild(ul);
      frag.appendChild(det);
    }
    return frag;
  }

  const pendientes = () => (app.data ? app.data.ordenes.filter((o) => o.estado === "pendiente") : []);

  function renderOOB(data) {
    const cont = $("oob");
    const abiertas = new Set([...cont.querySelectorAll("details[open] > summary")].map((s) => s.firstChild.textContent));
    limpiar(cont);
    const vista = bandoVista();
    $("oob-titulo").textContent = vista ? `Orden de batalla · Bando ${vista === "azul" ? "Azul" : "Rojo"}` : "Orden de batalla · Ambos bandos";
    const bandos = vista ? [vista] : ["azul", "rojo"];
    for (const b of bandos) {
      const propias = data.unidades.filter((u) => u.bando === b);
      if (vista) { cont.appendChild(ramas(propias)); continue; }
      const det = document.createElement("details");
      det.open = true;
      const sum = document.createElement("summary");
      sum.className = b;
      sum.append(`Bando ${b === "azul" ? "Azul" : "Rojo"}`);
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = `${propias.length} un.`;
      sum.appendChild(n);
      det.appendChild(sum);
      det.appendChild(ramas(propias));
      cont.appendChild(det);
    }
    if (vista) {
      const enemigas = data.unidades.filter((u) => u.bando !== vista);
      const contactos = data.contactos || [];
      const det = document.createElement("details");
      det.open = true;
      const sum = document.createElement("summary");
      sum.className = vista === "azul" ? "rojo" : "azul";
      sum.append("Contactos enemigos");
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = `${enemigas.filter((u) => u.estado !== "destruida").length + contactos.length}`;
      sum.appendChild(n);
      det.appendChild(sum);
      const ul = document.createElement("ul");
      enemigas.filter((u) => u.estado !== "destruida").forEach((u) => ul.appendChild(itemUnidad(u)));
      contactos.forEach((c) => ul.appendChild(itemUnidad(c, { contacto: true, turno: c.turno_visto })));
      if (!ul.children.length) { const li = document.createElement("li"); li.className = "vacio"; li.textContent = "Ninguno detectado."; ul.appendChild(li); }
      det.appendChild(ul);
      cont.appendChild(det);
    }
    for (const s of cont.querySelectorAll("summary")) {
      const d = s.parentElement;
      if (abiertas.size && !abiertas.has(s.firstChild.textContent)) d.open = false;
    }
    renderOOBSeleccion();
  }

  function renderOOBSeleccion() {
    document.querySelectorAll(".oob-item").forEach((b) => b.classList.toggle("sel", b.dataset.id === String(app.seleccion)));
  }

  function barra(nombre, valor) {
    const clase = Logica.claseBarra(valor);
    return `<div class="barra"><div class="fila-b"><span>${nombre}</span><b>${valor === null || valor === undefined ? "?" : Math.round(valor) + "%"}</b></div>`
      + `<div class="pista"><div class="relleno ${clase}" style="width:${clase === "oculto" ? 100 : Math.max(0, Math.min(100, valor))}%"></div></div></div>`;
  }
  const dato = (k, v) => `<div><dt>${k}</dt><dd>${escapar(v)}</dd></div>`;
  const km = (v) => (v === null || v === undefined ? "?" : `${v} km`);

  const turnosTxt = (n) => (n > 0 ? `${n} turno${n === 1 ? "" : "s"}` : "lista");

  function renderDetalle() {
    const cont = $("detalle-contenido");
    const c = app.contactosPorId.get(app.seleccion);
    const u = app.porId.get(app.seleccion) || (c ? { ...c, fuerza: null, combustible: null, municion: null, velocidad_kmh: null, alcance_km: null, deteccion_km: null, autonomia_km: null, carga: null, recarga_restante: null, despliegue_restante: null, terreno: "?" } : null);
    if (!u) { cont.innerHTML = '<p class="vacio">Seleccione una unidad en la lista o en el mapa.</p>'; return; }
    const cl = claseDe(u);
    const est = c && !app.porId.get(app.seleccion) ? { texto: `Último contacto T${c.turno_visto}`, clase: "fuego" } : Logica.estadoUnidad(u, pendientes());
    const bando = u.bando || (c ? (bandoVista() === "azul" ? "rojo" : "azul") : "");
    const nombreBando = bando === "azul" ? "Azul" : bando === "rojo" ? "Rojo" : "";
    const rama = (Logica.RAMAS.find((r) => r[0] === Logica.ramaDe(u)) || ["", ""])[1];
    const oculto = u.fuerza === null;
    const extra = [];
    if (cl) {
      extra.push(dato("Movilidad", cl.movilidad));
      if (cl.recarga_turnos) extra.push(dato("Recarga", oculto ? "?" : turnosTxt(u.recarga_restante)));
      if (cl.despliegue_turnos) extra.push(dato("Despliegue", oculto ? "?" : turnosTxt(u.despliegue_restante)));
      if (cl.penalizacion_movilidad) extra.push(dato("Peso / carga", `-${Math.round(cl.penalizacion_movilidad * 100)} % vel.`));
      if (cl.cadencia_fuego !== 1) extra.push(dato("Cadencia", `×${cl.cadencia_fuego}`));
    }
    const modelo = Logica.modeloDe(u, app.catalogo && app.catalogo.modelos);
    if (modelo) {
      const op = Logica.aeronavesOperativas(u);
      extra.push(dato("Modelo", modelo.nombre));
      extra.push(dato("Grupo", op === null ? `${u.aeronaves} aeronaves` : `${op} de ${u.aeronaves} operativas`));
    }
    const notas = [];
    if (modelo) notas.push(modelo.armamento);
    else if (cl && cl.armamento) notas.push(cl.armamento);
    if (cl && cl.vulnerable_emboscada) notas.push("Vulnerable a emboscadas: recibe mucho más daño si el atacante no fue detectado.");
    if (cl && cl.nodo_movil_km) notas.push(`Nodo móvil de reabastecimiento (radio ${cl.nodo_movil_km} km). Gasta suministros por cada unidad que abastece.`);
    if (oculto) notas.push("Niebla de guerra: de las unidades enemigas solo se conoce su posición y clase.");
    const foto = modelo
      ? `<figure class="foto-modelo"><img src="${escapar(modelo.foto)}" alt="${escapar(modelo.nombre)}">`
        + `<figcaption>${escapar(modelo.fabricante)} · ${escapar(modelo.pais)}. Foto: ${escapar(modelo.credito.autor)}, ${escapar(modelo.credito.licencia)}</figcaption></figure>`
      : "";
    cont.innerHTML = foto + `<div class="det-titulo"><span class="simbolo">${simboloSvg(u.sidc, 30)}</span>`
      + `<div><h3>${escapar(u.nombre)}</h3><small>Bando ${nombreBando} · ${rama}${u.echelon ? " · " + escapar(u.echelon) : ""}</small></div></div>`
      + `<span class="insignia ${est.clase}">${escapar(est.texto)}</span>`
      + barra("Fuerza", u.fuerza) + barra("Combustible", u.combustible) + barra("Munición", u.municion)
      + (cl && cl.carga_max ? barra("Suministros del convoy", u.carga) : "")
      + `<dl class="det-datos">${dato("Clase", u.clase || u.tipo)}${dato("Terreno", u.terreno || "?")}`
      + `${dato("Velocidad", u.velocidad_kmh === null ? "?" : u.velocidad_kmh + " km/h")}${dato("Alcance", km(u.alcance_km))}`
      + `${dato("Detección", km(u.deteccion_km))}${dato("Autonomía", km(u.autonomia_km))}${extra.join("")}</dl>`
      + notas.map((n) => `<p class="nota">${escapar(n)}</p>`).join("");
  }

  // ---------- aviacion: envio de grupos de caza ----------
  function actualizarAviacion(data) {
    if (!esAlumno() || !app.catalogo) return;
    const rol = bandoVista() || app.usuario.rol;
    const bases = Logica.basesAereasPropias(data.unidades, rol);
    const tope = (app.catalogo.aeronaves || {}).max_bando || 24;
    const usadas = Logica.aeronavesComprometidas(data.unidades, data.ordenes, rol);
    $("aviacion-tope").textContent = `${usadas}/${tope}`;
    const puede = data.escenario.estado === "activo" && data.escenario.fase === "decision" && bases.length > 0;
    $("btn-enviar-caza").disabled = !puede;
    $("aviacion-ayuda").textContent = bases.length
      ? "Elija F-16 o Su-30 (con foto y datos) y la base de la que despegan. El grupo aparece al resolverse el turno."
      : "Su bando no tiene una base aérea activa: pídale al instructor que coloque una desde la capa «Bases aéreas de Venezuela».";
  }
  $("btn-enviar-caza").addEventListener("click", () => app.aviacion && app.aviacion.abrirDespegue(app.baseSeleccionada));

  // ---------- nueva orden y cola de ordenes ----------
  function actualizarNuevaOrden(data) {
    if (!esAlumno()) return;
    const propias = Logica.unidadesConOrdenes(data.unidades, bandoVista() || app.usuario.rol);
    if (app.unidadOrden && !propias.some((u) => u.id === app.unidadOrden)) app.unidadOrden = null;
    const u = app.porId.get(app.unidadOrden);
    const cl = u ? claseDe(u) : null;
    const puedeConstruir = !!(cl && cl.construye);
    $("modo-construir").hidden = !puedeConstruir;
    if (app.modoOrden === "construir" && !puedeConstruir) app.modoOrden = "mover";
    $("orden-unidad").textContent = u ? u.nombre : "elija una unidad";
    $("btn-emitir").disabled = !u || data.escenario.estado !== "activo" || data.escenario.fase !== "decision";
    document.querySelectorAll(".modos button").forEach((b) => b.classList.toggle("activo", b.dataset.modo === app.modoOrden));
    $("o-mover").hidden = app.modoOrden !== "mover";
    $("o-construir").hidden = app.modoOrden !== "construir";
    $("o-objetivo-box").hidden = app.modoOrden === "mover" || app.modoOrden === "construir";
    if (app.modoOrden === "atacar" || app.modoOrden === "apoyar") {
      const lista = Logica.objetivosDisponibles(data.unidades, app.usuario.rol, app.modoOrden, app.unidadOrden);
      llenarSelect($("o-objetivo"), lista.map((x) => [x.id, x.nombre]));
      $("o-objetivo-ayuda").textContent = app.modoOrden === "apoyar"
        ? "Unidad propia a apoyar (dentro de su alcance; consume 10% de munición). También puede hacer clic en el mapa."
        : lista.length ? "Solo puede atacar unidades detectadas por su bando. También puede hacer clic en el mapa." : "No hay enemigos detectados.";
    }
  }

  document.querySelectorAll(".modos button").forEach((b) => b.addEventListener("click", () => {
    app.modoOrden = b.dataset.modo;
    app.capas.preview.clearLayers();
    if (app.modoOrden === "mover") pedirPreview();
    else if (app.modoOrden === "construir") dibujarSitioObra();
    if (app.data) actualizarNuevaOrden(app.data);
  }));
  $("btn-limpiar-wp").addEventListener("click", () => { app.waypoints = []; dibujarWaypoints(); });

  $("btn-emitir").addEventListener("click", async () => {
    const unidad_id = app.unidadOrden;
    if (!unidad_id) return toast("Seleccione una unidad propia que pueda recibir órdenes.");
    const cuerpo = { unidad_id, tipo: app.modoOrden, waypoints: [], objetivo_unidad_id: null };
    if (app.modoOrden === "mover") {
      if (!app.waypoints.length) return toast("Marque al menos un waypoint en el mapa.");
      cuerpo.waypoints = app.waypoints;
    } else if (app.modoOrden === "construir") {
      if (!app.obraSitio) return toast("Haga clic en el mapa, sobre el río, donde quiere construir.");
      cuerpo.detalle = $("o-obra").value;
      cuerpo.waypoints = [app.obraSitio];
    } else {
      const obj = parseInt($("o-objetivo").value, 10);
      if (!obj) return toast("Elija una unidad objetivo.");
      cuerpo.objetivo_unidad_id = obj;
    }
    try {
      await api("POST", rutaEsc("/ordenes"), cuerpo);
      toast("Orden emitida", true);
      app.waypoints = [];
      app.obraSitio = null;
      dibujarWaypoints();
      app.capas.preview.clearLayers();
      $("o-sitio").textContent = "";
    } catch (_) { /* toast ya mostrado */ }
  });

  const CHIP = { pendiente: ["pend", "PENDIENTE"], resuelta: ["res", "RESUELTA"], rechazada: ["rech", "RECHAZADA"] };
  function textoOrden(o) {
    const obj = app.porId.get(o.objetivo_unidad_id) || app.contactosPorId.get(o.objetivo_unidad_id);
    const nombreObj = obj ? obj.nombre : `#${o.objetivo_unidad_id}`;
    if (o.tipo === "mover") return `Mover (${o.waypoints.length} waypoint${o.waypoints.length === 1 ? "" : "s"})`;
    if (o.tipo === "construir") return `Construir ${o.detalle || "obra"}`;
    if (o.tipo === "despegar") return Logica.textoDespegue(o, app.catalogo && app.catalogo.modelos);
    return `${o.tipo === "atacar" ? "Atacar" : "Apoyar a"} ${nombreObj}`;
  }

  function renderCola(data) {
    const ol = $("cola");
    limpiar(ol);
    const orden = [...data.ordenes].sort((a, b) => (a.estado === "pendiente") === (b.estado === "pendiente") ? b.id - a.id : a.estado === "pendiente" ? -1 : 1).slice(0, 30);
    if (!orden.length) { const li = document.createElement("li"); li.className = "vacio"; li.style.display = "block"; li.textContent = "Sin órdenes: las unidades mantienen su posición."; ol.appendChild(li); }
    for (const o of orden) {
      const u = app.porId.get(o.unidad_id);
      const li = document.createElement("li");
      li.className = o.estado + (esAlumno() ? "" : " " + (u ? u.bando : ""));
      const t = document.createElement("div");
      t.className = "texto";
      const b = document.createElement("b");
      b.textContent = `Orden ${o.id}: ${textoOrden(o)}`;
      const s = document.createElement("span");
      s.textContent = `${u ? u.nombre : "#" + o.unidad_id} · turno ${o.turno_emitida}${o.resultado ? " · " + o.resultado : ""}`;
      t.append(b, s);
      const [claseChip, textoChip] = CHIP[o.estado] || ["pend", o.estado];
      const chip = document.createElement("span");
      chip.className = "chip " + claseChip;
      chip.textContent = textoChip;
      li.append(t, chip);
      if (esAlumno() && o.estado === "pendiente") {
        const x = boton("×", () => enSilencio(api("DELETE", rutaEsc(`/ordenes/${o.id}`))), "");
        x.title = "Cancelar orden";
        x.setAttribute("aria-label", `Cancelar orden ${o.id}`);
        li.appendChild(x);
      }
      li.addEventListener("click", (ev) => { if (ev.target.tagName !== "BUTTON") seleccionar(o.unidad_id, "lista"); });
      ol.appendChild(li);
    }
    $("cola-contador").textContent = String(data.ordenes.filter((o) => o.estado === "pendiente").length);
  }

  // ---------- cabecera, reloj, pie y tarjetas ----------
  function actualizarReloj() {
    const d = app.data;
    const r = $("reloj");
    if (!d) return;
    const esc = d.escenario;
    const etiqueta = $("reloj-etiqueta");
    const valor = $("reloj-valor");
    r.classList.remove("urgente");
    r.classList.remove("inactivo");
    if (esc.estado === "finalizado") { etiqueta.textContent = ""; valor.textContent = "ESCENARIO FINALIZADO"; r.classList.add("inactivo"); return; }
    if (esc.estado === "pausado") { etiqueta.textContent = ""; valor.textContent = "PAUSADO"; r.classList.add("inactivo"); return; }
    if (!esc.decision_termina_en) { etiqueta.textContent = "PLANIFICACIÓN:"; valor.textContent = "SIN LÍMITE"; r.classList.add("inactivo"); return; }
    const seg = Logica.segundosRestantes(esc.decision_termina_en, d.ahora, app.recibidoEn);
    etiqueta.textContent = "TIEMPO RESTANTE PLANIFICACIÓN:";
    valor.textContent = Logica.formatoTiempo(seg);
    r.classList.toggle("urgente", seg !== null && seg <= 15);
    if (app.videowall) app.videowall.actualizarReloj(d, app.recibidoEn);
  }

  function actualizarCabecera(data) {
    const esc = data.escenario;
    $("h-turno").textContent = String(esc.turno_actual);
    $("h-hora").textContent = horaDelTurno(esc.turno_actual);
    const rol = app.usuario.rol;
    const b = $("h-bando");
    b.textContent = Logica.etiquetaBando(rol, data.vista);
    const bando = bandoVista();
    b.className = bando || "";
    actualizarReloj();

    if (esInstructor()) {
      const enfoque = document.activeElement;
      const set = (id, fn) => { if (enfoque !== $(id)) fn($(id)); };
      set("cfg-clima", (e) => { e.value = esc.clima; });
      set("cfg-limite", (e) => { e.value = esc.limite_decision_seg || 0; });
      set("cfg-hora", (e) => { e.value = `${String(Math.floor(esc.hora_inicio_min / 60)).padStart(2, "0")}:${String(esc.hora_inicio_min % 60).padStart(2, "0")}`; });
      set("cfg-azar", (e) => { e.checked = esc.azar; });
      set("cfg-auto", (e) => { e.checked = esc.auto_resolver; });
      if (esc.com_perdida_pct !== undefined) {
        set("cfg-com-latencia", (e) => { e.value = esc.com_latencia_ms; });
        set("cfg-com-jitter", (e) => { e.value = esc.com_jitter_ms; });
        set("cfg-com-perdida", (e) => { e.value = esc.com_perdida_pct; });
      }
      $("btn-archivar").textContent = esc.archivado ? "Desarchivar" : "Archivar";
      $("lnk-exportar").href = rutaEsc("/exportar");
    }
  }

  function actualizarPie(data) {
    const esc = data.escenario;
    const rol = app.usuario.rol;
    for (const bando of ["azul", "rojo"]) {
      const listo = esc[`listo_${bando}`];
      const el = $(`estado-${bando}`);
      el.classList.toggle("listo", listo);
      el.querySelector("b").textContent = listo ? "LISTO" : rol === bando ? "PLANIFICANDO" : "PENDIENTE";
      el.querySelector("i").classList.toggle("pulso", !listo);
    }
    if (esAlumno()) {
      const listo = esc[`listo_${rol}`];
      const btn = $("btn-listo");
      btn.classList.toggle("confirmado", listo);
      $("btn-listo-texto").textContent = listo ? "ÓRDENES CONFIRMADAS - CLIC PARA RETIRAR" : "ESTOY LISTO - CONFIRMAR ÓRDENES";
      btn.disabled = esc.estado !== "activo" || esc.fase !== "decision";
    }
    if (esInstructor()) $("btn-avanzar").disabled = esc.estado !== "activo";
  }

  const ICONOS_CLIMA = {
    despejado: '<circle class="sol" cx="24" cy="24" r="9"/><g class="rayo-sol"><path d="M24 4v7M24 37v7M4 24h7M37 24h7M9.9 9.9l5 5M33.1 33.1l5 5M9.9 38.1l5-5M33.1 14.9l5-5"/></g>',
    nublado: '<circle class="sol" cx="17" cy="17" r="7"/><path class="nube" d="M14 38h21a8 8 0 0 0 .8-16A11 11 0 0 0 14.6 23 7.5 7.5 0 0 0 14 38Z"/>',
    lluvia: '<path class="nube-oscura" d="M14 30h21a8 8 0 0 0 .8-16A11 11 0 0 0 14.6 15 7.5 7.5 0 0 0 14 30Z"/><g class="gota"><path d="M17 34l-2 6M25 34l-2 6M33 34l-2 6"/></g>',
    tormenta: '<path class="nube-oscura" d="M14 28h21a8 8 0 0 0 .8-16A11 11 0 0 0 14.6 13 7.5 7.5 0 0 0 14 28Z"/><path class="rayo-tormenta" d="M26 27l-7 11h5l-2 8 10-13h-6l3-6Z"/>',
  };

  function actualizarTarjetas(data) {
    const esc = data.escenario;
    const ef = Logica.efectosClima(esc.clima);
    $("icono-clima").innerHTML = ICONOS_CLIMA[esc.clima] || ICONOS_CLIMA.despejado;
    $("clima-nombre").textContent = Logica.etiquetaClima(esc.clima);
    $("clima-vis").textContent = `Visibilidad ${Logica.visibilidadPct(esc.clima)} %`;
    $("clima-mov").textContent = `×${ef.terrestre}`;
    $("clima-aire").textContent = `×${ef.ataqueAereo}`;
    $("esc-fase").textContent = `${ETIQUETA_FASE[esc.fase] || esc.fase} · ${esc.estado}`;
    $("esc-modo").textContent = `${esc.azar ? "Azar" : "Determinista"} · ${esc.auto_resolver ? "Auto" : "Manual"}`;
  }

  // ---------- alertas ----------
  function registrarAlertas(data) {
    const { alertas, memoria } = Logica.alertasNuevas(app.memoria, data, app.usuario.rol);
    app.memoria = memoria;
    for (const a of alertas) {
      app.alertas.unshift({ ...a, hora: horaDelTurno(a.turno), nueva: true });
      app.alertasSinLeer += 1;
    }
    app.alertas = app.alertas.slice(0, MAX_ALERTAS);
    renderAlertas();
  }

  function renderAlertas() {
    const ul = $("alertas");
    limpiar(ul);
    if (!app.alertas.length) { const li = document.createElement("li"); li.className = "info"; li.textContent = "Sin novedades."; ul.appendChild(li); }
    for (const a of app.alertas) {
      const li = document.createElement("li");
      li.className = a.nivel + (a.nueva ? " nueva" : "");
      const t = document.createElement("time");
      t.textContent = `TURNO ${a.turno} · ${a.hora}`;
      li.append(t, a.texto);
      ul.appendChild(li);
      a.nueva = false;
    }
    const n = $("alertas-nuevas");
    n.hidden = app.alertasSinLeer === 0;
    n.textContent = String(app.alertasSinLeer);
  }
  $("tarjeta-alertas").addEventListener("mouseenter", () => { app.alertasSinLeer = 0; renderAlertas(); });
  $("tarjeta-alertas").addEventListener("click", () => { app.alertasSinLeer = 0; renderAlertas(); });

  // ---------- render principal ----------
  function render(data) {
    app.data = data;
    app.recibidoEn = Date.now();
    app.porId = new Map(data.unidades.map((u) => [u.id, u]));
    app.contactosPorId = new Map((data.contactos || []).map((c) => [c.unidad_id, c]));
    if (app.seleccion !== null && !app.porId.has(app.seleccion) && !app.contactosPorId.has(app.seleccion)) app.seleccion = null;
    if (esBando(data.vista) && esInstructor()) app.vista = data.vista;

    registrarAlertas(data);
    actualizarCabecera(data);
    actualizarPie(data);
    actualizarTarjetas(data);
    app.chat.actualizarEnlace(data.escenario);
    app.graficos.sincronizar(data.graficos || []);
    app.videowall.actualizarHud(data, app.alertas);
    renderOOB(data);
    renderDetalle();
    renderCola(data);
    actualizarNuevaOrden(data);
    actualizarAviacion(data);
    llenarSelect($("adj-unidad"), data.unidades.map((u) => [u.id, `${u.nombre} (${u.bando})`]));
    if (app.informe && app.informe.activo()) return; // durante la repeticion no se pisa el mapa

    dibujarUnidades(data.unidades);
    dibujarContactos(data.contactos || []);
    dibujarObras(data.obras || []);
    dibujarCoberturaYNiebla(data.unidades, data.escenario.clima);
    dibujarOrdenes(data);
    dibujarSeleccion();
    if (!app.encuadrado && data.unidades.length) {
      app.map.fitBounds(data.unidades.map((u) => [u.lat, u.lon]), { padding: [80, 80], maxZoom: 10 });
      app.encuadrado = true;
    }
  }

  // ---------- obras (puentes y vados) ----------
  const claseDe = (u) => (app.catalogo ? app.catalogo.clases.find((c) => c.id === (u.clase || "")) : null) || null;

  function dibujarObras(obras) {
    const g = app.capas.obras;
    g.clearLayers();
    const vista = bandoVista();
    for (const o of obras) {
      const enemiga = !!vista && o.bando !== vista;
      L.marker([o.lat, o.lon], {
        icon: L.divIcon({ className: `obra ${o.tipo}${enemiga ? " enemiga" : ""}`, html: `<span>${o.tipo === "puente" ? "P" : "V"}</span>`, iconSize: [24, 24], iconAnchor: [12, 12] }),
        keyboard: false,
      }).bindTooltip(`${o.tipo === "puente" ? "Puente" : "Vado"} (${o.bando}) · transitable hasta el turno ${o.expira_turno}`, { direction: "top" }).addTo(g);
      L.circle([o.lat, o.lon], { radius: o.radio_km * 1000, color: enemiga ? "#EF233C" : "#ffd166", weight: 1, dashArray: "3 4", fillOpacity: 0.05, interactive: false }).addTo(g);
    }
  }

  function dibujarSitioObra() {
    const g = app.capas.preview;
    g.clearLayers();
    const u = app.porId.get(app.unidadOrden);
    if (!u || app.modoOrden !== "construir") return;
    L.circle([u.lat, u.lon], { radius: u.alcance_km * 1000, color: "#ffd54f", weight: 1, dashArray: "6 4", fill: false, interactive: false })
      .bindTooltip("Alcance de trabajo de los ingenieros").addTo(g);
    if (!app.obraSitio) { $("o-sitio").textContent = "Aún no eligió el punto de construcción."; return; }
    const d = Logica.distanciaKm(u.lat, u.lon, app.obraSitio[0], app.obraSitio[1]);
    L.circleMarker(app.obraSitio, { radius: 8, color: "#ffd166", fillColor: "#4a3a10", fillOpacity: 0.9 }).bindTooltip("Punto de construcción").addTo(g);
    $("o-sitio").textContent = `Punto: ${app.obraSitio[0].toFixed(4)}, ${app.obraSitio[1].toFixed(4)} · a ${d.toFixed(1)} km de los ingenieros`
      + (d > u.alcance_km ? ` (fuera de su alcance de trabajo de ${u.alcance_km} km)` : "") + ".";
  }

  // ---------- modulos: graficos tacticos, comunicaciones y videowall ----------
  function enviarWs(obj) {
    if (!app.ws || app.ws.readyState !== 1) return false;
    app.ws.send(JSON.stringify(obj));
    return true;
  }

  function iniciarModulos() {
    if (app.graficos) return;
    app.graficos = Graficos.crear({
      map: () => app.map, api, toast, escenarioId: () => app.escenarioId, usuario: () => app.usuario,
      alDibujar: (b) => { app.dibujando = b; },
    });
    app.graficos.conectar(app.map);
    app.chat = Chat.crear({ enviar: enviarWs, usuario: () => app.usuario, toast });
    app.chat.conectar();
    app.chat.configurarRol();
    app.videowall = Videowall.crear({
      map: () => app.map,
      alCambiar: (activo) => {
        app.tamSimbolo = activo ? 36 : 26; // simbolos mas grandes para verlos desde lejos
        if (app.data && !(app.informe && app.informe.activo())) { limpiarCapasVivas(); render(app.data); }
      },
    });
    app.videowall.conectar();
    app.aviacion = Aviacion.crear({
      map: () => app.map, api, toast, rutaEsc, usuario: () => app.usuario, catalogo: () => app.catalogo,
      datos: () => app.data, escenarioId: () => app.escenarioId, capa: app.capas.bases_ven,
    });
    app.aviacion.conectar();
  }

  /** ?modo=videowall&escenario=ID&vista=azul|rojo|completa (se aplica una sola vez, tras iniciar sesion) */
  function aplicarParametrosUrl() {
    const u = app.urlInicial;
    app.urlInicial = {};
    if (u.escenario && [...$("escenario").options].some((o) => o.value === String(u.escenario))) {
      $("escenario").value = String(u.escenario);
      cambiarEscenario();
    }
    if (u.vista && esInstructor()) {
      $("cfg-vista").value = u.vista;
      $("cfg-vista").dispatchEvent(new Event("change"));
    }
    if (u.videowall) app.videowall.alternar(true, { pantallaCompleta: false });
  }

  // ---------- websocket ----------
  function cerrarWs() {
    clearInterval(app.wsAlive);
    if (app.ws) { app.ws.onclose = null; app.ws.close(); app.ws = null; }
  }

  function conectar() {
    cerrarWs();
    if (!app.escenarioId || !app.usuario) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/${app.escenarioId}`);
    app.ws = ws;
    ws.onopen = () => {
      $("estado-conexion").className = "conexion on";
      $("estado-conexion").title = "conectado";
      if (esInstructor() && app.vista !== "completa") ws.send(JSON.stringify({ vista: app.vista }));
      app.wsAlive = setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
    };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.tipo === "estado") render(m);
      else if (m.tipo === "grafico") app.graficos.aplicar(m);
      else if (m.tipo === "chat_historial") app.chat.historial(m.mensajes);
      else if (m.tipo === "chat") app.chat.recibir(m);
      else if (m.tipo === "chat_error") app.chat.error(m.detalle);
    };
    ws.onclose = () => {
      clearInterval(app.wsAlive);
      $("estado-conexion").className = "conexion off";
      $("estado-conexion").title = "desconectado";
      // Un rechazo por sesion vencida llega como cierre generico (1006), asi que
      // se consulta la sesion antes de reintentar: sin sesion, se vuelve al login.
      const reintentar = () => setTimeout(() => { if (app.ws === ws) conectar(); }, 2000);
      fetch("/api/auth/yo", { credentials: "same-origin" })
        .then((r) => { if (r.status === 401) mostrarLogin(); else reintentar(); })
        .catch(reintentar);
    };
  }

  async function cargarEscenarios(seleccionarId) {
    const archivados = esInstructor() && $("ver-archivados").checked;
    const lista = await api("GET", `/api/escenarios${archivados ? "?archivados=true" : ""}`);
    llenarSelect($("escenario"), lista.map((e) => [e.id, `${e.id} - ${e.nombre}${e.archivado ? " (archivado)" : ""}`]));
    if (seleccionarId) $("escenario").value = String(seleccionarId);
    cambiarEscenario();
  }

  function cambiarEscenario() {
    const v = $("escenario").value;
    app.escenarioId = v ? parseInt(v, 10) : null;
    app.encuadrado = false;
    app.seleccion = null;
    app.unidadOrden = null;
    app.data = null;
    app.vista = "completa";
    app.memoria = Logica.memoriaVacia();
    app.alertas = [];
    app.alertasSinLeer = 0;
    $("cfg-vista").value = "completa";
    renderAlertas();
    if (app.chat) { app.chat.reiniciar(); app.graficos.limpiar(); }
    if (app.informe) app.informe.cerrar();
    limpiarCapasVivas();
    conectar();
    if (esInstructor() && app.escenarioId) enSilencio(cargarAsignados());
  }

  // ---------- consola del instructor: usuarios ----------
  function pedirClave(username) {
    return new Promise((resolve) => {
      const d = document.createElement("dialog");
      const f = document.createElement("form");
      f.method = "dialog";
      const p = document.createElement("p");
      p.textContent = `Nueva contraseña para ${username} (mín. 8 caracteres):`;
      const inp = document.createElement("input");
      inp.type = "password";
      inp.autocomplete = "new-password";
      const ok = document.createElement("button");
      ok.textContent = "Guardar";
      const no = boton("Cancelar", () => d.close(), "secundario");
      let guardar = false;
      f.append(p, inp, ok, no);
      d.appendChild(f);
      document.body.appendChild(d);
      f.addEventListener("submit", () => { guardar = true; });
      d.addEventListener("close", () => {
        resolve(guardar && inp.value ? inp.value : null);
        d.remove();
      });
      d.showModal();
      inp.focus();
    });
  }

  async function cargarUsuarios() {
    const usuarios = await api("GET", "/api/usuarios");
    app.usuariosLista = usuarios;
    const ul = $("lista-usuarios");
    limpiar(ul);
    for (const u of usuarios) {
      const item = document.createElement("li");
      if (!u.activo) item.className = "inactiva";
      const et = document.createElement("span");
      et.textContent = `${u.username}${u.activo ? "" : " (inactivo)"}`;
      item.appendChild(et);
      const esYo = u.id === app.usuario.id;
      const sel = document.createElement("select");
      for (const r of ["instructor", "azul", "rojo", "observador"]) {
        const o = document.createElement("option");
        o.value = r; o.textContent = r; sel.appendChild(o);
      }
      sel.value = u.rol;
      sel.disabled = esYo;
      sel.addEventListener("change", () => api("PATCH", `/api/usuarios/${u.id}`, { rol: sel.value }).finally(cargarUsuarios));
      item.appendChild(sel);
      item.appendChild(boton("Clave", async () => {
        const clave = await pedirClave(u.username);
        if (clave) enSilencio(api("PATCH", `/api/usuarios/${u.id}`, { password: clave }).then(() => toast("Contraseña actualizada", true)));
      }));
      if (!esYo) {
        item.appendChild(boton(u.activo ? "Desactivar" : "Activar", () => api("PATCH", `/api/usuarios/${u.id}`, { activo: !u.activo }).finally(cargarUsuarios)));
      }
      ul.appendChild(item);
    }
    if (app.escenarioId) enSilencio(cargarAsignados());
  }

  async function cargarAsignados() {
    const { usuario_ids } = await api("GET", rutaEsc("/usuarios"), undefined, true);
    const marcados = new Set(usuario_ids);
    const ul = $("lista-asignados");
    limpiar(ul);
    const candidatos = app.usuariosLista.filter((u) => u.rol !== "instructor" && u.activo);
    if (!candidatos.length) { const li = document.createElement("li"); li.className = "vacio"; li.textContent = "No hay alumnos ni observadores creados."; ul.appendChild(li); }
    for (const u of candidatos) {
      const item = document.createElement("li");
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.checked = marcados.has(u.id);
      chk.dataset.id = String(u.id);
      chk.addEventListener("change", async () => {
        const ids = [...ul.querySelectorAll("input:checked")].map((c) => parseInt(c.dataset.id, 10));
        try { await api("PUT", rutaEsc("/usuarios"), { usuario_ids: ids }); } catch (_) { chk.checked = !chk.checked; }
      });
      const et = document.createElement("span");
      et.textContent = `${u.username} (${u.rol})`;
      item.append(chk, et);
      ul.appendChild(item);
    }
  }

  // ---------- eventos de UI ----------
  $("escenario").addEventListener("change", cambiarEscenario);
  $("ver-archivados").addEventListener("change", () => enSilencio(cargarEscenarios()));

  $("btn-nuevo-escenario").addEventListener("click", async () => {
    const nombre = prompt("Nombre del escenario:");
    if (!nombre) return;
    const e = await api("POST", "/api/escenarios", { nombre });
    await cargarEscenarios(e.id);
  });

  const accion = (id, ruta) => $(id).addEventListener("click", () => app.escenarioId && enSilencio(api("POST", rutaEsc(`/${ruta}`))));
  accion("btn-avanzar", "avanzar_turno");
  accion("btn-pausar", "pausar");
  accion("btn-reanudar", "reanudar");
  $("btn-finalizar").addEventListener("click", () => {
    if (app.escenarioId && confirm("¿Finalizar el escenario? Ya no se podrán emitir órdenes y el informe se abrirá a los alumnos.")) {
      enSilencio(api("POST", rutaEsc("/finalizar")));
    }
  });

  $("btn-config").addEventListener("click", () => {
    if (!app.escenarioId) return;
    const cuerpo = {
      clima: $("cfg-clima").value, azar: $("cfg-azar").checked, auto_resolver: $("cfg-auto").checked,
      limite_decision_seg: Math.max(0, parseInt($("cfg-limite").value, 10) || 0),
    };
    if ($("cfg-hora").value) cuerpo.hora_inicio = $("cfg-hora").value;
    enSilencio(api("PATCH", rutaEsc("/config"), cuerpo).then(() => toast("Configuración aplicada", true)));
  });

  $("btn-config-com").addEventListener("click", () => {
    if (!app.escenarioId) return;
    const n = (id) => Math.max(0, parseInt($(id).value, 10) || 0);
    enSilencio(api("PATCH", rutaEsc("/config"), {
      com_latencia_ms: n("cfg-com-latencia"), com_jitter_ms: n("cfg-com-jitter"), com_perdida_pct: Math.min(100, n("cfg-com-perdida")),
    }).then(() => toast("Comunicaciones actualizadas", true)));
  });

  $("cfg-vista").addEventListener("change", () => {
    app.vista = $("cfg-vista").value;
    if (app.ws && app.ws.readyState === 1) app.ws.send(JSON.stringify({ vista: app.vista }));
    // la niebla visual solo tiene sentido al ver como un bando
    const chk = document.querySelector('[data-capa="niebla"]');
    chk.checked = app.vista !== "completa";
    alternarCapa("niebla", chk.checked);
  });

  $("btn-modo-agregar").addEventListener("click", () => {
    app.modoAgregar = !app.modoAgregar;
    $("btn-modo-agregar").textContent = app.modoAgregar ? "Haga clic en el mapa… (cancelar)" : "Ubicar en mapa";
  });

  $("btn-evento").addEventListener("click", async () => {
    const descripcion = $("ev-desc").value.trim();
    if (!descripcion || !app.escenarioId) return;
    await enSilencio(api("POST", rutaEsc("/eventos"), { descripcion, bando_destino: $("ev-bando").value }));
    $("ev-desc").value = "";
  });

  $("btn-ajustar").addEventListener("click", async () => {
    const id = $("adj-unidad").value;
    const cuerpo = {};
    for (const [campo, el] of [["fuerza", "adj-fuerza"], ["combustible", "adj-combustible"], ["municion", "adj-municion"]]) {
      const v = parseFloat($(el).value);
      if (!Number.isNaN(v)) cuerpo[campo] = v;
    }
    if (!id || !Object.keys(cuerpo).length) return toast("Indique al menos un valor a ajustar.");
    await enSilencio(api("PATCH", rutaEsc(`/unidades/${id}`), cuerpo));
    ["adj-fuerza", "adj-combustible", "adj-municion"].forEach((el) => { $(el).value = ""; });
  });

  $("btn-archivar").addEventListener("click", async () => {
    if (!app.data) return;
    const archivado = app.data.escenario.archivado;
    await enSilencio(api("POST", rutaEsc(archivado ? "/desarchivar" : "/archivar")));
    toast(archivado ? "Escenario restaurado" : "Escenario archivado", true);
    await cargarEscenarios(archivado || $("ver-archivados").checked ? app.escenarioId : undefined);
  });

  $("btn-duplicar").addEventListener("click", async () => {
    try {
      const copia = await api("POST", rutaEsc("/duplicar"));
      toast(`Copia creada: ${copia.nombre}`, true);
      await cargarEscenarios(copia.id);
    } catch (_) { /* toast ya mostrado */ }
  });

  $("btn-crear-usuario").addEventListener("click", async () => {
    try {
      await api("POST", "/api/usuarios", { username: $("nu-user").value.trim(), password: $("nu-pass").value, rol: $("nu-rol").value });
      $("nu-user").value = ""; $("nu-pass").value = "";
      toast("Usuario creado", true);
      cargarUsuarios();
    } catch (_) { /* toast ya mostrado */ }
  });

  $("btn-informe").addEventListener("click", () => app.informe && app.informe.abrir());

  $("btn-listo").addEventListener("click", () => {
    if (!app.data) return;
    enSilencio(api("POST", rutaEsc("/listo"), { listo: !app.data.escenario[`listo_${app.usuario.rol}`] }));
  });

  arrancar();
})();
