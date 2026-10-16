/* Misiones aereas: planificador de ruta con rol (panel sobre el mapa), lista de misiones del bando, rutas en el mapa
 * y cronograma (flow sheet). La validacion y la estimacion de hora y combustible las hace el servidor
 * (POST /misiones/previsualizar) con las mismas reglas con que despues resuelve los turnos. */
(function (raiz) {
  "use strict";

  const TIPO = Logica.TIPOS_PUNTO_MISION;
  const COLOR_ROL = { CAP: "#4cc9f0", INTERDICCION: "#f77f00", CAS: "#fcbf49", SEAD: "#ef476f", RECO: "#90be6d", GE: "#c77dff", TRASLADO: "#adb5bd" };
  const LETRA = { orbita: "O", blanco: "✕", aterrizaje: "▼" };
  const NS = "http://www.w3.org/2000/svg";

  /** ctx: { api, toast, rutaEsc(sufijo), usuario(), datos(), catalogo(), capaBorrador, capaRutas, puede(funcion),
   *  claseDe(u), horaDeTurno(turno), seleccion(), seleccionar(id), mapaLibre(), alPlanificar(activo) } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const el = (tag, clase, texto) => {
      const e = document.createElement(tag);
      if (clase) e.className = clase;
      if (texto !== undefined) e.textContent = texto;
      return e;
    };
    const limpiar = (n) => { while (n.firstChild) n.removeChild(n.firstChild); };
    const opciones = (sel, pares, valor) => {
      limpiar(sel);
      for (const [v, t] of pares) { const o = el("option", "", t); o.value = String(v); sel.appendChild(o); }
      if (valor !== undefined && valor !== null && pares.some(([v]) => String(v) === String(valor))) sel.value = String(valor);
    };

    let borrador = null; // mision en edicion (null = panel cerrado)
    let temporizador = null;

    const cat = () => ctx.catalogo() || {};
    const roles = () => (cat().misiones || { roles: [] }).roles;
    const rolDe = (id) => roles().find((r) => r.id === id) || null;
    const datos = () => ctx.datos();
    const bando = () => (ctx.usuario() || {}).rol;
    const esAlumno = () => Logica.esBando(bando());
    const delBando = (f) => (datos() ? datos().unidades.filter((u) => u.bando === bando() && u.estado === "activa" && f(u)) : []);
    // aeronaves que la reparticion del alumno puede conducir (A-3, A-3 D/A, A-2 o C-E segun la clase)
    const conduce = (u) => !esAlumno() || ctx.puede(Logica.funcionDeOrden(u, "mision", ctx.claseDe(u)));
    const grupos = () => delBando((u) => u.tipo === "aerea" && conduce(u));
    const conduceId = (id) => { const u = datos() && datos().unidades.find((x) => x.id === id); return !!u && conduce(u); };
    const bases = () => delBando((u) => u.clase === "base_aerea");
    const enemigos = () => (datos() ? datos().unidades.filter((u) => u.bando !== bando() && u.estado === "activa" && (u.tipo !== "aerea" || u.en_tierra)) : []);
    const puedeGrupos = () => esAlumno() && grupos().length > 0;
    const puedeBases = () => esAlumno() && ctx.puede("despegar");
    const turnoActual = () => (datos() ? datos().escenario.turno_actual : 1);
    const inicioMin = () => (datos() ? datos().escenario.hora_inicio_min : 360);

    function claseDelBorrador() {
      if (!borrador || !datos()) return null;
      if (borrador.origen === "grupo") {
        const u = datos().unidades.find((x) => x.id === borrador.unidadId);
        return u ? ctx.claseDe(u) : null;
      }
      const m = (cat().modelos || []).find((x) => x.id === borrador.modelo);
      return m ? (cat().clases || []).find((c) => c.id === m.clase) || null : null;
    }
    const esKamikaze = () => { const c = claseDelBorrador(); return !!(c && c.se_consume); };

    function origen() {
      if (!borrador || !datos()) return null;
      const id = borrador.origen === "grupo" ? borrador.unidadId : borrador.baseId;
      const u = datos().unidades.find((x) => x.id === id);
      return u ? [u.lat, u.lon] : null;
    }

    // ------------------------------------------------------------------ panel de planificacion
    function abrir() {
      if (!datos()) return;
      const g = puedeGrupos() && grupos().length > 0;
      const b = puedeBases() && bases().length > 0;
      if (!g && !b) {
        ctx.toast(puedeBases() ? "Su bando no tiene bases aéreas en servicio."
          : "Su bando no tiene grupos aéreos: Planificación (A5) debe enviar uno primero.");
        return;
      }
      const elegido = datos().unidades.find((u) => u.id === ctx.seleccion() && u.bando === bando() && u.tipo === "aerea");
      borrador = {
        origen: g ? "grupo" : "base", unidadId: (elegido || grupos()[0] || {}).id ?? null,
        baseId: (bases()[0] || {}).id ?? null, modelo: ((cat().modelos || [])[0] || {}).id ?? null, aeronaves: 2,
        turno: turnoActual(), nombre: "", rol: "CAP", puntos: [], aterrizajeId: (bases()[0] || {}).id ?? null,
        escoltaDe: null, escolta: "",
      };
      $("pm-origen-grupo").disabled = !g;
      $("pm-origen-base").disabled = !b;
      $("pm-nombre").value = "";
      $("panel-mision").hidden = false;
      ctx.alPlanificar(true);
      llenar();
      refrescar();
    }

    function cerrar() {
      borrador = null;
      clearTimeout(temporizador);
      $("panel-mision").hidden = true;
      ctx.capaBorrador.clearLayers();
      ctx.alPlanificar(false);
    }

    function llenar() {
      if (!borrador) return;
      $(borrador.origen === "grupo" ? "pm-origen-grupo" : "pm-origen-base").checked = true;
      $("pm-grupo-fila").hidden = borrador.origen !== "grupo";
      $("pm-base-fila").hidden = borrador.origen !== "base";
      opciones($("pm-grupo"), grupos().map((u) => [u.id, `${u.nombre}${u.en_tierra ? " (en pista)" : ""}`]), borrador.unidadId);
      opciones($("pm-base"), bases().map((u) => [u.id, u.nombre]), borrador.baseId);
      opciones($("pm-modelo"), (cat().modelos || []).map((m) => [m.id, m.nombre]), borrador.modelo);
      const max = (cat().aeronaves || {}).max_grupo || 8;
      opciones($("pm-cantidad"), Array.from({ length: max }, (_, i) => [i + 1, `${i + 1}`]), borrador.aeronaves);
      const t0 = turnoActual();
      opciones($("pm-turno"), Array.from({ length: 13 }, (_, i) => [t0 + i, `T${t0 + i} · ${ctx.horaDeTurno(t0 + i)}${i === 0 ? " (al resolver este turno)" : ""}`]), borrador.turno);
      opciones($("pm-rol"), roles().map((r) => [r.id, r.nombre]), borrador.rol);
      opciones($("pm-aterrizaje"), bases().map((u) => [u.id, u.nombre]), borrador.aterrizajeId);
      // rol ESCOLTA: que mision escolta; roles de ataque: escolta opcional del paquete (grupo existente o grupo que despega)
      const escoltables = (datos() ? datos().misiones || [] : []).filter((m) => m.bando === bando() && ["programada", "en_curso"].includes(m.estado) && m.rol !== "ESCOLTA");
      opciones($("pm-escolta-de"), escoltables.map((m) => [m.id, `M${m.id} · ${m.nombre || m.rol_nombre}`]), borrador.escoltaDe);
      const cazas = grupos().filter((u) => !u.en_tierra && u.clase === "caza");
      opciones($("pm-escolta"), [["", "Sin escolta"], ...cazas.map((u) => [`u:${u.id}`, `${u.nombre} (en vuelo)`]),
        ...(borrador.origen === "base" ? (cat().modelos || []).filter((m) => (m.ataque_vs || {}).aerea > 0 && !m.misil).map((m) => [`m:${m.id}`, `${m.corto || m.nombre} ×2 desde la misma base`]) : [])], borrador.escolta);
      borrador.escoltaDe = parseInt($("pm-escolta-de").value, 10) || null;
      borrador.escolta = $("pm-escolta").value || "";
      borrador.unidadId = parseInt($("pm-grupo").value, 10) || null;
      borrador.baseId = parseInt($("pm-base").value, 10) || null;
      borrador.modelo = $("pm-modelo").value || null;
      borrador.aterrizajeId = parseInt($("pm-aterrizaje").value, 10) || null;
      borrador.rol = $("pm-rol").value || borrador.rol;
    }

    // ------------------------------------------------------------------ puntos de la ruta
    /** Tipo sugerido para un punto nuevo: la orbita que el rol necesita, o blanco si se hizo clic junto a un enemigo. */
    function tipoPorDefecto(lat, lon) {
      const rol = rolDe(borrador.rol);
      const tipos = borrador.puntos.map((p) => p.tipo);
      const requiere = rol ? rol.requiere : [];
      if (requiere.includes("blanco") && !tipos.includes("blanco") && enemigoMasCercano(lat, lon, 8)) return "blanco";
      if (requiere.includes("orbita") && !tipos.includes("orbita")) return "orbita";
      return "paso";
    }

    function enemigoMasCercano(lat, lon, km = 30) {
      let mejor = null;
      for (const e of enemigos()) {
        const d = Logica.distanciaKm(lat, lon, e.lat, e.lon);
        if (d <= km && (!mejor || d < mejor.d)) mejor = { e, d };
      }
      return mejor ? mejor.e : null;
    }

    function apuntar(p, e) {
      p.objetivo_unidad_id = e ? e.id : null;
      if (e) { p.lat = e.lat; p.lon = e.lon; }
    }

    /** Clic en el mapa mientras se planifica: agrega un punto a la ruta. Devuelve true si lo uso. */
    function alClickMapa(lat, lon) {
      if (!borrador) return false;
      const max = ((cat().misiones || {}).max_puntos || 12) - (esKamikaze() ? 0 : 1);
      if (borrador.puntos.length >= max) {
        ctx.toast(`La ruta admite hasta ${max} puntos${esKamikaze() ? "" : " más el aterrizaje"}.`);
        return true;
      }
      const p = { tipo: tipoPorDefecto(lat, lon), lat, lon, turnos: 2, objetivo_unidad_id: null };
      if (p.tipo === "blanco") apuntar(p, enemigoMasCercano(lat, lon));
      borrador.puntos.push(p);
      refrescar();
      return true;
    }

    /** Clic sobre el simbolo de una unidad mientras se planifica: un enemigo se agrega como blanco. */
    function alClickUnidad(u) {
      if (!borrador || !u || u.bando === bando() || u.estado !== "activa") return false;
      const rol = rolDe(borrador.rol);
      if (rol && rol.prohibe.includes("blanco")) {
        ctx.toast(`El rol ${rol.nombre} no ataca blancos: elija otro rol o haga clic fuera de la unidad.`);
        return true;
      }
      const p = { tipo: "blanco", lat: u.lat, lon: u.lon, turnos: 2, objetivo_unidad_id: null };
      apuntar(p, u);
      borrador.puntos.push(p);
      refrescar();
      return true;
    }

    function renderPuntos() {
      const ol = $("pm-puntos");
      limpiar(ol);
      const rol = rolDe(borrador.rol);
      const permitidos = ["paso", "orbita", "blanco"].filter((t) => !rol || !rol.prohibe.includes(t));
      if (!borrador.puntos.length) ol.appendChild(el("li", "vacio", "Sin puntos: haga clic en el mapa."));
      borrador.puntos.forEach((p, i) => {
        const li = el("li");
        li.appendChild(el("b", "", String(i + 1)));
        const tipo = el("select");
        tipo.setAttribute("aria-label", `Tipo del punto ${i + 1}`);
        opciones(tipo, [...new Set([...permitidos, p.tipo])].map((t) => [t, TIPO[t]]), p.tipo);
        tipo.addEventListener("change", () => {
          p.tipo = tipo.value;
          if (p.tipo === "blanco" && !p.objetivo_unidad_id) apuntar(p, enemigoMasCercano(p.lat, p.lon));
          refrescar();
        });
        li.appendChild(tipo);
        if (p.tipo === "orbita") {
          const t = el("select");
          t.setAttribute("aria-label", `Turnos de órbita del punto ${i + 1}`);
          const max = (cat().misiones || {}).max_turnos_orbita || 12;
          opciones(t, Array.from({ length: max }, (_, k) => [k + 1, `${k + 1} turno${k ? "s" : ""}`]), p.turnos);
          t.addEventListener("change", () => { p.turnos = parseInt(t.value, 10); refrescar(); });
          li.appendChild(t);
        } else if (p.tipo === "blanco") {
          const o = el("select");
          o.setAttribute("aria-label", `Blanco del punto ${i + 1}`);
          const cerca = enemigos().map((e) => ({ e, d: Logica.distanciaKm(p.lat, p.lon, e.lat, e.lon) })).sort((a, b) => a.d - b.d).slice(0, 8);
          opciones(o, [["", "El enemigo detectado más cercano"], ...cerca.map(({ e, d }) => [e.id, `${e.nombre} · ${Math.round(d)} km`])], p.objetivo_unidad_id ?? "");
          o.addEventListener("change", () => { apuntar(p, enemigos().find((e) => String(e.id) === o.value) || null); refrescar(); });
          li.appendChild(o);
        } else {
          li.appendChild(el("span", "sec", `${p.lat.toFixed(2)}, ${p.lon.toFixed(2)}`));
        }
        const x = el("button", "mini secundario", "×");
        x.type = "button";
        x.title = "Quitar punto";
        x.setAttribute("aria-label", `Quitar punto ${i + 1}`);
        x.addEventListener("click", () => { borrador.puntos.splice(i, 1); refrescar(); });
        li.appendChild(x);
        ol.appendChild(li);
      });
      $("pm-aterrizaje-fila").hidden = esKamikaze();
    }

    function puntosParaEnviar() {
      const pts = borrador.puntos.map((p) => {
        const d = { tipo: p.tipo, lat: p.lat, lon: p.lon };
        if (p.tipo === "orbita") d.turnos = p.turnos;
        if (p.tipo === "blanco" && p.objetivo_unidad_id) d.objetivo_unidad_id = p.objetivo_unidad_id;
        return d;
      });
      if (!esKamikaze() && borrador.aterrizajeId) {
        const b = bases().find((x) => x.id === borrador.aterrizajeId);
        if (b) pts.push({ tipo: "aterrizaje", lat: b.lat, lon: b.lon, base_id: b.id });
      }
      return pts;
    }

    function cuerpo() {
      const c = { rol: borrador.rol, nombre: borrador.nombre.trim(), puntos: puntosParaEnviar() };
      if (borrador.origen === "grupo") c.unidad_id = borrador.unidadId;
      else Object.assign(c, { base_id: borrador.baseId, modelo: borrador.modelo, aeronaves: borrador.aeronaves, turno_despegue: borrador.turno });
      if (borrador.rol === "ESCOLTA") c.escolta_de = borrador.escoltaDe;
      else if (borrador.escolta && borrador.escolta.startsWith("u:")) c.escolta = { unidad_id: parseInt(borrador.escolta.slice(2), 10) };
      else if (borrador.escolta && borrador.escolta.startsWith("m:")) c.escolta = { base_id: borrador.baseId, modelo: borrador.escolta.slice(2), aeronaves: 2 };
      return c;
    }

    function refrescar() {
      if (!borrador) return;
      $("pm-rol-desc").textContent = (rolDe(borrador.rol) || {}).descripcion || "";
      $("pm-escolta-de-fila").hidden = borrador.rol !== "ESCOLTA";
      $("pm-paquete").hidden = !["INTERDICCION", "CAS", "SEAD", "RECO", "GE"].includes(borrador.rol);
      renderPuntos();
      dibujarBorrador();
      clearTimeout(temporizador);
      temporizador = setTimeout(estimar, 250);
    }

    // ------------------------------------------------------------------ estimacion (servidor)
    async function estimar() {
      if (!borrador) return;
      const tabla = $("pm-estimacion");
      const avisos = $("pm-avisos");
      if (!borrador.puntos.length) {
        limpiar(tabla);
        limpiar(avisos);
        $("pm-crear").disabled = true;
        return;
      }
      let r;
      try {
        r = await ctx.api("POST", ctx.rutaEsc("/misiones/previsualizar"), cuerpo(), true);
      } catch (e) {
        limpiar(tabla);
        limpiar(avisos);
        avisos.appendChild(el("li", "error", e.message));
        $("pm-crear").disabled = true;
        return;
      }
      if (borrador) renderEstimacion(r);
    }

    function renderEstimacion(r) {
      const tabla = $("pm-estimacion");
      limpiar(tabla);
      const t = el("table", "pm-tabla");
      const cab = el("tr");
      for (const h of ["#", "Punto", "Llega", "Combustible"]) cab.appendChild(el("th", "", h));
      t.appendChild(cab);
      r.plan.puntos.forEach((f, i) => {
        const tipo = f.tipo || (r.puntos[i] || {}).tipo;
        const hora = (h) => Logica.horaEstimada(inicioMin(), r.turno_despegue, h);
        const tr = el("tr");
        tr.append(
          el("td", "", String(i + 1)), el("td", "", TIPO[tipo] || tipo),
          el("td", "", hora(f.llegada_h) + (tipo === "orbita" && f.salida_h !== undefined ? ` → ${hora(f.salida_h)}` : "")),
          el("td", Logica.claseBarra(Math.min(f.combustible_llegada, f.combustible_salida ?? 100)),
            `${Math.round(f.combustible_llegada)} %` + (f.combustible_salida !== undefined ? ` → ${Math.round(f.combustible_salida)} %` : "")),
        );
        t.appendChild(tr);
      });
      tabla.appendChild(t);
      const avisos = $("pm-avisos");
      limpiar(avisos);
      for (const e of r.errores) avisos.appendChild(el("li", "error", e));
      for (const a of r.plan.advertencias) avisos.appendChild(el("li", "aviso", a));
      if (!r.errores.length && !r.plan.advertencias.length) {
        avisos.appendChild(el("li", "ok", `Duración estimada ${r.plan.duracion_h.toFixed(1)} h · combustible final ${Math.round(r.plan.combustible_final)} %.`));
      }
      const lg = r.plan.logistica;
      if (lg) {
        const n = (v, d = 0) => Number(v).toLocaleString("es", { maximumFractionDigits: d });
        avisos.appendChild(el("li", "logistica",
          `Logística: ${n(lg.combustible_kg)} kg de combustible (${n(lg.combustible_por_aeronave_kg)} kg por aeronave, con ${lg.reserva_pct} % de reserva; `
          + `interno ${n(lg.combustible_interno_kg)} kg)`
          + (lg.lox_a_bordo_l ? ` · ${n(lg.lox_l, 1)} l de oxígeno líquido (${n(lg.lox_por_aeronave_l, 1)} l por aeronave de ${n(lg.lox_a_bordo_l, 1)} l a bordo)` : "")
          + (lg.tripulantes ? ` · ${lg.tripulantes} tripulantes.` : ".")));
      }
      $("pm-crear").disabled = r.errores.length > 0;
    }

    async function crearMision() {
      if (!borrador) return;
      try {
        const m = await ctx.api("POST", ctx.rutaEsc("/misiones"), cuerpo());
        ctx.toast(`Misión M${m.id} (${m.rol}) planificada`, true);
        cerrar();
      } catch (_) { /* el toast ya explica el motivo */ }
    }

    // ------------------------------------------------------------------ mapa
    // no interactivos: no deben tapar el clic sobre las unidades (p. ej. el enemigo que es el blanco)
    function marcador(p, n, color) {
      return L.marker([p.lat, p.lon], {
        icon: L.divIcon({
          className: `pm-punto ${p.tipo}`, iconSize: [22, 22], iconAnchor: [11, 11],
          html: `<span style="border-color:${color};color:${color}" title="${n + 1}. ${TIPO[p.tipo] || p.tipo}">${LETRA[p.tipo] || n + 1}</span>`,
        }),
        keyboard: false, interactive: false,
      });
    }

    function dibujarBorrador() {
      const g = ctx.capaBorrador;
      g.clearLayers();
      const o = origen();
      if (!o) return;
      const pts = puntosParaEnviar();
      const color = COLOR_ROL[borrador.rol] || "#fff";
      if (pts.length) L.polyline([o, ...pts.map((p) => [p.lat, p.lon])], { color, weight: 3, dashArray: "8 6", opacity: 0.95, interactive: false }).addTo(g);
      pts.forEach((p, i) => marcador(p, i, color).addTo(g));
    }

    function dibujarRutas(data) {
      const g = ctx.capaRutas;
      g.clearLayers();
      for (const m of (data.misiones || []).filter(Logica.misionActiva)) {
        const desde = data.unidades.find((x) => x.id === (m.unidad_id || m.base_id));
        const inicio = m.estado === "en_curso" ? m.indice : 0;
        const pts = (m.puntos || []).slice(inicio);
        if (!desde || !pts.length) continue;
        const color = COLOR_ROL[m.rol] || "#fff";
        L.polyline([[desde.lat, desde.lon], ...pts.map((p) => [p.lat, p.lon])], {
          color, weight: 2.5, dashArray: m.estado === "programada" ? "3 7" : "10 6", opacity: 0.9,
        }).bindTooltip(`M${m.id} · ${m.rol_nombre} · ${Logica.textoMision(m)}`, { sticky: true }).addTo(g);
        pts.forEach((p, i) => marcador(p, inicio + i, color).addTo(g));
      }
    }

    // ------------------------------------------------------------------ lista de misiones
    function render(data) {
      const lista = $("lista-misiones");
      limpiar(lista);
      const misiones = data.misiones || [];
      const activas = misiones.filter(Logica.misionActiva);
      $("misiones-contador").textContent = String(activas.length);
      $("btn-planificar-mision").hidden = !(puedeGrupos() || puedeBases());
      const orden = [...activas, ...misiones.filter((m) => !Logica.misionActiva(m))].slice(0, 20);
      if (!orden.length) lista.appendChild(el("li", "vacio", "Sin misiones aéreas."));
      for (const m of orden) {
        const li = el("li", `mision ${m.estado}${esAlumno() ? "" : " " + m.bando}`);
        li.style.borderLeftColor = COLOR_ROL[m.rol] || "#888";
        const u = data.unidades.find((x) => x.id === m.unidad_id);
        const t = el("div", "texto");
        t.append(
          el("b", "", `M${m.id} · ${m.rol} · ${m.nombre || (u ? u.nombre : "grupo nuevo")}`),
          el("span", "", `${Logica.ESTADOS_MISION[m.estado] || m.estado} · ${Logica.textoMision(m)}`),
        );
        li.appendChild(t);
        if (esAlumno() && Logica.misionActiva(m) && (m.unidad_id ? conduceId(m.unidad_id) : ctx.puede("despegar"))) {
          const x = el("button", "", "×");
          x.type = "button";
          x.title = m.estado === "en_curso" ? "Abortar: regresa a la base" : "Cancelar la misión";
          x.setAttribute("aria-label", `${x.title} (M${m.id})`);
          x.addEventListener("click", async (ev) => {
            ev.stopPropagation();
            try {
              const r = await ctx.api("DELETE", ctx.rutaEsc(`/misiones/${m.id}`));
              ctx.toast(r.resultado || "Misión cancelada", true);
            } catch (_) { /* toast ya mostrado */ }
          });
          li.appendChild(x);
        }
        if (u) li.addEventListener("click", () => ctx.seleccionar(u.id));
        lista.appendChild(li);
      }
      if (borrador) { llenar(); renderPuntos(); dibujarBorrador(); }
      if (ctx.mapaLibre()) dibujarRutas(data);
    }

    // ------------------------------------------------------------------ cronograma (flow sheet)
    function abrirCronograma() {
      const d = datos();
      if (!d) return;
      const svg = $("fs-svg");
      limpiar(svg);
      const nodo = (tag, attrs, texto) => {
        const n = document.createElementNS(NS, tag);
        for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
        if (texto !== undefined) n.textContent = texto;
        svg.appendChild(n);
        return n;
      };
      const misiones = (d.misiones || []).filter((m) => m.estado !== "cancelada" && m.plan && (m.plan.puntos || []).length);
      if (!misiones.length) {
        svg.setAttribute("viewBox", "0 0 600 50");
        svg.setAttribute("width", "600");
        svg.setAttribute("height", "50");
        nodo("text", { x: 10, y: 30, class: "fs-vacio" }, "No hay misiones planificadas.");
        $("dlg-cronograma").showModal();
        return;
      }
      const filas = misiones.map((m) => ({ m, t: Logica.tramosCronograma(m) })).sort((a, b) => a.t.inicio - b.t.inicio || a.m.id - b.m.id);
      const ahora = d.escenario.turno_actual - 1;
      const h0 = Math.floor(Math.min(ahora, ...filas.map((x) => x.t.inicio)));
      const h1 = Math.ceil(Math.max(ahora + 1, ...filas.map((x) => x.t.fin))) + 1;
      const IZQ = 200, SUP = 36, FILA = 28;
      const PX = Math.max(38, Math.min(80, 800 / Math.max(1, h1 - h0)));
      const ancho = IZQ + (h1 - h0) * PX + 70;
      const alto = SUP + filas.length * FILA + 8;
      svg.setAttribute("viewBox", `0 0 ${ancho} ${alto}`);
      svg.setAttribute("width", String(ancho));
      svg.setAttribute("height", String(alto));
      const x = (h) => IZQ + (h - h0) * PX;
      for (let h = h0; h <= h1; h++) {
        nodo("line", { x1: x(h), y1: SUP - 4, x2: x(h), y2: alto, class: "fs-grilla" });
        if (h < h1) {
          nodo("text", { x: x(h) + 3, y: 13, class: "fs-hora" }, `T${h + 1}`);
          nodo("text", { x: x(h) + 3, y: 26, class: "fs-hora" }, ctx.horaDeTurno(h + 1));
        }
      }
      filas.forEach(({ m, t }, i) => {
        const y = SUP + i * FILA + FILA / 2;
        const color = COLOR_ROL[m.rol] || "#aaa";
        nodo("text", { x: 6, y: y + 4, class: "fs-etiqueta" }, `M${m.id} ${m.rol}${m.nombre ? " · " + m.nombre : ""}`.slice(0, 32));
        for (const s of t.segmentos) {
          if (s.tipo === "orbita") nodo("rect", { x: x(s.desde), y: y - 7, width: Math.max(2, (s.hasta - s.desde) * PX), height: 14, rx: 3, fill: color, opacity: 0.85 });
          else nodo("line", { x1: x(s.desde), y1: y, x2: x(s.hasta), y2: y, stroke: color, "stroke-width": 3, "stroke-linecap": "round" });
        }
        for (const mk of t.marcas) nodo("text", { x: x(mk.h) - 5, y: y + 5, class: "fs-marca", fill: color }, mk.tipo === "blanco" ? "◆" : "▼");
        nodo("text", { x: x(t.fin) + 10, y: y + 4, class: "fs-estado" }, Logica.ESTADOS_MISION[m.estado] || m.estado);
      });
      nodo("line", { x1: x(ahora), y1: SUP - 4, x2: x(ahora), y2: alto, class: "fs-ahora" });
      $("dlg-cronograma").showModal();
    }

    function conectar() {
      $("btn-planificar-mision").addEventListener("click", abrir);
      $("btn-cronograma").addEventListener("click", abrirCronograma);
      $("pm-cerrar").addEventListener("click", cerrar);
      for (const r of document.querySelectorAll('input[name="pm-origen"]')) {
        r.addEventListener("change", () => { if (!borrador) return; borrador.origen = r.value; llenar(); refrescar(); });
      }
      const alCambiar = (id, f) => $(id).addEventListener("change", () => { if (!borrador) return; f($(id).value); llenar(); refrescar(); });
      alCambiar("pm-grupo", (v) => { borrador.unidadId = parseInt(v, 10); });
      alCambiar("pm-base", (v) => { borrador.baseId = parseInt(v, 10); });
      alCambiar("pm-modelo", (v) => { borrador.modelo = v; });
      alCambiar("pm-cantidad", (v) => { borrador.aeronaves = parseInt(v, 10); });
      alCambiar("pm-turno", (v) => { borrador.turno = parseInt(v, 10); });
      alCambiar("pm-rol", (v) => { borrador.rol = v; });
      alCambiar("pm-aterrizaje", (v) => { borrador.aterrizajeId = parseInt(v, 10); });
      alCambiar("pm-escolta-de", (v) => { borrador.escoltaDe = parseInt(v, 10) || null; });
      alCambiar("pm-escolta", (v) => { borrador.escolta = v || ""; });
      $("pm-nombre").addEventListener("input", () => { if (borrador) borrador.nombre = $("pm-nombre").value; });
      $("pm-limpiar").addEventListener("click", () => { if (borrador) { borrador.puntos = []; refrescar(); } });
      $("pm-crear").addEventListener("click", crearMision);
    }

    return { conectar, render, alClickMapa, alClickUnidad, abrir, cerrar, abrirCronograma, planificando: () => !!borrador };
  }

  raiz.Misiones = { crear };
})(window);
