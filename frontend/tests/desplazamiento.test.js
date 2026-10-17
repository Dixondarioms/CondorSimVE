const test = require("node:test");
const assert = require("node:assert");
const Logica = require("../static/js/logica.js");

const previas = new Map([[1, [10, -66]], [2, [10.5, -66.5]], [3, [11, -67]]]);
const unidades = [
  { id: 1, bando: "azul", tipo: "terrestre", estado: "activa", lat: 10.1, lon: -66 },
  { id: 2, bando: "rojo", tipo: "aerea", estado: "activa", lat: 10.5, lon: -66.5 },
  { id: 3, bando: "azul", tipo: "terrestre", estado: "destruida", lat: 11.2, lon: -67 },
  { id: 4, bando: "azul", tipo: "terrestre", estado: "activa", lat: 9, lon: -65 },
];

test("al avanzar el turno se animan solo las unidades que se movieron", () => {
  const movs = Logica.movimientosDelTurno(previas, unidades, { escenario: 5, turno: 3 }, { escenario: 5, turno: 4 });
  assert.deepStrictEqual(movs, [{ id: 1, bando: "azul", tipo: "terrestre", desde: [10, -66], hasta: [10.1, -66] }]);
});

test("no se anima al cambiar de escenario, dentro del mismo turno ni sin estado previo", () => {
  assert.deepStrictEqual(Logica.movimientosDelTurno(previas, unidades, { escenario: 5, turno: 3 }, { escenario: 6, turno: 4 }), []);
  assert.deepStrictEqual(Logica.movimientosDelTurno(previas, unidades, { escenario: 5, turno: 3 }, { escenario: 5, turno: 3 }), []);
  assert.deepStrictEqual(Logica.movimientosDelTurno(previas, unidades, null, { escenario: 5, turno: 4 }), []);
  assert.deepStrictEqual(Logica.movimientosDelTurno(null, unidades, { escenario: 5, turno: 3 }, { escenario: 5, turno: 4 }), []);
});
