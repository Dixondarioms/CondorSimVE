const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("../static/js/pmi.js");

test("textoCoord escribe grados, minutos y segundos con el hemisferio", () => {
  assert.equal(P.textoCoord(8.287169, -62.763154), `08°17'13.8" N 062°45'47.4" O`);
  assert.equal(P.textoCoord(-0.5, 10.25), `00°30'00.0" S 010°15'00.0" E`);
});

test("basesPedibles: las bases enemigas conocidas sin un pedido vigente del bando", () => {
  const bases = [{ id: 1, nombre: "Base Aves" }, { id: 5, nombre: "Base Roques" }];
  const pedidos = [{ bando: "azul", base_id: 5 }, { bando: "rojo", base_id: 1 }];
  assert.deepEqual(P.basesPedibles(bases, "azul", pedidos).map((u) => u.id), [1]);
});
