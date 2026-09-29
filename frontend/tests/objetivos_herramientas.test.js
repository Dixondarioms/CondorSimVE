const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");
const H = require("../static/js/herramientas.js");

const U = (id, nombre, extra = {}) => ({ id, nombre, clase: "infanteria", tipo: "terrestre", modelo: "", ...extra });

test("filtrarUnidades busca por nombre, clase o modelo sin distinguir mayusculas ni acentos", () => {
  const lista = [U(1, "1ra Brigada de Infantería"), U(2, "Halcón 1", { clase: "caza", tipo: "aerea", modelo: "f16" }), U(3, "Artillería A", { clase: "artilleria" })];
  assert.deepEqual(L.filtrarUnidades(lista, "infanteria").map((u) => u.id), [1]);
  assert.deepEqual(L.filtrarUnidades(lista, "HALCON").map((u) => u.id), [2]);
  assert.deepEqual(L.filtrarUnidades(lista, "f16").map((u) => u.id), [2]);
  assert.deepEqual(L.filtrarUnidades(lista, "artiller").map((u) => u.id), [3]);
  assert.deepEqual(L.filtrarUnidades(lista, "aerea").map((u) => u.id), [2]);
  assert.equal(L.filtrarUnidades(lista, "   ").length, 3);
  assert.equal(L.filtrarUnidades(lista, "").length, 3);
  assert.deepEqual(L.filtrarUnidades(lista, "zzz"), []);
});

test("textoObjetivo describe cada tipo con sus puntos", () => {
  assert.equal(L.textoObjetivo({ tipo: "ocupar", radio_km: 5, turnos_requeridos: 1, puntos: 20 }), "Ocupar la zona (radio 5 km) · 20 pts");
  assert.equal(L.textoObjetivo({ tipo: "ocupar", radio_km: 3, turnos_requeridos: 3, puntos: 40 }), "Ocupar la zona (radio 3 km) durante 3 turnos seguidos · 40 pts");
  assert.equal(L.textoObjetivo({ tipo: "destruir", unidad_nombre: "Puesto de mando", puntos: 50 }), "Destruir Puesto de mando · 50 pts");
  assert.equal(L.textoObjetivo({ tipo: "proteger", unidad_nombre: "BA Uno", hasta_turno: 8, puntos: 30 }), "Proteger BA Uno hasta el turno 8 · 30 pts");
  assert.equal(L.textoObjetivo({ tipo: "destruir", unidad_nombre: "", puntos: 5 }), "Destruir la unidad · 5 pts");
});

test("avanceObjetivo: cumplido, fallido y en curso", () => {
  assert.deepEqual(L.avanceObjetivo({ estado: "cumplido", turno_resuelto: 4 }), { texto: "Cumplido (turno 4)", clase: "ok" });
  assert.deepEqual(L.avanceObjetivo({ estado: "fallido", turno_resuelto: 2 }), { texto: "Fallido (turno 2)", clase: "fuego" });
  assert.deepEqual(L.avanceObjetivo({ estado: "pendiente", tipo: "ocupar", progreso: 1, turnos_requeridos: 3 }), { texto: "1/3 turnos", clase: "mov" });
  assert.deepEqual(L.avanceObjetivo({ estado: "pendiente", tipo: "ocupar", progreso: 0, turnos_requeridos: 3 }), { texto: "0/3 turnos", clase: "" });
  assert.deepEqual(L.avanceObjetivo({ estado: "pendiente", tipo: "destruir" }), { texto: "En curso", clase: "" });
});

test("medir: un grado de latitud son unos 111 km hacia el norte y el rumbo es 0", () => {
  const m = H.medir([[8, -70], [9, -70]]);
  assert.equal(m.tramos.length, 1);
  assert.ok(Math.abs(m.total - 111.19) < 0.1);
  assert.ok(Math.abs(m.tramos[0].rumbo - 0) < 0.01);
});

test("medir acumula los tramos y da los rumbos cardinales", () => {
  const m = H.medir([[8, -70], [8, -69], [7, -69], [7, -70]]);
  assert.equal(m.tramos.length, 3);
  assert.ok(Math.abs(m.tramos[0].rumbo - 90) < 0.5); // este
  assert.ok(Math.abs(m.tramos[1].rumbo - 180) < 0.01); // sur
  assert.ok(Math.abs(m.tramos[2].rumbo - 270) < 0.6); // oeste
  assert.ok(Math.abs(m.total - m.tramos.reduce((s, t) => s + t.km, 0)) < 1e-9);
  assert.ok(Math.abs(m.tramos[2].acumulado - m.total) < 1e-9);
  assert.ok(m.tramos[0].acumulado < m.tramos[1].acumulado);
  assert.deepEqual(H.medir([[8, -70]]), { tramos: [], total: 0 });
  assert.deepEqual(H.medir([]), { tramos: [], total: 0 });
});

test("cardinal y textoTramo", () => {
  assert.deepEqual([0, 45, 90, 135, 180, 225, 270, 315, 359].map(H.cardinal), ["N", "NE", "E", "SE", "S", "SO", "O", "NO", "N"]);
  assert.equal(H.textoTramo({ km: 12.345, rumbo: 45 }), "12.3 km · 045° NE");
  assert.equal(H.textoTramo({ km: 100, rumbo: 270.4 }), "100.0 km · 270° O");
  assert.equal(H.textoTramo({ km: 1, rumbo: 5 }), "1.0 km · 005° N");
});

test("la distancia de la regla coincide con la de logica.js", () => {
  const a = [8.6, -70.6], b = [10.05, -69.37];
  assert.ok(Math.abs(H.distanciaKm(a, b) - L.distanciaKm(a[0], a[1], b[0], b[1])) < 1e-9);
});
