const test = require("node:test");
const assert = require("node:assert");
const Logica = require("../static/js/logica.js");

test("texto del calculo de armamento", () => {
  const w = { blanco_nombre: "Piezas antiaéreas", criterio_nombre: "Neutraliza el poder de fuego", angulo: 45, impactos: 8, arma: "BMK",
    dmpi: 4, lanzar: 24, guiada: false, aeronaves_necesarias: 4, por_aeronave: 6, lleva: 12, suficiente: false, radio_escombros_m: 240 };
  assert.strictEqual(Logica.textoWeaponeering(w),
    "Cálculo de armamento (piezas antiaéreas, «neutraliza el poder de fuego», 45°): 8 BMK en el blanco (4 DMPI) y 24 a lanzar "
    + "(×3 por la dispersión): 4 aeronaves de 6; el grupo lleva 12 (no alcanza). Radio de escombros 240 m.");
  assert.strictEqual(Logica.textoWeaponeering(null), "");
});

test("fila de los anillos de Warden", () => {
  assert.deepStrictEqual(Logica.filaWarden({ nombre: "Anillo 2", objetivos: 3, degradados: 0, neutralizados: 2, destruidos: 1, sin_noticias: 0, ejemplos: ["Refinería", "Central"] }),
    ["Anillo 2", "3", "2 neutralizados · 1 destruido", "Refinería, Central"]);
  assert.deepStrictEqual(Logica.filaWarden({ nombre: "Anillo 1", objetivos: 0, degradados: 0, neutralizados: 0, destruidos: 0, sin_noticias: 0, ejemplos: [] }),
    ["Anillo 1", "0", "—", ""]);
  assert.strictEqual(Logica.filaWarden({ nombre: "A", objetivos: 2, degradados: 0, neutralizados: 0, destruidos: 0, sin_noticias: 2 })[2], "2 sin noticias");
});
