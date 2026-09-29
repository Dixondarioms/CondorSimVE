const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

test("horaEstimada suma minutos al inicio del turno y marca el cambio de dia", () => {
  assert.equal(L.horaEstimada(360, 1, 0), "06:00");
  assert.equal(L.horaEstimada(360, 3, 0.5), "08:30");
  assert.equal(L.horaEstimada(1380, 2, 0.25), "00:15 (+1d)");
  assert.equal(L.horaEstimada(undefined, 1, 0), "06:00");
});

test("misionActiva y textoMision resumen el estado", () => {
  const base = { puntos: [{ tipo: "orbita" }, { tipo: "aterrizaje" }], turno_despegue: 4 };
  assert.equal(L.misionActiva({ estado: "programada" }), true);
  assert.equal(L.misionActiva({ estado: "cumplida" }), false);
  assert.equal(L.textoMision({ ...base, estado: "programada", unidad_id: null }), "Despega en el turno 4");
  assert.equal(L.textoMision({ ...base, estado: "programada", unidad_id: 7 }), "Se inicia al resolver el turno");
  assert.equal(L.textoMision({ ...base, estado: "en_curso", indice: 0, espera: 2 }), "Punto 1/2: Órbita (en órbita, 2 turnos más)");
  assert.equal(L.textoMision({ ...base, estado: "en_curso", indice: 1, espera: -1 }), "Punto 2/2: Aterrizaje");
  assert.equal(L.textoMision({ ...base, estado: "cumplida", resultado: "Mision cumplida: aterrizo en BA." }), "Mision cumplida: aterrizo en BA.");
});

test("tramosCronograma arma vuelo, orbita, ataque y aterrizaje a partir del plan", () => {
  const m = {
    turno_despegue: 3,
    puntos: [{ tipo: "orbita" }, { tipo: "blanco" }, { tipo: "aterrizaje" }],
    plan: { puntos: [
      { tipo: "orbita", llegada_h: 0.5, salida_h: 3 },
      { tipo: "blanco", llegada_h: 3.4, salida_h: 4 },
      { tipo: "aterrizaje", llegada_h: 4.6 },
    ] },
  };
  const t = L.tramosCronograma(m);
  assert.equal(t.inicio, 2);
  assert.equal(t.fin, 6.6);
  assert.deepEqual(t.segmentos, [
    { desde: 2, hasta: 2.5, tipo: "vuelo" }, { desde: 2.5, hasta: 5, tipo: "orbita" },
    { desde: 5, hasta: 5.4, tipo: "vuelo" }, { desde: 6, hasta: 6.6, tipo: "vuelo" },
  ]);
  assert.deepEqual(t.marcas, [{ h: 5.4, tipo: "blanco" }, { h: 6.6, tipo: "aterrizaje" }]);
  assert.deepEqual(L.tramosCronograma({ turno_despegue: 1, plan: {} }), { inicio: 0, fin: 0, segmentos: [], marcas: [] });
});
