const test = require("node:test");
const assert = require("node:assert/strict");
const A = require("../static/js/aerodromos.js");

// pista norte-sur de 3 km y 45 m centrada cerca de Maracay
const pista = { extremos: [[10.17, -67.56], [10.197, -67.56]], largo_m: 3000, ancho_m: 45, ref: "36/18" };

test("puntoEnPista: recorre la pista desde la cabecera A y se corre a estribor", () => {
  const [la0, lo0] = A.puntoEnPista(pista, 0);
  assert.ok(Math.abs(la0 - 10.17) < 1e-9 && Math.abs(lo0 + 67.56) < 1e-9);
  const [la, lo] = A.puntoEnPista(pista, 1500);
  assert.ok(Math.abs(A.distanciaKm(10.17, -67.56, la, lo) - 1.5) < 0.02);
  const [, loE] = A.puntoEnPista(pista, 0, 20); // rumbo norte: estribor es el este
  assert.ok(loE > -67.56);
});

test("sin daño no hay crateres; con mas daño hay mas, y los de antes no se mueven", () => {
  assert.equal(A.crateres([pista], 100, 7).length, 0);
  const pocos = A.crateres([pista], 80, 7);
  const muchos = A.crateres([pista], 20, 7);
  assert.ok(pocos.length > 0 && muchos.length > pocos.length);
  assert.deepEqual(muchos.slice(0, pocos.length), pocos);
  assert.ok(A.cantidadCrateres(0) <= 14);
});

test("los crateres caen sobre la pista (dentro de su largo y su ancho)", () => {
  for (const c of A.crateres([pista], 0, 99)) {
    assert.ok(c.lat > 10.17 && c.lat < 10.197);
    const desvio = A.distanciaKm(c.lat, -67.56, c.lat, c.lon) * 1000;
    assert.ok(desvio <= pista.ancho_m / 2, `desvio ${desvio}`);
    assert.ok(c.radio_m >= 9 && c.radio_m <= 18);
  }
});

test("la numeracion de pista crece con el zoom dentro de un rango legible", () => {
  assert.ok(A.tamNumero(14) < A.tamNumero(16));
  assert.ok(A.tamNumero(10) >= 9 && A.tamNumero(20) <= 34);
});

test("baseQueOcupa: la base_aerea mas cercana a menos de 4 km del aerodromo", () => {
  const aerodromo = { centro: [10.18, -67.56] };
  const unidades = [
    { id: 1, clase: "base_aerea", lat: 10.3, lon: -67.56 },
    { id: 2, clase: "base_aerea", lat: 10.19, lon: -67.56 },
    { id: 3, clase: "infanteria", lat: 10.18, lon: -67.56 },
  ];
  assert.equal(A.baseQueOcupa(aerodromo, unidades).id, 2);
  assert.equal(A.baseQueOcupa(aerodromo, [unidades[0]]), null);
});

test("indexar agrupa las pistas por base y centra el aerodromo en la pista mas larga", () => {
  const geo = {
    bases: [{ icao: "SVBL", nombre: "El Libertador", lat: 10.0, lon: -67.0 }],
    features: [{ type: "Feature", properties: { tipo: "pista", base: "SVBL", ...pista } }, { type: "Feature", properties: { tipo: "marca", base: "SVBL" } }],
  };
  const b = A.indexar(geo).SVBL;
  assert.equal(b.pistas.length, 1);
  assert.ok(Math.abs(b.centro[0] - 10.1835) < 0.001);
});

test("puestos de estacionamiento: dentro de la plataforma, distintos y separados", () => {
  // plataforma rectangular de ~400 x 110 m
  const plat = [[-67.560, 10.180], [-67.5564, 10.180], [-67.5564, 10.181], [-67.560, 10.181], [-67.560, 10.180]];
  const p = A.puestos([plat], 4);
  assert.equal(p.length, 4);
  for (const [lat, lon] of p) assert.ok(lat > 10.18 && lat < 10.181 && lon > -67.56 && lon < -67.5564);
  for (let i = 0; i < p.length; i++) for (let j = i + 1; j < p.length; j++) assert.ok(A.distanciaKm(...p[i], ...p[j]) > 0.05);
  assert.deepEqual(A.puestos([plat], 4), p); // deterministico
  assert.deepEqual(A.puestos([], 3), []);
});
