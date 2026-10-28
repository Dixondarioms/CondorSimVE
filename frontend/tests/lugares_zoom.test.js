const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("nivelLugar: metropolis, millon, 300 000 y el resto", () => {
  assert.equal(L.nivelLugar(21000000), 1);
  assert.equal(L.nivelLugar(1500000), 2);
  assert.equal(L.nivelLugar(400000), 3);
  assert.equal(L.nivelLugar(30000), 4);
  assert.equal(L.nivelLugar(undefined), 4);
});

test("lugaresOcultos: de lejos solo se ven los puntos de las metropolis y ningun nombre; de cerca, todo", () => {
  assert.deepEqual(L.lugaresOcultos(2), { puntos: [1, 2, 3, 4], nombres: [1, 2, 3, 4] });
  assert.deepEqual(L.lugaresOcultos(4), { puntos: [2, 3, 4], nombres: [1, 2, 3, 4] });
  assert.deepEqual(L.lugaresOcultos(6), { puntos: [4], nombres: [3, 4] });
  assert.deepEqual(L.lugaresOcultos(8), { puntos: [], nombres: [] });
});

test("filtroLugaresRepetidos: la misma ciudad de dos regiones pasa una sola vez; homonimas lejanas, las dos", () => {
  const nuevo = L.filtroLugaresRepetidos();
  assert.equal(nuevo("Caracas", -66.92, 10.5), true);
  assert.equal(nuevo("Caracas", -66.9, 10.49), false);
  assert.equal(nuevo("Valencia", -68.0, 10.17), true);
  assert.equal(nuevo("Valencia", -0.38, 39.47), true);
});
