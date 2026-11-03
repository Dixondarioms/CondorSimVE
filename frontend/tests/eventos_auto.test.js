const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("textoReglaAuto: cuando … → acciones", () => {
  const r = {
    nombre: "Refuerzos", repetir: false, disparos: 1,
    disparador: { tipo: "entra_area", area_nombre: "Valle", bando: "azul", unidad: "" },
    acciones: [{ tipo: "mensaje", para: "rojo", texto: "Azul en el valle" }, { tipo: "puntos", bando: "rojo", puntos: -5 }],
  };
  assert.equal(L.textoReglaAuto(r),
    "cuando una unidad Azul entra a «Valle» → mensaje a Rojo: «Azul en el valle»; -5 puntos para Rojo (disparada 1 vez)");
  assert.equal(L.textoReglaAuto({ disparador: { tipo: "hora", hora: "07:30" }, repetir: true, acciones: [{ tipo: "pausar" }] }),
    "cuando a las 07:30, cada vez → se pausa el reloj");
  assert.equal(L.textoReglaAuto({ disparador: { tipo: "objetivo", objetivo: "Puente", estado: "fallido" }, acciones: [{ tipo: "clima", clima: "lluvia" }] }),
    "cuando el objetivo «Puente» falla → el clima pasa a lluvia");
});

test("textoAccionAuto: aparecer unidades", () => {
  assert.equal(L.textoAccionAuto({ tipo: "aparecer", cantidad: 2, nombre: "Cía de reserva", clase: "infanteria", bando: "azul" }),
    "aparecen 2 Cía de reserva (Azul)");
});
