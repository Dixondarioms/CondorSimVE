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
    const pasivos = (x) => `${x.turnos_pasivos.cantidad}` + (x.turnos_pasivos.turnos.length ? ` (turnos ${x.turnos_pasivos.turnos.join(", ")})` : "");
    const def = [
      ["Órdenes emitidas / resueltas / rechazadas", (x) => `${x.ordenes.emitidas} / ${x.ordenes.resueltas} / ${x.ordenes.rechazadas}`],
      ["Tasa de rechazo", (x) => `${n(x.ordenes.tasa_rechazo).toFixed(0)} %`],
      ["Motivos de rechazo más frecuentes", (x) => motivos(x.ordenes)],
      ["Turnos pasivos (sin ninguna orden)", pasivos],
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
    return `${e.nombre || ""} · ${e.turnos_resueltos ?? 0} turno(s) resuelto(s)` + (e.estado ? ` · ${e.estado}` : "");
  }

  const api = { filasIndicadores, filasPuestos, observaciones, resumen, BANDOS };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }
  raiz.Rubrica = api;
})(typeof window !== "undefined" ? window : globalThis);
