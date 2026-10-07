(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const { esBando, pct } = Logica;
  const COLOR = { azul: "#3A86FF", rojo: "#EF233C" };
  // regiones del mapa (GET /api/terreno/mapas): Venezuela en detalle, America y, si se genero, el mundo; se apilan
  // de la mas general a la mas detallada (ver tools/preparar_terreno.py y Logica.limitesDeMapas)
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
    lote: new Set(), // seleccion multiple: ids de unidades propias (ademas de la principal, app.unidadOrden)
    graficos: null, chat: null, videowall: null, aviacion: null,
    modeloUnidad: null, baseSeleccionada: null, patrullaPunto: null, naciones: [],
    modoObjetivo: false, objetivoCentro: null, editando: false, filtroOOB: "", herramientas: null,
    rumbos: new Map(), posPrevia: new Map(), // hacia donde apunta cada aeronave (imagen 3D)
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
  /** Puesto del alumno dentro de su bando (los demas roles no tienen restricciones por puesto). */
  const puestoActual = () => (esAlumno() ? app.usuario.puesto || "mando" : "mando");
  const puedeFuncion = (f) => !esAlumno() || Logica.puestoPuede(puestoActual(), f);
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
  /** Muestra una de las pantallas de acceso: "login" | "registro" | "clave". */
  function pantallaAcceso(cual) {
    $("login-form").hidden = cual !== "login";
    $("registro-form").hidden = cual !== "registro";
    $("clave-form").hidden = cual !== "clave";
    $("login").hidden = false;
  }

  function mostrarLogin() {
    cerrarWs();
    clearInterval(app.relojTimer);
    clearInterval(app.solicitudesTimer);
    if (app.informe) app.informe.cerrar();
    app.usuario = null;
    $("app").hidden = true;
    pantallaAcceso("login");
    $("l-pass").value = "";
    $("l-user").focus();
  }

  /** Formulario de cambio de contrasena: obligatorio (contrasena inicial o puesta por el instructor: no se
   * puede usar el simulador hasta cambiarla) o a pedido desde el menu del perfil (se puede cancelar). */
  function mostrarCambioClave(obligatorio) {
    app.cambioObligatorio = obligatorio;
    for (const id of ["c-actual", "c-nueva", "c-nueva2"]) $(id).value = "";
    $("c-error").textContent = "";
    $("c-motivo").textContent = obligatorio
      ? `Hola ${app.usuario.username}: su contraseña es provisional (inicial o puesta por el instructor). Elija una nueva para continuar.`
      : "Escriba su contraseña actual y la nueva.";
    $("btn-clave-salir").textContent = obligatorio ? "Cerrar sesión" : "Cancelar";
    pantallaAcceso("clave");
    $("c-actual").focus();
  }

  async function arrancar() {
    try {
      app.usuario = await api("GET", "/api/auth/yo", undefined, true);
    } catch (_) {
      return mostrarLogin();
    }
    if (app.usuario.debe_cambiar_clave) {
      $("app").hidden = true;
      return mostrarCambioClave(true);
    }
    $("login").hidden = true;
    $("app").hidden = false;
    aplicarRol();
    try { app.mapas = (await api("GET", "/api/terreno/mapas", undefined, true)).mapas; } catch (_) { app.mapas = null; }
    initMapa();
    iniciarModulos();
    app.map.invalidateSize();
    app.informe = app.informe || Informe.crear({
      map: app.map, api, toast, escenarioId: () => app.escenarioId, crearIcono: (u) => iconoUnidad(u),
      alActivar: () => { limpiarCapasVivas(); },
      alDesactivar: () => { if (app.data) render(app.data); },
    });
    try { app.catalogo = await api("GET", "/api/catalogo"); prepararCatalogo(); } catch (_) { /* sin catalogo */ }
    try { app.naciones = (await api("GET", "/api/naciones")).naciones; prepararNaciones(); } catch (_) { /* sin naciones */ }
    clearInterval(app.relojTimer);
    app.relojTimer = setInterval(actualizarReloj, 1000);
    await cargarEscenarios();
    clearInterval(app.solicitudesTimer);
    if (esInstructor()) {
      enSilencio(cargarUsuarios());
      // las solicitudes de cuenta llegan desde la pantalla de acceso: se revisan cada 30 s
      app.solicitudesTimer = setInterval(() => enSilencio(cargarUsuarios()), 30000);
    }
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

  async function cerrarSesion() {
    try { await api("POST", "/api/auth/logout", undefined, true); } catch (_) { /* ya cerrada */ }
    $("menu-perfil").hidden = true;
    mostrarLogin();
  }
  $("btn-logout").addEventListener("click", cerrarSesion);

  $("btn-cambiar-clave").addEventListener("click", () => {
    $("menu-perfil").hidden = true;
    mostrarCambioClave(false);
  });

  $("btn-clave-salir").addEventListener("click", () => {
    if (app.cambioObligatorio) return cerrarSesion();
    $("login").hidden = true;  // cambio a pedido: se vuelve al simulador tal como estaba
  });

  $("clave-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("c-error").textContent = "";
    const nueva = $("c-nueva").value;
    if (nueva !== $("c-nueva2").value) { $("c-error").textContent = "Las contraseñas nuevas no coinciden."; return; }
    if (nueva.length < 8) { $("c-error").textContent = "La contraseña nueva debe tener al menos 8 caracteres."; return; }
    try {
      app.usuario = await api("POST", "/api/auth/cambiar-clave", { actual: $("c-actual").value, nueva }, true);
    } catch (err) {
      $("c-error").textContent = err.message;
      return;
    }
    toast("Contraseña cambiada", true);
    if (app.cambioObligatorio) arrancar();
    else $("login").hidden = true;
  });

  // ---------- solicitud de cuenta (sin sesion) ----------
  const actualizarPuestoSolicitado = () => { $("r-puesto").hidden = !esBando($("r-rol").value); };
  $("r-rol").addEventListener("change", actualizarPuestoSolicitado);

  $("btn-ir-registro").addEventListener("click", () => {
    for (const id of ["r-user", "r-pass", "r-pass2"]) $(id).value = "";
    $("r-error").textContent = "";
    $("r-ok").hidden = true;
    actualizarPuestoSolicitado();
    pantallaAcceso("registro");
    $("r-user").focus();
  });
  $("btn-volver-login").addEventListener("click", () => { pantallaAcceso("login"); $("l-user").focus(); });

  $("registro-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    $("r-error").textContent = "";
    $("r-ok").hidden = true;
    const username = $("r-user").value.trim();
    const password = $("r-pass").value;
    if (!/^[A-Za-z0-9_.-]{3,50}$/.test(username)) { $("r-error").textContent = "Usuario: de 3 a 50 letras, números, punto, guion o guion bajo (sin espacios)."; return; }
    if (password !== $("r-pass2").value) { $("r-error").textContent = "Las contraseñas no coinciden."; return; }
    if (password.length < 8) { $("r-error").textContent = "La contraseña debe tener al menos 8 caracteres."; return; }
    try {
      await api("POST", "/api/auth/solicitar", { username, password, rol: $("r-rol").value, puesto: $("r-puesto").value }, true);
      $("r-ok").textContent = `Solicitud enviada. Podrá ingresar como «${username}» cuando el instructor la apruebe.`;
      $("r-ok").hidden = false;
      $("l-user").value = username;
      for (const id of ["r-pass", "r-pass2"]) $(id).value = "";
    } catch (err) {
      $("r-error").textContent = err.message;
    }
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
    $("mp-rol").textContent = esBando(rol) ? `${rol} · ${Logica.etiquetaPuesto(puestoActual())}` : rol;
    document.querySelectorAll(".solo-instructor").forEach((e) => (e.hidden = rol !== "instructor"));
    document.querySelectorAll(".solo-alumno").forEach((e) => (e.hidden = !esBando(rol)));
    document.querySelectorAll(".solo-control").forEach((e) => (e.hidden = !(rol === "instructor" || rol === "observador")));
    document.querySelectorAll(".solo-dibuja").forEach((e) => (e.hidden = !(rol === "instructor" || esBando(rol))));
    // puesto por funcion: cada celula del bando solo ve las herramientas de lo que le toca conducir
    const puesto = Logica.puestoDe(puestoActual());
    $("puesto-nombre").textContent = Logica.etiquetaPuesto(puesto.id);
    $("puesto-desc").textContent = puesto.descripcion;
    $("sec-orden").hidden = !esBando(rol) || !puesto.funciones.some((f) => f !== "listo");
    $("sec-aviacion").hidden = !esBando(rol) || !puedeFuncion("despegar");
    $("btn-listo").hidden = !esBando(rol) || !puedeFuncion("listo");
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

  // ---------- identidad nacional de cada bando ----------
  function prepararNaciones() {
    for (const id of ["cfg-nacion-azul", "cfg-nacion-rojo"]) {
      llenarSelect($(id), [["", "(sin especificar)"], ...app.naciones.map((n) => [n.id, n.nombre])]);
    }
  }
  $("btn-config-nacion").addEventListener("click", () => enSilencio(api("PATCH", rutaEsc("/config"), {
    nacion_azul: $("cfg-nacion-azul").value, nacion_rojo: $("cfg-nacion-rojo").value,
  })));

  const nombreDeBando = (bando) => Logica.etiquetaBandoNacion(bando, app.data && app.data.escenario, app.naciones);

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
    const mapas = Logica.ordenarMapas(app.mapas);
    const { limites, zoomMin, principal } = Logica.limitesDeMapas(mapas);
    const bounds = L.latLngBounds(limites);
    const map = L.map("map", { zoomControl: false, attributionControl: false, minZoom: zoomMin, maxZoom: 17, maxBounds: bounds.pad(0.1), maxBoundsViscosity: 0.85 });
    map.fitBounds(L.latLngBounds(Logica.limitesDe(principal)));
    app.map = map;
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.control.attribution({ position: "bottomleft", prefix: false })
      .addAttribution("Satélite: Sentinel-2 cloudless (EOX, CC BY 4.0) · Relieve: SRTM/GMTED (AWS Terrain Tiles) · Cobertura: ESA WorldCover · Vectores: Natural Earth · Aeródromos: © colaboradores de OpenStreetMap (ODbL)").addTo(map);

    // Fondo: el relieve coloreado por clase de terreno de cada region (la mas detallada encima) y, opcionalmente, la foto
    // satelital real de cada region que la tenga descargada (tools/preparar_satelite.py: Venezuela hasta el zoom 12,
    // America hasta el 8), superpuesta al relieve y recortada al recuadro exacto de su region.
    const c = app.capas;
    c.baseRelieve = L.layerGroup().addTo(map);
    c.baseSatelite = L.layerGroup().addTo(map);
    const recortes = [];
    for (const m of mapas) {
      const limitesM = L.latLngBounds(Logica.limitesDe(m));
      L.tileLayer(`/static/tiles/${m.id}/{z}/{x}/{y}.jpg`, {
        minZoom: zoomMin, minNativeZoom: m.z_min, maxNativeZoom: m.z, maxZoom: 17, bounds: limitesM, zIndex: m.z,
      }).addTo(c.baseRelieve);
      if (!m.satelite) continue;
      const sat = L.tileLayer(`/static/tiles_sat/${m.id}/{z}/{x}/{y}.jpg`, {
        minZoom: Math.max(zoomMin, m.satelite.z_min), maxNativeZoom: m.satelite.z_max, maxZoom: 17, bounds: limitesM, zIndex: 20 + m.z,
      }).addTo(c.baseSatelite);
      // Leaflet dibuja enteras las teselas que tocan `bounds`: se recorta la capa al rectangulo exacto de la region para
      // que la foto no sobresalga con bordes rectos sobre la region de abajo
      const recortar = () => {
        const el = sat.getContainer();
        if (!el) return;
        const a = map.latLngToLayerPoint(limitesM.getNorthWest());
        const b = map.latLngToLayerPoint(limitesM.getSouthEast());
        el.style.clipPath = `polygon(${a.x}px ${a.y}px, ${b.x}px ${a.y}px, ${b.x}px ${b.y}px, ${a.x}px ${b.y}px)`;
      };
      sat.on("add", () => setTimeout(recortar, 0));
      recortes.push(recortar);
    }
    map.on("viewreset zoomend moveend", () => recortes.forEach((r) => r()));

    // botones para encajar la vista en cada region
    const irA = $("mapas-ir");
    irA.replaceChildren();
    for (const m of mapas.slice().reverse()) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "mini";
      b.textContent = m.nombre || m.id;
      b.title = Logica.textoMapa(m);
      b.addEventListener("click", () => map.fitBounds(L.latLngBounds(Logica.limitesDe(m))));
      irA.appendChild(b);
    }

    function elegirBaseMapa(nombre) {
      const satelite = nombre === "satelite";
      if (satelite) c.baseSatelite.addTo(map);
      else c.baseSatelite.remove();
      $("base-satelite").classList.toggle("activa", satelite);
      $("base-satelite").setAttribute("aria-pressed", String(satelite));
      $("base-relieve").classList.toggle("activa", !satelite);
      $("base-relieve").setAttribute("aria-pressed", String(!satelite));
    }
    $("base-satelite").addEventListener("click", () => elegirBaseMapa("satelite"));
    $("base-relieve").addEventListener("click", () => elegirBaseMapa("relieve"));

    c.referencias = L.layerGroup().addTo(map);
    c.bases_ven = L.layerGroup().addTo(map);
    // plano real de los aerodromos (OpenStreetMap): debajo de las unidades y los graficos, encima del fondo
    map.createPane("aerodromos").style.zIndex = 350;
    map.createPane("aerodromos-rotulos").style.zIndex = 390;
    map.getPane("aerodromos-rotulos").style.pointerEvents = "none";
    c.aerodromos = L.layerGroup().addTo(map);
    app.aerodromos = Aerodromos.crear({
      map, capa: c.aerodromos,
      alCargar: () => { if (app.data) { app.aerodromos.actualizar(app.data.unidades); dibujarUnidades(app.data.unidades); } },
    });
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
    for (const m of mapas) {
      for (const [archivo, capa] of [["fronteras", fronteras], ["estados", estados], ["rios", rios], ["lagos", lagos], ["lugares", lugares]]) {
        fetch(`/static/geo/${m.id}/${archivo}.geojson`).then((r) => (r.ok ? r.json() : null)).then((g) => { if (g) capa.addData(g); }).catch(() => {});
      }
    }

    c.niebla = L.layerGroup();
    c.cobertura = L.layerGroup();
    c.contactos = L.layerGroup().addTo(map);
    c.informes = L.layerGroup().addTo(map);
    c.unidades = L.layerGroup().addTo(map);
    c.ordenes = L.layerGroup().addTo(map);
    c.alcances = L.layerGroup(); // se agrega al acercar el mapa (ajustarPorZoom)
    c.seleccion = L.layerGroup().addTo(map);
    c.preview = L.layerGroup().addTo(map);
    c.waypoints = L.layerGroup().addTo(map);
    c.obras = L.layerGroup().addTo(map);
    c.objetivos = L.layerGroup().addTo(map);
    c.ge = L.layerGroup().addTo(map);
    c.meteorologia = L.layerGroup().addTo(map);
    c.misiones = L.layerGroup().addTo(map);
    app.capaActiva = { terreno: true, cobertura: false, niebla: esBando(app.usuario.rol), unidades: true, alcances: true, contactos: true, referencias: true, graficos: true, bases_ven: true, aerodromos: true, objetivos: true, ge: true, meteorologia: true, misiones: true };
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
    map.on("zoomend", () => {
      app.flechas.forEach((f) => f.actualizar());
      ajustarPorZoom();
      if (app.data && !(app.informe && app.informe.activo())) dibujarUnidades(app.data.unidades); // el tamaño de las unidades depende del zoom
    });
  }

  // capas alternables desde la tarjeta "Capas"
  function alternarCapa(nombre, encendida) {
    app.capaActiva[nombre] = encendida;
    const g = app.capas;
    const poner = (capa, on) => (on ? capa.addTo(app.map) : app.map.removeLayer(capa));
    if (nombre === "terreno") $("zona-mapa").classList.toggle("sin-terreno", !encendida);
    else if (nombre === "unidades") { poner(g.unidades, encendida); poner(g.ordenes, encendida); poner(g.obras, encendida); ajustarPorZoom(); if (encendida) app.flechas.forEach((f) => f.actualizar()); }
    else if (nombre === "alcances") ajustarPorZoom();
    else if (nombre === "graficos") poner(app.graficos.capa, encendida);
    else if (nombre === "contactos") { poner(g.contactos, encendida); poner(g.informes, encendida); }
    else if (g[nombre]) poner(g[nombre], encendida);
  }
  document.querySelectorAll("[data-capa]").forEach((chk) => chk.addEventListener("change", () => alternarCapa(chk.dataset.capa, chk.checked)));

  // miniaturas 3D (por defecto) o simbolos militares APP-6: preferencia de cada puesto, guardada en el navegador
  try { app.simbolosApp6 = localStorage.getItem("fenix.simbolosApp6") === "1"; } catch (_) { app.simbolosApp6 = false; }
  $("ver-app6").checked = app.simbolosApp6;
  $("ver-app6").addEventListener("change", () => {
    app.simbolosApp6 = $("ver-app6").checked;
    try { localStorage.setItem("fenix.simbolosApp6", app.simbolosApp6 ? "1" : "0"); } catch (_) { /* sin almacenamiento */ }
    if (app.data && !(app.informe && app.informe.activo())) dibujarUnidades(app.data.unidades);
  });

  async function alClickMapa(e) {
    if (app.dibujando || (app.informe && app.informe.activo())) return;
    const { lat, lng } = e.latlng;
    if (esInstructor() && app.marcandoEvento) { // informe inyectado: el clic es su posicion
      app.eventoPosicion = [lat, lng];
      $("ev-posicion").textContent = `Posición: ${lat.toFixed(3)}, ${lng.toFixed(3)}`;
      return;
    }
    if (esInstructor() && app.colocandoZonaClima) { // meteorologia: el clic es el centro de la zona
      app.colocandoZonaClima = false;
      $("btn-zona-clima").classList.remove("activo");
      const turnos = parseInt($("zc-turnos").value, 10) || 0;
      await enSilencio(api("POST", rutaEsc("/clima/zonas"), {
        tipo: $("zc-tipo").value, lat, lon: lng, radio_km: parseFloat($("zc-radio").value) || 60,
        deriva_rumbo: parseFloat($("zc-rumbo").value) || 0, deriva_kmh: parseFloat($("zc-kmh").value) || 0,
        turnos: turnos > 0 ? turnos : null, nombre: $("zc-nombre").value.trim() || null,
      }).then(() => toast("Zona meteorológica colocada", true)));
      return;
    }
    if (app.misiones && app.misiones.alClickMapa(lat, lng)) return; // planificando una mision: el clic agrega un punto
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
    if (esInstructor() && app.modoObjetivo) {
      app.objetivoCentro = [lat, lng];
      app.modoObjetivo = false;
      $("btn-ob-ubicar").textContent = "Ubicar la zona en el mapa";
      $("ob-centro").textContent = `Zona en ${lat.toFixed(4)}, ${lng.toFixed(4)}.`;
      return;
    }
    if (esAlumno() && app.modoOrden === "construir" && app.unidadOrden) {
      app.obraSitio = [lat, lng];
      dibujarSitioObra();
      return;
    }
    if (esAlumno() && app.modoOrden === "patrullar" && app.unidadOrden) {
      app.patrullaPunto = [lat, lng];
      dibujarPatrulla();
      return;
    }
    if (esAlumno() && app.modoOrden === "interferir" && app.unidadOrden) {
      app.interferenciaPunto = [lat, lng];
      dibujarInterferencia();
      return;
    }
    if (esAlumno() && (app.modoOrden === "mover" || app.modoOrden === "desembarcar") && app.unidadOrden) {
      app.waypoints.push([lat, lng]);
      dibujarWaypoints();
      if (app.modoOrden === "mover") pedirPreview();
      else if (app.data) actualizarNuevaOrden(app.data);
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

  /** Hacia donde apunta la aeronave: su ultimo desplazamiento; si no se movio, su orden pendiente; si no, el ultimo rumbo. */
  function rumboDe(u) {
    const previa = app.posPrevia.get(u.id);
    let r = app.rumbos.get(u.id);
    if (previa && Logica.distanciaKm(previa[0], previa[1], u.lat, u.lon) > 0.1) {
      r = Modelo3d.rumbo(previa[0], previa[1], u.lat, u.lon);
    } else {
      const orden = pendientes().find((o) => o.unidad_id === u.id && (o.tipo === "mover" ? o.waypoints.length : o.tipo === "atacar"));
      const objetivo = orden && orden.tipo === "atacar" ? app.porId.get(orden.objetivo_unidad_id) : null;
      const destino = orden ? (orden.tipo === "mover" ? orden.waypoints[0] : objetivo ? [objetivo.lat, objetivo.lon] : null) : null;
      if (destino) r = Modelo3d.rumbo(u.lat, u.lon, destino[0], destino[1]);
    }
    if (r === undefined) r = u.bando === "rojo" ? 225 : 45;
    app.posPrevia.set(u.id, [u.lat, u.lon]);
    app.rumbos.set(u.id, r);
    return r;
  }

  /** Lado (px) del cuadro de un Su-30 solo: chico con el mapa lejos (no tapa ni se enciman) y grande de cerca. */
  function baseAvion() {
    const zoom = app.map ? app.map.getZoom() : 8;
    return Math.round(app.tamSimbolo * 2.2 * Logica.escalaUnidad(zoom));
  }

  /** Tamaño del simbolo APP-6, con la misma regla (un poco menos de reduccion: debe seguir leyendose). */
  function tamApp6() {
    const zoom = app.map ? app.map.getZoom() : 8;
    return Math.round(app.tamSimbolo * Math.max(0.6, Logica.escalaUnidad(zoom)));
  }

  /** Lo que depende del zoom ademas del tamaño: sin nombres de lejos y anillos de alcance solo de cerca. */
  function ajustarPorZoom() {
    if (!app.map) return;
    const z = app.map.getZoom();
    app.map.getContainer().classList.toggle("z-sin-rotulos", z < Logica.ZOOM_ROTULOS);
    const on = app.capaActiva.alcances && app.capaActiva.unidades && z >= Logica.ZOOM_ALCANCES;
    if (on) app.capas.alcances.addTo(app.map);
    else app.map.removeLayer(app.capas.alcances);
  }

  /** Anillo de alcance de cada unidad desplegada (propias y enemigas a la vista): se ve al acercar el mapa. */
  function dibujarAlcances(unidades) {
    const g = app.capas.alcances;
    g.clearLayers();
    const vista = bandoVista();
    for (const u of Logica.unidadesConAlcance(unidades)) {
      const enemiga = vista ? u.bando !== vista : u.bando === "rojo";
      const color = enemiga ? "#EF233C" : "#3A86FF";
      L.circle([u.lat, u.lon], { radius: u.alcance_km * 1000, color, weight: 1, opacity: 0.6, dashArray: "4 6", fillColor: color, fillOpacity: 0.035, interactive: false }).addTo(g);
    }
  }

  /** Si la unidad se dibuja con su miniatura 3D (y no con el simbolo APP-6). */
  function conMiniatura(u) {
    return !app.simbolosApp6 && (Modelo3d.tieneSprite(u.modelo) || !!Modelo3d.mallaPara(u));
  }

  /** Base aerea sobre su plano real y con el mapa cerca: una ficha pequeña que no tapa la pista. */
  function enPlanoAerodromo(u) {
    return !!app.aerodromos && app.capaActiva.aerodromos && app.map.getZoom() >= app.aerodromos.zoomDetalle && app.aerodromos.cubre(u);
  }

  function iconoUnidad(u, clases = "", rumbo = u.bando === "rojo" ? 225 : 45) {
    // la cota solo se anota cuando no es la media: "rasante" o "alto" importan para leer el mapa
    const cota = u.tipo === "aerea" && !u.en_tierra && u.perfil_actual && u.perfil_actual !== "medio" && u.clase !== "misil_crucero" ? u.perfil_actual : "";
    const sub = [rotuloModelo(u), u.en_tierra ? "en base" : u.mision === "patrulla" ? "patrulla" : "", cota].filter(Boolean).join(" · ");
    const rotulos = `<div class="rotulo">${escapar(u.nombre || "")}</div>` + (sub ? `<div class="rotulo modelo">${escapar(sub)}</div>` : "");
    if (conMiniatura(u) && enPlanoAerodromo(u)) {
      return L.divIcon({
        className: `marca ${clases}`,
        html: `<div class="cuerpo"><div class="ficha-base ${u.bando}">BA</div>${rotulos}</div>`,
        iconSize: [120, 58], iconAnchor: [60, 14],
      });
    }
    if (conMiniatura(u)) {
      // miniatura 3D: el punto de la unidad es el centro de la imagen (la peana, para lo que esta en tierra o agua)
      const av = Modelo3d.marcador({
        modelo: u.modelo, clase: u.clase, rumbo, bando: u.bando, n: u.tipo === "aerea" ? u.aeronaves || 1 : 1, base: baseAvion(),
      });
      const ancho = Math.max(110, av.ancho + 10);
      return L.divIcon({
        className: `marca miniatura ${clases}`,
        html: `<div class="cuerpo"><div class="avion3d" style="height:${av.alto}px">${av.html}</div>${rotulos}</div>`,
        iconSize: [ancho, av.alto + (sub ? 30 : 16)],
        iconAnchor: [ancho / 2, av.alto / 2],
      });
    }
    const sym = new ms.Symbol((u.sidc || "SUGP").padEnd(15, "-"), { size: tamApp6() });
    const tam = sym.getSize();
    const anc = sym.getAnchor();
    // simbolo APP-6 puro (opcion "Simbolos militares" o unidad sin miniatura)
    const ancho = Math.max(110, tam.width + 10);
    return L.divIcon({
      className: `marca ${clases}`,
      html: `<div class="cuerpo">${sym.asSVG()}${rotulos}</div>`,
      iconSize: [ancho, tam.height + (sub ? 30 : 16)],
      iconAnchor: [ancho / 2 + (anc.x - tam.width / 2), anc.y],
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
    for (const g of ["contactos", "cobertura", "niebla", "ordenes", "alcances", "seleccion", "preview", "obras", "objetivos", "ge", "misiones"]) app.capas[g].clearLayers();
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
      if (u.estado === "destruida" || Logica.embarcada(u)) continue; // lo embarcado viaja dentro de su transporte
      vivas.add(u.id);
      const vista = bandoVista();
      const enemiga = vista ? u.bando !== vista : u.bando === "rojo";
      const clases = enemiga ? "enemigo" : "amigo";
      let m = app.markers.get(u.id);
      const mini = conMiniatura(u);
      const rumbo = mini && Modelo3d.gira(u) ? Math.round(rumboDe(u) / 5) * 5 : 0;
      const plano = mini && enPlanoAerodromo(u) ? "p" : "";
      const firma = `${app.editando ? "e" : ""}|${u.sidc}|${u.nombre}|${clases}|${app.tamSimbolo}|${rotuloModelo(u)}|${u.en_tierra ? "t" : ""}${u.mision || ""}${u.perfil_actual || ""}|${u.modelo || ""}|${u.aeronaves || ""}|${rumbo}|${mini ? baseAvion() : `s${tamApp6()}`}|${plano}`;
      // aeronaves estacionadas: sobre la plataforma real de su base cuando se ve el plano del aerodromo
      const estacionada = mini && app.capaActiva.aerodromos && app.aerodromos && app.map.getZoom() >= app.aerodromos.zoomDetalle
        ? app.aerodromos.posicionEstacionada(u, unidades) : null;
      const pos = estacionada || [u.lat, u.lon];
      if (m && m._firma !== firma) { app.capas.unidades.removeLayer(m); m = null; }
      if (!m) {
        m = L.marker(pos, { icon: iconoUnidad(u, clases, rumbo), keyboard: false, draggable: esInstructor() && app.editando }).addTo(app.capas.unidades);
        m._firma = firma;
        m._uid = u.id;
        m.on("dragend", async () => {
          const p = m.getLatLng();
          try { await api("PATCH", rutaEsc(`/unidades/${m._uid}`), { lat: p.lat, lon: p.lng }); } catch (_) {
            const v = app.porId.get(m._uid);
            if (v) m.setLatLng([v.lat, v.lon]); // el servidor lo rechazo (p. ej. terreno invalido): vuelve a su sitio
          }
        });
        m.on("click", (e) => { if (!(app.misiones && app.misiones.alClickUnidad(app.porId.get(u.id)))) seleccionar(u.id, "mapa", !!(e.originalEvent && (e.originalEvent.ctrlKey || e.originalEvent.shiftKey))); });
        app.markers.set(u.id, m);
      } else {
        m.setLatLng(pos);
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
      if (el) { el.classList.toggle("sel", id === app.seleccion); el.classList.toggle("sel-lote", app.lote.has(id)); }
    }
  }

  /** Informes inyectados con posicion (inteligencia, poblacion...): rombo amarillo con la fuente, hasta que caduquen. */
  function dibujarInformes(informes) {
    const g = app.capas.informes;
    g.clearLayers();
    for (const inf of informes) {
      const fuente = inf.fuente || "Informe";
      L.marker([inf.lat, inf.lon], {
        icon: L.divIcon({ className: "informe-marca", iconSize: [90, 36], iconAnchor: [45, 8], html: `<span class="rombo"></span><span class="fuente">${escapar(fuente)}</span>` }),
        keyboard: false,
      }).bindTooltip(`${escapar(fuente)} (turno ${inf.turno}${inf.hasta_turno ? `, vigente hasta el ${inf.hasta_turno}` : ""}): ${escapar(inf.descripcion)}`, { direction: "top", offset: [0, -10] }).addTo(g);
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
    const det = (u) => Logica.deteccionEfectiva(u, claseDe(u)); // un radar apagado solo ve a ojo
    const detectores = unidades.filter((u) => u.estado === "activa" && det(u) && (!vista || u.bando === vista));
    for (const u of detectores) {
      L.polygon(anillo(u.lat, u.lon, det(u) * factor), {
        color: COLOR[u.bando], weight: 1, dashArray: "4 4", fillColor: COLOR[u.bando], fillOpacity: 0.07, interactive: false,
      }).addTo(app.capas.cobertura);
    }
    if (vista) {
      const exterior = [[0.6, -73.4], [12.4, -73.4], [12.4, -59.6], [0.6, -59.6]];
      L.polygon([exterior, ...detectores.map((u) => anillo(u.lat, u.lon, det(u) * factor))], {
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
      } else if (o.tipo === "patrullar" && o.waypoints.length) {
        const [p] = o.waypoints;
        L.polyline([origen, p], { color: "#ffd166", weight: 3, dashArray: "9 7", opacity: 0.95 }).addTo(app.capas.ordenes);
        L.circle(p, { radius: (u.alcance_km || 80) * 1000, color: "#ffd166", weight: 1, dashArray: "6 6", fillOpacity: 0.04, interactive: false })
          .bindTooltip(`Patrulla · ${u.nombre}`).addTo(app.capas.ordenes);
      } else if (o.tipo === "aterrizar") {
        const destino = posicion(o.objetivo_unidad_id);
        if (destino) L.polyline([origen, destino], { color: "#2EC4B6", weight: 3, dashArray: "9 7", opacity: 0.95 }).bindTooltip(`Aterrizar · ${u.nombre}`).addTo(app.capas.ordenes);
      }
    }
    // patrullas en curso: zona que vigilan (solo las conocidas: propias, o todas para el instructor)
    for (const u of data.unidades) {
      if (u.mision !== "patrulla" || u.mision_lat === null || u.mision_lat === undefined || u.estado !== "activa") continue;
      const color = COLOR[u.bando] || "#fff";
      L.circle([u.mision_lat, u.mision_lon], { radius: (u.alcance_km || 80) * 1000, color, weight: 1.5, dashArray: "4 8", fillColor: color, fillOpacity: 0.05, interactive: false })
        .bindTooltip(`Zona de patrulla · ${u.nombre}`, { sticky: true }).addTo(app.capas.ordenes);
    }
  }

  /** Vista previa de la patrulla: punto elegido, zona que vigilaria y distancia desde la aeronave. */
  function dibujarPatrulla() {
    const g = app.capas.preview;
    g.clearLayers();
    const u = app.porId.get(app.unidadOrden);
    if (!u || app.modoOrden !== "patrullar") return;
    if (!app.patrullaPunto) { $("o-patrulla-punto").textContent = "Aún no eligió el punto de patrulla."; return; }
    const [lat, lon] = app.patrullaPunto;
    const d = Logica.distanciaKm(u.lat, u.lon, lat, lon);
    L.polyline([[u.lat, u.lon], app.patrullaPunto], { color: "#ffd166", weight: 3, dashArray: "9 7", interactive: false }).addTo(g);
    L.circle(app.patrullaPunto, { radius: (u.alcance_km || 80) * 1000, color: "#ffd166", weight: 1.5, dashArray: "6 6", fillOpacity: 0.06, interactive: false }).addTo(g);
    L.circleMarker(app.patrullaPunto, { radius: 6, color: "#ffd166", fillColor: "#4a3a10", fillOpacity: 0.9 }).bindTooltip("Punto de patrulla").addTo(g);
    const horas = u.velocidad_kmh ? Math.max(1, Math.ceil(d / u.velocidad_kmh)) : null;
    $("o-patrulla-punto").textContent = `Punto: ${lat.toFixed(3)}, ${lon.toFixed(3)} · a ${d.toFixed(0)} km`
      + (horas ? ` (${horas === 1 ? "llega este turno" : `llega en ${horas} turnos`})` : "") + `. Vigila un radio de ${u.alcance_km} km.`;
  }

  /** Vista previa de la interferencia: alcance del interferidor y zona que cubriria sobre el punto elegido. */
  function dibujarInterferencia() {
    const g = app.capas.preview;
    g.clearLayers();
    const u = app.porId.get(app.unidadOrden);
    const cl = u ? claseDe(u) : null;
    if (!u || !cl || app.modoOrden !== "interferir") return;
    L.circle([u.lat, u.lon], { radius: u.alcance_km * 1000, color: "#c77dff", weight: 1, dashArray: "6 4", fill: false, interactive: false })
      .bindTooltip("Alcance del interferidor").addTo(g);
    if (!app.interferenciaPunto) { $("o-interferencia-info").textContent = "Aún no eligió el centro de la zona."; return; }
    const [lat, lon] = app.interferenciaPunto;
    const d = Logica.distanciaKm(u.lat, u.lon, lat, lon);
    L.circle(app.interferenciaPunto, { radius: cl.interferencia_km * 1000, color: "#c77dff", weight: 2, dashArray: "2 6", fillColor: "#c77dff", fillOpacity: 0.12, interactive: false }).addTo(g);
    L.circleMarker(app.interferenciaPunto, { radius: 6, color: "#c77dff", fillColor: "#2a1540", fillOpacity: 0.9 }).bindTooltip("Centro de la interferencia").addTo(g);
    $("o-interferencia-info").textContent = `Centro: ${lat.toFixed(3)}, ${lon.toFixed(3)} · a ${d.toFixed(0)} km · radio ${cl.interferencia_km} km`
      + (d > u.alcance_km ? ` (fuera del alcance de ${u.alcance_km} km)` : "") + ".";
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
    let circuloDeteccion = null;
    if (u.deteccion_km > 0) {
      circuloDeteccion = L.circle([u.lat, u.lon], { radius: u.deteccion_km * 1000, color: "#2EC4B6", weight: 1, dashArray: "1 6", fill: false, interactive: false })
        .bindTooltip("Radio de detección (sin clima ni terreno)").addTo(g);
    }
    if (Logica.muestraCobertura(u, claseDe(u))) dibujarCobertura(u, circuloDeteccion);
    if (u.velocidad_kmh > 0) {
      L.circle([u.lat, u.lon], { radius: u.velocidad_kmh * 1000, color: "#81d4fa", weight: 1, dashArray: "2 5", fill: false, interactive: false })
        .bindTooltip("Avance máximo en 1 turno (en llano, despejado)").addTo(g);
    }
  }

  /** Cobertura del sensor seleccionado segun el relieve (GET .../cobertura): hasta donde ve una aeronave a baja cota
   * y a cota media; las entradas del poligono son las sombras de las montañas y el horizonte. Reemplaza al circulo
   * de deteccion (que no sabe del relieve). Se cachea por posicion, emision y turno. */
  function dibujarCobertura(u, circuloDeteccion) {
    const clave = `${u.id}|${u.lat}|${u.lon}|${u.emitiendo}|${app.data ? app.data.escenario.turno_actual : 0}`;
    app.coberturas = app.coberturas || new Map();
    const pintar = (c) => {
      if (!c || !c.disponible || app.seleccion !== u.id) return;
      const g = app.capas.seleccion;
      if (circuloDeteccion) g.removeLayer(circuloDeteccion);
      const capas = [
        ["medio", "#2EC4B6", "6 3", 0.05, "a cota media (1 500 m)"],
        ["rasante", "#ff9f1c", "3 4", 0.09, "a baja cota (rasante, 60 m)"],
      ];
      for (const [perfil, color, guiones, relleno, texto] of capas) {
        const p = c.perfiles[perfil];
        if (!p) continue;
        L.polygon(p.poligono, { color, weight: 1.5, dashArray: guiones, fillColor: color, fillOpacity: relleno, interactive: true })
          .bindTooltip(`Ve aeronaves ${texto} hasta aquí (máx. ${p.alcance_km} km). Las entradas son sombras del relieve o el horizonte.`, { sticky: true })
          .addTo(g);
      }
    };
    if (app.coberturas.has(clave)) return pintar(app.coberturas.get(clave));
    api("GET", rutaEsc(`/unidades/${u.id}/cobertura`), undefined, true)
      .then((c) => { app.coberturas.set(clave, c); pintar(c); })
      .catch(() => {});
  }

  // ---------- seleccion ----------
  /** Ctrl/Shift+clic: suma o quita la unidad de la seleccion multiple (solo propias que acepten ordenes del puesto). */
  function alternarEnLote(id) {
    const u = app.porId.get(id);
    if (!u || !esAlumno() || u.bando !== app.usuario.rol || u.estado !== "activa" || u.tipo === "base") return false;
    if (!Logica.puestoPuede(puestoActual(), Logica.funcionDeOrden(u, null, claseDe(u)))) return false;
    if (!app.unidadOrden) { seleccionar(id, "lista"); return true; }
    if (id === app.unidadOrden) return true;
    if (app.lote.has(id)) app.lote.delete(id); else app.lote.add(id);
    if (app.data) { actualizarNuevaOrden(app.data); renderOOBSeleccion(); marcarSeleccionEnMapa(); }
    return true;
  }

  function seleccionar(id, origen = "lista", modificador = false) {
    if (modificador && alternarEnLote(id)) return;
    const u = app.porId.get(id);
    const c = app.contactosPorId.get(id);
    if (!u && !c) return;
    const rol = app.usuario.rol;
    if (esAlumno()) {
      const propia = u && u.bando === rol;
      const objetivo = $("o-objetivo");
      if (origen === "mapa" && (app.modoOrden === "atacar" || app.modoOrden === "lanzar") && !propia && u && u.estado === "activa") {
        objetivo.value = String(id);
      } else if (origen === "mapa" && app.modoOrden === "apoyar" && propia && app.unidadOrden && id !== app.unidadOrden && u.tipo !== "base") {
        objetivo.value = String(id);
      } else if (propia && Logica.operaAeronaves(u)) {
        app.baseSeleccionada = id;
      } else if (propia && u.estado === "activa" && u.tipo !== "base" && Logica.puestoPuede(puestoActual(), Logica.funcionDeOrden(u, null, claseDe(u)))) {
        if (app.unidadOrden !== id) { app.unidadOrden = id; app.lote.clear(); app.waypoints = []; app.obraSitio = null; app.patrullaPunto = null; app.interferenciaPunto = null; dibujarWaypoints(); if (app.modoOrden === "construir") dibujarSitioObra(); }
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
    b.addEventListener("click", (e) => { const mod = e.ctrlKey || e.shiftKey; seleccionar(u.id, "lista", mod); if (u.estado !== "destruida" && !mod) app.map.panTo([u.lat, u.lon]); });
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
    $("oob-titulo").textContent = vista ? `Orden de batalla · ${nombreDeBando(vista)}` : "Orden de batalla · Ambos bandos";
    const bandos = vista ? [vista] : ["azul", "rojo"];
    const filtrar = (lista) => Logica.filtrarUnidades(lista, app.filtroOOB);
    for (const b of bandos) {
      const propias = filtrar(data.unidades.filter((u) => u.bando === b));
      if (vista) { cont.appendChild(ramas(propias)); continue; }
      const det = document.createElement("details");
      det.open = true;
      const sum = document.createElement("summary");
      sum.className = b;
      sum.append(nombreDeBando(b));
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = `${propias.length} un.`;
      sum.appendChild(n);
      det.appendChild(sum);
      det.appendChild(ramas(propias));
      cont.appendChild(det);
    }
    if (vista) {
      const enemigas = filtrar(data.unidades.filter((u) => u.bando !== vista));
      const contactos = filtrar(data.contactos || []);
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
    document.querySelectorAll(".oob-item").forEach((b) => {
      b.classList.toggle("sel", b.dataset.id === String(app.seleccion));
      b.classList.toggle("sel-lote", app.lote.has(parseInt(b.dataset.id, 10)));
    });
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
      if (cl.emisor && !oculto) extra.push(dato("Radar", u.emitiendo === false ? "Apagado (silencio)" : "Emitiendo"));
      if (cl.defensa_aerea && !oculto) extra.push(dato("Fuego automático", u.fuego_libre === false ? "Retenido" : "Libre"));
      if (cl.stock_max && !oculto && u.stock_combustible !== null && u.stock_combustible !== undefined) {
        extra.push(dato("Existencias", `${Math.round(u.stock_combustible)} comb. · ${Math.round(u.stock_municion)} mun. (máx. ${cl.stock_max})`));
      }
    }
    const modelo = Logica.modeloDe(u, app.catalogo && app.catalogo.modelos);
    if (app.data && (app.data.clima_zonas || []).length) {
      const local = Logica.climaEn(u.lat, u.lon, app.data.escenario.clima, app.data.clima_zonas);
      if (local !== app.data.escenario.clima) extra.push(dato("Clima local", `${Logica.etiquetaClima(local)} (zona meteorológica)`));
    }
    const vuelo = Logica.esMisil(u) && !oculto ? Logica.textoMisil(u, app.data ? app.data.unidades : [])
      : app.data ? Logica.situacionDeVuelo(u, app.data.unidades) : null;
    if (vuelo) extra.push(`<div class="ancho-completo"><dt>Situación</dt><dd>${escapar(vuelo)}</dd></div>`);
    if (cl && cl.plazas_aeronaves && !oculto && app.data) {
      const abordo = Logica.estacionadasEn(u, app.data.unidades);
      extra.push(dato("Aeronaves a bordo", `${abordo.reduce((s, x) => s + Math.max(1, x.aeronaves || 1), 0)} de ${cl.plazas_aeronaves} plazas`));
      extra.push(`<div class="ancho-completo"><dt>Daño por partes</dt><dd>${escapar(Logica.textoPartesBase(u))}${(u.dano_pista || 0) >= Logica.PISTA_INOPERATIVA ? " · <b>pista inoperativa</b>" : ""}</dd></div>`);
      extra.push(dato("Refugios reforzados", `${u.refugios || 0} (protegen a los primeros ${u.refugios || 0} grupos estacionados; ${abordo.length} a bordo)`));
    }
    if (cl && cl.lanza_misiles && !oculto) extra.push(dato("Misiles de crucero", `${Logica.misilesDisponibles(u)} listos (25 % de munición cada uno)`));
    if (Logica.embarcada(u) && app.data) {
      const t = app.porId.get(u.transporte_id);
      extra.push(`<div class="ancho-completo"><dt>Situación</dt><dd>A bordo de ${escapar(t ? t.nombre : "un transporte")}: viaja con él y no puede recibir órdenes hasta desembarcar.</dd></div>`);
    }
    if (Logica.esTransporte(u) && !oculto && app.data) {
      const carga = Logica.aBordo(u, app.data.unidades);
      extra.push(dato("Tropas a bordo", carga.length ? `${carga.map((x) => x.nombre).join(", ")} (${carga.length}/${Logica.CAPACIDAD_TRANSPORTE[u.clase]})` : `ninguna (capacidad ${Logica.CAPACIDAD_TRANSPORTE[u.clase]})`));
    }
    if (u.perfil_actual) extra.push(dato("Perfil de vuelo", u.en_tierra ? `${Logica.textoPerfil(u.perfil_actual)} al despegar` : Logica.textoPerfil(u.perfil_actual)));
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
    const interferida = app.porId.get(app.seleccion) ? Logica.textoInterferido(u, cl, app.data && app.data.interferencias) : "";
    if (interferida) notas.push(interferida);
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
      + (cl && cl.stock_max && !oculto && u.stock_combustible !== null && u.stock_combustible !== undefined
        ? barra("Combustible en depósito", Logica.pctStock(u.stock_combustible, cl)) + barra("Munición en depósito", Logica.pctStock(u.stock_municion, cl))
        : "")
      + `<dl class="det-datos">${dato("Clase", u.clase || u.tipo)}${dato("Terreno", u.terreno || "?")}`
      + `${dato("Velocidad", u.velocidad_kmh === null ? "?" : u.velocidad_kmh + " km/h")}${dato("Alcance", km(u.alcance_km))}`
      + `${dato("Detección", km(u.deteccion_km))}${dato("Autonomía", km(u.autonomia_km))}${extra.join("")}</dl>`
      + notas.map((n) => `<p class="nota">${escapar(n)}</p>`).join("")
      + (!oculto && app.porId.get(app.seleccion) && cl && u.estado === "activa" && puedeDefensa(u)
        ? (cl.emisor ? `<button id="btn-emision" class="mini ${u.emitiendo === false ? "primario" : "secundario"}" type="button">${u.emitiendo === false ? "Encender radar" : "Apagar radar (silencio de emisiones)"}</button>` : "")
          + (cl.defensa_aerea ? `<button id="btn-fuego" class="mini secundario" type="button">${u.fuego_libre === false ? "Liberar el fuego automático" : "Retener el fuego automático"}</button>` : "")
        : "")
      + (!oculto && app.porId.get(app.seleccion) && u.estado === "activa" && (u.perfiles_permitidos || []).length > 1 && puedeDefensa(u)
        ? `<div class="perfil-vuelo" role="group" aria-label="Perfil de vuelo"><span>Perfil de vuelo</span>${u.perfiles_permitidos.map((p) =>
          `<button type="button" class="mini ${p === u.perfil_actual ? "primario" : "secundario"}" data-perfil="${p}" title="${escapar(Logica.PERFILES_VUELO[p].ayuda)}">${escapar(Logica.PERFILES_VUELO[p].nombre)}</button>`).join("")}</div>`
          + `<p class="ayuda">${escapar(Logica.PERFILES_VUELO[u.perfil_actual] ? Logica.PERFILES_VUELO[u.perfil_actual].ayuda : "")} Rige de inmediato.</p>`
        : "")
      + (esInstructor() && app.porId.get(app.seleccion) ? '<button id="btn-eliminar-unidad" class="peligro mini" type="button">Eliminar unidad del escenario</button>' : "");
    const emision = $("btn-emision");
    if (emision) emision.addEventListener("click", () => enSilencio(api("POST", rutaEsc(`/unidades/${u.id}/defensa`), { emitiendo: u.emitiendo === false })));
    const fuego = $("btn-fuego");
    if (fuego) fuego.addEventListener("click", () => enSilencio(api("POST", rutaEsc(`/unidades/${u.id}/defensa`), { fuego_libre: u.fuego_libre === false })));
    cont.querySelectorAll("[data-perfil]").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.perfil !== u.perfil_actual) enSilencio(api("POST", rutaEsc(`/unidades/${u.id}/perfil`), { perfil_vuelo: b.dataset.perfil }));
    }));
    const eliminar = $("btn-eliminar-unidad");
    if (eliminar) {
      eliminar.addEventListener("click", async () => {
        if (!window.confirm(`¿Eliminar «${u.nombre}» del escenario? Esta acción no se puede deshacer.`)) return;
        try { await api("DELETE", rutaEsc(`/unidades/${u.id}`)); toast("Unidad eliminada", true); } catch (_) { /* el toast ya explica el motivo */ }
      });
    }
  }

  /** Puede encender/apagar el radar o liberar/retener el fuego de esta unidad (instructor, o el puesto que la conduce). */
  function puedeDefensa(u) {
    if (esInstructor()) return true;
    return esAlumno() && u.bando === app.usuario.rol && Logica.puestoPuede(puestoActual(), Logica.funcionDeOrden(u, "defensa", claseDe(u)));
  }

  // ---------- aviacion: envio de grupos de caza ----------
  function actualizarAviacion(data) {
    if (!esAlumno() || !app.catalogo) return;
    const rol = bandoVista() || app.usuario.rol;
    const bases = Logica.basesAereasPropias(data.unidades, rol);
    const tope = (app.catalogo.aeronaves || {}).max_bando || 24;
    const usadas = Logica.aeronavesComprometidas(data.unidades, data.ordenes, rol, false, app.catalogo);
    $("aviacion-tope").textContent = `${usadas}/${tope}`;
    const puede = data.escenario.estado === "activo" && data.escenario.fase === "decision" && bases.length > 0;
    $("btn-enviar-caza").disabled = !puede;
    $("aviacion-ayuda").textContent = bases.length
      ? "Elija el caza, el dron o el avión de guerra electrónica (con imagen y datos) y la base de la que despegan. El grupo aparece al resolverse el turno; los drones tienen su propio tope."
      : "Su bando no tiene una base aérea activa: pídale al instructor que coloque una desde la capa «Bases aéreas y aeródromos».";
  }
  $("btn-enviar-caza").addEventListener("click", () => app.aviacion && app.aviacion.abrirDespegue(app.baseSeleccionada));

  // ---------- nueva orden y cola de ordenes ----------
  function actualizarNuevaOrden(data) {
    if (!esAlumno()) return;
    const bando = bandoVista() || app.usuario.rol;
    const propias = Logica.unidadesDelPuesto(data.unidades, bando, puestoActual(), claseDe);
    if (app.unidadOrden && !propias.some((u) => u.id === app.unidadOrden)) app.unidadOrden = null;
    for (const id of [...app.lote]) if (!propias.some((u) => u.id === id) || id === app.unidadOrden) app.lote.delete(id);
    $("o-lote").hidden = !app.unidadOrden || app.lote.size === 0;
    if (app.lote.size) $("o-lote-texto").textContent = `${app.lote.size + 1} unidades seleccionadas: la orden se emite a todas.`;
    const sel = app.porId.get(app.seleccion);
    const ajena = sel && sel.bando === bando && sel.estado === "activa" && sel.tipo !== "base" && !propias.some((p) => p.id === sel.id)
      ? Logica.textoPuestoAjeno(sel, claseDe(sel)) : "";
    $("o-puesto").hidden = !ajena;
    $("o-puesto").textContent = ajena;
    const u = app.porId.get(app.unidadOrden);
    const cl = u ? claseDe(u) : null;
    const puedeConstruir = !!(cl && cl.construye);
    $("modo-construir").hidden = !puedeConstruir;
    if (app.modoOrden === "construir" && !puedeConstruir) app.modoOrden = "mover";
    const aerea = !!(u && u.tipo === "aerea");
    const puedeAterrizar = aerea && !u.en_tierra;
    $("modo-patrullar").hidden = !aerea;
    $("modo-aterrizar").hidden = !puedeAterrizar;
    const interfiere = Logica.puedeInterferir(u, cl);
    $("modo-interferir").hidden = !interfiere;
    const lanza = Logica.puedeLanzarMisiles(u, cl);
    $("modo-lanzar").hidden = !lanza;
    const transportes = u ? Logica.transportesCercanos(u, data.unidades, claseDe) : [];
    const puedeEmbarcar = transportes.length > 0;
    const puedeDesembarcar = !!u && Logica.esTransporte(u) && Logica.aBordo(u, data.unidades).length > 0;
    $("modo-embarcar").hidden = !puedeEmbarcar;
    $("modo-desembarcar").hidden = !puedeDesembarcar;
    if (app.modoOrden === "embarcar" && !puedeEmbarcar) app.modoOrden = "mover";
    if (app.modoOrden === "desembarcar" && !puedeDesembarcar) app.modoOrden = "mover";
    if (app.modoOrden === "patrullar" && !aerea) app.modoOrden = "mover";
    if (app.modoOrden === "aterrizar" && !puedeAterrizar) app.modoOrden = "mover";
    if (app.modoOrden === "interferir" && !interfiere) app.modoOrden = "mover";
    if (app.modoOrden === "lanzar" && !lanza) app.modoOrden = "mover";
    const espera = u && u.en_tierra && u.espera_restante > 0;
    $("o-espera").hidden = !espera;
    if (espera) $("o-espera").textContent = `En tierra: podrá despegar en ${u.espera_restante} turno${u.espera_restante === 1 ? "" : "s"}; hasta entonces no acepta órdenes de vuelo.`;
    $("orden-unidad").textContent = u ? u.nombre : "elija una unidad";
    $("btn-emitir").disabled = !u || data.escenario.estado !== "activo" || data.escenario.fase !== "decision";
    document.querySelectorAll(".modos button").forEach((b) => b.classList.toggle("activo", b.dataset.modo === app.modoOrden));
    $("o-mover").hidden = app.modoOrden !== "mover" && app.modoOrden !== "desembarcar";
    $("o-construir").hidden = app.modoOrden !== "construir";
    $("o-patrullar").hidden = app.modoOrden !== "patrullar";
    $("o-aterrizar").hidden = app.modoOrden !== "aterrizar";
    $("o-interferir").hidden = app.modoOrden !== "interferir";
    if (app.modoOrden === "aterrizar" && u) {
      const opciones = Logica.opcionesDeAterrizaje(u, data.unidades);
      llenarSelect($("o-base"), opciones.map((o) => [o.base.id, `${o.base.nombre} · ${Math.round(o.km)} km`]));
      const elegida = opciones.find((o) => String(o.base.id) === $("o-base").value);
      $("o-aterrizaje-info").textContent = !opciones.length
        ? "No hay una base propia con plazas libres para este grupo."
        : elegida.llegaEsteTurno
          ? `Llega y aterriza este turno (${Math.round(elegida.km)} km).`
          : `A ${Math.round(elegida.km)} km: tardará ${elegida.turnos} turnos en llegar.`
            + (elegida.alcanzaCombustible ? "" : ` Necesita ~${Math.round(elegida.combustibleNecesario)} % de combustible y tiene ${Math.round(u.combustible)} %.`);
    }
    $("o-objetivo-box").hidden = ["mover", "construir", "patrullar", "aterrizar", "interferir", "embarcar", "desembarcar"].includes(app.modoOrden);
    $("o-lanzar").hidden = app.modoOrden !== "lanzar";
    $("o-embarcar").hidden = app.modoOrden !== "embarcar";
    $("o-desembarcar").hidden = app.modoOrden !== "desembarcar";
    if (app.modoOrden === "embarcar" && u) {
      llenarSelect($("o-transporte"), transportes.map((x) => [x.t.id, `${x.t.nombre} · ${x.km.toFixed(1)} km · ${Logica.aBordo(x.t, data.unidades).length}/${Logica.CAPACIDAD_TRANSPORTE[x.t.clase]} a bordo`]));
      $("o-embarcar-info").textContent = "La unidad sube al resolverse el turno.";
    }
    if (app.modoOrden === "desembarcar" && u) {
      const carga = Logica.aBordo(u, data.unidades).map((x) => x.nombre).join(", ");
      $("o-desembarcar-info").textContent = `A bordo: ${carga}. ${app.waypoints.length ? `Punto de desembarco: ${app.waypoints[app.waypoints.length - 1].map((v) => v.toFixed(3)).join(", ")}.` : "Marque la ruta y el punto de desembarco en el mapa."}`;
    }
    if (app.modoOrden === "atacar" || app.modoOrden === "apoyar" || app.modoOrden === "lanzar") {
      const lista = Logica.objetivosDisponibles(data.unidades, app.usuario.rol, app.modoOrden, app.unidadOrden);
      llenarSelect($("o-objetivo"), lista.map((x) => [x.id, x.nombre]));
      $("o-objetivo-ayuda").textContent = app.modoOrden === "apoyar"
        ? "Unidad propia a apoyar (dentro de su alcance; consume 10% de munición). También puede hacer clic en el mapa."
        : app.modoOrden === "lanzar"
          ? (lista.length ? "Blanco de los misiles: una unidad enemiga detectada en tierra o en el mar (a menos de 1 000 km). También puede hacer clic en el mapa." : "No hay blancos detectados.")
          : lista.length ? "Solo puede atacar unidades detectadas por su bando. También puede hacer clic en el mapa." : "No hay enemigos detectados.";
    }
    if (app.modoOrden === "atacar") {
      const obj = app.porId.get(parseInt($("o-objetivo").value, 10));
      const base = !!obj && Logica.operaAeronaves(obj);
      $("o-parte-fila").hidden = !base;
      if (base && !$("o-parte").options.length) llenarSelect($("o-parte"), Logica.PARTES_BASE);
    } else $("o-parte-fila").hidden = true;
    if (app.modoOrden === "lanzar" && u) {
      const max = Logica.misilesDisponibles(u);
      const actual = parseInt($("o-misiles").value, 10);
      llenarSelect($("o-misiles"), Array.from({ length: max }, (_, i) => [i + 1, `${i + 1} misil${i ? "es" : ""}`]));
      if (actual && actual <= max) $("o-misiles").value = String(actual);
      $("o-lanzar-info").textContent = max
        ? `Munición ${Math.round(u.municion)} %: hasta ${max} misil${max === 1 ? "" : "es"} en esta salva.`
        : "Sin munición suficiente para un misil (25 % cada uno): reabastezca en un puerto o depósito.";
    }
  }

  document.querySelectorAll(".modos button").forEach((b) => b.addEventListener("click", () => {
    app.modoOrden = b.dataset.modo;
    app.capas.preview.clearLayers();
    if (app.modoOrden === "mover") pedirPreview();
    else if (app.modoOrden === "construir") dibujarSitioObra();
    else if (app.modoOrden === "patrullar") dibujarPatrulla();
    else if (app.modoOrden === "interferir") dibujarInterferencia();
    if (app.data) actualizarNuevaOrden(app.data);
  }));
  $("btn-limpiar-wp").addEventListener("click", () => { app.waypoints = []; dibujarWaypoints(); });
  $("o-lote-limpiar").addEventListener("click", () => { app.lote.clear(); if (app.data) { actualizarNuevaOrden(app.data); renderOOBSeleccion(); marcarSeleccionEnMapa(); } });
  $("o-objetivo").addEventListener("change", () => { if (app.data) actualizarNuevaOrden(app.data); });

  $("btn-emitir").addEventListener("click", async () => {
    const unidad_id = app.unidadOrden;
    if (!unidad_id) return toast("Seleccione una unidad propia que pueda recibir órdenes.");
    const cuerpo = { unidad_id, tipo: app.modoOrden, waypoints: [], objetivo_unidad_id: null };
    if (app.modoOrden === "mover") {
      if (!app.waypoints.length) return toast("Marque al menos un waypoint en el mapa.");
      cuerpo.waypoints = app.waypoints;
    } else if (app.modoOrden === "desembarcar") {
      if (!app.waypoints.length) return toast("Marque en el mapa la ruta y el punto de desembarco (el último).");
      cuerpo.waypoints = app.waypoints;
    } else if (app.modoOrden === "embarcar") {
      const t = parseInt($("o-transporte").value, 10);
      if (!t) return toast("Elija el transporte.");
      cuerpo.objetivo_unidad_id = t;
    } else if (app.modoOrden === "patrullar") {
      if (!app.patrullaPunto) return toast("Haga clic en el mapa donde quiere que patrulle.");
      cuerpo.waypoints = [app.patrullaPunto];
    } else if (app.modoOrden === "interferir") {
      if (!app.interferenciaPunto) return toast("Haga clic en el mapa en el centro de la zona a interferir.");
      cuerpo.waypoints = [app.interferenciaPunto];
    } else if (app.modoOrden === "aterrizar") {
      const base = parseInt($("o-base").value, 10);
      if (!base) return toast("Elija una base propia con plazas libres.");
      cuerpo.objetivo_unidad_id = base;
    } else if (app.modoOrden === "construir") {
      if (!app.obraSitio) return toast("Haga clic en el mapa, sobre el río, donde quiere construir.");
      cuerpo.detalle = $("o-obra").value;
      cuerpo.waypoints = [app.obraSitio];
    } else if (app.modoOrden === "lanzar") {
      const obj = parseInt($("o-objetivo").value, 10);
      if (!obj) return toast("Elija el blanco de los misiles.");
      const n = parseInt($("o-misiles").value, 10);
      if (!n) return toast("Sin munición suficiente para lanzar.");
      cuerpo.objetivo_unidad_id = obj;
      cuerpo.misiles = n;
    } else {
      const obj = parseInt($("o-objetivo").value, 10);
      if (!obj) return toast("Elija una unidad objetivo.");
      cuerpo.objetivo_unidad_id = obj;
      if (app.modoOrden === "atacar" && !$("o-parte-fila").hidden && $("o-parte").value) cuerpo.parte = $("o-parte").value;
    }
    try {
      if (app.lote.size) {
        const r = await api("POST", rutaEsc("/ordenes/lote"), { unidad_ids: [unidad_id, ...app.lote], formacion: $("o-formacion").checked, orden: cuerpo });
        const fallas = r.resultados.filter((x) => !x.ok);
        toast(`Orden emitida a ${r.emitidas} de ${r.resultados.length} unidades` + (fallas.length ? `. ${fallas.map((f) => `${(app.porId.get(f.unidad_id) || {}).nombre || f.unidad_id}: ${f.detalle}`).join(" · ")}` : ""), fallas.length === 0);
      } else {
        await api("POST", rutaEsc("/ordenes"), cuerpo);
        toast("Orden emitida", true);
      }
      app.waypoints = [];
      app.obraSitio = null;
      app.patrullaPunto = null;
      app.interferenciaPunto = null;
      dibujarWaypoints();
      app.capas.preview.clearLayers();
      $("o-sitio").textContent = "";
      $("o-patrulla-punto").textContent = "";
      $("o-interferencia-info").textContent = "";
    } catch (_) { /* toast ya mostrado */ }
  });

  const CHIP = { pendiente: ["pend", "PENDIENTE"], resuelta: ["res", "RESUELTA"], rechazada: ["rech", "RECHAZADA"] };
  function textoOrden(o) {
    const obj = app.porId.get(o.objetivo_unidad_id) || app.contactosPorId.get(o.objetivo_unidad_id);
    const nombreObj = obj ? obj.nombre : `#${o.objetivo_unidad_id}`;
    if (o.tipo === "mover") return `Mover (${o.waypoints.length} waypoint${o.waypoints.length === 1 ? "" : "s"})`;
    if (o.tipo === "embarcar") return `Embarcar en ${nombreObj}`;
    if (o.tipo === "desembarcar") return `Desembarcar en (${o.waypoints[o.waypoints.length - 1][0].toFixed(2)}, ${o.waypoints[o.waypoints.length - 1][1].toFixed(2)})`;
    if (o.tipo === "construir") return `Construir ${o.detalle || "obra"}`;
    if (o.tipo === "despegar") return Logica.textoDespegue(o, app.catalogo && app.catalogo.modelos);
    if (o.tipo === "patrullar") return `Patrullar (${o.waypoints[0][0].toFixed(2)}, ${o.waypoints[0][1].toFixed(2)})`;
    if (o.tipo === "interferir") return `Interferir sobre (${o.waypoints[0][0].toFixed(2)}, ${o.waypoints[0][1].toFixed(2)})`;
    if (o.tipo === "aterrizar") {
      const b = app.porId.get(o.objetivo_unidad_id);
      return `Aterrizar en ${b ? b.nombre : "la base"}${o.detalle === "combustible critico" ? " (combustible crítico)" : ""}`;
    }
    if (o.tipo === "atacar" && o.detalle === "intercepcion") return `Interceptar a ${nombreObj}`;
    if (o.tipo === "atacar" && o.detalle === "impacto") return `Impacto de misiles en ${nombreObj}`;
    if (o.tipo === "atacar" && o.detalle === "defensa aerea") return `Defensa aérea contra ${nombreObj}`;
    if (o.tipo === "atacar" && ["pista", "plataforma", "combustible"].includes(o.detalle)) return `Atacar ${nombreObj} (${o.detalle === "combustible" ? "depósito de combustible" : o.detalle})`;
    if (o.tipo === "lanzar") {
      let n = 1;
      try { n = JSON.parse(o.detalle || "{}").misiles || 1; } catch (_) { /* detalle vacio */ }
      return `Lanzar ${n} misil${n === 1 ? "" : "es"} de crucero contra ${nombreObj}`;
    }
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
      // autor registrado (usuario y puesto al emitirla); las ordenes automaticas del motor no lo tienen
      if (o.autor) {
        const a = document.createElement("span");
        a.className = "autor";
        a.textContent = ` · ${o.autor}${o.autor_puesto ? " (" + Logica.puestoDe(o.autor_puesto).sigla + ")" : ""}`;
        a.title = `Emitida por ${o.autor}${o.autor_puesto ? ", puesto " + Logica.etiquetaPuesto(o.autor_puesto) : ""}`;
        s.appendChild(a);
      }
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
    b.textContent = Logica.etiquetaBando(rol, data.vista, esAlumno() ? puestoActual() : null);
    const bando = bandoVista();
    b.className = bando || "";
    actualizarReloj();

    if (esInstructor()) {
      const enfoque = document.activeElement;
      const set = (id, fn) => { if (enfoque !== $(id)) fn($(id)); };
      set("cfg-clima", (e) => { e.value = esc.clima; });
      for (const [id, campo] of [["dir-niebla", "niebla"], ["dir-logistica", "logistica"], ["dir-clima", "efectos_clima"], ["dir-fuego", "fuego_automatico"]]) {
        set(id, (e) => { e.checked = esc[campo] !== false; });
      }
      set("cfg-limite", (e) => { e.value = esc.limite_decision_seg || 0; });
      set("cfg-hora", (e) => { e.value = `${String(Math.floor(esc.hora_inicio_min / 60)).padStart(2, "0")}:${String(esc.hora_inicio_min % 60).padStart(2, "0")}`; });
      set("cfg-nacion-azul", (e) => { e.value = esc.nacion_azul || ""; });
      set("cfg-nacion-rojo", (e) => { e.value = esc.nacion_rojo || ""; });
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
      el.querySelector(".rotulo-bando").textContent = nombreDeBando(bando).toUpperCase();
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
    renderObjetivos(data);
    actualizarNuevaOrden(data);
    actualizarAviacion(data);
    if (app.misiones) app.misiones.render(data);
    if (app.aerodromos) app.aerodromos.actualizar(data.unidades);
    llenarSelect($("adj-unidad"), data.unidades.map((u) => [u.id, `${u.nombre} (${u.bando})`]));
    if (app.informe && app.informe.activo()) return; // durante la repeticion no se pisa el mapa

    dibujarUnidades(data.unidades);
    dibujarAlcances(data.unidades);
    ajustarPorZoom();
    dibujarContactos(data.contactos || []);
    dibujarInformes(data.informes || []);
    dibujarObras(data.obras || []);
    dibujarInterferencias(data.interferencias || []);
    dibujarZonasClima(data.clima_zonas || []);
    dibujarObjetivos(data.objetivos || []);
    dibujarCoberturaYNiebla(data.unidades, data.escenario.clima);
    dibujarOrdenes(data);
    dibujarSeleccion();
    if (!app.encuadrado && data.unidades.length) {
      const lugar = app.urlInicial && app.urlInicial.lugar;
      if (lugar) app.map.setView([lugar.lat, lugar.lon], lugar.zoom);
      else app.map.fitBounds(data.unidades.map((u) => [u.lat, u.lon]), { padding: [80, 80], maxZoom: 10 });
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

  // ---------- guerra electronica: zonas de interferencia vigentes ----------
  function dibujarInterferencias(zonas) {
    const g = app.capas.ge;
    g.clearLayers();
    const vista = bandoVista();
    for (const z of zonas) {
      const propia = !vista || z.bando === vista;
      const quien = z.bando === "azul" ? "Azul" : "Rojo";
      const texto = `Interferencia electrónica (${quien}) · radio ${Math.round(z.radio_km)} km · vigente hasta resolver el turno ${z.turno + 1}`
        + (propia && vista ? "" : vista ? " · sus sensores, antiaérea y drones están degradados aquí" : "");
      L.circle([z.lat, z.lon], { radius: z.radio_km * 1000, color: "#c77dff", weight: 2, dashArray: "2 7", fillColor: COLOR[z.bando] || "#c77dff", fillOpacity: 0.1, interactive: true })
        .bindTooltip(texto, { sticky: true }).addTo(g);
      L.marker([z.lat, z.lon], {
        icon: L.divIcon({ className: "ge-zona", iconSize: [30, 18], iconAnchor: [15, 9], html: '<span style="display:block;font:700 10px system-ui;color:#fff;background:#7b2cbf;border:1px solid #e0aaff;border-radius:3px;text-align:center;line-height:16px">GE</span>' }),
        keyboard: false, interactive: false,
      }).addTo(g);
    }
  }

  const COLOR_ZONA_CLIMA = { nublado: "#9aa5b1", lluvia: "#3b7dd8", tormenta: "#7b2cbf" };
  function dibujarZonasClima(zonas) {
    const g = app.capas.meteorologia;
    g.clearLayers();
    for (const z of zonas) {
      const color = COLOR_ZONA_CLIMA[z.tipo] || "#9aa5b1";
      L.circle([z.lat, z.lon], { radius: z.radio_km * 1000, color, weight: 2, dashArray: "6 6", fillColor: color, fillOpacity: z.tipo === "tormenta" ? 0.28 : 0.18, interactive: true })
        .bindTooltip(Logica.textoZonaClima(z), { sticky: true }).addTo(g);
      if (z.deriva_kmh > 0) { // flecha de deriva: hacia donde se mueve en las proximas 3 horas
        const r = (z.deriva_rumbo * Math.PI) / 180, km = z.deriva_kmh * 3;
        const fin = [z.lat + (km * Math.cos(r)) / 110.574, z.lon + (km * Math.sin(r)) / (111.32 * Math.cos((z.lat * Math.PI) / 180))];
        L.polyline([[z.lat, z.lon], fin], { color: "#fff", weight: 2, opacity: 0.9, interactive: false }).addTo(g);
        L.circleMarker(fin, { radius: 3, color: "#fff", fillColor: color, fillOpacity: 1, interactive: false }).addTo(g);
      }
      L.marker([z.lat, z.lon], {
        icon: L.divIcon({ className: "zona-clima-rotulo", iconSize: [90, 18], iconAnchor: [45, 9], html: `<span style="border-color:${color}">${escapar(Logica.etiquetaClima(z.tipo))}${z.nombre ? " " + escapar(z.nombre) : ""}</span>` }),
        keyboard: false, interactive: false,
      }).addTo(g);
    }
    if (esInstructor()) {
      const ul = $("lista-zonas-clima");
      ul.innerHTML = zonas.length ? "" : "<li class='sec'>Sin zonas: rige el clima general.</li>";
      for (const z of zonas) {
        const li = document.createElement("li");
        li.innerHTML = `<span>${escapar(Logica.textoZonaClima(z))}</span> <button type="button" class="mini peligro" data-zona="${z.id}" title="Quitar">×</button>`;
        li.querySelector("button").addEventListener("click", () => enSilencio(api("DELETE", rutaEsc(`/clima/zonas/${z.id}`))));
        ul.appendChild(li);
      }
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
      map: () => app.map, naciones: () => app.naciones,
      alCambiar: (activo) => {
        app.tamSimbolo = activo ? 36 : 26; // simbolos mas grandes para verlos desde lejos
        if (app.data && !(app.informe && app.informe.activo())) { limpiarCapasVivas(); render(app.data); }
      },
    });
    app.videowall.conectar();
    app.aviacion = Aviacion.crear({
      map: () => app.map, api, toast, rutaEsc, usuario: () => app.usuario, catalogo: () => app.catalogo,
      datos: () => app.data, escenarioId: () => app.escenarioId, capa: app.capas.bases_ven, naciones: () => app.naciones,
    });
    app.aviacion.conectar();
    app.misiones = Misiones.crear({
      api, toast, rutaEsc, usuario: () => app.usuario, datos: () => app.data, catalogo: () => app.catalogo,
      capaBorrador: app.capas.preview, capaRutas: app.capas.misiones, puede: puedeFuncion, claseDe,
      horaDeTurno: horaDelTurno, seleccion: () => app.seleccion, seleccionar: (id) => seleccionar(id, "lista"),
      mapaLibre: () => !(app.informe && app.informe.activo()),
      alPlanificar: (activo) => { document.body.classList.toggle("planificando-mision", activo); },
    });
    app.misiones.conectar();
    app.herramientas = Herramientas.crear({ map: () => app.map, alMedir: (b) => { app.dibujando = b; } });
    app.herramientas.conectar();
    $("btn-regla").addEventListener("click", () => { if (app.herramientas.activa()) app.graficos.cancelar(); });
  }

  // ---------- objetivos y puntaje ----------
  function renderObjetivos(data) {
    const m = data.marcador || { azul: { total: 0, objetivos: 0, bajas: 0 }, rojo: { total: 0, objetivos: 0, bajas: 0 } };
    for (const b of ["azul", "rojo"]) {
      $(`marcador-${b}`).textContent = String(m[b].total);
      $(`marcador-${b}-det`).textContent = ` (${m[b].objetivos} obj. + ${m[b].bajas} bajas)`;
    }
    const lista = $("objetivos-lista");
    limpiar(lista);
    const objetivos = data.objetivos || [];
    if (!objetivos.length) {
      const li = document.createElement("li");
      li.className = "vacio";
      li.textContent = "Sin objetivos definidos.";
      lista.appendChild(li);
    }
    for (const o of objetivos) {
      const av = Logica.avanceObjetivo(o);
      const li = document.createElement("li");
      li.className = `objetivo ${o.estado} ${o.bando}`;
      const t = document.createElement("div");
      t.append(Object.assign(document.createElement("b"), { textContent: o.nombre }), Object.assign(document.createElement("span"), { textContent: Logica.textoObjetivo(o) }));
      const chip = Object.assign(document.createElement("span"), { className: `chip ${av.clase}`, textContent: av.texto });
      li.append(t, chip);
      li.addEventListener("click", () => {
        if (o.tipo === "ocupar") app.map.panTo([o.lat, o.lon]);
        else if (o.unidad_id && app.porId.has(o.unidad_id)) seleccionar(o.unidad_id, "lista");
      });
      lista.appendChild(li);
    }
    // consola del instructor: lista con boton de borrar y unidades elegibles
    if (esInstructor()) {
      const ul = $("ob-lista");
      limpiar(ul);
      for (const o of objetivos) {
        const li = document.createElement("li");
        li.append(Object.assign(document.createElement("span"), { textContent: `${o.bando === "azul" ? "Azul" : "Rojo"} · ${o.nombre} (${Logica.avanceObjetivo(o).texto})` }));
        li.appendChild(boton("×", () => enSilencio(api("DELETE", rutaEsc(`/objetivos/${o.id}`))), "mini peligro"));
        ul.appendChild(li);
      }
      llenarUnidadesObjetivo(data.unidades);
    }
  }

  function llenarUnidadesObjetivo(unidades) {
    const tipo = $("ob-tipo").value;
    const bando = $("ob-bando").value;
    const candidatas = unidades.filter((u) => u.estado === "activa" && (tipo === "destruir" ? u.bando !== bando : u.bando === bando));
    llenarSelect($("ob-unidad"), candidatas.map((u) => [u.id, `${u.nombre} (${u.bando})`]));
  }

  function actualizarFormularioObjetivo() {
    const tipo = $("ob-tipo").value;
    document.querySelectorAll(".ob-ocupar").forEach((e) => { e.hidden = tipo !== "ocupar"; });
    document.querySelectorAll(".ob-unidad").forEach((e) => { e.hidden = tipo === "ocupar"; });
    document.querySelectorAll(".ob-proteger").forEach((e) => { e.hidden = tipo !== "proteger"; });
    if (app.data) llenarUnidadesObjetivo(app.data.unidades);
  }
  $("ob-tipo").addEventListener("change", actualizarFormularioObjetivo);
  $("ob-bando").addEventListener("change", actualizarFormularioObjetivo);
  $("btn-ob-ubicar").addEventListener("click", () => {
    app.modoObjetivo = !app.modoObjetivo;
    $("btn-ob-ubicar").textContent = app.modoObjetivo ? "Haga clic en el mapa… (cancelar)" : "Ubicar la zona en el mapa";
  });
  $("btn-ob-crear").addEventListener("click", async () => {
    if (!app.escenarioId) return;
    const tipo = $("ob-tipo").value;
    const nombre = $("ob-nombre").value.trim();
    if (!nombre) return toast("Escriba un nombre para el objetivo.");
    const cuerpo = { tipo, bando: $("ob-bando").value, nombre, puntos: parseInt($("ob-puntos").value, 10) || 0 };
    if (tipo === "ocupar") {
      if (!app.objetivoCentro) return toast("Ubique la zona en el mapa.");
      Object.assign(cuerpo, { lat: app.objetivoCentro[0], lon: app.objetivoCentro[1], radio_km: parseFloat($("ob-radio").value) || 5, turnos_requeridos: parseInt($("ob-turnos").value, 10) || 1 });
    } else {
      cuerpo.unidad_id = parseInt($("ob-unidad").value, 10) || null;
      if (tipo === "proteger") cuerpo.hasta_turno = parseInt($("ob-hasta").value, 10) || null;
    }
    try {
      await api("POST", rutaEsc("/objetivos"), cuerpo);
      $("ob-nombre").value = "";
      app.objetivoCentro = null;
      $("ob-centro").textContent = "";
      toast("Objetivo creado", true);
    } catch (_) { /* toast ya mostrado */ }
  });
  // pantallas estrechas: el panel derecho y la barra de dibujo se abren y cierran con botones
  function alternarPanelMovil(id, boton) {
    const abierto = $(id).classList.toggle("abierto");
    $(boton).setAttribute("aria-expanded", String(abierto));
    if (abierto && id === "panel-der") $("barra-graficos").classList.remove("abierto");
    if (abierto && id === "barra-graficos") $("panel-der").classList.remove("abierto");
    $("btn-panel-der").setAttribute("aria-expanded", String($("panel-der").classList.contains("abierto")));
    $("btn-panel-graficos").setAttribute("aria-expanded", String($("barra-graficos").classList.contains("abierto")));
  }
  $("btn-panel-der").addEventListener("click", () => alternarPanelMovil("panel-der", "btn-panel-der"));
  $("btn-panel-graficos").addEventListener("click", () => alternarPanelMovil("barra-graficos", "btn-panel-graficos"));

  $("chk-editar").addEventListener("change", () => {
    app.editando = $("chk-editar").checked;
    if (app.data) dibujarUnidades(app.data.unidades);
  });
  $("oob-buscar").addEventListener("input", () => { app.filtroOOB = $("oob-buscar").value; if (app.data) renderOOB(app.data); });
  $("oob-buscar").addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const primero = document.querySelector("#oob .oob-item");
    if (primero) primero.click();
  });

  function dibujarObjetivos(objetivos) {
    const g = app.capas.objetivos;
    g.clearLayers();
    for (const o of objetivos) {
      const color = o.estado === "cumplido" ? "#2EC4B6" : o.estado === "fallido" ? "#8D99AE" : (COLOR[o.bando] || "#fff");
      const etiqueta = `${o.nombre} · ${o.puntos} pts · ${Logica.avanceObjetivo(o).texto}`;
      let centro = null;
      if (o.tipo === "ocupar") {
        centro = [o.lat, o.lon];
        L.circle(centro, { radius: o.radio_km * 1000, color, weight: 2, dashArray: o.estado === "pendiente" ? "10 6" : null, fillColor: color, fillOpacity: 0.08 })
          .bindTooltip(etiqueta, { sticky: true }).addTo(g);
      } else {
        const u = app.porId.get(o.unidad_id);
        if (!u) continue;
        centro = [u.lat, u.lon];
        L.circle(centro, { radius: 6000, color, weight: 2, dashArray: "3 5", fill: false })
          .bindTooltip(`${o.tipo === "destruir" ? "Destruir" : "Proteger"}: ${etiqueta}`, { sticky: true }).addTo(g);
      }
      L.marker(centro, {
        interactive: false, keyboard: false,
        icon: L.divIcon({ className: `objetivo-marca ${o.bando} ${o.estado}`, html: `<span>${o.tipo === "ocupar" ? "◎" : o.tipo === "destruir" ? "✕" : "⛨"}</span>`, iconSize: [22, 22], iconAnchor: [11, 11] }),
      }).addTo(g);
    }
  }

  /** ?modo=videowall&escenario=ID&vista=azul|rojo|completa (se aplica una sola vez, tras iniciar sesion) */
  function aplicarParametrosUrl() {
    const u = app.urlInicial;
    app.urlInicial = { lugar: u.lugar }; // el encuadre se aplica al llegar el primer estado
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
    app.rumbos.clear();
    app.posPrevia.clear();
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

  function selectRol(valor, etiqueta) {
    const sel = document.createElement("select");
    sel.setAttribute("aria-label", etiqueta);
    for (const r of ["instructor", "azul", "rojo", "observador"]) {
      const o = document.createElement("option");
      o.value = r; o.textContent = r; sel.appendChild(o);
    }
    sel.value = valor;
    return sel;
  }

  function selectPuesto(valor, etiqueta) {
    const sp = document.createElement("select");
    sp.title = "Puesto dentro del bando";
    sp.setAttribute("aria-label", etiqueta);
    for (const p of Logica.PUESTOS) {
      const o = document.createElement("option");
      o.value = p.id; o.textContent = `${p.sigla} · ${p.nombre}`; sp.appendChild(o);
    }
    sp.value = valor || "mando";
    return sp;
  }

  /** Solicitudes de cuenta hechas desde la pantalla de acceso: el instructor las aprueba (con el rol y el puesto
   * pedidos o los que elija) o las rechaza. */
  function pintarSolicitudes(pendientes) {
    const previas = app.solicitudesVistas;
    app.solicitudesVistas = new Set(pendientes.map((u) => u.id));
    if (previas && pendientes.some((u) => !previas.has(u.id))) toast("Nueva solicitud de cuenta: revise el panel Usuarios", true);
    $("bloque-solicitudes").hidden = !pendientes.length;
    $("badge-solicitudes").hidden = !pendientes.length;
    $("badge-solicitudes").textContent = pendientes.length;
    const ul = $("lista-solicitudes");
    limpiar(ul);
    for (const u of pendientes) {
      const item = document.createElement("li");
      const et = document.createElement("span");
      et.textContent = `${u.username} · pide ${u.rol}${esBando(u.rol) ? ` (${Logica.PUESTOS.find((p) => p.id === u.puesto)?.sigla || "EM"})` : ""}`;
      item.appendChild(et);
      const sel = selectRol(u.rol, `Rol con que se aprueba a ${u.username}`);
      const sp = selectPuesto(u.puesto, `Puesto con que se aprueba a ${u.username}`);
      const ajustarPuesto = () => { sp.hidden = !esBando(sel.value); };
      sel.addEventListener("change", ajustarPuesto);
      ajustarPuesto();
      item.append(sel, sp);
      item.appendChild(boton("Aprobar", () => api("POST", `/api/usuarios/${u.id}/aprobar`, { rol: sel.value, puesto: sp.value })
        .then(() => toast(`Cuenta de ${u.username} aprobada`, true)).catch(() => {}).finally(cargarUsuarios), "mini"));
      item.appendChild(boton("Rechazar", () => {
        if (!confirm(`¿Rechazar la solicitud de ${u.username}? Se borra y el nombre queda libre.`)) return;
        api("DELETE", `/api/usuarios/${u.id}/solicitud`).catch(() => {}).finally(cargarUsuarios);
      }));
      ul.appendChild(item);
    }
  }

  async function cargarUsuarios() {
    const todos = await api("GET", "/api/usuarios", undefined, true);
    pintarSolicitudes(todos.filter((u) => u.aprobado === false));
    const usuarios = todos.filter((u) => u.aprobado !== false);
    app.usuariosLista = usuarios;
    const ul = $("lista-usuarios");
    limpiar(ul);
    for (const u of usuarios) {
      const item = document.createElement("li");
      if (!u.activo) item.className = "inactiva";
      const et = document.createElement("span");
      et.textContent = `${u.username}${u.activo ? "" : " (inactivo)"}`;
      if (u.debe_cambiar_clave) {
        et.textContent += " ·";
        const aviso = document.createElement("small");
        aviso.className = "sec";
        aviso.textContent = " contraseña provisional";
        aviso.title = "Deberá cambiarla al entrar";
        et.appendChild(aviso);
      }
      item.appendChild(et);
      const esYo = u.id === app.usuario.id;
      const sel = selectRol(u.rol, `Rol de ${u.username}`);
      sel.disabled = esYo;
      sel.addEventListener("change", () => api("PATCH", `/api/usuarios/${u.id}`, { rol: sel.value }).finally(cargarUsuarios));
      item.appendChild(sel);
      if (esBando(u.rol)) {
        const sp = selectPuesto(u.puesto, `Puesto de ${u.username}`);
        sp.addEventListener("change", () => api("PATCH", `/api/usuarios/${u.id}`, { puesto: sp.value }).finally(cargarUsuarios));
        item.appendChild(sp);
      }
      item.appendChild(boton("Clave", async () => {
        const clave = await pedirClave(u.username);
        // la contrasena puesta aqui es provisional: el usuario la cambia al entrar (salvo la propia)
        if (clave) enSilencio(api("PATCH", `/api/usuarios/${u.id}`, { password: clave }).then(() => { toast("Contraseña actualizada", true); cargarUsuarios(); }));
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
      et.textContent = `${u.username} (${u.rol}${esBando(u.rol) ? " · " + Logica.puestoDe(u.puesto).sigla : ""})`;
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

  // ---------- escenarios precargados (plantillas) ----------
  $("btn-plantillas").addEventListener("click", async () => {
    const lista = $("plantilla-lista");
    limpiar(lista);
    let plantillas;
    try { plantillas = (await api("GET", "/api/plantillas")).plantillas; } catch (_) { return; }
    for (const p of plantillas) {
      const li = document.createElement("li");
      const info = document.createElement("div");
      info.append(Object.assign(document.createElement("b"), { textContent: p.nombre }),
        Object.assign(document.createElement("p"), { className: "ayuda", textContent: p.descripcion }),
        Object.assign(document.createElement("small"), { textContent: `${p.unidades} unidades · ${p.objetivos} objetivos` }));
      const btn = boton("Crear", async () => {
        try {
          const e = await api("POST", `/api/plantillas/${p.id}`);
          $("dlg-plantillas").close();
          toast(`Escenario «${e.nombre}» creado`, true);
          await cargarEscenarios(e.id);
        } catch (_) { /* toast ya mostrado */ }
      }, "primario");
      li.append(info, btn);
      lista.appendChild(li);
    }
    $("dlg-plantillas").showModal();
  });
  $("plantilla-cerrar").addEventListener("click", () => $("dlg-plantillas").close());

  const accion = (id, ruta) => $(id).addEventListener("click", () => app.escenarioId && enSilencio(api("POST", rutaEsc(`/${ruta}`))));
  accion("btn-avanzar", "avanzar_turno");
  accion("btn-pausar", "pausar");
  accion("btn-reanudar", "reanudar");
  $("btn-finalizar").addEventListener("click", () => {
    if (app.escenarioId && confirm("¿Finalizar el escenario? Ya no se podrán emitir órdenes y el informe se abrirá a los alumnos.")) {
      enSilencio(api("POST", rutaEsc("/finalizar")));
    }
  });

  $("btn-direccion").addEventListener("click", () => {
    if (!app.escenarioId) return;
    enSilencio(api("PATCH", rutaEsc("/config"), {
      niebla: $("dir-niebla").checked, logistica: $("dir-logistica").checked,
      efectos_clima: $("dir-clima").checked, fuego_automatico: $("dir-fuego").checked,
    }).then(() => toast("Interruptores aplicados", true)));
  });
  $("btn-evento-posicion").addEventListener("click", () => {
    app.marcandoEvento = !app.marcandoEvento;
    $("btn-evento-posicion").classList.toggle("activo", app.marcandoEvento);
    if (app.marcandoEvento) toast("Haga clic en el mapa donde ubicar el informe.");
    else { app.eventoPosicion = null; $("ev-posicion").textContent = "Sin posición: aviso de texto."; }
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

  $("btn-zona-clima").addEventListener("click", () => {
    app.colocandoZonaClima = !app.colocandoZonaClima;
    $("btn-zona-clima").classList.toggle("activo", app.colocandoZonaClima);
    toast(app.colocandoZonaClima ? "Haga clic en el mapa en el centro de la zona meteorológica." : "Colocación cancelada.");
  });

  $("btn-evento").addEventListener("click", async () => {
    const descripcion = $("ev-desc").value.trim();
    if (!descripcion || !app.escenarioId) return;
    const cuerpo = { descripcion, bando_destino: $("ev-bando").value, fuente: $("ev-fuente").value.trim() };
    if (app.eventoPosicion) {
      [cuerpo.lat, cuerpo.lon] = app.eventoPosicion;
      cuerpo.turnos = Math.max(1, parseInt($("ev-turnos").value, 10) || 3);
      cuerpo.tipo = "inteligencia";
    }
    await enSilencio(api("POST", rutaEsc("/eventos"), cuerpo));
    app.eventoPosicion = null;
    app.marcandoEvento = false;
    $("btn-evento-posicion").classList.remove("activo");
    $("ev-posicion").textContent = "Sin posición: aviso de texto.";
    $("ev-desc").value = "";
  });

  $("btn-ajustar").addEventListener("click", async () => {
    const id = $("adj-unidad").value;
    const cuerpo = {};
    const campos = [["fuerza", "adj-fuerza"], ["combustible", "adj-combustible"], ["municion", "adj-municion"],
      ["stock_combustible", "adj-stock-comb"], ["stock_municion", "adj-stock-mun"], ["dano_pista", "adj-dano-pista"],
      ["dano_plataforma", "adj-dano-plat"], ["dano_combustible", "adj-dano-comb"], ["refugios", "adj-refugios"]];
    for (const [campo, el] of campos) {
      const v = parseFloat($(el).value);
      if (!Number.isNaN(v)) cuerpo[campo] = v;
    }
    if (!id || !Object.keys(cuerpo).length) return toast("Indique al menos un valor a ajustar.");
    await enSilencio(api("PATCH", rutaEsc(`/unidades/${id}`), cuerpo));
    campos.forEach(([, el]) => { $(el).value = ""; });
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
      await api("POST", "/api/usuarios", { username: $("nu-user").value.trim(), password: $("nu-pass").value, rol: $("nu-rol").value, puesto: $("nu-puesto").value });
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
