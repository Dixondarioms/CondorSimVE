const test = require("node:test");
const assert = require("node:assert/strict");
const R = require("../static/js/rubrica.js");
const P = require("../static/js/plantillas.js");

const bando = (extra = {}) => ({
  ordenes: { emitidas: 3, resueltas: 1, rechazadas: 2, pendientes: 0, tasa_rechazo: 66.7,
    motivos_rechazo: [{ motivo: "Objetivo fuera de alcance", veces: 2 }] },
  turnos_pasivos: { cantidad: 2, turnos: [1, 3] },
  logistica: { unidades_criticas: [{ unidad_id: 1, unidad: "A", bando: "azul", variables: ["combustible", "municion"], turno: 2, minimo: 12.4 }], unidades_en_nivel_critico: 1, reabastecimientos: 1 },
  perdidas: { infligidas: 30.25, sufridas: 10, unidades_destruidas: 0, enemigas_destruidas: 1 },
  objetivos: { cumplidos: 1, fallidos: 0, pendientes: 2, puntos: 20 },
  misiones: { planificadas: 2, cumplidas: 1, abortadas: 1, fallidas: 0, canceladas: 0, en_curso: 0 },
  puestos: {
    inteligencia: { sigla: "A2", nombre: "Inteligencia", ordenes: { emitidas: 0, resueltas: 0, rechazadas: 0, motivos_rechazo: [] }, misiones: 0, observaciones: [] },
    planificacion: { sigla: "A5", nombre: "Planificacion", ordenes: { emitidas: 3, resueltas: 1, rechazadas: 2, motivos_rechazo: [{ motivo: "Objetivo fuera de alcance", veces: 2 }] }, misiones: 0,
      observaciones: ["2 orden(es) rechazada(s) en A5 por 'Objetivo fuera de alcance': revisar la apreciacion de distancias antes de emitir la orden."] },
  },
  observaciones: ["Alta proporcion de ordenes rechazadas (67 % de 3): verificar alcance, municion y estado de la unidad antes de emitir."],
  ...extra,
});

const datos = () => ({
  escenario: { id: 1, nombre: "Prueba", estado: "activo", turno_actual: 4, turnos_resueltos: 3 },
  umbral_critico: 25, nota_puestos: "nota",
  bandos: { azul: bando(), rojo: bando({ turnos_pasivos: { cantidad: 0, turnos: [] }, logistica: { unidades_criticas: [], unidades_en_nivel_critico: 0, reabastecimientos: 0 } }) },
});

test("filasIndicadores arma una fila por indicador con una columna por bando", () => {
  const filas = R.filasIndicadores(datos());
  assert.equal(filas.length, 10);
  assert.ok(filas.every((f) => f.length === 3));
  const por = Object.fromEntries(filas.map((f) => [f[0], f.slice(1)]));
  assert.deepEqual(por["Órdenes emitidas / resueltas / rechazadas"], ["3 / 1 / 2", "3 / 1 / 2"]);
  assert.deepEqual(por["Tasa de rechazo"], ["67 %", "67 %"]);
  assert.deepEqual(por["Motivos de rechazo más frecuentes"], ["Objetivo fuera de alcance (2)", "Objetivo fuera de alcance (2)"]);
  assert.deepEqual(por["Turnos pasivos (sin ninguna orden)"], ["2 (turnos 1, 3)", "0"]);
  assert.deepEqual(por["Unidades bajo el 25 % de combustible o munición"], ["A (comb./mun. 12 %, t2)", "ninguna"]);
  assert.deepEqual(por["Pérdidas infligidas / sufridas (pts)"], ["30.3 / 10.0", "30.3 / 10.0"]);
  assert.deepEqual(por["Objetivos cumplidos / fallidos / pendientes"], ["1 / 0 / 2 (20 pts)", "1 / 0 / 2 (20 pts)"]);
  assert.deepEqual(por["Misiones aéreas cumplidas / abortadas / fallidas"], ["1 / 1 / 0 (de 2)", "1 / 1 / 0 (de 2)"]);
});

test("filasIndicadores tolera un bando ausente", () => {
  const d = datos();
  delete d.bandos.rojo;
  assert.deepEqual(R.filasIndicadores(d)[0], ["Órdenes emitidas / resueltas / rechazadas", "3 / 1 / 2", "-"]);
});

test("filasPuestos omite los puestos sin actividad y muestra los motivos", () => {
  const filas = R.filasPuestos(bando());
  assert.deepEqual(filas, [["A5 · Planificacion", 3, 1, 2, 0, "Objetivo fuera de alcance (2)"]]);
  assert.deepEqual(R.filasPuestos({ puestos: {} }), []);
});

test("observaciones reune las del bando y las de sus puestos sin repetir", () => {
  const b = bando();
  b.puestos.planificacion.observaciones.push(b.observaciones[0]);
  const obs = R.observaciones(b);
  assert.equal(obs.length, 2);
  assert.match(obs[1], /^2 orden\(es\) rechazada\(s\) en A5/);
});

test("resumen describe el escenario", () => {
  assert.equal(R.resumen(datos()), "Prueba · 3 turno(s) resuelto(s) · activo");
  assert.equal(R.resumen({}), " · 0 turno(s) resuelto(s)");
});

test("etiquetaOrigen distingue plantillas del sistema y del instructor", () => {
  assert.equal(P.etiquetaOrigen({ origen: "codigo" }), "Plantilla del sistema");
  assert.equal(P.etiquetaOrigen({ origen: "usuario", guardada_en: "2026-09-30T05:31:16+00:00", con_estado: true }),
    "Guardada por un instructor el 2026-09-30 05:31 · conserva el estado");
  assert.equal(P.etiquetaOrigen({ origen: "usuario", guardada_en: "" }), "Guardada por un instructor");
});

test("emparejar asocia cada <li> con su plantilla por nombre, en orden y sin repetir", () => {
  const ps = [{ id: "a", nombre: "Uno" }, { id: "b", nombre: "Dos" }, { id: "c", nombre: "Dos" }];
  const r = P.emparejar(["Dos", "Uno", "Dos", "Tres"], ps);
  assert.deepEqual(r.map((p) => p && p.id), ["b", "a", "c", null]);
});
