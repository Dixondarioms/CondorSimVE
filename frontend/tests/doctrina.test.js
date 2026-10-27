const test = require("node:test");
const assert = require("node:assert");
const Doctrina = require("../static/js/doctrina.js");

test("leer convierte el valor del formulario y '' hereda del bando", () => {
  assert.strictEqual(Doctrina.leer("armas_aire", "restringido"), "restringido");
  assert.strictEqual(Doctrina.leer("disparos_por_blanco", "2"), 2);
  assert.strictEqual(Doctrina.leer("regreso_sin_armas", "false"), false);
  assert.strictEqual(Doctrina.leer("combustible_regreso", ""), null);
});

test("etiqueta da el texto de cada valor", () => {
  assert.strictEqual(Doctrina.etiqueta("armas_superficie", "retenido"), "Solo con orden");
  assert.strictEqual(Doctrina.etiqueta("distancia_pct", 75), "75 % del alcance");
});

test("los campos son los del motor (engine/doctrina.py)", () => {
  assert.deepStrictEqual(Doctrina.CAMPOS.map(([k]) => k),
    ["armas_aire", "armas_superficie", "disparos_por_blanco", "distancia_pct", "combustible_regreso", "regreso_sin_armas"]);
});
