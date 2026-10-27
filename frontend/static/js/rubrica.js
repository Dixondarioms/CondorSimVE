/* Rubrica de evaluacion del informe posterior: convierte la respuesta de /aar/rubrica en filas de tabla
 * (funciones puras, probadas con Node); informe.js las dibuja en el dialogo "Rubrica". */
(function (raiz) {
  "use strict";

  const BANDOS = ["azul", "rojo"];
  const VARIABLE = { combustible: "comb.", municion: "mun." };

  const motivos = (o) => (o.motivos_rechazo || []).map((m) => `${m.motivo} (${m.veces})`).join("; ") || "-";
  const n = (v) => Number(v || 0);

  /** Filas [indicador, valor azul, valor rojo] de la tabla principal. */
  function filasIndicadores(rubrica) {
    const b = rubrica.bandos || {};
    const umbral = rubrica.umbral_critico ?? 25;
    const criticas = (x) => (x.logistica.unidades_criticas || [])
      .map((c) => `${c.unidad} (${c.variables.map((v) => VARIABLE[v] || v).join("/")} ${Math.round(c.minimo)} %, t${c.turno})`)
      .join(", ") || "ninguna";
    const pasivos = (x) => `${x.turnos_pasivos.cantidad}` + (x.turnos_pasivos.turnos.length ? ` (horas ${x.turnos_pasivos.turnos.join(", ")})` : "");
    const def = [
      ["Órdenes emitidas / resueltas / rechazadas", (x) => `${x.ordenes.emitidas} / ${x.ordenes.resueltas} / ${x.ordenes.rechazadas}`],
      ["Tasa de rechazo", (x) => `${n(x.ordenes.tasa_rechazo).toFixed(0)} %`],
      ["Motivos de rechazo más frecuentes", (x) => motivos(x.ordenes)],
      ["Horas sin órdenes (pasivas)", pasivos],
      [`Unidades bajo el ${umbral} % de combustible o munición`, criticas],
      ["Reabastecimientos realizados", (x) => `${x.logistica.reabastecimientos}`],
      ["Pérdidas infligidas / sufridas (pts)", (x) => `${n(x.perdidas.infligidas).toFixed(1)} / ${n(x.perdidas.sufridas).toFixed(1)}`],
      ["Unidades destruidas propias / enemigas", (x) => `${x.perdidas.unidades_destruidas} / ${x.perdidas.enemigas_destruidas}`],
      ["Objetivos cumplidos / fallidos / pendientes", (x) => `${x.objetivos.cumplidos} / ${x.objetivos.fallidos} / ${x.objetivos.pendientes} (${x.objetivos.puntos} pts)`],
      ["Misiones aéreas cumplidas / abortadas / fallidas", (x) => `${x.misiones.cumplidas} / ${x.misiones.abortadas} / ${x.misiones.fallidas} (de ${x.misiones.planificadas})`],
    ];
    return def.map(([etiqueta, f]) => [etiqueta, ...BANDOS.map((k) => (b[k] ? f(b[k]) : "-"))]);
  }

  /** Filas por puesto responsable de un bando (solo los puestos con actividad). */
  function filasPuestos(bando) {
    return Object.values(bando.puestos || {})
      .filter((p) => p.ordenes.emitidas > 0 || p.misiones > 0)
      .map((p) => [`${p.sigla} · ${p.nombre}`, p.ordenes.emitidas, p.ordenes.resueltas, p.ordenes.rechazadas, p.misiones, motivos(p.ordenes)]);
  }

  /** Observaciones del bando mas las de sus puestos (con la sigla delante), sin repetir. */
  function observaciones(bando) {
    const lista = [...(bando.observaciones || [])];
    for (const p of Object.values(bando.puestos || {})) {
      for (const o of p.observaciones || []) if (!lista.includes(o)) lista.push(o);
    }
    return lista;
  }

  function resumen(rubrica) {
    const e = rubrica.escenario || {};
    return `${e.nombre || ""} · ${e.turnos_resueltos ?? 0} hora(s) cumplida(s)` + (e.estado ? ` · ${e.estado}` : "");
  }

  const SIN_AUTOR = "sin autor registrado";
  const turnos = (t) => `${t.cantidad}` + (t.turnos && t.turnos.length ? ` (${t.turnos.join(", ")})` : "");

  /** Filas por alumno [alumno, bando, puesto, ordenes, resueltas, rechazadas, turnos activos / pasivos, misiones,
   * observaciones] mas, por bando, lo que quedo sin autor registrado (ordenes anteriores a esta version). */
  function filasAlumnos(rubrica) {
    const filas = (rubrica.alumnos || []).map((a) => [
      a.username, a.bando, `${a.sigla} · ${a.puesto_nombre}`,
      a.ordenes.emitidas, a.ordenes.resueltas, a.ordenes.rechazadas,
      `${turnos(a.turnos_activos)} / ${turnos(a.turnos_pasivos)}`,
      `${a.misiones.planificadas}` + (a.misiones.planificadas ? ` (${a.misiones.cumplidas} cumplida(s))` : ""),
      (a.observaciones || []).join(" "),
    ]);
    for (const [b, n] of Object.entries(rubrica.sin_autor || {})) {
      if (n.ordenes || n.misiones) filas.push([SIN_AUTOR, b, "-", n.ordenes, "-", "-", "-", `${n.misiones}`, "Órdenes o misiones anteriores al registro del autor."]);
    }
    return filas;
  }

  /** Filas [indicador, azul, rojo] de los indicadores doctrinales (valor y puntaje 0-100) y la calificacion. */
  function filasDoctrina(rubrica) {
    const b = rubrica.bandos || {};
    const ref = BANDOS.map((k) => b[k] && b[k].doctrina).find(Boolean);
    if (!ref) return [];
    const celda = (k, i) => {
      const x = b[k] && b[k].doctrina && b[k].doctrina.indicadores[i];
      if (!x) return "-";
      return `${x.valor}${x.puntaje === null || x.puntaje === undefined ? " (no aplica)" : ` · ${x.puntaje}/100`}`;
    };
    const filas = ref.indicadores.map((ind, i) => [ind.nombre, ...BANDOS.map((k) => celda(k, i))]);
    filas.push(["Calificación (1 a 20)", ...BANDOS.map((k) => (b[k] && b[k].doctrina && b[k].doctrina.nota != null ? `${b[k].doctrina.nota} / 20` : "-"))]);
    return filas;
  }

  /** Filas [indicador, azul, rojo] de la evaluación del trabajo de Estado Mayor (TIEM) y sus notas; [] si ningún
   * bando trabajó con los documentos del TIEM. */
  function filasTiem(rubrica) {
    const b = rubrica.bandos || {};
    const ref = BANDOS.map((k) => b[k] && b[k].tiem).find((x) => x && x.aplica);
    if (!ref) return [];
    const celda = (k, i) => {
      const x = b[k] && b[k].tiem && b[k].tiem.aplica && b[k].tiem.indicadores[i];
      if (!x) return "-";
      return `${x.valor}${x.puntaje === null || x.puntaje === undefined ? " (no aplica)" : ` · ${x.puntaje}/100`}`;
    };
    const nota = (k, campo) => (b[k] && b[k].tiem && b[k].tiem[campo] != null ? `${b[k].tiem[campo]} / 20` : "-");
    const filas = ref.indicadores.map((ind, i) => [ind.nombre, ...BANDOS.map((k) => celda(k, i))]);
    filas.push(["Nota automática", ...BANDOS.map((k) => nota(k, "nota_automatica"))]);
    filas.push(["Nota del instructor (documentos)", ...BANDOS.map((k) => nota(k, "nota_instructor"))]);
    filas.push(["Calificación del trabajo de Estado Mayor", ...BANDOS.map((k) => nota(k, "nota"))]);
    return filas;
  }

  /** Criterio de cada indicador doctrinal (para la nota al pie). */
  const criterios = (rubrica) => {
    const ref = BANDOS.map((k) => rubrica.bandos && rubrica.bandos[k] && rubrica.bandos[k].doctrina).find(Boolean);
    return ref ? ref.indicadores.map((i) => `${i.nombre}: ${i.criterio}`) : [];
  };

  const api = { filasIndicadores, filasPuestos, filasAlumnos, filasDoctrina, filasTiem, criterios, observaciones, resumen, BANDOS, SIN_AUTOR };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  raiz.Rubrica = api;
})(typeof window !== "undefined" ? window : globalThis);
