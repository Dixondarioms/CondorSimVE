const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("distanciaKm: un grado de latitud son unos 111 km y la distancia a si mismo es 0", () => {
  assert.equal(L.distanciaKm(8, -70, 8, -70), 0);
  assert.ok(Math.abs(L.distanciaKm(8, -70, 9, -70) - 111.19) < 0.1);
  // simetrica y con longitud reducida por el coseno de la latitud
  assert.ok(Math.abs(L.distanciaKm(8.6, -70.6, 8.6, -70.5) - L.distanciaKm(8.6, -70.5, 8.6, -70.6)) < 1e-9);
  assert.ok(Math.abs(L.distanciaKm(8.6, -70.6, 8.6, -70.5) - 11.0) < 0.2);
});

test("etiquetaCanal traduce los canales conocidos y deja pasar los desconocidos", () => {
  assert.equal(L.etiquetaCanal("azul"), "Red azul");
  assert.equal(L.etiquetaCanal("rojo"), "Red roja");
  assert.equal(L.etiquetaCanal("todos"), "Difusión");
  assert.equal(L.etiquetaCanal("mando"), "Al mando");
  assert.equal(L.etiquetaCanal("otro"), "otro");
});

test("canalesDe: el instructor elige bandos, el alumno solo su red o el mando, el observador no escribe", () => {
  assert.deepEqual(L.canalesDe("instructor").map((c) => c[0]), ["todos", "azul", "rojo"]);
  assert.deepEqual(L.canalesDe("azul").map((c) => c[0]), ["bando", "mando"]);
  assert.deepEqual(L.canalesDe("rojo").map((c) => c[0]), ["bando", "mando"]);
  assert.deepEqual(L.canalesDe("observador"), []);
});

test("resumenEntrega describe perdido, con demora o entregado, y tolera entrega vacia", () => {
  const r = L.resumenEntrega({ azul: { perdido: false, demora_ms: 1800 }, rojo: { perdido: true, demora_ms: 0 } });
  assert.equal(r.find((x) => x.lado === "azul").texto, "azul: +1.8 s");
  assert.equal(r.find((x) => x.lado === "rojo").texto, "rojo: perdido");
  assert.equal(r.find((x) => x.lado === "rojo").perdido, true);
  assert.equal(L.resumenEntrega({ azul: { perdido: false, demora_ms: 0 } })[0].texto, "azul: entregado");
  assert.deepEqual(L.resumenEntrega(undefined), []);
});

test("latLngsDe invierte [lon, lat] a [lat, lon] segun el tipo de geometria", () => {
  assert.deepEqual(L.latLngsDe({ type: "Point", coordinates: [-70.5, 8.6] }), [8.6, -70.5]);
  assert.deepEqual(L.latLngsDe({ type: "LineString", coordinates: [[-70, 8], [-71, 9]] }), [[8, -70], [9, -71]]);
  const poligono = { type: "Polygon", coordinates: [[[-70, 8], [-71, 8], [-71, 9], [-70, 8]]] };
  assert.deepEqual(L.latLngsDe(poligono), [[8, -70], [8, -71], [9, -71], [8, -70]]);
  assert.deepEqual(L.latLngsDe({ type: "MultiPoint", coordinates: [] }), []);
});

test("puedeBorrarGrafico: instructor todo; alumno solo los de su bando; observador nada", () => {
  const g = (bando) => ({ id: 1, bando });
  assert.equal(L.puedeBorrarGrafico(g("azul"), "instructor"), true);
  assert.equal(L.puedeBorrarGrafico(g("todos"), "instructor"), true);
  assert.equal(L.puedeBorrarGrafico(g("azul"), "azul"), true);
  assert.equal(L.puedeBorrarGrafico(g("azul"), "rojo"), false);
  assert.equal(L.puedeBorrarGrafico(g("todos"), "azul"), false);
  assert.equal(L.puedeBorrarGrafico(g("azul"), "observador"), false);
});

test("TIPOS_GRAFICO cubre los cuatro trazados con su geometria esperada", () => {
  assert.deepEqual(Object.keys(L.TIPOS_GRAFICO).sort(), ["eje_avance", "linea_fase", "punto_control", "zona_reunion"]);
  assert.equal(L.TIPOS_GRAFICO.zona_reunion.geometria, "Polygon");
  assert.equal(L.TIPOS_GRAFICO.punto_control.geometria, "Point");
});
