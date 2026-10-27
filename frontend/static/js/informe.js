/* Visor del informe posterior al ejercicio: repeticion turno a turno sobre el mapa. */
(function (raiz) {
  "use strict";

  const COLOR = { azul: "#4aa3ff", rojo: "#ff5b5b" };

  function crear(ctx) {
    const $ = (id) => document.getElementById(id);
    const capa = L.layerGroup();
    let datos = null;
    let turnos = [];
    let indice = 0;
    let temporizador = null;
    let activo = false;

    const limpiar = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
    const celda = (tag, texto, clase) => {
      const c = document.createElement(tag);
      c.textContent = texto;
      if (clase) c.className = clase;
      return c;
    };

    function tabla(cabeceras, filas, numericas = []) {
      const t = document.createElement("table");
      const cab = document.createElement("tr");
      cabeceras.forEach((h) => cab.appendChild(celda("th", h)));
      t.appendChild(cab);
      for (const fila of filas) {
        const tr = document.createElement("tr");
        fila.forEach((v, i) => {
          const c = celda("td", String(v.texto ?? v), numericas.includes(i) ? "num" : v.clase);
          tr.appendChild(c);
        });
        t.appendChild(tr);
      }
      return t;
    }

    function pararReproduccion() {
      clearInterval(temporizador);
      temporizador = null;
      $("rp-play").textContent = "Reproducir";
    }

    // Replay animado (replay.js): mientras esta abierto, oculta las marcas fijas de la repeticion por turnos.
    const replay = Replay.crear({
      map: ctx.map, api: ctx.api, toast: ctx.toast, escenarioId: ctx.escenarioId, crearIcono: ctx.crearIcono,
      alAbrir: () => { pararReproduccion(); ctx.map.removeLayer(capa); },
      alCerrar: () => { if (activo) { capa.addTo(ctx.map); mostrarTurno(indice); } },
    });

    function mostrarTurno(i) {
      indice = Math.max(0, Math.min(turnos.length - 1, i));
      const t = turnos[indice];
      $("rp-slider").value = String(indice);
      $("rp-turno").textContent = t.turno === 0
        ? "Despliegue inicial"
        : `Hora ${t.turno} de ${turnos[turnos.length - 1].turno} del ejercicio${t.en_curso ? " (en curso)" : ""} · ${Logica.etiquetaClima(t.clima)}`;

      capa.clearLayers();
      if (indice > 0) {
        for (const tr of Logica.trayectorias(turnos[indice - 1].unidades, t.unidades)) {
          L.polyline([tr.desde, tr.hasta], { color: COLOR[tr.bando], weight: 2, dashArray: "5 5", opacity: 0.8, interactive: false }).addTo(capa);
        }
      }
      for (const u of t.unidades) {
        const marcador = L.marker([u.lat, u.lon], { icon: ctx.crearIcono(u), opacity: u.estado === "destruida" ? 0.35 : 1 });
        const tip = document.createElement("span");
        tip.textContent = `${u.nombre} (${u.clase || u.tipo}) fuerza ${Logica.pct(u.fuerza)}, comb ${Logica.pct(u.combustible)}, mun ${Logica.pct(u.municion)} - ${u.estado}`;
        marcador.bindTooltip(tip).addTo(capa);
      }
      const lista = $("rp-combates");
      limpiar(lista);
      for (const l of Logica.lineasCombate(t.combates, t.unidades)) {
        const desc = Logica.describirCombate(l.combate);
        L.polyline([l.desde, l.hasta], { color: "#ff3d00", weight: 3, opacity: 0.9 }).bindTooltip(desc).addTo(capa);
        L.circleMarker(l.hasta, { radius: 7, color: "#ff3d00", fillColor: "#ffab00", fillOpacity: 0.8, weight: 2 }).bindTooltip(desc).addTo(capa);
      }
      for (const c of t.combates) {
        const li = document.createElement("li");
        li.textContent = Logica.describirCombate(c);
        lista.appendChild(li);
      }
      for (const e of t.eventos) {
        if (e.tipo === "ajuste" || e.tipo === "clima" || e.tipo === "logistica" || e.bando_destino === "todos") {
          const li = document.createElement("li");
          li.textContent = `[${e.tipo}] ${e.descripcion}`;
          lista.appendChild(li);
        }
      }
      if (!lista.children.length) {
        const li = document.createElement("li");
        li.textContent = t.turno === 0 ? "Posiciones al comenzar el ejercicio." : "Sin combates ni novedades este turno.";
        lista.appendChild(li);
      }
    }

    async function abrir() {
      const id = ctx.escenarioId();
      if (!id) return;
      try {
        datos = await ctx.api("GET", `/api/escenarios/${id}/aar`);
      } catch (_) {
        return; // el aviso ya se mostro (p. ej. el informe aun no esta disponible)
      }
      turnos = Logica.turnosReproducibles(datos);
      if (!turnos.length) return ctx.toast("Aún no se resolvió ningún turno: no hay nada que repetir.");
      activo = true;
      ctx.alActivar();
      capa.addTo(ctx.map);
      $("replay").hidden = false;
      document.body.classList.add("repitiendo");
      $("rp-slider").max = String(turnos.length - 1);
      $("rp-imprimible").href = `/api/escenarios/${id}/aar.html`;
      $("rp-diapositivas").href = `/api/escenarios/${id}/aar/diapositivas.html`;
      $("rp-csv").href = `/api/escenarios/${id}/aar.csv`;
      mostrarTurno(0);
      ctx.map.fitBounds(turnos[0].unidades.map((u) => [u.lat, u.lon]), { padding: [60, 60], maxZoom: 9 });
    }

    function cerrar() {
      if (!activo) return;
      pararReproduccion();
      replay.cerrar();
      activo = false;
      capa.clearLayers();
      ctx.map.removeLayer(capa);
      $("replay").hidden = true;
      document.body.classList.remove("repitiendo");
      ctx.alDesactivar();
    }

    function resumen() {
      if (!datos) return;
      const cont = $("dlg-contenido");
      limpiar(cont);
      const r = datos.resumen;
      cont.appendChild(tabla(
        ["Bando", "Unidades", "Destruidas", "Combates iniciados", "Recibidos", "Fuerza perdida", "Daño infligido", "Órdenes", "Rechazadas"],
        Object.entries(r).map(([b, x]) => [
          { texto: b, clase: "tag-" + b }, x.unidades, x.destruidas, x.combates_iniciados, x.combates_recibidos,
          x.fuerza_perdida, x.dano_infligido, x.ordenes_emitidas, x.ordenes_rechazadas,
        ]), [1, 2, 3, 4, 5, 6, 7, 8]));
      const conUnidades = turnos;
      if (conUnidades.length) {
        const ini = new Map(conUnidades[0].unidades.map((u) => [u.id, u]));
        const fin = conUnidades[conUnidades.length - 1].unidades;
        cont.appendChild(tabla(
          ["Unidad", "Bando", "Clase", "Fuerza inicial", "Fuerza final", "Estado", "Combustible", "Munición"],
          fin.map((u) => [u.nombre, { texto: u.bando, clase: "tag-" + u.bando }, u.clase || u.tipo,
            Logica.pct((ini.get(u.id) || u).fuerza), Logica.pct(u.fuerza), u.estado, Logica.pct(u.combustible), Logica.pct(u.municion)]),
          [3, 4, 6, 7]));
      }
      $("dlg-resumen").showModal();
    }

    $("rp-slider").addEventListener("input", () => { pararReproduccion(); replay.cerrar(); mostrarTurno(parseInt($("rp-slider").value, 10)); });
    $("rp-ant").addEventListener("click", () => { pararReproduccion(); mostrarTurno(indice - 1); });
    $("rp-sig").addEventListener("click", () => { pararReproduccion(); mostrarTurno(indice + 1); });
    $("rp-replay").addEventListener("click", () => replay.alternar());
    $("rp-play").addEventListener("click", () => {
      if (temporizador) return pararReproduccion();
      replay.cerrar();
      if (indice >= turnos.length - 1) mostrarTurno(0);
      $("rp-play").textContent = "Pausa";
      temporizador = setInterval(() => {
        if (indice >= turnos.length - 1) return pararReproduccion();
        mostrarTurno(indice + 1);
      }, 1800);
    });
    $("rp-resumen").addEventListener("click", resumen);
    $("rp-cerrar").addEventListener("click", cerrar);

    // Linea de tiempo (logistica vs combates): al elegir un suceso, la repeticion salta a ese turno y lugar.
    function alElegirEnLinea(m) {
      $("dlg-timeline").close();
      if (!activo) return;
      const i = turnos.findIndex((t) => t.turno === m.turno);
      if (i >= 0) { pararReproduccion(); replay.cerrar(); mostrarTurno(i); }
      let punto = null;
      if (m.tipo === "combate") punto = [m.datos.lat, m.datos.lon];
      else if (m.unidad_id !== null && i >= 0) {
        const u = turnos[i].unidades.find((x) => x.id === m.unidad_id);
        if (u) punto = [u.lat, u.lon];
      }
      if (punto) ctx.map.setView(punto, Math.max(ctx.map.getZoom(), 9));
    }
    const linea = Timeline.crear({ api: ctx.api, escenarioId: ctx.escenarioId, alElegir: alElegirEnLinea });
    $("rp-timeline").addEventListener("click", () => linea.abrir());

    // Rubrica de evaluacion: indicadores por bando y por puesto responsable, con observaciones automaticas.
    async function rubrica() {
      const id = ctx.escenarioId();
      if (!id) return;
      let datos;
      try {
        datos = await ctx.api("GET", `/api/escenarios/${id}/aar/rubrica`);
      } catch (_) { return; }
      const cont = $("rb-contenido");
      limpiar(cont);
      $("rb-resumen").textContent = Rubrica.resumen(datos);
      $("rb-nota").textContent = datos.nota_puestos || "";
      const t = tabla([], Rubrica.filasIndicadores(datos));
      const th = t.firstChild;
      th.appendChild(celda("th", "Indicador"));
      for (const b of Rubrica.BANDOS) th.appendChild(celda("th", b, "tag-" + b));
      cont.appendChild(t);
      // indicadores doctrinales y calificacion (1 a 20)
      const doctrina = Rubrica.filasDoctrina(datos);
      if (doctrina.length) {
        cont.appendChild(celda("h4", "Indicadores doctrinales y calificación"));
        const td = tabla([], doctrina);
        const thd = td.firstChild;
        thd.appendChild(celda("th", "Indicador"));
        for (const b of Rubrica.BANDOS) thd.appendChild(celda("th", b, "tag-" + b));
        td.lastChild && td.lastChild.classList && td.lastChild.classList.add("fila-nota");
        cont.appendChild(td);
        const det = document.createElement("details");
        det.appendChild(celda("summary", "Cómo se calcula cada indicador"));
        const ul = document.createElement("ul");
        for (const c of Rubrica.criterios(datos)) ul.appendChild(celda("li", c));
        det.appendChild(ul);
        cont.appendChild(det);
      }
      // trabajo de Estado Mayor (TIEM): documentos, forma, oportunidad, ejecucion del plan y supervision
      const tiem = Rubrica.filasTiem(datos);
      if (tiem.length) {
        cont.appendChild(celda("h4", "Trabajo de Estado Mayor (TIEM)"));
        const tt = tabla([], tiem);
        const tht = tt.firstChild;
        tht.appendChild(celda("th", "Indicador"));
        for (const b of Rubrica.BANDOS) tht.appendChild(celda("th", b, "tag-" + b));
        tt.lastChild && tt.lastChild.classList && tt.lastChild.classList.add("fila-nota");
        cont.appendChild(tt);
      }
      for (const b of Rubrica.BANDOS) {
        const x = datos.bandos[b];
        if (!x) continue;
        cont.appendChild(celda("h4", `Observaciones para ${b}`, "tag-" + b));
        const ul = document.createElement("ul");
        for (const o of Rubrica.observaciones(x)) ul.appendChild(celda("li", o));
        cont.appendChild(ul);
        const filas = Rubrica.filasPuestos(x);
        if (filas.length) {
          cont.appendChild(celda("h4", `Por puesto responsable (${b})`));
          cont.appendChild(tabla(["Puesto", "Órdenes", "Resueltas", "Rechazadas", "Misiones", "Motivos de rechazo"], filas, [1, 2, 3, 4]));
        }
      }
      // evaluacion por alumno (autor registrado en cada orden y mision)
      const alumnos = Rubrica.filasAlumnos(datos);
      if (alumnos.length) {
        cont.appendChild(celda("h4", "Evaluación por alumno"));
        cont.appendChild(tabla(["Alumno", "Bando", "Puesto", "Órdenes", "Resueltas", "Rechazadas", "Horas activas / pasivas", "Misiones", "Observaciones"], alumnos, [3, 4, 5]));
        if (datos.nota_alumnos) cont.appendChild(celda("p", datos.nota_alumnos, "ayuda"));
      }
      $("rb-csv").href = `/api/escenarios/${id}/aar/rubrica.csv`;
      $("dlg-rubrica").showModal();
    }
    $("rp-rubrica").addEventListener("click", rubrica);

    // Comparar ejercicios: calificacion e indicadores por bando y evolucion de cada alumno
    async function abrirComparar() {
      let lista = [];
      try { lista = (await ctx.api("GET", "/api/escenarios")) || []; } catch (_) { return; }
      if (!Array.isArray(lista)) lista = lista.escenarios || [];
      const cont = $("cmp-lista");
      limpiar(cont);
      const actual = ctx.escenarioId();
      for (const e of lista) {
        const l = document.createElement("label");
        l.className = "chk";
        const c = document.createElement("input");
        c.type = "checkbox"; c.value = e.id; c.checked = e.id === actual;
        l.append(c, celda("span", `${e.id} · ${e.nombre} (${e.estado}, turno ${e.turno_actual})`));
        cont.appendChild(l);
      }
      limpiar($("cmp-contenido"));
      $("dlg-comparar").showModal();
    }
    async function verComparacion() {
      const ids = [...document.querySelectorAll("#cmp-lista input:checked")].map((c) => c.value);
      if (!ids.length) return ctx.toast("Marque al menos un ejercicio.");
      let d;
      try { d = await ctx.api("GET", `/api/evaluacion/comparar?ids=${ids.join(",")}`); } catch (e) { return ctx.toast(e.message); }
      const cont = $("cmp-contenido");
      limpiar(cont);
      const claves = Object.keys(d.indicadores);
      const filas = [];
      for (const ej of d.ejercicios) {
        for (const b of Rubrica.BANDOS) {
          const x = ej.bandos[b];
          if (!x) continue;
          filas.push([`${ej.nombre} (${ej.turnos} t.)`, b, x.nota == null ? "-" : `${x.nota} / 20`,
            ...claves.map((k) => (x.indicadores[k] == null ? "-" : x.indicadores[k]))]);
        }
      }
      cont.appendChild(celda("h4", "Calificación e indicadores doctrinales (0 a 100) por ejercicio y bando"));
      cont.appendChild(tabla(["Ejercicio", "Bando", "Nota", ...claves.map((k) => d.indicadores[k])], filas, [2]));
      if (d.alumnos.length) {
        cont.appendChild(celda("h4", "Evolución por alumno"));
        const fa = [];
        for (const a of d.alumnos) {
          for (const e of a.ejercicios) {
            fa.push([a.username, e.escenario, `${e.bando} · ${e.puesto}`, e.ordenes, e.rechazadas,
              `${e.turnos_activos} / ${e.turnos_pasivos}`, e.misiones, e.nota_bando == null ? "-" : `${e.nota_bando} / 20`]);
          }
        }
        cont.appendChild(tabla(["Alumno", "Ejercicio", "Bando · puesto", "Órdenes", "Rechazadas", "Horas activas / pasivas", "Misiones", "Nota del bando"], fa, [3, 4, 6]));
      }
    }
    $("rb-comparar").addEventListener("click", abrirComparar);
    $("cmp-ver").addEventListener("click", verComparacion);

    return { abrir, cerrar, activo: () => activo };
  }

  raiz.Informe = { crear };
})(window);
