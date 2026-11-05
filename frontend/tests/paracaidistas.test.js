const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const U = (id, extra = {}) => ({ id, bando: "azul", tipo: "terrestre", estado: "activa", lat: 0, lon: 0, ...extra });

test("el avion de transporte lleva segun su modelo y embarca solo en tierra", () => {
  const c130 = U(1, { tipo: "aerea", clase: "avion_transporte", modelo: "c130h", en_tierra: true });
  const il76 = U(2, { tipo: "aerea", clase: "avion_transporte", modelo: "il76md", aeronaves: 2 });
  assert.equal(L.capacidadTransporte(c130), 2);
  assert.equal(L.capacidadTransporte(il76), 6);
  const para = U(3, { clase: "paracaidistas" });
  const tanque = U(4, { clase: "blindado" });
  const claseDe = (u) => ({ movilidad: u.clase === "blindado" ? "oruga" : "ligera" });
  assert.deepEqual(L.transportesCercanos(para, [c130, para], claseDe).map((x) => x.t.id), [1]);
  assert.equal(L.transportesCercanos(tanque, [c130, tanque], claseDe).length, 0);
  c130.en_tierra = false;
  assert.equal(L.transportesCercanos(para, [c130, para], claseDe).length, 0);
});

test("lanza paracaidistas en vuelo y desembarca en tierra", () => {
  const avion = U(1, { tipo: "aerea", clase: "avion_transporte", en_tierra: false });
  const para = U(2, { clase: "paracaidistas", transporte_id: 1 });
  const inf = U(3, { clase: "infanteria", transporte_id: 1 });
  assert.ok(L.puedeLanzarParacaidistas(avion, [avion, para, inf]));
  assert.ok(!L.puedeLanzarParacaidistas(avion, [avion, inf]));
  assert.deepEqual(L.paracaidistasABordo(avion, [avion, para, inf]).map((x) => x.id), [2]);
  assert.ok(!L.puedeDesembarcar(avion, [avion, inf]));
  avion.en_tierra = true;
  assert.ok(L.puedeDesembarcar(avion, [avion, inf]));
  const lst = U(5, { tipo: "naval", clase: "buque_desembarco" });
  assert.ok(L.puedeDesembarcar(lst, [lst, U(6, { transporte_id: 5 })]) && !L.puedeLanzarParacaidistas(lst, [lst]));
});
