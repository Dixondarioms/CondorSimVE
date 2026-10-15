/* Documentos del TIEM (Fase I, Paso 1: apreciación inicial): análisis de la misión, concepto del comandante, guía
 * de planeamiento y formas de acción con el criterio APA. La pestaña TIEM lista los documentos del bando con su
 * estado; cada uno se abre en un diálogo ancho para leerlo, redactarlo (según la repartición), presentarlo al
 * instructor, adjuntarle un Word y, el instructor, aprobarlo o devolverlo con observaciones. Ver engine/tiem.py.
 * Funciones puras (se prueban con Node) y el dibujo, que app.js llama en cada estado nuevo. */
(function (raiz) {
  "use strict";

  const ESTADOS = {
    borrador: { texto: "Borrador", clase: "" },
    presentado: { texto: "Presentado", clase: "mov" },
    aprobado: { texto: "Aprobado", clase: "ok" },
    devuelto: { texto: "Devuelto", clase: "fuego" },
  };
  const OPCIONES = { si: "Sí", parcial: "Parcial", no: "No", estrategico: "Estratégico", operacional: "Operacional", tactico: "Táctico",
    simultaneo: "Simultáneo", sistemico: "Sistémico" };
  const SIGLAS = { comandante: "CMDTE", jem: "JEM", a1: "A-1", a2: "A-2", a3: "A-3", a3da: "A-3 D/A", a4: "A-4", ce: "C-E", instructor: "Instructor" };

  /** {texto, clase} del estado de un documento, con el turno en que se presentó o revisó. */
  function textoEstado(doc) {
    const e = ESTADOS[doc.estado] || ESTADOS.borrador;
    let texto = e.texto;
    if (doc.estado === "presentado" && doc.presentado_turno) texto += ` (turno ${doc.presentado_turno})`;
    if ((doc.estado === "aprobado" || doc.estado === "devuelto") && doc.revisado_turno) texto += ` (turno ${doc.revisado_turno})`;
    if (doc.estado === "borrador" && !doc.existe) texto = "Sin empezar";
    return { texto, clase: e.clase };
  }

  /** "2 de 4 aprobados · 1 presentado" para la lista de la pestaña. */
  function textoAvance(docs) {
    const lista = Object.values(docs || {});
    const n = (e) => lista.filter((d) => d.estado === e).length;
    const partes = [`${n("aprobado")} de ${lista.length} aprobados`];
    if (n("presentado")) partes.push(`${n("presentado")} presentado${n("presentado") > 1 ? "s" : ""}`);
    if (n("devuelto")) partes.push(`${n("devuelto")} devuelto${n("devuelto") > 1 ? "s" : ""}`);
    return partes.join(" · ");
  }

  const textoOpcion = (v) => OPCIONES[v] || (v ? v.charAt(0).toUpperCase() + v.slice(1) : "—");
  const siglasRedactan = (def) => (def.redactan || []).map((p) => SIGLAS[p] || p).join(", ");

  /** Completa solo los campos vacíos con lo sugerido (transcripción y cálculo), sin pisar lo escrito. */
  function completarVacios(contenido, sugerido) {
    const vacio = (v) => v == null || v === "" || (Array.isArray(v) && !v.length) || (typeof v === "object" && !Array.isArray(v) && !Object.values(v).some(Boolean));
    const out = { ...contenido };
    const llenados = [];
    for (const [k, v] of Object.entries(sugerido || {})) {
      if (vacio(out[k]) && !vacio(v)) { out[k] = v; llenados.push(k); }
    }
    return { contenido: out, llenados };
  }

  const EFECTOS = { "no afecta": "ok", degrada: "mov", anula: "fuego" };

  /** Filas (F/A) y columnas (capacidades del enemigo) de la matriz de confrontación: las del contexto del bando más
   * las que ya tienen celdas escritas (por si una F/A cambió de nombre). */
  function ejesMatriz(celdas, contexto) {
    const filas = [...(contexto && contexto.formas) || []];
    const columnas = [...(contexto && contexto.capacidades) || []];
    for (const c of celdas || []) {
      if (c.fa && !filas.includes(c.fa)) filas.push(c.fa);
      if (c.capacidad && !columnas.includes(c.capacidad)) columnas.push(c.capacidad);
    }
    return { filas, columnas };
  }

  /** Celda de la matriz para esa F/A y capacidad (o una vacía). */
  const celdaDe = (celdas, fa, capacidad) => (celdas || []).find((c) => c.fa === fa && c.capacidad === capacidad) || { fa, capacidad, efecto: "", analisis: "" };

  const TITULOS_PASO = {
    "Fase I · Paso 1": "Fase I · Paso 1: Apreciación inicial",
    "Fase I · Paso 2": "Fase I · Paso 2: Apreciaciones de Estado Mayor",
    "Fase I · Paso 3": "Fase I · Paso 3: Decisión del Comandante",
    "Fase II · Paso 1": "Fase II · Análisis previo al plan",
    "Fase II · Paso 2": "Fase II · Plan de Operaciones",
  };

  /** "H", "H+3" o "H-2" de un turno, o "" sin hora H. */
  function refH(turno, turnoH) {
    if (!turnoH || !turno) return "";
    const n = turno - turnoH;
    return n === 0 ? "H" : `H${n > 0 ? "+" : ""}${n}`;
  }

  /** Orden de Operaciones: las tareas del plan que vencen ahora (o antes y no se emitieron) y las de las próximas
   * `horizonte` horas, cada una con su estado. */
  function ordenDelDia(tareas, ejecuciones, turno, horizonte = 24) {
    const vencen = [];
    const proximas = [];
    for (const t of tareas || []) {
      if (!t.turno) continue;
      const e = (ejecuciones || {})[t.id] || null;
      const item = { tarea: t, ejecucion: e, estado: e ? e.estado : "pendiente" };
      if (t.turno <= turno) {
        if (!e || e.estado !== "emitida" || e.turno === turno) vencen.push(item);
      } else if (t.turno < turno + horizonte) proximas.push(item);
    }
    const orden = (a, b) => a.tarea.turno - b.tarea.turno;
    return { vencen: vencen.sort(orden), proximas: proximas.sort(orden) };
  }

  /** "Atacar con A a R1" (como engine/tiem.texto_tarea, sin el turno). */
  function textoTarea(t, tipos) {
    const verbo = (tipos || {})[t.tipo] || "Cumplir";
    const nexo = { mover: "hacia", patrullar: "sobre", interferir: "sobre", aterrizar: "en" }[t.tipo] || "a";
    return `${verbo} con ${t.unidad_nombre || "la unidad"}${t.objetivo_nombre ? ` ${nexo} ${t.objetivo_nombre}` : ""}`;
  }

  const nuevoId = () => Array.from({ length: 8 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");

  /** Agrupa los documentos por paso del TIEM, en el orden recibido: [{paso, tipos: [...]}]. */
  function porPaso(orden, definiciones) {
    const grupos = [];
    for (const t of orden || []) {
      const paso = definiciones[t].paso;
      let g = grupos.find((x) => x.paso === paso);
      if (!g) { g = { paso, tipos: [] }; grupos.push(g); }
      g.tipos.push(t);
    }
    return grupos;
  }

  /** Resumen APA de una Forma de Acción: "Naturaleza Sí · Integridad Parcial · Oportunidad Sí · Practicable · Aceptabilidad alta". */
  function resumenApa(fa) {
    const p = [];
    for (const [k, t] of [["naturaleza", "Naturaleza"], ["integridad", "Integridad"], ["oportunidad", "Oportunidad"]]) if (fa[k]) p.push(`${t} ${textoOpcion(fa[k])}`);
    if (fa.practicabilidad) p.push(textoOpcion(fa.practicabilidad));
    if (fa.aceptabilidad) p.push(`Aceptabilidad ${fa.aceptabilidad}`);
    return p.join(" · ");
  }

  // ------------------------------------------------------------------ pestaña y diálogo
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const el = (tag, clase, texto) => {
      const e = document.createElement(tag);
      if (clase) e.className = clase;
      if (texto !== undefined) e.textContent = texto;
      return e;
    };
    const boton = (texto, fn, clase = "secundario") => { const b = el("button", clase, texto); b.type = "button"; b.addEventListener("click", fn); return b; };
    const Pmo = raiz.Pmo;
    let datos = null; // GET /tiem
    let firma = "";
    let abierto = null; // {bando, tipo}
    let borrador = null; // contenido en edición (null = leyendo)

    const doc = () => (abierto && datos ? datos.documentos[abierto.bando][abierto.tipo] : null);
    const def = () => (abierto && datos ? datos.definiciones[abierto.tipo] : null);
    const bandoElegido = () => ctx.bando();

    async function cargar() {
      if (!ctx.escenarioId()) return;
      try { datos = await ctx.api("GET", ctx.rutaEsc("/tiem"), undefined, true); } catch (_) { datos = null; }
      dibujarLista();
      if (abierto && !borrador) dibujarDialogo();
    }

    // ---------------------------------------------------------------- lista de la pestaña
    function dibujarLista() {
      const caja = $("tiem-docs");
      caja.replaceChildren();
      const b = bandoElegido();
      const docs = datos && datos.documentos[b];
      if (!docs) { caja.append(el("p", "vacio", "Sin documentos.")); return; }
      $("tiem-avance").textContent = textoAvance(docs);
      for (const g of porPaso(datos.orden, datos.definiciones)) {
        caja.append(el("h3", "tiem-paso", TITULOS_PASO[g.paso] || g.paso));
        const ol = el("ol", "tiem-lista");
        for (const tipo of g.tipos) {
          const d = docs[tipo];
          const df = datos.definiciones[tipo];
          const li = el("li");
          const est = textoEstado(d);
          const t = el("div", "texto");
          t.append(el("b", "", df.titulo), el("span", "ayuda", `Redactan: ${siglasRedactan(df)}${d.archivos.length ? ` · ${d.archivos.length} adjunto(s)` : ""}`));
          li.append(t, el("span", `chip ${est.clase}`, est.texto), boton("Abrir", () => abrir(b, tipo), "mini"));
          ol.append(li);
        }
        caja.append(ol);
      }
      dibujarEnsayos(b);
      dibujarOrden(b);
    }

    // ---------------------------------------------------------------- Orden de Operaciones (tareas -> órdenes)
    function dibujarOrden(b) {
      const esc = ctx.escenario();
      const plan = datos.documentos[b].plan_operaciones;
      const tareas = (plan && plan.contenido.tareas) || [];
      $("sec-orden-op").hidden = !!(esc && esc.ensayo_de);
      const turnoH = esc && esc.calendario ? esc.calendario.turno_h : null;
      const { vencen, proximas } = ordenDelDia(tareas, datos.ejecuciones && datos.ejecuciones[b], datos.turno_actual);
      const tipos = datos.definiciones.plan_operaciones.tipos_tarea;
      const pintar = (ul, items, vacio) => {
        ul.replaceChildren();
        if (!items.length) { ul.append(el("li", "vacio", vacio)); return; }
        for (const { tarea: t, ejecucion: e, estado } of items) {
          const li = el("li");
          const txt = el("div", "texto");
          const ref = refH(t.turno, turnoH);
          txt.append(el("b", "", textoTarea(t, tipos)), el("span", "ayuda", `Turno ${t.turno}${ref ? ` (${ref})` : ""}${t.detalle ? ` · ${t.detalle}` : ""}`));
          if (e && e.estado === "rechazada" && e.motivo) txt.append(el("span", "ayuda motivo", `Rechazada: ${e.motivo}`));
          const chip = { emitida: ["Emitida", "ok"], rechazada: ["Rechazada", "fuego"], pendiente: ["Pendiente", ""] }[estado];
          li.append(txt, el("span", `chip ${chip[1]}`, chip[0]));
          ul.append(li);
        }
      };
      pintar($("orden-vencen"), vencen, tareas.length ? "Ninguna tarea vence en este turno." : "El Plan de Operaciones todavía no tiene tareas.");
      pintar($("orden-proximas"), proximas, "Sin tareas en las próximas 24 horas.");
      const porEmitir = vencen.filter((x) => x.estado !== "emitida").length;
      $("btn-emitir-orden").disabled = !porEmitir;
      $("btn-emitir-orden").textContent = porEmitir ? `Emitir ${porEmitir} tarea(s) de este turno como órdenes` : "No hay tareas por emitir";
      $("btn-emitir-orden").hidden = (ctx.usuario() || {}).rol === "observador";
    }

    async function emitirOrden() {
      try {
        const r = await ctx.api("POST", ctx.rutaEsc(`/tiem/${bandoElegido()}/emitir`), {});
        const malas = r.resultados.filter((x) => !x.ok);
        ctx.toast(`${r.emitidas} orden(es) emitida(s)${malas.length ? `; ${malas.length} rechazada(s): ${malas.map((x) => x.motivo).join(" · ")}` : ""}.`, !malas.length);
        cargar();
      } catch (_) { /* toast ya mostrado */ }
    }

    // ---------------------------------------------------------------- juego de guerra: ensayos
    function dibujarEnsayos(b) {
      const esc = ctx.escenario();
      $("ensayo-aviso").hidden = !(esc && esc.ensayo_de);
      $("sec-ensayos").hidden = !!(esc && esc.ensayo_de);
      $("sec-apreciacion").hidden = !!(esc && esc.ensayo_de); // los documentos se redactan en el ejercicio original
      if (esc && esc.ensayo_de) {
        $("ensayo-aviso-texto").textContent = `Esto es un ensayo (juego de guerra) de «${esc.ensayo_fa}»: la IA conduce al enemigo y el turno se resuelve en cuanto su bando confirma.`;
        return;
      }
      const formas = (datos.contexto && datos.contexto[b] && datos.contexto[b].formas) || [];
      const sel = $("ensayo-fa");
      const previo = sel.value;
      sel.replaceChildren(...formas.map((f) => new Option(f, f)));
      if (formas.includes(previo)) sel.value = previo;
      const puede = !!(datos.puede_ensayar && datos.puede_ensayar[b]);
      $("ensayo-crear").hidden = !puede || !formas.length;
      $("ensayo-sin-fa").hidden = !!formas.length;
      const ul = $("ensayos-lista");
      ul.replaceChildren();
      for (const e of (datos.ensayos && datos.ensayos[b]) || []) {
        const li = el("li");
        const t = el("div", "texto");
        t.append(el("b", "", e.nombre), el("span", "ayuda", e.texto));
        li.append(t, boton("Ir al ensayo", () => ctx.irEscenario(e.id), "mini"));
        ul.append(li);
      }
    }

    async function ensayar() {
      const fa = $("ensayo-fa").value;
      if (!fa) return;
      if (!confirm(`Se creará una copia del ejercicio en su estado actual para ensayar «${fa}» contra la IA. ¿Continuar?`)) return;
      try {
        const e = await ctx.api("POST", ctx.rutaEsc(`/tiem/${bandoElegido()}/ensayos`), { fa });
        ctx.toast(`Ensayo creado: ${e.nombre}. Ábralo con «Ir al ensayo».`, true);
        await ctx.recargarEscenarios();
        cargar();
      } catch (_) { /* toast ya mostrado */ }
    }

    // ---------------------------------------------------------------- diálogo
    function abrir(bando, tipo) {
      abierto = { bando, tipo };
      borrador = null;
      dibujarDialogo();
      const dlg = $("dlg-tiem");
      if (!dlg.open) dlg.showModal();
    }

    function cerrar() {
      if (borrador && !confirm("Hay cambios sin guardar. ¿Cerrar igual?")) return;
      borrador = null;
      abierto = null;
      $("dlg-tiem").close();
    }

    function dibujarDialogo() {
      const d = doc();
      const df = def();
      if (!d || !df) return;
      const est = textoEstado(d);
      $("tiem-titulo").textContent = `${df.titulo} · ${abierto.bando === "azul" ? "Azul" : "Rojo"}`;
      const sub = $("tiem-sub");
      sub.replaceChildren(el("span", `chip ${est.clase}`, est.texto),
        el("span", "ayuda", ` ${df.paso} · Redactan: ${siglasRedactan(df)}${d.editado_por ? ` · última edición: ${d.editado_por} (${SIGLAS[d.editado_puesto] || d.editado_puesto})` : ""}`));
      const obs = $("tiem-observaciones");
      obs.hidden = !d.observaciones;
      obs.textContent = d.observaciones ? `Observaciones del instructor: ${d.observaciones}` : "";
      const cuerpo = $("tiem-cuerpo");
      cuerpo.replaceChildren();
      if (df.descripcion) cuerpo.append(el("p", "ayuda", df.descripcion));
      for (const c of df.campos) cuerpo.append(borrador ? campoEditable(c, df) : campoLectura(c, d.contenido[c.clave], df));
      dibujarRevision(borrador ? null : d.revision);
      dibujarAdjuntos(d);
      dibujarBotones(d);
    }

    function dibujarRevision(rev) {
      const caja = $("tiem-revision");
      caja.replaceChildren();
      if (!rev) return;
      if (rev.faltan.length) {
        const ul = el("ul", "faltan");
        rev.faltan.forEach((f) => ul.append(el("li", "", f)));
        caja.append(el("b", "", "Falta para poder presentarlo:"), ul);
      }
      if (rev.avisos.length) {
        const ul = el("ul", "avisos");
        rev.avisos.forEach((a) => ul.append(el("li", "", a)));
        caja.append(el("b", "", "Observaciones de forma (TIEM):"), ul);
      }
    }

    function dibujarAdjuntos(d) {
      const caja = $("tiem-adjuntos");
      caja.replaceChildren();
      for (const a of d.archivos) {
        const li = el("li");
        const enlace = el("a", "", a.nombre);
        enlace.href = ctx.rutaEsc(`/tiem/archivos/${a.id}`);
        enlace.download = a.nombre;
        li.append(enlace, el("span", "ayuda", ` · ${Math.max(1, Math.round(a.tamano / 1024))} KB · ${a.subido_por}`));
        if (d.puede_redactar) li.append(boton("×", () => quitarAdjunto(a.id), "mini peligro"));
        caja.append(li);
      }
      $("tiem-adjuntos-caja").hidden = !d.archivos.length && !d.puede_redactar;
      $("btn-tiem-adjuntar").hidden = !d.puede_redactar;
    }

    function dibujarBotones(d) {
      const caja = $("tiem-botones");
      caja.replaceChildren();
      const instructor = ctx.esInstructor();
      const bloqueado = !instructor && (d.estado === "presentado" || d.estado === "aprobado");
      if (borrador) {
        caja.append(boton("Traer datos del PMO y del escenario", traerSugerencias),
          boton("Guardar", guardar, ""), boton("Cancelar", () => { borrador = null; dibujarDialogo(); }));
      } else {
        if (d.puede_redactar && !bloqueado) caja.append(boton(d.existe ? "Editar" : "Redactar", () => { borrador = JSON.parse(JSON.stringify(d.contenido)); dibujarDialogo(); }, ""));
        if (d.puede_redactar && !instructor && (d.estado === "borrador" || d.estado === "devuelto") && d.existe) caja.append(boton("Presentar al instructor", presentar, ""));
        if (instructor) {
          caja.append(boton("Aprobar", () => revisar("aprobado"), ""), boton("Devolver con observaciones", () => revisar("devuelto")));
          if (d.estado !== "borrador") caja.append(boton("Reabrir como borrador", () => revisar("borrador")));
        }
      }
      caja.append(boton("Cerrar", cerrar));
    }

    // ---------------------------------------------------------------- lectura
    function bloquesTexto(texto) {
      const frag = document.createDocumentFragment();
      let ul = null;
      for (const b of Pmo.bloques(texto)) {
        if (b.tipo === "li") { if (!ul) { ul = el("ul"); frag.append(ul); } ul.append(el("li", "", b.texto)); }
        else { ul = null; frag.append(el("p", "", b.texto)); }
      }
      return frag;
    }

    function tablaLectura(columnas, filas) {
      const t = el("table", "tiem-tabla");
      const tr = el("tr");
      columnas.forEach((c) => tr.append(el("th", "", c.titulo)));
      t.append(tr);
      for (const f of filas) {
        const r = el("tr");
        columnas.forEach((c) => r.append(el("td", "", c.opciones.length ? textoOpcion(f[c.clave]) : f[c.clave] || "")));
        t.append(r);
      }
      return t;
    }

    function campoLectura(c, v, df) {
      const sec = el("section", "tiem-campo");
      sec.append(el("h4", "", c.titulo));
      const vacio = v == null || v === "" || (Array.isArray(v) && !v.length) || (c.tipo === "mision" && !Object.values(v).some(Boolean));
      if (vacio) { sec.append(el("p", "vacio", "—")); return sec; }
      if (c.tipo === "texto" || c.tipo === "linea") sec.append(bloquesTexto(v));
      else if (c.tipo === "mision") {
        sec.append(el("p", "pmo-mision", Pmo.textoMision(v)));
      } else if (c.tipo === "tabla") sec.append(tablaLectura(c.columnas, v));
      else if (c.tipo === "matriz") sec.append(matrizLectura(v));
      else if (c.tipo === "tareas") sec.append(tareasLectura(v));
      else if (c.tipo === "formas") {
        for (const fa of v) {
          const card = el("div", "tiem-fa");
          card.append(el("h5", "", `${fa.nombre || "F/A"}: ${fa.que}`));
          const dl = el("dl", "pmo-partes");
          for (const [k, t] of [["donde", "Dónde"], ["cuando", "Cuándo"], ["quien", "Quién"], ["como", "Cómo"]]) {
            if (!fa[k]) continue;
            const d = el("div");
            d.append(el("dt", "", t), el("dd", "", fa[k]));
            dl.append(d);
          }
          card.append(dl, el("p", "apa", resumenApa(fa)));
          const det = el("details");
          det.append(el("summary", "", "Análisis APA completo"));
          for (const s of df.campos_fa) {
            if (["nombre", "que", "donde", "cuando", "quien", "como"].includes(s.clave) || !fa[s.clave]) continue;
            const p = el("p");
            p.append(el("b", "", `${s.titulo}: `), document.createTextNode(s.tipo === "opcion" ? textoOpcion(fa[s.clave]) : fa[s.clave]));
            det.append(p);
          }
          card.append(det);
          sec.append(card);
        }
      }
      return sec;
    }

    function matrizLectura(celdas) {
      const { filas, columnas } = ejesMatriz(celdas, contextoActual());
      const t = el("table", "tiem-tabla tiem-matriz");
      const tr = el("tr");
      tr.append(el("th", "", "F/A \\ Capacidad del enemigo"), ...columnas.map((c) => el("th", "", c)));
      t.append(tr);
      for (const fa of filas) {
        const r = el("tr");
        r.append(el("th", "", fa));
        for (const cap of columnas) {
          const c = celdaDe(celdas, fa, cap);
          const td = el("td");
          if (c.efecto) td.append(el("span", `chip ${EFECTOS[c.efecto] || ""}`, textoOpcion(c.efecto)));
          if (c.analisis) td.append(el("p", "ayuda", c.analisis));
          r.append(td);
        }
        t.append(r);
      }
      return t;
    }

    function tareasLectura(tareas) {
      const esc = ctx.escenario();
      const turnoH = esc && esc.calendario ? esc.calendario.turno_h : null;
      const ej = (datos.ejecuciones && datos.ejecuciones[abierto.bando]) || {};
      const tipos = def().tipos_tarea;
      const t = el("table", "tiem-tabla");
      const tr = el("tr");
      ["Turno", "Unidad", "Acción", "Objetivo o destino", "Detalle", "Ejecución"].forEach((x) => tr.append(el("th", "", x)));
      t.append(tr);
      for (const x of [...tareas].sort((a, b) => (a.turno || 0) - (b.turno || 0))) {
        const r = el("tr");
        const e = ej[x.id];
        const ref = refH(x.turno, turnoH);
        [`${x.turno || "—"}${ref ? ` (${ref})` : ""}`, x.unidad_nombre, tipos[x.tipo] || "—", x.objetivo_nombre, x.detalle,
          e ? (e.estado === "emitida" ? `Emitida (turno ${e.turno})` : `Rechazada: ${e.motivo}`) : "Pendiente"]
          .forEach((v) => r.append(el("td", "", v || "")));
        t.append(r);
      }
      return t;
    }

    function editorTareas(c) {
      const caja = el("div", "tiem-editor-tabla");
      const tareas = borrador[c.clave] || (borrador[c.clave] = []);
      const op = (datos.opciones_tarea && datos.opciones_tarea[abierto.bando]) || { unidades: [], objetivos: [] };
      const tipos = def().tipos_tarea;
      const esc = ctx.escenario();
      const turnoH = esc && esc.calendario ? esc.calendario.turno_h : null;
      const pintar = () => {
        caja.replaceChildren();
        const t = el("table", "tiem-tabla");
        const tr = el("tr");
        ["Turno", "Unidad", "Acción", "Objetivo o destino", "Detalle (en infinitivo)", ""].forEach((x) => tr.append(el("th", "", x)));
        t.append(tr);
        tareas.forEach((x, i) => {
          const r = el("tr");
          const turno = el("input");
          turno.type = "number"; turno.min = 1; turno.value = x.turno || "";
          const ref = el("span", "ayuda", refH(x.turno, turnoH));
          turno.addEventListener("input", () => { x.turno = parseInt(turno.value, 10) || null; ref.textContent = refH(x.turno, turnoH); });
          const tdT = el("td"); tdT.append(turno, ref);
          const uni = el("select");
          uni.append(new Option("—", ""), ...op.unidades.map((u) => new Option(u.nombre, String(u.id))));
          uni.value = x.unidad_id ? String(x.unidad_id) : "";
          uni.addEventListener("change", () => { x.unidad_id = parseInt(uni.value, 10) || null; x.unidad_nombre = uni.selectedOptions[0] ? uni.selectedOptions[0].text : ""; });
          const acc = el("select");
          acc.append(new Option("—", ""), ...Object.entries(tipos).map(([k, v]) => new Option(v, k)));
          acc.value = x.tipo || "";
          acc.addEventListener("change", () => { x.tipo = acc.value; });
          const obj = el("select");
          obj.append(new Option("—", ""));
          const grupos = {};
          for (const o of op.objetivos) {
            if (!grupos[o.grupo]) { grupos[o.grupo] = el("optgroup"); grupos[o.grupo].label = o.grupo; obj.append(grupos[o.grupo]); }
            grupos[o.grupo].append(new Option(o.nombre, o.clave));
          }
          if (x.objetivo && ![...obj.options].some((o) => o.value === x.objetivo)) obj.append(new Option(x.objetivo_nombre || x.objetivo, x.objetivo));
          obj.value = x.objetivo || "";
          obj.addEventListener("change", () => { x.objetivo = obj.value; x.objetivo_nombre = obj.selectedOptions[0] ? obj.selectedOptions[0].text : ""; });
          const det = el("input");
          det.value = x.detalle || "";
          det.placeholder = "Atacar el día D a la hora H con 4 aviones…";
          det.addEventListener("input", () => { x.detalle = det.value; });
          for (const e of [uni, acc, obj, det]) { const td = el("td"); td.append(e); r.append(td); }
          r.prepend(tdT);
          const tdX = el("td");
          tdX.append(boton("×", () => { tareas.splice(i, 1); pintar(); }, "mini peligro"));
          r.append(tdX);
          t.append(r);
        });
        caja.append(t, boton("+ Agregar tarea", () => { tareas.push({ id: nuevoId(), turno: (esc && esc.turno_actual) || 1 }); pintar(); }, "mini"));
      };
      pintar();
      return caja;
    }

    const contextoActual = () => (datos && datos.contexto && abierto ? datos.contexto[abierto.bando] : null);

    function editorMatriz(c) {
      const celdas = borrador[c.clave] || (borrador[c.clave] = []);
      const { filas, columnas } = ejesMatriz(celdas, contextoActual());
      if (!filas.length || !columnas.length) {
        return el("p", "vacio", "Primero se necesitan las Formas de Acción y las capacidades del enemigo (Guía de Planeamiento o Apreciación de Inteligencia).");
      }
      const t = el("table", "tiem-tabla tiem-matriz");
      const tr = el("tr");
      tr.append(el("th", "", "F/A \\ Capacidad del enemigo"), ...columnas.map((x) => el("th", "", x)));
      t.append(tr);
      for (const fa of filas) {
        const r = el("tr");
        r.append(el("th", "", fa));
        for (const cap of columnas) {
          const td = el("td");
          const celda = () => {
            let x = celdas.find((y) => y.fa === fa && y.capacidad === cap);
            if (!x) { x = { fa, capacidad: cap, efecto: "", analisis: "" }; celdas.push(x); }
            return x;
          };
          const actual = celdaDe(celdas, fa, cap);
          const sel = el("select");
          sel.append(new Option("—", ""), ...(def().efectos || []).map((e) => new Option(textoOpcion(e), e)));
          sel.value = actual.efecto || "";
          sel.addEventListener("change", () => { celda().efecto = sel.value; });
          const ta = el("textarea");
          ta.rows = 2;
          ta.placeholder = "Análisis";
          ta.value = actual.analisis || "";
          ta.addEventListener("input", () => { celda().analisis = ta.value; });
          td.append(sel, ta);
          r.append(td);
        }
        t.append(r);
      }
      return t;
    }

    // ---------------------------------------------------------------- edición
    function campoEditable(c, df) {
      const sec = el("section", "tiem-campo editando");
      sec.append(el("h4", "", c.titulo + (c.requerido ? "" : " (opcional)")));
      if (c.ayuda) sec.append(el("p", "ayuda", c.ayuda));
      const v = borrador[c.clave];
      if (c.tipo === "texto" || c.tipo === "linea") {
        const e = c.tipo === "texto" ? el("textarea") : el("input");
        if (c.tipo === "texto") e.rows = 4;
        e.value = v || "";
        e.addEventListener("input", () => { borrador[c.clave] = e.value; });
        sec.append(e);
      } else if (c.tipo === "mision") sec.append(editorMision(c.clave));
      else if (c.tipo === "tabla") sec.append(editorTabla(c));
      else if (c.tipo === "formas") sec.append(editorFormas(c, df));
      else if (c.tipo === "matriz") sec.append(editorMatriz(c));
      else if (c.tipo === "tareas") sec.append(editorTareas(c));
      return sec;
    }

    function editorMision(clave) {
      const caja = el("div", "pmo-mision-form");
      const m = borrador[clave] || (borrador[clave] = {});
      const prev = el("p", "pmo-mision");
      const avisos = el("ul", "avisos");
      const actualizar = () => {
        prev.textContent = Pmo.textoMision(m) || "(la misión se arma con sus partes)";
        avisos.replaceChildren(...Pmo.avisosMision(m).map((a) => el("li", "", a)));
      };
      for (const [k, nombre, ejemplo] of Pmo.PARTES_MISION) {
        const lab = el("label", "mini", nombre);
        const inp = el("input");
        inp.placeholder = ejemplo;
        inp.value = m[k] || "";
        inp.addEventListener("input", () => { m[k] = inp.value; actualizar(); });
        lab.append(inp);
        caja.append(lab);
      }
      caja.append(prev, avisos);
      actualizar();
      return caja;
    }

    function editorTabla(c) {
      const caja = el("div", "tiem-editor-tabla");
      const filas = borrador[c.clave] || (borrador[c.clave] = []);
      const pintar = () => {
        caja.replaceChildren();
        const t = el("table", "tiem-tabla");
        const tr = el("tr");
        c.columnas.forEach((col) => tr.append(el("th", "", col.titulo)));
        tr.append(el("th", "", ""));
        t.append(tr);
        filas.forEach((f, i) => {
          const r = el("tr");
          for (const col of c.columnas) {
            const td = el("td");
            let e;
            if (col.opciones.length) {
              e = el("select");
              e.append(new Option("—", ""), ...col.opciones.map((o) => new Option(textoOpcion(o), o)));
            } else e = el("input");
            e.value = f[col.clave] || "";
            e.addEventListener("input", () => { f[col.clave] = e.value; });
            e.addEventListener("change", () => { f[col.clave] = e.value; });
            td.append(e);
            r.append(td);
          }
          const td = el("td");
          td.append(boton("×", () => { filas.splice(i, 1); pintar(); }, "mini peligro"));
          r.append(td);
          t.append(r);
        });
        caja.append(t, boton("+ Agregar fila", () => { filas.push({}); pintar(); }, "mini"));
      };
      pintar();
      return caja;
    }

    function editorFormas(c, df) {
      const caja = el("div", "tiem-editor-formas");
      const formas = borrador[c.clave] || (borrador[c.clave] = []);
      const pintar = () => {
        caja.replaceChildren();
        formas.forEach((fa, i) => {
          const card = el("fieldset", "tiem-fa");
          card.append(el("legend", "", fa.nombre || `F/A ${i + 1}`));
          for (const s of df.campos_fa) {
            const lab = el("label", `mini fa-${s.tipo} fa-${s.clave}`, s.titulo);
            let e;
            if (s.tipo === "opcion") { e = el("select"); e.append(new Option("—", ""), ...s.opciones.map((o) => new Option(textoOpcion(o), o))); }
            else if (s.tipo === "texto") { e = el("textarea"); e.rows = 2; }
            else e = el("input");
            e.value = fa[s.clave] || "";
            const guardarValor = () => { fa[s.clave] = e.value; if (s.clave === "nombre") card.querySelector("legend").textContent = e.value || `F/A ${i + 1}`; };
            e.addEventListener("input", guardarValor);
            e.addEventListener("change", guardarValor);
            lab.append(e);
            card.append(lab);
          }
          card.append(boton("Quitar esta F/A", () => { formas.splice(i, 1); pintar(); }, "mini peligro"));
          caja.append(card);
        });
        caja.append(boton("+ Agregar Forma de Acción", () => { formas.push({ nombre: `F/A ${formas.length + 1}` }); pintar(); }, "mini"));
      };
      pintar();
      return caja;
    }

    // ---------------------------------------------------------------- acciones
    const rutaDoc = (sufijo = "") => ctx.rutaEsc(`/tiem/${abierto.bando}/${abierto.tipo}${sufijo}`);

    function reemplazar(d) {
      datos.documentos[abierto.bando][abierto.tipo] = d;
      dibujarLista();
      dibujarDialogo();
    }

    async function traerSugerencias() {
      try {
        const r = await ctx.api("GET", rutaDoc("/sugerencias"));
        const { contenido, llenados } = completarVacios(borrador, r.contenido);
        borrador = contenido;
        dibujarDialogo();
        ctx.toast(llenados.length ? `Se completaron ${llenados.length} campo(s) vacío(s); revíselos y complete el análisis.` : "No había campos vacíos que el simulador pueda completar.", true);
      } catch (_) { /* toast ya mostrado */ }
    }

    async function guardar() {
      try {
        const d = await ctx.api("PUT", rutaDoc(), { contenido: borrador });
        borrador = null;
        reemplazar(d);
        ctx.toast("Documento guardado", true);
      } catch (_) { /* toast ya mostrado */ }
    }

    async function presentar() {
      if (!confirm("Al presentarlo, el documento queda bloqueado hasta que el instructor lo revise. ¿Presentar?")) return;
      try { reemplazar(await ctx.api("POST", rutaDoc("/presentar"))); ctx.toast("Presentado al instructor", true); } catch (_) { /* toast */ }
    }

    async function revisar(estado) {
      let observaciones = doc().observaciones || "";
      if (estado === "devuelto") {
        const o = prompt("Observaciones para el bando:", observaciones);
        if (o === null) return;
        observaciones = o;
      }
      try { reemplazar(await ctx.api("POST", rutaDoc("/revisar"), { estado, observaciones })); } catch (_) { /* toast */ }
    }

    async function quitarAdjunto(id) {
      if (!confirm("¿Quitar el archivo adjunto?")) return;
      try { reemplazar(await ctx.api("DELETE", ctx.rutaEsc(`/tiem/archivos/${id}`))); } catch (_) { /* toast */ }
    }

    $("tiem-archivo").addEventListener("change", () => {
      const f = $("tiem-archivo").files[0];
      $("tiem-archivo").value = "";
      if (!f || !abierto) return;
      if (f.size > 10 * 1024 * 1024) return ctx.toast("El archivo debe pesar menos de 10 MB.");
      const lector = new FileReader();
      lector.onload = async () => {
        const datosB64 = String(lector.result).split(",")[1] || "";
        try { reemplazar(await ctx.api("POST", rutaDoc("/archivos"), { nombre: f.name, datos: datosB64 })); ctx.toast("Archivo adjuntado", true); } catch (_) { /* toast */ }
      };
      lector.readAsDataURL(f);
    });
    $("btn-tiem-adjuntar").addEventListener("click", () => $("tiem-archivo").click());
    $("btn-ensayar").addEventListener("click", ensayar);
    $("btn-emitir-orden").addEventListener("click", emitirOrden);
    $("ensayo-volver").addEventListener("click", () => { const e = ctx.escenario(); if (e && e.ensayo_de) ctx.irEscenario(e.ensayo_de); });
    $("dlg-tiem").addEventListener("cancel", (e) => { e.preventDefault(); cerrar(); });

    return {
      cargar,
      dibujarLista,
      /** En cada estado: recarga cuando cambia el escenario o llega un aviso del TIEM. */
      render(data) {
        const avisos = (data.eventos || []).filter((ev) => ev.tipo === "tiem").map((ev) => ev.id);
        // tambien al cambiar de turno: la Orden de Operaciones y las unidades conocidas cambian
        const nueva = `${data.escenario.id}:${data.escenario.turno_actual}:${avisos.length ? Math.max(...avisos) : 0}`;
        if (nueva !== firma) { firma = nueva; cargar(); }
      },
      reiniciar() { datos = null; firma = ""; abierto = null; borrador = null; if ($("dlg-tiem").open) $("dlg-tiem").close(); },
    };
  }

  const api = { ESTADOS, textoEstado, textoAvance, textoOpcion, completarVacios, resumenApa, ejesMatriz, celdaDe, porPaso,
    refH, ordenDelDia, textoTarea, crear };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Tiem = api;
})(typeof window !== "undefined" ? window : globalThis);
