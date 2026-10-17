const test = require("node:test");
const assert = require("node:assert");
const Logica = require("../static/js/logica.js");

test("simbologia segun el estado de la unidad", () => {
  assert.strictEqual(Logica.estadoSimbolo({ fuerza: 20 }), "critico");
  assert.strictEqual(Logica.estadoSimbolo({ fuerza: 55 }), "degradado");
  assert.strictEqual(Logica.estadoSimbolo({ fuerza: 90, tipo: "aerea", combustible: 20, en_tierra: false }), "sin-combustible");
  assert.strictEqual(Logica.estadoSimbolo({ fuerza: 90, tipo: "aerea", combustible: 20, en_tierra: true }), "");
  assert.strictEqual(Logica.estadoSimbolo({ fuerza: null }), "");
});

test("lineas de la tarjeta tactica", () => {
  const caza = { tipo: "aerea", clase: "caza", fuerza: 80, combustible: 60, municion: 40, aeronaves: 4, en_tierra: false,
    perfil_actual: "rasante", mision: "patrulla" };
  assert.deepStrictEqual(Logica.lineasTarjeta(caza, { tipo: "mover" }), [
    "Fuerza 80 %", "Combustible 60 % · Munición 40 %", "4 aeronaves · en vuelo, perfil rasante",
    "Patrulla: intercepta lo que entre a su alcance", "Orden pendiente: mover"]);
  assert.deepStrictEqual(Logica.lineasTarjeta({ ...caza, en_tierra: true, espera_restante: 1, mision: "" }, null).slice(2),
    ["4 aeronaves · en tierra, lista en 1 turno"]);
  assert.deepStrictEqual(Logica.lineasTarjeta({ tipo: "terrestre", fuerza: null, combustible: null }, null), ["Fuerza desconocida (enemigo)"]);
  assert.deepStrictEqual(Logica.lineasTarjeta(null), []);
});
