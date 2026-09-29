const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const base = (extra) => ({ id: 1, nombre: "BA Uno", bando: "azul", tipo: "base", clase: "base_aerea", estado: "activa", fuerza: 100, lat: 10, lon: -67, ...extra });
const caza = (extra) => ({
  id: 10, nombre: "C1", bando: "azul", tipo: "aerea", clase: "caza", estado: "activa", fuerza: 100, lat: 10, lon: -66, velocidad_kmh: 900,
  autonomia_km: 1800, combustible: 80, aeronaves: 4, en_tierra: false, base_id: null, espera_restante: 0, mision: "", ...extra,
});

test("estadoUnidad: en tierra (esperando o lista), patrullando y ordenes de vuelo", () => {
  assert.deepEqual(L.estadoUnidad(caza({ en_tierra: true, espera_restante: 2 })), { texto: "En base · 2 t", clase: "mov" });
  assert.deepEqual(L.estadoUnidad(caza({ en_tierra: true, espera_restante: 0 })), { texto: "En base · lista", clase: "ok" });
  assert.deepEqual(L.estadoUnidad(caza({ mision: "patrulla", mision_lat: 9, mision_lon: -66 })), { texto: "Patrullando", clase: "mov" });
  assert.equal(L.estadoUnidad(caza(), [{ unidad_id: 10, tipo: "aterrizar" }]).texto, "Orden: aterrizar");
  assert.equal(L.estadoUnidad(caza(), [{ unidad_id: 10, tipo: "patrullar" }]).texto, "Orden: patrullar");
  assert.equal(L.estadoUnidad(caza()).texto, "Operativa");
});

test("plazasLibres descuenta las aeronaves estacionadas en esa base y solo en ella", () => {
  const b = base();
  const otras = base({ id: 2, nombre: "Otra" });
  const unidades = [
    b, otras,
    caza({ id: 11, en_tierra: true, base_id: 1, aeronaves: 4 }), caza({ id: 12, en_tierra: true, base_id: 1, aeronaves: 2 }),
    caza({ id: 13, en_tierra: true, base_id: 2, aeronaves: 8 }), caza({ id: 14, en_tierra: true, base_id: 1, aeronaves: 4, estado: "destruida" }),
    caza({ id: 15, en_tierra: false, base_id: null, aeronaves: 8 }),
  ];
  assert.equal(L.plazasLibres(b, unidades), L.CAPACIDAD_BASE - 6);
  assert.equal(L.plazasLibres(otras, unidades), L.CAPACIDAD_BASE - 8);
});

test("opcionesDeAterrizaje: solo bases propias con plazas, ordenadas por distancia, con llegada y combustible", () => {
  const cerca = base({ id: 1, nombre: "Cerca", lat: 10, lon: -66.5 }); // ~55 km
  const lejos = base({ id: 2, nombre: "Lejos", lat: 10, lon: -63 }); // ~330 km
  const llena = base({ id: 3, nombre: "Llena", lat: 10, lon: -66.9 });
  const enemiga = base({ id: 4, nombre: "Roja", bando: "rojo", lat: 10, lon: -66.1 });
  const dañada = base({ id: 5, nombre: "Dañada", fuerza: 10, lat: 10, lon: -66.2 });
  const u = caza({ velocidad_kmh: 100, combustible: 5 }); // 1 turno = 100 km; 5 % de 1800 km = 90 km
  const unidades = [
    u, cerca, lejos, llena, enemiga, dañada,
    caza({ id: 20, en_tierra: true, base_id: 3, aeronaves: 8 }), caza({ id: 21, en_tierra: true, base_id: 3, aeronaves: 4 }),
  ];
  const o = L.opcionesDeAterrizaje(u, unidades);
  assert.deepEqual(o.map((x) => x.base.nombre), ["Cerca", "Lejos"]);
  assert.equal(o[0].llegaEsteTurno, true);
  assert.equal(o[0].turnos, 1);
  assert.equal(o[1].llegaEsteTurno, false);
  assert.equal(o[1].turnos, 4);
  assert.equal(o[0].alcanzaCombustible, true); // 55 km necesitan ~3 %
  assert.equal(o[1].alcanzaCombustible, false); // 330 km necesitan ~18 % y solo hay 5 %
  assert.ok(Math.abs(o[0].combustibleNecesario - (o[0].km / 1800) * 100) < 1e-9);
  // un grupo mas grande ya no cabe en la base casi llena
  const grande = caza({ id: 30, aeronaves: 8 });
  assert.ok(!L.opcionesDeAterrizaje(grande, [grande, llena, caza({ id: 31, en_tierra: true, base_id: 3, aeronaves: 8 })]).length);
});

test("situacionDeVuelo describe el vuelo, la espera en tierra y la patrulla; null si no es una aeronave activa", () => {
  const b = base();
  assert.equal(L.situacionDeVuelo(caza(), [b]), "En vuelo");
  assert.equal(L.situacionDeVuelo(caza({ en_tierra: true, base_id: 1, espera_restante: 2 }), [b]), "En tierra en BA Uno: reabasteciendo y rearmando, lista en 2 turnos");
  assert.equal(L.situacionDeVuelo(caza({ en_tierra: true, base_id: 1, espera_restante: 1 }), [b]), "En tierra en BA Uno: reabasteciendo y rearmando, lista en 1 turno");
  assert.equal(L.situacionDeVuelo(caza({ en_tierra: true, base_id: 1, espera_restante: 0 }), [b]), "En tierra en BA Uno: lista para despegar");
  assert.equal(L.situacionDeVuelo(caza({ mision: "patrulla", mision_lat: 9.5, mision_lon: -66.25 }), [b]), "Patrullando sobre 9.50, -66.25");
  // enemigo detectado: se ve si esta en tierra, no cuanto le falta
  assert.equal(L.situacionDeVuelo(caza({ en_tierra: true, base_id: null, espera_restante: null }), [b]), "En tierra");
  assert.equal(L.situacionDeVuelo(base(), [b]), null);
  assert.equal(L.situacionDeVuelo(caza({ estado: "destruida" }), [b]), null);
});
