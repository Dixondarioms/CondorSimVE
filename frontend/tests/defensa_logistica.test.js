const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("deteccionEfectiva: un radar apagado solo ve a ojo", () => {
  const radar = { emisor: true };
  assert.equal(L.deteccionEfectiva({ deteccion_km: 150, emitiendo: true }, radar), 150);
  assert.equal(L.deteccionEfectiva({ deteccion_km: 150, emitiendo: false }, radar), L.RADIO_SIN_EMISION_KM);
  assert.equal(L.deteccionEfectiva({ deteccion_km: 16, emitiendo: false }, { emisor: false }), 16);
  assert.equal(L.deteccionEfectiva({ deteccion_km: 3, emitiendo: false }, radar), 3);
  assert.equal(L.deteccionEfectiva({ deteccion_km: 20 }, null), 20);
});

test("pctStock expresa las existencias respecto del maximo de la base", () => {
  assert.equal(L.pctStock(1000, { stock_max: 2000 }), 50);
  assert.equal(L.pctStock(0, { stock_max: 2000 }), 0);
  assert.equal(L.pctStock(5000, { stock_max: 2000 }), 100);
  assert.equal(L.pctStock(null, { stock_max: 2000 }), null); // base enemiga: oculto
  assert.equal(L.pctStock(100, { stock_max: 0 }), null);
});

test("estadoUnidad avisa radar apagado, fuego retenido y base sin existencias", () => {
  const u = (x) => ({ id: 1, estado: "activa", fuerza: 100, combustible: 100, municion: 100, tipo: "terrestre", ...x });
  assert.equal(L.estadoUnidad(u({ emitiendo: false })).texto, "Radar apagado");
  assert.equal(L.estadoUnidad(u({ fuego_libre: false })).texto, "Fuego retenido");
  assert.equal(L.estadoUnidad(u({ tipo: "base", stock_combustible: 0, stock_municion: 500 })).texto, "Base sin existencias");
  assert.equal(L.estadoUnidad(u({ tipo: "base", stock_combustible: 400, stock_municion: 500 })).texto, "Base operativa");
  assert.equal(L.estadoUnidad(u({ tipo: "base", stock_combustible: null, stock_municion: null })).texto, "Base operativa");
});
