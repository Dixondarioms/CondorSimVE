// Unidades de medida (aeronauticas para aviacion y defensa aerea, navales, metricas para tierra), convertidor,
// ficha tecnica de las aeronaves y pista de despegue (logica.js).
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("el convertidor pasa entre las unidades de cada magnitud", () => {
  assert.ok(Math.abs(L.convertir("distancia", 1, "nm", "km") - 1.852) < 1e-9);
  assert.ok(Math.abs(L.convertir("velocidad", 900, "kmh", "kt") - 485.96) < 0.01);
  assert.ok(Math.abs(L.convertir("altura", 6000, "m", "ft") - 19685.04) < 0.01);
  assert.ok(Math.abs(L.convertir("altura", 350, "fl", "ft") - 35000) < 1e-6);  // FL350 = 35 000 ft
  assert.ok(Math.abs(L.convertir("masa", 1, "lb", "kg") - 0.45359237) < 1e-9);
  assert.equal(L.convertir("masa", 1, "kg", "km"), null);
});

test("cada fuerza con sus unidades: aviacion y defensa aerea en nudos y millas, tierra en km", () => {
  assert.equal(L.sistemaMedidas({ tipo: "aerea" }), "aeronautico");
  assert.equal(L.sistemaMedidas({ tipo: "terrestre" }, { defensa_aerea: true }), "aeronautico");
  assert.equal(L.sistemaMedidas({ tipo: "terrestre" }, { emisor: true, solo_aereo: true }), "aeronautico");
  assert.equal(L.sistemaMedidas({ tipo: "naval" }), "naval");
  assert.equal(L.sistemaMedidas({ tipo: "terrestre" }, {}), "metrico");
  assert.match(L.medida("aeronautico", "velocidad", 900), /^486 kt \(900 km\/h\)$/);
  assert.match(L.medida("naval", "distancia", 45), /^24,3 NM \(45 km\)$/);
  assert.equal(L.medida("metrico", "distancia", 45), "45 km");
  assert.equal(L.medida("metrico", "velocidad", 30), "30 km/h");
  assert.match(L.medida("aeronautico", "altura", 6000), /^19.685 ft \(6000 m\)$/);
  assert.equal(L.medida("aeronautico", "distancia", null), "?");
});

const FICHA = { roles: ["CAP", "INTERDICCION"], roles_nombres: ["Patrulla aérea de combate", "Interdicción"], crucero_kt: 480,
  max_kt: 1150, radio_nm: 800, techo_ft: 56800, combustible_kg: 9640, consumo_kg_h: 2900, lox_l: 10, lox_l_h: 1,
  despegue_m: 750, aterrizaje_m: 750, tripulacion: 2, autonomia_h: 3.3, lox_horas: 10 };

test("la ficha tecnica se lee en la interfaz", () => {
  const filas = Object.fromEntries(L.filasFicha(FICHA));
  assert.equal(filas.Roles, "Patrulla aérea de combate, Interdicción");
  assert.match(filas["Radio de acción"], /^800 NM \(1482 km\)$/);
  assert.match(filas["Oxígeno líquido"], /^10 l · 1 l\/h \(10 h\)$/);
  assert.match(filas["Despegue / aterrizaje"], /^750 m \(2461 ft\)/);
  assert.equal(Object.fromEntries(L.filasFicha({ ...FICHA, lox_l: 0, lox_l_h: 0 }))["Oxígeno líquido"], "Genera su oxígeno a bordo (OBOGS)");
  assert.equal(Object.fromEntries(L.filasFicha({ ...FICHA, despegue_m: 0, aterrizaje_m: 0 }))["Despegue / aterrizaje"], "Vertical (no necesita pista)");
  assert.deepEqual(L.filasFicha(null), []);
});

test("solo despega donde su carrera entra en la pista util", () => {
  const su30 = { ficha: FICHA };
  assert.equal(L.entraEnPista(su30, { pista_util_m: 3000 }), true);
  assert.equal(L.entraEnPista(su30, { pista_util_m: 600 }), false);
  assert.equal(L.entraEnPista({ ficha: { ...FICHA, despegue_m: 0 } }, { pista_util_m: 100 }), true);  // vertical
  assert.equal(L.entraEnPista(su30, { pista_util_m: null }), true);  // portaaviones: rige lo embarcable
  assert.equal(L.entraEnPista({}, { pista_util_m: 100 }), true);
});
