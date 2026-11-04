/* Comodidades de la pantalla del Cóndor: tarjetas del panel derecho y grupos de capas que se pliegan (y se
 * recuerdan), atajos de teclado y filtros de las alertas. Las funciones puras (grupoAlerta, pasaFiltro,
 * accionDeTecla) se prueban en tests/interfaz.test.js. */
(function (raiz) {
  "use strict";

  // causa de la alerta (engine/tiempo_real.py, ctx.alerta) -> filtro de la tarjeta Alertas
  const GRUPO_CAUSA = {
    ataque: "ataques", perdida: "ataques", colateral: "ataques",
    contacto: "contactos", intercepcion: "contactos", zona: "contactos",
    evento: "director",
  };
  const FILTROS = [["todas", "Todas"], ["ataques", "Ataques"], ["contactos", "Contactos"], ["director", "Director"], ["otras", "Otras"]];

  const grupoAlerta = (a) => GRUPO_CAUSA[(a && a.causa) || ""] || "otras";
  const pasaFiltro = (a, filtro) => !filtro || filtro === "todas" || grupoAlerta(a) === filtro;

  // tecla -> accion. Las de orden y centrar son para todos; las del reloj, solo para el director
  const TECLAS = { m: "mover", a: "atacar", i: "interceptar", p: "patrullar", c: "centrar" };
  const TECLAS_DIRECTOR = { " ": "marcha", "1": "vel-1", "2": "vel-10", "3": "vel-60" };
  const ATAJOS = [
    ["M", "Orden Mover"], ["A", "Orden Atacar"], ["I", "Orden Interceptar"], ["P", "Orden Patrullar"],
    ["C", "Centrar el mapa"], ["Esc", "Cancelar el dibujo o la ventana"], ["V", "Videowall"], ["F1", "Ayuda"],
    ["+ / −", "Acercar o alejar"], ["Espacio", "Poner en marcha o detener el reloj (director)"],
    ["1 / 2 / 3", "Velocidad 1×, 10× o 60× (director)"],
  ];

  /** La accion de una tecla (o null): no cuenta si escribe en un campo, con Ctrl/Alt o con una ventana abierta. */
  function accionDeTecla(e, director, ventanaAbierta) {
    if (!e || e.ctrlKey || e.metaKey || e.altKey || ventanaAbierta) return null;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || "") || (e.target && e.target.isContentEditable)) return null;
    const k = (e.key || "").toLowerCase();
    if (TECLAS[k]) return TECLAS[k];
    if (director && TECLAS_DIRECTOR[e.key]) return TECLAS_DIRECTOR[e.key];
    return null;
  }

  function guardado(clave) {
    try { return localStorage.getItem(clave); } catch (_) { return null; }
  }
  function guardar(clave, valor) {
    try { localStorage.setItem(clave, valor); } catch (_) { /* sin almacenamiento */ }
  }

  /** ctx: { esDirector(), alCambiarFiltro() } */
  function crear(ctx) {
    let filtro = guardado("condor.filtroAlertas") || "todas";

    function visible(el) {
      return !!el && !el.hidden && el.offsetParent !== null;
    }

    function clic(sel) {
      const el = document.querySelector(sel);
      if (visible(el) && !el.disabled) { el.click(); return true; }
      return false;
    }

    function hacer(accion) {
      if (["mover", "atacar", "interceptar", "patrullar"].includes(accion)) return clic(`#sec-orden .modos [data-modo="${accion}"]`);
      if (accion === "centrar") return clic("#btn-centrar");
      if (accion === "marcha") return clic("#btn-marcha");
      if (accion.startsWith("vel-")) return clic(`.velocidades [data-vel="${accion.slice(4)}"]`);
      return false;
    }

    function plegarTarjetas() {
      document.querySelectorAll("#panel-der .tarjeta").forEach((t) => {
        const h = t.querySelector(":scope > h2");
        if (!h) return;
        const clave = `condor.plegada.${t.id || h.textContent.trim().split(/\s+/)[0].toLowerCase()}`;
        h.classList.add("plegable");
        h.tabIndex = 0;
        h.title = "Clic: plegar o desplegar";
        const fijar = (p) => { t.classList.toggle("plegada", p); h.setAttribute("aria-expanded", p ? "false" : "true"); };
        fijar(guardado(clave) === "1");
        const alternar = (e) => {
          if (e.target.closest("button, input, select, a")) return;
          const p = !t.classList.contains("plegada");
          fijar(p);
          guardar(clave, p ? "1" : "0");
        };
        h.addEventListener("click", alternar);
        h.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); alternar(e); } });
      });
    }

    function gruposDeCapas() {
      document.querySelectorAll(".capas-grupo").forEach((d) => {
        const clave = `condor.capas.${d.dataset.grupo}`;
        const g = guardado(clave);
        if (g !== null) d.open = g === "1";
        d.addEventListener("toggle", () => guardar(clave, d.open ? "1" : "0"));
      });
    }

    function filtrosDeAlertas() {
      const caja = document.getElementById("filtro-alertas");
      if (!caja) return;
      caja.replaceChildren(...FILTROS.map(([id, nombre]) => {
        const b = Object.assign(document.createElement("button"), { type: "button", className: "mini secundario", textContent: nombre });
        b.dataset.filtro = id;
        b.addEventListener("click", (e) => {
          e.stopPropagation();
          filtro = id;
          guardar("condor.filtroAlertas", id);
          pintarFiltro();
          ctx.alCambiarFiltro();
        });
        return b;
      }));
      pintarFiltro();
    }

    function pintarFiltro() {
      document.querySelectorAll("#filtro-alertas [data-filtro]").forEach((b) => {
        const activo = b.dataset.filtro === filtro;
        b.classList.toggle("primario", activo);
        b.classList.toggle("secundario", !activo);
        b.setAttribute("aria-pressed", activo ? "true" : "false");
      });
    }

    function conectar() {
      plegarTarjetas();
      gruposDeCapas();
      filtrosDeAlertas();
      document.addEventListener("keydown", (e) => {
        const ventana = !!document.querySelector("dialog[open], .recorrido-tarjeta");
        const accion = accionDeTecla(e, ctx.esDirector(), ventana);
        if (accion && hacer(accion)) e.preventDefault();
      });
    }

    return { conectar, filtro: () => filtro, pasa: (a) => pasaFiltro(a, filtro) };
  }

  const api = { crear, grupoAlerta, pasaFiltro, accionDeTecla, ATAJOS, FILTROS };
  if (typeof module !== "undefined") module.exports = api;
  raiz.Interfaz = api;
})(typeof window !== "undefined" ? window : globalThis);
