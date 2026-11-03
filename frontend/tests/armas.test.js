const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const cat = {
  cargas: { f16: { aire_aire: { M120: 4, M9X: 2 }, ataque: { BGB: 2, M9X: 2 }, reconocimiento: { M9X: 2 } } },
  nombres_carga: { aire_aire: "Aire-aire", ataque: "Ataque", reconocimiento: "Reconocimiento" },
  armas: {
    M120: { nombre: "AIM-120 AMRAAM", tipo_nombre: "aire-aire", alcance_km: 75, pk: 0.6 },
    M9X: { nombre: "AIM-9X", tipo_nombre: "aire-aire", alcance_km: 25, pk: 0.75 },
    BGB: { nombre: "GBU-10 (láser)", tipo_nombre: "bomba", alcance_km: 12, pk: 0.8 },
  },
};

test("opcionesDeCarga: las cargas del modelo con sus armas por aeronave", () => {
  assert.deepEqual(L.opcionesDeCarga(cat, "f16")[0], ["aire_aire", "Aire-aire: AIM-120 AMRAAM ×4, AIM-9X ×2"]);
  assert.equal(L.opcionesDeCarga(cat, "f16").length, 3);
  assert.deepEqual(L.opcionesDeCarga(cat, "desconocido"), []);
  assert.equal(L.textoCarga(cat, "reconocimiento", {}), "Reconocimiento: sin armas");
});

test("cargaParaRol: la que conviene a cada misión", () => {
  const disp = ["aire_aire", "ataque", "reconocimiento"];
  assert.equal(L.cargaParaRol("CAP", disp), "aire_aire");
  assert.equal(L.cargaParaRol("INTERDICCION", disp), "ataque");
  assert.equal(L.cargaParaRol("SEAD", disp), "aire_aire"); // sin carga SEAD: la primera
  assert.equal(L.cargaParaRol("CAP", []), "");
});

test("detalleArmas: alcance y probabilidad de impacto", () => {
  assert.deepEqual(L.detalleArmas(cat, { M120: 4 }), ["AIM-120 AMRAAM: aire-aire, 75 km, Pk 0,6"]);
});
