const test = require("node:test");
const assert = require("node:assert");
const Logica = require("../static/js/logica.js");

const CAT = {
  armamento: { MAA: { nombre: "RVV-AE", tipo: "aa" }, MA1: { nombre: "Kh-29L", tipo: "as" }, BKR: { nombre: "KAB-500KR", tipo: "bomba" },
    M120: { nombre: "AIM-120", tipo: "aa" }, BBU: { nombre: "GBU-12", tipo: "bomba" } },
  por_modelo: { su30: ["MAA", "MA1", "BKR"] },
};

test("el armamento primario sirve al rol y es el de la aeronave", () => {
  assert.deepStrictEqual(Logica.armasParaRol(CAT, "su30", "CAP").map(([c]) => c), ["MAA"]);
  assert.deepStrictEqual(Logica.armasParaRol(CAT, "su30", "INTERDICCION").map(([c]) => c), ["MA1", "BKR"]);
  assert.deepStrictEqual(Logica.armasParaRol(CAT, "su30", "CAP", false).map(([c]) => c), ["MAA", "MA1", "BKR"]);
  assert.strictEqual(Logica.armasParaRol(CAT, "su30", "CAP")[0][1], "MAA · RVV-AE");
  assert.deepStrictEqual(Logica.armasParaRol(CAT, "otro", "INTERDICCION").map(([c]) => c), ["BBU"]);
  assert.deepStrictEqual(Logica.armasParaRol(null, "su30", "CAP"), []);
});

test("tramo y paquete de la OTA", () => {
  assert.strictEqual(Logica.textoTramo({ rumbo: 45, nm: 54, altitud_ft: 5000 }), "045° · 54 NM · 5000 ft");
  assert.strictEqual(Logica.textoTramo({ rumbo: 270, nm: 3.2, altitud_ft: null }), "270° · 3.2 NM");
  assert.strictEqual(Logica.textoTramo(null), "");
  assert.strictEqual(Logica.textoPaquete({ ota: { paquete: "TELA", funcion: "CM" } }), "paq. TELA (CM)");
  assert.strictEqual(Logica.textoPaquete({ ota: { paquete: "TELA", funcion: "-" } }), "paq. TELA");
  assert.strictEqual(Logica.textoPaquete({ ota: {} }), "");
});
