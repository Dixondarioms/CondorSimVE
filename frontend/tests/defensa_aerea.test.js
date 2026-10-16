// Ficha de los sistemas de defensa aerea (Logica.resumenSistemaDA): armas con lo listo y en reserva, radares,
// tiempos, vehiculos y el arma elegida por el operador.
const test = require("node:test");
const assert = require("node:assert/strict");
const L = require("../static/js/logica.js");

const BUK = {
  modelo: "buk_m2e", radar_vigilancia_km: 160, radar_tiro_km: 45, reaccion_s: 12, canales: 8, despliegue_min: 5,
  repliegue_min: 5, movilidad: "Autopropulsada sobre orugas (pesada)", personal: 30, nota: "Nota.", total_vehiculos: 3,
  vehiculos: [{ cantidad: 2, descripcion: "TELAR 9A317E" }, { cantidad: 1, descripcion: "TEL 9A316E" }],
  armas: [
    { id: "9m317e", nombre: "9M317E (largo alcance)", tipo: "misil_radar", tipo_nombre: "Misil guiado por radar", categoria: "largo",
      alcance_min_km: 3, alcance_max_km: 45, altura_min_m: 15, altura_max_m: 25000, pk: 0.75, por_blanco: 2, cargados: 12, reserva: 8, recarga_min: 13 },
    { id: "igla_s", nombre: "Igla-S (defensa cercana)", tipo: "misil_ir", tipo_nombre: "Misil infrarrojo", categoria: "corto",
      alcance_min_km: 0.5, alcance_max_km: 6, altura_min_m: 10, altura_max_m: 3500, pk: 0.4, por_blanco: 1, cargados: 4, reserva: 8, recarga_min: 1 },
  ],
};

test("resume las armas con lo listo, la reserva y el arma elegida", () => {
  const r = L.resumenSistemaDA(BUK, { armas: [{ id: "9m317e", listos: 6, reserva: 8 }, { id: "igla_s", listos: 4, reserva: 2 }], arma_elegida: "igla_s" });
  assert.equal(r.armas[0].alcance, "3–45 km");
  assert.equal(r.armas[0].pk, "75 %");
  assert.equal(r.armas[0].listos, "6 de 12");
  assert.equal(r.armas[1].reserva, "2 de 8");
  assert.equal(r.armas[0].carga, "6/12 (+8)");
  assert.equal(r.armas[1].alcance, "0,5–6 km");
  assert.equal(r.armas[0].categoria, "Largo alcance");
  assert.equal(r.elegida, "igla_s");
  assert.match(r.radar, /Vigilancia 160 km · tiro 45 km/);
  assert.match(r.reaccion, /12 s · 8 canales/);
  assert.match(r.vehiculos, /^3: 2 TELAR/);
});

test("sin estado (enemigo) muestra la dotacion de referencia y un canon sin radar lo dice", () => {
  const r = L.resumenSistemaDA(BUK, null);
  assert.equal(r.armas[0].listos, "12");
  assert.equal(r.elegida, "");
  const zu = L.resumenSistemaDA({ ...BUK, radar_vigilancia_km: 0, radar_tiro_km: 0, canales: 1 }, null);
  assert.match(zu.radar, /Sin radar: puntería óptica/);
  assert.match(zu.reaccion, /1 canal de tiro/);
  assert.equal(L.resumenSistemaDA(null, null), null);
});
