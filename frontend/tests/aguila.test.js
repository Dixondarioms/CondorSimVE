// Aguila de la pantalla de acceso (static/js/aguila.js): trayectoria, aleteo y que siempre se entre al simulador.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const Aguila = require("../static/js/aguila.js");

test("el vuelo empieza en su lugar, abre las alas posada y termina grande y transparente sobre la pantalla", () => {
  const c = Aguila.cuadrosVuelo(100, 200);
  assert.strictEqual(c[0].offset, 0);
  assert.strictEqual(c[c.length - 1].offset, 1);
  assert.match(c[0].transform, /translate\(0px, 0px\) scale\(1\)/);
  assert.strictEqual(c[1].transform, c[0].transform);  // mientras abre las alas no se mueve
  assert.ok(Math.abs(c[1].offset - Aguila.DESPLIEGUE_MS / Aguila.VUELO_MS) < 1e-9);
  assert.match(c[c.length - 1].transform, /translate\(100px, 200px\) scale\(9\)/);
  assert.strictEqual(c[c.length - 1].opacity, 0);
  for (let i = 1; i < c.length; i++) assert.ok(c[i].offset > c[i - 1].offset);
});

test("aleteo pausado y simetrico; las alas salen de la posicion recogida de style.css", () => {
  assert.ok(Aguila.VUELO_MS <= 1000);  // un segundo como maximo
  assert.ok(Aguila.ALETEO_MS >= 500);  // aleteo pausado
  const izq = Aguila.cuadrosAleteo(1), der = Aguila.cuadrosAleteo(-1);
  assert.strictEqual(izq.length, der.length);
  assert.match(izq[1].transform, /rotate\(30deg\)/);
  assert.match(der[1].transform, /rotate\(-30deg\)/);
  assert.strictEqual(Aguila.cuadrosDespliegue(1)[0].transform, Aguila.plegada(1));
  const css = fs.readFileSync(path.join(__dirname, "..", "static", "css", "style.css"), "utf8");
  assert.ok(css.includes(`.aguila.plegada .ala-izq { transform: ${Aguila.plegada(1)}; }`));
  assert.ok(css.includes(`.aguila.plegada .ala-der { transform: ${Aguila.plegada(-1)}; }`));
});

test("sin animaciones disponibles se entra igual al simulador", async () => {
  let llamadas = 0;
  await Aguila.despegar(null, () => { llamadas += 1; });
  await Aguila.despegar({}, () => { llamadas += 1; });
  assert.strictEqual(llamadas, 2);
});
