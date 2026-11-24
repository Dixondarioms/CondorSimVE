/* Modo "Centro de operaciones" (videowall): los paneles colapsan por completo y el mapa ocupa el 100 % del
 * viewport, con un HUD grande (turno, hora, reloj, estado de los bandos y ultimas alertas). Se activa con el
 * boton del instructor, la tecla V o el parametro de URL ?modo=videowall (opcional: &escenario=ID&vista=azul).
 *
 * Es tambien el lector de los parametros con que la PC del director abre una ventana por reparticion:
 *   /?escenario=ID&vista=azul|rojo&puesto=comandante|jem|a1|a2|a3|a3da|a4|ce[&emitir=1][&lat=&lon=&zoom=]
 * (sin &vista se abre la vista completa del instructor). */
(function (raiz) {
  "use strict";
  const { etiquetaClima } = Logica;

  function parametrosDeUrl() {
    const p = new URLSearchParams(location.search);
    const vista = p.get("vista");
    const puesto = p.get("puesto");
    return {
      videowall: p.get("modo") === "videowall" || location.hash === "#videowall",
      escenario: p.get("escenario") ? parseInt(p.get("escenario"), 10) || null : null,
      vista: ["azul", "rojo", "completa"].includes(vista) ? vista : null,
      // reparticion cuya pantalla se abre (solo tiene sentido junto a &vista=azul|rojo)
      puesto: Logica.PUESTOS.some((q) => q.id === puesto) ? puesto : null,
      // esa ventana ademas emite ordenes como la reparticion (hace falta que el bando este a cargo del instructor)
      emitir: p.get("emitir") === "1",
      // ?lat=&lon=[&zoom=]: encuadre inicial del mapa (enlace directo a un lugar, p. ej. una base)
      lugar: p.get("lat") && p.get("lon") && Number.isFinite(+p.get("lat")) && Number.isFinite(+p.get("lon"))
        ? { lat: +p.get("lat"), lon: +p.get("lon"), zoom: Math.min(17, Math.max(2, parseInt(p.get("zoom"), 10) || 12)) } : null,
    };
  }

  /** ctx: { map(), alCambiar(activo) } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    let activo = false;
    let temporizadorSalida = null;
    let ultimo = null; // ultimo estado recibido: el HUD se pinta al activar sin esperar al siguiente

    function redimensionar() {
      const m = ctx.map();
      if (m) m.invalidateSize({ animate: false });
    }

    async function alternar(encender, { pantallaCompleta = true } = {}) {
      if (encender === activo) return;
      activo = encender;
      document.body.classList.toggle("videowall", activo);
      if (activo && ultimo) actualizarHud(ultimo.data, ultimo.alertas);
      if (activo && pantallaCompleta && document.documentElement.requestFullscreen) {
        try { await document.documentElement.requestFullscreen(); } catch (_) { /* el navegador lo puede negar; el modo sigue */ }
      } else if (!activo && document.fullscreenElement) {
        try { await document.exitFullscreen(); } catch (_) { /* ya salio */ }
      }
      ctx.alCambiar(activo);
      // el mapa se ajusta mientras se anima el colapso de los paneles y al terminar
      [50, 200, 420].forEach((ms) => setTimeout(redimensionar, ms));
      if (activo) mostrarSalida();
    }

    function mostrarSalida() {
      document.body.classList.add("mostrar-salida");
      clearTimeout(temporizadorSalida);
      temporizadorSalida = setTimeout(() => document.body.classList.remove("mostrar-salida"), 3500);
    }

    /** Actualiza el HUD con el ultimo estado y las alertas mas recientes. */
    function actualizarHud(data, alertas) {
      if (data) ultimo = { data, alertas };
      if (!activo || !data) return;
      const esc = data.escenario;
      $("hud-escenario").textContent = esc.nombre;
      $("hud-turno").textContent = String(esc.turno_actual);
      $("hud-clima").textContent = etiquetaClima(esc.clima).toUpperCase();
      if (data.marcador) {
        $("hud-marcador-azul").textContent = String(data.marcador.azul.total);
        $("hud-marcador-rojo").textContent = String(data.marcador.rojo.total);
      }
      const eAzul = Logica.etiquetaBandoNacion("azul", esc, ctx.naciones()).toUpperCase();
      const eRojo = Logica.etiquetaBandoNacion("rojo", esc, ctx.naciones()).toUpperCase();
      $("hud-azul").textContent = eAzul;
      $("hud-rojo").textContent = eRojo;
      const ul = $("hud-alertas");
      while (ul.firstChild) ul.removeChild(ul.firstChild);
      for (const a of alertas.slice(0, 3)) {
        const li = document.createElement("li");
        li.className = a.nivel;
        li.textContent = a.texto;
        ul.appendChild(li);
      }
    }

    /** Reloj del tiempo real: hora simulada en curso, marcha o pausa y velocidad (lo llama la app cada 250 ms). */
    function actualizarReloj(data, hora, estado, velocidad) {
      if (!activo || !data) return;
      $("hud-hora").textContent = hora;
      const r = $("hud-reloj");
      r.classList.remove("urgente");
      r.classList.toggle("inactivo", estado !== "activo");
      r.textContent = estado === "finalizado" ? "FINALIZADO" : estado === "activo" ? `▶ ${velocidad}×` : "⏸ DETENIDO";
    }

    function conectar() {
      $("btn-videowall").addEventListener("click", () => alternar(!activo));
      $("btn-vw-salir").addEventListener("click", () => alternar(false));
      document.addEventListener("mousemove", () => { if (activo) mostrarSalida(); });
      document.addEventListener("keydown", (e) => {
        const escribiendo = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || ""));
        if (e.key === "Escape" && activo) alternar(false);
        else if ((e.key === "v" || e.key === "V") && !escribiendo && !e.ctrlKey && !e.metaKey && !e.altKey && !$("btn-videowall").hidden) alternar(!activo);
      });
      // si el usuario sale de pantalla completa con Esc del navegador, el modo se mantiene (solo cambia el tamano)
      document.addEventListener("fullscreenchange", () => setTimeout(redimensionar, 100));
      window.addEventListener("resize", redimensionar);
      if (typeof ResizeObserver !== "undefined") new ResizeObserver(redimensionar).observe($("zona-mapa"));
    }

    return { conectar, alternar, actualizarHud, actualizarReloj, activo: () => activo };
  }

  raiz.Videowall = { crear, parametrosDeUrl };
})(window);
