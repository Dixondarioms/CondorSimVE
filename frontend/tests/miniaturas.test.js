const test = require("node:test");
const assert = require("node:assert/strict");
const M = require("../static/js/modelo3d.js");
require("../static/js/miniaturas.js");

const CLASES = ["infanteria", "blindado", "artilleria", "reconocimiento", "antiaerea", "antiaerea_portatil", "artilleria_antiaerea", "ingenieros",
  "transporte", "radar", "guerra_electronica", "caza", "ataque", "helicoptero", "helicoptero_artillado", "avion_ge", "alerta_temprana", "cisterna",
  "dron_reconocimiento", "dron_ataque", "municion_merodeadora", "fragata", "patrullero", "base_aerea", "deposito", "puerto",
  "termoelectrica", "hidroelectrica", "refineria", "centro_comunicaciones", "puente"];

test("todas las clases del catalogo tienen miniatura", () => {
  for (const clase of CLASES) assert.ok(M.mallaPara({ clase }), clase);
  assert.equal(M.mallaPara({ modelo: "uav_reco", clase: "dron_reconocimiento" }), "dron_reconocimiento");
  assert.equal(M.mallaPara({ modelo: "su30", clase: "caza" }), "su30");
});

test("cada miniatura da un SVG valido en cualquier rumbo y lleva el color del bando", () => {
  for (const id of M.MALLAS) {
    for (const rumbo of [0, 37, 90, 200, 315]) {
      const s = M.svg({ modelo: id, rumbo, bando: "rojo", px: 80 });
      assert.match(s, /^<svg /);
      assert.ok(!/NaN|undefined|Infinity/.test(s), `${id} ${rumbo}`);
    }
    assert.notEqual(M.svg({ modelo: id, bando: "azul" }), M.svg({ modelo: id, bando: "rojo" }), id); // deriva, panel, banda o peana
  }
});

test("lo que esta en tierra o en el agua lleva peana y no forma grupos; las instalaciones no giran", () => {
  const tanque = M.marcador({ clase: "blindado", bando: "azul", n: 4, base: 50 });
  assert.equal(tanque.suelo, true);
  assert.match(tanque.html, /<ellipse cx="0" cy="0"/);
  assert.equal(M.gira({ clase: "base_aerea" }), false);
  assert.equal(M.gira({ clase: "fragata" }), true);
  const a = M.svg({ modelo: "base_aerea", rumbo: 25, px: 80 });
  assert.equal(M.marcador({ clase: "base_aerea", rumbo: 200, base: 50 }).html.length > 0, true);
  assert.ok(a.length > 0);
});

test("los buques se dibujan mas grandes que un caza y el personal mas chico", () => {
  const px = (clase) => M.marcador({ clase, rumbo: 0, bando: "azul", base: 50 }).ancho;
  assert.ok(px("fragata") > px("caza"));
  assert.ok(px("infanteria") < px("caza"));
  assert.ok(px("base_aerea") > px("fragata"));
});
