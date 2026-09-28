/* Panel de comunicaciones (chat tactico) sobre el WebSocket existente. El servidor aplica la latencia y la
 * perdida de mensajes; el instructor ve ademas que le paso a cada bando. */
(function (raiz) {
  "use strict";
  const { etiquetaCanal, canalesDe, resumenEntrega, fechaUtc } = Logica;
  const MAX_MENSAJES = 120;

  /** ctx: { enviar(obj) -> bool, usuario(), toast } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    let mensajes = [];
    let sinLeer = 0;

    function hora(iso) {
      const t = fechaUtc(iso);
      return t === null ? "" : new Date(t).toLocaleTimeString("es", { hour12: false });
    }

    function render() {
      const ul = $("chat-lista");
      const alFinal = ul.scrollTop + ul.clientHeight >= ul.scrollHeight - 12;
      while (ul.firstChild) ul.removeChild(ul.firstChild);
      const yo = ctx.usuario();
      if (!mensajes.length) {
        const li = document.createElement("li");
        li.className = "sistema";
        li.textContent = "Sin mensajes. Las comunicaciones pueden sufrir demoras o interferencia.";
        ul.appendChild(li);
      }
      for (const m of mensajes) {
        const li = document.createElement("li");
        li.className = (m.canal === "azul" || m.canal === "rojo" || m.canal === "mando" ? m.canal : "") + (m.remitente === yo.username ? " mio" : "");
        const meta = document.createElement("span");
        meta.className = "meta";
        meta.append(`${hora(m.creado_en)} · ${m.remitente}${m.rol === "instructor" ? " (mando)" : ""} → ${etiquetaCanal(m.canal)}`);
        for (const e of resumenEntrega(m.entrega)) {
          const s = document.createElement("span");
          s.className = "entrega" + (e.perdido ? " perdido" : "");
          s.textContent = ` [${e.texto}]`;
          meta.appendChild(s);
        }
        const texto = document.createElement("span");
        texto.textContent = m.texto; // textContent: el contenido de un mensaje nunca se interpreta como HTML
        li.append(meta, texto);
        ul.appendChild(li);
      }
      if (alFinal) ul.scrollTop = ul.scrollHeight;
      const n = $("chat-nuevos");
      n.hidden = sinLeer === 0;
      n.textContent = String(sinLeer);
    }

    function historial(lista) {
      mensajes = lista.map((x) => x.mensaje);
      sinLeer = 0;
      render();
    }

    function recibir(m) {
      mensajes.push(m.mensaje);
      mensajes = mensajes.slice(-MAX_MENSAJES);
      if (m.mensaje.remitente !== ctx.usuario().username) sinLeer += 1;
      render();
    }

    function configurarRol() {
      const rol = ctx.usuario().rol;
      const canales = canalesDe(rol);
      $("tarjeta-chat").classList.toggle("oculta", canales.length === 0);
      const sel = $("chat-canal");
      while (sel.firstChild) sel.removeChild(sel.firstChild);
      for (const [valor, texto] of canales) {
        const o = document.createElement("option");
        o.value = valor;
        o.textContent = texto;
        sel.appendChild(o);
      }
    }

    /** Solo el instructor conoce la configuracion del enlace (el servidor no se la envia a los demas). */
    function actualizarEnlace(esc) {
      const p = $("chat-enlace");
      if (esc.com_perdida_pct === undefined) { p.textContent = ""; return; }
      const partes = [`latencia ${esc.com_latencia_ms} ms ±${esc.com_jitter_ms}`, `pérdida ${esc.com_perdida_pct} %`];
      p.textContent = esc.com_latencia_ms || esc.com_jitter_ms || esc.com_perdida_pct ? `Enlace degradado: ${partes.join(", ")}.` : "Enlace normal (sin interferencia).";
    }

    function reiniciar() {
      mensajes = [];
      sinLeer = 0;
      render();
    }

    function conectar() {
      $("chat-form").addEventListener("submit", (e) => {
        e.preventDefault();
        const texto = $("chat-texto").value.trim();
        if (!texto) return;
        if (!ctx.enviar({ tipo: "chat", canal: $("chat-canal").value, texto })) return ctx.toast("Sin conexión con el servidor: el mensaje no se envió.");
        $("chat-texto").value = "";
      });
      $("tarjeta-chat").addEventListener("mouseenter", () => { sinLeer = 0; render(); });
      $("chat-texto").addEventListener("focus", () => { sinLeer = 0; render(); });
      render();
    }

    return { conectar, historial, recibir, configurarRol, actualizarEnlace, reiniciar, error: (t) => ctx.toast(t) };
  }

  raiz.Chat = { crear };
})(window);
