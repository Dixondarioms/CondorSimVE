const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

test("index.html no repite identificadores (getElementById devolveria el primero y el otro control dejaria de andar)", () => {
  const vistos = new Map();
  for (const [, id] of html.matchAll(/\sid="([^"]+)"/g)) vistos.set(id, (vistos.get(id) || 0) + 1);
  const repetidos = [...vistos].filter(([, n]) => n > 1).map(([id]) => id);
  assert.deepEqual(repetidos, []);
});

test("los controles de direccion del ejercicio existen (dia y noche, nivel de la IA, reloj en vivo)", () => {
  for (const id of ["dir-noche", "dir-ia-nivel", "btn-marcha", "reloj-vivo", "dir-cond-azul", "dir-cond-rojo", "pest-pmo", "cal-fecha", "ob-padre", "dlg-tiem", "tiem-docs", "tiem-archivo", "sec-ensayos", "btn-ensayar", "ensayo-volver", "sec-orden-op", "btn-emitir-orden", "sec-supervision", "sup-cuadro", "btn-sup-abrir", "sec-evaluacion", "legajo-word", "legajo-pdf", "mp-tipo-nombre"]) {
    assert.ok(html.includes(`id="${id}"`), id);
  }
});

test("tiempo real: sin LISTO ni resolver turno; el director tiene las tres velocidades", () => {
  for (const id of ["btn-listo", "btn-avanzar", "cfg-limite", "cfg-auto"]) assert.ok(!html.includes(`id="${id}"`), id);
  for (const v of ["1", "10", "60"]) assert.ok(html.includes(`data-vel="${v}"`), v);
});
