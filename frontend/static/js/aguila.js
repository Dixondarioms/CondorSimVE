/* Aguila del SIETE en la pantalla de acceso. En reposo esta posada con las alas recogidas (imagen propia); al
 * aprobarse el ingreso se funde en la desplegada, abre las alas, las bate con un aleteo pausado y levanta el vuelo
 * hacia la pantalla. La desplegada son tres piezas de la misma imagen (ala izquierda, cuerpo y ala derecha,
 * recortadas con clip-path en style.css) para que las alas giren en los hombros. Con "reducir movimiento" del
 * sistema no hay animacion: se entra directo. */
(function (raiz) {
  "use strict";

  const VUELO_MS = 1000;      // todo: de posada hasta desaparecer sobre la pantalla
  const DESPLIEGUE_MS = 250;  // abre las alas
  const FUNDIDO_MS = 180;     // de la imagen posada a la desplegada
  const ALETEO_MS = 600;      // un aleteo (amplio y sin prisa dentro del segundo)
  // alas recogidas (las mismas de .aguila.plegada en style.css); signo +1 ala izquierda, -1 la derecha
  const plegada = (s) => `rotate(${s * -84}deg) scaleX(.3) scaleY(.85)`;
  const abierta = "rotate(0deg) scaleX(1) scaleY(1)";

  const sinMovimiento = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);

  /** Abre el ala: de recogida a desplegada, pasando por arriba (el primer batido). */
  function cuadrosDespliegue(s) {
    return [
      { transform: plegada(s) },
      { transform: `rotate(${s * 30}deg) scaleX(.95) scaleY(.95)`, offset: 0.65 },
      { transform: abierta },
    ];
  }

  /** Un aleteo: sube despacio y baja con fuerza (el giro positivo sube la punta del ala izquierda). */
  function cuadrosAleteo(s) {
    return [
      { transform: abierta, easing: "ease-in-out" },
      { transform: `rotate(${s * 30}deg) scaleX(.96) scaleY(.92)`, offset: 0.5, easing: "ease-in" },
      { transform: `rotate(${s * -24}deg) scaleX(.98) scaleY(.8)`, offset: 0.82, easing: "ease-out" },
      { transform: abierta },
    ];
  }

  function batirAlas(figura) {
    const vuelo = VUELO_MS - DESPLIEGUE_MS;
    // de la imagen posada a la desplegada: el cuerpo coincide y las alas salen de su posicion recogida
    const fundido = (sel, de, a, ms) => {
      const el = figura.querySelector(sel);
      if (el) el.animate([{ opacity: de }, { opacity: a }], { duration: ms, easing: "ease-out", fill: "forwards" });
    };
    fundido(".posada", 1, 0, FUNDIDO_MS);
    fundido(".cuerpo", 0, 1, FUNDIDO_MS / 2);
    fundido(".ala-izq", 0, 1, FUNDIDO_MS);
    fundido(".ala-der", 0, 1, FUNDIDO_MS);
    [[".ala-izq", 1], [".ala-der", -1]].forEach(([sel, s]) => {
      const ala = figura.querySelector(sel);
      if (!ala) return;
      ala.animate(cuadrosDespliegue(s), { duration: DESPLIEGUE_MS, easing: "ease-out", fill: "forwards" });
      ala.animate(cuadrosAleteo(s), { duration: ALETEO_MS, delay: DESPLIEGUE_MS, iterations: vuelo / ALETEO_MS });
    });
  }

  /** Trayectoria: abre las alas posada, toma impulso, levanta el vuelo y viene hacia la pantalla. */
  function cuadrosVuelo(dx, dy) {
    const d = DESPLIEGUE_MS / VUELO_MS;
    return [
      { transform: "translate(0px, 0px) scale(1)", opacity: 1, offset: 0 },
      { transform: "translate(0px, 0px) scale(1)", opacity: 1, offset: d },                     // abre las alas
      { transform: "translate(0px, 10px) scale(.97)", opacity: 1, offset: d + 0.08 },           // toma impulso
      { transform: "translate(0px, -70px) scale(1.05)", opacity: 1, offset: 0.52 },             // levanta el vuelo
      { transform: `translate(${dx}px, ${dy - 40}px) scale(2.4)`, opacity: 1, offset: 0.8 },    // viene hacia la pantalla
      { transform: `translate(${dx}px, ${dy}px) scale(9)`, opacity: 0, offset: 1 },             // pasa y desaparece
    ];
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
    const r = figura.getBoundingClientRect();
    const vuelo = figura.cloneNode(true);
    vuelo.removeAttribute("id");
    vuelo.classList.remove("en-reposo");
    vuelo.classList.add("en-vuelo");
    Object.assign(vuelo.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
    document.body.appendChild(vuelo);
    figura.style.visibility = "hidden";
    const dx = raiz.innerWidth / 2 - (r.left + r.width / 2);
    const dy = raiz.innerHeight / 2 - (r.top + r.height / 2);
    batirAlas(vuelo);
    const anim = vuelo.animate(cuadrosVuelo(dx, dy), { duration: VUELO_MS, easing: "ease-in-out", fill: "forwards" });
    const fin = () => { vuelo.remove(); figura.style.visibility = ""; listo(); };
    return anim.finished.then(fin, fin);
  }

  const Aguila = { despegar, cuadrosVuelo, cuadrosAleteo, cuadrosDespliegue, plegada, VUELO_MS, DESPLIEGUE_MS, ALETEO_MS };
  if (typeof module !== "undefined" && module.exports) module.exports = Aguila;
  raiz.Aguila = Aguila;
})(typeof window !== "undefined" ? window : globalThis);
