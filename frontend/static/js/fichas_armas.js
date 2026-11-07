/* Fichas de las armas (catalogo.fichas_armas, backend/app/engine/fichas_armas.py): la tira de fotos chicas del panel
 * de abajo y de la ventana de despegue, y la ficha grande con la foto y las caracteristicas al hacer clic.
 * Cualquier boton con data-ficha-arma="<id>" abre la ficha (un solo escuchador para toda la pagina). */
(function () {
  "use strict";
  const escapar = (s) => String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let catalogo = () => null;

  /** HTML de la tira: una foto chica por arma, con su nombre; sin foto, solo el nombre. */
  function tira(grupo) {
    if (!grupo || !grupo.fichas || !grupo.fichas.length) return "";
    const botones = grupo.fichas.map((f) => `<button type="button" class="arma-mini" data-ficha-arma="${escapar(f.id)}" `
      + `title="${escapar(`${f.nombre} · ${f.tipo}. Clic: ficha completa`)}">`
      + (f.foto ? `<img src="${escapar(f.foto)}" loading="lazy" alt="">` : '<span class="arma-sinfoto" aria-hidden="true">sin foto</span>')
      + `<span class="arma-nombre">${escapar(f.nombre)}</span></button>`).join("");
    return `<div class="armas-fotos"><span class="pu-etq">${escapar(grupo.titulo)}</span><div class="armas-tira">${botones}</div></div>`;
  }

  /** Abre la ficha grande de un arma. */
  function abrir(id) {
    const cat = catalogo();
    const f = cat && cat.fichas_armas && cat.fichas_armas.fichas[id];
    const dlg = document.getElementById("dlg-arma");
    if (!f || !dlg) return;
    document.getElementById("arma-titulo").textContent = f.nombre;
    const filas = Logica.filasFichaArma(f).map(([k, v]) => `<div><dt>${escapar(k)}</dt><dd>${escapar(v)}</dd></div>`).join("");
    const c = f.credito;
    const foto = f.foto
      ? `<figure class="arma-foto"><img src="${escapar(f.foto)}" alt="${escapar(f.nombre)}"><figcaption>`
        + `${c && c.obra ? `Referencia: ${escapar(c.obra)}. ` : ""}Foto: ${escapar(c ? c.autor : "")}, ${escapar(c ? c.licencia : "")}`
        + (c && c.pagina ? ` · <a href="${escapar(c.pagina)}" target="_blank" rel="noopener">Wikimedia Commons</a>` : "")
        + "</figcaption></figure>"
      : '<p class="nota">No hay una foto libre de esta arma en Wikimedia Commons.</p>';
    document.getElementById("arma-cuerpo").innerHTML = foto + `<dl class="arma-datos">${filas}</dl>`
      + `<p class="arma-desc">${escapar(f.descripcion)}</p>`
      + '<p class="ayuda">Datos públicos de referencia. En el simulador, el alcance y la probabilidad de impacto de cada arma son los de la tabla del panel.</p>';
    if (!dlg.open) dlg.showModal();
  }

  function iniciar(obtenerCatalogo) {
    catalogo = obtenerCatalogo;
    document.addEventListener("click", (ev) => {
      const b = ev.target.closest && ev.target.closest("[data-ficha-arma]");
      if (!b) return;
      ev.preventDefault();
      abrir(b.dataset.fichaArma);
    });
    const cerrar = document.getElementById("arma-cerrar");
    if (cerrar) cerrar.addEventListener("click", () => document.getElementById("dlg-arma").close());
  }

  window.FichasArmas = { tira, abrir, iniciar };
})();
