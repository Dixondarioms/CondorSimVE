/* Ayuda del Cóndor: botón "Ayuda" (o tecla F1) que abre el panel con un buscador ("escriba su pregunta"), los temas por
 * sección (ayuda_temas.js) y el recorrido guiado paso a paso por la pantalla (recorrido.js). Funciona sin internet. */
(function (raiz) {
  "use strict";

  /** ctx: { esInstructor(), recorrido() } */
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const T = raiz.AyudaTemas;
    let actual = null;

    const director = () => !!(ctx.esInstructor && ctx.esInstructor());
    const visibles = () => T.TEMAS.filter((t) => !t.director || director());

    function botonTema(t) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "ayuda-tema" + (actual === t.id ? " activo" : "");
      b.textContent = t.titulo;
      b.addEventListener("click", () => mostrar(t.id));
      return b;
    }

    function indice() {
      const nav = $("ayuda-indice");
      nav.replaceChildren();
      const q = $("ayuda-buscar").value.trim();
      if (q) {
        const res = T.buscar(q, { director: director() });
        nav.appendChild(Object.assign(document.createElement("h4"), { textContent: res.length ? "Lo que encontré" : "Sin resultados" }));
        if (!res.length) {
          nav.appendChild(Object.assign(document.createElement("p"), {
            className: "ayuda",
            textContent: "Pruebe con otras palabras (por ejemplo: despegar, radar, combustible, reloj) o recorra los temas.",
          }));
        }
        res.forEach((t) => nav.appendChild(botonTema(t)));
        return res;
      }
      for (const s of T.SECCIONES) {
        const temas = visibles().filter((t) => t.seccion === s);
        if (!temas.length) continue;
        nav.appendChild(Object.assign(document.createElement("h4"), { textContent: s }));
        temas.forEach((t) => nav.appendChild(botonTema(t)));
      }
      return [];
    }

    function bienvenida() {
      const a = $("ayuda-articulo");
      a.innerHTML = `<h3>¿En qué le ayudo?</h3>
        <p>Escriba arriba su pregunta con sus palabras (por ejemplo: <i>¿cómo despego un caza?</i>, <i>no veo al enemigo</i>,
        <i>qué hace el A-4</i>) o elija un tema de la lista.</p>
        <p>Si es la primera vez, haga el <b>recorrido guiado</b>: le muestra cada parte de la pantalla paso a paso. Para practicar
        sin apuro, pida al director el ejercicio <b>«Tutorial del Cóndor»</b>.</p>`;
    }

    function mostrar(id) {
      const t = T.TEMAS.find((x) => x.id === id);
      if (!t) return;
      actual = id;
      const a = $("ayuda-articulo");
      a.innerHTML = `<p class="ayuda-seccion">${t.seccion}</p><h3>${t.titulo}</h3>${t.texto}`;  // contenido propio y fijo
      const rel = T.buscar(`${t.titulo} ${t.claves}`, { director: director(), max: 4 }).filter((x) => x.id !== id).slice(0, 3);
      if (rel.length) {
        const p = Object.assign(document.createElement("p"), { className: "ayuda-relacionados" });
        p.append("Vea también: ");
        rel.forEach((x, i) => {
          const b = Object.assign(document.createElement("button"), { type: "button", className: "enlace", textContent: x.titulo });
          b.addEventListener("click", () => mostrar(x.id));
          p.append(b, i < rel.length - 1 ? " · " : "");
        });
        a.appendChild(p);
      }
      a.scrollTop = 0;
      document.querySelectorAll("#ayuda-indice .ayuda-tema").forEach((b) => b.classList.toggle("activo", b.textContent === t.titulo));
    }

    function abrir(id) {
      const d = $("dlg-ayuda");
      if (!d.open) d.showModal();
      indice();
      if (id) mostrar(id); else if (!actual) bienvenida();
      $("ayuda-buscar").focus();
    }

    function conectar() {
      $("btn-ayuda").addEventListener("click", () => abrir());
      $("ayuda-cerrar").addEventListener("click", () => $("dlg-ayuda").close());
      $("ayuda-recorrido").addEventListener("click", () => { $("dlg-ayuda").close(); ctx.recorrido(); });
      let espera = null;
      $("ayuda-buscar").addEventListener("input", () => {
        clearTimeout(espera);
        espera = setTimeout(() => { const res = indice(); if (res.length) mostrar(res[0].id); }, 180);
      });
      $("ayuda-buscar").addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); const res = indice(); if (res.length) mostrar(res[0].id); }
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "F1") { e.preventDefault(); abrir(); }
      });
    }

    return { conectar, abrir, mostrar };
  }

  const api = { crear };
  if (typeof module !== "undefined") module.exports = api;
  raiz.Ayuda = api;
})(typeof window !== "undefined" ? window : globalThis);
