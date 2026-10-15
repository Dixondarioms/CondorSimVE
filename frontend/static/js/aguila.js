/* Aguila del SIETE en la pantalla de acceso. En reposo esta posada con las alas recogidas (imagen propia); al
 * aprobarse el ingreso se funde en la desplegada, abre las alas, aletea y levanta el vuelo hacia la pantalla.
 *
 * La desplegada se arma con piezas de la misma imagen (recortadas con clip-path en style.css): el cuerpo y, en cada
 * ala, el brazo (gira en el hombro) y la mano con las plumas largas (gira en la muneca, dentro del brazo). El aleteo
 * es una onda continua: el brazo sube y baja con un coseno, la mano lo sigue con un retraso (el ala se curva como en
 * un vuelo real), el ala se acorta un poco al bajar (viene hacia adelante) y el cuerpo sube con cada batida.
 * Con "reducir movimiento" del sistema no hay animacion: se entra directo. */
(function (raiz) {
  "use strict";

  const VUELO_MS = 1000;      // todo: de posada hasta desaparecer sobre la pantalla
  const DESPLIEGUE_MS = 260;  // abre las alas hasta arriba
  const FUNDIDO_MS = 180;     // de la imagen posada a la desplegada
  const ALETEO_MS = 520;      // un ciclo de aleteo (arriba -> abajo -> arriba)
  const MUESTRAS = 16;        // cuadros por ciclo (entre ellos se interpola linealmente: la curva queda suave)
  // brazo: angulo medio y amplitud (grados, positivo = punta arriba); mano: amplitud y retraso (fraccion de ciclo)
  const BRAZO_MEDIO = 6, BRAZO_AMPL = 30, MANO_AMPL = 18, MANO_RETRASO = 0.14, ACORTE = 0.08, BATIDA_PX = 6;
  // alas recogidas (las mismas de .aguila.plegada en style.css); signo +1 ala izquierda, -1 la derecha
  const plegada = (s) => `rotate(${s * -84}deg) scaleX(.3) scaleY(.85)`;

  const sinMovimiento = () => !!(raiz.matchMedia && raiz.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const r2 = (x) => Math.round(x * 100) / 100;

  /** Pose del brazo y de la mano en la fase p del ciclo (0 = arriba, 0,5 = abajo). */
  function pose(p) {
    const c = Math.cos(2 * Math.PI * p);
    return {
      brazo: BRAZO_MEDIO + BRAZO_AMPL * c,
      acorte: 1 - ACORTE * (1 - c) / 2,
      mano: MANO_AMPL * Math.cos(2 * Math.PI * (p - MANO_RETRASO)),
      batida: -BATIDA_PX * Math.sin(2 * Math.PI * p),  // el cuerpo sube mientras las alas bajan
    };
  }
  const brazo = (s, q) => `rotate(${r2(s * q.brazo)}deg) scaleX(${r2(q.acorte)})`;
  const mano = (s, q) => `rotate(${r2(s * q.mano)}deg)`;

  /** Un ciclo de aleteo muestreado: [{transform}...] del brazo o de la mano (el primero igual al ultimo). */
  function cicloAleteo(parte, s) {
    const f = parte === "mano" ? mano : brazo;
    return Array.from({ length: MUESTRAS + 1 }, (_, i) => ({ transform: f(s, pose(i / MUESTRAS)) }));
  }
  function cicloBatida() {
    return Array.from({ length: MUESTRAS + 1 }, (_, i) => ({ transform: `translateY(${r2(pose(i / MUESTRAS).batida)}px)` }));
  }

  /** Abre el ala desde recogida hasta la pose de arriba, donde empieza el aleteo (sin saltos). */
  function cuadrosDespliegue(parte, s) {
    const arriba = pose(0);
    if (parte === "mano") return [{ transform: "rotate(0deg)" }, { transform: `rotate(${s * -22}deg)`, offset: 0.45 }, { transform: mano(s, arriba) }];
    return [{ transform: plegada(s) }, { transform: brazo(s, arriba) }];
  }

  function animarAlas(figura) {
    const vueltas = (VUELO_MS - DESPLIEGUE_MS) / ALETEO_MS;
    const ciclo = { duration: ALETEO_MS, delay: DESPLIEGUE_MS, iterations: vueltas, easing: "linear" };
    const abrir = { duration: DESPLIEGUE_MS, easing: "cubic-bezier(.3,0,.25,1)", fill: "forwards" };
    const fundido = (sel, de, a, ms) => {
      const el = figura.querySelector(sel);
      if (el) el.animate([{ opacity: de }, { opacity: a }], { duration: ms, easing: "ease-out", fill: "forwards" });
    };
    // de la imagen posada a la desplegada: el cuerpo coincide y las alas salen de su posicion recogida
    fundido(".posada", 1, 0, FUNDIDO_MS);
    fundido(".cuerpo", 0, 1, FUNDIDO_MS / 2);
    fundido(".ala-izq", 0, 1, FUNDIDO_MS);
    fundido(".ala-der", 0, 1, FUNDIDO_MS);
    [[".ala-izq", 1], [".ala-der", -1]].forEach(([sel, s]) => {
      const ala = figura.querySelector(sel);
      if (!ala) return;
      ala.animate(cuadrosDespliegue("brazo", s), abrir);
      ala.animate(cicloAleteo("brazo", s), ciclo);
      const m = ala.querySelector(".mano");
      if (m) {
        m.animate(cuadrosDespliegue("mano", s), abrir);
        m.animate(cicloAleteo("mano", s), ciclo);
      }
    });
    // el cuerpo sube con cada batida (se suma a la trayectoria del vuelo)
    figura.animate(cicloBatida(), { ...ciclo, composite: "add" });
  }

  /** Trayectoria: abre las alas posada, levanta el vuelo y viene hacia la pantalla. */
  function cuadrosVuelo(dx, dy) {
    const d = DESPLIEGUE_MS / VUELO_MS;
    return [
      { transform: "translate(0px, 0px) scale(1)", opacity: 1, offset: 0 },
      { transform: "translate(0px, 0px) scale(1)", opacity: 1, offset: d, easing: "ease-in" },          // abre las alas
      { transform: "translate(0px, -60px) scale(1.06)", opacity: 1, offset: 0.52 },                     // levanta el vuelo
      { transform: `translate(${dx}px, ${dy - 40}px) scale(2.4)`, opacity: 1, offset: 0.8, easing: "ease-in" }, // viene hacia la pantalla
      { transform: `translate(${dx}px, ${dy}px) scale(9)`, opacity: 0, offset: 1 },                    // pasa y desaparece
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
    const anim = vuelo.animate(cuadrosVuelo(dx, dy), { duration: VUELO_MS, fill: "forwards" });
    animarAlas(vuelo);
    const fin = () => { vuelo.remove(); figura.style.visibility = ""; listo(); };
    return anim.finished.then(fin, fin);
  }

  const Aguila = { despegar, cuadrosVuelo, cicloAleteo, cicloBatida, cuadrosDespliegue, pose, plegada, VUELO_MS, DESPLIEGUE_MS, ALETEO_MS };
  if (typeof module !== "undefined" && module.exports) module.exports = Aguila;
  raiz.Aguila = Aguila;
})(typeof window !== "undefined" ? window : globalThis);
