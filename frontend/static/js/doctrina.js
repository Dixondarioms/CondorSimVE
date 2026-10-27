/* Doctrina y reglas de enfrentamiento del Cóndor (backend/app/engine/doctrina.py): para todo el bando (el director, el
 * Comandante y el JEM) o para la unidad seleccionada (quien la conduce); lo que la unidad no fija, lo hereda del bando. */
(function (raiz) {
  "use strict";

  const CAMPOS = [
    ["armas_aire", [["libre", "Libre"], ["restringido", "Solo identificados"], ["retenido", "Solo con orden"]]],
    ["armas_superficie", [["libre", "Libre"], ["restringido", "Solo identificados"], ["retenido", "Solo con orden"]]],
    ["disparos_por_blanco", [[0, "Según el arma"], [1, "1 misil"], [2, "2 misiles"], [4, "4 misiles"]]],
    ["distancia_pct", [[100, "100 % del alcance"], [75, "75 % del alcance"], [50, "50 % del alcance"]]],
    ["combustible_regreso", [[20, "20 %"], [25, "25 %"], [30, "30 %"], [40, "40 %"], [50, "50 %"]]],
    ["regreso_sin_armas", [[true, "Regresa a la base"], [false, "Sigue en su tarea"]]],
  ];

  /** Texto de un valor de un campo ("Solo identificados", "2 misiles"...). */
  function etiqueta(campo, valor) {
    const c = CAMPOS.find(([k]) => k === campo);
    const o = c && c[1].find(([v]) => String(v) === String(valor));
    return o ? o[1] : String(valor);
  }

  /** Valor del formulario ("" = heredar del bando). */
  function leer(campo, texto) {
    if (texto === "") return null;
    if (campo === "regreso_sin_armas") return texto === "true";
    if (campo.startsWith("armas_")) return texto;
    return Number(texto);
  }

  /** ctx: { api, rutaEsc, toast, enSilencio, esInstructor(), puedeBando(), rol(), seleccionada() } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    let datos = null;
    let sucio = false;

    function ambitos() {
      const lista = [];
      const u = ctx.seleccionada();
      const rol = ctx.rol();
      if (u && (ctx.esInstructor() || u.bando === rol)) lista.push([`unidad:${u.id}`, `Unidad: ${u.nombre}`]);
      if (ctx.esInstructor()) lista.push(["bando:azul", "Todo el bando Azul"], ["bando:rojo", "Todo el bando Rojo"]);
      else if (ctx.puedeBando()) lista.push([`bando:${rol}`, "Todo el bando"]);
      return lista;
    }

    function delBando(bando) {
      return datos && datos.doctrina && datos.doctrina[bando] ? datos.doctrina[bando].valores : null;
    }

    function pintar() {
      const sel = $("doc-ambito");
      const lista = ambitos();
      $("sec-doctrina").hidden = !lista.length;
      if (!lista.length) return;
      const previo = sel.value;
      while (sel.firstChild) sel.removeChild(sel.firstChild);
      for (const [v, t] of lista) sel.appendChild(Object.assign(document.createElement("option"), { value: v, textContent: t }));
      sel.value = lista.some(([v]) => v === previo) ? previo : lista[0][0];
      if (!sucio) cargarValores();
    }

    function cargarValores() {
      const [tipo, id] = $("doc-ambito").value.split(":");
      let bando = id;
      let propia = null;
      if (tipo === "unidad") {
        const u = datos.unidades.find((x) => String(x.id) === id);
        if (!u) return;
        bando = u.bando;
        propia = u.doctrina || {};
      }
      const base = delBando(bando) || {};
      for (const [campo, opciones] of CAMPOS) {
        const s = $(`doc-${campo}`);
        while (s.firstChild) s.removeChild(s.firstChild);
        if (propia) {
          const heredado = base[campo] !== undefined ? ` (${etiqueta(campo, base[campo])})` : "";
          s.appendChild(Object.assign(document.createElement("option"), { value: "", textContent: `Del bando${heredado}` }));
        }
        for (const [v, t] of opciones) s.appendChild(Object.assign(document.createElement("option"), { value: String(v), textContent: t }));
        const valor = propia ? propia[campo] : base[campo];
        s.value = valor === undefined || valor === null ? "" : String(valor);
      }
      $("doc-texto").textContent = !propia && datos.doctrina && datos.doctrina[bando] ? datos.doctrina[bando].texto
        : propia ? "Lo que deje «Del bando» lo toma de la doctrina de su bando." : "";
      sucio = false;
    }

    async function aplicar() {
      const [tipo, id] = $("doc-ambito").value.split(":");
      const cuerpo = {};
      for (const [campo] of CAMPOS) {
        const v = leer(campo, $(`doc-${campo}`).value);
        if (tipo === "unidad" || v !== null) cuerpo[campo] = v;
      }
      const ruta = tipo === "unidad" ? ctx.rutaEsc(`/unidades/${id}/doctrina`) : ctx.rutaEsc(`/doctrina/${id}`);
      try {
        await ctx.api("PUT", ruta, cuerpo);
        sucio = false;
        ctx.toast(tipo === "unidad" ? "Doctrina de la unidad aplicada" : "Doctrina del bando aplicada", true);
      } catch (_) { /* toast ya mostrado */ }
    }

    function conectar() {
      $("doc-ambito").addEventListener("change", () => { sucio = false; cargarValores(); });
      for (const [campo] of CAMPOS) $(`doc-${campo}`).addEventListener("change", () => { sucio = true; });
      $("doc-aplicar").addEventListener("click", aplicar);
    }

    function render(data) {
      datos = data;
      pintar();
    }

    return { conectar, render, refrescar: () => datos && pintar() };
  }

  const api = { crear, etiqueta, leer, CAMPOS };
  if (typeof module !== "undefined") module.exports = api;
  raiz.Doctrina = api;
})(typeof window !== "undefined" ? window : globalThis);
