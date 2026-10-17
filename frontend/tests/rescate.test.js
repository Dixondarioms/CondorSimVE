const test = require("node:test");
const assert = require("node:assert");
const Logica = require("../static/js/logica.js");

test("texto de las tripulaciones derribadas", () => {
  const d = { tripulantes: 2, grupo: "Halcón", turno: 5, estado: "aislado", medio: "agua", bando: "azul", lat: 10, lon: -66 };
  assert.strictEqual(Logica.textoDerribado(d), "2 tripulantes de Halcón · aislados desde T5 (en el agua)");
  assert.strictEqual(Logica.textoDerribado({ ...d, tripulantes: 1, estado: "rescatado", por: "Rescate 1", turno_fin: 7 }),
    "1 tripulante de Halcón · rescatados por Rescate 1 en T7");
  assert.strictEqual(Logica.textoDerribado({ ...d, estado: "perdido", por: "", turno_fin: 17 }), "2 tripulantes de Halcón · perdidos en T17");
  assert.strictEqual(Logica.textoDerribado(null), "");
});

test("la orbita de rescate va sobre la tripulacion propia mas cercana", () => {
  const lista = [
    { id: 1, estado: "aislado", bando: "azul", lat: 10, lon: -66 },
    { id: 2, estado: "aislado", bando: "rojo", lat: 10.01, lon: -66 },
    { id: 3, estado: "rescatado", bando: "azul", lat: 10.02, lon: -66 },
  ];
  assert.strictEqual(Logica.derribadoCercano(lista, "azul", 10.05, -66).id, 1);
  assert.strictEqual(Logica.derribadoCercano(lista, "azul", 12, -66), null);
  assert.strictEqual(Logica.derribadoCercano(null, "azul", 10, -66), null);
});

test("el PRO opera aeronaves", () => {
  assert.ok(Logica.operaAeronaves({ clase: "punto_recobre" }));
  assert.strictEqual(Logica.plazasDe({ clase: "punto_recobre" }), 4);
});

test("rotulo de un tramo de carretera apto para PRO", () => {
  const p = { id: "Tramo 030", ref: "T-13", nombre: "Carretera Nacional de Los Llanos", largo_m: 10577, ancho_m: 12, pendiente_pct: 0.2 };
  assert.strictEqual(Logica.textoTramoPro(p), "Tramo 030 · T-13 Carretera Nacional de Los Llanos: tramo recto de 10.577 m, ancho 12 m, pendiente 0.2 %");
  assert.ok(Logica.textoTramoPro({ ...p, ref: "", nombre: "" }).startsWith("Tramo 030 · Carretera: "));
});
