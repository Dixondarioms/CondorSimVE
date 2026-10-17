// Parte de personal por unidad (plantilla, reservas y milicia) y esfuerzo aereo en la pestaña Situación.
const test = require("node:test");
const assert = require("node:assert/strict");
const S = require("../static/js/situacion.js");

const cat = (autorizado, existente, reserva = 0, milicia = 0) => ({ autorizado, existente, reserva, milicia, deficit: autorizado - existente - reserva - milicia });
const PARTE = {
  config: { cobertura: 50, tripulaciones: 3, reserva: 5, milicia: 100 }, reserva_restante: 0, milicia_restante: 94,
  unidades: [{ nombre: "Halcón", categorias: { pilotos: cat(12, 6, 5), tecnicos: cat(28, 14), oficiales: cat(2, 1), tropa: cat(12, 6, 0, 6) } }],
  total: { pilotos: cat(12, 6, 5), tecnicos: cat(28, 14), oficiales: cat(2, 1), tropa: cat(12, 6, 0, 6) },
};

test("cada celda dice lo existente, lo que cubren reservas y milicia, la plantilla y lo que falta", () => {
  assert.equal(S.celdaParte(cat(12, 6, 5)), "6 + 5 res. / 12 · faltan 1");
  assert.equal(S.celdaParte(cat(12, 6, 0, 6)), "6 + 6 mil. / 12");
  assert.equal(S.celdaParte(cat(0, 0)), "—");
  const filas = S.filasParte(PARTE);
  assert.equal(filas.length, 2);
  assert.equal(filas[1].total, true);
  assert.equal(filas[0].deficit, 1 + 14 + 1);
  assert.match(S.textoConfigPersonal(PARTE), /Plantilla al 50 %, 3 tripulaciones por aeronave.*milicianos sin asignar: 94 de 100/);
});

test("el esfuerzo aereo muestra salidas, horas, perdidas y atricion", () => {
  const l = Object.fromEntries(S.lineasEsfuerzo({ salidas: 20, horas: 35.5, perdidas: 2, atricion_pct: 10, salidas_por_aeronave_dia: 1.5,
    no_disponibles: 3, abortos: 1, fallas: true }));
  assert.equal(l["Atrición (pérdidas cada 100 salidas)"], "10 %");
  assert.equal(l["Horas de vuelo"], "35,5");
  assert.equal(l["Abortos por falla en vuelo"], "1");
  const sin = Object.fromEntries(S.lineasEsfuerzo({ salidas: 0, horas: 0, perdidas: 0, atricion_pct: 0, fallas: false }));
  assert.match(sin["Abortos por falla en vuelo"], /desactivadas/);
});
