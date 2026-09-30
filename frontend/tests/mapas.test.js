const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const VEN = { id: "venezuela", nombre: "Venezuela y vecinos", bbox: [-73.5, 0.5, -59.5, 12.5], z: 9, z_min: 5, metros_por_pixel: 304 };
const AME = { id: "america", nombre: "América", bbox: [-170, -56, -30, 72], z: 7, z_min: 3, metros_por_pixel: 1178 };

test("ordenarMapas: de menos a mas detallada, descarta entradas invalidas y sin datos deja Venezuela", () => {
  assert.deepEqual(L.ordenarMapas([VEN, AME]).map((m) => m.id), ["america", "venezuela"]);
  assert.deepEqual(L.ordenarMapas([VEN, { id: "rota" }, null, { id: "sinz", bbox: [0, 0, 1, 1] }]).map((m) => m.id), ["venezuela"]);
  assert.deepEqual(L.ordenarMapas(null).map((m) => m.id), ["venezuela"]);
  assert.deepEqual(L.ordenarMapas([]), [L.MAPA_VENEZUELA]);
  assert.deepEqual(L.MAPA_VENEZUELA.satelite, { z_min: 5, z_max: 12 }); // la foto de Venezuela existe aunque el servidor no responda
});

test("limitesDeMapas abarca todas las regiones, toma el zoom minimo y la principal es la mas detallada", () => {
  const r = L.limitesDeMapas([VEN, AME]);
  assert.deepEqual(r.limites, [[-56, -170], [72, -30]]);
  assert.equal(r.zoomMin, 3);
  assert.equal(r.principal.id, "venezuela");
  const solo = L.limitesDeMapas([VEN]);
  assert.deepEqual(solo.limites, [[0.5, -73.5], [12.5, -59.5]]);
  assert.equal(solo.zoomMin, 5);
  // sin z_min se asume z-4 (nunca menos de 2)
  assert.equal(L.limitesDeMapas([{ id: "x", bbox: [0, 0, 1, 1], z: 4 }]).zoomMin, 2);
});

test("limitesDe y textoMapa", () => {
  assert.deepEqual(L.limitesDe(AME), [[-56, -170], [72, -30]]);
  assert.equal(L.textoMapa(VEN), "Venezuela y vecinos · 304 m/píxel");
  assert.equal(L.textoMapa(AME), "América · 1,2 km/píxel");
  assert.equal(L.textoMapa({ id: "x", nombre: "Recuadro" }), "Recuadro");
});
