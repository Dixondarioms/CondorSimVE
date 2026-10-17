/* Pestaña PMO (TIEM): el Problema Militar Operativo del bando y el calendario de la operación (día D, hora H y
 * fases). Cada bando lee el suyo; el instructor ve los dos, los redacta o los genera a partir del escenario.
 * Funciones puras (se prueban con Node) y el dibujo de la pestaña, que app.js llama en cada estado nuevo. */
(function (raiz) {
  "use strict";

  const PARTES_MISION = [
    ["tarea", "Tarea", "Verbo en infinitivo: Conducir, Neutralizar, Defender…"],
    ["que", "Qué", "para obtener la superioridad aérea local…"],
    ["donde", "Dónde", "en el área de operaciones del Teatro…"],
    ["cuando", "Cuándo", "a partir del día D a la hora H…"],
    ["proposito", "Propósito (a fin de…)", "contribuir a que el Teatro de Operaciones…"],
  ];

  /** "TAREA qué dónde cuándo, a fin de PROPÓSITO." a partir de sus partes (igual que engine/pmo.py). */
  function textoMision(m) {
    const p = (k) => String((m || {})[k] || "").trim();
    const cuerpo = ["tarea", "que", "donde", "cuando"].map(p).filter(Boolean).join(" ");
    if (!cuerpo) return "";
    return p("proposito") ? `${cuerpo}, a fin de ${p("proposito")}.` : `${cuerpo}.`;
  }

  /** Reglas del TIEM para enunciar la misión (mismas que el servidor). */
  function avisosMision(m) {
    const p = (k) => String((m || {})[k] || "").trim();
    const avisos = [];
    const primera = p("tarea").split(" ")[0].toLowerCase();
    if (!p("tarea")) avisos.push("Falta la tarea.");
    else if (!/(ar|er|ir|ár|ér|ír)$/.test(primera)) avisos.push("La tarea debe empezar con un verbo en infinitivo (conducir, neutralizar, defender...).");
    for (const [k, nombre] of [["que", "qué"], ["donde", "dónde"], ["cuando", "cuándo"]]) if (!p(k)) avisos.push(`Falta el ${nombre} de la tarea.`);
    if (!p("proposito")) avisos.push("Falta el propósito (\"a fin de...\").");
    const todo = ` ${PARTES_MISION.map(([k]) => p(k)).join(" ").toLowerCase()} `;
    if ([" si ", " en caso de ", " de ser posible", " siempre que "].some((c) => todo.includes(c))) {
      avisos.push("La misión no debe contener condiciones (si, en caso de, de ser posible).");
    }
    return avisos;
  }

  /** Texto en bloques: líneas que empiezan con "- " son viñetas, el resto párrafos. */
  function bloques(texto) {
    return String(texto || "").split("\n").map((l) => l.trim()).filter(Boolean)
      .map((l) => (l.startsWith("- ") ? { tipo: "li", texto: l.slice(2) } : { tipo: "p", texto: l }));
  }

  /** Filas del calendario: [{nombre, rango, actual}] con los turnos y las referencias H de cada fase. */
  function filasFases(cal, turno) {
    if (!cal || !cal.fases) return [];
    const ref = (t) => {
      if (!cal.turno_h) return `turno ${t}`;
      const n = t - cal.turno_h;
      return n === 0 ? "H" : `H${n > 0 ? "+" : ""}${n}`;
    };
    return cal.fases.map((f) => ({
      nombre: raiz.Logica ? raiz.Logica.nombreFase(f.nombre) : f.nombre,
      rango: `turnos ${f.desde}–${f.hasta ?? "…"} (${ref(f.desde)}${f.hasta ? ` a ${ref(f.hasta)}` : " en adelante"})`,
      actual: turno >= f.desde && (f.hasta == null || turno <= f.hasta),
    }));
  }

  // ------------------------------------------------------------------ pestaña
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const el = (tag, clase, texto) => {
      const e = document.createElement(tag);
      if (clase) e.className = clase;
      if (texto !== undefined) e.textContent = texto;
      return e;
    };
    let datos = null; // respuesta de GET /pmo
    let firma = "";
    let editando = false;

    const bandoElegido = () => {
      const rol = (ctx.usuario() || {}).rol;
      return rol === "azul" || rol === "rojo" ? rol : $("pmo-bando").value;
    };

    async function cargar() {
      if (!ctx.escenarioId()) return;
      try {
        datos = await ctx.api("GET", ctx.rutaEsc("/pmo"), undefined, true);
      } catch (_) { datos = null; }
      dibujar();
    }

    function dibujarCalendario(data) {
      const caja = $("pmo-calendario");
      caja.replaceChildren();
      const esc = data && data.escenario;
      const cal = esc && esc.calendario;
      if (!cal) {
        caja.append(el("p", "vacio", "Sin calendario: el instructor no fijó el día D ni la hora H."));
        return;
      }
      const linea = (etq, texto, clase = "") => {
        const pp = el("p", `cal-linea ${clase}`.trim());
        pp.append(el("span", "", `${etq}: `), el("b", "", texto));
        caja.append(pp);
      };
      linea("Día D", cal.dia_d || "a determinar");
      linea("Hora H", cal.turno_h ? `${cal.hora_h || "--:--"} (turno ${cal.turno_h})` : "a determinar");
      if (cal.turno_final) linea("Último turno previsto", String(cal.turno_final));
      const ahora = raiz.Logica ? raiz.Logica.textoCalendario(cal) : "";
      linea("Ahora", [ahora, [cal.actual.fecha, cal.actual.hora].filter(Boolean).join(" ")].filter(Boolean).join(" · "), "ahora");
      const ol = el("ol", "fases-operacion");
      for (const f of filasFases(cal, esc.turno_actual)) {
        const li = el("li", f.actual ? "actual" : "");
        li.append(el("b", "", f.nombre), el("span", "", ` · ${f.rango}`));
        ol.append(li);
      }
      if (ol.children.length) caja.append(ol);
    }

    function dibujarDocumento() {
      const doc = $("pmo-doc");
      doc.replaceChildren();
      const b = bandoElegido();
      const pm = datos && datos.bandos && datos.bandos[b];
      $("pmo-origen").textContent = pm && pm.existe ? (pm.origen === "automatico" ? "generado por el simulador" : "redactado por el instructor") : "";
      if (!pm || !pm.existe) {
        doc.append(el("p", "vacio", ctx.esInstructor()
          ? "Este bando aún no tiene Problema Militar. Redáctelo o use «Crear la situación automáticamente»."
          : "El escalón superior todavía no emitió el Problema Militar Operativo."));
        return;
      }
      for (const campo of datos.campos) {
        const sec = el("section", "pmo-campo");
        sec.append(el("h3", "", campo.titulo));
        if (campo.clave === "mision") {
          sec.append(el("p", "pmo-mision", pm.mision_texto || "(sin misión)"));
          const partes = el("dl", "pmo-partes");
          for (const [k, nombre] of PARTES_MISION) {
            const d = el("div");
            d.append(el("dt", "", nombre), el("dd", "", pm.contenido.mision[k] || "—"));
            partes.append(d);
          }
          sec.append(partes);
          if (ctx.esInstructor() && pm.avisos_mision.length) {
            const ul = el("ul", "avisos");
            pm.avisos_mision.forEach((a) => ul.append(el("li", "", a)));
            sec.append(ul);
          }
        } else {
          let ul = null;
          for (const bl of bloques(pm.contenido[campo.clave])) {
            if (bl.tipo === "li") {
              if (!ul) { ul = el("ul"); sec.append(ul); }
              ul.append(el("li", "", bl.texto));
            } else {
              ul = null;
              sec.append(el("p", "", bl.texto));
            }
          }
          if (!pm.contenido[campo.clave]) sec.append(el("p", "vacio", "—"));
        }
        doc.append(sec);
      }
    }

    function abrirEdicion() {
      if (!datos) return;
      const pm = datos.bandos[bandoElegido()];
      const c = (pm && pm.contenido) || {};
      const form = $("pmo-form");
      form.replaceChildren();
      for (const campo of datos.campos) {
        if (campo.clave === "mision") {
          const fs = el("fieldset", "pmo-mision-form");
          fs.append(el("legend", "", campo.titulo));
          for (const [k, nombre, ejemplo] of PARTES_MISION) {
            const lab = el("label", "mini", nombre);
            const inp = el("input");
            inp.dataset.mision = k;
            inp.maxLength = 600;
            inp.placeholder = ejemplo;
            inp.value = (c.mision || {})[k] || "";
            inp.addEventListener("input", previsualizar);
            lab.append(inp);
            fs.append(lab);
          }
          fs.append(el("p", "pmo-mision", ""), el("ul", "avisos"));
          form.append(fs);
        } else {
          const lab = el("label", "pmo-texto", campo.titulo);
          const ta = el("textarea");
          ta.dataset.campo = campo.clave;
          ta.rows = campo.clave === "situacion_general" || campo.clave === "fuerzas_enemigas" ? 6 : 4;
          ta.maxLength = 6000;
          ta.value = c[campo.clave] || "";
          lab.append(ta);
          form.append(lab);
        }
      }
      const fila = el("div", "fila-botones");
      const guardar = el("button", "", "Guardar y enviar al bando");
      guardar.type = "submit";
      const cancelar = el("button", "secundario", "Cancelar");
      cancelar.type = "button";
      cancelar.addEventListener("click", () => { editando = false; dibujar(); });
      fila.append(guardar, cancelar);
      form.append(el("p", "ayuda", "Las líneas que empiezan con «- » se muestran como viñetas."), fila);
      editando = true;
      previsualizar();
      dibujar();
    }

    function leerFormulario() {
      const form = $("pmo-form");
      const contenido = { mision: {} };
      form.querySelectorAll("textarea[data-campo]").forEach((t) => { contenido[t.dataset.campo] = t.value; });
      form.querySelectorAll("input[data-mision]").forEach((i) => { contenido.mision[i.dataset.mision] = i.value; });
      return contenido;
    }

    function previsualizar() {
      const form = $("pmo-form");
      const m = leerFormulario().mision;
      const prev = form.querySelector(".pmo-mision-form .pmo-mision");
      const ul = form.querySelector(".pmo-mision-form .avisos");
      if (!prev) return;
      prev.textContent = textoMision(m) || "(la misión se arma con sus partes)";
      ul.replaceChildren(...avisosMision(m).map((a) => el("li", "", a)));
    }

    function dibujar() {
      $("pmo-doc").hidden = editando;
      $("pmo-form").hidden = !editando;
      $("btn-pmo-editar").textContent = editando ? "Editando…" : "Redactar / corregir";
      $("btn-pmo-editar").disabled = editando;
      if (!editando) dibujarDocumento();
    }

    $("pmo-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        datos = await ctx.api("PUT", ctx.rutaEsc(`/pmo/${bandoElegido()}`), { contenido: leerFormulario() });
        editando = false;
        ctx.toast("Problema Militar guardado y enviado al bando", true);
        dibujar();
      } catch (_) { /* toast ya mostrado */ }
    });
    $("btn-pmo-editar").addEventListener("click", abrirEdicion);
    $("pmo-bando").addEventListener("change", () => { editando = false; dibujar(); });
    $("btn-pmo-generar").addEventListener("click", async () => {
      const sobrescribir = $("pmo-sobrescribir").checked;
      if (sobrescribir && !confirm("Se reemplazará también lo que redactó a mano. ¿Continuar?")) return;
      try {
        const r = await ctx.api("POST", ctx.rutaEsc("/pmo/generar"), { sobrescribir });
        datos = r;
        editando = false;
        const h = r.hecho;
        const partes = [h.pmo.length ? `PMO de ${h.pmo.join(" y ")}` : "ningún PMO reemplazado (había textos del instructor)"];
        if (h.calendario) partes.push("calendario D/H");
        if (h.objetivos) partes.push(`${h.objetivos} objetivos de la cadena`);
        ctx.toast(`Situación creada: ${partes.join(", ")}.`, true);
        dibujar();
      } catch (_) { /* toast ya mostrado */ }
    });

    return {
      cargar,
      /** En cada estado: el calendario siempre; el documento, cuando cambia el escenario o llega un aviso de PMO. */
      render(data) {
        dibujarCalendario(data);
        const avisos = (data.eventos || []).filter((ev) => ev.tipo === "pmo").map((ev) => ev.id);
        const nueva = `${data.escenario.id}:${avisos.length ? Math.max(...avisos) : 0}`;
        if (nueva !== firma) {
          firma = nueva;
          editando = false;
          cargar();
        }
      },
      reiniciar() { datos = null; firma = ""; editando = false; },
    };
  }

  const api = { PARTES_MISION, textoMision, avisosMision, bloques, filasFases, crear };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else raiz.Pmo = api;
})(typeof window !== "undefined" ? window : globalThis);
