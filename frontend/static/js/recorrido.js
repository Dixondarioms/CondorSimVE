/* Recorrido guiado del Cóndor: muestra paso a paso cada parte de la pantalla (la resalta y explica para qué sirve),
 * con Anterior / Siguiente / Salir. Al final propone una práctica en el ejercicio «Tutorial del Cóndor».
 * Los pasos cuya parte no se ve para esa cuenta (p. ej., la CONSOLA para un alumno) se saltan solos. */
(function (raiz) {
  "use strict";

  // paso: sel (lo que se resalta; sin sel = tarjeta centrada), marco (resaltar el contenedor mas cercano), pestana (la
  // pestaña de la izquierda que hay que abrir antes), solo ("director" | "alumno"), titulo, texto (HTML propio)
  const PASOS = [
    { titulo: "Bienvenido al Cóndor", texto: `<p>Este recorrido le muestra, paso a paso, cada parte de la pantalla y para qué
      sirve. Tarda unos 5 minutos.</p><p>Avance con <b>Siguiente</b> (o la flecha →), vuelva con <b>Anterior</b> y salga
      cuando quiera con <b>Salir</b> (o Esc). Puede repetirlo desde el botón <b>Ayuda</b>.</p>` },
    { sel: "#cabecera .cab-izq", titulo: "La barra superior", texto: `<p>Muestra la <b>hora del ejercicio</b> (la primera es la 1),
      la <b>hora simulada</b>, el calendario de la operación (día D, hora H y fase) y su <b>bando</b> y repartición.</p>` },
    { sel: "#escenario", marco: "label", titulo: "El ejercicio", texto: `<p>En la lista <b>Escenario</b> se elige el ejercicio.
      Si su cuenta tiene más de uno, asegúrese de estar en el correcto antes de dar órdenes.</p>` },
    { sel: "#reloj", titulo: "El reloj en tiempo real", texto: `<p>Indica si el tiempo corre (▶ y la velocidad: 1×, 10× o 60×)
      o está <b>detenido</b>. En el Cóndor todo pasa en tiempo real: las unidades se mueven y combaten mientras corre el reloj, y
      las órdenes se cumplen en el acto.</p>` },
    { sel: "#panel-izq .pestanas", titulo: "Las pestañas de la izquierda", texto: `<p><b>FUERZAS</b>: sus unidades y sus órdenes.
      <b>SITUACIÓN</b>: radares, personal, apresto e infraestructura. <b>TIEM</b>: el trabajo de Estado Mayor. El director tiene
      además la <b>CONSOLA</b>.</p>` },
    { sel: "#oob", pestana: "fuerzas", marco: "section", titulo: "El orden de batalla", texto: `<p>La lista de las unidades, por
      bando y por tipo, con su estado (operativa, con orden, en base…). Con un clic se selecciona una unidad; con
      <b>Ctrl+clic</b> se suman varias. El buscador encuentra una por nombre, clase o modelo.</p>` },
    { sel: "#sec-doctrina", pestana: "fuerzas", titulo: "Doctrina y reglas de enfrentamiento", texto: `<p>Decide cómo actúan sus
      unidades por su cuenta: si tiran solas contra aeronaves y contra blancos de superficie (libre, solo identificados o solo con
      orden), cuántos misiles por blanco, a qué distancia abren fuego y cuándo regresan las aeronaves.</p>` },
    { sel: "#panel-unidad", titulo: "La unidad seleccionada (abajo)", texto: `<p>Al elegir una unidad, en la parte de
      abajo de la pantalla aparece todo lo suyo: su foto, su <b>misión</b> (la orden que cumple), fuerza, combustible y munición,
      capacidades (velocidad, alcances, detección, efectividad contra aire, tierra y mar) y su armamento. Con <b>▼ Esconder</b>
      se achica. De una unidad enemiga solo se ve lo que su bando sabe de ella.</p>` },
    { sel: "#sec-aviacion", pestana: "fuerzas", solo: "alumno", titulo: "Aviación", texto: `<p>Desde aquí despegan los aviones, drones
      y aviones de guerra electrónica: <b>Enviar aeronaves o drones…</b>, elija el tipo, cuántos y la base. Arriba se ve cuántas
      quedan del tope del bando.</p>` },
    { sel: "#sec-misiones", pestana: "fuerzas", titulo: "Misiones aéreas", texto: `<p>Para planificar misiones completas (aeronaves,
      ruta, blanco, escolta y hora) que se cumplen solas al llegar la hora.</p>` },
    { sel: "#sec-orden", pestana: "fuerzas", solo: "alumno", titulo: "Nueva orden", texto: `<p>Con una unidad seleccionada:
      elija el tipo de orden (<b>Mover</b>, <b>Atacar</b>, <b>Apoyar</b>… solo aparecen las que esa unidad puede cumplir), marque en
      el mapa los puntos o el blanco y envíela. Una orden nueva reemplaza a la anterior.</p>` },
    { sel: "#cola", pestana: "fuerzas", marco: "section", titulo: "La cola de órdenes", texto: `<p>Las órdenes en curso y las
      recientes, con su resultado. El botón <b>■</b> detiene una orden.</p>` },
    { sel: "#map", titulo: "El mapa", texto: `<p>Rueda del ratón: acercar o alejar. Arrastrar: mover el mapa. Clic sobre una unidad:
      seleccionarla. Pase el cursor sobre una unidad para ver su tarjeta.</p><p>Un enemigo dudoso lleva un <b>círculo amarillo</b>
      (dónde puede estar en realidad); las unidades que se mueven dejan una <b>estela</b>.</p>` },
    { sel: "#barra-graficos", titulo: "Gráficos tácticos", texto: `<p>Para dibujar líneas de fase, ejes de avance, zonas de reunión y
      puntos de control, visibles para todos o solo para su bando.</p>` },
    { sel: "#barra-herramientas", titulo: "Herramientas del mapa", texto: `<p>La <b>Regla</b> mide distancias y <b>Convertir</b> pasa
      coordenadas de un formato a otro. Abajo a la izquierda, el mapa muestra las coordenadas del cursor.</p>` },
    { sel: "#sec-radar", pestana: "situacion", titulo: "SITUACIÓN: el cuadro radar", texto: `<p>Lo que detecta ahora cada radar y
      sensor de su bando: distancia, rumbo y si el contacto es desconocido, clasificado o identificado. Más abajo: personal, apresto,
      esfuerzo aéreo, transmisiones, inteligencia e infraestructura.</p>` },
    { sel: "#sec-pmo", pestana: "pmo", titulo: "TIEM: trabajo de Estado Mayor", texto: `<p>El <b>Problema Militar Operativo</b> de
      su bando, las apreciaciones, el ensayo de las formas de acción, la <b>Orden de Operaciones</b>, la supervisión y la
      evaluación.</p>` },
    { sel: "#pest-consola", pestana: "consola", solo: "director", titulo: "CONSOLA del director", texto: `<p>Todo para preparar y
      conducir el ejercicio: reloj y pausa automática, meteorología, unidades, objetivos, eventos e informes para inyectar, el
      adversario automático y los usuarios con acceso.</p>` },
    { sel: "#icono-clima", marco: "section", titulo: "Estado del escenario", texto: `<p>El clima donde se mira, la visibilidad, cómo
      afecta al movimiento y a los ataques aéreos, la hora simulada y el estado del reloj.</p>` },
    { sel: "#tarjeta-objetivos", titulo: "Objetivos y puntaje", texto: `<p>Los objetivos de cada bando, su avance y los puntos. Al
      final del ejercicio deciden el resultado.</p>` },
    { sel: "#base-satelite", marco: "section", titulo: "Capas del mapa", texto: `<p>Qué se ve en el mapa: satélite o relieve, niebla
      de guerra, cobertura de detección, <b>estelas</b> (y su largo), símbolos militares APP-6, meteorología (<b>solo el radio</b> o
      <b>satélite meteorológico</b>), objetivos y más.</p>` },
    { sel: "#tarjeta-chat", titulo: "Comunicaciones", texto: `<p>Mensajes al resto de su bando (o al director). Las comunicaciones
      pueden tener demoras si el director las simula.</p>` },
    { sel: "#alertas-nuevas", marco: "section", titulo: "Alertas", texto: `<p>Lo importante, al instante: contacto nuevo, ataque a una
      unidad propia, unidad perdida, combustible crítico, misión terminada. Un clic lleva el mapa al lugar.</p>` },
    { sel: "#control-turno", titulo: "La barra del reloj", texto: `<p>La hora simulada grande y el estado del reloj. El director
      lo pone en marcha o lo detiene, elige la velocidad (1×, 10×, 60×) y puede adelantar una hora (+1 h). A la derecha, quién
      conduce cada bando.</p>` },
    { sel: "#btn-informe", titulo: "Informe y repetición", texto: `<p>El resumen del ejercicio, la línea de tiempo, la
      <b>repetición</b> sobre el mapa y la rúbrica de evaluación.</p>` },
    { sel: "#btn-videowall", titulo: "Videowall", texto: `<p>El mapa a pantalla completa para un proyector (tecla <b>V</b>; Esc
      para volver).</p>` },
    { sel: "#btn-ayuda", titulo: "Ayuda", texto: `<p>Cuando tenga una duda, pulse <b>Ayuda</b> (o la tecla <b>F1</b>) y escriba su
      pregunta con sus palabras.</p>` },
    { titulo: "Ahora, a practicar", texto: `<p>En el ejercicio <b>«Tutorial del Cóndor»</b> (pídaselo al director) pruebe, en
      este orden:</p><ol><li>Seleccione su brigada de infantería en el orden de batalla.</li>
      <li>Ordénele <b>Mover</b>: marque 2 puntos en el mapa y envíe la orden; mire cómo avanza y deja su estela.</li>
      <li>Despegue una patrulla de cazas desde su base (<b>Aviación</b>) y ordénele <b>Patrullar</b> sobre su brigada.</li>
      <li>Cuando aparezca el enemigo (círculo amarillo), vea en el <b>cuadro radar</b> cómo pasa de desconocido a identificado.</li>
      <li>Ordene <b>Atacar</b> con su artillería o sus blindados y siga el combate en <b>Alertas</b>.</li>
      <li>Al terminar, abra el <b>Informe</b> y mire la repetición.</li></ol>` },
  ];

  /** ctx: { esInstructor() } */
  function crear(ctx) {
    let pasos = [];
    let i = 0;
    let foco = null;
    let tarjeta = null;
    let activo = false;

    const corresponde = (p) => !p.solo || (p.solo === "director") === !!ctx.esInstructor();

    function objetivo(p) {
      if (!p.sel) return null;
      let el = document.querySelector(p.sel);
      if (el && p.marco) el = el.closest(p.marco) || el;
      if (!el) return null;
      const r = el.getBoundingClientRect();
      const visible = r.width > 4 && r.height > 4 && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
      return visible ? el : null;
    }

    function abrirPestana(p) {
      if (!p.pestana) return;
      const b = document.querySelector(`[data-pestana="${p.pestana}"]`);
      if (b && !b.classList.contains("activa")) b.click();
    }

    function colocar(el) {
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      if (!el) {
        foco.hidden = true;
        tarjeta.style.left = `${Math.max(12, (vw - tarjeta.offsetWidth) / 2)}px`;
        tarjeta.style.top = `${Math.max(12, (vh - tarjeta.offsetHeight) / 2)}px`;
        tarjeta.classList.add("centrada");
        return;
      }
      tarjeta.classList.remove("centrada");
      const r = el.getBoundingClientRect();
      const m = 6;
      const top = Math.max(2, r.top - m);
      const left = Math.max(2, r.left - m);
      foco.hidden = false;
      Object.assign(foco.style, { top: `${top}px`, left: `${left}px`, width: `${Math.min(vw - 4, r.width + 2 * m)}px`,
        height: `${Math.min(vh - 4, r.bottom + m - top)}px` });
      const w = tarjeta.offsetWidth;
      const h = tarjeta.offsetHeight;
      let x;
      let y;
      if (r.right + 14 + w < vw) { x = r.right + 14; y = r.top; }                // a la derecha
      else if (r.left - 14 - w > 0) { x = r.left - 14 - w; y = r.top; }          // a la izquierda
      else if (r.bottom + 14 + h < vh) { x = r.left; y = r.bottom + 14; }        // abajo
      else { x = r.left; y = r.top - 14 - h; }                                    // arriba
      if (r.width > vw * 0.5 && r.height > vh * 0.5) { x = r.left + 24; y = r.top + 24; }  // el mapa: dentro
      tarjeta.style.left = `${Math.min(Math.max(10, x), vw - w - 10)}px`;
      tarjeta.style.top = `${Math.min(Math.max(10, y), vh - h - 10)}px`;
    }

    function pintar(direccion = 1) {
      // salta los pasos cuya parte no se ve para esta cuenta
      while (i >= 0 && i < pasos.length) {
        abrirPestana(pasos[i]);
        if (!pasos[i].sel || objetivo(pasos[i])) break;
        i += direccion;
      }
      if (i < 0) i = 0;
      if (i >= pasos.length) { terminar(); return; }
      const p = pasos[i];
      const el = objetivo(p);
      if (el) el.scrollIntoView({ block: "nearest", inline: "nearest" });
      tarjeta.querySelector(".rec-paso").textContent = `Paso ${i + 1} de ${pasos.length}`;
      tarjeta.querySelector(".rec-titulo").textContent = p.titulo;
      tarjeta.querySelector(".rec-texto").innerHTML = p.texto;  // texto propio y fijo
      tarjeta.querySelector(".rec-anterior").disabled = i === 0;
      tarjeta.querySelector(".rec-siguiente").textContent = i === pasos.length - 1 ? "Terminar" : "Siguiente →";
      requestAnimationFrame(() => colocar(objetivo(p)));
      tarjeta.querySelector(".rec-siguiente").focus({ preventScroll: true });
    }

    function alTeclado(e) {
      if (!activo) return;
      if (e.key === "Escape") { e.preventDefault(); terminar(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); siguiente(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); anterior(); }
    }
    const alCambiarTamano = () => { if (activo) colocar(objetivo(pasos[i])); };

    function siguiente() { if (i >= pasos.length - 1) terminar(); else { i += 1; pintar(1); } }
    function anterior() { if (i > 0) { i -= 1; pintar(-1); } }

    function iniciar() {
      if (activo) return;
      pasos = PASOS.filter(corresponde);
      i = 0;
      activo = true;
      foco = Object.assign(document.createElement("div"), { className: "recorrido-foco" });
      tarjeta = Object.assign(document.createElement("div"), { className: "recorrido-tarjeta" });
      tarjeta.setAttribute("role", "dialog");
      tarjeta.setAttribute("aria-live", "polite");
      tarjeta.setAttribute("aria-label", "Recorrido guiado");
      tarjeta.innerHTML = `<p class="rec-paso"></p><h3 class="rec-titulo"></h3><div class="rec-texto"></div>
        <div class="rec-botones"><button type="button" class="rec-salir mini">Salir</button>
        <button type="button" class="rec-anterior secundario">← Anterior</button>
        <button type="button" class="rec-siguiente">Siguiente →</button></div>`;
      document.body.append(foco, tarjeta);
      tarjeta.querySelector(".rec-salir").addEventListener("click", terminar);
      tarjeta.querySelector(".rec-anterior").addEventListener("click", anterior);
      tarjeta.querySelector(".rec-siguiente").addEventListener("click", siguiente);
      document.addEventListener("keydown", alTeclado, true);
      window.addEventListener("resize", alCambiarTamano);
      pintar(1);
    }

    function terminar() {
      activo = false;
      document.removeEventListener("keydown", alTeclado, true);
      window.removeEventListener("resize", alCambiarTamano);
      if (foco) foco.remove();
      if (tarjeta) tarjeta.remove();
      foco = tarjeta = null;
      const b = document.querySelector('[data-pestana="fuerzas"]');
      if (b) b.click();
    }

    return { iniciar, terminar, activo: () => activo, paso: () => i };
  }

  const api = { crear, PASOS };
  if (typeof module !== "undefined") module.exports = api;
  raiz.Recorrido = api;
})(typeof window !== "undefined" ? window : globalThis);
