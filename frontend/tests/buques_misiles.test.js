const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const pa = { id: 1, clase: "portaaviones", tipo: "naval", bando: "azul", estado: "activa", fuerza: 100, lat: 0, lon: 0 };
const ba = { id: 2, clase: "base_aerea", tipo: "base", bando: "azul", estado: "activa", fuerza: 100, lat: 0, lon: 1 };

test("portaaviones y base aerea operan aeronaves; solo las embarcables usan el portaaviones", () => {
  assert.ok(L.operaAeronaves(pa) && L.operaAeronaves(ba) && !L.operaAeronaves({ clase: "fragata" }));
  assert.ok(L.esPortaaviones(pa) && !L.esPortaaviones(ba));
  assert.equal(L.plazasDe(pa), 10);
  const helo = { clase: "helicoptero", modelo: "" }, f16 = { clase: "caza", modelo: "f16" }, emb = { clase: "caza", modelo: "caza_embarcado" };
  assert.ok(L.puedeOperarEn(helo, pa) && L.puedeOperarEn(emb, pa) && !L.puedeOperarEn(f16, pa) && L.puedeOperarEn(f16, ba));
  assert.ok(!L.puedeOperarEn({ clase: "misil_crucero" }, ba));
  assert.ok(L.modeloDespegaDe({ embarcable: true }, pa) && !L.modeloDespegaDe({ embarcable: false }, pa));
  assert.ok(!L.modeloDespegaDe({ misil: true }, ba) && L.modeloDespegaDe({ embarcable: false }, ba));
});

test("las bases propias incluyen al portaaviones y el aterrizaje respeta lo embarcable", () => {
  const unidades = [pa, ba];
  assert.deepEqual(L.basesAereasPropias(unidades, "azul").map((b) => b.id), [1, 2]);
  const f16 = { id: 3, clase: "caza", modelo: "f16", tipo: "aerea", bando: "azul", lat: 0, lon: 0.5, velocidad_kmh: 900, combustible: 80, aeronaves: 2 };
  assert.deepEqual(L.opcionesDeAterrizaje(f16, unidades).map((o) => o.base.id), [2]);
  const helo = { ...f16, id: 4, clase: "helicoptero", modelo: "" };
  assert.deepEqual(L.opcionesDeAterrizaje(helo, unidades).map((o) => o.base.id), [1, 2]);
});

test("misiles: quien lanza, cuantos, blancos validos y texto de la salva", () => {
  assert.ok(L.puedeLanzarMisiles({ clase: "fragata", estado: "activa" }) && !L.puedeLanzarMisiles({ clase: "patrullero", estado: "activa" }));
  assert.ok(L.puedeLanzarMisiles({ clase: "x", estado: "activa" }, { lanza_misiles: true }));
  assert.equal(L.misilesDisponibles({ municion: 75 }), 3);
  assert.equal(L.misilesDisponibles({ municion: 100 }), 4);
  assert.equal(L.misilesDisponibles({ municion: 20 }), 0);
  const unidades = [
    { id: 1, bando: "rojo", estado: "activa", tipo: "naval" }, { id: 2, bando: "rojo", estado: "activa", tipo: "aerea", en_tierra: false },
    { id: 3, bando: "rojo", estado: "activa", tipo: "aerea", en_tierra: true }, { id: 4, bando: "azul", estado: "activa", tipo: "naval" },
  ];
  assert.deepEqual(L.objetivosDisponibles(unidades, "azul", "lanzar").map((u) => u.id), [1, 3]);
  const salva = { id: 9, clase: "misil_crucero", estado: "activa", aeronaves: 2, blanco_id: 1, bando: "azul" };
  assert.equal(L.textoMisil(salva, [{ id: 1, nombre: "Fragata Roja" }]), "2 misiles en vuelo hacia Fragata Roja");
  assert.equal(L.estadoUnidad(salva).texto, "Misil en vuelo");
  assert.ok(!L.unidadesConOrdenes([salva], "azul").length);
  assert.equal(L.ramaDe({ clase: "destructor", tipo: "naval" }), "naval");
});
