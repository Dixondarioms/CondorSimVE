const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../static/js/modelo3d.js");

test("urlSprite elige la imagen de 15 grados mas cercana y da la vuelta en 360", () => {
  assert.equal(M.urlSprite("f16", 0), "/static/aeronaves/f16_000.png");
  assert.equal(M.urlSprite("f16", 7), "/static/aeronaves/f16_000.png");
  assert.equal(M.urlSprite("f16", 8), "/static/aeronaves/f16_015.png");
  assert.equal(M.urlSprite("su30", 352), "/static/aeronaves/su30_345.png");
  assert.equal(M.urlSprite("su30", 353), "/static/aeronaves/su30_000.png");
  assert.equal(M.urlSprite("su30", 360), "/static/aeronaves/su30_000.png");
  assert.equal(M.urlSprite("su30", -15), "/static/aeronaves/su30_345.png");
  assert.equal(M.urlSprite("su30", 735), "/static/aeronaves/su30_015.png");
});

test("solo F-16 y Su-30 tienen imagenes reales; el resto usa el respaldo procedural", () => {
  assert.equal(M.tieneSprite("f16"), true);
  assert.equal(M.tieneSprite("su30"), true);
  assert.equal(M.tieneSprite("generico"), false);
  assert.equal(M.tieneSprite(undefined), false);
  assert.equal(M.tieneSprite("toString"), false); // no debe colarse por el prototipo
  const m = M.marcador({ modelo: undefined, clase: "caza", rumbo: 40, bando: "rojo", n: 1, base: 60 });
  assert.match(m.html, /^<svg /);
  const real = M.marcador({ modelo: "f16", rumbo: 40, bando: "azul", n: 1, base: 60 });
  assert.match(real.html, /^<div class="avion3d-grupo azul"/);
  assert.match(real.html, /f16_045\.png/);
});

test("un grupo dibuja tantas imagenes como aviones (hasta 4) en formacion sin coincidir", () => {
  for (const [n, esperadas] of [[1, 1], [2, 2], [3, 3], [4, 4], [8, 4]]) {
    const d = M.disposicion({ modelo: "f16", rumbo: 30, n, base: 100 });
    assert.equal(d.imagenes.length, esperadas, `n=${n}`);
    const puntos = new Set(d.imagenes.map((i) => `${i.x},${i.y}`));
    assert.equal(puntos.size, esperadas, "cada avion en su sitio");
  }
});

test("el cuadro del grupo no cambia con el rumbo y contiene todas las imagenes", () => {
  for (const modelo of ["f16", "su30"]) {
    for (const n of [1, 2, 4]) {
      const lados = new Set();
      for (let r = 0; r < 360; r += 15) {
        const d = M.disposicion({ modelo, rumbo: r, n, base: 90 });
        lados.add(d.ancho);
        for (const i of d.imagenes) {
          assert.ok(i.x >= 0 && i.y >= 0 && i.x + i.lado <= d.ancho + 1 && i.y + i.lado <= d.alto + 1, `${modelo} n=${n} rumbo ${r}`);
        }
      }
      assert.equal(lados.size, 1, `${modelo} n=${n}: el cuadro "respira" al girar`);
    }
  }
});

test("se conserva el tamano relativo: el Su-30 se dibuja mas grande que el F-16 a la misma escala", () => {
  const f16 = M.disposicion({ modelo: "f16", rumbo: 0, n: 1, base: 100 });
  const su30 = M.disposicion({ modelo: "su30", rumbo: 0, n: 1, base: 100 });
  assert.equal(su30.ancho, 100);
  assert.ok(f16.ancho < su30.ancho);
  assert.ok(Math.abs(f16.ancho / su30.ancho - 9.6 / 14) < 0.02);
});

test("en formacion, lo mas al norte se dibuja primero (queda detras)", () => {
  const d = M.disposicion({ modelo: "f16", rumbo: 0, n: 4, base: 100 });
  const ys = d.imagenes.map((i) => i.y);
  assert.deepEqual(ys, [...ys].sort((a, b) => a - b)); // rumbo norte: el lider (arriba) primero
});

test("rumbo() da 0 al norte, 90 al este, 180 al sur y 270 al oeste", () => {
  assert.ok(Math.abs(M.rumbo(8, -70, 9, -70) - 0) < 0.01);
  assert.ok(Math.abs(M.rumbo(8, -70, 8, -69) - 90) < 0.5);
  assert.ok(Math.abs(M.rumbo(8, -70, 7, -70) - 180) < 0.01);
  assert.ok(Math.abs(M.rumbo(8, -70, 8, -71) - 270) < 0.5);
  assert.ok(Math.abs(M.rumbo(0, 0, 1, 1) - 45) < 0.5);
});

test("mallaPara: modelo propio, caza generico para cazas sin modelo y nada para el resto", () => {
  assert.equal(M.mallaPara({ modelo: "su30", clase: "caza" }), "su30");
  assert.equal(M.mallaPara({ modelo: null, clase: "caza" }), "generico");
  assert.equal(M.mallaPara({ modelo: "", clase: "ataque" }), "generico");
  assert.equal(M.mallaPara({ modelo: "", clase: "helicoptero" }), null);
  assert.equal(M.mallaPara({ modelo: "", clase: "infanteria" }), null);
  assert.equal(M.mallaPara(null), null);
});

test("respaldo procedural: SVG valido, sin NaN y con el color del bando en la deriva", () => {
  for (const modelo of ["f16", "su30", "generico"]) {
    for (const rumbo of [0, 45, 90, 135, 180, 225, 270, 315]) {
      const s = M.svg({ modelo, rumbo, bando: "azul", n: 2, px: 60 });
      assert.match(s, /^<svg [^>]*viewBox="[^"]+"/);
      assert.ok(!/NaN|undefined|Infinity/.test(s), `${modelo} ${rumbo}`);
      const p = M.proyectar({ modelo, rumbo, bando: "azul", n: 2 });
      assert.ok(p.caras.length > 20);
      const h = M.semilado(modelo, 2);
      for (const c of p.caras) for (const [x, y] of c.puntos) assert.ok(Math.abs(x) <= h && Math.abs(y) <= h, `${modelo} ${rumbo} fuera del cuadro`);
    }
  }
  const azul = M.proyectar({ modelo: "f16", rumbo: 90, bando: "azul" }).caras.some((c) => c.relleno[2] > c.relleno[0] + 40);
  const rojo = M.proyectar({ modelo: "f16", rumbo: 90, bando: "rojo" }).caras.some((c) => c.relleno[0] > c.relleno[2] + 40);
  assert.ok(azul && rojo);
});

test("proyectar es determinista y depende del rumbo", () => {
  const a = JSON.stringify(M.proyectar({ modelo: "su30", rumbo: 30 }).caras);
  assert.equal(a, JSON.stringify(M.proyectar({ modelo: "su30", rumbo: 30 }).caras));
  assert.notEqual(a, JSON.stringify(M.proyectar({ modelo: "su30", rumbo: 120 }).caras));
});
