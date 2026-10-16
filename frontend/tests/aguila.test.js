// Aguila de la pantalla de acceso (static/js/aguila.js): trayectoria, aleteo y que siempre se entre al simulador.
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const Aguila = require("../static/js/aguila.js");

test("el vuelo dura un segundo: abre las alas posada y termina grande y transparente sobre la pantalla", () => {
  assert.ok(Aguila.VUELO_MS <= 1000);
  assert.strictEqual(Aguila.DESPLIEGUE_MS + Aguila.ALETEO_MS, Aguila.VUELO_MS);  // un solo aleteo
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

test("aleteo continuo: cada ciclo cierra en su inicio, las alas son simetricas y la mano va retrasada", () => {
  for (const parte of ["brazo", "mano"]) {
    const izq = Aguila.cicloAleteo(parte, 1), der = Aguila.cicloAleteo(parte, -1);
    assert.strictEqual(izq[0].transform, izq[izq.length - 1].transform);
    assert.strictEqual(izq.length, der.length);
    assert.ok(izq.length >= 12);  // curva bien muestreada
  }
  const arriba = Aguila.pose(0), abajo = Aguila.pose(0.5);
  assert.ok(arriba.brazo > 20 && abajo.brazo < -10);  // sube y baja
  assert.ok(abajo.acorte < arriba.acorte);            // al bajar el ala viene hacia adelante
  // la mano llega abajo despues que el brazo (retraso): a mitad de la bajada todavia esta mas arriba en su ciclo
  assert.ok(Aguila.pose(0.25).mano > 0);
  assert.ok(Aguila.pose(0.25).batida < 0);            // el cuerpo sube mientras las alas bajan
  const b = Aguila.cicloBatida();
  assert.strictEqual(b[0].transform, b[b.length - 1].transform);
});

test("las alas se abren desde la posicion recogida de style.css hasta donde empieza el aleteo", () => {
  for (const s of [1, -1]) {
    const brazo = Aguila.cuadrosDespliegue("brazo", s), mano = Aguila.cuadrosDespliegue("mano", s);
    assert.strictEqual(brazo[0].transform, Aguila.plegada(s));
    assert.strictEqual(brazo[brazo.length - 1].transform, Aguila.cicloAleteo("brazo", s)[0].transform);
    assert.strictEqual(mano[mano.length - 1].transform, Aguila.cicloAleteo("mano", s)[0].transform);
  }
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
