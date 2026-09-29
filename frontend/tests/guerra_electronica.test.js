const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const CAT = {
  clases: [{ id: "caza", dron: false }, { id: "dron_reconocimiento", dron: true }],
  modelos: [{ id: "f16", clase: "caza" }, { id: "uav_reco", clase: "dron_reconocimiento" }],
};
const despegue = (modelo, aeronaves) => ({ tipo: "despegar", estado: "pendiente", detalle: JSON.stringify({ modelo, aeronaves }) });

test("los drones se cuentan aparte de las aeronaves tripuladas", () => {
  const U = [
    { bando: "azul", tipo: "aerea", clase: "caza", estado: "activa", aeronaves: 4 },
    { bando: "azul", tipo: "aerea", clase: "dron_reconocimiento", estado: "activa", aeronaves: 2 },
  ];
  const O = [despegue("uav_reco", 3), despegue("f16", 2)];
  assert.equal(L.modeloEsDron("uav_reco", CAT), true);
  assert.equal(L.modeloEsDron("f16", CAT), false);
  assert.equal(L.modeloEsDron("inexistente", CAT), false);
  assert.equal(L.aeronavesComprometidas(U, O, "azul", false, CAT), 6);
  assert.equal(L.aeronavesComprometidas(U, O, "azul", true, CAT), 5);
  assert.equal(L.aeronavesComprometidas(U, O, "azul"), 11); // sin catalogo cuenta todo, como antes
});

test("interferenciasSobre solo cuenta zonas del bando contrario que cubren la unidad", () => {
  const u = { bando: "azul", lat: 0, lon: 0 };
  const zonas = [
    { bando: "rojo", lat: 0.1, lon: 0, radio_km: 25 },
    { bando: "rojo", lat: 1, lon: 0, radio_km: 25 },
    { bando: "azul", lat: 0, lon: 0, radio_km: 25 },
  ];
  assert.equal(L.interferenciasSobre(u, zonas).length, 1);
  assert.deepEqual(L.interferenciasSobre(u, []), []);
  assert.deepEqual(L.interferenciasSobre(u, undefined), []);
});

test("puedeInterferir y el aviso de unidad interferida", () => {
  assert.equal(L.puedeInterferir({ estado: "activa", tipo: "terrestre" }, { interferencia_km: 25 }), true);
  assert.equal(L.puedeInterferir({ estado: "activa", tipo: "aerea", en_tierra: true }, { interferencia_km: 40 }), false);
  assert.equal(L.puedeInterferir({ estado: "activa", tipo: "aerea", en_tierra: false }, { interferencia_km: 40 }), true);
  assert.equal(L.puedeInterferir({ estado: "activa", tipo: "terrestre" }, { interferencia_km: 0 }), false);
  assert.equal(L.puedeInterferir(null, { interferencia_km: 25 }), false);
  const zona = [{ bando: "rojo", lat: 0, lon: 0, radio_km: 10 }];
  const u = { bando: "azul", lat: 0, lon: 0 };
  assert.match(L.textoInterferido(u, { dron: true }, zona), /Sin enlace/);
  assert.match(L.textoInterferido(u, { solo_aereo: true }, zona), /20 %/);
  assert.match(L.textoInterferido(u, { emisor: true }, zona), /60 %/);
  assert.match(L.textoInterferido(u, {}, zona), /30 %/);
  assert.equal(L.textoInterferido({ bando: "rojo", lat: 0, lon: 0 }, {}, zona), "");
});

test("la guerra electronica terrestre la conduce A2 y la aerea A3", () => {
  const ge = { celula: "ge", interferencia_km: 25 };
  assert.equal(L.funcionDeOrden({ tipo: "terrestre" }, "interferir", ge), "guerra_electronica");
  assert.equal(L.funcionDeOrden({ tipo: "aerea" }, "interferir", { interferencia_km: 40 }), "aereo");
  assert.equal(L.puestoPuede("inteligencia", "guerra_electronica"), true);
  assert.equal(L.puestoPuede("planificacion", "guerra_electronica"), false);
  assert.equal(L.puestoPuede("mando", "guerra_electronica"), true);
});
