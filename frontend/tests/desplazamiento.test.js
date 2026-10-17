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
  assert.deepStrictEqual(movs, [{ id: 1, bando: "azul", tipo: "terrestre", desde: [10, -66], hasta: [10.1, -66], ruta: [[10, -66], [10.1, -66]] }]);
});

test("no se anima al cambiar de escenario, dentro del mismo turno ni sin estado previo", () => {
  assert.deepStrictEqual(Logica.movimientosDelTurno(previas, unidades, { escenario: 5, turno: 3 }, { escenario: 6, turno: 4 }), []);
  assert.deepStrictEqual(Logica.movimientosDelTurno(previas, unidades, { escenario: 5, turno: 3 }, { escenario: 5, turno: 3 }), []);
  assert.deepStrictEqual(Logica.movimientosDelTurno(previas, unidades, null, { escenario: 5, turno: 4 }), []);
  assert.deepStrictEqual(Logica.movimientosDelTurno(null, unidades, { escenario: 5, turno: 3 }, { escenario: 5, turno: 4 }), []);
});

test("con el camino del servidor, la animacion sigue la carretera", () => {
  const conCamino = [{ ...unidades[0], recorrido: [[10, -66], [10, -65.95], [10.05, -65.95], [10.1, -66]] }];
  const [m] = Logica.movimientosDelTurno(previas, conCamino, { escenario: 5, turno: 3 }, { escenario: 5, turno: 4 });
  assert.deepStrictEqual(m.ruta, [[10, -66], [10, -65.95], [10.05, -65.95], [10.1, -66]]);
});

test("punto a una fraccion del largo de la ruta", () => {
  const ruta = [[0, 0], [0, 1], [1, 1]];
  assert.deepStrictEqual(Logica.puntoEnRuta(ruta, 0), [0, 0]);
  assert.deepStrictEqual(Logica.puntoEnRuta(ruta, 1), [1, 1]);
  const medio = Logica.puntoEnRuta(ruta, 0.5);  // el codo: la mitad del largo esta en la esquina
  assert.ok(Math.abs(medio[0]) < 0.01 && Math.abs(medio[1] - 1) < 0.01);
  const cuarto = Logica.puntoEnRuta(ruta, 0.25);
  assert.ok(Math.abs(cuarto[0]) < 1e-9 && cuarto[1] > 0.45 && cuarto[1] < 0.55);
  assert.strictEqual(Logica.puntoEnRuta([], 0.5), null);
});
