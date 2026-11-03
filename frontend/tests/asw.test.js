const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const cat = { asw: { aviones: ["p3c", "p8a"], helos: ["nh90"], torpedo_km: { submarino: 30, fragata: 10, destructor: 10, aerea: 8 } } };

test("guerra antisubmarina: quién lanza torpedos y a qué distancia", () => {
  assert.equal(L.alcanceTorpedo({ estado: "activa", tipo: "naval", clase: "submarino" }, cat), 30);
  assert.equal(L.alcanceTorpedo({ estado: "activa", tipo: "naval", clase: "patrullero" }, cat), 0);
  assert.equal(L.alcanceTorpedo({ estado: "activa", tipo: "aerea", modelo: "p8a", en_tierra: false }, cat), 8);
  assert.equal(L.alcanceTorpedo({ estado: "activa", tipo: "aerea", modelo: "p8a", en_tierra: true }, cat), 0);
  assert.ok(L.esAvionAsw({ tipo: "aerea", modelo: "p3c" }, cat) && !L.esAvionAsw({ tipo: "aerea", modelo: "f16" }, cat));
  assert.ok(L.esHeloAsw({ tipo: "aerea", modelo: "nh90" }, cat));
});

test("el torpedo solo apunta a buques y submarinos enemigos", () => {
  const unidades = [
    { id: 1, bando: "rojo", tipo: "naval", clase: "fragata", estado: "activa" },
    { id: 2, bando: "rojo", tipo: "aerea", clase: "caza", estado: "activa" },
    { id: 3, bando: "rojo", tipo: "naval", clase: "torpedo", estado: "activa" },
    { id: 4, bando: "azul", tipo: "naval", clase: "submarino", estado: "activa" },
  ];
  assert.deepEqual(L.objetivosDisponibles(unidades, "azul", "torpedo", 4).map((u) => u.id), [1]);
});
