/* Simulador Fénix - maqueta de interfaz. Datos de ejemplo; el mapa usa el relieve offline del proyecto. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const AZUL = "#3A86FF";
  const ROJO = "#EF233C";

  // ---------------------------------------------------------------- datos de ejemplo
  const UNIDADES = [
    { id: "inf1", rama: "infanteria", nombre: "1-Bon Infantería", rotulo: "1-BON INF", glifo: "inf", ech: "II", pos: [10.565, -67.03],
      estado: "En Posición", clase: "ok", comb: 78, mun: 88, fuerza: 100, vel: "0 km/h", terreno: "Urbano" },
    { id: "inf2", rama: "infanteria", nombre: "2-Cía Infantería", rotulo: "2-CÍA INF", glifo: "inf", ech: "I", pos: [10.578, -66.865],
      estado: "En Posición", clase: "ok", comb: 90, mun: 74, fuerza: 92, vel: "0 km/h", terreno: "Montaña" },
    { id: "exp1", rama: "infanteria", nombre: "1-Sec Exploración", rotulo: "1-SEC EXP", glifo: "exp", ech: "•••", pos: [10.572, -66.775], det: 7,
      estado: "Reconociendo", clase: "", comb: 64, mun: 100, fuerza: 100, vel: "20 km/h", terreno: "Montaña" },
    { id: "blin1", rama: "blindados", nombre: "1-Cía Blindada", rotulo: "1-CÍA BLIND", glifo: "blin", ech: "I", pos: [10.585, -66.925],
      estado: "En Movimiento", clase: "", comb: 85, mun: 92, fuerza: 100, vel: "45 km/h", terreno: "Urbano" },
    { id: "blin2", rama: "blindados", nombre: "2-Cía Blindada", rotulo: "2-CÍA BLIND", glifo: "blin", ech: "I", pos: [10.590, -66.985],
      estado: "En Reserva", clase: "reposo", comb: 96, mun: 100, fuerza: 100, vel: "0 km/h", terreno: "Urbano" },
    { id: "art1", rama: "artilleria", nombre: "1-Bat Artillería", rotulo: "1-BAT ART", glifo: "art", ech: "II", pos: [10.552, -66.955],
      estado: "En Posición de Fuego", clase: "fuego", comb: 70, mun: 81, fuerza: 100, vel: "0 km/h", terreno: "Urbano" },
  ];
  const RAMAS = [["infanteria", "Infantería"], ["blindados", "Blindados"], ["artilleria", "Artillería"]];

  const ENEMIGOS = [
    { id: "red4", nombre: "Red 4", rotulo: "RED 4", tipo: "Infantería motorizada", glifo: "inf", pos: [10.585, -66.735], visto: "13:45h" },
    { id: "red2", nombre: "Red 2", rotulo: "RED 2", tipo: "Fuerza mecanizada", glifo: "blin", pos: [10.565, -66.72], visto: "13:52h" },
    { id: "red1", nombre: "Red 1", rotulo: "RED 1 ?", tipo: "Elemento sin identificar", glifo: "?", pos: [10.605, -66.70], visto: "12:30h", fantasma: true },
  ];

  const W = { W1: [10.600, -66.885], W2: [10.598, -66.835], W3: [10.596, -66.785], W4: [10.592, -66.752] };

  const ordenes = [
    { id: 1, unidad: "blin1", texto: "Mover a W3", detalle: "1-Cía Blindada · vía W1, W2", estado: "conf", tipo: "mover", wps: ["W1", "W2", "W3"] },
    { id: 2, unidad: "blin1", texto: "Atacar Red 4", detalle: "1-Cía Blindada · desde W3", estado: "pend", tipo: "atacar", desde: W.W3, objetivo: "red4" },
    { id: 3, unidad: "art1", texto: "Fuego sobre Red 2", detalle: "1-Bat Artillería · 26 km", estado: "pend", tipo: "atacar", desde: UNIDADES[5].pos, objetivo: "red2" },
  ];

  const ALERTAS = [
    { hora: "13:45h", nivel: "critica", texto: "Unidad Roja Detectada cerca de W4" },
    { hora: "13:52h", nivel: "critica", texto: "Fuerza mecanizada enemiga (Red 2) confirmada al este" },
    { hora: "13:30h", nivel: "aviso", texto: "1-Sec Exploración: combustible por debajo del 70 %" },
    { hora: "13:10h", nivel: "info", texto: "Clima despejado: sin restricciones de visibilidad" },
  ];

  // ---------------------------------------------------------------- simbologia (APP-6 simplificada, SVG)
  const GLIFOS_AMIGO = {
    inf: '<path d="M1 1 33 23M33 1 1 23" stroke="#fff" stroke-width="1.6" fill="none"/>',
    blin: '<ellipse cx="17" cy="12" rx="9" ry="5.5" fill="none" stroke="#fff" stroke-width="1.6"/>',
    art: '<circle cx="17" cy="12" r="3.4" fill="#fff"/>',
    exp: '<path d="M1 23 33 1" stroke="#fff" stroke-width="1.6" fill="none"/>',
  };
  const GLIFOS_ENEMIGO = {
    inf: '<path d="M8 8 22 22M22 8 8 22" stroke="#fff" stroke-width="1.6" fill="none"/>',
    blin: '<ellipse cx="15" cy="15" rx="8" ry="4.8" fill="none" stroke="#fff" stroke-width="1.6"/>',
    "?": '<text x="15" y="20" text-anchor="middle" font-size="14" font-weight="800" fill="#fff">?</text>',
  };

  function svgAmigo(u, clase = "frame") {
    return `<svg class="${clase}" width="34" height="24" viewBox="0 0 34 24" aria-hidden="true">`
      + `<rect x="1" y="1" width="32" height="22" rx="1" fill="rgba(58,134,255,.32)" stroke="${AZUL}" stroke-width="2"/>`
      + `${GLIFOS_AMIGO[u.glifo] || ""}`
      + `<text x="17" y="-3" text-anchor="middle" font-size="9" font-weight="800" fill="#fff">${u.ech}</text></svg>`;
  }
  function svgEnemigo(e, clase = "frame") {
    return `<svg class="${clase}" width="30" height="30" viewBox="0 0 30 30" aria-hidden="true">`
      + `<polygon points="15,1 29,15 15,29 1,15" fill="rgba(239,35,60,.3)" stroke="${ROJO}" stroke-width="2"${e.fantasma ? ' stroke-dasharray="4 3"' : ""}/>`
      + `${GLIFOS_ENEMIGO[e.glifo] || ""}</svg>`;
  }
  const iconoMarca = (svg, rotulo, clases, alto) => L.divIcon({
    className: "marca " + clases,
    html: `<div class="cuerpo">${svg}<div class="rotulo">${rotulo}</div></div>`,
    iconSize: [90, alto + 16], iconAnchor: [45, alto / 2 + 6],
  });

  // ---------------------------------------------------------------- mapa
  const LIMITES = L.latLngBounds([[0.6, -73.4], [12.4, -59.6]]);
  const map = L.map("map", { zoomControl: false, attributionControl: false, minZoom: 8, maxZoom: 11, maxBounds: LIMITES.pad(0.1) })
    .setView([10.58, -66.86], 11);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.control.attribution({ position: "bottomleft", prefix: false })
    .addAttribution("Relieve: SRTM/GMTED (AWS Terrain Tiles) · Cobertura: ESA WorldCover")
    .addTo(map);
  L.tileLayer("../tiles/venezuela/{z}/{x}/{y}.jpg", { minZoom: 5, maxNativeZoom: 9, maxZoom: 11, bounds: LIMITES }).addTo(map);

  const capaUnidades = L.layerGroup().addTo(map);
  const capaOrdenes = L.layerGroup().addTo(map);
  const capaCobertura = L.layerGroup();
  const capaNiebla = L.layerGroup();
  const marcadores = new Map(); // id -> marker
  let flechas = []; // vectores de ataque (se reorientan al cambiar el zoom)
  let seleccion = null;

  // ---------------------------------------------------------------- unidades en el mapa
  for (const u of UNIDADES) {
    const m = L.marker(u.pos, { icon: iconoMarca(svgAmigo(u), u.rotulo, "amigo", 24), keyboard: false })
      .on("click", () => seleccionar(u.id));
    m.bindTooltip(`${u.nombre} · ${u.estado}`, { direction: "top", offset: [0, -14] });
    m.addTo(capaUnidades);
    marcadores.set(u.id, m);
  }
  for (const e of ENEMIGOS) {
    const m = L.marker(e.pos, { icon: iconoMarca(svgEnemigo(e), e.rotulo, "enemigo" + (e.fantasma ? " fantasma" : ""), 30), keyboard: false })
      .on("click", () => seleccionar(e.id));
    m.bindTooltip(e.fantasma ? `${e.nombre} · último contacto ${e.visto}` : `${e.nombre} · ${e.tipo}`, { direction: "top", offset: [0, -16] });
    m.addTo(capaUnidades);
    marcadores.set(e.id, m);
  }

  // ---------------------------------------------------------------- ordenes en el mapa (rutas y vectores)
  const icono = (clase, texto) => L.divIcon({ className: "wp " + clase, html: `<span>${texto}</span>`, iconSize: [22, 22], iconAnchor: [11, 11] });

  function crearFlecha(desde, hasta) {
    const linea = L.polyline([desde, hasta], { color: ROJO, weight: 4, opacity: 0.95, lineCap: "round" }).addTo(capaOrdenes);
    const punta = L.marker(hasta, { icon: L.divIcon({ className: "flecha", html: "", iconSize: [1, 1] }), interactive: false, keyboard: false }).addTo(capaOrdenes);
    const f = { desde, hasta, linea, punta };
    f.actualizar = () => {
      const a = map.latLngToLayerPoint(desde);
      const b = map.latLngToLayerPoint(hasta);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const largo = Math.hypot(dx, dy) || 1;
      const retroceso = 24; // la punta se detiene antes del simbolo enemigo
      const fin = L.point(b.x - (dx / largo) * retroceso, b.y - (dy / largo) * retroceso);
      const grados = (Math.atan2(dy, dx) * 180) / Math.PI;
      linea.setLatLngs([desde, map.layerPointToLatLng(fin)]);
      punta.setLatLng(map.layerPointToLatLng(fin));
      punta.setIcon(L.divIcon({
        className: "flecha", iconSize: [1, 1],
        html: `<svg width="1" height="1"><g transform="rotate(${grados})"><path d="M8 0 -8 -8 -4 0 -8 8Z" fill="${ROJO}" stroke="#fff" stroke-width="1"/></g></svg>`,
      }));
    };
    f.actualizar();
    return f;
  }

  function dibujarOrdenes() {
    capaOrdenes.clearLayers();
    flechas = [];
    const usados = new Set();
    for (const o of ordenes) {
      if (o.tipo === "mover") {
        const u = UNIDADES.find((x) => x.id === o.unidad);
        const puntos = [u.pos, ...o.wps.map((w) => W[w])];
        L.polyline(puntos, { color: AZUL, weight: 3, dashArray: "9 7", opacity: 0.95, className: "ruta-anim" }).addTo(capaOrdenes);
        o.wps.forEach((w) => { usados.add(w); L.marker(W[w], { icon: icono("", w), keyboard: false }).addTo(capaOrdenes)
          .bindTooltip(`${w} · ${o.unidad === "blin1" ? "1-Cía Blindada" : u.nombre}`, { direction: "top" }); });
      } else if (o.tipo === "atacar") {
        const objetivo = ENEMIGOS.find((e) => e.id === o.objetivo);
        flechas.push(crearFlecha(o.desde, objetivo.pos));
      }
    }
    // punto de control de referencia (no forma parte de ninguna ruta)
    L.marker(W.W4, { icon: icono("neutro", "W4"), keyboard: false }).addTo(capaOrdenes).bindTooltip("W4 · punto de control", { direction: "top" });
  }
  map.on("zoomend", () => { flechas.forEach((f) => f.actualizar()); $("zoom-valor").textContent = String(map.getZoom()); });

  // ---------------------------------------------------------------- cobertura y niebla de guerra
  function anillo(centro, km, pasos = 56) {
    const [lat, lon] = centro;
    const dLat = km / 111.32;
    const dLon = km / (111.32 * Math.cos((lat * Math.PI) / 180));
    return Array.from({ length: pasos }, (_, i) => {
      const a = (i / pasos) * 2 * Math.PI;
      return [lat + dLat * Math.sin(a), lon + dLon * Math.cos(a)];
    });
  }
  const radioDeteccion = (u) => u.det || (u.glifo === "art" ? 6 : 8);
  for (const u of UNIDADES) {
    L.polygon(anillo(u.pos, radioDeteccion(u)), { color: AZUL, weight: 1, dashArray: "4 4", fillColor: AZUL, fillOpacity: 0.07, interactive: false }).addTo(capaCobertura);
  }
  // Niebla: un rectangulo que cubre el mapa con un agujero por cada zona que las unidades propias ven.
  const exterior = [[0.6, -73.4], [12.4, -73.4], [12.4, -59.6], [0.6, -59.6]];
  L.polygon([exterior, ...UNIDADES.map((u) => anillo(u.pos, radioDeteccion(u)))], {
    stroke: false, fillColor: "#0b1020", fillOpacity: 0.38, interactive: false,
  }).addTo(capaNiebla);
  capaNiebla.addTo(map);

  // ---------------------------------------------------------------- panel izquierdo: orden de batalla
  const barraClase = (v) => (v < 30 ? "critico" : v < 60 ? "bajo" : "");

  function renderOOB() {
    const cont = $("oob");
    cont.textContent = "";
    for (const [rama, titulo] of RAMAS) {
      const lista = UNIDADES.filter((u) => u.rama === rama);
      const det = document.createElement("details");
      det.open = true;
      const sum = document.createElement("summary");
      sum.append(titulo);
      const n = document.createElement("span");
      n.className = "n";
      n.textContent = `${lista.length} un.`;
      sum.appendChild(n);
      det.appendChild(sum);
      const ul = document.createElement("ul");
      for (const u of lista) {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.className = "oob-item";
        b.dataset.id = u.id;
        b.innerHTML = svgAmigo(u, "simbolo").replace(/<text[^>]*>[^<]*<\/text>/, "");
        const nom = document.createElement("span");
        nom.className = "nom";
        nom.textContent = u.nombre;
        const est = document.createElement("span");
        est.className = "estado-mini";
        est.textContent = u.estado.replace("En ", "");
        const punto = document.createElement("i");
        punto.className = "punto " + (u.clase === "ok" ? "ok" : u.clase === "" ? "mov" : "");
        b.append(nom, est, punto);
        b.addEventListener("click", () => { seleccionar(u.id); map.panTo(u.pos); });
        li.appendChild(b);
        ul.appendChild(li);
      }
      det.appendChild(ul);
      cont.appendChild(det);
    }
  }

  function barra(nombre, valor) {
    const oculto = valor === null;
    return `<div class="barra"><div class="fila"><span>${nombre}</span><b>${oculto ? "?" : valor + "%"}</b></div>`
      + `<div class="pista"><div class="relleno ${oculto ? "oculto" : barraClase(valor)}" style="width:${oculto ? 100 : valor}%"></div></div></div>`;
  }

  function renderDetalle() {
    const cont = $("detalle-contenido");
    const u = UNIDADES.find((x) => x.id === seleccion);
    const e = ENEMIGOS.find((x) => x.id === seleccion);
    if (u) {
      cont.innerHTML = `<div class="det-titulo">${svgAmigo(u, "simbolo").replace(/<text[^>]*>[^<]*<\/text>/, "")}<div><h3>${u.nombre}</h3>`
        + `<small>Bando Azul · ${RAMAS.find((r) => r[0] === u.rama)[1]}</small></div></div>`
        + `<span class="insignia ${u.clase}">${u.estado}</span>`
        + barra("Combustible", u.comb) + barra("Munición", u.mun)
        + `<dl class="det-datos"><div><dt>Fuerza</dt><dd>${u.fuerza}%</dd></div><div><dt>Velocidad</dt><dd>${u.vel}</dd></div>`
        + `<div><dt>Terreno</dt><dd>${u.terreno}</dd></div><div><dt>Detección</dt><dd>${radioDeteccion(u)} km</dd></div></dl>`;
    } else if (e) {
      cont.innerHTML = `<div class="det-titulo">${svgEnemigo(e, "simbolo")}<div><h3>${e.nombre}</h3><small>Bando Rojo · contacto</small></div></div>`
        + `<span class="insignia fuego">${e.fantasma ? "Último contacto" : "Detectado"} ${e.visto}</span>`
        + barra("Combustible", null) + barra("Munición", null)
        + `<dl class="det-datos"><div><dt>Fuerza</dt><dd>?</dd></div><div><dt>Tipo</dt><dd>${e.tipo}</dd></div></dl>`
        + `<p class="nota">Niebla de guerra: de las unidades enemigas solo se conoce su posición y clase.</p>`;
    }
  }

  function seleccionar(id) {
    seleccion = id;
    for (const [mid, m] of marcadores) {
      const el = m.getElement();
      if (el) el.classList.toggle("sel", mid === id);
    }
    document.querySelectorAll(".oob-item").forEach((b) => b.classList.toggle("sel", b.dataset.id === id));
    renderDetalle();
  }

  // ---------------------------------------------------------------- cola de ordenes
  function renderCola() {
    const ol = $("cola");
    ol.textContent = "";
    if (!ordenes.length) {
      const v = document.createElement("li");
      v.className = "vacio";
      v.textContent = "Sin órdenes: las unidades mantienen su posición.";
      v.style.gridTemplateColumns = "1fr";
      ol.appendChild(v);
    }
    for (const o of ordenes) {
      const li = document.createElement("li");
      li.className = o.estado === "pend" ? "pendiente" : "";
      const t = document.createElement("div");
      t.className = "texto";
      const b = document.createElement("b");
      b.textContent = `Orden ${o.id}: ${o.texto}`;
      const s = document.createElement("span");
      s.textContent = o.detalle;
      t.append(b, s);
      const chip = document.createElement("span");
      chip.className = "chip " + o.estado;
      chip.textContent = o.estado === "conf" ? "CONFIRMADA" : "PENDIENTE";
      const x = document.createElement("button");
      x.type = "button";
      x.title = "Cancelar orden";
      x.setAttribute("aria-label", `Cancelar orden ${o.id}`);
      x.textContent = "×";
      x.addEventListener("click", () => {
        ordenes.splice(ordenes.indexOf(o), 1);
        renderCola();
        dibujarOrdenes();
      });
      li.append(t, chip, x);
      li.addEventListener("click", (ev) => { if (ev.target !== x) seleccionar(o.unidad); });
      ol.appendChild(li);
    }
    $("cola-contador").textContent = String(ordenes.length);
  }

  // ---------------------------------------------------------------- alertas
  function renderAlertas() {
    const ul = $("alertas");
    ul.textContent = "";
    [...ALERTAS].sort((a, b) => b.hora.localeCompare(a.hora)).forEach((a) => {
      const li = document.createElement("li");
      li.className = a.nivel;
      const t = document.createElement("time");
      t.textContent = a.hora;
      li.append(t, a.texto);
      ul.appendChild(li);
    });
    $("alertas-nuevas").textContent = String(ALERTAS.filter((a) => a.nivel === "critica").length);
  }

  // ---------------------------------------------------------------- capas
  const capas = {
    terreno: (on) => $("zona-mapa").classList.toggle("sin-terreno", !on),
    cobertura: (on) => (on ? capaCobertura.addTo(map) : map.removeLayer(capaCobertura)),
    niebla: (on) => (on ? capaNiebla.addTo(map) : map.removeLayer(capaNiebla)),
    unidades: (on) => {
      for (const g of [capaUnidades, capaOrdenes]) on ? g.addTo(map) : map.removeLayer(g);
      if (on) { flechas.forEach((f) => f.actualizar()); if (seleccion) seleccionar(seleccion); }
    },
  };
  document.querySelectorAll("[data-capa]").forEach((chk) => chk.addEventListener("change", () => capas[chk.dataset.capa](chk.checked)));

  // ---------------------------------------------------------------- temporizador y confirmacion de turno
  let restante = 18 * 60 + 32;
  const reloj = $("reloj");
  function pintarReloj() {
    const m = String(Math.floor(restante / 60)).padStart(2, "0");
    const s = String(restante % 60).padStart(2, "0");
    $("reloj-valor").textContent = `${m}:${s}`;
    reloj.classList.toggle("urgente", restante <= 60);
  }
  setInterval(() => { if (restante > 0) { restante -= 1; pintarReloj(); } }, 1000);

  let confirmado = false;
  $("btn-listo").addEventListener("click", () => {
    confirmado = !confirmado;
    $("btn-listo").classList.toggle("confirmado", confirmado);
    $("btn-listo-texto").textContent = confirmado ? "ÓRDENES CONFIRMADAS - CLIC PARA RETIRAR" : "ESTOY LISTO - CONFIRMAR ÓRDENES";
    const az = $("estado-azul");
    az.classList.toggle("listo", confirmado);
    az.querySelector("b").textContent = confirmado ? "LISTO" : "PLANIFICANDO";
    // al confirmar, todas las ordenes pasan a "confirmada"; al retirar, vuelven a su estado previo
    ordenes.forEach((o) => {
      if (confirmado) { o.previo = o.estado; o.estado = "conf"; } else if (o.previo) { o.estado = o.previo; }
    });
    renderCola();
  });

  // ---------------------------------------------------------------- arranque
  pintarReloj();
  renderOOB();
  renderCola();
  renderAlertas();
  dibujarOrdenes();
  seleccionar("blin1");
  $("zoom-valor").textContent = String(map.getZoom());
})();
