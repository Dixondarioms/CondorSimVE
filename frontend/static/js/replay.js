/* Replay animado del informe posterior: recorre los turnos con instantanea de forma continua sobre el mapa
 * (posiciones interpoladas entre turno y turno, destellos en los combates, unidades destruidas que se desvanecen,
 * estela recorrida por cada unidad y rotulo con hora, clima, marcador y novedades del turno).
 *
 * La logica pura (interpolacion, estado en un instante, estelas, progreso) se exporta con module.exports para
 * probarla con Node; `crear` engancha esa logica al mapa Leaflet y a los controles del panel del informe. */
(function (raiz) {
  "use strict";

  const Logica = raiz.Logica || (typeof require === "function" ? require("./logica.js") : null);

  const COLOR = { azul: "#4aa3ff", rojo: "#ff5b5b" };
  const VELOCIDADES = [0.5, 1, 2, 4];
  const DURACION_TURNO_MS = 1500;   // a velocidad 1x, cada turno dura 1,5 s
  const PASOS_SLIDER = 1000;        // subdivisiones de la barra de progreso por turno
  const OPACIDAD_DESTRUIDA = 0.2;   // a lo que queda una unidad destruida (se desvanece hasta ahi)
  const UMBRAL_ESTELA = 0.0005;     // grados: por debajo no se considera movimiento

  // ------------------------------------------------------------------ logica pura
  /** Suavizado (ease in-out) de la fraccion 0..1: la unidad arranca y frena, no da un salto. */
  const suavizar = (f) => (f <= 0 ? 0 : f >= 1 ? 1 : f * f * (3 - 2 * f));

  /** Posicion [lat, lon] entre `a` (turno N) y `b` (turno N+1) para la fraccion `f` (0 = a, 1 = b). */
  function interpolar(a, b, f) {
    const s = suavizar(f);
    return [a.lat + (b.lat - a.lat) * s, a.lon + (b.lon - a.lon) * s];
  }

  /** Recorta el instante al rango valido [0, ultimo turno]. */
  const acotar = (tiempo, n) => Math.max(0, Math.min(Math.max(0, n - 1), Number.isFinite(tiempo) ? tiempo : 0));

  /** Estado de todas las unidades y los combates en el instante `tiempo` (en turnos: 1.25 = un cuarto del camino
   * entre la instantanea 1 y la 2). Cada unidad lleva su posicion interpolada y su opacidad (las destruidas y las
   * que desaparecen se desvanecen; las que aparecen, se materializan). */
  function estadoEnInstante(turnos, tiempo) {
    const n = turnos.length;
    if (!n) return { indice: 0, fraccion: 0, destino: 0, turno: null, unidades: [], combates: [] };
    const t = acotar(tiempo, n);
    const indice = Math.min(n - 1, Math.floor(t));
    const fraccion = t - indice;
    const desde = turnos[indice];
    const hasta = turnos[Math.min(n - 1, indice + 1)];
    const enTransicion = fraccion > 0 && indice < n - 1;
    const destino = enTransicion ? indice + 1 : indice;
    const porId = new Map(hasta.unidades.map((u) => [u.id, u]));
    const opacidadDe = (estado) => (estado === "destruida" ? OPACIDAD_DESTRUIDA : 1);
    const unidades = [];
    const vistas = new Set();
    for (const a of desde.unidades) {
      vistas.add(a.id);
      const b = porId.get(a.id);
      if (!enTransicion || !b) {
        // sin transicion (o la unidad desaparece en el turno siguiente: se desvanece)
        const op = enTransicion ? opacidadDe(a.estado) * (1 - fraccion) : opacidadDe(a.estado);
        unidades.push({ ...a, opacidad: op, desvaneciendo: enTransicion });
        continue;
      }
      const [lat, lon] = interpolar(a, b, fraccion);
      const oa = opacidadDe(a.estado), ob = opacidadDe(b.estado);
      unidades.push({
        ...b, lat, lon, opacidad: oa + (ob - oa) * fraccion,
        desvaneciendo: ob < oa, fuerza: a.fuerza + (b.fuerza - a.fuerza) * fraccion,
      });
    }
    if (enTransicion) {
      for (const b of hasta.unidades) {
        if (!vistas.has(b.id)) unidades.push({ ...b, opacidad: opacidadDe(b.estado) * fraccion, desvaneciendo: false });
      }
    }
    return {
      indice, fraccion, destino, turno: turnos[destino], unidades,
      combates: turnos[destino].combates || [],
    };
  }

  /** Intensidad 0..1 del destello de un combate a lo largo de la transicion: tres pulsos que se apagan al final. */
  function intensidadCombate(fraccion) {
    const f = Math.max(0, Math.min(1, fraccion));
    const pulso = 0.5 + 0.5 * Math.sin(f * Math.PI * 6 - Math.PI / 2);
    return pulso * (1 - 0.6 * f);
  }

  /** Lineas atacante -> defensor de los combates, con las posiciones ya interpoladas de `unidades`. */
  function lineasCombate(combates, unidades) {
    const por = new Map(unidades.map((u) => [u.id, u]));
    const salida = [];
    for (const c of combates) {
      const a = por.get(c.atacante_id);
      const d = por.get(c.defensor_id);
      const lugar = c.lat != null && c.lon != null ? [c.lat, c.lon] : d ? [d.lat, d.lon] : null;
      if (!lugar) continue;
      salida.push({ combate: c, desde: a ? [a.lat, a.lon] : null, hasta: lugar });
    }
    return salida;
  }

  /** Estelas: para cada unidad que se movio, los puntos recorridos hasta el instante `tiempo` (el ultimo es la
   * posicion interpolada). Solo unidades con al menos dos puntos distintos. */
  function estelas(turnos, tiempo) {
    const n = turnos.length;
    if (!n) return [];
    const t = acotar(tiempo, n);
    const indice = Math.min(n - 1, Math.floor(t));
    const actual = new Map(estadoEnInstante(turnos, t).unidades.map((u) => [u.id, u]));
    const puntos = new Map();
    for (let i = 0; i <= indice; i++) {
      for (const u of turnos[i].unidades) {
        const lista = puntos.get(u.id) || { id: u.id, bando: u.bando, nombre: u.nombre, puntos: [] };
        lista.puntos.push([u.lat, u.lon]);
        puntos.set(u.id, lista);
      }
    }
    const salida = [];
    for (const e of puntos.values()) {
      const u = actual.get(e.id);
      if (u) e.puntos.push([u.lat, u.lon]);
      const limpios = e.puntos.filter((p, i, arr) =>
        i === 0 || Math.abs(p[0] - arr[i - 1][0]) > UMBRAL_ESTELA || Math.abs(p[1] - arr[i - 1][1]) > UMBRAL_ESTELA);
      if (limpios.length >= 2) salida.push({ id: e.id, bando: e.bando, nombre: e.nombre, puntos: limpios });
    }
    return salida;
  }

  /** Zona donde pasa algo: puntos de las estelas completas y lugares de combate ([[lat, lon], ...]); vacia si
   * nadie se movio ni combatio (entonces el visor conserva el encuadre que tenga). */
  function zonaDeInteres(turnos) {
    const puntos = [];
    for (const e of estelas(turnos, turnos.length - 1)) puntos.push(...e.puntos);
    for (const t of turnos) {
      for (const c of t.combates || []) if (c.lat != null && c.lon != null) puntos.push([c.lat, c.lon]);
    }
    return puntos;
  }

  /** Instante siguiente tras `dtMs` milisegundos a la velocidad dada (acotado al ultimo turno). */
  function avanzar(tiempo, dtMs, velocidad, n, duracionMs = DURACION_TURNO_MS) {
    return acotar(tiempo + (Math.max(0, dtMs) * (velocidad || 1)) / duracionMs, n);
  }

  /** Conversion entre el instante y el valor entero de la barra de progreso. */
  const sliderDeTiempo = (tiempo) => Math.round(tiempo * PASOS_SLIDER);
  const tiempoDeSlider = (valor, n) => acotar((parseInt(valor, 10) || 0) / PASOS_SLIDER, n);
  const sliderMax = (n) => Math.max(0, n - 1) * PASOS_SLIDER;

  /** Texto del rotulo: "Turno 2 de 5 · 08:00h · Lluvia · Marcador azul 12 - rojo 4". */
  function textoRotulo(turnos, estado, horaInicioMin) {
    if (!estado.turno) return "";
    const t = estado.turno;
    const ultimo = turnos[turnos.length - 1].turno;
    const clima = Logica ? Logica.etiquetaClima(t.clima) : (t.clima || "");
    const partes = [];
    if (t.turno === 0) partes.push("Despliegue inicial");
    else {
      partes.push(`Turno ${t.turno} de ${ultimo}`);
      if (Logica) partes.push(Logica.textoHora(Logica.horaSimulada(horaInicioMin, t.turno)));
    }
    if (clima) partes.push(clima);
    if (t.marcador) partes.push(`Marcador azul ${t.marcador.azul.total} - rojo ${t.marcador.rojo.total}`);
    return partes.join(" · ");
  }

  /** Novedades del turno para el rotulo: combates (con sus bajas) y eventos publicos. */
  function novedades(turno) {
    if (!turno) return [];
    const lista = [];
    for (const c of turno.combates || []) {
      lista.push(`${c.atacante} → ${c.defensor}: bajas ${Number(c.perdida_atacante || 0).toFixed(0)}/${Number(c.perdida_defensor || 0).toFixed(0)}`);
    }
    for (const e of turno.eventos || []) lista.push(`[${e.tipo}] ${e.descripcion}`);
    return lista;
  }

  // ------------------------------------------------------------------ visor sobre el mapa
  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const capaEstelas = L.layerGroup();
    const capaCombates = L.layerGroup();
    const capaUnidades = L.layerGroup();
    const marcadores = new Map();   // id -> L.marker (uno por unidad, se reubica en cada cuadro)
    const rotulos = new Map();      // id -> span del tooltip (texto plano: el nombre no se interpreta como HTML)
    const trazas = new Map();       // id -> L.polyline de la estela
    let turnos = [];
    let escenario = null;
    let tiempo = 0;
    let velocidad = 1;
    let reproduciendo = false;
    let cuadro = null;              // requestAnimationFrame pendiente
    let ultimo = 0;                 // marca de tiempo del cuadro anterior
    let activo = false;
    let reanudarTrasArrastre = false;

    const limpiar = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };

    function textoUnidad(u) {
      return `${u.nombre} (${u.clase || u.tipo}) fuerza ${Math.round(u.fuerza)} - ${u.estado}`;
    }

    function dibujar() {
      const estado = estadoEnInstante(turnos, tiempo);
      const vivos = new Set();
      for (const u of estado.unidades) {
        vivos.add(u.id);
        let m = marcadores.get(u.id);
        if (!m) {
          m = L.marker([u.lat, u.lon], { icon: ctx.crearIcono(u), keyboard: false });
          const tip = document.createElement("span");
          m.bindTooltip(tip).addTo(capaUnidades);
          marcadores.set(u.id, m);
          rotulos.set(u.id, tip);
        }
        m.setLatLng([u.lat, u.lon]);
        m.setOpacity(u.opacidad);
        rotulos.get(u.id).textContent = textoUnidad(u);
      }
      for (const [id, m] of marcadores) {
        if (!vivos.has(id)) { capaUnidades.removeLayer(m); marcadores.delete(id); rotulos.delete(id); }
      }

      capaCombates.clearLayers();
      const intensidad = estado.fraccion > 0 ? intensidadCombate(estado.fraccion) : 0.5;
      for (const l of lineasCombate(estado.combates, estado.unidades)) {
        if (l.desde) L.polyline([l.desde, l.hasta], { color: "#ff3d00", weight: 2 + 2 * intensidad, opacity: 0.4 + 0.6 * intensidad, interactive: false }).addTo(capaCombates);
        L.circleMarker(l.hasta, { radius: 6 + 14 * intensidad, color: "#ff3d00", fillColor: "#ffab00", fillOpacity: 0.25 + 0.5 * intensidad, weight: 2, interactive: false }).addTo(capaCombates);
        L.circleMarker(l.hasta, { radius: 4, color: "#fff3c4", fillColor: "#fff3c4", fillOpacity: 1, weight: 1, interactive: false }).addTo(capaCombates);
      }

      if ($("ra-estela").checked) {
        const activas = new Set();
        for (const e of estelas(turnos, tiempo)) {
          activas.add(e.id);
          let p = trazas.get(e.id);
          if (!p) {
            p = L.polyline(e.puntos, { color: COLOR[e.bando] || "#ccc", weight: 2, opacity: 0.75, dashArray: "6 4", interactive: false }).addTo(capaEstelas);
            trazas.set(e.id, p);
          } else p.setLatLngs(e.puntos);
        }
        for (const [id, p] of trazas) if (!activas.has(id)) { capaEstelas.removeLayer(p); trazas.delete(id); }
      } else if (trazas.size) {
        capaEstelas.clearLayers();
        trazas.clear();
      }

      $("ra-progreso").value = String(sliderDeTiempo(tiempo));
      $("ra-turno").textContent = textoRotulo(turnos, estado, escenario ? escenario.hora_inicio_min : 360);
      const ul = $("ra-novedades");
      limpiar(ul);
      for (const texto of novedades(estado.turno)) {
        const li = document.createElement("li");
        li.textContent = texto;
        ul.appendChild(li);
      }
      ul.hidden = !ul.children.length;
    }

    function paso(ahora) {
      cuadro = null;
      if (!reproduciendo) return;
      const dt = ultimo ? ahora - ultimo : 0;
      ultimo = ahora;
      tiempo = avanzar(tiempo, dt, velocidad, turnos.length);
      dibujar();
      if (tiempo >= turnos.length - 1) return pausar();
      cuadro = requestAnimationFrame(paso);
    }

    function reproducir() {
      if (!turnos.length) return;
      if (tiempo >= turnos.length - 1) tiempo = 0;
      reproduciendo = true;
      ultimo = 0;
      $("ra-play").textContent = "Pausa";
      if (!cuadro) cuadro = requestAnimationFrame(paso);
    }

    function pausar() {
      reproduciendo = false;
      if (cuadro) cancelAnimationFrame(cuadro);
      cuadro = null;
      $("ra-play").textContent = "Reproducir";
    }

    function irA(t) {
      tiempo = acotar(t, turnos.length);
      dibujar();
    }

    async function abrir() {
      const id = ctx.escenarioId();
      if (!id) return;
      let datos;
      try {
        datos = await ctx.api("GET", `/api/escenarios/${id}/aar/replay`);
      } catch (_) {
        return; // el aviso ya se mostro
      }
      turnos = (datos.turnos || []).filter((t) => t.unidades && t.unidades.length);
      escenario = datos.escenario || null;
      if (turnos.length < 2) return ctx.toast("Hace falta al menos un turno resuelto para animar el replay.");
      if (activo) cerrar();
      activo = true;
      ctx.alAbrir();
      capaEstelas.addTo(ctx.map);
      capaCombates.addTo(ctx.map);
      capaUnidades.addTo(ctx.map);
      $("replay-anim").hidden = false;
      $("rp-replay").classList.add("activo");
      document.body.classList.add("replay-animado");
      $("ra-progreso").max = String(sliderMax(turnos.length));
      $("ra-velocidad").value = String(velocidad);
      tiempo = 0;
      const zona = zonaDeInteres(turnos);
      if (zona.length) ctx.map.fitBounds(zona, { padding: [80, 80], maxZoom: 12 });
      dibujar();
      reproducir();
    }

    function cerrar() {
      if (!activo) return;
      pausar();
      activo = false;
      for (const capa of [capaUnidades, capaCombates, capaEstelas]) {
        capa.clearLayers();
        ctx.map.removeLayer(capa);
      }
      marcadores.clear();
      rotulos.clear();
      trazas.clear();
      $("replay-anim").hidden = true;
      $("rp-replay").classList.remove("activo");
      document.body.classList.remove("replay-animado");
      ctx.alCerrar();
    }

    $("ra-play").addEventListener("click", () => (reproduciendo ? pausar() : reproducir()));
    $("ra-inicio").addEventListener("click", () => { pausar(); irA(0); });
    $("ra-fin").addEventListener("click", () => { pausar(); irA(turnos.length - 1); });
    $("ra-velocidad").addEventListener("change", () => { velocidad = parseFloat($("ra-velocidad").value) || 1; });
    $("ra-estela").addEventListener("change", () => { if (activo) dibujar(); });
    $("ra-progreso").addEventListener("input", () => {
      if (reproduciendo) { reanudarTrasArrastre = true; pausar(); }
      irA(tiempoDeSlider($("ra-progreso").value, turnos.length));
    });
    $("ra-progreso").addEventListener("change", () => {
      if (reanudarTrasArrastre && tiempo < turnos.length - 1) reproducir();
      reanudarTrasArrastre = false;
    });

    return { abrir, cerrar, activo: () => activo, alternar: () => (activo ? cerrar() : abrir()) };
  }

  const api = {
    crear, suavizar, interpolar, estadoEnInstante, intensidadCombate, lineasCombate, estelas, zonaDeInteres, avanzar,
    sliderDeTiempo, tiempoDeSlider, sliderMax, textoRotulo, novedades,
    VELOCIDADES, DURACION_TURNO_MS, PASOS_SLIDER, OPACIDAD_DESTRUIDA,
  };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  raiz.Replay = api;
})(typeof window !== "undefined" ? window : globalThis);
