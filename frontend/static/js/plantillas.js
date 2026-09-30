/* Plantillas guardadas por el instructor: boton "Guardar como plantilla…" (cabecera) con su dialogo, y el
 * control "Eliminar" de las plantillas de usuario en la lista de "Desde plantilla…" (que dibuja app.js).
 * Modulo independiente: no toca app.js; habla con el servidor por su cuenta. Las funciones puras
 * (etiquetaOrigen, emparejar) se prueban con Node. */
(function (raiz) {
  "use strict";

  /** Texto secundario de una plantilla en la lista: de donde salio y si conserva el estado. */
  function etiquetaOrigen(p) {
    if (p.origen !== "usuario") return "Plantilla del sistema";
    const fecha = (p.guardada_en || "").slice(0, 16).replace("T", " ");
    return "Guardada por un instructor" + (fecha ? ` el ${fecha}` : "") + (p.con_estado ? " · conserva el estado" : "");
  }

  /** Empareja los <li> de la lista (por el nombre en su <b>) con las plantillas del servidor, en orden. */
  function emparejar(nombres, plantillas) {
    const pendientes = [...plantillas];
    return nombres.map((nombre) => {
      const i = pendientes.findIndex((p) => p.nombre === nombre);
      return i >= 0 ? pendientes.splice(i, 1)[0] : null;
    });
  }

  const api = { etiquetaOrigen, emparejar };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  raiz.Plantillas = api;
  if (typeof document === "undefined") return;

  const $ = (id) => document.getElementById(id);
  if (!$("btn-guardar-plantilla") || !$("dlg-guardar-plantilla")) return;

  let toastTimer = null;
  function toast(msg, ok = false) {
    const t = $("toast");
    if (!t) return;
    t.textContent = msg;
    t.className = ok ? "ok" : "";
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 4500);
  }

  async function llamar(metodo, ruta, cuerpo) {
    const resp = await fetch(ruta, {
      method: metodo, headers: { "Content-Type": "application/json" },
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined, credentials: "same-origin",
    });
    let datos = null;
    try { datos = await resp.json(); } catch (_) { /* sin cuerpo */ }
    if (!resp.ok) {
      const err = new Error((datos && typeof datos.detail === "string") ? datos.detail : resp.statusText);
      err.status = resp.status;
      throw err;
    }
    return datos;
  }

  const escenarioActual = () => parseInt($("escenario").value, 10) || null;

  // ---------- guardar el escenario actual ----------
  $("btn-guardar-plantilla").addEventListener("click", () => {
    if (!escenarioActual()) return toast("Elija primero un escenario.");
    $("gp-form").reset();
    $("gp-error").hidden = true;
    $("gp-reemplazar-fila").hidden = true;
    const sel = $("escenario");
    const texto = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].textContent : "";
    $("gp-nombre").value = texto.replace(/^\d+ - /, "").replace(/ \(archivado\)$/, "");
    $("dlg-guardar-plantilla").showModal();
    $("gp-nombre").focus();
  });
  $("gp-cancelar").addEventListener("click", () => $("dlg-guardar-plantilla").close());
  $("gp-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = escenarioActual();
    if (!id) return;
    const cuerpo = {
      nombre: $("gp-nombre").value.trim(), descripcion: $("gp-descripcion").value.trim(),
      con_estado: $("gp-con-estado").checked, reemplazar: $("gp-reemplazar").checked,
    };
    $("gp-guardar").disabled = true;
    try {
      const p = await llamar("POST", `/api/escenarios/${id}/guardar_plantilla`, cuerpo);
      $("dlg-guardar-plantilla").close();
      toast(`Plantilla «${p.nombre}» guardada (${p.unidades} unidades, ${p.objetivos} objetivos). Ya está en «Desde plantilla…».`, true);
    } catch (err) {
      $("gp-error").textContent = err.message;
      $("gp-error").hidden = false;
      if (err.status === 409) $("gp-reemplazar-fila").hidden = false;
    } finally {
      $("gp-guardar").disabled = false;
    }
  });

  // ---------- eliminar plantillas de usuario desde la lista de "Desde plantilla…" ----------
  let catalogo = [];
  $("btn-plantillas").addEventListener("click", async () => {
    try { catalogo = (await llamar("GET", "/api/plantillas")).plantillas || []; } catch (_) { catalogo = []; }
    decorar();
  });

  function decorar() {
    const lista = $("plantilla-lista");
    const items = [...lista.querySelectorAll(":scope > li")].filter((li) => !li.dataset.plantillaId);
    if (!items.length || !catalogo.length) return;
    const nombres = items.map((li) => (li.querySelector("b") || {}).textContent || "");
    emparejar(nombres, catalogo).forEach((p, i) => {
      if (!p) return;
      const li = items[i];
      li.dataset.plantillaId = p.id;
      const info = li.querySelector("div");
      const origen = document.createElement("small");
      origen.className = "origen-plantilla";
      origen.textContent = " · " + etiquetaOrigen(p);
      if (info) info.appendChild(origen);
      if (p.origen !== "usuario") return;
      const b = document.createElement("button");
      b.type = "button";
      b.className = "mini secundario peligro";
      b.textContent = "Eliminar";
      b.title = "Borrar esta plantilla del servidor (no afecta a los escenarios ya creados)";
      b.addEventListener("click", async () => {
        if (!window.confirm(`¿Eliminar la plantilla «${p.nombre}»? Los escenarios creados con ella no cambian.`)) return;
        try {
          await llamar("DELETE", `/api/plantillas/${encodeURIComponent(p.id)}`);
          li.remove();
          catalogo = catalogo.filter((x) => x.id !== p.id);
          toast(`Plantilla «${p.nombre}» eliminada`, true);
        } catch (err) { toast(err.message); }
      });
      li.appendChild(b);
    });
  }
  // app.js llena la lista de forma asincrona: se decora cuando aparecen los <li>
  new MutationObserver(decorar).observe($("plantilla-lista"), { childList: true });
})(typeof window !== "undefined" ? window : globalThis);
