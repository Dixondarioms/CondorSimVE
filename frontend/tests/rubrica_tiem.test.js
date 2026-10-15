const test = require("node:test");
const assert = require("node:assert/strict");
const R = require("../static/js/rubrica.js");

const ind = (nombre, valor, puntaje) => ({ id: nombre, nombre, valor, puntaje, criterio: "" });

test("filas de la evaluación del TIEM en la rúbrica", () => {
  const rub = { bandos: {
    azul: { tiem: { aplica: true, indicadores: [ind("Documentos del TIEM", "3 aprobado(s)", 40), ind("Oportunidad", "sin hora H", null)],
      nota_automatica: 8.6, nota_instructor: 15, nota: 11.8 } },
    rojo: { tiem: { aplica: false, indicadores: [], nota_automatica: null, nota_instructor: null, nota: null } } } };
  assert.deepEqual(R.filasTiem(rub), [
    ["Documentos del TIEM", "3 aprobado(s) · 40/100", "-"],
    ["Oportunidad", "sin hora H (no aplica)", "-"],
    ["Nota automática", "8.6 / 20", "-"],
    ["Nota del instructor (documentos)", "15 / 20", "-"],
    ["Calificación del trabajo de Estado Mayor", "11.8 / 20", "-"],
  ]);
  assert.deepEqual(R.filasTiem({ bandos: { azul: {}, rojo: {} } }), []);
});
