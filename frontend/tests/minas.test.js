const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const cat = { minas: { navales: ["patrullero", "fragata", "submarino", "buque_desembarco"], aereos: ["ataque"] } };

test("quién siembra y quién barre minas", () => {
  assert.ok(L.siembraMinas({ estado: "activa", tipo: "naval", clase: "fragata" }, cat));
  assert.ok(!L.siembraMinas({ estado: "activa", tipo: "naval", clase: "destructor" }, cat));
  assert.ok(L.siembraMinas({ estado: "activa", tipo: "aerea", clase: "ataque" }, cat));
  assert.ok(!L.siembraMinas({ estado: "destruida", tipo: "naval", clase: "fragata" }, cat));
  assert.ok(L.barreMinas({ estado: "activa", clase: "cazaminas" }) && !L.barreMinas({ estado: "activa", clase: "fragata" }));
});
