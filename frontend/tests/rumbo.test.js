const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("rumboObjetivo: virar a un lado o tomar un rumbo, como el control de tránsito aéreo", () => {
  assert.deepEqual(L.rumboObjetivo(80, "virar", 30, "derecha"), { objetivo: 110, lado: "derecha", giro: 30 });
  assert.deepEqual(L.rumboObjetivo(10, "virar", 25, "izquierda"), { objetivo: 345, lado: "izquierda", giro: 25 });
  assert.deepEqual(L.rumboObjetivo(0, "rumbo", 270, "corto"), { objetivo: 270, lado: "izquierda", giro: 90 });
  assert.deepEqual(L.rumboObjetivo(0, "rumbo", 270, "derecha"), { objetivo: 270, lado: "derecha", giro: 270 });
  assert.equal(L.rumboObjetivo(null, "rumbo", 360, "corto").objetivo, 0);
});

test("destinoPorRumbo: 111 km al norte es un grado de latitud; al este, de longitud en el ecuador", () => {
  const [lat, lon] = L.destinoPorRumbo(0, 0, 0, 111.19);
  assert.ok(Math.abs(lat - 1) < 0.01 && Math.abs(lon) < 1e-9);
  const [lat2, lon2] = L.destinoPorRumbo(0, 0, 90, 111.19);
  assert.ok(Math.abs(lat2) < 1e-9 && Math.abs(lon2 - 1) < 0.01);
});

test("textoRumbo: la cola de órdenes muestra la instrucción y el rumbo final", () => {
  assert.equal(L.textoRumbo(JSON.stringify({ modo: "virar", grados: 30, sentido: "derecha", objetivo: 110, lado: "derecha" })),
    "Virar a la derecha 30° (rumbo 110°)");
  assert.equal(L.textoRumbo(JSON.stringify({ modo: "rumbo", grados: 270, sentido: "corto", objetivo: 270, lado: "izquierda" })),
    "Rumbo 270°, virando a la izquierda");
  assert.equal(L.textoRumbo(JSON.stringify({ modo: "rumbo", grados: 90, sentido: "corto" })), "Rumbo 090°");
});
