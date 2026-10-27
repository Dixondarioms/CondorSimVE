/* Figura de la pantalla de acceso (en esta version, el condor: condor_posado.png y condor_vuelo.webm, de
 * tools/manual/condor_video.py; el aguila del SIETE por turnos usa siete_aguila_posada.png y aguila_vuelo.webm).
 * En reposo esta posada con las alas recogidas (el primer cuadro del video); al aprobarse el ingreso se reproduce el
 * video (2,8 s, con transparencia: abre las alas y despega) mientras la figura levanta el vuelo y viene hacia la
 * pantalla hasta desaparecer. Recien entonces se muestra el simulador.
 * Si el video no se puede reproducir, vuela la imagen posada; con "reducir movimiento" del sistema se entra directo. */
(function (raiz) {
  "use strict";

  const VUELO_MS = 2800;       // lo que dura el video y el vuelo
  const ESPERA_VIDEO_MS = 400; // reproducir(): si el video no arranca en este tiempo, se da por perdido

  const sinMovimiento = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);

  /** Trayectoria de la figura mientras corre el video: abre las alas en su lugar, sube y viene hacia la pantalla. */
  function cuadrosVuelo(dx, dy) {
    return [
      { transform: "translate(0px, 0px) scale(1)", opacity: 1, offset: 0 },
      { transform: "translate(0px, 0px) scale(1)", opacity: 1, offset: 0.4, easing: "ease-in-out" },        // abre las alas
      { transform: "translate(0px, -40px) scale(1.08)", opacity: 1, offset: 0.6, easing: "ease-in" },       // levanta el vuelo
      { transform: `translate(${dx}px, ${dy - 30}px) scale(2.2)`, opacity: 1, offset: 0.85, easing: "ease-in" }, // viene hacia la pantalla
      { transform: `translate(${dx}px, ${dy}px) scale(7)`, opacity: 0, offset: 1 },                        // pasa y desaparece
    ];
  }

  /** Reproduce el video desde el principio; se cumple con true si arranco, false si no (en ESPERA_VIDEO_MS). */
  function reproducir(video) {
    if (!video || typeof video.play !== "function") return Promise.resolve(false);
    try { video.currentTime = 0; } catch (_) { /* sin datos todavia */ }
    const intento = Promise.resolve(video.play()).then(() => true, () => false);
    const espera = new Promise((ok) => setTimeout(() => ok(false), ESPERA_VIDEO_MS));
    return Promise.race([intento, espera]);
  }

  /**
   * Despega la figura `figura` (el aguila de la pantalla de acceso). `alTerminar` se llama una vez, cuando el aguila
   * ya desaparecio (para mostrar el simulador). Devuelve una promesa que se cumple al terminar el vuelo.
   */
  function despegar(figura, alTerminar) {
    let avisado = false;
    const listo = () => { if (!avisado && alTerminar) { avisado = true; alTerminar(); } };
    if (!figura || sinMovimiento() || typeof figura.animate !== "function") {
      listo();
      return Promise.resolve();
    }
    const video = figura.querySelector("video");
    const r = figura.getBoundingClientRect();
    const dx = raiz.innerWidth / 2 - (r.left + r.width / 2);
    const dy = raiz.innerHeight / 2 - (r.top + r.height / 2);
    // la figura sale de la tarjeta (que se desvanece) y vuela sobre la pantalla; al terminar vuelve a su lugar
    const lugar = document.createComment("aguila");
    figura.parentNode.insertBefore(lugar, figura);
    document.body.appendChild(figura);
    figura.classList.remove("en-reposo");
    figura.classList.add("en-vuelo");
    Object.assign(figura.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
    const fin = () => {
      if (video) { video.pause(); try { video.currentTime = 0; } catch (_) { /* nada */ } }
      figura.getAnimations().forEach((a) => a.cancel());
      figura.classList.remove("en-vuelo", "volando");
      figura.classList.add("en-reposo");
      figura.removeAttribute("style");
      lugar.replaceWith(figura);
      listo();
    };
    // el video reemplaza a la imagen en cuanto muestra su primer cuadro (que es igual); el vuelo arranca ya
    if (video) video.addEventListener("playing", () => figura.classList.add("volando"), { once: true });
    reproducir(video);
    return figura.animate(cuadrosVuelo(dx, dy), { duration: VUELO_MS, fill: "forwards" }).finished.then(fin, fin);
  }

  /** Carga el video entero en memoria (blob): el servidor no atiende pedidos por partes, y sin eso el navegador no
   * deja volver al principio para repetirlo en el siguiente ingreso. */
  function preparar(figura) {
    const video = figura && figura.querySelector("video[data-src]");
    if (!video || typeof fetch !== "function" || !raiz.URL || !URL.createObjectURL) return Promise.resolve(false);
    return fetch(video.dataset.src)
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then((b) => { video.src = URL.createObjectURL(b); video.removeAttribute("data-src"); return true; })
      .catch(() => false);
  }
  if (typeof document !== "undefined") {
    const iniciar = () => preparar(document.getElementById("aguila-login"));
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
    else iniciar();
  }

  const Aguila = { despegar, cuadrosVuelo, reproducir, preparar, VUELO_MS };
  if (typeof module !== "undefined" && module.exports) module.exports = Aguila;
  raiz.Aguila = Aguila;
})(typeof window !== "undefined" ? window : globalThis);
