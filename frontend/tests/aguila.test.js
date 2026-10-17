// Aguila de la pantalla de acceso (static/js/aguila.js): trayectoria, archivos y que siempre se entre al simulador.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const Aguila = require("../static/js/aguila.js");

const ESTATICO = path.join(__dirname, "..", "static");

test("el vuelo es breve: abre las alas en su lugar y termina grande y transparente sobre la pantalla", () => {
  assert.ok(Aguila.VUELO_MS >= 1000 && Aguila.VUELO_MS <= 3000);
  const c = Aguila.cuadrosVuelo(100, 200);
  assert.strictEqual(c[0].offset, 0);
  assert.strictEqual(c[c.length - 1].offset, 1);
  assert.match(c[0].transform, /translate\(0px, 0px\) scale\(1\)/);
  assert.strictEqual(c[1].transform, c[0].transform);  // mientras abre las alas no se mueve
  assert.match(c[c.length - 1].transform, /translate\(100px, 200px\)/);
  assert.strictEqual(c[c.length - 1].opacity, 0);
  for (let i = 1; i < c.length; i++) assert.ok(c[i].offset > c[i - 1].offset);
});

test("la pantalla de acceso usa la imagen posada y el video del vuelo, y la CSP deja cargar el video en memoria", () => {
  const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");
  const img = html.match(/<img class="posada" src="\/static\/([^"]+)"/);
  const video = html.match(/<video class="vuelo" data-src="\/static\/([^"]+)"/);
  assert.ok(img && video);
  assert.ok(fs.existsSync(path.join(ESTATICO, img[1])));
  assert.ok(fs.existsSync(path.join(ESTATICO, video[1])));
  const main = fs.readFileSync(path.join(__dirname, "..", "..", "backend", "app", "main.py"), "utf8");
  assert.match(main, /media-src 'self' blob:/);
});

test("sin animaciones o sin video se entra igual al simulador", async () => {
  let llamadas = 0;
  await Aguila.despegar(null, () => { llamadas += 1; });
  await Aguila.despegar({}, () => { llamadas += 1; });
  assert.strictEqual(llamadas, 2);
  assert.strictEqual(await Aguila.reproducir(null), false);
  assert.strictEqual(await Aguila.preparar(null), false);
});
